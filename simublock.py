import hashlib, time, random, threading, queue, os
from flask import Flask, Response

app = Flask(__name__)
event_bus = queue.Queue()

def emit(msg):
    event_bus.put(msg)

from flask import request, jsonify

pending_ops = []

class Operation:
    def __init__(self, user, action, data):
        self.user = user
        self.action = action
        self.data = data

    def __repr__(self):
        return f"{self.user} | {self.action} | {self.data}"


# ---------------- CORE ----------------

class Transaction:
    def __init__(self, s, r, a):
        self.s, self.r, self.a = s, r, a
    def __repr__(self):
        return f"{self.s}→{self.r}:{self.a}"

class Block:
    def __init__(self, i, prev, txs):
        self.i = i
        self.prev = prev
        self.txs = txs
        self.nonce = 0
        self.ts = time.time()
        self.h = self.hash()
    def hash(self):
        return hashlib.sha256(f"{self.i}{self.prev}{self.txs}{self.nonce}{self.ts}".encode()).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [Block(0,"0",[])]
        self.state = {"Alice":50,"Bob":50}
    def last(self): return self.chain[-1]
    def add(self,b):
        if b.prev == self.last().h:
            for tx in b.txs:
                if self.state[tx.s] >= tx.a:
                    self.state[tx.s] -= tx.a
                    self.state[tx.r] += tx.a
                    emit(f"TX confirmed {tx}")
            self.chain.append(b)
            emit(f"BLOCK {b.i} {b.h[:10]}")

def mine(b,d=2):
    while not b.h.startswith("0"*d):
        b.nonce+=1
        b.h=b.hash()
    return b

def run_sim():
    bc = Blockchain()
    emit("Simulation started")

    while len(bc.chain) < 50:
        if not pending_ops:
            time.sleep(0.5)
            continue

        op = pending_ops.pop(0)
        emit(f"Mining block for: {op}")

        b = Block(len(bc.chain), bc.last().h, [op])
        mine(b, 2)
        bc.add(b)

# ---------------- WEB ----------------

@app.route("/")
@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<title>SimuBlock Live</title>
<style>
body { background:#0f0f14; color:#e0e0ff; font-family:monospace; }
#feed { height:60vh; overflow:auto; border:1px solid #333; padding:8px; }
form { margin-top:10px; }
input { background:#111; color:#fff; border:1px solid #444; padding:4px; }
button { background:#7aa2ff; border:none; padding:6px 10px; cursor:pointer; }
</style>
</head>
<body>
<h2>SimuBlock – Non-Financial Blockchain</h2>
<div id="status">Connecting...</div>

<div id="feed"></div>

<form id="opForm">
  <input id="user" placeholder="User" required />
  <input id="action" placeholder="Action" required />
  <input id="data" placeholder="Data" required />
  <button type="submit">Submit Operation</button>
</form>

<script>
const status = document.getElementById("status");
const feed = document.getElementById("feed");

const es = new EventSource("/stream");
es.onopen = () => status.textContent = "Connected to SimuBlock";
es.onerror = () => status.textContent = "Connection error";
es.onmessage = e => {
  const d = document.createElement("div");
  d.textContent = e.data;
  feed.prepend(d);
};

document.getElementById("opForm").onsubmit = async (e) => {
  e.preventDefault();
  const user = document.getElementById("user").value;
  const action = document.getElementById("action").value;
  const data = document.getElementById("data").value;

  await fetch("/op", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({user, action, data})
  });

  document.getElementById("action").value = "";
  document.getElementById("data").value = "";
};
</script>
</body>
</html>
"""


@app.route("/stream")
def stream():
    def gen():
        emit("Client connected")
        if not getattr(app,"started",False):
            app.started=True
            threading.Thread(target=run_sim,daemon=True).start()
        while True:
            try:
                m = event_bus.get(timeout=1)
                yield f"data: {m}\n\n"
            except:
                yield "data: .\n\n"
    return Response(gen(), mimetype="text/event-stream")

@app.route("/op", methods=["POST"])
def submit_op():
    payload = request.json or {}
    op = Operation(
        payload.get("user", "anonymous"),
        payload.get("action", "unknown"),
        payload.get("data", "")
    )
    pending_ops.append(op)
    emit(f"OP received: {op}")
    return jsonify({"status": "queued"})


if __name__ == "__main__":
    port = int(os.getenv("PORT",10000))
    app.run(host="0.0.0.0", port=port)
