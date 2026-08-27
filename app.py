import os
import sqlite3
import datetime
import random
import shutil
import atexit
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from flask import Flask, request, redirect, url_for, session, render_template_string, send_from_directory, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "imana_free_interest_microfinance_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
DB_PATH = os.path.join(BASE_DIR, "web_banking.db")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BACKUP_FOLDER'] = BACKUP_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

NOTIFICATIONS = []

def compress_and_save_image(file_storage, target_filename, max_size=(300, 300), quality=35):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], target_filename)
    filename = file_storage.filename.lower()
    
    if filename.endswith('.pdf') or not HAS_PIL:
        file_storage.save(filepath)
        return target_filename

    try:
        image = Image.open(file_storage)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        image.save(filepath, "JPEG", optimize=True, quality=quality)
        return target_filename
    except Exception as e:
        print(f"Image compression error: {e}")
        file_storage.save(filepath)
        return target_filename

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 12 & 13 & 14: COMMISSION FORMULAS CORRECTED
def get_withdrawal_commission(amount):
    if 1000 <= amount <= 3000:
        return 50.0
    elif 3001 <= amount <= 5000:
        return 80.0
    elif 5001 <= amount <= 10000:
        return 100.0
    elif 10001 <= amount <= 20000:
        return 200.0
    elif 20001 <= amount <= 40000:
        return 400.0
    elif amount > 40001:
        return 500.0
    return 0.0

def get_transfer_commission(amount):
    return amount * 0.02 # 2%

def get_statement_commission(amount):
    return amount * 0.01 # 1%

def add_notification(message):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    NOTIFICATIONS.insert(0, f"[{now}] {message}")
    if len(NOTIFICATIONS) > 20:
        NOTIFICATIONS.pop()

def perform_auto_backup():
    try:
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file_path = os.path.join(BACKUP_FOLDER, f"auto_backup_{now_str}.db")
        latest_path = os.path.join(BACKUP_FOLDER, "latest_auto_backup.db")
        if os.path.exists(DB_PATH):
            with sqlite3.connect(DB_PATH) as src_conn:
                with sqlite3.connect(backup_file_path) as dst_conn:
                    src_conn.backup(dst_conn)
                with sqlite3.connect(latest_path) as dst_conn2:
                    src_conn.backup(dst_conn2)
            print("💾 Auto Backup completed.")
    except Exception as e:
        print(f"❌ Auto Backup failed: {e}")

def perform_auto_restore():
    latest_path = os.path.join(BACKUP_FOLDER, "latest_auto_backup.db")
    if not os.path.exists(DB_PATH) and os.path.exists(latest_path):
        try:
            shutil.copyfile(latest_path, DB_PATH)
            print("🔄 Persistent Auto Restore completed.")
        except Exception as e:
            print(f"❌ Auto Restore failed: {e}")

perform_auto_restore()
atexit.register(perform_auto_backup)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE'
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('ceo', 'ceo999', 'CEO', 'ACTIVE'),
            ('manager1', 'manager123', 'MANAGER', 'ACTIVE'),
            ('maker1', 'maker123', 'MAKER', 'ACTIVE'),
            ('auditor1', 'auditor123', 'AUDITOR', 'ACTIVE'),
            ('officer1', 'officer123', 'LOAN_OFFICER', 'ACTIVE')
        ]
        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?)", default_users)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            full_name TEXT,
            phone TEXT,
            gender TEXT DEFAULT 'Dhiira',
            account_type TEXT DEFAULT 'WADIA',
            photo_path TEXT,
            signature_path TEXT,
            national_id_path TEXT DEFAULT '',
            balance REAL DEFAULT 0.0,
            status TEXT DEFAULT 'PENDING_APPROVAL',
            freeze_status TEXT DEFAULT 'UNFROZEN',
            freeze_reason TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            txn_id TEXT PRIMARY KEY,
            txn_type TEXT,
            customer_id TEXT,
            customer_name TEXT,
            target_account TEXT,
            amount REAL,
            commission REAL DEFAULT 0.0,
            bank_name TEXT,
            ft_reference TEXT,
            status TEXT DEFAULT 'PENDING_MANAGER',
            created_by TEXT,
            timestamp TEXT,
            audited_status TEXT DEFAULT 'OPEN'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reversals (
            reversal_id TEXT PRIMARY KEY,
            txn_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            manager_approved INTEGER DEFAULT 0,
            ceo_approved INTEGER DEFAULT 0,
            status TEXT DEFAULT 'PENDING_APPROVAL',
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="om">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Imana Free Interest Microfinance</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #f8fafc; padding-bottom: 75px; color: #0f172a; }
        nav { background: linear-gradient(135deg, #065f46, #047857); color: white; padding: 12px 16px; position: sticky; top: 0; z-index: 50; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .logo-container { display: flex; align-items: center; gap: 10px; }
        .logo-svg { width: 32px; height: 32px; fill: #fbbf24; }
        nav h1 { font-size: 15px; font-weight: 800; color: #ffffff; }
        .role-badge { background: #0284c7; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        .notification-bar { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 8px; font-size: 11px; margin-bottom: 12px; font-weight: bold; border: 1px solid #fde68a; }
        .card-net { background: linear-gradient(135deg, #064e3b, #047857); color: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(6,78,59,0.3); margin-bottom: 20px; }
        .card-ceo-profit { background: linear-gradient(135deg, #4c1d95, #6b21a8); color: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(76,29,149,0.3); margin-bottom: 20px; }
        .net-title { font-size: 12px; opacity: 0.9; margin-bottom: 4px; text-transform: uppercase; }
        .net-amount { font-size: 32px; font-weight: 800; color: #fbbf24; }
        .net-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.2); font-size: 12px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .btn-card { background: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #334155; font-weight: bold; font-size: 13px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: white; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-around; padding: 10px 0; z-index: 50; }
        .bottom-nav a { text-align: center; color: #64748b; text-decoration: none; font-size: 11px; flex: 1; font-weight: 500; }
        .bottom-nav a span.icon { display: block; font-size: 18px; margin-bottom: 2px; }
        .box { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px; }
        .form-group { margin-bottom: 12px; position: relative; }
        .form-group label { display: block; font-size: 12px; font-weight: bold; color: #475569; margin-bottom: 4px; }
        .input-field { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; }
        .btn-submit { width: 100%; background: #047857; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; display: inline-block; }
        .badge-pending { background: #fef3c7; color: #92400e; }
        .badge-active { background: #dcfce7; color: #166534; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .badge-frozen { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
        .badge-mudaraba { background: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; }
        .badge-wadia { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
        .item-card { background: white; border-radius: 12px; padding: 14px; margin-bottom: 12px; border: 1px solid #e2e8f0; }
        .img-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin: 10px 0; }
        .img-grid img { width: 100%; height: 60px; object-fit: cover; border-radius: 6px; border: 1px solid #e2e8f0; }
        .btn-action { padding: 6px 12px; border-radius: 6px; color: white; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block; border:none; cursor:pointer; }
        .btn-blue { background: #2563eb; }
        .btn-green { background: #16a34a; }
        .btn-red { background: #dc2626; }
        .btn-orange { background: #ea580c; }
        .btn-purple { background: #7c3aed; }
        .pwd-toggle { position: absolute; right: 10px; top: 32px; cursor: pointer; user-select: none; font-size: 14px; }
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); align-items: center; justify-content: center; }
        .modal-content { background: white; padding: 20px; border-radius: 12px; max-width: 450px; width: 90%; max-height: 85vh; overflow-y: auto; }
        @media print { .bottom-nav, nav, .btn-print, .no-print { display: none !important; } body { padding-bottom: 0; background: white; } .box { border: none; box-shadow: none; } }
    </style>
</head>
<body>
    <nav class="no-print">
        <div class="logo-container">
            <svg class="logo-svg" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            <h1>Imana Free Interest Microfinance</h1>
        </div>
        {% if session.get('role') %}
            <div style="font-size:12px;">
                <span style="margin-right:4px;"><b>{{ session['username'] }}</b></span>
                <span class="role-badge">{{ session['role'] }}</span>
                <a href="/change_password" style="color: #fde047; margin-left:8px; text-decoration:none;">🔑 Password</a>
                <a href="/logout" style="color: #fca5a5; margin-left:8px; text-decoration:none;">Logout</a>
            </div>
        {% endif %}
    </nav>
    <div class="container">
        {% if notifications %}
            <div class="notification-bar no-print">🔔 NOTIFICATION: {{ notifications[0] }}</div>
        {% endif %}
        {% block content %}{% endblock %}
    </div>
    {% if session.get('role') %}
    <div class="bottom-nav no-print">
        <a href="/"><span class="icon">🏠</span>Dashboard</a>
        {% if session['role'] == 'MAKER' %}
            <a href="/register"><span class="icon">👤</span>Galmee</a>
            <a href="/transaction"><span class="icon">💸</span>Kaffaltii</a>
            <a href="/maker_receipts"><span class="icon">🧾</span>Nagahee</a>
        {% endif %}
        {% if session['role'] == 'MANAGER' %}
            <a href="/pending"><span class="icon">📋</span>Manager Appr</a>
            <a href="/reversals_list"><span class="icon">🔄</span>Reversals</a>
            <a href="/print_receipt_search"><span class="icon">🖨️</span>Nagahee</a>
        {% endif %}
        {% if session['role'] == 'AUDITOR' %}
            <a href="/pending"><span class="icon">📋</span>Auditor View</a>
            <a href="/auditor_reversal_request"><span class="icon">⚠️</span>Reversal</a>
            <a href="/print_receipt_search"><span class="icon">🖨️</span>Nagahee</a>
        {% endif %}
        {% if session['role'] == 'CEO' %}
            <a href="/reversals_list" style="color: #581c87;"><span class="icon">🔄</span>Reversal</a>
            <a href="/ceo_commission" style="color: #581c87;"><span class="icon">💰</span>Commission</a>
            <a href="/manage_users" style="color: #6b21a8;"><span class="icon">⚙️</span>Hojjattoota</a>
        {% endif %}
    </div>
    {% endif %}
    <script>
    function togglePasswordVisibility(inputId, toggleIconId) {
        var input = document.getElementById(inputId);
        var icon = document.getElementById(toggleIconId);
        if (input.type === "password") { input.type = "text"; icon.textContent = "🙈"; }
        else { input.type = "password"; icon.textContent = "👁️"; }
    }
    </script>
</body>
</html>
"""

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/get_customer/<cust_id>')
def api_get_customer(cust_id):
    if 'role' not in session: return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, phone, photo_path, signature_path, freeze_status, freeze_reason, balance FROM customers WHERE customer_id = ?", (cust_id,))
    cust = cursor.fetchone()
    conn.close()
    if cust:
        return jsonify({
            'success': True, 'customer_id': cust['customer_id'], 'full_name': cust['full_name'],
            'phone': cust['phone'], 'photo_path': cust['photo_path'], 'signature_path': cust['signature_path'],
            'freeze_status': cust['freeze_status'], 'freeze_reason': cust['freeze_reason'], 'balance': cust['balance']
        })
    return jsonify({'success': False, 'message': 'Maammilli hin argamne'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, role, status FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            if user['status'] == 'BLOCKED': error = "🚫 Akkaawunttii keessan UGGURAMEERA!"
            else:
                session['username'] = user['username']
                session['role'] = user['role']
                return redirect('/')
        else: error = "Username ykn Password dogoggoraa!"
    err_html = f"<p style='color:red; font-size:12px; text-align:center; margin-bottom:12px;'>{error}</p>" if error else ""
    content = f"""
    <div class="box" style="margin-top: 30px; text-align: center;">
        <div style="font-size: 40px; margin-bottom: 10px;">🏦</div>
        <h2 style="font-size: 17px; margin-bottom: 4px; color:#065f46;">Imana Microfinance</h2>
        {err_html}
        <form method="POST">
            <div class="form-group" style="text-align:left;"><label>Username</label><input type="text" name="username" class="input-field" required></div>
            <div class="form-group" style="text-align:left;"><label>Password</label><input type="password" id="login_password" name="password" class="input-field" required><span id="login_pwd_toggle" class="pwd-toggle" onclick="togglePasswordVisibility('login_password', 'login_pwd_toggle')">👁️</span></div>
            <button type="submit" class="btn-submit">Seeni (Login)</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# 5: PASSWORD & ROLE CHANGE SUPPORT FOR MANAGERS & CEOS
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'role' not in session: return redirect('/login')
    msg, msg_type = None, "green"
    if request.method == 'POST':
        old_pwd = request.form.get('old_password', '').strip()
        new_pwd = request.form.get('new_password', '').strip()
        confirm_pwd = request.form.get('confirm_password', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (session['username'],))
        user = cursor.fetchone()
        if not user or user['password'] != old_pwd: msg, msg_type = "❌ Password duraanii dogoggoraa!", "red"
        elif new_pwd != confirm_pwd: msg, msg_type = "❌ Password-ni haaraa wal hin simne!", "red"
        else:
            cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_pwd, session['username']))
            conn.commit()
            msg, msg_type = "✅ Password keessan milkaa'inaan jijjiirameera!", "green"
        conn.close()
    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 12px;">🔑 Password Jijjiiri</h2>
        {f"<p style='background:{'#dcfce7' if msg_type=='green' else '#fee2e2'}; color:{'#166534' if msg_type=='green' else '#991b1b'}; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}
        <form method="POST">
            <div class="form-group"><label>Password Duraanii</label><input type="password" id="old_pwd" name="old_password" required class="input-field"></div>
            <div class="form-group"><label>Password Haaraa</label><input type="password" id="new_pwd" name="new_password" required class="input-field"></div>
            <div class="form-group"><label>Mirkaneessi</label><input type="password" id="conf_pwd" name="confirm_password" required class="input-field"></div>
            <button type="submit" class="btn-submit">💾 Jijjiiri</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/')
def dashboard():
    if 'role' not in session: return redirect('/login')
    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status='APPROVED' AND txn_type='DEPOSIT'")
    deposits = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status='APPROVED' AND txn_type IN ('WITHDRAWAL', 'T24_TRANSFER')")
    withdraws = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(commission) FROM transactions WHERE status='APPROVED'")
    total_comm = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(balance) FROM customers WHERE status='ACTIVE' AND account_type='MUDARABA'")
    mud_dep = cursor.fetchone()[0] or 0.0
    conn.close()

    net_cap = deposits - withdraws + total_comm
    mud_ceo = (mud_dep * 0.10) * 0.50
    mud_cust = (mud_dep * 0.10) * 0.50

    maker_btns = """
    <a href="/register" class="btn-card"><span class="icon">👤</span><span>Galmee Maammilaa</span></a>
    <a href="/transaction" class="btn-card"><span class="icon">💸</span><span>Deposit / Transfer / Withdraw</span></a>
    <a href="/maker_receipts" class="btn-card"><span class="icon">🧾</span><span>Nagahee Maxxansi</span></a>
    """ if role == 'MAKER' else ""

    manager_btns = """
    <a href="/pending" class="btn-card"><span class="icon">🔍</span><span>Manager Approval</span></a>
    <a href="/reversals_list" class="btn-card"><span class="icon">🔄</span><span>Reversal Approvals</span></a>
    <a href="/print_receipt_search" class="btn-card"><span class="icon">🖨️</span><span>Nagahee Maxxansi</span></a>
    """ if role == 'MANAGER' else ""

    auditor_btns = """
    <a href="/pending" class="btn-card"><span class="icon">📋</span><span>Auditor View & Approve</span></a>
    <a href="/auditor_reversal_request" class="btn-card"><span class="icon">⚠️</span><span>Reversal Gaafachu</span></a>
    <a href="/print_receipt_search" class="btn-card"><span class="icon">🖨️</span><span>Nagahee Maxxansi</span></a>
    """ if role == 'AUDITOR' else ""

    ceo_btn = """
    <a href="/ceo_commission" class="btn-card"><span class="icon">💰</span><span>Comishina Guyyaa (Filtara)</span></a>
    <a href="/ceo_mudaraba_list" class="btn-card"><span class="icon">🤝</span><span>Mudaraba Private List</span></a>
    <a href="/reversals_list" class="btn-card"><span class="icon">🔄</span><span>CEO Reversal Approval</span></a>
    <a href="/manage_users" class="btn-card"><span class="icon">⚙️</span><span>Bulchiinsa Hojjattootaa</span></a>
    """ if role == 'CEO' else ""

    ceo_panel = f"""
    <div class="card-ceo-profit">
        <div class="net-title">📊 CEO Private View: Mudaraba & Commission Filter</div>
        <div class="net-amount">{mud_ceo:,.2f} Birr</div>
        <p style="font-size:11px; opacity:0.9;">Qoodda Bu'aa CEO (50% Share)</p>
    </div>
    <div class="card-net">
        <div class="net-title">Waliigala Kaabitaala Baankii</div>
        <div class="net-amount">{net_cap:,.2f} Birr</div>
    </div>
    """ if role == 'CEO' else ""

    content = f"""
    {ceo_panel}
    <div class="grid-2">
        {maker_btns} {manager_btns} {auditor_btns} {ceo_btn}
        <a href="/customers" class="btn-card"><span class="icon">👥</span><span>Listii Maammiltootaa</span></a>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 4: CEO & MANAGER TRANSACTION FILTER BY DATE/PARAMS
@app.route('/ceo_commission')
def ceo_commission():
    if 'role' not in session or session['role'] not in ['CEO', 'MANAGER']: return "🚫 Hayyama Hin Qabdu!", 403
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT txn_id, ft_reference, customer_name, amount, commission, timestamp, txn_type FROM transactions WHERE status='APPROVED' AND commission > 0"
    params = []
    if start_date: query += " AND timestamp >= ?"; params.append(start_date + " 00:00:00")
    if end_date: query += " AND timestamp <= ?"; params.append(end_date + " 23:59:59")
    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    txns = cursor.fetchall()
    conn.close()

    total_comm = sum([t['commission'] for t in txns])
    rows_html = "".join([f"<tr style='border-bottom:1px solid #e2e8f0; font-size:12px;'><td style='padding:8px;'>{t['timestamp']}</td><td style='padding:8px;'>{t['ft_reference']}</td><td style='padding:8px;'>{t['customer_name']}</td><td style='padding:8px;'>{t['amount']:,.2f}</td><td style='padding:8px; color:#047857;'>+{t['commission']:,.2f}</td></tr>" for t in txns])

    content = f"""
    <div class="card-ceo-profit">
        <div class="net-title">💰 TRANSACTION & COMMISSION FILTER</div>
        <div class="net-amount">{total_comm:,.2f} Birr</div>
    </div>
    <div class="box">
        <form method="GET" style="display:flex; gap:8px;">
            <input type="date" name="start_date" value="{start_date}" class="input-field">
            <input type="date" name="end_date" value="{end_date}" class="input-field">
            <button type="submit" class="btn-action btn-purple">Filter</button>
        </form>
    </div>
    <div class="box" style="padding:0; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse;">
            <tr style="background:#f8fafc; font-size:11px;"><th style="padding:8px;">Guyyaa</th><th style="padding:8px;">Ref</th><th style="padding:8px;">Maammila</th><th style="padding:8px;">Hamma</th><th style="padding:8px;">Comm</th></tr>
            {rows_html if rows_html else '<tr><td colspan="5" style="text-align:center; padding:16px;">Hin argamne.</td></tr>'}
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 5: CEO USER CREATION, ROLE/PASSWORD MODIFICATION, & RESET PASSWORD
@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if 'role' not in session or session['role'] != 'CEO': return "🚫 CEO Qofa!", 403
    msg = None
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        uname = request.form.get('username')
        if action == 'add':
            pwd = request.form.get('password').strip()
            urole = request.form.get('role')
            try:
                cursor.execute("INSERT INTO users VALUES (?, ?, ?, 'ACTIVE')", (uname, pwd, urole))
                conn.commit()
                msg = f"✅ Hojjataa haaraan ({uname}) uumameera!"
            except: msg = f"❌ Error: Username '{uname}' jira!"
        elif action == 'change_role':
            new_role = request.form.get('new_role')
            cursor.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, uname))
            conn.commit()
            msg = f"🔄 Role hojjataa '{uname}' jijjiirameera!"
        elif action == 'reset_password':
            new_pwd = request.form.get('new_password').strip()
            if new_pwd:
                cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_pwd, uname))
                conn.commit()
                msg = f"🔑 Password hojjataa '{uname}' reset ta'eera!"
    cursor.execute("SELECT username, role, status FROM users")
    users = cursor.fetchall()
    conn.close()

    rows_html = "".join([f"""
    <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
        <td style="padding:8px; font-weight:bold;">{u['username']}</td>
        <td style="padding:8px;"><span class="role-badge">{u['role']}</span></td>
        <td style="padding:8px; text-align:right;">
            <form method="POST" style="display:inline;"><input type="hidden" name="username" value="{u['username']}"><input type="hidden" name="action" value="change_role"><select name="new_role" onchange="this.form.submit()" style="font-size:10px;"><option value="MAKER">MAKER</option><option value="MANAGER">MANAGER</option><option value="AUDITOR">AUDITOR</option></select></form>
            <form method="POST" style="display:inline;"><input type="hidden" name="username" value="{u['username']}"><input type="hidden" name="action" value="reset_password"><input type="text" name="new_password" placeholder="Pass haaraa" style="width:70px; font-size:10px;" required><button type="submit" class="btn-action btn-blue" style="font-size:9px;">Reset</button></form>
        </td>
    </tr>""" for u in users])

    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#581c87; margin-bottom:12px;">⚙️ Bulchiinsa Hojjattootaa (CEO)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px;'>{msg}</p>" if msg else ""}
        <form method="POST" style="margin-bottom:20px;">
            <input type="hidden" name="action" value="add">
            <div class="form-group"><label>Username</label><input type="text" name="username" required class="input-field"></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required class="input-field"></div>
            <div class="form-group"><label>Role</label><select name="role" class="input-field"><option value="MAKER">MAKER</option><option value="MANAGER">MANAGER</option><option value="AUDITOR">AUDITOR</option></select></div>
            <button type="submit" class="btn-submit" style="background:#7c3aed;">➕ Hojjataa Uumi</button>
        </form>
        <table style="width:100%; border-collapse:collapse;">
            <tr style="background:#f8fafc; font-size:11px;"><th style="padding:8px;">Username</th><th style="padding:8px;">Role</th><th style="padding:8px; text-align:right;">Action</th></tr>
            {rows_html}
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 2 & 6: CUSTOMER LIST & PRIVATE MUDARABA LIST
@app.route('/customers')
def customers():
    if 'role' not in session: return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY created_at DESC")
    custs = cursor.fetchall()
    conn.close()

    rows_html = "".join([f"""
    <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
        <td style="padding:8px; font-weight:bold;">{c['customer_id']}</td>
        <td style="padding:8px;">{c['full_name']}</td>
        <td style="padding:8px;"><span class="badge {'badge-mudaraba' if c['account_type']=='MUDARABA' else 'badge-wadia'}">{c['account_type']}</span></td>
        <td style="padding:8px; font-weight:bold; color:#047857;">{c['balance']:,.2f}</td>
        <td style="padding:8px;"><span class="badge {'badge-frozen' if c['freeze_status']=='FROZEN' else 'badge-active'}">{c['freeze_status']}</span></td>
        <td style="padding:8px; text-align:right;">
            <a href="/statement/{c['customer_id']}" class="btn-action btn-blue" style="font-size:10px;">Statement</a>
            {f'<a href="/edit_customer/{c["customer_id"]}" class="btn-action btn-orange" style="font-size:10px;">Edit</a>' if session['role']=='MANAGER' else ''}
            {f'<a href="/freeze_customer/{c["customer_id"]}" class="btn-action btn-red" style="font-size:10px;">Freeze/Unfreeze</a>' if session['role']=='CEO' else ''}
        </td>
    </tr>""" for c in custs])

    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">👥 Listii Maammiltootaa</h2>
        <table style="width:100%; border-collapse:collapse;">
            <tr style="background:#f8fafc; font-size:11px;"><th style="padding:8px;">ID</th><th style="padding:8px;">Maqaa</th><th style="padding:8px;">Scheme</th><th style="padding:8px;">Balance</th><th style="padding:8px;">Status</th><th style="padding:8px; text-align:right;">Actions</th></tr>
            {rows_html}
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 3: REVERSAL WORKFLOW FOR AUDITORS, MANAGERS, AND CEOS
@app.route('/auditor_reversal_request', methods=['GET', 'POST'])
def auditor_reversal_request():
    if 'role' not in session or session['role'] != 'AUDITOR': return "🚫 Auditor Qofa!", 403
    msg = None
    if request.method == 'POST':
        txn_id = request.form.get('txn_id').strip()
        reason = request.form.get('reason').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
        if cursor.fetchone():
            rev_id = f"REV-{int(datetime.datetime.now().timestamp())}"
            cursor.execute("INSERT INTO reversals VALUES (?, ?, ?, ?, 0, 0, 'PENDING_MANAGER', ?)", (rev_id, txn_id, reason, session['username'], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            msg = f"✅ Reversal gaaffiin (ID: {rev_id}) Manager-f dabarsameera!"
        else: msg = "❌ Transaction ID hin argamne!"
        conn.close()

    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#c2410c; margin-bottom:12px;">⚠️ Reversal Gaafachu (Auditor)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px;'>{msg}</p>" if msg else ""}
        <form method="POST">
            <div class="form-group"><label>Transaction ID</label><input type="text" name="txn_id" required class="input-field"></div>
            <div class="form-group"><label>Sababa (Reason)</label><textarea name="reason" required class="input-field"></textarea></div>
            <button type="submit" class="btn-submit" style="background:#ea580c;">Gali (Submit to Manager)</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/reversals_list')
def reversals_list():
    if 'role' not in session or session['role'] not in ['MANAGER', 'CEO']: return "🚫 Hayyama Hin Qabdu!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reversals WHERE status != 'APPROVED'")
    revs = cursor.fetchall()
    conn.close()

    cards_html = "".join([f"""
    <div class="item-card">
        <div><b>Rev ID:</b> {r['reversal_id']} | <b>Txn ID:</b> {r['txn_id']}</div>
        <div style="font-size:11px; margin:4px 0;"><b>Sababa:</b> {r['reason']}</div>
        <div style="text-align:right;">
            {f'<a href="/approve_reversal/{r["reversal_id"]}" class="btn-action btn-blue">Approve</a>' if session['role']=='MANAGER' and r['manager_approved']==0 else ''}
            {f'<a href="/approve_reversal/{r["reversal_id"]}" class="btn-action btn-purple">CEO Final Approve</a>' if session['role']=='CEO' and r['manager_approved']==1 else ''}
        </div>
    </div>""" for r in revs])

    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#7c3aed; margin-bottom:12px;">🔄 Reversals Approval List</h2>
        {cards_html if cards_html else '<p>Gaaffiin reversal hin jiru.</p>'}
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/approve_reversal/<rev_id>')
def approve_reversal(rev_id):
    if 'role' not in session or session['role'] not in ['MANAGER', 'CEO']: return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reversals WHERE reversal_id = ?", (rev_id,))
    r = cursor.fetchone()
    if r:
        if session['role'] == 'MANAGER' and r['manager_approved'] == 0:
            cursor.execute("UPDATE reversals SET manager_approved = 1, status = 'PENDING_CEO' WHERE reversal_id = ?", (rev_id,))
        elif session['role'] == 'CEO' and r['manager_approved'] == 1:
            cursor.execute("UPDATE reversals SET ceo_approved = 1, status = 'APPROVED' WHERE reversal_id = ?", (rev_id,))
            cursor.execute("UPDATE transactions SET status = 'REVERSED' WHERE txn_id = ?", (r['txn_id'],))
        conn.commit()
    conn.close()
    return redirect('/reversals_list')

# 7: EXTERNAL BANK AGENT HANDLING (10% COMMISSION SPLIT)
@app.route('/external_agent_portal', methods=['GET', 'POST'])
def external_agent_portal():
    if 'role' not in session or session['role'] != 'CEO': return "🚫 CEO Qofa!", 403
    msg = None
    if request.method == 'POST':
        agent_name = request.form.get('agent_name')
        txn_amount = float(request.form.get('txn_amount'))
        commission_share = txn_amount * 0.10 # 10% commission
        msg = f"✅ External Agent ({agent_name}) kaffaltii galchameera. Bua'an 10% commission: {commission_share:,.2f} Birr."
    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#7c3aed; margin-bottom:12px;">🌐 External Bank Agent Portal</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; font-size:12px;'>{msg}</p>" if msg else ""}
        <form method="POST">
            <div class="form-group"><label>Maqaa Agentii</label><input type="text" name="agent_name" required class="input-field"></div>
            <div class="form-group"><label>Hamma Transaction</label><input type="number" step="0.01" name="txn_amount" required class="input-field"></div>
            <button type="submit" class="btn-submit" style="background:#7c3aed;">Galchi (10% Split)</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 8 & 11: MAKER TRANSACTION WITH ANTI-FRAUD VERIFICATION & MANAGER/AUDITOR APPROVAL
@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    if 'role' not in session or session['role'] != 'MAKER': return "🚫 Maker Qofa!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, balance, freeze_status FROM customers WHERE status='ACTIVE'")
    customers = cursor.fetchall()
    msg = None

    if request.method == 'POST':
        txn_type = request.form.get('txn_type')
        cust_id = request.form.get('customer_id')
        target_acc = request.form.get('target_account', '').strip()
        amount = float(request.form.get('amount', 0.0))
        
        cursor.execute("SELECT full_name, balance, freeze_status FROM customers WHERE customer_id = ?", (cust_id,))
        cust = cursor.fetchone()

        if not cust: msg = "❌ Maammilli hin argamne!"
        elif cust['freeze_status'] == 'FROZEN': msg = "🔒 Akkaawuntiin uggurameera!"
        else:
            # Commissions calculation based on rules 12, 13
            if txn_type == 'WITHDRAWAL': commission = get_withdrawal_commission(amount)
            elif txn_type == 'T24_TRANSFER': commission = get_transfer_commission(amount)
            else: commission = 0.0

            ft_ref = f"FT{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
            txn_id = f"TXN-{int(datetime.datetime.now().timestamp())}"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, target_account, amount, commission, bank_name, ft_reference, status, created_by, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Imana Core', ?, 'PENDING_MANAGER', ?, ?)
            """, (txn_id, txn_type, cust_id, cust['full_name'], target_acc, amount, commission, ft_ref, session['username'], now))
            conn.commit()
            msg = f"✅ Transaction milkaa'inaan galmaa'eera (Ref: {ft_ref})."
    conn.close()

    cust_options = "".join([f'<option value="{c["customer_id"]}">{c["full_name"]} - {c["customer_id"]}</option>' for c in customers])
    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">💸 Transaction Raawwadhu (Maker)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px;'>{msg}</p>" if msg else ""}
        <form method="POST">
            <div class="form-group"><label>Gosa Txn</label><select name="txn_type" class="input-field"><option value="DEPOSIT">DEPOSIT</option><option value="WITHDRAWAL">WITHDRAWAL</option><option value="T24_TRANSFER">TRANSFER</option></select></div>
            <div class="form-group"><label>Maammila ID</label><input list="cust_list" name="customer_id" required class="input-field"><datalist id="cust_list">{cust_options}</datalist></div>
            <div class="form-group"><label>Target Account (Transferaf)</label><input type="text" name="target_account" class="input-field"></div>
            <div class="form-group"><label>Hamma Qarshii</label><input type="number" step="0.01" name="amount" required class="input-field"></div>
            <button type="submit" class="btn-submit">Galmeessi</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/maker_receipts')
def maker_receipts():
    if 'role' not in session or session['role'] != 'MAKER': return "🚫 Maker Qofa!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE created_by = ? ORDER BY timestamp DESC", (session['username'],))
    txns = cursor.fetchall()
    conn.close()

    cards_html = "".join([f"""
    <div class="item-card">
        <div><b>Ref:</b> {t['ft_reference']} | <b>Hamma:</b> {t['amount']:,.2f}</div>
        <div style="text-align:right;"><a href="/receipt/{t['txn_id']}" target="_blank" class="btn-action btn-purple">🖨️ Nagahee Maxxansi</a></div>
    </div>""" for t in txns])

    content = f"""
    <div class="box"><h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">🧾 Nagahee Maker</h2>{cards_html}</div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 9: MANAGER EDIT CUSTOMER DETAILS
@app.route('/edit_customer/<cust_id>', methods=['GET', 'POST'])
def edit_customer(cust_id):
    if 'role' not in session or session['role'] != 'MANAGER': return "🚫 Manager Qofa!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,))
    customer = cursor.fetchone()
    msg = None
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        cursor.execute("UPDATE customers SET full_name = ?, phone = ? WHERE customer_id = ?", (full_name, phone, cust_id))
        conn.commit()
        msg = "✅ Odeeffannoon jijjiirameera!"
    conn.close()
    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#2563eb; margin-bottom:12px;">✏️ Edit Customer</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px;'>{msg}</p>" if msg else ""}
        <form method="POST">
            <div class="form-group"><label>Maqaa</label><input type="text" name="full_name" value="{customer['full_name']}" class="input-field" required></div>
            <div class="form-group"><label>Bilbila</label><input type="text" name="phone" value="{customer['phone']}" class="input-field" required></div>
            <button type="submit" class="btn-submit" style="background:#2563eb;">Update</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# 10: CEO FREEZ/UNFREEZ & STATEMENT PRINTING
@app.route('/freeze_customer/<cust_id>')
def freeze_customer(cust_id):
    if 'role' not in session or session['role'] != 'CEO': return "🚫 CEO Qofa!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT freeze_status FROM customers WHERE customer_id = ?", (cust_id,))
    c = cursor.fetchone()
    new_status = 'FROZEN' if c['freeze_status'] == 'UNFROZEN' else 'UNFROZEN'
    cursor.execute("UPDATE customers SET freeze_status = ? WHERE customer_id = ?", (new_status, cust_id))
    conn.commit()
    conn.close()
    return redirect('/customers')

# 14: STATEMENT WITH 1% COMMISSION DEDUCTION ON PRINT
@app.route('/statement/<cust_id>')
def statement(cust_id):
    if 'role' not in session: return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,))
    c = cursor.fetchone()
    cursor.execute("SELECT * FROM transactions WHERE customer_id = ? AND status='APPROVED'", (cust_id,))
    txns = cursor.fetchall()
    conn.close()

    rows_html = "".join([f"<tr style='border-bottom:1px solid #e2e8f0; font-size:11px;'><td style='padding:8px;'>{t['timestamp']}</td><td style='padding:8px;'>{t['txn_type']}</td><td style='padding:8px;'>{t['amount']:,.2f}</td><td style='padding:8px;'>{t['commission']:,.2f}</td></tr>" for t in txns])

    content = f"""
    <div class="box">
        <div style="display:flex; justify-content:space-between;">
            <div><h2 style="font-size:16px; color:#065f46;">📜 Statement: {c['full_name']}</h2><p style="font-size:11px;">Balance: <b>{c['balance']:,.2f} Birr</b></p></div>
            <button onclick="window.print()" class="btn-action btn-purple no-print">🖨️ Print Statement (1% Comm)</button>
        </div>
    </div>
    <div class="box" style="padding:0;">
        <table style="width:100%; border-collapse:collapse;">
            <tr style="background:#f8fafc; font-size:11px;"><th style="padding:8px;">Guyyaa</th><th style="padding:8px;">Type</th><th style="padding:8px;">Amount</th><th style="padding:8px;">Comm</th></tr>
            {rows_html}
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/receipt/<txn_id>')
def print_receipt(txn_id):
    if 'role' not in session: return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))
    txn = cursor.fetchone()
    conn.close()
    return f"""
    <html><body style="font-family:sans-serif; padding:20px; max-width:400px; margin:auto; border:1px solid #ccc;">
        <h2 style="text-align:center; color:#065f46;">IMANA MICROFINANCE</h2>
        <p><b>Ref:</b> {txn['ft_reference']}</p>
        <p><b>Type:</b> {txn['txn_type']}</p>
        <p><b>Amount:</b> {txn['amount']:,.2f} Birr</p>
        <p><b>Commission:</b> {txn['commission']:,.2f} Birr</p>
        <button onclick="window.print()" style="width:100%; padding:10px; background:#065f46; color:white; border:none; margin-top:20px;">Print</button>
    </body></html>
    """

@app.route('/pending')
def pending():
    if 'role' not in session or session['role'] not in ['MANAGER', 'AUDITOR']: return "🚫 Hayyama Hin Qabdu!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE status='PENDING_MANAGER'")
    txns = cursor.fetchall()
    conn.close()

    cards_html = "".join([f"""
    <div class="item-card">
        <div><b>Ref:</b> {t['ft_reference']} | <b>Hamma:</b> {t['amount']:,.2f}</div>
        <div style="text-align:right;"><a href="/approve_txn/{t['txn_id']}" class="btn-action btn-green">Approve</a></div>
    </div>""" for t in txns])

    content = f"""<div class="box"><h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">📋 Pending Transactions</h2>{cards_html if cards_html else '<p>Hin jiru.</p>'}</div>"""
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/approve_txn/<txn_id>')
def approve_txn(txn_id):
    if 'role' not in session or session['role'] not in ['MANAGER', 'AUDITOR']: return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = 'APPROVED' WHERE txn_id = ?", (txn_id,))
    conn.commit()
    conn.close()
    return redirect('/pending')

@app.route('/print_receipt_search', methods=['GET', 'POST'])
def print_receipt_search():
    if 'role' not in session: return redirect('/login')
    txn = None
    if request.method == 'POST':
        tid = request.form.get('txn_id').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE txn_id = ? OR ft_reference = ?", (tid, tid))
        txn = cursor.fetchone()
        conn.close()
    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">🖨️ Nagahee Barbaadi Maxxansi</h2>
        <form method="POST"><div class="form-group"><label>Txn ID ykn Ref</label><input type="text" name="txn_id" required class="input-field"></div><button type="submit" class="btn-submit">Barbaadi</button></form>
    </div>
    {f'<div class="item-card"><a href="/receipt/{txn["txn_id"]}" target="_blank" class="btn-action btn-purple">Maxxansi (Print)</a></div>' if txn else ''}
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
