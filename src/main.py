import os
import sys
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from server import ZmqServer
from server_bridge import ServerBridge

from settings_manager import SettingsManager
from capture_worker import CaptureWorker
from video_label import VideoLabel
from ui_distortion_crop_dialog import DistortionWindow
from image_display import gray16_to_qimage_bytes, gray16_to_qimage_8bit_preview

from distortion import DistortionCorrector
from crop import apply_crop_if_enabled

from snapshot import SnapshotManager


class MainWindow(QtWidgets.QMainWindow):
    exposure_changed = QtCore.pyqtSignal(int)  # microseconds
    gain_changed = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASI Live View")

        self._last_frame16 = None
        self._qimg_buf = None

        self.distortion = DistortionCorrector()

        self._crop_selecting = False
        self._crop_points = []

        self._display = {
            "frame_w": None,
            "frame_h": None,
            "scaled_w": None,
            "scaled_h": None,
            "offset_x": 0,
            "offset_y": 0,
        }

        self._frame_counter = 0

        self.settings_path = os.path.join(os.getcwd(), "settings.json")
        self.settings = SettingsManager(self.settings_path)
        self.settings.load()

        if "crop" not in self.settings.data:
            self.settings.set("crop", {"enabled": False, "rect": None})

        if "dark" not in self.settings.data:
            self.settings.set("dark", {"enabled": False, "path": None, "exposure_us": None, "gain": None})

        if "flat" not in self.settings.data:
            self.settings.set("flat", {"enabled": False, "path": None, "exposure_us": None, "gain": None})

        if "snapshot" not in self.settings.data:
            self.settings.set("snapshot", {"stack_n": 1})

        self._build_ui()

        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.settings.save)

        self.thread = QtCore.QThread(self)
        self.worker = CaptureWorker(self.settings)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.start)
        self.exposure_changed.connect(self.worker.set_exposure_us, QtCore.Qt.QueuedConnection)
        self.gain_changed.connect(self.worker.set_gain, QtCore.Qt.QueuedConnection)

        self.worker.frame_ready.connect(self.on_frame_ready)
        self.worker.error.connect(self.on_worker_error)
        self.worker.status.connect(self.image_label.setText)

        self.thread.start()

        exposure_us = int(self.settings.data.get("exposure_us", 5000))
        exposure_ms = max(50, min(5000, exposure_us // 1000))

        gain = int(self.settings.data.get("gain", 50))
        gain = max(0, min(600, gain))

        self.exposure_changed.emit(exposure_ms * 1000)
        self.gain_changed.emit(gain)

        self.distortion_window = None

        self.snapshot_manager = SnapshotManager(
            settings=self.settings,
            parent_widget=self,
            get_last_frame_fn=lambda: self._last_frame16,
            get_frame_counter_fn=lambda: self._frame_counter,
        )
        self.snapshot_manager.status.connect(self._set_status)

        self.server_bridge = ServerBridge(self)
        self.server = ZmqServer(self.server_bridge, bind_addr="tcp://127.0.0.1:5555")
        self.server.start()

        self._refresh_calibration_ui_state()

    def take_snapshot_and_return_path(self) -> str:
        snap = self.settings.data.get("snapshot", {})
        n = int(snap.get("stack_n", 1))
        return self.snapshot_manager.take_snapshot(n)        

    def _set_status(self, txt: str):
        self.status_hint.setText(txt)
        self._schedule_save()
        self._refresh_calibration_ui_state()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        self.image_label = VideoLabel("Starting camera...")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.clicked.connect(self.on_video_clicked)
        main_layout.addWidget(self.image_label, stretch=1)

        right = QtWidgets.QFrame()
        right.setFrameShape(QtWidgets.QFrame.StyledPanel)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        title = QtWidgets.QLabel("Camera Controls")
        font = title.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        title.setFont(font)
        right_layout.addWidget(title)

        self.exposure_label = QtWidgets.QLabel()
        right_layout.addWidget(self.exposure_label)

        self.exposure_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.exposure_slider.setMinimum(50)
        self.exposure_slider.setMaximum(5000)
        self.exposure_slider.setSingleStep(10)
        self.exposure_slider.setPageStep(100)
        right_layout.addWidget(self.exposure_slider)

        self.gain_label = QtWidgets.QLabel()
        right_layout.addWidget(self.gain_label)

        self.gain_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.gain_slider.setMinimum(0)
        self.gain_slider.setMaximum(600)
        self.gain_slider.setSingleStep(1)
        self.gain_slider.setPageStep(10)
        right_layout.addWidget(self.gain_slider)

        self.distort_btn = QtWidgets.QPushButton("Distortion calibration")
        right_layout.addWidget(self.distort_btn)

        line1 = QtWidgets.QFrame()
        line1.setFrameShape(QtWidgets.QFrame.HLine)
        line1.setFrameShadow(QtWidgets.QFrame.Sunken)
        right_layout.addWidget(line1)

        calib_title = QtWidgets.QLabel("Calibration Frames")
        f2 = calib_title.font()
        f2.setBold(True)
        calib_title.setFont(f2)
        right_layout.addWidget(calib_title)

        self.dark_btn = QtWidgets.QPushButton("Capture Dark (10 frames)")
        right_layout.addWidget(self.dark_btn)

        self.use_dark_cb = QtWidgets.QCheckBox("Use Dark")
        right_layout.addWidget(self.use_dark_cb)

        self.flat_btn = QtWidgets.QPushButton("Capture Flat (10 frames)")
        right_layout.addWidget(self.flat_btn)

        self.use_flat_cb = QtWidgets.QCheckBox("Use Flat")
        right_layout.addWidget(self.use_flat_cb)

        line2 = QtWidgets.QFrame()
        line2.setFrameShape(QtWidgets.QFrame.HLine)
        line2.setFrameShadow(QtWidgets.QFrame.Sunken)
        right_layout.addWidget(line2)

        snap_title = QtWidgets.QLabel("Snapshot")
        f3 = snap_title.font()
        f3.setBold(True)
        snap_title.setFont(f3)
        right_layout.addWidget(snap_title)

        self.stack_label = QtWidgets.QLabel()
        right_layout.addWidget(self.stack_label)

        self.stack_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.stack_slider.setMinimum(1)
        self.stack_slider.setMaximum(50)
        self.stack_slider.setSingleStep(1)
        self.stack_slider.setPageStep(5)
        right_layout.addWidget(self.stack_slider)

        self.snapshot_btn = QtWidgets.QPushButton("Take Snapshot")
        right_layout.addWidget(self.snapshot_btn)

        self.status_hint = QtWidgets.QLabel("")
        right_layout.addWidget(self.status_hint)

        right_layout.addStretch(1)
        main_layout.addWidget(right, stretch=0)

        exposure_us = int(self.settings.data.get("exposure_us", 5000))
        exposure_ms = max(50, min(5000, exposure_us // 1000))

        gain = int(self.settings.data.get("gain", 50))
        gain = max(0, min(600, gain))

        self.exposure_slider.blockSignals(True)
        self.gain_slider.blockSignals(True)
        self.exposure_slider.setValue(exposure_ms)
        self.gain_slider.setValue(gain)
        self.exposure_slider.blockSignals(False)
        self.gain_slider.blockSignals(False)

        self._update_exposure_label(exposure_ms)
        self._update_gain_label(gain)

        stack_n = int(self.settings.data.get("snapshot", {}).get("stack_n", 1))
        stack_n = max(1, min(50, stack_n))
        self.stack_slider.blockSignals(True)
        self.stack_slider.setValue(stack_n)
        self.stack_slider.blockSignals(False)
        self._update_stack_label(stack_n)

        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)
        self.gain_slider.valueChanged.connect(self.on_gain_changed)
        self.distort_btn.clicked.connect(self.open_distortion_window)

        self.dark_btn.clicked.connect(lambda: self.snapshot_manager.capture_dark(10))
        self.flat_btn.clicked.connect(lambda: self.snapshot_manager.capture_flat(10))
        self.use_dark_cb.stateChanged.connect(self.on_use_dark_changed)
        self.use_flat_cb.stateChanged.connect(self.on_use_flat_changed)
        self.stack_slider.valueChanged.connect(self.on_stack_changed)

        self.snapshot_btn.clicked.connect(self.take_snapshot)

    def _update_exposure_label(self, exposure_ms: int):
        self.exposure_label.setText(f"Exposure: {exposure_ms} ms")

    def _update_gain_label(self, gain: int):
        self.gain_label.setText(f"Gain: {gain}")

    def _update_stack_label(self, n: int):
        self.stack_label.setText(f"Stack frames: {n}")

    def _schedule_save(self):
        self._save_timer.start(250)

    def on_exposure_changed(self, exposure_ms: int):
        self._update_exposure_label(exposure_ms)
        self._schedule_save()
        self.exposure_changed.emit(int(exposure_ms) * 1000)

    def on_gain_changed(self, gain: int):
        self._update_gain_label(gain)
        self._schedule_save()
        self.gain_changed.emit(int(gain))

    def on_stack_changed(self, n: int):
        n = int(n)
        self._update_stack_label(n)
        snap = self.settings.data.get("snapshot", {})
        snap["stack_n"] = n
        self.settings.set("snapshot", snap)
        self._schedule_save()

    def take_snapshot(self):
        self.take_snapshot_and_return_path()

    def _refresh_calibration_ui_state(self):
        dark = self.settings.data.get("dark", {})
        flat = self.settings.data.get("flat", {})

        dark_path = dark.get("path", None)
        has_dark = bool(dark_path and isinstance(dark_path, str) and len(dark_path) > 0 and os.path.exists(dark_path))

        flat_path = flat.get("path", None)
        has_flat = bool(flat_path and isinstance(flat_path, str) and len(flat_path) > 0 and os.path.exists(flat_path))

        self.use_dark_cb.blockSignals(True)
        self.use_flat_cb.blockSignals(True)

        self.use_dark_cb.setChecked(bool(dark.get("enabled", False)) and has_dark)
        self.use_flat_cb.setChecked(bool(flat.get("enabled", False)) and has_flat)

        self.use_dark_cb.blockSignals(False)
        self.use_flat_cb.blockSignals(False)

        self.flat_btn.setEnabled(has_dark)
        self.use_flat_cb.setEnabled(has_flat)

        if not has_flat:
            flat["enabled"] = False
            self.settings.set("flat", flat)
            self._schedule_save()

    def on_use_dark_changed(self, state: int):
        dark = self.settings.data.get("dark", {})
        dark["enabled"] = bool(state == QtCore.Qt.Checked)
        self.settings.set("dark", dark)
        self._schedule_save()

    def on_use_flat_changed(self, state: int):
        flat = self.settings.data.get("flat", {})
        flat["enabled"] = bool(state == QtCore.Qt.Checked)
        self.settings.set("flat", flat)
        self._schedule_save()

    def open_distortion_window(self):
        if self.distortion_window is None:
            self.distortion_window = DistortionWindow(self.settings, parent=self)
            self.distortion_window.changed.connect(self.on_calibration_changed)
            self.distortion_window.request_crop_selection.connect(self.begin_crop_selection)

        self.distortion_window.show()
        self.distortion_window.raise_()
        self.distortion_window.activateWindow()
        self.distortion_window.update_crop_rect_display()

    @QtCore.pyqtSlot()
    def on_calibration_changed(self):
        self._schedule_save()
        self.distortion.invalidate()

    def begin_crop_selection(self):
        crop = self.settings.data.get("crop", {})
        crop["enabled"] = False
        self.settings.set("crop", crop)
        self._schedule_save()

        self._crop_selecting = True
        self._crop_points = []
        self.status_hint.setText("Crop selection: click 4 points on the image")

        if self.distortion_window:
            self.distortion_window.update_crop_rect_display()

    def _finish_crop_selection(self):
        if len(self._crop_points) != 4:
            return

        xs = sorted([p[0] for p in self._crop_points])
        ys = sorted([p[1] for p in self._crop_points])

        x0, x1 = xs[1], xs[2]
        y0, y1 = ys[1], ys[2]

        if self._last_frame16 is not None:
            h, w = self._last_frame16.shape
            x0 = max(0, min(w - 2, x0))
            x1 = max(1, min(w - 1, x1))
            y0 = max(0, min(h - 2, y0))
            y1 = max(1, min(h - 1, y1))

        if x1 <= x0 or y1 <= y0:
            self.status_hint.setText("Crop selection failed. Try again.")
            self._crop_selecting = False
            self._crop_points = []
            return

        crop = self.settings.data.get("crop", {})
        crop["rect"] = [int(x0), int(y0), int(x1), int(y1)]
        crop["enabled"] = True
        self.settings.set("crop", crop)
        self._schedule_save()

        self._crop_selecting = False
        self._crop_points = []
        self.status_hint.setText("")

        if self.distortion_window:
            self.distortion_window.update_crop_rect_display()

    def _label_to_frame_coords(self, lx: int, ly: int):
        fw = self._display["frame_w"]
        fh = self._display["frame_h"]
        sw = self._display["scaled_w"]
        sh = self._display["scaled_h"]
        ox = self._display["offset_x"]
        oy = self._display["offset_y"]

        if fw is None or fh is None or sw is None or sh is None:
            return None
        if lx < ox or ly < oy or lx >= ox + sw or ly >= oy + sh:
            return None

        nx = (lx - ox) / float(sw)
        ny = (ly - oy) / float(sh)

        x = int(round(nx * (fw - 1)))
        y = int(round(ny * (fh - 1)))
        return x, y

    @QtCore.pyqtSlot(int, int)
    def on_video_clicked(self, lx: int, ly: int):
        if not self._crop_selecting:
            return

        pt = self._label_to_frame_coords(lx, ly)
        if pt is None:
            return

        self._crop_points.append(pt)
        self.status_hint.setText(f"Crop selection: {len(self._crop_points)}/4 points")

        if len(self._crop_points) >= 4:
            self._finish_crop_selection()

    @QtCore.pyqtSlot(object)
    def on_frame_ready(self, frame):
        try:
            frame = frame if isinstance(frame, np.ndarray) else np.array(frame)

            if frame.dtype != np.uint16:
                frame = frame.astype(np.uint16, copy=False)

            if frame.ndim == 3:
                frame = frame[:, :, 0]

            h, w = frame.shape
            self.distortion.ensure_maps(w, h, self.settings)
            frame = self.distortion.apply(frame)

            frame = apply_crop_if_enabled(frame, self.settings, selecting=self._crop_selecting)

            self._last_frame16 = frame
            self._frame_counter += 1

            qimg16, buf = gray16_to_qimage_bytes(frame)
            if qimg16 is not None:
                self._qimg_buf = buf
                pix = QtGui.QPixmap.fromImage(qimg16)
            else:
                qimg8, buf8 = gray16_to_qimage_8bit_preview(frame)
                self._qimg_buf = buf8
                pix = QtGui.QPixmap.fromImage(qimg8)

            label_w = max(1, self.image_label.width())
            label_h = max(1, self.image_label.height())
            pix_scaled = pix.scaled(label_w, label_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

            sw = pix_scaled.width()
            sh = pix_scaled.height()
            ox = int((label_w - sw) / 2)
            oy = int((label_h - sh) / 2)

            self._display["frame_w"] = frame.shape[1]
            self._display["frame_h"] = frame.shape[0]
            self._display["scaled_w"] = sw
            self._display["scaled_h"] = sh
            self._display["offset_x"] = ox
            self._display["offset_y"] = oy

            self.image_label.setPixmap(pix_scaled)

        except Exception as e:
            self.image_label.setText(f"Display failed:\n{e}")

    @QtCore.pyqtSlot(str)
    def on_worker_error(self, msg: str):
        self.image_label.setText(msg)

    def closeEvent(self, event):
        try:
            self._save_timer.stop()
            try:
                self.settings.save()
            except Exception:
                pass

            if self.worker:
                QtCore.QMetaObject.invokeMethod(self.worker, "stop", QtCore.Qt.QueuedConnection)

            try:
                self.server.stop()
            except Exception:
                pass

            if self.thread:
                self.thread.quit()
                self.thread.wait(2000)
        finally:
            event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
