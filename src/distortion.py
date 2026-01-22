import numpy as np
import cv2


class DistortionCorrector:
    def __init__(self):
        self._map1 = None
        self._map2 = None
        self._cache_key = None

    def invalidate(self):
        self._map1 = None
        self._map2 = None
        self._cache_key = None

    def _get_params_from_settings(self, settings):
        d = settings.data.get("distortion_manual", {})
        enabled = bool(d.get("enabled", False))
        k1 = float(d.get("k1", 0.0))
        k2 = float(d.get("k2", 0.0))
        k3 = float(d.get("k3", 0.0))
        zoom = float(d.get("zoom", 1.0))
        zoom = max(0.2, min(3.0, zoom))
        return enabled, k1, k2, k3, zoom

    def ensure_maps(self, w: int, h: int, settings):
        enabled, k1, k2, k3, zoom = self._get_params_from_settings(settings)

        if not enabled:
            self.invalidate()
            return False

        key = (w, h, round(k1, 6), round(k2, 6), round(k3, 6), round(zoom, 6))
        if self._cache_key == key and self._map1 is not None and self._map2 is not None:
            return True

        cx = w / 2.0
        cy = h / 2.0

        base_f = max(w, h) * 0.9
        fx = base_f * zoom
        fy = base_f * zoom

        camera_matrix = np.array(
            [[fx, 0.0, cx],
             [0.0, fy, cy],
             [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

        dist = np.array([k1, k2, 0.0, 0.0, k3], dtype=np.float64)

        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(camera_matrix, dist, (w, h), 0.0, (w, h))
        map1, map2 = cv2.initUndistortRectifyMap(
            camera_matrix, dist, None, new_camera_matrix, (w, h), cv2.CV_16SC2
        )

        self._map1 = map1
        self._map2 = map2
        self._cache_key = key
        return True

    def apply(self, frame16: np.ndarray) -> np.ndarray:
        if self._map1 is None or self._map2 is None:
            return frame16
        return cv2.remap(frame16, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)
