import os
import time
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from calibration_frames import (
    save_tiff16,
    save_flat_float,
    make_master_dark,
    make_master_flat,
)

from image_display import gray16_to_qimage_bytes, gray16_to_qimage_8bit_preview


class SnapshotPreviewDialog(QtWidgets.QDialog):
    def __init__(self, frame16: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snapshot Preview")
        self.resize(1100, 800)

        self._buf = None
        self._last_frame16 = frame16

        layout = QtWidgets.QVBoxLayout(self)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.label, stretch=1)

        btns = QtWidgets.QHBoxLayout()
        layout.addLayout(btns)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btns.addStretch(1)
        btns.addWidget(close_btn)

        self._render()

    def set_frame(self, frame16: np.ndarray):
        self._last_frame16 = frame16
        self._render()

    def _render(self):
        frame16 = self._last_frame16

        qimg16, buf = gray16_to_qimage_bytes(frame16)
        if qimg16 is not None:
            self._buf = buf
            pix = QtGui.QPixmap.fromImage(qimg16)
        else:
            qimg8, buf8 = gray16_to_qimage_8bit_preview(frame16)
            self._buf = buf8
            pix = QtGui.QPixmap.fromImage(qimg8)

        pix_scaled = pix.scaled(
            self.label.width(), self.label.height(),
            QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )
        self.label.setPixmap(pix_scaled)

    def resizeEvent(self, event):
        self._render()
        super().resizeEvent(event)


class SnapshotManager(QtCore.QObject):
    status = QtCore.pyqtSignal(str)

    def __init__(self, settings, parent_widget: QtWidgets.QWidget, get_last_frame_fn, get_frame_counter_fn):
        super().__init__(parent_widget)
        self.settings = settings
        self.parent_widget = parent_widget

        self.get_last_frame = get_last_frame_fn
        self.get_counter = get_frame_counter_fn

        self._preview = None

    def _wait_for_new_frame(self, start_counter: int, timeout_s: float = 20.0) -> bool:
        t0 = time.time()
        while self.get_counter() <= start_counter:
            QtWidgets.QApplication.processEvents()
            time.sleep(0.01)
            if (time.time() - t0) >= timeout_s:
                return False
        return True

    def _capture_n_frames(self, n: int, title: str):
        if self.get_last_frame() is None:
            QtWidgets.QMessageBox.warning(self.parent_widget, "No frames", "No camera frames yet.")
            return None

        progress = QtWidgets.QProgressDialog(title, "Cancel", 0, n, self.parent_widget)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)

        frames = []
        last_counter = self.get_counter()

        for i in range(n):
            if progress.wasCanceled():
                break

            ok = self._wait_for_new_frame(last_counter, timeout_s=60.0)
            if not ok:
                break

            last_counter = self.get_counter()
            fr = self.get_last_frame()
            if fr is not None:
                frames.append(fr.copy())

            progress.setValue(i + 1)

        progress.close()

        if len(frames) != n:
            QtWidgets.QMessageBox.warning(
                self.parent_widget,
                "Capture incomplete",
                f"Captured {len(frames)} of {n} frames.",
            )
            return None

        return frames

    def _stack_median_uint16(self, frames_u16: list[np.ndarray]) -> np.ndarray:
        stack = np.stack(frames_u16, axis=0).astype(np.float32)
        out = np.median(stack, axis=0)
        return np.clip(out, 0, 65535).astype(np.uint16)

    def _load_master_dark(self):
        dark = self.settings.data.get("dark", {})
        if not bool(dark.get("enabled", False)):
            return None

        path = dark.get("path", None)
        if not path or not os.path.exists(path):
            return None

        import cv2
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.ndim == 3:
            img = img[:, :, 0]
        if img.dtype != np.uint16:
            img = img.astype(np.uint16, copy=False)
        return img

    def _load_master_flat(self):
        flat = self.settings.data.get("flat", {})
        if not bool(flat.get("enabled", False)):
            return None

        path = flat.get("path", None)
        if not path or not os.path.exists(path):
            return None

        import cv2
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.ndim == 3:
            img = img[:, :, 0]
        if img.dtype != np.float32:
            img = img.astype(np.float32, copy=False)
        return img

    def capture_dark(self, n=10):
        frames = self._capture_n_frames(n, f"Capturing dark frames ({n})")
        if frames is None:
            return

        master_dark = make_master_dark(frames, method="median")

        out_dir = os.path.join(os.getcwd(), "calibration")
        os.makedirs(out_dir, exist_ok=True)
        dark_path = os.path.join(out_dir, "master_dark.tiff")

        save_tiff16(dark_path, master_dark)

        dark = self.settings.data.get("dark", {})
        dark["path"] = dark_path
        dark["enabled"] = True
        dark["exposure_us"] = int(self.settings.data.get("exposure_us", 0))
        dark["gain"] = int(self.settings.data.get("gain", 0))
        self.settings.set("dark", dark)

        flat = self.settings.data.get("flat", {})
        flat["enabled"] = False
        self.settings.set("flat", flat)

        self.status.emit("Master dark saved")

    def capture_flat(self, n=10):
        dark = self.settings.data.get("dark", {})
        dark_path = dark.get("path", None)
        if not dark_path or not os.path.exists(dark_path):
            QtWidgets.QMessageBox.warning(self.parent_widget, "No dark", "Capture a dark frame first.")
            return

        frames = self._capture_n_frames(n, f"Capturing flat frames ({n})")
        if frames is None:
            return

        master_dark = self._load_master_dark()
        if master_dark is None:
            QtWidgets.QMessageBox.warning(self.parent_widget, "Dark missing", "Could not load master dark.")
            return

        master_flat_norm = make_master_flat(frames, master_dark, method="median")

        out_dir = os.path.join(os.getcwd(), "calibration")
        os.makedirs(out_dir, exist_ok=True)
        flat_path = os.path.join(out_dir, "master_flat.tiff")

        save_flat_float(flat_path, master_flat_norm)

        flat = self.settings.data.get("flat", {})
        flat["path"] = flat_path
        flat["enabled"] = True
        flat["exposure_us"] = int(self.settings.data.get("exposure_us", 0))
        flat["gain"] = int(self.settings.data.get("gain", 0))
        self.settings.set("flat", flat)

        self.status.emit("Master flat saved")

    def take_snapshot(self, n: int):
        n = max(1, min(200, int(n)))

        frames = self._capture_n_frames(n, f"Capturing snapshot ({n} frames)")
        if frames is None:
            return

        master_dark = self._load_master_dark()
        master_flat = self._load_master_flat()

        calibrated = []
        for f in frames:
            img = f.astype(np.float32)

            if master_dark is not None and master_dark.shape == f.shape:
                img = img - master_dark.astype(np.float32)

            if master_flat is not None and master_flat.shape == f.shape:
                denom = np.clip(master_flat, 1e-6, None)
                img = img / denom

            img = np.clip(img, 0, 65535).astype(np.uint16)
            calibrated.append(img)

        out16 = self._stack_median_uint16(calibrated)

        out_dir = os.path.join(os.getcwd(), "snapshots")
        os.makedirs(out_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"snapshot_{ts}.tiff")

        save_tiff16(out_path, out16)

        self.status.emit(f"Snapshot saved: {os.path.basename(out_path)}")
        self._show_preview(out16)
        return out_path

    def _show_preview(self, frame16: np.ndarray):
        if self._preview is None or not self._preview.isVisible():
            self._preview = SnapshotPreviewDialog(frame16, parent=self.parent_widget)
        else:
            self._preview.set_frame(frame16)

        self._preview.show()
        self._preview.raise_()
        self._preview.activateWindow()
