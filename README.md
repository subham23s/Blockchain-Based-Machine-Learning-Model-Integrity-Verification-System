# BlockVerify 🔗

> **Blockchain-based File Integrity Verification System**  
> SHA-256 · Proof-of-Work · IPFS via Pinata · Multi-user Authentication

Built by Subham Mishra 


---

## What is BlockVerify?

BlockVerify lets you register any file (image, document, ML model) into a blockchain. Each file is hashed with **SHA-256**, mined into a block using **Proof-of-Work**, and stored on **IPFS via Pinata**. Anyone can later verify whether a file has been tampered with by checking its hash against the chain.

---

## Features

- 🔐 **Multi-user login & signup** — anyone can create an account
- 👤 **Per-user file registry** — each user sees only their own files
- ⛏ **Proof-of-Work mining** — difficulty 4 (hash must start with `0000`)
- 🔒 **SHA-256 hashing** — content-based, not filename-based
- 🌐 **IPFS storage via Pinata** — decentralized blockchain persistence
- ⬇ **File download** — download your registered files anytime
- 🗑 **File deletion** — remove files from your account
- 🛡 **Admin panel** — separate admin login with full user management
- 📊 **Chain explorer** — view all blocks with validity check

---

## Project Structure

```
blockchain_iris_project/
│
├── app.py               ← Main Flask web app
├── blockchain.py        ← Block + Blockchain classes with PoW
├── hash_utils.py        ← SHA-256 hashing + file type detection
├── pinata_utils.py      ← Pinata IPFS integration
├── train_model.py       ← Iris model trainer (original project)
├── iris_model.joblib    ← Trained ML model
├── requirements.txt     ← Python dependencies
├── .env                 ← API keys (never commit this)
├── users.json           ← Auto-created on first signup (local user store)
├── uploaded_files/      ← Auto-created file storage for downloads
└── README.md
```

---

## Setup & Installation

### 1. Clone the repo
```bash
git clone https://github.com/subham23s/energy-consumption-prediction
cd blockchain_iris_project
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up Pinata IPFS

1. Create a free account at [pinata.cloud](https://pinata.cloud)
2. Go to **API Keys** → Generate new key
3. Copy your **API Key** and **Secret Key**

### 5. Create `.env` file

Create a file called `.env` in your project folder:

```
PINATA_API_KEY=your_pinata_api_key_here
PINATA_SECRET_KEY=your_pinata_secret_key_here
```

### 6. Run the app
```bash
python app.py
```

Browser opens automatically at `http://127.0.0.1:5000`

---

## Usage

### Regular Users
1. Open `http://127.0.0.1:5000`
2. **Sign Up** with any username and password
3. **Register** tab — drop any file to register it on the blockchain
4. **Verify** tab — drop a file to check if it has been tampered with
5. **My Files** tab — view, download, or delete your registered files
6. **Chain** tab — explore all blocks in the blockchain

### Admin
Login from the main page with admin credentials — automatically redirects to the admin panel.

**Default admin credentials:**
```
Username : admin@username
Password : admin@password
```

**Admin can:**
- View all registered users 
- Delete user accounts
- Set Pinata API keys
- Change admin password

> Change the admin password after first login via Admin Panel → Config tab.

---

## How It Works

```
File Upload
    ↓
SHA-256 Hash (content-based fingerprint)
    ↓
Proof-of-Work Mining (find nonce so hash starts with "0000")
    ↓
Block added to Blockchain
    ↓
Chain saved to IPFS via Pinata (get CID)
    ↓
File stored locally in uploaded_files/<hash>/
    ↓
User's file list updated in users.json (local JSON store)
```

### Verification
```
Upload file again
    ↓
Compute SHA-256 hash
    ↓
Search blockchain for matching hash
    ↓
✅ Found = File is intact
❌ Not found = File tampered or not registered
```

---

## User Data Storage

User accounts (username, hashed password, file list) are stored locally in `users.json`.  
This is ideal for **college demos and small deployments**.

> For large-scale public deployment with many users, this can be migrated to a cloud database like Firebase Firestore in the future.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Blockchain | Custom implementation (SHA-256 + PoW) |
| Storage | IPFS via Pinata |
| Frontend | HTML, CSS, Vanilla JS |
| Auth | Flask Sessions + SHA-256 password hashing |
| User Store | Local JSON file (`users.json`) |
| ML Model | Scikit-learn (Iris dataset) |


---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/signup` | Create new account |
| POST | `/login` | Login (redirects admin to /admin) |
| POST | `/logout` | Logout and clear session |
| POST | `/register` | Register a file on blockchain |
| POST | `/verify` | Verify file integrity |
| GET | `/my_files` | Get logged-in user's files |
| GET | `/download/<hash>` | Download a registered file |
| POST | `/delete_file` | Remove file from account |
| GET | `/chain` | Get full blockchain data |
| GET | `/pinata_status` | Check Pinata connection |
| GET | `/admin` | Admin panel |
| GET | `/admin/users` | Get all users (admin only) |
| POST | `/admin/config` | Update Pinata keys (admin only) |

---

## .gitignore

```
.env
venv/
__pycache__/
*.joblib
users.json
uploaded_files/
```

---

## License

MIT License — © 2026 Subham Mishra 