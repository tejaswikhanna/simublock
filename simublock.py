import hashlib, time, random, threading, queue, os
import threading
from flask import Flask, Response
from config import EXPERIMENT
from core.block import Block, Operation
from core.blockchain import Blockchain
import sim.engine as engine
from sim.engine import mine_event, start_sim
import csv

threading.Thread(
    target=start_sim,
    args=(app, emit, pending_ops, metrics, EXPERIMENT),
    daemon=True
).start()

app = Flask(__name__)
event_bus = queue.Queue()


metrics = {
    "block_times": [],
    "ops_committed": 0,
    "start_time": None
}


def emit(msg):
    event_bus.put(msg)

from flask import request, jsonify

pending_ops = []

# ---------------- CORE ----------------

def mine(b,d=2):
    while not b.h.startswith("0"*d):
        b.nonce+=1
        b.h=b.hash()
    return b

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
        while True:
            try:
                msg = event_bus.get(timeout=2)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield "data: [heartbeat]\n\n"
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
    engine.chain_running = True
    emit("Blockchain started")
    return {"status": "running"}

@app.route("/stop", methods=["POST"])
def stop_chain():
    engine.chain_running = False
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
            for b in app.blockchain.chain
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



