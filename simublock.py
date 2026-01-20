import hashlib, time, random, threading, queue, os
from flask import Flask, Response

import csv

app = Flask(__name__)
event_bus = queue.Queue()
mine_event = threading.Event()


EXPERIMENT = {
    "difficulty": 2,
    "max_blocks": 50,
    "block_capacity": 5,     #ops per block
    "op_interval": 0.0,      # seconds between ops
    "run_id": int(time.time())
}

metrics = {
    "block_times": [],
    "ops_committed": 0,
    "start_time": None
}


chain_running = False

def emit(msg):
    event_bus.put(msg)

from flask import request, jsonify

pending_ops = []

# ---------------- CORE ----------------

class Operation:
    def __init__(self, user, action, data):
        self.user = user
        self.action = action
        self.data = data

    def __repr__(self):
        return f"{self.user} | {self.action} | {self.data}"

class Block:
    def __init__(self, i, prev, ops):
        self.i = i
        self.prev = prev
        self.ops = ops   # operations, not transactions
        self.nonce = 0
        self.ts = time.time()
        self.h = self.hash()

    def hash(self):
        return hashlib.sha256(
            f"{self.i}{self.prev}{self.ops}{self.nonce}{self.ts}".encode()
        ).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [Block(0, "0", [])]

    def last(self):
        return self.chain[-1]

    def add(self, block):
        if block.prev == self.last().h:
            self.chain.append(block)
            emit(f"BLOCK {block.i} committed")


def mine(b,d=2):
    while not b.h.startswith("0"*d):
        b.nonce+=1
        b.h=b.hash()
    return b

def run_sim():
    global chain_running

    bc = Blockchain()
    app.blockchain = bc
    metrics["start_time"] = time.time()
    emit("Simulation initialized")

    while len(bc.chain) < EXPERIMENT["max_blocks"]:

        # Governance pause
        if not chain_running:
            time.sleep(0.2)
            continue

        # ⛔ WAIT for explicit mining trigger
        mine_event.wait()

        # If no ops, consume trigger and do nothing
        if not pending_ops:
            emit("No operations to mine")
            mine_event.clear()
            continue

        # -------------------------
        # Batch operations
        # -------------------------
        ops = []
        while pending_ops and len(ops) < EXPERIMENT["block_capacity"]:
            ops.append(pending_ops.pop(0))

        emit(f"Mining block with {len(ops)} operations")

        t0 = time.time()
        block = Block(len(bc.chain), bc.last().h, ops)
        mine(block, EXPERIMENT["difficulty"])
        bc.add(block)

        metrics["block_times"].append(time.time() - t0)
        metrics["ops_committed"] += len(ops)

        # ⛔ consume the trigger
        mine_event.clear()

    emit("Simulation completed")


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

<button onclick="fetch('/start',{method:'POST'})">▶ Start</button>
<button onclick="fetch('/stop',{method:'POST'})">⏸ Stop</button>
<button onclick="loadChain()">🔍 Refresh Explorer</button>
<button onclick="loadMetrics()">📊 Metrics</button>
<pre id="metrics"></pre>

<div id="status">Connecting...</div>

<h3>Live Feed</h3>
<div id="feed" style="height:40vh;overflow:auto;border:1px solid #333"></div>

<h3>Operations</h3>
<form id="opForm">
  <input id="user" placeholder="User" required />
  <input id="action" placeholder="Action" required />
  <input id="data" placeholder="Data" required />
  <button type="submit">Submit Operation</button>
</form>

<button onclick="triggerMine()">⛏ Mine Block</button>


<h3>Block Explorer</h3>
<pre id="explorer" style="background:#111;padding:8px;height:30vh;overflow:auto"></pre>

<script>
const status = document.getElementById("status");
const feed = document.getElementById("feed");
const explorer = document.getElementById("explorer");

const es = new EventSource("/stream");
es.onopen = () => status.textContent = "Connected";
es.onerror = () => status.textContent = "Connection error";
es.onmessage = e => {
  const d = document.createElement("div");
  d.textContent = e.data;
  feed.prepend(d);
};

document.getElementById("opForm").onsubmit = async e => {
  e.preventDefault();
  await fetch("/op", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      user:user.value,
      action:action.value,
      data:data.value
    })
  });
};

async function loadChain(){
  const res = await fetch("/chain");
  const data = await res.json();
  explorer.textContent = JSON.stringify(data, null, 2);
}

async function loadMetrics(){
  const r = await fetch("/metrics");
  document.getElementById("metrics").textContent =
    JSON.stringify(await r.json(), null, 2);
}

document.getElementById("opForm").onsubmit = async e => {
  e.preventDefault();
  await fetch("/op", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      user:user.value,
      action:action.value,
      data:data.value
    })
  });
};

function triggerMine(){
  fetch("/mine", {method:"POST"});
}

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

@app.route("/start", methods=["POST"])
def start_chain():
    global chain_running
    chain_running = True
    emit("Blockchain started")
    return {"status": "running"}

@app.route("/stop", methods=["POST"])
def stop_chain():
    global chain_running
    chain_running = False
    emit("Blockchain stopped")
    return {"status": "stopped"}

@app.route("/chain")
def chain_view():
    bc = getattr(app, "blockchain", None)
    if not bc:
        return {"chain": []}

    return {
        "chain": [
            {
                "index": b.i,
                "hash": b.h,
                "prev": b.prev,
                "timestamp": b.ts,
                "operations": [str(op) for op in b.ops]
            }
            for b in bc.chain
        ]
    }

@app.route("/metrics")
def get_metrics():
    duration = time.time() - metrics["start_time"] if metrics["start_time"] else 0
    avg_block_time = (
        sum(metrics["block_times"]) / len(metrics["block_times"])
        if metrics["block_times"] else 0
    )

    return {
        "run_id": EXPERIMENT["run_id"],
        "difficulty": EXPERIMENT["difficulty"],
        "blocks": len(metrics["block_times"]),
        "ops_committed": metrics["ops_committed"],
        "avg_block_time": avg_block_time,
        "runtime_sec": duration
    }

@app.route("/metrics.csv")
def metrics_csv():
    def gen():
        yield "block_index,block_time\n"
        for i, t in enumerate(metrics["block_times"]):
            yield f"{i},{t}\n"

    return Response(gen(), mimetype="text/csv")

@app.route("/mine", methods=["POST"])
def mine_block():
    mine_event.set()
    emit("Mining triggered by user")
    return {"status": "mining triggered"}





if __name__ == "__main__":
    port = int(os.getenv("PORT",10000))
    app.run(host="0.0.0.0", port=port)



