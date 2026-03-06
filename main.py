from blockchain import Blockchain, Block
from hash_utils import generate_file_hash
import json
import os

BLOCKCHAIN_FILE = "blockchain_data.json"

def save_blockchain(blockchain):
    chain_data = []
    for block in blockchain.chain:
        chain_data.append({
            "index": block.index,
            "timestamp": block.timestamp,
            "model_hash": block.model_hash,
            "previous_hash": block.previous_hash,
            "current_hash": block.current_hash
        })

    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump(chain_data, f)

def load_blockchain():
    blockchain = Blockchain()

    if not os.path.exists(BLOCKCHAIN_FILE):
        return blockchain

    with open(BLOCKCHAIN_FILE, "r") as f:
        chain_data = json.load(f)

    blockchain.chain = []

    for block_data in chain_data:
        block = Block(
            block_data["index"],
            block_data["model_hash"],
            block_data["previous_hash"]
        )
        block.timestamp = block_data["timestamp"]
        block.current_hash = block_data["current_hash"]
        blockchain.chain.append(block)

    return blockchain

# =============================

# Load existing blockchain if exists
blockchain = load_blockchain()

# If blockchain only has genesis, add original model hash
if len(blockchain.chain) == 1:
    model_hash = generate_file_hash("iris_model.joblib")
    blockchain.add_block(model_hash)
    save_blockchain(blockchain)
    print("Original model hash stored in blockchain.")
else:
    print("Blockchain already exists.")

# Now verify
current_hash = generate_file_hash("iris_model.joblib")
stored_hash = blockchain.chain[1].model_hash

print("Stored Hash:", stored_hash)
print("Current Hash:", current_hash)

if current_hash == stored_hash:
    print("Model Integrity Verified ✅")
else:
    print("Model Tampered ❌")

print("Is Blockchain Valid?", blockchain.is_chain_valid())