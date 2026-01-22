import cv2
import numpy as np


class DistortionCalibrator:
    """
    Chessboard based calibration using OpenCV pinhole model with k1,k2,p1,p2,k3.
    Good for barrel and pincushion distortion.

    Default chessboard: 9x6 inner corners (common).
    Adjust CHESSBOARD_SIZE if your printed board is different.
    """

    CHESSBOARD_SIZE = (9, 6)   # inner corners: columns, rows
    SQUARE_SIZE = 1.0          # arbitrary units, only matters if you care about real scale

    def __init__(self):
        self.objpoints = []
        self.imgpoints = []
        self.image_size = None

        objp = np.zeros((self.CHESSBOARD_SIZE[0] * self.CHESSBOARD_SIZE[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.CHESSBOARD_SIZE[0], 0:self.CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
        objp *= float(self.SQUARE_SIZE)
        self._objp_template = objp

    def try_add_frame(self, frame_gray_u8: np.ndarray) -> tuple[bool, np.ndarray | None]:
        """
        Attempts to find chessboard corners and add them.

        Returns:
          ok: bool
          debug_bgr: optional debug image with drawn corners
        """
        if frame_gray_u8.ndim != 2:
            raise ValueError("Expected 2D grayscale image")

        self.image_size = (frame_gray_u8.shape[1], frame_gray_u8.shape[0])

        found, corners = cv2.findChessboardCorners(
            frame_gray_u8,
            self.CHESSBOARD_SIZE,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        debug = cv2.cvtColor(frame_gray_u8, cv2.COLOR_GRAY2BGR)

        if not found:
            return False, debug

        term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners2 = cv2.cornerSubPix(frame_gray_u8, corners, (11, 11), (-1, -1), term)

        self.objpoints.append(self._objp_template.copy())
        self.imgpoints.append(corners2)

        cv2.drawChessboardCorners(debug, self.CHESSBOARD_SIZE, corners2, found)
        return True, debug

    def can_calibrate(self) -> bool:
        return len(self.objpoints) >= 8 and self.image_size is not None

    def calibrate(self) -> dict:
        """
        Returns dict suitable for storing in settings.json
        """
        if not self.can_calibrate():
            raise RuntimeError("Need at least 8 good frames with detected chessboard corners.")

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self.objpoints,
            self.imgpoints,
            self.image_size,
            None,
            None
        )

        return {
            "distortion_enabled": True,
            "image_size": [int(self.image_size[0]), int(self.image_size[1])],
            "camera_matrix": mtx.tolist(),
            "dist_coeffs": dist.reshape(-1).tolist(),
            "reprojection_error": float(ret),
        }


def build_undistort_maps(calib: dict):
    """
    Precompute remap matrices for fast undistortion.
    """
    w, h = calib["image_size"]
    mtx = np.array(calib["camera_matrix"], dtype=np.float64)
    dist = np.array(calib["dist_coeffs"], dtype=np.float64).reshape(-1, 1)

    new_mtx, _ = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 0)
    map1, map2 = cv2.initUndistortRectifyMap(mtx, dist, None, new_mtx, (w, h), cv2.CV_16SC2)
    return map1, map2
