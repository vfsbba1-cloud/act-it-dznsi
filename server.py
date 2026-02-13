#!/usr/bin/env python3
"""
VFS License Management Server
==============================
python3 server.py

Admin panel: http://YOUR_IP:5000/admin
API: http://YOUR_IP:5000/api/check?device_id=XXX
"""

from flask import Flask, request, jsonify, render_template_string, Response
from datetime import datetime, timedelta
from functools import wraps
import json, os

app = Flask(__name__)

# ===== CONFIG =====
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"  # CHANGE THIS!
DB_FILE = "licenses.json"
DEFAULT_DAYS = 30
PORT = int(os.environ.get("PORT", 5000))
# ==================

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"devices": {}}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2, default=str)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return decorated

# ===== API =====

@app.route('/api/check', methods=['GET'])
def api_check():
    device_id = request.args.get('device_id', '')
    if not device_id:
        return "ERROR: No device_id", 400
    db = load_db()
    dev = db["devices"].get(device_id)
    if not dev or not dev.get("active"):
        return "NOT_ACTIVE", 200
    expiry = datetime.fromisoformat(dev["expiry"])
    if datetime.now() > expiry:
        dev["active"] = False
        save_db(db)
        return "NOT_ACTIVE: Expired", 200
    days_left = (expiry - datetime.now()).days
    return f"ACTIVE: {days_left} days left", 200

@app.route('/api/activate', methods=['POST'])
@require_auth
def api_activate():
    data = request.json or {}
    device_id = data.get('device_id', '').strip()
    days = int(data.get('days', DEFAULT_DAYS))
    note = data.get('note', '')
    if not device_id:
        return jsonify({"error": "device_id required"}), 400
    db = load_db()
    expiry = datetime.now() + timedelta(days=days)
    db["devices"][device_id] = {
        "active": True,
        "activated_at": datetime.now().isoformat(),
        "expiry": expiry.isoformat(),
        "days": days,
        "note": note
    }
    save_db(db)
    return jsonify({"status": "activated", "device_id": device_id, "expiry": expiry.isoformat()})

@app.route('/api/deactivate', methods=['POST'])
@require_auth
def api_deactivate():
    data = request.json or {}
    device_id = data.get('device_id', '').strip()
    if not device_id:
        return jsonify({"error": "device_id required"}), 400
    db = load_db()
    if device_id in db["devices"]:
        db["devices"][device_id]["active"] = False
        save_db(db)
    return jsonify({"status": "deactivated", "device_id": device_id})

@app.route('/api/delete', methods=['POST'])
@require_auth
def api_delete():
    data = request.json or {}
    device_id = data.get('device_id', '').strip()
    db = load_db()
    if device_id in db["devices"]:
        del db["devices"][device_id]
        save_db(db)
    return jsonify({"status": "deleted"})

@app.route('/api/list', methods=['GET'])
@require_auth
def api_list():
    db = load_db()
    return jsonify(db["devices"])

# ===== ADMIN PANEL =====

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>VFS License Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; color: #333; }
        .header { background: linear-gradient(135deg, #D32F2F, #FF5722); color: white; padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; }
        .container { max-width: 900px; margin: 20px auto; padding: 0 15px; }
        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .card h2 { color: #D32F2F; margin-bottom: 15px; font-size: 18px; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 10px; font-size: 14px; }
        .btn { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; color: white; }
        .btn-activate { background: #4CAF50; }
        .btn-deactivate { background: #FF9800; }
        .btn-delete { background: #f44336; }
        .btn:hover { opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }
        th { background: #f9f9f9; font-weight: 600; }
        .status-active { color: #4CAF50; font-weight: bold; }
        .status-inactive { color: #f44336; font-weight: bold; }
        .status-expired { color: #FF9800; font-weight: bold; }
        #msg { padding: 10px; border-radius: 6px; margin-bottom: 10px; display: none; }
        .msg-ok { background: #e8f5e9; color: #2e7d32; }
        .msg-err { background: #fbe9e7; color: #c62828; }
        .stats { display: flex; gap: 10px; margin-bottom: 15px; }
        .stat { flex: 1; background: white; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .stat .num { font-size: 28px; font-weight: bold; color: #D32F2F; }
        .stat .label { font-size: 12px; color: #999; }
    </style>
</head>
<body>
    <div class="header">
        <h1>VFS License Manager</h1>
        <p>Admin Panel</p>
    </div>
    <div class="container">
        <div class="stats">
            <div class="stat"><div class="num" id="totalDevices">-</div><div class="label">Total</div></div>
            <div class="stat"><div class="num" id="activeDevices">-</div><div class="label">Active</div></div>
            <div class="stat"><div class="num" id="expiredDevices">-</div><div class="label">Expired</div></div>
        </div>

        <div class="card">
            <h2>Activate Device</h2>
            <div id="msg"></div>
            <input id="deviceId" placeholder="Device ID (ex: VFS-abc123def456)" />
            <input id="days" type="number" value="30" placeholder="Days" />
            <input id="note" placeholder="Note (optional: client name)" />
            <button class="btn btn-activate" onclick="activate()">ACTIVATE</button>
        </div>

        <div class="card">
            <h2>Licensed Devices</h2>
            <table>
                <thead><tr><th>Device ID</th><th>Status</th><th>Expiry</th><th>Days</th><th>Note</th><th>Actions</th></tr></thead>
                <tbody id="deviceList"></tbody>
            </table>
        </div>
    </div>

    <script>
        const headers = {'Content-Type': 'application/json'};
        
        function showMsg(text, ok) {
            const m = document.getElementById('msg');
            m.textContent = text;
            m.className = ok ? 'msg-ok' : 'msg-err';
            m.style.display = 'block';
            setTimeout(() => m.style.display = 'none', 3000);
        }

        async function activate() {
            const device_id = document.getElementById('deviceId').value.trim();
            const days = document.getElementById('days').value;
            const note = document.getElementById('note').value;
            if (!device_id) { showMsg('Enter Device ID!', false); return; }
            const r = await fetch('/api/activate', {method:'POST', headers, body: JSON.stringify({device_id, days, note})});
            if (r.ok) { showMsg('Device activated!', true); document.getElementById('deviceId').value=''; loadDevices(); }
            else showMsg('Error!', false);
        }

        async function deactivate(id) {
            if (!confirm('Deactivate ' + id + '?')) return;
            await fetch('/api/deactivate', {method:'POST', headers, body: JSON.stringify({device_id: id})});
            loadDevices();
        }

        async function deleteDevice(id) {
            if (!confirm('DELETE ' + id + '?')) return;
            await fetch('/api/delete', {method:'POST', headers, body: JSON.stringify({device_id: id})});
            loadDevices();
        }

        async function loadDevices() {
            const r = await fetch('/api/list');
            const devices = await r.json();
            const tbody = document.getElementById('deviceList');
            tbody.innerHTML = '';
            let total=0, active=0, expired=0;
            
            for (const [id, dev] of Object.entries(devices)) {
                total++;
                const expiry = new Date(dev.expiry);
                const now = new Date();
                let status, statusClass;
                if (!dev.active) { status='INACTIVE'; statusClass='status-inactive'; }
                else if (now > expiry) { status='EXPIRED'; statusClass='status-expired'; expired++; }
                else { status='ACTIVE'; statusClass='status-active'; active++; }
                
                const daysLeft = dev.active ? Math.max(0, Math.ceil((expiry-now)/(1000*60*60*24))) : 0;
                
                tbody.innerHTML += `<tr>
                    <td style="font-family:monospace;font-size:12px">${id}</td>
                    <td class="${statusClass}">${status}</td>
                    <td>${expiry.toLocaleDateString()}</td>
                    <td>${daysLeft}d left</td>
                    <td>${dev.note||''}</td>
                    <td>
                        ${dev.active ? `<button class="btn btn-deactivate" style="padding:5px 10px;font-size:11px" onclick="deactivate('${id}')">OFF</button>` : 
                        `<button class="btn btn-activate" style="padding:5px 10px;font-size:11px" onclick="reactivate('${id}')">ON</button>`}
                        <button class="btn btn-delete" style="padding:5px 10px;font-size:11px" onclick="deleteDevice('${id}')">DEL</button>
                    </td>
                </tr>`;
            }
            document.getElementById('totalDevices').textContent = total;
            document.getElementById('activeDevices').textContent = active;
            document.getElementById('expiredDevices').textContent = expired;
        }

        async function reactivate(id) {
            const days = prompt('How many days?', '30');
            if (!days) return;
            await fetch('/api/activate', {method:'POST', headers, body: JSON.stringify({device_id: id, days: parseInt(days)})});
            loadDevices();
        }

        loadDevices();
    </script>
</body>
</html>
"""

@app.route('/admin')
@require_auth
def admin():
    return render_template_string(ADMIN_HTML)

@app.route('/')
def index():
    return '<h1>VFS License Server</h1><p><a href="/admin">Admin Panel</a></p>'

if __name__ == '__main__':
    print(f"\\n{'='*50}")
    print(f"  VFS License Server")
    print(f"  Admin: http://0.0.0.0:{PORT}/admin")
    print(f"  User: {ADMIN_USER} / {ADMIN_PASS}")
    print(f"{'='*50}\\n")
    app.run(host='0.0.0.0', port=PORT, debug=False)
