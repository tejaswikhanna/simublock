import hashlib

def mine(b, d=2):
    """
    Proof of Work mining:
    Changes b.nonce until b.hash() starts with 'd' zeros.
    """
    prefix = "0" * d
    while not b.h.startswith(prefix):
        b.nonce += 1
        b.h = b.hash()
    return b

class Consensus:
    def __init__(self, difficulty):
        self.difficulty = difficulty

    def propose_block(self, block):
        return mine(block, self.difficulty)

    def validate_block(self, block, chain_obj):
        # Check hash difficulty
        if not block.h.startswith("0" * self.difficulty):
            return False
        # Check link
        last = chain_obj.last()
        if block.prev != last.h:
            return False
        return True

def get_consensus(experiment_config):
    # For now, just return our simple PoW consensus
    return Consensus(experiment_config.get("difficulty", 2))
