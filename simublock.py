import hashlib, time, random, threading, queue, os
from flask import Flask, Response

app = Flask(__name__)
event_bus = queue.Queue()

def emit(msg):
    event_bus.put(msg)

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
    while len(bc.chain) < 12:
        tx = Transaction("Alice","Bob",random.randint(1,3))
        emit(f"TX created {tx}")
        b = Block(len(bc.chain), bc.last().h, [tx])
        emit("Mining...")
        mine(b,2)
        bc.add(b)
        time.sleep(0.3)

# ---------------- WEB ----------------

@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<body style="background:#0f0f14;color:#e0e0ff;font-family:monospace">
<h2>SimuBlock Live</h2>
<div id="status">Connecting...</div>
<div id="feed"></div>
<script>
let s=document.getElementById("status");
let f=document.getElementById("feed");
let es=new EventSource("/stream");
es.onopen=()=>s.textContent="Connected";
es.onerror=()=>s.textContent="Connection error";
es.onmessage=e=>{
  let d=document.createElement("div");
  d.textContent=e.data;
  f.prepend(d);
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

if __name__ == "__main__":
    port = int(os.getenv("PORT",10000))
    app.run(host="0.0.0.0", port=port)
