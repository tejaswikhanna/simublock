from .block import Block

class Blockchain:
    def __init__(self):
        self.chain = [Block(0, "0", [])]

    def last(self):
        return self.chain[-1]

    def add(self, block):
        if block.prev == self.last().h:
            self.chain.append(block)
            # emit(f"BLOCK {block.i} committed")