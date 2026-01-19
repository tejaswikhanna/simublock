import hashlib, time, random, threading, os

# ---------- CORE ----------

class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount

    def __repr__(self):
        return f"{self.sender}->{self.receiver}:{self.amount}"


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
            return True
        return False

    def apply(self, block):
        for tx in block.txs:
            if self.state.get(tx.sender, 0) >= tx.amount:
                self.state[tx.sender] -= tx.amount
                self.state[tx.receiver] = self.state.get(tx.receiver, 0) + tx.amount


# ---------- CONSENSUS ----------

def mine(block, difficulty):
    while not block.hash.startswith("0" * difficulty):
        block.nonce += 1
        block.hash = block.compute_hash()
    return block


# ---------- NETWORK / NODE ----------

class Node:
    def __init__(self, nid, network, selfish=False):
        self.id = nid
        self.bc = Blockchain()
        self.network = network
        self.selfish = selfish
        self.private_chain = []

    def create_tx(self):
        return Transaction("Alice", "Bob", random.randint(1, 5))

    def mine_loop(self):
        while len(self.bc.chain) < 15:
            txs = [self.create_tx()]
            b = Block(len(self.bc.chain), self.bc.last().hash, txs)
            b = mine(b, difficulty=3)

            if self.selfish:
                self.private_chain.append(b)
                if len(self.private_chain) >= 2:
                    for pb in self.private_chain:
                        self.network.broadcast(pb, self)
                    self.private_chain.clear()
            else:
                self.network.broadcast(b, self)


class Network:
    def __init__(self, delay=(0.05, 0.2)):
        self.nodes = []
        self.delay = delay
        self.block_times = []

    def add(self, n):
        self.nodes.append(n)

    def broadcast(self, block, sender):
        t0 = time.time()
        for n in self.nodes:
            time.sleep(random.uniform(*self.delay))
            n.bc.add_block(block)
        self.block_times.append(time.time() - t0)


# ---------- EXPERIMENT ----------

def run():
    net = Network()
    nodes = [
        Node(0, net),
        Node(1, net),
        Node(2, net, selfish=True)  # attacker
    ]
    for n in nodes:
        net.add(n)

    threads = []
    for n in nodes:
        t = threading.Thread(target=n.mine_loop)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    avg_block_time = sum(net.block_times) / len(net.block_times)
    tps = (len(nodes[0].bc.chain) * 1) / sum(net.block_times)

    print("\nFinal chain length:", len(nodes[0].bc.chain))
    print("State:", nodes[0].bc.state)
    print("Avg block propagation time:", round(avg_block_time, 3), "s")
    print("Approx TPS:", round(tps, 2))


if __name__ == "__main__":
    runs = int(os.getenv("RUNS", "1"))
    for i in range(runs):
        print(f"\n--- SimuBlock Experiment {i+1} ---")
        run()
