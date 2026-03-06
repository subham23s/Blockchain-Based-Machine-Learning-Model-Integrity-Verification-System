# Blockchain-Based Machine Learning Model Integrity Verification (Iris Dataset)

## 📌 Project Overview

This project demonstrates how blockchain technology can be used to ensure the integrity of a trained Machine Learning model.

A Logistic Regression model is trained using the Iris dataset.  
The trained model is serialized and saved to disk.  
A SHA-256 cryptographic hash of the model file is generated.  +
This hash is stored inside a custom-built blockchain structure.

Any modification to the model file or blockchain data is detected through hash validation.

---

## 🎯 Objective

The goal of this project is to:

- Train a Machine Learning model
- Serialize the trained model
- Generate a SHA-256 hash of the model file
- Store the hash in a blockchain structure
- Detect tampering of:
  - The ML model file
  - The blockchain data itself

This project combines Machine Learning + Cryptography + Blockchain concepts.

---

## 🧠 Technologies Used

- Python
- Scikit-learn
- Joblib
- SHA-256 (hashlib)
- Custom Blockchain Implementation (Python)

---

## 📊 Dataset Used

Iris Dataset (from sklearn)

- 150 samples
- 4 numerical features
- 3 classes (Setosa, Versicolor, Virginica)
- Multi-class classification

The dataset is built-in within `scikit-learn` and requires no external download.

---

## 🏗 Project Architecture

System Workflow:

1. Train ML Model
2. Save model as `iris_model.joblib`
3. Generate SHA-256 hash of model file
4. Store hash inside blockchain block
5. Save blockchain to JSON file
6. Verify integrity on subsequent runs

---

## 🔐 Blockchain Structure

Each block contains:

- index
- timestamp
- model_hash
- previous_hash
- current_hash

The current_hash is generated using:

SHA-256(index + timestamp + model_hash + previous_hash)

Each block links to the previous block using `previous_hash`, ensuring immutability.

---

## 🔒 Why SHA-256?

SHA-256 is a cryptographic hash function that:

- Produces fixed 256-bit output
- Is one-way (cannot reverse to original data)
- Exhibits avalanche effect (small change → completely different hash)
- Is widely used in blockchain systems (e.g., Bitcoin)

---

## 📂 Project Structure

blockchain_iris_project/
│
├── train_model.py # Trains and saves ML model
├── hash_utils.py # Generates SHA-256 file hash
├── blockchain.py # Block and Blockchain classes
├── main.py # Integrity verification logic
├── iris_model.joblib # Serialized ML model
├── blockchain_data.json # Stored blockchain data
└── README.md

---

## 🚀 How to Run

### Step 1 — Train Model

python train_model.py

This will:

- Train Logistic Regression model
- Save it as `iris_model.joblib`

---

### Step 2 — Initialize Blockchain

(Delete `blockchain_data.json` if it exists)

python main.py

This will:

- Generate model hash
- Store it in blockchain
- Save blockchain to JSON file

---

### Step 3 — Verify Integrity

Run again:

python main.py

If model not modified:

Model Integrity Verified ✅  
Is Blockchain Valid? True

---

### Step 4 — Tampering Test

Modify `iris_model.joblib` manually.

Run:

python main.py

Output:

Model Tampered ❌  
Is Blockchain Valid? True

---

### Step 5 — Blockchain Tampering Test

Modify `blockchain_data.json`.

Run:

python main.py

Output:

Is Blockchain Valid? False

---

## 🧩 Key Concepts Demonstrated

✔ Model Serialization  
✔ Cryptographic Hashing  
✔ Avalanche Effect  
✔ Blockchain Linking  
✔ Immutability  
✔ Tamper Detection  

---

## ⚠ Limitations

- Not a distributed blockchain
- No consensus mechanism
- No mining / Proof-of-Work
- Educational simulation only

---

## 📈 Future Improvements

- Add digital signatures
- Implement Proof-of-Work
- Deploy as API using Flask
- Use IPFS for decentralized storage
- Extend to larger ML models

---

## 🎓 Academic Relevance

This project demonstrates how blockchain can be used to ensure integrity of deployed Machine Learning models.

It connects:

Blockchain → Cryptographic Hashing → Model Integrity → Trustworthy AI

---

## 👨‍💻 Author

SUBHAM MISHRA  
Regd no: 240301370048
B.Tech CSE (AI/ML Specialization)  
Blockchain Intro Course Project
