from PyQt5 import QtCore
from server import ControlAPI, RpcResult


class ServerBridge(QtCore.QObject, ControlAPI):
    _do_set_exposure = QtCore.pyqtSignal(int)
    _do_set_gain = QtCore.pyqtSignal(int)
    _do_set_stack = QtCore.pyqtSignal(int)
    _do_snapshot = QtCore.pyqtSignal()

    _snapshot_done = QtCore.pyqtSignal(bool, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.w = main_window

        self._do_set_exposure.connect(self._on_set_exposure)
        self._do_set_gain.connect(self._on_set_gain)
        self._do_set_stack.connect(self._on_set_stack)
        self._do_snapshot.connect(self._on_snapshot)

        self._last_snapshot_ok = False
        self._last_snapshot_path = ""

    def set_exposure_ms(self, exposure_ms: int) -> RpcResult:
        self._do_set_exposure.emit(int(exposure_ms))
        return RpcResult(ok=True, result={"exposure_ms": int(exposure_ms)})

    def set_gain(self, gain: int) -> RpcResult:
        self._do_set_gain.emit(int(gain))
        return RpcResult(ok=True, result={"gain": int(gain)})

    def set_stack_n(self, n: int) -> RpcResult:
        self._do_set_stack.emit(int(n))
        return RpcResult(ok=True, result={"stack_n": int(n)})

    def take_snapshot(self) -> RpcResult:
        loop = QtCore.QEventLoop()

        def done(ok, path):
            self._last_snapshot_ok = bool(ok)
            self._last_snapshot_path = path or ""
            loop.quit()

        self._snapshot_done.connect(done)
        self._do_snapshot.emit()
        loop.exec_()
        try:
            self._snapshot_done.disconnect(done)
        except Exception:
            pass

        if not self._last_snapshot_ok:
            return RpcResult(ok=False, error="snapshot failed")
        return RpcResult(ok=True, result={"path": self._last_snapshot_path})

    def get_state(self) -> RpcResult:
        s = self.w.settings.data
        return RpcResult(ok=True, result={
            "exposure_us": int(s.get("exposure_us", 0)),
            "gain": int(s.get("gain", 0)),
            "stack_n": int(s.get("snapshot", {}).get("stack_n", 1)),
            "dark_enabled": bool(s.get("dark", {}).get("enabled", False)),
            "flat_enabled": bool(s.get("flat", {}).get("enabled", False)),
        })

    def _on_set_exposure(self, exposure_ms: int):
        exposure_ms = max(50, min(5000, int(exposure_ms)))
        self.w.exposure_slider.setValue(exposure_ms)

    def _on_set_gain(self, gain: int):
        gain = max(0, min(600, int(gain)))
        self.w.gain_slider.setValue(gain)

    def _on_set_stack(self, n: int):
        n = max(1, min(50, int(n)))
        self.w.stack_slider.setValue(n)

    def _on_snapshot(self):
        try:
            path = self.w.take_snapshot_and_return_path()
            self._snapshot_done.emit(True, path)
        except Exception:
            self._snapshot_done.emit(False, "")
