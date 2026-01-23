import hashlib
import time

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
