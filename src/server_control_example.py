import zmq, json

ctx = zmq.Context()
s = ctx.socket(zmq.REQ)
s.connect("tcp://127.0.0.1:5555")

def call(cmd, **args):
    s.send(json.dumps({"cmd": cmd, "args": args}).encode("utf-8"))
    return json.loads(s.recv().decode("utf-8"))

print(call("set_exposure_ms", value=50))
print(call("set_gain", value=48))
print(call("set_stack_n", value=15))
resp = call("take_snapshot")
print(resp)