from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
from blockchain import Blockchain
from hash_utils import generate_bytes_hash, detect_file_type
from pinata_utils import (
    save_blockchain_to_pinata,
    load_blockchain_from_pinata,
    test_pinata_connection,
    get_latest_cid
)
import os, base64, mimetypes, json, hashlib, time, io

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Random on every restart = clears all sessions

USERS_FILE   = "users.json"
ADMIN_USERNAME = "admin-admin@23s"
ADMIN_PASSWORD = "admin@3131"

# ── .env loader ────────────────────────────────────────────────────────────
def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
                    import pinata_utils as pu
                    if k.strip() == "PINATA_API_KEY":    pu.PINATA_API_KEY    = v.strip()
                    if k.strip() == "PINATA_SECRET_KEY": pu.PINATA_SECRET_KEY = v.strip()
                    if k.strip() == "ADMIN_PASSWORD":
                        global ADMIN_PASSWORD
                        ADMIN_PASSWORD = v.strip()
load_env()

# ── User helpers ───────────────────────────────────────────────────────────
def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE): return {}
    with open(USERS_FILE) as f: return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f: json.dump(u, f, indent=2)

def create_user(username, password):
    users = load_users()
    if username in users: return False, "Username already exists."
    users[username] = {"password": hp(password), "created_at": time.time(),
                       "login_count": 0, "files": []}
    save_users(users)
    return True, "ok"

def verify_user(username, password):
    u = load_users().get(username)
    return u and u["password"] == hp(password)

def bump_login(username):
    users = load_users()
    if username in users:
        users[username]["login_count"] = users[username].get("login_count", 0) + 1
        users[username]["last_login"] = time.time()
        save_users(users)
    return users.get(username, {}).get("login_count", 1)

def _normalize_files(files):
    """Convert old format (list of strings) to new format (list of dicts)."""
    result = []
    for f in files:
        if isinstance(f, str):
            result.append({"hash": f, "name": "unknown", "type": "file", "added": 0})
        elif isinstance(f, dict):
            result.append(f)
    return result

def add_file_to_user(username, file_hash, file_name, file_type):
    users = load_users()
    if username not in users: return
    users[username]["files"] = _normalize_files(users[username].get("files", []))
    entry = {"hash": file_hash, "name": file_name, "type": file_type, "added": time.time()}
    if not any(f["hash"] == file_hash for f in users[username]["files"]):
        users[username]["files"].append(entry)
    save_users(users)

def remove_file_from_user(username, file_hash):
    users = load_users()
    if username not in users: return
    users[username]["files"] = _normalize_files(users[username].get("files", []))
    users[username]["files"] = [f for f in users[username]["files"] if f["hash"] != file_hash]
    save_users(users)

def get_user_file_hashes(username):
    u = load_users().get(username)
    if not u: return []
    return [f["hash"] if isinstance(f, dict) else f for f in u.get("files", [])]

# ── Blockchain helpers ─────────────────────────────────────────────────────
def get_blockchain():
    try:
        d = load_blockchain_from_pinata()
        if d: return Blockchain.from_list(d)
    except: pass
    return Blockchain(difficulty=4)

def save_bc(bc): return save_blockchain_to_pinata(bc.to_list())

# ── Persistent file store ─────────────────────────────────────────────────
import pathlib
file_previews = {}   # hash -> data_url (images only, in-memory is fine)
UPLOAD_DIR = pathlib.Path("uploaded_files")
UPLOAD_DIR.mkdir(exist_ok=True)

def save_file_bytes(file_hash, filename, raw_bytes):
    """Save file to disk using hash as folder."""
    folder = UPLOAD_DIR / file_hash
    folder.mkdir(exist_ok=True)
    filepath = folder / filename
    filepath.write_bytes(raw_bytes)
    return filepath

def get_file_bytes(file_hash, filename=None):
    """Retrieve file from disk."""
    folder = UPLOAD_DIR / file_hash
    if not folder.exists():
        return None, None
    if filename:
        fp = folder / filename
        if fp.exists():
            return fp.read_bytes(), filename
    # Find any file in folder
    files = list(folder.iterdir())
    if files:
        return files[0].read_bytes(), files[0].name
    return None, None

# ══════════════════════════════════════════════════════════════════════════
# MAIN APP HTML
# ══════════════════════════════════════════════════════════════════════════
MAIN_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>BlockVerify</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#0a0a0f;--surface:#111118;--border:#1e1e2e;--accent:#00ff88;--accent2:#7c3aed;--warn:#ff4444;--text:#e2e8f0;--muted:#64748b;--mono:'Space Mono',monospace;--sans:'Syne',sans-serif;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,255,136,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,136,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}

/* AUTH */
.auth-page{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;position:relative;z-index:1;}
.auth-card{width:100%;max-width:420px;background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:40px;animation:fadeIn .4s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.auth-logo{font-size:1.6rem;font-weight:800;margin-bottom:6px;letter-spacing:-.5px;}
.auth-logo span{color:var(--accent);}
.auth-tagline{font-family:var(--mono);font-size:.7rem;color:var(--muted);margin-bottom:28px;}
.auth-tabs{display:flex;gap:0;margin-bottom:26px;background:var(--bg);border-radius:10px;padding:4px;}
.auth-tab{flex:1;padding:10px;font-family:var(--mono);font-size:.78rem;border:none;background:none;color:var(--muted);border-radius:8px;cursor:pointer;transition:all .2s;}
.auth-tab.active{background:var(--accent);color:#000;font-weight:700;}
.welcome-banner{background:rgba(0,255,136,.07);border:1px solid var(--accent);border-radius:10px;padding:14px 18px;margin-bottom:22px;font-family:var(--mono);font-size:.8rem;color:var(--accent);display:none;}

/* FORMS */
.form-group{margin-bottom:16px;}
.form-label{display:block;font-family:var(--mono);font-size:.7rem;color:var(--muted);margin-bottom:7px;letter-spacing:.5px;}
.form-input{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px 16px;color:var(--text);font-family:var(--mono);font-size:.85rem;transition:border-color .2s;}
.form-input:focus{outline:none;border-color:var(--accent);}
.form-input::placeholder{color:var(--muted);}

/* BUTTONS */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:12px 28px;border-radius:8px;font-family:var(--mono);font-size:.85rem;font-weight:700;cursor:pointer;border:none;transition:all .2s;letter-spacing:.5px;}
.btn-primary{background:var(--accent);color:#000;width:100%;}
.btn-primary:hover{background:#00cc6a;transform:translateY(-1px);}
.btn-outline{background:transparent;color:var(--accent);border:1px solid var(--accent);}
.btn-outline:hover{background:rgba(0,255,136,.08);}
.btn-sm{padding:6px 14px;font-size:.72rem;border-radius:6px;width:auto;}
.btn-dl{background:rgba(0,255,136,.1);color:var(--accent);border:1px solid rgba(0,255,136,.3);padding:5px 12px;font-size:.68rem;border-radius:6px;font-family:var(--mono);cursor:pointer;transition:all .2s;}
.btn-dl:hover{background:rgba(0,255,136,.2);}
.btn-danger-sm{background:transparent;color:var(--warn);border:1px solid var(--warn);padding:5px 12px;font-size:.68rem;border-radius:6px;font-family:var(--mono);cursor:pointer;transition:all .2s;}
.btn-danger-sm:hover{background:rgba(255,68,68,.1);}
.auth-msg{font-family:var(--mono);font-size:.76rem;margin-top:12px;text-align:center;min-height:18px;}
.auth-msg.err{color:var(--warn);}
.auth-msg.ok{color:var(--accent);}

/* APP SHELL */
.app-shell{display:none;min-height:100vh;position:relative;z-index:1;}
.container{max-width:1100px;margin:0 auto;padding:0 24px;}
header{border-bottom:1px solid var(--border);padding:16px 0;}
.header-inner{display:flex;align-items:center;justify-content:space-between;}
.logo{font-size:1.3rem;font-weight:800;letter-spacing:-.5px;}
.logo span{color:var(--accent);}
.header-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.user-pill{font-family:var(--mono);font-size:.7rem;padding:6px 14px;border-radius:20px;border:1px solid var(--accent2);color:#a78bfa;display:flex;align-items:center;gap:6px;}
.status-pill{font-family:var(--mono);font-size:.7rem;padding:6px 14px;border-radius:20px;border:1px solid;display:flex;align-items:center;gap:6px;}
.status-pill.ok{border-color:var(--accent);color:var(--accent);}
.status-pill.fail{border-color:var(--warn);color:var(--warn);}
.status-pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.logout-btn{font-family:var(--mono);font-size:.7rem;padding:6px 14px;border-radius:20px;border:1px solid var(--border);color:var(--muted);background:none;cursor:pointer;transition:all .2s;}
.logout-btn:hover{border-color:var(--warn);color:var(--warn);}

.hero{padding:44px 0 28px;}
.hero h1{font-size:clamp(1.8rem,4vw,3rem);font-weight:800;line-height:1.1;letter-spacing:-1px;}
.hero h1 em{font-style:normal;color:var(--accent);}
.hero p{margin-top:10px;color:var(--muted);font-size:.92rem;max-width:500px;line-height:1.6;}

.tabs{display:flex;gap:4px;margin:28px 0 0;border-bottom:1px solid var(--border);flex-wrap:wrap;}
.tab{padding:10px 18px;font-family:var(--mono);font-size:.76rem;cursor:pointer;border:none;background:none;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .2s;}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);}
.tab:hover:not(.active){color:var(--text);}
.panel{display:none;padding:32px 0;}
.panel.active{display:block;}

/* Upload */
.upload-zone{border:2px dashed var(--border);border-radius:12px;padding:50px 40px;text-align:center;cursor:pointer;transition:all .3s;position:relative;overflow:hidden;}
.upload-zone::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(0,255,136,.04) 0%,transparent 70%);opacity:0;transition:opacity .3s;}
.upload-zone:hover,.upload-zone.drag{border-color:var(--accent);}
.upload-zone:hover::before,.upload-zone.drag::before{opacity:1;}
.upload-icon{font-size:2.6rem;margin-bottom:12px;}
.upload-zone h3{font-size:1rem;font-weight:600;margin-bottom:6px;}
.upload-zone p{color:var(--muted);font-size:.8rem;font-family:var(--mono);}
.upload-zone input{display:none;}

/* Result cards */
.result-card{margin-top:20px;border-radius:12px;padding:24px;border:1px solid;animation:slideUp .3s ease;}
@keyframes slideUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.result-card.success{border-color:var(--accent);background:rgba(0,255,136,.05);}
.result-card.danger{border-color:var(--warn);background:rgba(255,68,68,.05);}
.result-card.info{border-color:var(--accent2);background:rgba(124,58,237,.05);}
.result-title{font-size:1.05rem;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.result-card.success .result-title{color:var(--accent);}
.result-card.danger .result-title{color:var(--warn);}
.result-card.info .result-title{color:#a78bfa;}
.result-meta{font-family:var(--mono);font-size:.72rem;color:var(--muted);line-height:2;}
.hash-val{color:var(--text);word-break:break-all;}
.mining-bar{margin-top:12px;height:4px;background:var(--border);border-radius:2px;overflow:hidden;display:none;}
.mining-bar.active{display:block;}
.mining-bar::after{content:'';display:block;height:100%;background:linear-gradient(90deg,transparent,var(--accent),transparent);animation:mine 1.5s infinite;}
@keyframes mine{from{transform:translateX(-100%)}to{transform:translateX(300%)}}

/* Chain */
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:26px;}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}
.stat-label{font-family:var(--mono);font-size:.66rem;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;}
.stat-value{font-size:1.6rem;font-weight:800;color:var(--accent);}
.validity-banner{display:flex;align-items:center;gap:10px;padding:11px 16px;border-radius:8px;font-family:var(--mono);font-size:.76rem;margin-bottom:20px;border:1px solid;}
.validity-banner.valid{border-color:var(--accent);background:rgba(0,255,136,.05);color:var(--accent);}
.validity-banner.invalid{border-color:var(--warn);background:rgba(255,68,68,.05);color:var(--warn);}
.chain-list{display:flex;flex-direction:column;gap:10px;}
.chain-block{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;display:grid;grid-template-columns:48px 1fr auto;gap:12px;align-items:center;transition:border-color .2s;}
.chain-block:hover{border-color:var(--accent2);}
.block-index{width:42px;height:42px;border-radius:8px;background:linear-gradient(135deg,var(--accent2),#4f46e5);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem;}
.block-name{font-weight:600;font-size:.88rem;margin-bottom:3px;}
.block-meta{font-family:var(--mono);font-size:.66rem;color:var(--muted);}
.block-badge{font-family:var(--mono);font-size:.6rem;padding:3px 9px;border-radius:10px;border:1px solid var(--border);color:var(--muted);white-space:nowrap;}
.chain-link{text-align:center;color:var(--accent);opacity:.4;padding:3px 0;}

/* File grid */
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;flex-wrap:wrap;gap:10px;}
.section-header h2{font-size:1.2rem;font-weight:800;}
.file-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;}
.file-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;overflow:hidden;transition:all .3s;animation:slideUp .3s ease;}
.file-card:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,255,136,.07);}
.file-preview{height:140px;display:flex;align-items:center;justify-content:center;background:#0d0d16;border-bottom:1px solid var(--border);overflow:hidden;position:relative;}
.file-preview img{width:100%;height:100%;object-fit:cover;}
.file-icon-big{font-size:3rem;}
.ftype-badge{position:absolute;top:7px;right:7px;font-family:var(--mono);font-size:.56rem;padding:2px 7px;border-radius:8px;background:rgba(0,0,0,.75);border:1px solid var(--border);color:var(--muted);}
.file-info{padding:13px;}
.file-name{font-weight:700;font-size:.85rem;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.file-detail{font-family:var(--mono);font-size:.64rem;color:var(--muted);line-height:1.85;}
.file-hash-short{color:var(--accent);}
.file-actions{display:flex;gap:6px;margin-top:9px;flex-wrap:wrap;}
.empty-state{text-align:center;padding:60px 0;color:var(--muted);}
.empty-icon{font-size:3.2rem;margin-bottom:12px;}
.empty-state p{font-family:var(--mono);font-size:.8rem;line-height:2;}

/* Config */
.config-form{max-width:460px;}
.config-section-title{font-size:.95rem;font-weight:700;margin:24px 0 14px;}
hr.divider{border:none;border-top:1px solid var(--border);margin:24px 0;}

footer{border-top:1px solid var(--border);padding:18px 0;text-align:center;font-family:var(--mono);font-size:.66rem;color:var(--muted);margin-top:48px;}
footer a{color:var(--accent);text-decoration:none;}

@media(max-width:640px){.stats{grid-template-columns:1fr;}.chain-block{grid-template-columns:42px 1fr;}.block-badge{display:none;}.file-grid{grid-template-columns:1fr;}.header-right{gap:6px;}}
</style>
</head>
<body>

<!-- AUTH PAGE -->
<div class="auth-page" id="authPage">
  <div class="auth-card">
    <div class="auth-logo">Block<span>Verify</span></div>
    <div class="auth-tagline">SHA-256 · Proof-of-Work · IPFS</div>
    <div class="auth-tabs">
      <button class="auth-tab active" onclick="switchAuthTab('login')">Login</button>
      <button class="auth-tab" onclick="switchAuthTab('signup')">Sign Up</button>
    </div>
    <div class="welcome-banner" id="welcomeBanner"></div>

    <!-- Login -->
    <div id="loginForm">
      <div class="form-group"><label class="form-label">USERNAME</label><input class="form-input" type="text" id="authLoginUser" placeholder="Enter username" onkeydown="if(event.key==='Enter')submitLogin()"/></div>
      <div class="form-group"><label class="form-label">PASSWORD</label><input class="form-input" type="password" id="authLoginPass" placeholder="Enter password" onkeydown="if(event.key==='Enter')submitLogin()"/></div>
      <button class="btn btn-primary" onclick="submitLogin()">Login →</button>
      <div class="auth-msg" id="loginMsg"></div>
    </div>

    <!-- Signup -->
    <div id="signupForm" style="display:none">
      <div class="form-group"><label class="form-label">USERNAME</label><input class="form-input" type="text" id="authSignupUser" placeholder="Choose a username" onkeydown="if(event.key==='Enter')submitSignup()"/></div>
      <div class="form-group"><label class="form-label">PASSWORD</label><input class="form-input" type="password" id="authSignupPass" placeholder="Choose a password" onkeydown="if(event.key==='Enter')submitSignup()"/></div>
      <div class="form-group"><label class="form-label">CONFIRM PASSWORD</label><input class="form-input" type="password" id="authSignupPassConfirm" placeholder="Repeat password" onkeydown="if(event.key==='Enter')submitSignup()"/></div>
      <button class="btn btn-primary" onclick="submitSignup()">Create Account →</button>
      <div class="auth-msg" id="signupMsg"></div>
    </div>
  </div>
</div>

<!-- APP SHELL -->
<div class="app-shell" id="appShell">
  <div class="container">
    <header>
      <div class="header-inner">
        <div class="logo">Block<span>Verify</span></div>
        <div class="header-right">
          <div class="user-pill">👤 <span id="loggedInUsername"></span></div>
          <div class="status-pill fail" id="pinataStatus"><span class="dot"></span><span id="pinataStatusText">Checking...</span></div>
          <button class="logout-btn" onclick="doLogout()">Logout</button>
        </div>
      </div>
    </header>
    <div class="hero">
      <h1>Verify <em>Integrity</em><br/>with Blockchain</h1>
      <p>Register any file — image, document, ML model. Hash it with SHA-256, mine into a block, store on IPFS.</p>
    </div>
    <div class="tabs">
      <button class="tab active" onclick="switchTab('register')">⬆ Register</button>
      <button class="tab" onclick="switchTab('verify')">🔍 Verify</button>
      <button class="tab" onclick="switchTab('retrieve')">📂 My Files</button>
      <button class="tab" onclick="switchTab('chain')">⛓ Chain</button>
    </div>

    <!-- REGISTER -->
    <div class="panel active" id="panel-register">
      <div class="upload-zone" id="registerZone" onclick="document.getElementById('registerInput').click()">
        <div class="upload-icon">📁</div><h3>Drop a file to register</h3><p>Images, Documents, ML Models — anything goes</p>
        <input type="file" id="registerInput" onchange="handleRegisterFile(this.files[0])"/>
      </div>
      <div class="mining-bar" id="registerMining"></div>
      <div id="registerStatus"></div>
    </div>

    <!-- VERIFY -->
    <div class="panel" id="panel-verify">
      <div class="upload-zone" id="verifyZone" onclick="document.getElementById('verifyInput').click()">
        <div class="upload-icon">🔍</div><h3>Drop a file to verify</h3><p>We'll check if this exact file exists in the blockchain</p>
        <input type="file" id="verifyInput" onchange="handleVerifyFile(this.files[0])"/>
      </div>
      <div class="mining-bar" id="verifyMining"></div>
      <div id="verifyStatus"></div>
    </div>

    <!-- MY FILES -->
    <div class="panel" id="panel-retrieve">
      <div class="section-header">
        <h2>📂 My Registered Files</h2>
        <button class="btn btn-outline btn-sm" onclick="loadMyFiles()">↺ Refresh</button>
      </div>
      <div class="file-grid" id="fileList"><div class="empty-state"><div class="empty-icon">⏳</div><p>Loading...</p></div></div>
    </div>

    <!-- CHAIN -->
    <div class="panel" id="panel-chain">
      <div class="stats">
        <div class="stat-card"><div class="stat-label">Total Blocks</div><div class="stat-value" id="statBlocks">—</div></div>
        <div class="stat-card"><div class="stat-label">PoW Difficulty</div><div class="stat-value">4</div></div>
        <div class="stat-card"><div class="stat-label">IPFS CID</div><div class="stat-value" style="font-size:.66rem;font-family:var(--mono);word-break:break-all;margin-top:6px" id="statCID">—</div></div>
      </div>
      <div id="validityBanner"></div>
      <div class="chain-list" id="chainList"><p style="color:var(--muted);font-family:var(--mono);font-size:.8rem">Loading...</p></div>
      <br/><button class="btn btn-outline btn-sm" onclick="loadChain()">↺ Refresh</button>
    </div>
  </div>
  <footer>BlockVerify • SHA-256 + Proof-of-Work + IPFS • Built by <a href="https://github.com/subham23s" target="_blank">Subham Mishra</a> &amp; <a href="https://github.com/Anubhav-axt" target="_blank">Anubhav Pati</a></footer>
</div>

<script>
function switchAuthTab(t){
  document.querySelectorAll('.auth-tab').forEach((el,i)=>el.classList.toggle('active',['login','signup'][i]===t));
  document.getElementById('loginForm').style.display=t==='login'?'block':'none';
  document.getElementById('signupForm').style.display=t==='signup'?'block':'none';
}

async function submitLogin(){
  const u=document.getElementById('authLoginUser').value.trim();
  const p=document.getElementById('authLoginPass').value.trim();
  const msg=document.getElementById('loginMsg');
  msg.textContent='';msg.className='auth-msg';
  if(!u||!p){msg.className='auth-msg err';msg.textContent='Fill both fields.';return;}
  try{
    const res=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const data=await res.json();
    if(data.success){
      if(data.is_admin){ window.location.href='/admin'; return; }
      const banner=document.getElementById('welcomeBanner');
      if(data.login_count>1){
        banner.textContent=`👋 Welcome back, ${u}! You've logged in ${data.login_count} times.`;
        banner.style.display='block';
        setTimeout(()=>{banner.style.display='none';enterApp(u);},1800);
      } else { enterApp(u); }
    } else { msg.className='auth-msg err'; msg.textContent='❌ Invalid username or password.'; }
  }catch(e){msg.className='auth-msg err';msg.textContent='Error: '+e.message;}
}

async function submitSignup(){
  const u=document.getElementById('authSignupUser').value.trim();
  const p=document.getElementById('authSignupPass').value.trim();
  const c=document.getElementById('authSignupPassConfirm').value.trim();
  const msg=document.getElementById('signupMsg');
  msg.textContent='';msg.className='auth-msg';
  if(!u||!p){msg.className='auth-msg err';msg.textContent='Fill all fields.';return;}
  if(p!==c){msg.className='auth-msg err';msg.textContent='❌ Passwords do not match.';return;}
  if(p.length<4){msg.className='auth-msg err';msg.textContent='❌ Password too short (min 4).';return;}
  try{
    const res=await fetch('/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const data=await res.json();
    if(data.success){msg.className='auth-msg ok';msg.textContent='✅ Account created! Logging in...';setTimeout(()=>enterApp(u),900);}
    else{msg.className='auth-msg err';msg.textContent='❌ '+data.message;}
  }catch(e){msg.className='auth-msg err';msg.textContent='Error: '+e.message;}
}

function enterApp(username){
  document.getElementById('authPage').style.display='none';
  document.getElementById('appShell').style.display='block';
  document.getElementById('loggedInUsername').textContent=username;
  checkPinataStatus();
}

async function doLogout(){
  await fetch('/logout',{method:'POST'});
  document.getElementById('appShell').style.display='none';
  document.getElementById('authPage').style.display='flex';
  document.getElementById('authLoginPass').value='';
  document.getElementById('authLoginUser').value='';
  document.getElementById('loginMsg').textContent='';
  // reset to register tab
  switchTab('register');
}

function switchTab(name){
  const names=['register','verify','retrieve','chain'];
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',names[i]===name));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  if(name==='chain')loadChain();
  if(name==='retrieve')loadMyFiles();
}

['registerZone','verifyZone'].forEach(id=>{
  const z=document.getElementById(id);
  z.addEventListener('dragover',e=>{e.preventDefault();z.classList.add('drag');});
  z.addEventListener('dragleave',()=>z.classList.remove('drag'));
  z.addEventListener('drop',e=>{e.preventDefault();z.classList.remove('drag');const f=e.dataTransfer.files[0];if(!f)return;id==='registerZone'?handleRegisterFile(f):handleVerifyFile(f);});
});

async function handleRegisterFile(file){
  if(!file)return;
  const bar=document.getElementById('registerMining'),status=document.getElementById('registerStatus');
  bar.classList.add('active');
  status.innerHTML=`<p style="font-family:var(--mono);font-size:.8rem;color:var(--muted);margin-top:12px">⛏ Mining block for <strong>${file.name}</strong>...</p>`;
  const fd=new FormData();fd.append('file',file);
  try{
    const res=await fetch('/register',{method:'POST',body:fd});
    const data=await res.json();
    bar.classList.remove('active');
    if(data.status==='registered'){status.innerHTML=`<div class="result-card success"><div class="result-title">✅ Registered Successfully</div><div class="result-meta">FILE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>TYPE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_type}</span><br/>HASH &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>BLOCK &nbsp;&nbsp;&nbsp;<span class="hash-val">#${data.block_index}</span><br/>NONCE &nbsp;&nbsp;&nbsp;<span class="hash-val">${data.nonce}</span><br/>IPFS CID <span class="hash-val">${data.ipfs_cid}</span></div></div>`;}
    else if(data.status==='exists'){status.innerHTML=`<div class="result-card info"><div class="result-title">ℹ️ Already Registered</div><div class="result-meta">FILE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>BLOCK &nbsp;&nbsp;&nbsp;<span class="hash-val">#${data.block_index}</span><br/>HASH &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span></div></div>`;}
    else{status.innerHTML=`<div class="result-card danger"><div class="result-title">❌ Error</div><div class="result-meta">${data.message}</div></div>`;}
  }catch(e){bar.classList.remove('active');status.innerHTML=`<div class="result-card danger"><div class="result-title">❌ Failed</div><div class="result-meta">${e.message}</div></div>`;}
}

async function handleVerifyFile(file){
  if(!file)return;
  const bar=document.getElementById('verifyMining'),status=document.getElementById('verifyStatus');
  bar.classList.add('active');
  status.innerHTML=`<p style="font-family:var(--mono);font-size:.8rem;color:var(--muted);margin-top:12px">🔍 Verifying <strong>${file.name}</strong>...</p>`;
  const fd=new FormData();fd.append('file',file);
  try{
    const res=await fetch('/verify',{method:'POST',body:fd});
    const data=await res.json();
    bar.classList.remove('active');
    if(data.verified){status.innerHTML=`<div class="result-card success"><div class="result-title">✅ Integrity Verified</div><div class="result-meta">FILE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>TYPE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_type}</span><br/>HASH &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>REG BLOCK &nbsp;<span class="hash-val">#${data.block_index}</span><br/>CHAIN OK &nbsp;&nbsp;<span class="hash-val">${data.chain_valid?'✅ Valid':'❌ Tampered'}</span></div></div>`;}
    else{status.innerHTML=`<div class="result-card danger"><div class="result-title">❌ ${data.reason==='not_found'?'File Not Registered':'Tampered / Unknown'}</div><div class="result-meta">FILE &nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>HASH &nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>${data.reason==='not_found'?'No record in the blockchain.':'Hash mismatch detected.'}</div></div>`;}
  }catch(e){bar.classList.remove('active');status.innerHTML=`<div class="result-card danger"><div class="result-title">❌ Failed</div><div class="result-meta">${e.message}</div></div>`;}
}

function fileIcon(t){return{image:'🖼️',document:'📄',ml_model:'🤖',file:'📁'}[t]||'📁';}

async function loadMyFiles(){
  const list=document.getElementById('fileList');
  list.innerHTML='<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading your files...</p></div>';
  try{
    const res=await fetch('/my_files');
    if(res.status===401){doLogout();return;}
    const data=await res.json();
    const files=data.files;
    if(!files||files.length===0){list.innerHTML='<div class="empty-state"><div class="empty-icon">📭</div><p>No files yet.<br/>Go to Register tab to add files.</p></div>';return;}
    list.innerHTML=files.map(f=>`
      <div class="file-card">
        <div class="file-preview">
          ${f.preview?`<img src="${f.preview}" alt="${f.file_name}"/>`:`<div class="file-icon-big">${fileIcon(f.file_type)}</div>`}
          <div class="ftype-badge">${f.file_type.toUpperCase()}</div>
        </div>
        <div class="file-info">
          <div class="file-name" title="${f.file_name}">${f.file_name}</div>
          <div class="file-detail">BLOCK &nbsp;&nbsp;#${f.index}<br/>HASH &nbsp;&nbsp;&nbsp;<span class="file-hash-short">${f.file_hash.substring(0,16)}...</span><br/>DATE &nbsp;&nbsp;&nbsp;${new Date(f.timestamp*1000).toLocaleDateString()}<br/>NONCE &nbsp;&nbsp;${f.nonce}</div>
          <div class="file-actions">
            <button class="btn-dl" onclick="downloadFile('${f.file_hash}','${f.file_name}')">⬇ Download</button>
            <button class="btn btn-outline btn-sm" onclick="copyHash('${f.file_hash}')">📋</button>
            <button class="btn-danger-sm" onclick="deleteFile('${f.file_hash}','${f.file_name}')">🗑</button>
          </div>
        </div>
      </div>`).join('');
  }catch(e){list.innerHTML=`<div class="empty-state"><div class="empty-icon">❌</div><p>${e.message}</p></div>`;}
}

function copyHash(h){navigator.clipboard.writeText(h);alert('Hash copied!');}

async function downloadFile(fileHash, fileName){
  try{
    const res=await fetch(`/download/${fileHash}`);
    if(!res.ok){alert('File not found on server. It may have been deleted.');return;}
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download=fileName;a.click();
    URL.revokeObjectURL(url);
  }catch(e){alert('Download failed: '+e.message);}
}

async function deleteFile(fileHash,fileName){
  if(!confirm(`Remove "${fileName}" from your files?\n\nThe blockchain record stays intact.`))return;
  try{
    const res=await fetch('/delete_file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_hash:fileHash})});
    const data=await res.json();
    if(data.success)loadMyFiles();
    else alert('Error: '+data.message);
  }catch(e){alert('Failed: '+e.message);}
}

async function loadChain(){
  const list=document.getElementById('chainList');
  list.innerHTML='<p style="color:var(--muted);font-family:var(--mono);font-size:.8rem">Loading...</p>';
  try{
    const res=await fetch('/chain');const data=await res.json();
    document.getElementById('statBlocks').textContent=data.chain.length;
    document.getElementById('statCID').textContent=data.cid||'Not synced';
    document.getElementById('validityBanner').innerHTML=`<div class="validity-banner ${data.valid?'valid':'invalid'}">${data.valid?'🔒 Blockchain valid — all blocks intact':'⚠️ Chain integrity compromised!'}</div>`;
    list.innerHTML=data.chain.map((b,i)=>`${i>0?'<div class="chain-link">↓</div>':''}<div class="chain-block"><div class="block-index">${b.index}</div><div><div class="block-name">${b.file_name}</div><div class="block-meta">${new Date(b.timestamp*1000).toLocaleString()} | nonce: ${b.nonce} | ${b.file_type}</div><div class="block-meta" style="margin-top:3px;color:#475569">${b.current_hash.substring(0,32)}...</div></div><div class="block-badge">${b.file_type.toUpperCase()}</div></div>`).join('');
  }catch(e){list.innerHTML=`<p style="color:var(--warn);font-family:var(--mono);font-size:.8rem">Error: ${e.message}</p>`;}
}

async function checkPinataStatus(){
  try{const res=await fetch('/pinata_status');const data=await res.json();document.getElementById('pinataStatus').className='status-pill '+(data.connected?'ok':'fail');document.getElementById('pinataStatusText').textContent=data.connected?'Pinata Connected':'Pinata Offline';}catch{}
}

(async()=>{
  try{const res=await fetch('/auth_status');const data=await res.json();if(data.logged_in)enterApp(data.username);}catch{}
})();
</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════════════
# ADMIN HTML
# ══════════════════════════════════════════════════════════════════════════
ADMIN_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>BlockVerify — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#0a0a0f;--surface:#111118;--border:#1e1e2e;--accent:#ff9500;--accent2:#7c3aed;--warn:#ff4444;--green:#00ff88;--text:#e2e8f0;--muted:#64748b;--mono:'Space Mono',monospace;--sans:'Syne',sans-serif;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(255,149,0,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,149,0,.025) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}

.auth-page{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;position:relative;z-index:1;}
.auth-card{width:100%;max-width:400px;background:var(--surface);border:1px solid #2a1f00;border-radius:20px;padding:40px;animation:fadeIn .4s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.auth-logo{font-size:1.5rem;font-weight:800;margin-bottom:4px;letter-spacing:-.5px;}
.auth-logo span{color:var(--accent);}
.auth-badge{display:inline-block;font-family:var(--mono);font-size:.65rem;padding:3px 10px;border-radius:10px;border:1px solid var(--accent);color:var(--accent);margin-bottom:24px;}

.form-group{margin-bottom:16px;}
.form-label{display:block;font-family:var(--mono);font-size:.7rem;color:var(--muted);margin-bottom:7px;letter-spacing:.5px;}
.form-input{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px 16px;color:var(--text);font-family:var(--mono);font-size:.85rem;transition:border-color .2s;}
.form-input:focus{outline:none;border-color:var(--accent);}
.form-input::placeholder{color:var(--muted);}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:12px 28px;border-radius:8px;font-family:var(--mono);font-size:.85rem;font-weight:700;cursor:pointer;border:none;transition:all .2s;width:100%;}
.btn-admin{background:var(--accent);color:#000;}
.btn-admin:hover{background:#e68600;transform:translateY(-1px);}
.btn-outline{background:transparent;color:var(--accent);border:1px solid var(--accent);width:auto;padding:8px 18px;font-size:.78rem;}
.btn-outline:hover{background:rgba(255,149,0,.08);}
.btn-sm{padding:6px 14px;font-size:.7rem;border-radius:6px;width:auto;}
.btn-green{background:transparent;color:var(--green);border:1px solid var(--green);width:auto;padding:6px 14px;font-size:.7rem;border-radius:6px;}
.btn-green:hover{background:rgba(0,255,136,.08);}
.btn-danger{background:transparent;color:var(--warn);border:1px solid var(--warn);width:auto;padding:6px 14px;font-size:.7rem;border-radius:6px;}
.btn-danger:hover{background:rgba(255,68,68,.08);}
.auth-msg{font-family:var(--mono);font-size:.76rem;margin-top:12px;text-align:center;}
.auth-msg.err{color:var(--warn);}

/* ADMIN SHELL */
.admin-shell{display:none;min-height:100vh;position:relative;z-index:1;}
.container{max-width:1100px;margin:0 auto;padding:0 24px;}
header{border-bottom:1px solid #2a1f00;padding:16px 0;background:rgba(255,149,0,.03);}
.header-inner{display:flex;align-items:center;justify-content:space-between;}
.logo{font-size:1.3rem;font-weight:800;letter-spacing:-.5px;}
.logo span{color:var(--accent);}
.admin-pill{font-family:var(--mono);font-size:.68rem;padding:5px 12px;border-radius:20px;border:1px solid var(--accent);color:var(--accent);display:flex;align-items:center;gap:6px;}
.logout-btn{font-family:var(--mono);font-size:.7rem;padding:6px 14px;border-radius:20px;border:1px solid var(--border);color:var(--muted);background:none;cursor:pointer;transition:all .2s;}
.logout-btn:hover{border-color:var(--warn);color:var(--warn);}

.tabs{display:flex;gap:4px;margin:28px 0 0;border-bottom:1px solid var(--border);flex-wrap:wrap;}
.tab{padding:10px 18px;font-family:var(--mono);font-size:.76rem;cursor:pointer;border:none;background:none;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .2s;}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);}
.tab:hover:not(.active){color:var(--text);}
.panel{display:none;padding:32px 0;}
.panel.active{display:block;}

/* Stats */
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;}
.stat-label{font-family:var(--mono);font-size:.64rem;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;}
.stat-value{font-size:1.6rem;font-weight:800;color:var(--accent);}

/* Users table */
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:.74rem;}
th{padding:10px 14px;text-align:left;color:var(--muted);border-bottom:1px solid var(--border);font-size:.66rem;letter-spacing:.5px;text-transform:uppercase;}
td{padding:10px 14px;border-bottom:1px solid #0d0d18;vertical-align:middle;}
tr:hover td{background:rgba(255,149,0,.03);}
.user-name{font-weight:700;color:var(--text);}
.file-count{color:var(--accent);}

/* File list in user expand */
.user-files{padding:12px 14px;background:#0d0d16;border-top:1px solid var(--border);}
.user-file-item{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #1a1a28;font-family:var(--mono);font-size:.68rem;color:var(--muted);}
.user-file-item:last-child{border-bottom:none;}
.ufi-name{color:var(--text);font-weight:600;}
.ufi-hash{color:#475569;}

/* Config form */
.config-form{max-width:460px;}
.config-section-title{font-size:.95rem;font-weight:700;margin:24px 0 14px;color:var(--accent);}
hr.divider{border:none;border-top:1px solid var(--border);margin:24px 0;}
.result-msg{font-family:var(--mono);font-size:.76rem;margin-top:12px;}
.result-msg.ok{color:var(--green);}
.result-msg.err{color:var(--warn);}

.status-pill{font-family:var(--mono);font-size:.7rem;padding:6px 14px;border-radius:20px;border:1px solid;display:flex;align-items:center;gap:6px;}
.status-pill.ok{border-color:var(--green);color:var(--green);}
.status-pill.fail{border-color:var(--warn);color:var(--warn);}
.status-pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

footer{border-top:1px solid #2a1f00;padding:16px 0;text-align:center;font-family:var(--mono);font-size:.64rem;color:var(--muted);margin-top:48px;}
@media(max-width:640px){.stats-grid{grid-template-columns:repeat(2,1fr);}th:nth-child(3),td:nth-child(3){display:none;}}
</style>
</head>
<body>

<!-- ADMIN AUTH -->
<div class="auth-page" id="adminAuthPage">
  <div class="auth-card">
    <div class="auth-logo">Block<span>Verify</span></div>
    <div class="auth-badge">🛡 ADMIN PANEL</div>
    <div class="form-group"><label class="form-label">ADMIN PASSWORD</label><input class="form-input" type="password" id="adminPassInput" placeholder="Enter admin password" onkeydown="if(event.key==='Enter')submitAdminLogin()"/></div>
    <button class="btn btn-admin" onclick="submitAdminLogin()">Access Admin Panel →</button>
    <div class="auth-msg err" id="adminLoginMsg"></div>
    <p style="font-family:var(--mono);font-size:.66rem;color:var(--muted);margin-top:20px;text-align:center"><a href="/" style="color:var(--accent)">← Back to main app</a></p>
  </div>
</div>

<!-- ADMIN SHELL -->
<div class="admin-shell" id="adminShell">
  <div class="container">
    <header>
      <div class="header-inner">
        <div class="logo">Block<span>Verify</span> <span style="font-size:.75rem;color:var(--muted);font-weight:400">/ Admin</span></div>
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="admin-pill">🛡 ADMIN</div>
          <div class="status-pill fail" id="adminPinataStatus"><span class="dot"></span><span id="adminPinataText">Checking...</span></div>
          <button class="logout-btn" onclick="adminLogout()">Logout</button>
        </div>
      </div>
    </header>

    <div class="tabs" style="margin-top:28px">
      <button class="tab active" onclick="switchAdminTab('dashboard')">📊 Dashboard</button>
      <button class="tab" onclick="switchAdminTab('users')">👥 Users</button>
      <button class="tab" onclick="switchAdminTab('config')">⚙ Config</button>
    </div>

    <!-- DASHBOARD -->
    <div class="panel active" id="apanel-dashboard">
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-label">Total Users</div><div class="stat-value" id="aStat-users">—</div></div>
        <div class="stat-card"><div class="stat-label">Total Files</div><div class="stat-value" id="aStat-files">—</div></div>
        <div class="stat-card"><div class="stat-label">Chain Blocks</div><div class="stat-value" id="aStat-blocks">—</div></div>
        <div class="stat-card"><div class="stat-label">Chain Valid</div><div class="stat-value" id="aStat-valid" style="font-size:1.4rem">—</div></div>
      </div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;font-family:var(--mono);font-size:.76rem;">
        <div style="color:var(--accent);font-weight:700;margin-bottom:10px;">IPFS / PINATA</div>
        <div style="color:var(--muted)">Latest CID: <span style="color:var(--text)" id="aStat-cid">—</span></div>
      </div>
    </div>

    <!-- USERS -->
    <div class="panel" id="apanel-users">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <h2 style="font-size:1.2rem;font-weight:800;">👥 All Users & Files</h2>
        <button class="btn-outline" onclick="loadAdminUsers()">↺ Refresh</button>
      </div>
      <div class="table-wrap">
        <table id="usersTable">
          <thead><tr><th>Username</th><th>Files</th><th>Joined</th><th>Last Login</th><th>Logins</th><th>Action</th></tr></thead>
          <tbody id="usersBody"><tr><td colspan="6" style="color:var(--muted);text-align:center;padding:30px">Loading...</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- CONFIG -->
    <div class="panel" id="apanel-config">
      <div class="config-form">
        <div class="config-section-title">🔌 Pinata IPFS Keys</div>
        <div class="form-group"><label class="form-label">API KEY</label><input class="form-input" type="text" id="aCfgApiKey" placeholder="Pinata API key"/></div>
        <div class="form-group"><label class="form-label">SECRET KEY</label><input class="form-input" type="password" id="aCfgSecretKey" placeholder="Pinata Secret key"/></div>
        <div class="form-group"><label class="form-label">POW DIFFICULTY (1–6)</label><input class="form-input" type="number" id="aCfgDifficulty" value="4" min="1" max="6"/></div>
        <button class="btn-green" onclick="saveAdminConfig()">Save & Test Connection</button>
        <div class="result-msg" id="aCfgResult"></div>

        <hr class="divider"/>
        <div class="config-section-title">🔑 Change Admin Password</div>
        <div class="form-group"><label class="form-label">CURRENT PASSWORD</label><input class="form-input" type="password" id="aOldPass" placeholder="Current admin password"/></div>
        <div class="form-group"><label class="form-label">NEW PASSWORD</label><input class="form-input" type="password" id="aNewPass" placeholder="New admin password"/></div>
        <button class="btn-green" onclick="changeAdminPass()">Update Admin Password</button>
        <div class="result-msg" id="aPassResult"></div>
      </div>
    </div>
  </div>
  <footer>BlockVerify Admin Panel • Built by <a href="https://github.com/subham23s" target="_blank" style="color:var(--accent)">Subham Mishra</a> &amp; <a href="https://github.com/Anubhav-axt" target="_blank" style="color:var(--accent)">Anubhav Pati</a></footer>
</div>

<script>
async function submitAdminLogin(){
  const pass=document.getElementById('adminPassInput').value.trim();
  const msg=document.getElementById('adminLoginMsg');
  msg.textContent='';
  if(!pass){msg.textContent='Enter password.';return;}
  try{
    const res=await fetch('/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})});
    const data=await res.json();
    if(data.success){enterAdminPanel();}
    else{msg.textContent='❌ Wrong admin password.';}
  }catch(e){msg.textContent='Error: '+e.message;}
}

function enterAdminPanel(){
  document.getElementById('adminAuthPage').style.display='none';
  document.getElementById('adminShell').style.display='block';
  loadAdminDashboard();
  checkAdminPinata();
}

async function adminLogout(){
  await fetch('/admin/logout',{method:'POST'});
  document.getElementById('adminShell').style.display='none';
  document.getElementById('adminAuthPage').style.display='flex';
  document.getElementById('adminPassInput').value='';
}

function switchAdminTab(name){
  const names=['dashboard','users','config'];
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',names[i]===name));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('apanel-'+name).classList.add('active');
  if(name==='users')loadAdminUsers();
  if(name==='dashboard')loadAdminDashboard();
}

async function loadAdminDashboard(){
  try{
    const [uRes,cRes]=await Promise.all([fetch('/admin/users'),fetch('/chain')]);
    const uData=await uRes.json();
    const cData=await cRes.json();
    const users=uData.users||[];
    const totalFiles=users.reduce((s,u)=>s+u.file_count,0);
    document.getElementById('aStat-users').textContent=users.length;
    document.getElementById('aStat-files').textContent=totalFiles;
    document.getElementById('aStat-blocks').textContent=cData.chain?cData.chain.length:'—';
    document.getElementById('aStat-valid').textContent=cData.valid?'✅':'❌';
    document.getElementById('aStat-cid').textContent=cData.cid||'Not synced';
  }catch(e){console.error(e);}
}

async function loadAdminUsers(){
  const tbody=document.getElementById('usersBody');
  tbody.innerHTML='<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:24px">Loading...</td></tr>';
  try{
    const res=await fetch('/admin/users');
    const data=await res.json();
    const users=data.users||[];
    if(users.length===0){tbody.innerHTML='<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:24px">No users yet.</td></tr>';return;}
    tbody.innerHTML=users.map(u=>`
      <tr>
        <td><span class="user-name">👤 ${u.username}</span></td>
        <td><span class="file-count">${u.file_count} files</span></td>
        <td>${new Date(u.created_at*1000).toLocaleDateString()}</td>
        <td>${u.last_login?new Date(u.last_login*1000).toLocaleDateString():'Never'}</td>
        <td>${u.login_count||0}</td>
        <td><button class="btn-outline btn-sm" onclick="toggleUserFiles('${u.username}')">View Files</button>
            <button class="btn-danger btn-sm" style="margin-left:6px" onclick="deleteUser('${u.username}')">Delete</button></td>
      </tr>
      <tr id="ufiles-${u.username}" style="display:none">
        <td colspan="6">
          <div class="user-files">
            ${u.files.length===0
              ?'<div style="color:var(--muted);font-family:var(--mono);font-size:.72rem;padding:8px">No files registered.</div>'
              :u.files.map(f=>`<div class="user-file-item"><span>${{image:'🖼️',document:'📄',ml_model:'🤖',file:'📁'}[f.type]||'📁'}</span><span class="ufi-name">${f.name}</span><span class="ufi-hash">${f.hash.substring(0,20)}...</span><span>${new Date(f.added*1000).toLocaleDateString()}</span></div>`).join('')
            }
          </div>
        </td>
      </tr>
    `).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="6" style="color:var(--warn);text-align:center;padding:24px">${e.message}</td></tr>`;}
}

function toggleUserFiles(username){
  const row=document.getElementById('ufiles-'+username);
  row.style.display=row.style.display==='none'?'table-row':'none';
}

async function deleteUser(username){
  if(!confirm(`Delete user "${username}" and all their file records?\n\nBlockchain blocks will remain.`))return;
  try{
    const res=await fetch('/admin/delete_user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username})});
    const data=await res.json();
    if(data.success)loadAdminUsers();
    else alert('Error: '+data.message);
  }catch(e){alert('Failed: '+e.message);}
}

async function saveAdminConfig(){
  const key=document.getElementById('aCfgApiKey').value.trim();
  const secret=document.getElementById('aCfgSecretKey').value.trim();
  const diff=document.getElementById('aCfgDifficulty').value;
  const result=document.getElementById('aCfgResult');
  result.textContent='Testing...'; result.className='result-msg';
  try{
    const res=await fetch('/admin/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key,secret_key:secret,difficulty:parseInt(diff)})});
    const data=await res.json();
    result.className='result-msg '+(data.success?'ok':'err');
    result.textContent=data.message;
    if(data.success)checkAdminPinata();
  }catch(e){result.className='result-msg err';result.textContent='Failed: '+e.message;}
}

async function changeAdminPass(){
  const oldP=document.getElementById('aOldPass').value.trim();
  const newP=document.getElementById('aNewPass').value.trim();
  const result=document.getElementById('aPassResult');
  result.textContent=''; result.className='result-msg';
  if(!oldP||!newP){result.className='result-msg err';result.textContent='Fill both fields.';return;}
  try{
    const res=await fetch('/admin/change_password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:oldP,new_password:newP})});
    const data=await res.json();
    result.className='result-msg '+(data.success?'ok':'err');
    result.textContent=data.message;
  }catch(e){result.className='result-msg err';result.textContent='Failed: '+e.message;}
}

async function checkAdminPinata(){
  try{
    const res=await fetch('/pinata_status');const data=await res.json();
    document.getElementById('adminPinataStatus').className='status-pill '+(data.connected?'ok':'fail');
    document.getElementById('adminPinataText').textContent=data.connected?'Pinata Connected':'Pinata Offline';
  }catch{}
}

(async()=>{
  try{const res=await fetch('/admin/auth_status');const data=await res.json();if(data.logged_in)enterAdminPanel();}catch{}
})();

// Also check main session admin flag
(async()=>{
  try{
    const res=await fetch('/admin/auth_status');
    const data=await res.json();
    if(data.logged_in){ enterAdminPanel(); }
  }catch{}
})();
</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════════════
# ROUTES — MAIN APP
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    from flask import Response
    return Response(MAIN_HTML, mimetype='text/html')

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    u = data.get("username","").strip()
    p = data.get("password","").strip()
    if not u or not p: return jsonify({"success":False,"message":"Fields required."})
    if len(u) < 3: return jsonify({"success":False,"message":"Username too short (min 3)."})
    ok, msg = create_user(u, p)
    if ok: session["user"] = u
    return jsonify({"success":ok,"message":msg})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    u = data.get("username","").strip()
    p = data.get("password","").strip()
    # Check if admin credentials
    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"success":True,"is_admin":True})
    if verify_user(u, p):
        session["user"] = u
        count = bump_login(u)
        return jsonify({"success":True,"is_admin":False,"login_count":count})
    return jsonify({"success":False})

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"success":True})

@app.route("/auth_status")
def auth_status():
    u = session.get("user")
    return jsonify({"logged_in":bool(u),"username":u or ""})

@app.route("/my_files")
def my_files():
    u = session.get("user")
    if not u: return jsonify({"error":"Unauthorized"}), 401
    try:
        bc = get_blockchain()
        hashes = set(get_user_file_hashes(u))

        # Build a lookup from blockchain blocks
        block_lookup = {}
        for block in bc.chain[1:]:
            block_lookup[block.file_hash] = block

        # Also get file metadata from users.json directly as fallback
        users = load_users()
        user_files = _normalize_files(users.get(u, {}).get("files", []))

        result = []
        seen = set()
        for fentry in user_files:
            fhash = fentry["hash"]
            if fhash in seen:
                continue
            seen.add(fhash)
            block = block_lookup.get(fhash)
            result.append({
                "index":   block.index     if block else "?",
                "file_name": block.file_name if block else fentry.get("name","unknown"),
                "file_hash": fhash,
                "file_type": block.file_type if block else fentry.get("type","file"),
                "timestamp": block.timestamp if block else fentry.get("added", 0),
                "nonce":   block.nonce     if block else 0,
                "preview": file_previews.get(fhash)
            })
        return jsonify({"files":result})
    except Exception as e:
        import traceback
        return jsonify({"error":str(e), "trace": traceback.format_exc()}), 500

@app.route("/download/<file_hash>")
def download(file_hash):
    u = session.get("user")
    if not u: return jsonify({"error":"Unauthorized"}), 401
    if file_hash not in get_user_file_hashes(u):
        return jsonify({"error":"Not your file"}), 403
    bc = get_blockchain()
    block = bc.find_block_by_hash(file_hash)
    fname = block.file_name if block else "download"
    data, actual_name = get_file_bytes(file_hash, fname)
    if not data:
        return jsonify({"error":"File not found on server"}), 404
    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    return send_file(io.BytesIO(data), mimetype=mime,
                     as_attachment=True, download_name=fname)

@app.route("/delete_file", methods=["POST"])
def delete_file():
    u = session.get("user")
    if not u: return jsonify({"success":False,"message":"Not logged in."}), 401
    data = request.get_json()
    fh = data.get("file_hash","")
    if fh not in get_user_file_hashes(u):
        return jsonify({"success":False,"message":"File not in your account."})
    remove_file_from_user(u, fh)
    file_previews.pop(fh, None)
    # Remove from disk
    import shutil
    folder = UPLOAD_DIR / fh
    if folder.exists():
        shutil.rmtree(folder)
    return jsonify({"success":True})

@app.route("/register", methods=["POST"])
def register():
    u = session.get("user")
    if not u: return jsonify({"status":"error","message":"Not logged in."}), 401
    if "file" not in request.files:
        return jsonify({"status":"error","message":"No file uploaded"}), 400
    f = request.files["file"]
    raw = f.read()
    fhash = generate_bytes_hash(raw)
    ftype = detect_file_type(f.filename)
    save_file_bytes(fhash, f.filename, raw)
    if ftype == "image":
        mime = mimetypes.guess_type(f.filename)[0] or "image/jpeg"
        file_previews[fhash] = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    try:
        bc = get_blockchain()
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500
    # Check if THIS user already registered this exact file
    user_hashes = get_user_file_hashes(u)
    if fhash in user_hashes:
        existing = bc.find_block_by_hash(fhash)
        return jsonify({"status":"exists","file_name":f.filename,"file_hash":fhash,
            "block_index":existing.index if existing else "?"})

    # Always create a new block — even if another user registered the same file
    block = bc.add_block(f.filename, fhash, ftype)
    try:
        cid = save_bc(bc)
    except Exception as e:
        return jsonify({"status":"error","message":f"Pinata save failed: {e}"}), 500
    add_file_to_user(u, fhash, f.filename, ftype)
    return jsonify({"status":"registered","file_name":f.filename,"file_hash":fhash,
        "file_type":ftype,"block_index":block.index,"nonce":block.nonce,"ipfs_cid":cid})

@app.route("/verify", methods=["POST"])
def verify():
    if "file" not in request.files:
        return jsonify({"verified":False,"reason":"no_file"}), 400
    f = request.files["file"]
    raw = f.read()
    fhash = generate_bytes_hash(raw)
    ftype = detect_file_type(f.filename)
    try:
        bc = get_blockchain()
    except Exception as e:
        return jsonify({"verified":False,"reason":"blockchain_error","message":str(e)}), 500
    block = bc.find_block_by_hash(fhash)
    valid = bc.is_chain_valid()
    if block:
        return jsonify({"verified":True,"file_name":f.filename,"file_hash":fhash,
            "file_type":ftype,"block_index":block.index,"chain_valid":valid})
    return jsonify({"verified":False,"reason":"not_found","file_name":f.filename,
        "file_hash":fhash,"file_type":ftype})

@app.route("/chain")
def chain():
    try:
        bc = get_blockchain()
        return jsonify({"chain":bc.to_list(),"valid":bc.is_chain_valid(),"cid":get_latest_cid()})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/pinata_status")
def pinata_status():
    return jsonify({"connected":test_pinata_connection()})

# ══════════════════════════════════════════════════════════════════════════
# ROUTES — ADMIN
# ══════════════════════════════════════════════════════════════════════════

@app.route("/admin")
def admin_page():
    from flask import Response
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    u = data.get("username", "").strip()
    p = data.get("password", "").strip()
    # Accept either: admin credentials OR already has admin session
    if (u == ADMIN_USERNAME and p == ADMIN_PASSWORD) or session.get("admin"):
        session["admin"] = True
        return jsonify({"success":True})
    return jsonify({"success":False})

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success":True})

@app.route("/admin/auth_status")
def admin_auth_status():
    return jsonify({"logged_in":bool(session.get("admin"))})

@app.route("/admin/users")
def admin_users():
    if not session.get("admin"):
        return jsonify({"error":"Unauthorized"}), 401
    users = load_users()
    result = []
    for uname, udata in users.items():
        result.append({
            "username": uname,
            "created_at": udata.get("created_at", 0),
            "last_login": udata.get("last_login"),
            "login_count": udata.get("login_count", 0),
            "file_count": len(udata.get("files", [])),
            "files": udata.get("files", [])
        })
    return jsonify({"users": result})

@app.route("/admin/delete_user", methods=["POST"])
def admin_delete_user():
    if not session.get("admin"):
        return jsonify({"success":False,"message":"Unauthorized"}), 401
    data = request.get_json()
    username = data.get("username","")
    users = load_users()
    if username not in users:
        return jsonify({"success":False,"message":"User not found."})
    del users[username]
    save_users(users)
    return jsonify({"success":True})

@app.route("/admin/config", methods=["POST"])
def admin_config():
    if not session.get("admin"):
        return jsonify({"success":False,"message":"Unauthorized"}), 401
    import pinata_utils as pu
    data = request.get_json()
    api_key = data.get("api_key","")
    secret_key = data.get("secret_key","")
    pu.PINATA_API_KEY = api_key
    pu.PINATA_SECRET_KEY = secret_key
    os.environ["PINATA_API_KEY"] = api_key
    os.environ["PINATA_SECRET_KEY"] = secret_key
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k,v = line.split("=",1)
                    env[k.strip()] = v.strip()
    env["PINATA_API_KEY"] = api_key
    env["PINATA_SECRET_KEY"] = secret_key
    with open(".env","w") as f:
        for k,v in env.items(): f.write(f"{k}={v}\n")
    connected = pu.test_pinata_connection()
    return jsonify({"success":connected,
        "message":"✅ Connected! Keys saved." if connected else "❌ Connection failed."})

@app.route("/admin/change_password", methods=["POST"])
def admin_change_password():
    if not session.get("admin"):
        return jsonify({"success":False,"message":"Unauthorized"}), 401
    global ADMIN_PASSWORD
    data = request.get_json()
    old_p = data.get("old_password","")
    new_p = data.get("new_password","")
    if old_p != ADMIN_PASSWORD:
        return jsonify({"success":False,"message":"❌ Current password is wrong."})
    if len(new_p) < 6:
        return jsonify({"success":False,"message":"❌ New password too short (min 6)."})
    ADMIN_PASSWORD = new_p
    os.environ["ADMIN_PASSWORD"] = new_p
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k,v = line.split("=",1)
                    env[k.strip()] = v.strip()
    env["ADMIN_PASSWORD"] = new_p
    with open(".env","w") as f:
        for k,v in env.items(): f.write(f"{k}={v}\n")
    return jsonify({"success":True,"message":"✅ Admin password updated!"})

if __name__ == "__main__":
    import webbrowser
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, port=5000)