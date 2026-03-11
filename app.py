import webbrowser
from flask import Flask, request, jsonify, render_template_string
from blockchain import Blockchain
from hash_utils import generate_bytes_hash, detect_file_type
from pinata_utils import (
    save_blockchain_to_pinata,
    load_blockchain_from_pinata,
    test_pinata_connection,
    get_latest_cid
)
import os
import time

app = Flask(__name__)

# Auto-load .env file if exists
def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
                    import pinata_utils as pu
                    if key.strip() == "PINATA_API_KEY": pu.PINATA_API_KEY = val.strip()
                    if key.strip() == "PINATA_SECRET_KEY": pu.PINATA_SECRET_KEY = val.strip()

load_env()

# ── Load or create blockchain ──────────────────────────────────────────────────
def get_blockchain() -> Blockchain:
    try:
        chain_data = load_blockchain_from_pinata()
        if chain_data:
            return Blockchain.from_list(chain_data)
    except Exception:
        pass
    return Blockchain(difficulty=4)


def save_blockchain(bc: Blockchain) -> str:
    try:
        cid = save_blockchain_to_pinata(bc.to_list())
        return cid
    except Exception as e:
        raise e


# ── HTML Template ───────────────────────────────────────────────────────────────
HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>BlockVerify — ML & Document Integrity</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --border: #1e1e2e;
    --accent: #00ff88;
    --accent2: #7c3aed;
    --warn: #ff4444;
    --text: #e2e8f0;
    --muted: #64748b;
    --mono: 'Space Mono', monospace;
    --sans: 'Syne', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Grid background */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0,255,136,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,255,136,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .container { max-width: 1100px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }

  /* Header */
  header {
    border-bottom: 1px solid var(--border);
    padding: 24px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .logo {
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.5px;
  }
  .logo span { color: var(--accent); }

  .status-pill {
    font-family: var(--mono);
    font-size: 0.7rem;
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .status-pill.ok { border-color: var(--accent); color: var(--accent); }
  .status-pill.fail { border-color: var(--warn); color: var(--warn); }
  .status-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  /* Hero */
  .hero { padding: 60px 0 40px; }
  .hero h1 { font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 800; line-height: 1.1; letter-spacing: -1px; }
  .hero h1 em { font-style: normal; color: var(--accent); }
  .hero p { margin-top: 16px; color: var(--muted); font-size: 1rem; max-width: 540px; line-height: 1.6; }

  /* Tabs */
  .tabs { display: flex; gap: 4px; margin: 40px 0 0; border-bottom: 1px solid var(--border); }
  .tab {
    padding: 12px 24px;
    font-family: var(--mono);
    font-size: 0.8rem;
    cursor: pointer;
    border: none;
    background: none;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: all 0.2s;
    letter-spacing: 0.5px;
  }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab:hover:not(.active) { color: var(--text); }

  /* Panels */
  .panel { display: none; padding: 40px 0; }
  .panel.active { display: block; }

  /* Upload zone */
  .upload-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 60px 40px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s;
    position: relative;
    overflow: hidden;
  }
  .upload-zone::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, rgba(0,255,136,0.04) 0%, transparent 70%);
    opacity: 0;
    transition: opacity 0.3s;
  }
  .upload-zone:hover, .upload-zone.drag { border-color: var(--accent); }
  .upload-zone:hover::before, .upload-zone.drag::before { opacity: 1; }

  .upload-icon { font-size: 3rem; margin-bottom: 16px; }
  .upload-zone h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }
  .upload-zone p { color: var(--muted); font-size: 0.85rem; font-family: var(--mono); }
  .upload-zone input { display: none; }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 28px;
    border-radius: 8px;
    font-family: var(--mono);
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    letter-spacing: 0.5px;
  }
  .btn-primary { background: var(--accent); color: #000; }
  .btn-primary:hover { background: #00cc6a; transform: translateY(-1px); }
  .btn-primary:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; transform: none; }
  .btn-outline { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn-outline:hover { background: rgba(0,255,136,0.08); }

  /* Result card */
  .result-card {
    margin-top: 24px;
    border-radius: 12px;
    padding: 28px;
    border: 1px solid;
    animation: slideUp 0.3s ease;
  }
  @keyframes slideUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
  .result-card.success { border-color: var(--accent); background: rgba(0,255,136,0.05); }
  .result-card.danger { border-color: var(--warn); background: rgba(255,68,68,0.05); }
  .result-card.info { border-color: var(--accent2); background: rgba(124,58,237,0.05); }

  .result-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }
  .result-card.success .result-title { color: var(--accent); }
  .result-card.danger .result-title { color: var(--warn); }
  .result-card.info .result-title { color: #a78bfa; }

  .result-meta { font-family: var(--mono); font-size: 0.75rem; color: var(--muted); line-height: 2; }
  .hash-val { color: var(--text); word-break: break-all; }

  /* Mining animation */
  .mining-bar {
    margin-top: 16px;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    display: none;
  }
  .mining-bar.active { display: block; }
  .mining-bar::after {
    content: '';
    display: block;
    height: 100%;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    animation: mine 1.5s infinite;
  }
  @keyframes mine { from{transform:translateX(-100%)} to{transform:translateX(300%)} }

  /* Chain viewer */
  .chain-list { display: flex; flex-direction: column; gap: 12px; }
  .chain-block {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    display: grid;
    grid-template-columns: 60px 1fr auto;
    gap: 16px;
    align-items: center;
    transition: border-color 0.2s;
  }
  .chain-block:hover { border-color: var(--accent2); }

  .block-index {
    width: 48px; height: 48px;
    border-radius: 8px;
    background: linear-gradient(135deg, var(--accent2), #4f46e5);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1rem;
  }
  .block-name { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; }
  .block-meta { font-family: var(--mono); font-size: 0.7rem; color: var(--muted); }
  .block-badge {
    font-family: var(--mono);
    font-size: 0.65rem;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--muted);
    white-space: nowrap;
  }

  .chain-link {
    text-align: center;
    color: var(--accent);
    font-size: 1.2rem;
    opacity: 0.4;
    padding: 4px 0;
  }

  /* Stats row */
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }
  .stat-label { font-family: var(--mono); font-size: 0.7rem; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
  .stat-value { font-size: 1.8rem; font-weight: 800; color: var(--accent); }

  /* Validity banner */
  .validity-banner {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px;
    border-radius: 8px;
    font-family: var(--mono);
    font-size: 0.8rem;
    margin-bottom: 24px;
    border: 1px solid;
  }
  .validity-banner.valid { border-color: var(--accent); background: rgba(0,255,136,0.05); color: var(--accent); }
  .validity-banner.invalid { border-color: var(--warn); background: rgba(255,68,68,0.05); color: var(--warn); }

  /* Config panel */
  .config-form { max-width: 480px; }
  .form-group { margin-bottom: 20px; }
  .form-label { display: block; font-family: var(--mono); font-size: 0.75rem; color: var(--muted); margin-bottom: 8px; letter-spacing: 0.5px; }
  .form-input {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 0.85rem;
    transition: border-color 0.2s;
  }
  .form-input:focus { outline: none; border-color: var(--accent); }
  .form-input::placeholder { color: var(--muted); }

  /* Spinner */
  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid rgba(0,0,0,0.2);
    border-top-color: #000;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .hidden { display: none !important; }

  footer {
    border-top: 1px solid var(--border);
    padding: 24px 0;
    text-align: center;
    font-family: var(--mono);
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 60px;
  }

  @media (max-width: 640px) {
    .stats { grid-template-columns: 1fr; }
    .chain-block { grid-template-columns: 48px 1fr; }
    .block-badge { display: none; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">Block<span>Verify</span></div>
    <div class="status-pill" id="pinataStatus">
      <span class="dot"></span>
      <span id="pinataStatusText">Checking Pinata...</span>
    </div>
  </header>

  <div class="hero">
    <h1>Verify <em>Integrity</em><br/>with Blockchain</h1>
    <p>Upload any image, document, or ML model. We hash it with SHA-256, mine it into a blockchain block using Proof-of-Work, and store everything on IPFS via Pinata.</p>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('register')">⬆ Register</button>
    <button class="tab" onclick="switchTab('verify')">🔍 Verify</button>
    <button class="tab" onclick="switchTab('chain')">⛓ Chain Explorer</button>
    <button class="tab" onclick="switchTab('config')">⚙ Config</button>
  </div>

  <!-- REGISTER PANEL -->
  <div class="panel active" id="panel-register">
    <div class="upload-zone" id="registerZone" onclick="document.getElementById('registerInput').click()">
      <div class="upload-icon">📁</div>
      <h3>Drop a file to register</h3>
      <p>Images, Documents, ML Models — anything goes</p>
      <input type="file" id="registerInput" onchange="handleRegisterFile(this.files[0])"/>
    </div>
    <div class="mining-bar" id="registerMining"></div>
    <div id="registerStatus"></div>
  </div>

  <!-- VERIFY PANEL -->
  <div class="panel" id="panel-verify">
    <div class="upload-zone" id="verifyZone" onclick="document.getElementById('verifyInput').click()">
      <div class="upload-icon">🔍</div>
      <h3>Drop a file to verify</h3>
      <p>We'll check if this exact file is registered in the blockchain</p>
      <input type="file" id="verifyInput" onchange="handleVerifyFile(this.files[0])"/>
    </div>
    <div class="mining-bar" id="verifyMining"></div>
    <div id="verifyStatus"></div>
  </div>

  <!-- CHAIN EXPLORER -->
  <div class="panel" id="panel-chain">
    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Total Blocks</div>
        <div class="stat-value" id="statBlocks">—</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">PoW Difficulty</div>
        <div class="stat-value" id="statDifficulty">4</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">IPFS CID</div>
        <div class="stat-value" style="font-size:0.75rem;font-family:var(--mono);word-break:break-all;margin-top:8px" id="statCID">—</div>
      </div>
    </div>
    <div id="validityBanner"></div>
    <div class="chain-list" id="chainList">
      <p style="color:var(--muted);font-family:var(--mono);font-size:0.85rem">Loading chain...</p>
    </div>
    <br/>
    <button class="btn btn-outline" onclick="loadChain()">↺ Refresh</button>
  </div>

  <!-- CONFIG PANEL -->
  <div class="panel" id="panel-config">
    <div class="config-form">
      <h2 style="font-size:1.3rem;font-weight:700;margin-bottom:8px">Pinata Configuration</h2>
      <p style="color:var(--muted);font-size:0.85rem;margin-bottom:28px">Get your API keys from <a href="https://pinata.cloud" target="_blank" style="color:var(--accent)">pinata.cloud</a> → API Keys</p>
      <div class="form-group">
        <label class="form-label">PINATA API KEY</label>
        <input class="form-input" type="text" id="cfgApiKey" placeholder="Enter your Pinata API key"/>
      </div>
      <div class="form-group">
        <label class="form-label">PINATA SECRET KEY</label>
        <input class="form-input" type="password" id="cfgSecretKey" placeholder="Enter your Pinata Secret key"/>
      </div>
      <div class="form-group">
        <label class="form-label">POW DIFFICULTY (1–6)</label>
        <input class="form-input" type="number" id="cfgDifficulty" value="4" min="1" max="6"/>
      </div>
      <button class="btn btn-primary" onclick="saveConfig()">Save & Test Connection</button>
      <div id="configResult" style="margin-top:16px;font-family:var(--mono);font-size:0.8rem"></div>
    </div>
  </div>
</div>

<footer>
  BlockVerify • Built by Anubhav pati and Subham Mishra 
  <br/>
  <p>This is our github profiles </p>
  <a href="https://github.com/Anubhav-axt" target="_blank">Anubhav pati</a> | <a href="https://github.com/subham23s" target="_blank">Subham Mishra</a>
</footer>

<script>
// ── Tab switching ──────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    t.classList.toggle('active', ['register','verify','chain','config'][i] === name);
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'chain') loadChain();
}

// ── Drag & drop ────────────────────────────────────────────────────────────
['registerZone','verifyZone'].forEach(id => {
  const zone = document.getElementById(id);
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag');
    const f = e.dataTransfer.files[0];
    if (!f) return;
    if (id === 'registerZone') handleRegisterFile(f);
    else handleVerifyFile(f);
  });
});

// ── Register ───────────────────────────────────────────────────────────────
async function handleRegisterFile(file) {
  if (!file) return;
  const bar = document.getElementById('registerMining');
  const status = document.getElementById('registerStatus');
  bar.classList.add('active');
  status.innerHTML = `<p style="font-family:var(--mono);font-size:0.8rem;color:var(--muted);margin-top:16px">⛏ Mining block for <strong>${file.name}</strong>...</p>`;

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/register', { method: 'POST', body: fd });
    const data = await res.json();
    bar.classList.remove('active');

    if (data.status === 'registered') {
      status.innerHTML = `
        <div class="result-card success">
          <div class="result-title">✅ Registered Successfully</div>
          <div class="result-meta">
            FILE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>
            TYPE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_type}</span><br/>
            HASH &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>
            BLOCK &nbsp;&nbsp;&nbsp;<span class="hash-val">#${data.block_index}</span><br/>
            NONCE &nbsp;&nbsp;&nbsp;<span class="hash-val">${data.nonce}</span><br/>
            IPFS CID <span class="hash-val">${data.ipfs_cid}</span>
          </div>
        </div>`;
    } else if (data.status === 'exists') {
      status.innerHTML = `
        <div class="result-card info">
          <div class="result-title">ℹ️ Already Registered</div>
          <div class="result-meta">
            FILE &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>
            BLOCK &nbsp;&nbsp;&nbsp;<span class="hash-val">#${data.block_index}</span><br/>
            HASH &nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span>
          </div>
        </div>`;
    } else {
      status.innerHTML = `<div class="result-card danger"><div class="result-title">❌ Error</div><div class="result-meta">${data.message}</div></div>`;
    }
  } catch (e) {
    bar.classList.remove('active');
    status.innerHTML = `<div class="result-card danger"><div class="result-title">❌ Request Failed</div><div class="result-meta">${e.message}</div></div>`;
  }
}

// ── Verify ─────────────────────────────────────────────────────────────────
async function handleVerifyFile(file) {
  if (!file) return;
  const bar = document.getElementById('verifyMining');
  const status = document.getElementById('verifyStatus');
  bar.classList.add('active');
  status.innerHTML = `<p style="font-family:var(--mono);font-size:0.8rem;color:var(--muted);margin-top:16px">🔍 Verifying <strong>${file.name}</strong>...</p>`;

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/verify', { method: 'POST', body: fd });
    const data = await res.json();
    bar.classList.remove('active');

    if (data.verified) {
      status.innerHTML = `
        <div class="result-card success">
          <div class="result-title">✅ Integrity Verified</div>
          <div class="result-meta">
            FILE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>
            TYPE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_type}</span><br/>
            HASH &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>
            REG BLOCK &nbsp;<span class="hash-val">#${data.block_index}</span><br/>
            CHAIN OK &nbsp;&nbsp;<span class="hash-val">${data.chain_valid ? '✅ Valid' : '❌ Tampered'}</span>
          </div>
        </div>`;
    } else {
      status.innerHTML = `
        <div class="result-card danger">
          <div class="result-title">❌ ${data.reason === 'not_found' ? 'File Not Registered' : 'Tampered / Unknown File'}</div>
          <div class="result-meta">
            FILE &nbsp;&nbsp;<span class="hash-val">${data.file_name}</span><br/>
            HASH &nbsp;&nbsp;<span class="hash-val">${data.file_hash}</span><br/>
            ${data.reason === 'not_found' ? 'This file has no record in the blockchain.' : 'Hash does not match any registered file.'}
          </div>
        </div>`;
    }
  } catch (e) {
    bar.classList.remove('active');
    status.innerHTML = `<div class="result-card danger"><div class="result-title">❌ Request Failed</div><div class="result-meta">${e.message}</div></div>`;
  }
}

// ── Chain Explorer ─────────────────────────────────────────────────────────
async function loadChain() {
  const list = document.getElementById('chainList');
  list.innerHTML = '<p style="color:var(--muted);font-family:var(--mono);font-size:0.85rem">Loading...</p>';
  try {
    const res = await fetch('/chain');
    const data = await res.json();

    document.getElementById('statBlocks').textContent = data.chain.length;
    document.getElementById('statCID').textContent = data.cid || 'Not synced';

    const banner = document.getElementById('validityBanner');
    banner.innerHTML = `<div class="validity-banner ${data.valid ? 'valid' : 'invalid'}">
      ${data.valid ? '🔒 Blockchain is valid — all blocks intact' : '⚠️ Chain integrity compromised!'}
    </div>`;

    list.innerHTML = data.chain.map((b, i) => `
      ${i > 0 ? '<div class="chain-link">↓</div>' : ''}
      <div class="chain-block">
        <div class="block-index">${b.index}</div>
        <div>
          <div class="block-name">${b.file_name}</div>
          <div class="block-meta">
            ${new Date(b.timestamp * 1000).toLocaleString()} &nbsp;|&nbsp;
            nonce: ${b.nonce} &nbsp;|&nbsp;
            ${b.file_type}
          </div>
          <div class="block-meta" style="margin-top:4px;color:#475569">${b.current_hash.substring(0,32)}...</div>
        </div>
        <div class="block-badge">${b.file_type.toUpperCase()}</div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = `<p style="color:var(--warn);font-family:var(--mono);font-size:0.85rem">Error loading chain: ${e.message}</p>`;
  }
}

// ── Config ─────────────────────────────────────────────────────────────────
async function saveConfig() {
  const key = document.getElementById('cfgApiKey').value.trim();
  const secret = document.getElementById('cfgSecretKey').value.trim();
  const diff = document.getElementById('cfgDifficulty').value;
  const result = document.getElementById('configResult');
  result.textContent = 'Testing connection...';
  try {
    const res = await fetch('/config', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ api_key: key, secret_key: secret, difficulty: parseInt(diff) })
    });
    const data = await res.json();
    result.style.color = data.success ? 'var(--accent)' : 'var(--warn)';
    result.textContent = data.message;
    if (data.success) checkPinataStatus();
  } catch (e) {
    result.style.color = 'var(--warn)';
    result.textContent = 'Failed: ' + e.message;
  }
}

// ── Pinata status ──────────────────────────────────────────────────────────
async function checkPinataStatus() {
  try {
    const res = await fetch('/pinata_status');
    const data = await res.json();
    const pill = document.getElementById('pinataStatus');
    const text = document.getElementById('pinataStatusText');
    pill.className = 'status-pill ' + (data.connected ? 'ok' : 'fail');
    text.textContent = data.connected ? 'Pinata Connected' : 'Pinata Offline';
  } catch {}
}

checkPinataStatus();
</script>
</body>
</html>'''


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/register", methods=["POST"])
def register():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    f = request.files["file"]
    file_bytes = f.read()
    file_hash = generate_bytes_hash(file_bytes)
    file_type = detect_file_type(f.filename)

    try:
        bc = get_blockchain()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Could not load blockchain: {str(e)}"}), 500

    existing = bc.find_block_by_hash(file_hash)
    if existing:
        return jsonify({
            "status": "exists",
            "file_name": f.filename,
            "file_hash": file_hash,
            "block_index": existing.index
        })

    block = bc.add_block(f.filename, file_hash, file_type)

    try:
        cid = save_blockchain(bc)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Pinata save failed: {str(e)}"}), 500

    return jsonify({
        "status": "registered",
        "file_name": f.filename,
        "file_hash": file_hash,
        "file_type": file_type,
        "block_index": block.index,
        "nonce": block.nonce,
        "ipfs_cid": cid
    })


@app.route("/verify", methods=["POST"])
def verify():
    if "file" not in request.files:
        return jsonify({"verified": False, "reason": "no_file"}), 400

    f = request.files["file"]
    file_bytes = f.read()
    file_hash = generate_bytes_hash(file_bytes)
    file_type = detect_file_type(f.filename)

    try:
        bc = get_blockchain()
    except Exception as e:
        return jsonify({"verified": False, "reason": "blockchain_error", "message": str(e)}), 500

    block = bc.find_block_by_hash(file_hash)
    chain_valid = bc.is_chain_valid()

    if block:
        return jsonify({
            "verified": True,
            "file_name": f.filename,
            "file_hash": file_hash,
            "file_type": file_type,
            "block_index": block.index,
            "chain_valid": chain_valid
        })
    else:
        return jsonify({
            "verified": False,
            "reason": "not_found",
            "file_name": f.filename,
            "file_hash": file_hash,
            "file_type": file_type
        })


@app.route("/chain")
def chain():
    try:
        bc = get_blockchain()
        return jsonify({
            "chain": bc.to_list(),
            "valid": bc.is_chain_valid(),
            "cid": get_latest_cid()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/pinata_status")
def pinata_status():
    connected = test_pinata_connection()
    return jsonify({"connected": connected})


@app.route("/config", methods=["POST"])
def config():
    import pinata_utils as pu
    data = request.get_json()
    api_key = data.get("api_key", "")
    secret_key = data.get("secret_key", "")

    # Set in module
    pu.PINATA_API_KEY = api_key
    pu.PINATA_SECRET_KEY = secret_key

    # Set in env for current process
    os.environ["PINATA_API_KEY"] = api_key
    os.environ["PINATA_SECRET_KEY"] = secret_key

    # Save to .env file permanently
    with open(".env", "w") as f:
        f.write(f"PINATA_API_KEY={api_key}\n")
        f.write(f"PINATA_SECRET_KEY={secret_key}\n")

    connected = pu.test_pinata_connection()
    return jsonify({
        "success": connected,
        "message": "✅ Connected to Pinata successfully! Keys saved." if connected else "❌ Connection failed. Check your API keys."
    })


if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, port=5000)