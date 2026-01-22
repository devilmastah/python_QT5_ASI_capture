import json
import threading
import time
from dataclasses import dataclass
import zmq


@dataclass
class RpcResult:
    ok: bool
    result: dict | None = None
    error: str | None = None


class ControlAPI:
    """
    Implement these methods in main and pass an instance into ZmqServer.
    All methods should be blocking and return quickly unless explicitly expected.
    """
    def set_exposure_ms(self, exposure_ms: int) -> RpcResult:
        raise NotImplementedError

    def set_gain(self, gain: int) -> RpcResult:
        raise NotImplementedError

    def set_stack_n(self, n: int) -> RpcResult:
        raise NotImplementedError

    def take_snapshot(self) -> RpcResult:
        raise NotImplementedError

    def get_state(self) -> RpcResult:
        raise NotImplementedError


class ZmqServer:
    def __init__(self, api: ControlAPI, bind_addr: str = "tcp://127.0.0.1:5555"):
        self.api = api
        self.bind_addr = bind_addr

        self._ctx = None
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            if self._sock is not None:
                self._sock.close(0)
        except Exception:
            pass
        try:
            if self._ctx is not None:
                self._ctx.term()
        except Exception:
            pass

    def _run(self):
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.REP)
        self._sock.linger = 0
        self._sock.bind(self.bind_addr)

        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)

        while not self._stop.is_set():
            try:
                events = dict(poller.poll(100))
            except Exception:
                time.sleep(0.05)
                continue

            if self._sock not in events:
                continue

            try:
                raw = self._sock.recv()
                req = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._send({"ok": False, "error": f"bad request: {e}"})
                continue

            resp = self._handle(req)
            self._send(resp)

    def _send(self, obj: dict):
        try:
            self._sock.send(json.dumps(obj).encode("utf-8"))
        except Exception:
            pass

    def _handle(self, req: dict) -> dict:
        cmd = req.get("cmd", None)
        args = req.get("args", {}) or {}

        try:
            if cmd == "set_exposure_ms":
                exposure_ms = int(args.get("value"))
                r = self.api.set_exposure_ms(exposure_ms)

            elif cmd == "set_gain":
                gain = int(args.get("value"))
                r = self.api.set_gain(gain)

            elif cmd == "set_stack_n":
                n = int(args.get("value"))
                r = self.api.set_stack_n(n)

            elif cmd == "take_snapshot":
                r = self.api.take_snapshot()

            elif cmd == "get_state":
                r = self.api.get_state()

            else:
                return {"ok": False, "error": "unknown cmd"}

        except Exception as e:
            return {"ok": False, "error": str(e)}

        if not r.ok:
            return {"ok": False, "error": r.error or "error"}

        return {"ok": True, "result": r.result or {}}
