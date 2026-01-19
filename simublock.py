import hashlib, time, random, threading, os, queue
from flask import Flask, Response

# ----------------- EVENT BUS -----------------

event_bus = queue.Queue()

def emit(event):
    event_bus.put(event)

# ----------------- CORE -----------------

class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount

    def __repr__(self):
        return f"{self.sender} → {self.receiver} : {self.amount}"


class Block:
    def __init__(self, index, prev_hash, txs, nonce=0):
        self.index = index
        self.prev_hash = prev_hash
        self.txs = txs
        self.nonce = nonce
        self.timestamp = time.time()
        self.hash = self.compute_hash()

    def compute_hash(self):
        s = f"{self.index}{self.prev_hash}{self.txs}{self.nonce}{self.timestamp}"
        return hashlib.sha256(s.encode()).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = [self.genesis()]
        self.state = {"Alice": 100, "Bob": 100, "Miner": 0}

    def genesis(self):
        return Block(0, "0", [])

    def last(self):
        return self.chain[-1]

    def add_block(self, block):
        if block.prev_hash == self.last().hash:
            self.apply(block)
            self.chain.append(block)
            emit(f"BLOCK #{block.index} added | hash {block.hash[:12]}...")
            return True
        return False

    def apply(self, block):
        for tx in block.txs:
            if self.state.get(tx.sender, 0) >= tx.amount:
                self.state[tx.sender] -= tx.amount
                self.state[tx.receiver] = self.state.get(tx.receiver, 0) + tx.amount
                emit(f"TX confirmed: {tx}")

# ----------------- CONSENSUS -----------------

def mine(block, difficulty):
    while not block.hash.startswith("0" * difficulty):
        block.nonce += 1
        block.hash = block.compute_hash()
    return block

# ----------------- NODE -----------------

class Node:
    def __init__(self, nid, network, selfish=False):
        self.id = nid
        self.bc = Blockchain()
        self.network = network
        self.selfish = selfish
        self.private_chain = []

    def create_tx(self):
        tx = Transaction("Alice", "Bob", random.randint(1, 5))
        emit(f"TX created: {tx}")
        return tx

    def mine_loop(self):
        while len(self.bc.chain) < 20:
            txs = [self.create_tx()]
            b = Block(len(self.bc.chain), self.bc.last().hash, txs)
            emit(f"Node {self.id} mining block {b.index}")
            b = mine(b, difficulty=3)
            emit(f"Node {self.id} mined block {b.index}")

            if self.selfish:
                self.private_chain.append(b)
                if len(self.private_chain) >= 2:
                    for pb in self.private_chain:
                        self.network.broadcast(pb)
                    self.private_chain.clear()
            else:
                self.network.broadcast(b)

# ----------------- NETWORK -----------------

class Network:
    def __init__(self, delay=(0.1, 0.3)):
        self.nodes = []
        self.delay = delay

    def add(self, n):
        self.nodes.append(n)

    def broadcast(self, block):
        for n in self.nodes:
            time.sleep(random.uniform(*self.delay))
            n.bc.add_block(block)

# ----------------- SIMULATION -----------------

def start_simulation():
    net = Network()
    nodes = [
        Node(0, net),
        Node(1, net),
        Node(2, net, selfish=True)
    ]
    for n in nodes:
        net.add(n)

    threads = []
    for n in nodes:
        t = threading.Thread(target=n.mine_loop, daemon=True)
        t.start()
        threads.append(t)

# ----------------- WEB LAYER -----------------

app = Flask(__name__)

@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<title>SimuBlock Live</title>
<style>
body { font-family: monospace; background:#0f0f14; color:#e0e0ff; }
h2 { color:#7aa2ff; }
#feed { height:80vh; overflow:auto; border:1px solid #333; padding:10px; }
</style>
</head>
<body>
<h2>SimuBlock – Live Blockchain</h2>
<div id="feed"></div>

<script>
const feed = document.getElementById("feed");
const es = new EventSource("/stream");
es.onmessage = e => {
  const d = document.createElement("div");
  d.textContent = e.data;
  feed.prepend(d);
};
</script>
</body>
</html>
"""

@app.route("/stream")
def stream():
    def gen():
        while True:
            msg = event_bus.get()
            yield f"data: {msg}\\n\\n"
    return Response(gen(), mimetype="text/event-stream")

# ----------------- ENTRY -----------------

if __name__ == "__main__":
    start_simulation()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)
