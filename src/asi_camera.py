import os
from typing import Optional

import numpy as np
import zwoasi as asi


class ASICamera:
    def __init__(self, camera_index: int = 0, sdk_path: Optional[str] = None):
        self._init_sdk(sdk_path)
        self._open_camera(camera_index)

    def _init_sdk(self, sdk_path: Optional[str]) -> None:
        env_path = os.environ.get("ASI_SDK_PATH")
        chosen = sdk_path or env_path
        if chosen:
            asi.init(chosen)

    def _open_camera(self, camera_index: int) -> None:
        num = asi.get_num_cameras()
        if num <= 0:
            raise RuntimeError("No ASI cameras found")

        if camera_index < 0 or camera_index >= num:
            raise RuntimeError(f"Invalid camera_index {camera_index}. Found {num} camera(s).")

        self.cam = asi.Camera(camera_index)

        self.cam.set_image_type(asi.ASI_IMG_RAW16)
        self.cam.set_roi()

        self.cam.start_video_capture()

    def set_exposure_us(self, exposure_us: int) -> None:
        self.cam.set_control_value(asi.ASI_EXPOSURE, int(exposure_us))

    def set_gain(self, gain: int) -> None:
        self.cam.set_control_value(asi.ASI_GAIN, int(gain))

    def get_frame(self) -> np.ndarray:
        frame = self.cam.capture_video_frame()
        if not isinstance(frame, np.ndarray):
            frame = np.array(frame)

        if frame.dtype != np.uint16:
            frame = frame.astype(np.uint16, copy=False)

        if frame.ndim == 3:
            frame = frame[:, :, 0]

        return frame

    def close(self) -> None:
        try:
            self.cam.stop_video_capture()
        except Exception:
            pass
        try:
            self.cam.close()
        except Exception:
            pass
