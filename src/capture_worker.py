from PyQt5 import QtCore
from asi_camera import ASICamera
from settings_manager import SettingsManager


class CaptureWorker(QtCore.QObject):
    frame_ready = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)

    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self.camera = None
        self._timer = None
        self._running = False

        self._pending_exposure_us = int(self.settings.data.get("exposure_us", 5000))
        self._pending_gain = int(self.settings.data.get("gain", 50))

    @QtCore.pyqtSlot()
    def start(self):
        self._running = True
        try:
            self.camera = ASICamera(camera_index=0, sdk_path=None)
            self.status.emit("Camera connected.")
            self.camera.set_exposure_us(self._pending_exposure_us)
            self.camera.set_gain(self._pending_gain)
        except Exception as e:
            self.error.emit(f"Camera init failed:\n{e}")
            self._running = False
            return

        self._timer = QtCore.QTimer()
        self._timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._timer.timeout.connect(self._grab_one_frame)
        self._timer.start(0)

    @QtCore.pyqtSlot()
    def stop(self):
        self._running = False

        try:
            if self._timer:
                self._timer.stop()
        except Exception:
            pass

        try:
            if self.camera:
                self.camera.close()
        except Exception:
            pass
        self.camera = None

    @QtCore.pyqtSlot()
    def _grab_one_frame(self):
        if not self._running or not self.camera:
            return
        try:
            frame = self.camera.get_frame()
            self.frame_ready.emit(frame)
        except Exception as e:
            self.error.emit(f"Capture failed:\n{e}")
            self.stop()

    @QtCore.pyqtSlot(int)
    def set_exposure_us(self, exposure_us: int):
        self._pending_exposure_us = int(exposure_us)
        self.settings.set("exposure_us", int(exposure_us))
        try:
            if self.camera:
                self.camera.set_exposure_us(int(exposure_us))
        except Exception:
            pass

    @QtCore.pyqtSlot(int)
    def set_gain(self, gain: int):
        self._pending_gain = int(gain)
        self.settings.set("gain", int(gain))
        try:
            if self.camera:
                self.camera.set_gain(int(gain))
        except Exception:
            pass
