import hashlib
import json
import time


class Block:
    def __init__(self, index, model_hash, previous_hash):
        self.index = index
        self.timestamp = time.time()
        self.model_hash = model_hash
        self.previous_hash = previous_hash
        self.current_hash = self.compute_hash()

    def compute_hash(self):
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "model_hash": self.model_hash,
            "previous_hash": self.previous_hash
        }

        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, "GENESIS", "0")
        self.chain.append(genesis_block)

    def add_block(self, model_hash):
        previous_block = self.chain[-1]

        new_block = Block(
            index=len(self.chain),
            model_hash=model_hash,
            previous_hash=previous_block.current_hash
        )

        self.chain.append(new_block)

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Recalculate hash
            if current.current_hash != current.compute_hash():
                return False

            # Check previous link
            if current.previous_hash != previous.current_hash:
                return False

        return True