import os
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import random
import sys
import time
import secrets
import json
import threading
from decimal import Decimal
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash

# PIL (Pillow) exception handling for Render deployment stability
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from flask import Flask, request, redirect, url_for, session, render_template_string, send_from_directory, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
if not os.environ.get('SECRET_KEY'):
    print("⚠️ SECRET_KEY env variable hin argamne — yeroo ammaa random tokko fayyadamnee jirra. "
          "Render (ykn deploy) irratti SECRET_KEY dabaluun barbaachisaadha, yoo hin dabalamin "
          "restart hunda booda session/login jiraan hundi cabu (logout godhu).")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

NOTIFICATIONS = []

# --- NEON.TECH / POSTGRESQL DATABASE CONNECTION ---
DEFAULT_DB_URL = 'postgresql://neondb_owner:PAASWORDII_SIRRII_KANAAN_BAKKA_BUUSAA@ep-cool-sample-a5xyz.us-east-2.aws.neon.tech/neondb?sslmode=require'
DATABASE_URL = os.environ.get('DATABASE_URL', DEFAULT_DB_URL)

def get_db_connection(max_retries=5, delay=0.5):
    """Establishes connection to Neon.tech PostgreSQL database with retry logic"""
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e

def compress_and_save_image(file_storage, target_filename, max_size=(500, 500), quality=50):
    """Compresses uploaded images aggressively for ultra-fast performance on 2G/3G/4G networks"""
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_commission(amount):
    if 1000 <= amount < 3000:
        return 50.0
    elif 3000 <= amount < 5000:
        return 100.0
    elif 7000 <= amount < 10000:
        return 200.0
    elif 10000 <= amount <= 20000:
        return 400.0
    return 0.0

def send_sms_alert(phone_number, message):
    print(f"📱 [SMS SENT TO {phone_number}]: {message}")

def add_notification(message):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    NOTIFICATIONS.insert(0, f"[{now}] {message}")
    if len(NOTIFICATIONS) > 20:
        NOTIFICATIONS.pop()

# --- POSTGRESQL NEON DATABASE SETUP & MIGRATION ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(100) PRIMARY KEY,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'ACTIVE'
        );
    """)

    cursor.execute("SELECT COUNT(*) AS cnt FROM users;")
    row = cursor.fetchone()
    if row['cnt'] == 0:
        default_users = [
            ('ceo', 'ceo999', 'CEO', 'ACTIVE'),
            ('manager1', 'manager123', 'MANAGER', 'ACTIVE'),
            ('maker1', 'maker123', 'MAKER', 'ACTIVE'),
            ('auditor1', 'auditor123', 'AUDITOR', 'ACTIVE'),
            ('officer1', 'officer123', 'LOAN_OFFICER', 'ACTIVE')
        ]
        for u in default_users:
            username, plain_pw, role, status = u
            cursor.execute("INSERT INTO users (username, password, role, status) VALUES (%s, %s, %s, %s);",
                           (username, generate_password_hash(plain_pw), role, status))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id VARCHAR(100) PRIMARY KEY,
            full_name VARCHAR(255),
            phone VARCHAR(100),
            gender VARCHAR(50) DEFAULT 'Dhiira',
            account_type VARCHAR(50) DEFAULT 'WADIA',
            photo_path TEXT,
            signature_path TEXT,
            national_id_path TEXT DEFAULT '',
            balance NUMERIC DEFAULT 0.0,
            status VARCHAR(50) DEFAULT 'PENDING_APPROVAL',
            freeze_status VARCHAR(50) DEFAULT 'UNFROZEN',
            freeze_reason TEXT DEFAULT '',
            created_at VARCHAR(100)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            txn_id VARCHAR(100) PRIMARY KEY,
            txn_type VARCHAR(50),
            customer_id VARCHAR(100),
            customer_name VARCHAR(255),
            target_account VARCHAR(100),
            amount NUMERIC,
            commission NUMERIC DEFAULT 0.0,
            bank_name VARCHAR(255),
            ft_reference VARCHAR(100),
            status VARCHAR(50) DEFAULT 'PENDING_MANAGER',
            created_by VARCHAR(100),
            timestamp VARCHAR(100),
            audited_status VARCHAR(50) DEFAULT 'OPEN'
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reversals (
            reversal_id VARCHAR(100) PRIMARY KEY,
            txn_id VARCHAR(100) NOT NULL,
            reason TEXT NOT NULL,
            requested_by VARCHAR(100) NOT NULL,
            manager_approved INT DEFAULT 0,
            ceo_approved INT DEFAULT 0,
            status VARCHAR(50) DEFAULT 'PENDING_APPROVAL',
            timestamp VARCHAR(100)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS islamic_financing (
            loan_id VARCHAR(100) PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL,
            customer_name VARCHAR(255),
            financing_type VARCHAR(50) NOT NULL,
            principal_amount NUMERIC NOT NULL,
            profit_margin NUMERIC DEFAULT 0.0,
            total_repayment NUMERIC NOT NULL,
            tenure_months INT,
            monthly_installment NUMERIC,
            status VARCHAR(50) DEFAULT 'PENDING_MANAGER',
            manager_approved INT DEFAULT 0,
            ceo_approved INT DEFAULT 0,
            agent_notes TEXT,
            created_by VARCHAR(100),
            timestamp VARCHAR(100)
        );
    """)

    # --- MIGRATION: customer self-service app support (PIN login + tokens) ---
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS pin VARCHAR(255);")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_sessions (
            token VARCHAR(100) PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL,
            created_at VARCHAR(100)
        );
    """)

    # --- MIGRATION: auto-backup / auto-restore support (CEO controlled) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            backup_id VARCHAR(100) PRIMARY KEY,
            created_by VARCHAR(100),
            created_at VARCHAR(100),
            data TEXT NOT NULL,
            size_bytes INTEGER DEFAULT 0
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()

init_db()

# Optional safety cap for the customer self-service app (no manager approval path).
CUSTOMER_TXN_AUTO_LIMIT = float(os.environ.get('CUSTOMER_TXN_AUTO_LIMIT', 0))

BACKUP_TABLES = ['users', 'customers', 'transactions', 'reversals', 'islamic_financing']

def _json_default(o):
    if isinstance(o, Decimal):
        return float(o)
    return str(o)

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = %s;", (key,))
    row = cursor.fetchone()
    cursor.close(); conn.close()
    return row['setting_value'] if row else default

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)
        ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value;
    """, (key, value))
    conn.commit()
    cursor.close(); conn.close()

def create_backup(triggered_by):
    """Dumps all core banking tables into one JSON snapshot row in the `backups` table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    dump = {}
    for t in BACKUP_TABLES:
        cursor.execute(f"SELECT * FROM {t};")
        dump[t] = [dict(r) for r in cursor.fetchall()]

    payload = json.dumps(dump, default=_json_default)
    backup_id = f"BKP-{int(datetime.datetime.now().timestamp())}"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO backups (backup_id, created_by, created_at, data, size_bytes)
        VALUES (%s, %s, %s, %s, %s);
    """, (backup_id, triggered_by, now, payload, len(payload)))
    conn.commit()

    keep = int(get_setting('backup_retention_count', '30') or 30)
    cursor.execute("SELECT backup_id FROM backups ORDER BY created_at ASC;")
    all_ids = [r['backup_id'] for r in cursor.fetchall()]
    if len(all_ids) > keep:
        to_delete = all_ids[:len(all_ids) - keep]
        cursor.execute("DELETE FROM backups WHERE backup_id = ANY(%s);", (to_delete,))
        conn.commit()

    cursor.close(); conn.close()
    add_notification(f"💾 Backup {backup_id} ({triggered_by}) uumameera.")
    return backup_id

def restore_backup(backup_id, restored_by):
    """Restores all core tables from a stored snapshot."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM backups WHERE backup_id = %s;", (backup_id,))
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if not row:
        return False, "❌ Backup-iin kun hin argamne."

    dump = json.loads(row['data'])

    create_backup(f"AUTO_PRE_RESTORE_by_{restored_by}")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for t in BACKUP_TABLES:
            rows = dump.get(t, [])
            cursor.execute(f"DELETE FROM {t};")
            if rows:
                cols = list(rows[0].keys())
                col_names = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                insert_sql = f"INSERT INTO {t} ({col_names}) VALUES ({placeholders});"
                for r in rows:
                    cursor.execute(insert_sql, tuple(r[c] for c in cols))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close(); conn.close()
        return False, f"❌ Restore dogongora: {e}"

    cursor.close(); conn.close()
    add_notification(f"♻️ Backup {backup_id} deebi'ee bu'uureffameera ({restored_by}).")
    return True, "✅ Deebi'ee bu'uureffamuun (restore) milkaa'eera!"

def _autobackup_loop():
    """Background loop for periodic automatic backups."""
    time.sleep(30)
    while True:
        try:
            enabled = (get_setting('autobackup_enabled', 'true') or 'true').lower() == 'true'
            if enabled:
                interval_hours = float(get_setting('autobackup_interval_hours', '24') or 24)
                last_at = get_setting('last_auto_backup_at')
                due = True
                if last_at:
                    try:
                        last_dt = datetime.datetime.strptime(last_at, "%Y-%m-%d %H:%M:%S")
                        due = (datetime.datetime.now() - last_dt).total_seconds() >= interval_hours * 3600
                    except Exception:
                        due = True
                if due:
                    create_backup('AUTO')
                    set_setting('last_auto_backup_at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print(f"⚠️ Autobackup loop error: {e}")
        time.sleep(1800)

_autobackup_thread = threading.Thread(target=_autobackup_loop, daemon=True)
_autobackup_thread.start()

def get_customer_by_token(token):
    """Looks up the customer tied to a mobile-app bearer token."""
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id FROM customer_sessions WHERE token = %s;", (token,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return None
    cursor.execute("SELECT * FROM customers WHERE customer_id = %s;", (row['customer_id'],))
    cust = cursor.fetchone()
    cursor.close()
    conn.close()
    return cust

def get_bearer_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth.split(' ', 1)[1].strip()
    data = request.get_json(silent=True) or {}
    return data.get('token') or request.form.get('token') or request.args.get('token')

def get_bank_capital():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(amount) AS val FROM transactions WHERE status='APPROVED' AND txn_type='DEPOSIT';")
    res = cursor.fetchone()
    total_deposit = float(res['val']) if res and res['val'] is not None else 0.0
    
    cursor.execute("SELECT SUM(amount) AS val FROM transactions WHERE status='APPROVED' AND txn_type IN ('WITHDRAWAL', 'T24_TRANSFER');")
    res = cursor.fetchone()
    total_withdraw = float(res['val']) if res and res['val'] is not None else 0.0
    
    cursor.execute("SELECT SUM(balance) AS val FROM customers WHERE status='ACTIVE';")
    res = cursor.fetchone()
    total_cust_balance = float(res['val']) if res and res['val'] is not None else 0.0

    cursor.execute("SELECT SUM(commission) AS val FROM transactions WHERE status='APPROVED';")
    res = cursor.fetchone()
    total_commission = float(res['val']) if res and res['val'] is not None else 0.0

    cursor.execute("SELECT SUM(balance) AS val FROM customers WHERE status='ACTIVE' AND account_type='MUDARABA';")
    res = cursor.fetchone()
    total_mudaraba_deposits = float(res['val']) if res and res['val'] is not None else 0.0

    mudaraba_gross_profit = total_mudaraba_deposits * 0.10
    mudaraba_ceo_share = mudaraba_gross_profit * 0.50
    mudaraba_customer_share = mudaraba_gross_profit * 0.50
    
    net_capital = total_deposit - total_withdraw + total_commission
    cursor.close()
    conn.close()
    return max(0.0, net_capital), total_deposit, total_withdraw, total_cust_balance, total_commission, total_mudaraba_deposits, mudaraba_gross_profit, mudaraba_ceo_share, mudaraba_customer_share

# --- API FOR MAKER ACCOUNT VERIFICATION ---
@app.route('/api/verify_account/<cust_id>')
def api_verify_account(cust_id):
    if 'role' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, freeze_status, status, balance FROM customers WHERE customer_id = %s;", (cust_id,))
    cust = cursor.fetchone()
    cursor.close()
    conn.close()

    if cust:
        if cust['freeze_status'] == 'FROZEN':
            return jsonify({"success": False, "message": f"🔒 Account ID: {cust_id} ({cust['full_name']}) UGGURAMEERA!"})
        return jsonify({"success": True, "full_name": cust['full_name'], "status": cust['status'], "balance": float(cust['balance'])})
    return jsonify({"success": False, "message": "❌ Account ID kanaa hin argamne!"})

# --- UI TEMPLATE ---
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
        nav h1 { font-size: 15px; font-weight: 800; letter-spacing: 0.3px; color: #ffffff; }
        .role-badge { background: #0284c7; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        
        .notification-bar { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 8px; font-size: 11px; margin-bottom: 12px; font-weight: bold; border: 1px solid #fde68a; }

        .card-net { background: linear-gradient(135deg, #064e3b, #047857); color: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(6,78,59,0.3); margin-bottom: 20px; }
        .card-ceo-profit { background: linear-gradient(135deg, #4c1d95, #6b21a8); color: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(76,29,149,0.3); margin-bottom: 20px; }
        .net-title { font-size: 12px; opacity: 0.9; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
        .net-amount { font-size: 32px; font-weight: 800; color: #fbbf24; }
        .net-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; pt: 12px; border-top: 1px solid rgba(255,255,255,0.2); font-size: 12px; }
        
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .btn-card { background: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #334155; font-weight: bold; font-size: 13px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: 0.2s; }
        .btn-card:active { transform: scale(0.98); }
        .btn-card span.icon { font-size: 24px; margin-bottom: 8px; }
        .btn-card-ceo { background: #faf5ff; border-color: #e9d5ff; color: #581c87; }
        .btn-card-auditor { background: #fff7ed; border-color: #ffedd5; color: #c2410c; }
        .btn-card-loan { background: #f0fdf4; border-color: #bbf7d0; color: #15803d; }
        
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
        .img-grid img { width: 100%; height: 60px; object-fit: cover; border-radius: 6px; border: 1px solid #e2e8f0; loading: lazy; }
        
        .btn-action { padding: 6px 12px; border-radius: 6px; color: white; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block; border:none; cursor:pointer; }
        .btn-blue { background: #2563eb; }
        .btn-green { background: #16a34a; }
        .btn-red { background: #dc2626; }
        .btn-orange { background: #ea580c; }
        .btn-purple { background: #7c3aed; }
        
        .pwd-toggle { position: absolute; right: 10px; top: 32px; cursor: pointer; user-select: none; font-size: 14px; }
        
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); align-items: center; justify-content: center; }
        .modal-content { background: white; padding: 20px; border-radius: 12px; max-width: 450px; width: 90%; max-height: 85vh; overflow-y: auto; }
        
        @media print {
            .bottom-nav, nav, .btn-print, .no-print { display: none !important; }
            body { padding-bottom: 0; background: white; }
            .box { border: none; box-shadow: none; }
        }
    </style>
</head>
<body>
    <nav class="no-print">
        <div class="logo-container">
            <svg class="logo-svg" viewBox="0 0 24 24">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <h1>Imana Free Interest Microfinance</h1>
        </div>
        {% if session.get('role') %}
            <div style="font-size:12px;">
                <span style="margin-right:4px;"><b>{{ session['username'] }}</b></span>
                <span class="role-badge">{{ session['role'] }}</span>
                <a href="/logout" style="color: #fca5a5; margin-left:8px; text-decoration:none;">Logout</a>
            </div>
        {% endif %}
    </nav>

    <div class="container">
        {% if notifications %}
            <div class="notification-bar no-print">
                🔔 NOTIFICATION: {{ notifications[0] }}
            </div>
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
        {% endif %}
        {% if session['role'] == 'AUDITOR' %}
            <a href="/pending"><span class="icon">📋</span>Auditor View</a>
            <a href="/auditor_reversal_request"><span class="icon">⚠️</span>Reversal Gaafachu</a>
        {% endif %}
        {% if session['role'] in ['LOAN_OFFICER', 'CEO', 'MANAGER'] %}
            <a href="/islamic_loan"><span class="icon">📜</span>Liqaa Islaamaa</a>
        {% endif %}
        {% if session['role'] == 'CEO' %}
            <a href="/reversals_list" style="color: #581c87;"><span class="icon">🔄</span>Reversal CEO</a>
            <a href="/ceo_mudaraba_list" style="color: #581c87;"><span class="icon">🤝</span>Mudaraba List</a>
            <a href="/manage_users" style="color: #6b21a8;"><span class="icon">⚙️</span>Hojjattoota</a>
            <a href="/admin/backups" style="color: #6b21a8;"><span class="icon">💾</span>Backup</a>
        {% endif %}
    </div>
    {% endif %}

    <script>
    function togglePasswordVisibility(inputId, toggleIconId) {
        var input = document.getElementById(inputId);
        var icon = document.getElementById(toggleIconId);
        if (input.type === "password") {
            input.type = "text";
            icon.textContent = "🙈";
        } else {
            input.type = "password";
            icon.textContent = "👁️";
        }
    }
    </script>
</body>
</html>
"""

# --- STATIC FILE SERVING ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- ROUTES & VIEWS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, password, role, status FROM users WHERE username = %s;", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        valid = False
        if user:
            stored = user['password'] or ''
            if stored.startswith(('pbkdf2:', 'scrypt:', 'argon2')):
                valid = check_password_hash(stored, password)
            else:
                valid = (stored == password)
                if valid:
                    up_conn = get_db_connection()
                    up_cursor = up_conn.cursor()
                    up_cursor.execute("UPDATE users SET password = %s WHERE username = %s;",
                                      (generate_password_hash(password), username))
                    up_conn.commit()
                    up_cursor.close(); up_conn.close()

        if valid:
            if user['status'] == 'BLOCKED':
                error = "🚫 Akkaawunttii keessan UGGURAMEERA! CEO qunnamaa."
            else:
                session['username'] = user['username']
                session['role'] = user['role']
                return redirect('/')
        else:
            error = "Username ykn Password dogoggoraa!"

    err_html = f"<p style='color:red; font-size:12px; text-align:center; margin-bottom:12px;'>{error}</p>" if error else ""
    content = f"""
    <div class="box" style="margin-top: 30px; text-align: center;">
        <div style="font-size: 40px; margin-bottom: 10px;">🏦</div>
        <h2 style="font-size: 17px; margin-bottom: 4px; color:#065f46;">Imana Free Interest Microfinance</h2>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 16px;">Seensa Systema (Login)</p>
        {err_html}
        <form method="POST">
            <div class="form-group" style="text-align:left;">
                <label>Username</label>
                <input type="text" name="username" placeholder="Fkn: ceo, manager1, maker1" class="input-field" required>
            </div>
            <div class="form-group" style="text-align:left;">
                <label>Password</label>
                <input type="password" id="login_password" name="password" placeholder="Password" class="input-field" required>
                <span id="login_pwd_toggle" class="pwd-toggle" onclick="togglePasswordVisibility('login_password', 'login_pwd_toggle')">👁️</span>
            </div>
            <button type="submit" class="btn-submit">Seeni (Login)</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def dashboard():
    if 'role' not in session:
        return redirect('/login')
    
    net_cap, deposits, withdraws, cust_bal, total_comm, mud_dep, mud_gross, mud_ceo, mud_cust = get_bank_capital()
    role = session['role']

    maker_btns = ""
    if role == 'MAKER':
        maker_btns = """
        <a href="/register" class="btn-card"><span class="icon">👤</span><span>Galmee Maammilaa</span></a>
        <a href="/transaction" class="btn-card"><span class="icon">💸</span><span>Deposit / Transfer / Withdraw</span></a>
        <a href="/maker_receipts" class="btn-card"><span class="icon">🧾</span><span>Nagahee Maxxansi</span></a>
        """

    manager_btns = ""
    if role == 'MANAGER':
        manager_btns = """
        <a href="/pending" class="btn-card"><span class="icon">🔍</span><span>Manager Approval</span></a>
        <a href="/reversals_list" class="btn-card"><span class="icon">🔄</span><span>Reversal Approvals</span></a>
        """

    auditor_btns = ""
    if role == 'AUDITOR':
        auditor_btns = """
        <a href="/pending" class="btn-card btn-card-auditor"><span class="icon">📋</span><span>View Maammilaa & Approve</span></a>
        <a href="/auditor_reversal_request" class="btn-card btn-card-auditor"><span class="icon">⚠️</span><span>Transaction Reversal Gaafachu</span></a>
        """

    loan_btn = ""
    if role in ['LOAN_OFFICER', 'CEO', 'MANAGER']:
        loan_btn = """
        <a href="/islamic_loan" class="btn-card btn-card-loan"><span class="icon">📜</span><span>Mudaraba & Murabaha Loan</span></a>
        """

    ceo_btn = ""
    ceo_mudaraba_dashboard = ""
    if role == 'CEO':
        ceo_mudaraba_dashboard = f"""
        <div class="card-ceo-profit">
            <div class="net-title">📊 CEO Private View: Mudaraba 50/50 Profit Share</div>
            <div class="net-amount">{mud_ceo:,.2f} Birr</div>
            <p style="font-size:11px; opacity:0.9; margin-top:4px;">Qoodda Bu'aa Baankii/CEO (50% Share)</p>
            <div class="net-grid">
                <div>📈 Waliigala Kuusaa Mudaraba: <b>{mud_dep:,.2f} Birr</b></div>
                <div>🤝 Qoodda Maammiltootaa (50%): <b>{mud_cust:,.2f} Birr</b></div>
            </div>
        </div>
        """
        ceo_btn = """
        <a href="/ceo_commission" class="btn-card btn-card-ceo"><span class="icon">💰</span><span>Comishina Guyyaa</span></a>
        <a href="/ceo_mudaraba_list" class="btn-card btn-card-ceo"><span class="icon">🤝</span><span>Mudaraba Private List</span></a>
        <a href="/ceo_blank_form" target="_blank" class="btn-card btn-card-ceo"><span class="icon">🖨️</span><span>Formii Duwwaa Maxxansi</span></a>
        <a href="/reversals_list" class="btn-card btn-card-ceo"><span class="icon">🔄</span><span>CEO Reversal Approval</span></a>
        <a href="/manage_users" class="btn-card btn-card-ceo"><span class="icon">⚙️</span><span>Bulchiinsa Hojjattootaa</span></a>
        """

    content = f"""
    {ceo_mudaraba_dashboard}

    <div class="card-net">
        <div class="net-title">Waliigala Kaabitaala Baankii (Net Capital)</div>
        <div class="net-amount">{net_cap:,.2f} Birr</div>
        <div class="net-grid">
            <div>📥 Deposit: <b>{deposits:,.2f} Birr</b></div>
            <div>📤 Withdraw/FT: <b>{withdraws:,.2f} Birr</b></div>
        </div>
    </div>

    <h3 style="font-size: 14px; margin-bottom: 12px; color: #475569;">Menu Hojii ({role})</h3>
    <div class="grid-2">
        {maker_btns}
        {manager_btns}
        {auditor_btns}
        {loan_btn}
        <a href="/customers" class="btn-card"><span class="icon">👥</span><span>Listii Maammiltootaa</span></a>
        {ceo_btn}
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- CEO USER MANAGEMENT ROUTE ---
@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Shoora CEO qofatu hojjattoota bulchuu danda'a", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    msg = None

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role')
            if username and password and role:
                cursor.execute("SELECT username FROM users WHERE username = %s;", (username,))
                if cursor.fetchone():
                    msg = "❌ User-n kun duraan galmaa'eera!"
                else:
                    cursor.execute("INSERT INTO users (username, password, role, status) VALUES (%s, %s, %s, 'ACTIVE');", (username, generate_password_hash(password), role))
                    conn.commit()
                    msg = f"✅ User {username} ({role}) milkaa'inaan uumameera!"
        elif action == 'toggle_status':
            target_user = request.form.get('username')
            new_status = request.form.get('status')
            if target_user != session['username']:
                cursor.execute("UPDATE users SET status = %s WHERE username = %s;", (new_status, target_user))
                conn.commit()
                msg = f"✅ Status {target_user} gara {new_status} 'ttii jijjiirameera."
        elif action == 'reset_password':
            target_user = request.form.get('username', '').strip()
            new_password = request.form.get('new_password', '').strip()
            if not new_password or len(new_password) < 4:
                msg = "❌ Password haaraa yoo xiqqaate lakkoofsa/qubee 4 qabaachuu qaba."
            else:
                cursor.execute("UPDATE users SET password = %s WHERE username = %s;",
                               (generate_password_hash(new_password), target_user))
                conn.commit()
                msg = f"✅ Password {target_user} tiif haaromfameera (reset)."
                add_notification(f"🔑 Password hojjataa {target_user} CEO-n haaromfame.")

    cursor.execute("SELECT username, role, status FROM users ORDER BY username ASC;")
    users_list = cursor.fetchall()
    cursor.close()
    conn.close()

    users_html = ""
    for u in users_list:
        status_badge = "badge-active" if u['status'] == 'ACTIVE' else "badge-danger"
        toggle_btn = ""
        if u['username'] != session['username']:
            if u['status'] == 'ACTIVE':
                toggle_btn = f'''
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="toggle_status">
                    <input type="hidden" name="username" value="{u['username']}">
                    <input type="hidden" name="status" value="BLOCKED">
                    <button type="submit" class="btn-action btn-red" style="font-size:10px; padding:3px 6px;">🚫 Block</button>
                </form>'''
            else:
                toggle_btn = f'''
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="toggle_status">
                    <input type="hidden" name="username" value="{u['username']}">
                    <input type="hidden" name="status" value="ACTIVE">
                    <button type="submit" class="btn-action btn-green" style="font-size:10px; padding:3px 6px;">🔓 Activate</button>
                </form>'''

        users_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
            <td style="padding:8px; font-weight:bold;">{u['username']}</td>
            <td style="padding:8px;"><span class="role-badge">{u['role']}</span></td>
            <td style="padding:8px;"><span class="badge {status_badge}">{u['status']}</span></td>
            <td style="padding:8px; text-align:right; white-space:nowrap;">
                {toggle_btn}
                <button type="button" class="btn-action btn-purple" style="font-size:10px; padding:3px 6px;"
                        onclick="document.getElementById('reset_pw_modal_{u['username']}').style.display='flex'">🔑 Reset PW</button>
            </td>
        </tr>
        <div id="reset_pw_modal_{u['username']}" class="modal">
            <div class="modal-content">
                <h4 style="color:#7c3aed; font-size:14px;">🔑 Password Haaromsi — {u['username']}</h4>
                <p style="font-size:12px; color:#475569;">Password haaraa galchi; namni kun password haaraa kanaan seena.</p>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_password">
                    <input type="hidden" name="username" value="{u['username']}">
                    <div class="form-group">
                        <input type="text" name="new_password" placeholder="Password haaraa" class="input-field" required minlength="4">
                    </div>
                    <button type="submit" class="btn-submit" style="background:#7c3aed;">✅ Password Haaromsi</button>
                    <button type="button" class="btn-action" style="background:#64748b; margin-top:8px; width:100%; text-align:center;"
                            onclick="document.getElementById('reset_pw_modal_{u['username']}').style.display='none'">Haqi (Cancel)</button>
                </form>
            </div>
        </div>
        """

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#581c87; margin-bottom: 12px;">⚙️ Bulchiinsa Hojjattootaa (CEO User Management)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST" style="margin-bottom:20px; background:#faf5ff; padding:12px; border-radius:8px; border:1px solid #e9d5ff;">
            <input type="hidden" name="action" value="create">
            <h4 style="font-size:13px; color:#581c87; margin-bottom:8px;">➕ Hojjataa Haaraa Uumi</h4>
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required class="input-field">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="text" name="password" required class="input-field">
            </div>
            <div class="form-group">
                <label>Shoora (Role)</label>
                <select name="role" class="input-field" required>
                    <option value="MAKER">MAKER</option>
                    <option value="MANAGER">MANAGER</option>
                    <option value="AUDITOR">AUDITOR</option>
                    <option value="LOAN_OFFICER">LOAN_OFFICER</option>
                    <option value="CEO">CEO</option>
                </select>
            </div>
            <button type="submit" class="btn-submit" style="background:#7c3aed;">➕ Hojjataa Galmeessi</button>
        </form>

        <h3 style="font-size:14px; margin-bottom:8px; color:#334155;">📋 Tarree Hojjattoota Systema</h3>
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Username</th>
                    <th style="padding:8px;">Role</th>
                    <th style="padding:8px;">Status</th>
                    <th style="padding:8px; text-align:right;">Tarkaanfii</th>
                </tr>
            </thead>
            <tbody>
                {users_html}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- CEO: AUTO-BACKUP / AUTO-RESTORE CONTROL PANEL ---
@app.route('/admin/backups', methods=['GET', 'POST'])
def admin_backups():
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Shoora CEO qofatu backup to'achuu danda'a", 403

    msg = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_now':
            bid = create_backup(session['username'])
            msg = f"✅ Backup haaraa {bid} uumameera!"

        elif action == 'save_settings':
            enabled = 'true' if request.form.get('autobackup_enabled') == 'on' else 'false'
            interval = (request.form.get('autobackup_interval_hours') or '24').strip()
            retention = (request.form.get('backup_retention_count') or '30').strip()
            set_setting('autobackup_enabled', enabled)
            set_setting('autobackup_interval_hours', interval)
            set_setting('backup_retention_count', retention)
            msg = "✅ Qindaa'inni Auto-Backup sirreeffameera!"

        elif action == 'restore':
            backup_id = request.form.get('backup_id')
            confirm = (request.form.get('confirm') or '').strip()
            if confirm != 'RESTORE':
                msg = "❌ Restore gochuuf 'RESTORE' jettee barreessuu qabda (mirkaneessaaf)."
            else:
                ok, rmsg = restore_backup(backup_id, session['username'])
                msg = rmsg

    autobackup_enabled = (get_setting('autobackup_enabled', 'true') or 'true') == 'true'
    interval_hours = get_setting('autobackup_interval_hours', '24')
    retention_count = get_setting('backup_retention_count', '30')
    last_auto = get_setting('last_auto_backup_at', 'Hin jiru (Amma hin uumamne)')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT backup_id, created_by, created_at, size_bytes FROM backups ORDER BY created_at DESC LIMIT 100;")
    backups_list = cursor.fetchall()
    cursor.close(); conn.close()

    rows_html = ""
    for b in backups_list:
        size_kb = (b['size_bytes'] or 0) / 1024.0
        rows_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
            <td style="padding:8px; font-weight:bold;">{b['backup_id']}</td>
            <td style="padding:8px;">{b['created_by']}</td>
            <td style="padding:8px;">{b['created_at']}</td>
            <td style="padding:8px;">{size_kb:.1f} KB</td>
            <td style="padding:8px; text-align:right; white-space:nowrap;">
                <a href="/admin/backups/download/{b['backup_id']}" class="btn-action btn-blue" style="font-size:10px; padding:3px 6px;">⬇️ Download</a>
                <button type="button" class="btn-action btn-orange" style="font-size:10px; padding:3px 6px;"
                        onclick="document.getElementById('restore_modal_{b['backup_id']}').style.display='flex'">♻️ Restore</button>
            </td>
        </tr>
        <div id="restore_modal_{b['backup_id']}" class="modal">
            <div class="modal-content">
                <h4 style="color:#dc2626; font-size:14px;">⚠️ Restore Mirkaneessi</h4>
                <p style="font-size:12px; color:#475569;">
                    Kun deetaa ammaa (customers, transactions, users...) hunda balleessee, backup
                    <b>{b['backup_id']}</b> ({b['created_at']}) tiin bakka buusa. Dura backup-iin ammaa
                    ofumaan uumama (undo danda'ama). Mirkaneessuuf gadii "RESTORE" jettee barreessi.
                </p>
                <form method="POST">
                    <input type="hidden" name="action" value="restore">
                    <input type="hidden" name="backup_id" value="{b['backup_id']}">
                    <div class="form-group">
                        <input type="text" name="confirm" placeholder="RESTORE jettee barreessi" class="input-field" required>
                    </div>
                    <button type="submit" class="btn-submit" style="background:#dc2626;">♻️ Eeyyee, Restore Godhi</button>
                    <button type="button" class="btn-action" style="background:#64748b; margin-top:8px; width:100%; text-align:center;"
                            onclick="document.getElementById('restore_modal_{b['backup_id']}').style.display='none'">Haqi (Cancel)</button>
                </form>
            </div>
        </div>
        """

    checked_attr = "checked" if autobackup_enabled else ""

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#581c87; margin-bottom: 12px;">💾 Backup &amp; Restore (CEO)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <div style="background:#faf5ff; padding:12px; border-radius:8px; border:1px solid #e9d5ff; margin-bottom:16px;">
            <h4 style="font-size:13px; color:#581c87; margin-bottom:8px;">⚙️ Qindaa'ina Auto-Backup</h4>
            <form method="POST">
                <input type="hidden" name="action" value="save_settings">
                <div class="form-group" style="display:flex; align-items:center; gap:8px;">
                    <input type="checkbox" name="autobackup_enabled" id="ab_enabled" {checked_attr} style="width:auto;">
                    <label for="ab_enabled" style="margin:0;">Auto-Backup Banii (Enable)</label>
                </div>
                <div class="form-group">
                    <label>Yeroo gidduu (sa'aatiidhaan)</label>
                    <input type="number" step="0.5" min="1" name="autobackup_interval_hours" value="{interval_hours}" class="input-field">
                </div>
                <div class="form-group">
                    <label>Backup meeqa turfamu (Retention count)</label>
                    <input type="number" step="1" min="1" name="backup_retention_count" value="{retention_count}" class="input-field">
                </div>
                <p style="font-size:11px; color:#64748b; margin-bottom:8px;">Backup dhumaa ofumaan: {last_auto}</p>
                <button type="submit" class="btn-submit" style="background:#7c3aed;">💾 Qindaa'ina Olkaa'i</button>
            </form>
        </div>

        <form method="POST" style="margin-bottom:16px;">
            <input type="hidden" name="action" value="create_now">
            <button type="submit" class="btn-submit" style="background:#16a34a;">💾 Amma Backup Uumi (Manual)</button>
        </form>

        <h3 style="font-size:14px; margin-bottom:8px; color:#334155;">📋 Tarree Backup-oota</h3>
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Backup ID</th>
                    <th style="padding:8px;">Namni Uume</th>
                    <th style="padding:8px;">Yeroo</th>
                    <th style="padding:8px;">Guddina</th>
                    <th style="padding:8px; text-align:right;">Tarkaanfii</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/admin/backups/download/<backup_id>')
def admin_backup_download(backup_id):
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Shoora CEO qofatu backup buufachuu danda'a", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM backups WHERE backup_id = %s;", (backup_id,))
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if not row:
        return "❌ Backup hin argamne", 404

    buf = BytesIO(row['data'].encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='application/json', as_attachment=True,
                      download_name=f"{backup_id}.json")

# --- MAKER TRANSACTION ROUTE ---
@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    if 'role' not in session or session['role'] != 'MAKER':
        return "🚫 Shoora MAKER qofatu transaction raawwachuu danda'a", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, balance, freeze_status FROM customers WHERE status='ACTIVE';")
    customers = cursor.fetchall()

    msg = None
    msg_type = "green"

    if request.method == 'POST':
        txn_type = request.form.get('txn_type')
        cust_id = request.form.get('customer_id')
        target_acc = request.form.get('target_account', '').strip()
        amount1 = float(request.form.get('amount', 0.0))
        amount2 = float(request.form.get('amount_confirm', 0.0))
        bank_name = request.form.get('bank_name', 'Imana Microfinance Core')

        cursor.execute("SELECT full_name, balance, freeze_status FROM customers WHERE customer_id = %s;", (cust_id,))
        cust = cursor.fetchone()

        if amount1 != amount2:
            msg = "❌ Dogoggora: Hammi maallaqaa bakka lamatti galchitanii wal-hin simu! Qajeeltoon irra deebi'a barreessaa."
            msg_type = "red"
        elif not cust:
            msg = "❌ Maammilli source hin argamne!"
            msg_type = "red"
        elif cust['freeze_status'] == 'FROZEN' and txn_type in ['WITHDRAWAL', 'T24_TRANSFER']:
            msg = "🔒 Akkaawuntiin maammila kanaa UGGURAMEERA! Baasii ykn Transfer gochuun hin danda'amu."
            msg_type = "red"
        elif amount1 <= 0:
            msg = "❌ Hamma maallaqaa sirrii ta'e galchaa!"
            msg_type = "red"
        else:
            amount = amount1
            commission = get_commission(amount) if txn_type == 'WITHDRAWAL' else 0.0
            total_req = amount + commission

            if txn_type in ['WITHDRAWAL', 'T24_TRANSFER'] and float(cust['balance']) < total_req:
                msg = f"❌ Balansii gahaa miti! Balansii jiru: {float(cust['balance']):,.2f} Birr, Hamma Barbaadamu: {total_req:,.2f} Birr"
                msg_type = "red"
            else:
                timestamp_str = int(datetime.datetime.now().timestamp())
                ft_ref = f"FT{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                txn_id = f"TXN-{timestamp_str}"

                cursor.execute("""
                    INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, target_account, amount, commission, bank_name, ft_reference, status, created_by, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING_MANAGER', %s, %s);
                """, (txn_id, txn_type, cust_id, cust['full_name'], target_acc, amount, commission, bank_name, ft_ref, session['username'], now))

                conn.commit()
                msg = f"✅ Transaction ({txn_type}) {amount:,.2f} Birr galmaa'eera (Ref: {ft_ref}). Approval Manager eegaa jira!"
                add_notification(f"Maker transaction haaraa uumeera: {ft_ref} ({txn_type})")

    cursor.close()
    conn.close()

    cust_options = "".join([f'<option value="{c["customer_id"]}">{c["full_name"]} - {c["customer_id"]} (Bal: {float(c["balance"]):,.2f} Birr)</option>' for c in customers])
    alert_box_style = f"background:{'#dcfce7' if msg_type=='green' else '#fee2e2'}; color:{'#166534' if msg_type=='green' else '#991b1b'}; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;"

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 12px;">💸 Transaction Raawwadhu (Maker T24)</h2>
        
        {f"<p style='{alert_box_style}'>{msg}</p>" if msg else ""}

        <form method="POST" onsubmit="return validateAmounts()">
            <div class="form-group">
                <label>Gosa Kaffaltii (Transaction Type)</label>
                <select name="txn_type" id="txn_type" class="input-field" onchange="toggleTargetAcc()">
                    <option value="DEPOSIT">📥 Deposit (Galii Maallaqaa)</option>
                    <option value="WITHDRAWAL">📤 Withdrawal (Baasii Maallaqaa)</option>
                    <option value="T24_TRANSFER">🔄 T24 Account Transfer (Akaawuntii irraa gara Akaawuntiitti)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Maammila Filadhu (Source Account)</label>
                <select name="customer_id" id="source_account_id" required class="input-field" onchange="verifySourceAccount()">
                    <option value="">-- Maammila Filadhu --</option>
                    {cust_options}
                </select>
                <div id="source_verify_result" style="font-size:11px; margin-top:4px; font-weight:bold;"></div>
            </div>

            <div class="form-group" id="target_acc_group" style="display:none; background:#f0fdf4; padding:10px; border-radius:8px; border:1px solid #bbf7d0;">
                <label>Account ID Nama Fudhatuu (Target Account ID)</label>
                <div style="display:flex; gap:6px;">
                    <input type="text" name="target_account" id="target_account" placeholder="Fkn: 100099008801" class="input-field">
                    <button type="button" onclick="verifyTargetAccount()" class="btn-action btn-purple" style="white-space:nowrap;">🔍 Verify Account</button>
                </div>
                <div id="verify_result" style="font-size:11px; margin-top:6px; font-weight:bold;"></div>
            </div>

            <div class="form-group">
                <label>1. Hamma Maallaqaa (Amount in Birr)</label>
                <input type="number" step="0.01" id="amount" name="amount" placeholder="0.00" required class="input-field">
            </div>
            <div class="form-group">
                <label>2. Irra Deebi'i Barreessi (Confirm Amount in Birr)</label>
                <input type="number" step="0.01" id="amount_confirm" name="amount_confirm" placeholder="0.00" required class="input-field">
            </div>

            <div class="form-group">
                <label>Moggaasa Baankii / Note</label>
                <input type="text" name="bank_name" value="Imana Microfinance Core" class="input-field">
            </div>
            <button type="submit" class="btn-submit">⚡ Transaction Galmeessi (Send to Manager)</button>
        </form>
    </div>

    <script>
    function toggleTargetAcc() {{
        var type = document.getElementById('txn_type').value;
        var group = document.getElementById('target_acc_group');
        if (type === 'T24_TRANSFER') {{
            group.style.display = 'block';
        }} else {{
            group.style.display = 'none';
        }}
    }}

    function verifySourceAccount() {{
        var accId = document.getElementById('source_account_id').value;
        var resDiv = document.getElementById('source_verify_result');
        if(!accId) {{ resDiv.innerHTML = ""; return; }}
        fetch('/api/verify_account/' + accId)
            .then(res => res.json())
            .then(data => {{
                if (data.success) {{
                    resDiv.innerHTML = "<span style='color:#16a34a;'>✅ Source Account Verified: " + data.full_name + " (Bal: " + data.balance + " Birr)</span>";
                }} else {{
                    resDiv.innerHTML = "<span style='color:#dc2626;'>" + data.message + "</span>";
                }}
            }});
    }}

    function verifyTargetAccount() {{
        var accId = document.getElementById('target_account').value.trim();
        var resDiv = document.getElementById('verify_result');
        if (!accId) {{
            resDiv.innerHTML = "<span style='color:red;'>⚠️ Lakkoofsa Account target galchaa!</span>";
            return;
        }}
        resDiv.innerHTML = "⏳ Verification barbaadaa jira...";
        fetch('/api/verify_account/' + accId)
            .then(res => res.json())
            .then(data => {{
                if (data.success) {{
                    resDiv.innerHTML = "<span style='color:#16a34a;'>✅ Target Account Verified: " + data.full_name + " (" + data.status + ")</span>";
                }} else {{
                    resDiv.innerHTML = "<span style='color:#dc2626;'>" + data.message + "</span>";
                }}
            }})
            .catch(err => {{
                resDiv.innerHTML = "<span style='color:red;'>❌ Connection error!</span>";
            }});
    }}

    function validateAmounts() {{
        var a1 = document.getElementById('amount').value;
        var a2 = document.getElementById('amount_confirm').value;
        if (parseFloat(a1) !== parseFloat(a2)) {{
            alert("❌ Dogoggora! Hammi maallaqaa bakka lamatti galchitan wal-hin simu. Maaloo irra deebi'a mirkaneessaa.");
            return false;
        }}
        return true;
    }}
    </script>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- FAST REGISTER CUSTOMER ROUTE ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'role' not in session or session['role'] != 'MAKER':
        return "🚫 Shoora MAKER qofatu maammila galmeessuu danda'a", 403

    msg = None
    if request.method == 'POST':
        full_name = request.form.get('full_name').strip()
        phone = request.form.get('phone').strip()
        gender = request.form.get('gender')
        account_type = request.form.get('account_type')
        initial_balance = max(0.0, float(request.form.get('initial_balance', 0.0)))
        photo_file = request.files.get('photo')
        sig_file = request.files.get('signature')
        nat_id_file = request.files.get('national_id')

        if photo_file and sig_file and allowed_file(photo_file.filename) and allowed_file(sig_file.filename):
            timestamp_str = int(datetime.datetime.now().timestamp())
            
            photo_filename = compress_and_save_image(photo_file, f"face_{timestamp_str}_" + secure_filename(photo_file.filename))
            sig_filename = compress_and_save_image(sig_file, f"sig_{timestamp_str}_" + secure_filename(sig_file.filename))
            
            nat_id_filename = ""
            if nat_id_file and allowed_file(nat_id_file.filename):
                nat_id_filename = compress_and_save_image(nat_id_file, f"nat_{timestamp_str}_" + secure_filename(nat_id_file.filename))

            START_ID = 100099008800
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT MAX(CAST(customer_id AS BIGINT)) AS max_id FROM customers WHERE customer_id >= '100099008800';")
            res = cursor.fetchone()
            max_id = res['max_id'] if res else None

            cust_id = str(START_ID) if max_id is None or max_id < START_ID else str(max_id + 1)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO customers (customer_id, full_name, phone, gender, account_type, photo_path, signature_path, national_id_path, balance, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING_APPROVAL', %s);
            """, (cust_id, full_name, phone, gender, account_type, photo_filename, sig_filename, nat_id_filename, initial_balance, now))

            if initial_balance > 0:
                ft_ref = f"FT{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
                cursor.execute("""
                    INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, amount, bank_name, ft_reference, status, created_by, timestamp)
                    VALUES (%s, 'DEPOSIT', %s, %s, %s, 'Imana Microfinance Core', %s, 'APPROVED', %s, %s);
                """, (f"TXN-INIT-{timestamp_str}", cust_id, full_name, initial_balance, ft_ref, session['username'], now))

            conn.commit()
            cursor.close()
            conn.close()
            msg = f"⚡ Maammilli {full_name} ({account_type} / {gender}) dafee galmaa'eera! (T24 Acc: {cust_id})."
            add_notification(f"Galmeen maammila haaraa ({full_name}) raawwatameera.")

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; margin-bottom: 12px; color:#065f46;">⚡ Galmee Maammilaa Saffisaa (Network 2G/3G/4G Optimized)</h2>
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}
        
        <form method="POST" enctype="multipart/form-data" id="fastRegForm" onsubmit="showLoading()">
            <div class="form-group">
                <label>Maqaa Guutuu Maammilaa</label>
                <input type="text" name="full_name" required class="input-field">
            </div>
            <div class="form-group">
                <label>Saala (Sex / Gender)</label>
                <select name="gender" class="input-field" required>
                    <option value="Dhiira">Dhiira (Male)</option>
                    <option value="Dubartii">Dubartii (Female)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Gosa Akkaawuntii (Account Scheme)</label>
                <select name="account_type" class="input-field" required>
                    <option value="WADIA">A, Wadia Savings (Yeroo Gabaabduu / Waadiaa Faaydaa Malee)</option>
                    <option value="MUDARABA">B, Mudaraba Investment (50%, 50% Profit Share)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Lakkoofsa Bilbilaa</label>
                <input type="text" name="phone" required class="input-field">
            </div>
            <div class="form-group">
                <label>Balansii Jalqabaa (Initial Balance in Birr)</label>
                <input type="number" step="0.01" min="0" name="initial_balance" value="0.00" required class="input-field">
            </div>
            <div class="form-group">
                <label>📸 Suuraa Fuula Maammilaa</label>
                <input type="file" name="photo" accept="image/*" required class="input-field">
            </div>
            <div class="form-group">
                <label>✍️ Mallattoo Galmee (Signature)</label>
                <input type="file" name="signature" accept="image/*" required class="input-field">
            </div>
            <div class="form-group">
                <label>🆔 Waraqaa Eenyummaa (National ID / Fayda / Passport)</label>
                <input type="file" name="national_id" accept="image/*,.pdf" class="input-field">
            </div>
            <button type="submit" id="btnRegSubmit" class="btn-submit">⚡ Dafeen Galmeessi (Create T24 Account)</button>
        </form>
    </div>

    <script>
    function showLoading() {{
        var btn = document.getElementById('btnRegSubmit');
        btn.innerHTML = "⏳ Process gochaa jira (Fast Speed)...";
        btn.disabled = true;
        btn.style.opacity = "0.7";
        return true;
    }}
    </script>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- MAKER RECEIPTS ROUTE ---
@app.route('/maker_receipts')
def maker_receipts():
    if 'role' not in session or session['role'] != 'MAKER':
        return "🚫 Shoora MAKER qofa!", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT txn_id, ft_reference, txn_type, customer_name, amount, status, timestamp 
        FROM transactions 
        WHERE created_by = %s 
        ORDER BY timestamp DESC;
    """, (session['username'],))
    txns = cursor.fetchall()
    cursor.close()
    conn.close()

    cards_html = ""
    for t in txns:
        badge_cls = "badge-active" if t['status'] == 'APPROVED' else ("badge-danger" if 'REJECTED' in t['status'] else "badge-pending")
        cards_html += f"""
        <div class="item-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:12px; font-weight:bold; color:#065f46;">Ref: {t['ft_reference']}</span>
                <span class="badge {badge_cls}">{t['status']}</span>
            </div>
            <div style="font-size:13px; font-weight:bold; margin-top:4px;">{t['txn_type']}: {float(t['amount']):,.2f} Birr</div>
            <div style="font-size:11px; color:#64748b; margin-top:2px;">Maammila: {t['customer_name']} | {t['timestamp']}</div>
            <div style="text-align:right; margin-top:8px;">
                <a href="/receipt/{t['txn_id']}" target="_blank" class="btn-action btn-purple">🖨️ Nagahee Maxxansi</a>
            </div>
        </div>
        """

    content = f"""
    <h2 style="font-size: 16px; margin-bottom: 12px; color:#065f46;">🧾 Nagaheewwan Kaffaltii (Maker Receipts)</h2>
    {cards_html if cards_html else "<p style='text-align:center; padding:20px; color:#64748b; font-size:12px;'>Nagaheen galmaa'e hin jiru.</p>"}
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- CEO PRIVATE VIEW: MUDARABA LIST ---
@app.route('/ceo_mudaraba_list')
def ceo_mudaraba_list():
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Addatti CEO Qofatu Listii Mudarabaa Ilaaluu Danda'a!", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, phone, gender, balance, created_at FROM customers WHERE account_type='MUDARABA' AND status='ACTIVE';")
    mudaraba_custs = cursor.fetchall()
    cursor.close()
    conn.close()

    rows_html = ""
    total_mudaraba_bal = 0.0

    for c in mudaraba_custs:
        bal = float(c['balance'])
        total_mudaraba_bal += bal
        cust_profit = (bal * 0.10) * 0.50
        ceo_profit = (bal * 0.10) * 0.50

        rows_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
            <td style="padding:8px; font-weight:bold;">{c['customer_id']}</td>
            <td style="padding:8px;">{c['full_name']} ({c['gender']})</td>
            <td style="padding:8px;">{c['phone']}</td>
            <td style="padding:8px; font-weight:bold; color:#065f46;">{bal:,.2f} Birr</td>
            <td style="padding:8px; color:#6b21a8; font-weight:bold;">+{cust_profit:,.2f} Birr</td>
            <td style="padding:8px; color:#047857; font-weight:bold;">+{ceo_profit:,.2f} Birr</td>
        </tr>
        """

    content = f"""
    <div class="card-ceo-profit">
        <div class="net-title">🔒 CEO PRIVATE: LISTII MAAMMILTOOTAA MUDARABA</div>
        <div class="net-amount">{total_mudaraba_bal:,.2f} Birr</div>
        <p style="font-size:11px; opacity:0.9; margin-top:4px;">Kuusaa Waliigala Maammiltoota Mudaraba Investment</p>
    </div>

    <h3 style="font-size:14px; margin-bottom:8px; color:#334155;">📋 Tarree Maammiltoota Mudarabaa (50/50 Profit Split)</h3>
    <div class="box" style="padding:0; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Acc ID</th>
                    <th style="padding:8px;">Maqaa Guutuu</th>
                    <th style="padding:8px;">Bilbila</th>
                    <th style="padding:8px;">Balance</th>
                    <th style="padding:8px;">Qooda Maammilaa (50%)</th>
                    <th style="padding:8px;">Qooda CEO/Bank (50%)</th>
                </tr>
            </thead>
            <tbody>
                {rows_html if rows_html else '<tr><td colspan="6" style="padding:16px; text-align:center; color:#64748b;">Maammilli Mudarabaa galmaa\'e hin jiru.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- STATEMENT PRINTING ROUTE ---
@app.route('/statement/<cust_id>')
def statement(cust_id):
    if 'role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = %s;", (cust_id,))
    c = cursor.fetchone()

    if not c:
        cursor.close()
        conn.close()
        return "Maammilli Hin Argamne", 404

    cursor.execute("""
        SELECT txn_id, txn_type, amount, commission, ft_reference, status, created_by, timestamp
        FROM transactions
        WHERE customer_id = %s OR target_account = %s
        ORDER BY timestamp DESC;
    """, (cust_id, cust_id))
    txns = cursor.fetchall()
    cursor.close()
    conn.close()

    rows_html = ""
    for t in txns:
        badge_cls = "badge-active" if t['status'] == 'APPROVED' else ("badge-danger" if 'REJECTED' in t['status'] else "badge-pending")
        rows_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:11px;">
            <td style="padding:8px;">{t['timestamp']}</td>
            <td style="padding:8px; font-weight:bold;">{t['ft_reference']}</td>
            <td style="padding:8px;">{t['txn_type']}</td>
            <td style="padding:8px; font-weight:bold;">{float(t['amount']):,.2f}</td>
            <td style="padding:8px;">{float(t['commission']):,.2f}</td>
            <td style="padding:8px;"><span class="badge {badge_cls}">{t['status']}</span></td>
        </tr>
        """

    content = f"""
    <div class="box">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h2 style="font-size: 16px; color:#065f46; margin-bottom:4px;">📜 Account Statement</h2>
                <p style="font-size: 12px; font-weight:bold;">{c['full_name']} (Acc: {c['customer_id']})</p>
                <p style="font-size: 11px; color:#64748b;">Saala: <b>{c['gender']}</b> | Scheme: <b>{c['account_type']}</b></p>
                <p style="font-size: 11px; color:#64748b;">Haafe (Current Balance): <b style="color:#065f46;">{float(c['balance']):,.2f} Birr</b></p>
            </div>
            <button onclick="window.print()" class="btn-action btn-purple no-print">🖨️ Print Statement</button>
        </div>
    </div>

    <div class="box" style="padding:0; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Guyyaa</th>
                    <th style="padding:8px;">Ref</th>
                    <th style="padding:8px;">Type</th>
                    <th style="padding:8px;">Hamma</th>
                    <th style="padding:8px;">Comm</th>
                    <th style="padding:8px;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows_html if rows_html else '<tr><td colspan="6" style="padding:16px; text-align:center; color:#64748b;">Transaction-ni socho\'e hin jiru.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- EDIT CUSTOMER INFORMATION ROUTE ---
@app.route('/edit_customer/<cust_id>', methods=['GET', 'POST'])
def edit_customer(cust_id):
    if 'role' not in session or session['role'] != 'MANAGER':
        return "🚫 Shoora MANAGER qofatu odeeffannoo maammilaa edituu danda'a", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = %s;", (cust_id,))
    customer = cursor.fetchone()

    if not customer:
        cursor.close()
        conn.close()
        return "Maammilli Hin Argamne", 404

    msg = None
    if request.method == 'POST':
        full_name = request.form.get('full_name').strip()
        phone = request.form.get('phone').strip()
        gender = request.form.get('gender')
        account_type = request.form.get('account_type')

        photo_file = request.files.get('photo')
        sig_file = request.files.get('signature')
        nat_id_file = request.files.get('national_id')

        photo_filename = customer['photo_path']
        sig_filename = customer['signature_path']
        nat_id_filename = customer['national_id_path']

        timestamp_str = int(datetime.datetime.now().timestamp())

        if photo_file and photo_file.filename and allowed_file(photo_file.filename):
            photo_filename = compress_and_save_image(photo_file, f"face_edit_{timestamp_str}_" + secure_filename(photo_file.filename))

        if sig_file and sig_file.filename and allowed_file(sig_file.filename):
            sig_filename = compress_and_save_image(sig_file, f"sig_edit_{timestamp_str}_" + secure_filename(sig_file.filename))

        if nat_id_file and nat_id_file.filename and allowed_file(nat_id_file.filename):
            nat_id_filename = compress_and_save_image(nat_id_file, f"nat_edit_{timestamp_str}_" + secure_filename(nat_id_file.filename))

        cursor.execute("""
            UPDATE customers 
            SET full_name = %s, phone = %s, gender = %s, account_type = %s, photo_path = %s, signature_path = %s, national_id_path = %s
            WHERE customer_id = %s;
        """, (full_name, phone, gender, account_type, photo_filename, sig_filename, nat_id_filename, cust_id))
        conn.commit()
        
        cursor.execute("SELECT * FROM customers WHERE customer_id = %s;", (cust_id,))
        customer = cursor.fetchone()
        msg = f"✅ Odeeffannoon maammilaa ({cust_id}) milkaa'inaan foyya'eera (Edited)!"
        add_notification(f"Manager odeeffannoo maammilaa ({cust_id}) jijjiiree jira.")

    cursor.close()
    conn.close()
    
    nat_id_link = f'<a href="/uploads/{customer["national_id_path"]}" target="_blank">Ilaali</a>' if customer['national_id_path'] else 'Hin Jiru'
    dhiira_selected = 'selected' if customer['gender'] == 'Dhiira' else ''
    dubartii_selected = 'selected' if customer['gender'] == 'Dubartii' else ''
    wadia_selected = 'selected' if customer['account_type'] == 'WADIA' else ''
    mudaraba_selected = 'selected' if customer['account_type'] == 'MUDARABA' else ''

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#2563eb; margin-bottom: 4px;">✏️ Odeeffannoo Maammilaa Foyyeessi (Edit Customer)</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Acc ID: <b>{customer['customer_id']}</b></p>
        
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label>Maqaa Guutuu Maammilaa</label>
                <input type="text" name="full_name" value="{customer['full_name']}" required class="input-field">
            </div>
            <div class="form-group">
                <label>Lakkoofsa Bilbilaa</label>
                <input type="text" name="phone" value="{customer['phone']}" required class="input-field">
            </div>
            <div class="form-group">
                <label>Saala (Gender)</label>
                <select name="gender" class="input-field">
                    <option value="Dhiira" {dhiira_selected}>Dhiira</option>
                    <option value="Dubartii" {dubartii_selected}>Dubartii</option>
                </select>
            </div>
            <div class="form-group">
                <label>Gosa Akkaawuntii (Account Scheme)</label>
                <select name="account_type" class="input-field">
                    <option value="WADIA" {wadia_selected}>A, Wadia Savings (Yeroo Gabaabduu / Faaydaa Malee)</option>
                    <option value="MUDARABA" {mudaraba_selected}>B, Mudaraba Investment (50%, 50% Profit Share)</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>📸 Suuraa Fuulaa Jijjiiri (Optional)</label>
                <input type="file" name="photo" accept="image/*" class="input-field">
                <p style="font-size:10px; color:#64748b;">Suuraa Duraan Jiru: <a href="/uploads/{customer['photo_path']}" target="_blank">Ilaali</a></p>
            </div>
            <div class="form-group">
                <label>✍️ Mallattoo Jijjiiri (Optional)</label>
                <input type="file" name="signature" accept="image/*" class="input-field">
                <p style="font-size:10px; color:#64748b;">Mallattoo Duraan Jiru: <a href="/uploads/{customer['signature_path']}" target="_blank">Ilaali</a></p>
            </div>
            <div class="form-group">
                <label>🆔 National ID / Fayda Jijjiiri (Optional)</label>
                <input type="file" name="national_id" accept="image/*,.pdf" class="input-field">
                <p style="font-size:10px; color:#64748b;">National ID Duraan Jiru: {nat_id_link}</p>
            </div>

            <button type="submit" class="btn-submit" style="background:#2563eb;">💾 Odeeffannoo Foyya'e Save Godhi</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# --- ISLAMIC FINANCING (MUDARABA & MURABAHA) ---
@app.route('/islamic_loan', methods=['GET', 'POST'])
def islamic_loan():
    if 'role' not in session or session['role'] not in ['LOAN_OFFICER', 'CEO', 'MANAGER']:
        return "🚫 Shoora Hayyama Qabu Qofatu Kanatti Fayyadama", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, balance FROM customers WHERE status='ACTIVE';")
    active_customers = cursor.fetchall()

    msg = None
    if request.method == 'POST':
        cust_id = request.form.get('customer_id')
        financing_type = request.form.get('financing_type')
        principal = float(request.form.get('principal_amount', 0))
        profit_rate = float(request.form.get('profit_margin', 0))
        tenure = int(request.form.get('tenure_months', 12))
        notes = request.form.get('agent_notes', '').strip()

        cursor.execute("SELECT full_name FROM customers WHERE customer_id = %s;", (cust_id,))
        cust_row = cursor.fetchone()
        cust_name = cust_row['full_name'] if cust_row else "Unknown"

        profit_amount = principal * (profit_rate / 100.0)
        total_repayment = principal + profit_amount
        monthly_installment = total_repayment / tenure if tenure > 0 else total_repayment

        loan_id = f"LN-{financing_type[:3]}-{int(datetime.datetime.now().timestamp())}"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO islamic_financing (loan_id, customer_id, customer_name, financing_type, principal_amount, profit_margin, total_repayment, tenure_months, monthly_installment, status, agent_notes, created_by, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING_MANAGER', %s, %s, %s);
        """, (loan_id, cust_id, cust_name, financing_type, principal, profit_amount, total_repayment, tenure, monthly_installment, notes, session['username'], now))

        conn.commit()
        msg = f"📜 Liqaa Islaamaa {financing_type} ({principal:,.2f} Birr) Maammila {cust_name}-f mijeesseera! Mirkaneessa Manager & CEO eegaa jira."
        add_notification(f"Gaaffii liqaa {financing_type} uumameera ID: {loan_id}")

    cursor.execute("SELECT * FROM islamic_financing ORDER BY timestamp DESC;")
    loans_list = cursor.fetchall()
    cursor.close()
    conn.close()

    options_html = "".join([f'<option value="{c["customer_id"]}">{c["full_name"]} (Acc: {c["customer_id"]})</option>' for c in active_customers])

    loans_html = ""
    for l in loans_list:
        badge_cls = "badge-pending" if 'PENDING' in l['status'] else ("badge-active" if l['status'] == 'APPROVED' else "badge-danger")
        
        approval_actions = ""
        if session['role'] == 'MANAGER' and l['status'] == 'PENDING_MANAGER':
            approval_actions = f"""
            <div style="margin-top:8px;">
                <a href="/approve_loan/manager/{l['loan_id']}" class="btn-action btn-blue">✅ Manager Approve</a>
                <a href="/reject_loan/{l['loan_id']}" class="btn-action btn-red">❌ Reject</a>
            </div>
            """
        elif session['role'] == 'CEO' and l['status'] == 'PENDING_CEO':
            approval_actions = f"""
            <div style="margin-top:8px;">
                <a href="/approve_loan/ceo/{l['loan_id']}" class="btn-action btn-purple">✅ CEO Final Approve</a>
                <a href="/reject_loan/{l['loan_id']}" class="btn-action btn-red">❌ Reject</a>
            </div>
            """

        notes_div = f'<div style="font-size:10px; color:#64748b; margin-top:4px;">Yaada Analysis: {l["agent_notes"]}</div>' if l['agent_notes'] else ''

        loans_html += f"""
        <div class="item-card" style="border-left: 4px solid #16a34a;">
            <div style="display:flex; justify-content:space-between;">
                <span style="font-size:12px; font-weight:bold; color:#16a34a;">{l['loan_id']} ({l['financing_type']})</span>
                <span class="badge {badge_cls}">{l['status']}</span>
            </div>
            <div style="font-size:13px; font-weight:bold; margin-top:4px;">Maammila: {l['customer_name']}</div>
            <div style="font-size:11px; color:#475569; margin-top:4px;">
                Kaabitaala: <b>{float(l['principal_amount']):,.2f} Birr</b> | Dhala/Gabbii: <b>{float(l['profit_margin']):,.2f} Birr</b><br>
                Waliigala Deebi'u: <b>{float(l['total_repayment']):,.2f} Birr</b> | Baatiitti: <b>{float(l['monthly_installment']):,.2f} Birr ({l['tenure_months']} Baatii)</b>
            </div>
            {notes_div}
            {approval_actions}
        </div>
        """

    content = f"""
    <div class="box" style="background:#f0fdf4; border-color:#bbf7d0;">
        <h2 style="font-size: 16px; color:#15803d; margin-bottom: 4px;">📜 Mijjeessaa Liqaa Islaamaa (Mudaraba & Murabaha)</h2>
        <p style="font-size: 11px; color:#166534;">Liqaa dhala irraa bilisa ta'e (Interest Free) shallagii fi uumi.</p>
    </div>

    {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

    <div class="box">
        <form method="POST">
            <div class="form-group">
                <label>Maammila Filadhu</label>
                <select name="customer_id" required class="input-field">
                    {options_html}
                </select>
            </div>
            <div class="form-group">
                <label>Gosa Liqaa Islaamaa (Financing Scheme)</label>
                <select name="financing_type" class="input-field">
                    <option value="MUDARABA">MUDARABA (Shiraakaa Kaabitaalaa & Hojii)</option>
                    <option value="MURABAHA">MURABAHA (Gurgurtaa Gabbii / Cost-Plus Profit)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Hamma Kaabitaala Liqaa (Principal Birr)</label>
                <input type="number" step="0.01" name="principal_amount" placeholder="Fkn: 50000" required class="input-field">
            </div>
            <div class="form-group">
                <label>Dhibbeentaa Gabbii / Bu'aa (Profit Margin %)</label>
                <input type="number" step="0.1" name="profit_margin" placeholder="Fkn: 5" required class="input-field">
            </div>
            <div class="form-group">
                <label>Turee Yeroo Deebii (Months / Baatii)</label>
                <input type="number" name="tenure_months" value="12" required class="input-field">
            </div>
            <div class="form-group">
                <label>Yaada / Qorannoo Liqaa (Analysis Notes)</label>
                <textarea name="agent_notes" rows="2" placeholder="Yaada..." class="input-field"></textarea>
            </div>
            <button type="submit" class="btn-submit" style="background:#16a34a;">📜 Liqaa Islaamaa Shallagi Uumi</button>
        </form>
    </div>

    <h3 style="font-size: 14px; margin-bottom: 8px; color: #334155;">📋 Listii Liqaa Islaamaa Uumamaan</h3>
    {loans_html if loans_html else "<p style='text-align:center; padding:16px; color:#64748b; font-size:12px;'>Liqaan galmaa'e hin jiru.</p>"}
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/approve_loan/<role_type>/<loan_id>')
def approve_loan(role_type, loan_id):
    if 'role' not in session or session['role'] not in ['MANAGER', 'CEO']:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM islamic_financing WHERE loan_id = %s;", (loan_id,))
    loan = cursor.fetchone()

    if not loan:
        cursor.close()
        conn.close()
        return "Liqaan Hin Argamne", 404

    if role_type == 'manager' and session['role'] == 'MANAGER':
        cursor.execute("UPDATE islamic_financing SET status = 'PENDING_CEO', manager_approved = 1 WHERE loan_id = %s;", (loan_id,))
        add_notification(f"Manager loan_id {loan_id} approve godheera. CEO approval eegaa jira.")
    elif role_type == 'ceo' and session['role'] == 'CEO':
        cursor.execute("UPDATE islamic_financing SET status = 'APPROVED', ceo_approved = 1 WHERE loan_id = %s;", (loan_id,))
        cursor.execute("UPDATE customers SET balance = balance + %s WHERE customer_id = %s;", (loan['principal_amount'], loan['customer_id']))
        add_notification(f"CEO loan_id {loan_id} FINAL APPROVED! Maallaqni maammilaaf dhangala'eera.")

    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/islamic_loan')

@app.route('/reject_loan/<loan_id>')
def reject_loan(loan_id):
    if 'role' not in session or session['role'] not in ['MANAGER', 'CEO']:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE islamic_financing SET status = 'REJECTED' WHERE loan_id = %s;", (loan_id,))
    conn.commit()
    cursor.close()
    conn.close()
    add_notification(f"Gaaffiin liqaa {loan_id} REJECTED ta'ee jira.")
    return redirect('/islamic_loan')

@app.route('/pending')
def pending():
    if 'role' not in session or session['role'] not in ['MANAGER', 'AUDITOR']:
        return "🚫 Hayyama Manager ykn Auditor Qofa!", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT customer_id, full_name, phone, gender, account_type, photo_path, signature_path, national_id_path FROM customers WHERE status='PENDING_APPROVAL';")
    pending_custs = cursor.fetchall()

    cursor.execute("""
        SELECT 
            t.txn_id, t.txn_type, t.customer_name, t.amount, t.bank_name, t.status,
            c.photo_path, c.signature_path, c.national_id_path, c.phone, t.customer_id, t.ft_reference, t.target_account, t.commission,
            c.freeze_status, c.freeze_reason, c.gender, c.account_type
        FROM transactions t
        LEFT JOIN customers c ON t.customer_id = c.customer_id
        WHERE t.status = 'PENDING_MANAGER'
        ORDER BY t.timestamp DESC;
    """)
    pending_txns = cursor.fetchall()
    cursor.close()
    conn.close()

    cards_html = ""

    if pending_custs:
        cards_html += "<h3 style='font-size:12px; color:#1e40af; margin-bottom:8px;'>👤 Galmee Maammiltoota Eeggamaa Jiran</h3>"
        for c in pending_custs:
            account_badge = "badge-mudaraba" if c['account_type'] == 'MUDARABA' else "badge-wadia"
            cards_html += f"""
            <div class="item-card" style="background:#eff6ff; border-color:#bfdbfe;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12px; font-weight:bold; color:#1e3a8a;">Acc: {c['customer_id']}</span>
                    <div>
                        <span class="badge {account_badge}">{c['account_type']}</span>
                        <span class="badge badge-pending">PENDING</span>
                    </div>
                </div>
                <div style="font-size:13px; font-weight:bold; margin-bottom:2px;">Maqaa: {c['full_name']} (📞 {c['phone']})</div>
                <div style="font-size:11px; color:#475569; margin-bottom:6px;">Saala: <b>{c['gender']}</b></div>
                <div class="img-grid">
                    <div style="text-align:center;"><img src="/uploads/{c['photo_path']}"><span style="font-size:10px;">Fuula</span></div>
                    <div style="text-align:center;"><img src="/uploads/{c['signature_path']}"><span style="font-size:10px;">Mallattoo</span></div>
                </div>
                <div style="text-align:right; margin-top:8px;">
                    <a href="/approve_customer/{c['customer_id']}" class="btn-action btn-green">✅ Approve</a>
                    <a href="/reject_customer/{c['customer_id']}" class="btn-action btn-red">❌ Reject</a>
                </div>
            </div>
            """

    if pending_txns:
        cards_html += "<h3 style='font-size:12px; color:#065f46; margin-top:16px; margin-bottom:8px;'>💸 Transaction-ooma Eeggamaa Jiran</h3>"
        for t in pending_txns:
            cards_html += f"""
            <div class="item-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:12px; font-weight:bold; color:#065f46;">Ref: {t['ft_reference']}</span>
                    <span class="badge badge-pending">{t['status']}</span>
                </div>
                <div style="font-size:13px; font-weight:bold; margin-top:4px;">{t['txn_type']}: {float(t['amount']):,.2f} Birr</div>
                <div style="font-size:11px; color:#64748b; margin-top:2px;">Maammila: {t['customer_name']} (Acc: {t['customer_id']})</div>
                <div style="text-align:right; margin-top:8px;">
                    <a href="/approve_transaction/{t['txn_id']}" class="btn-action btn-green">✅ Approve</a>
                    <a href="/reject_transaction/{t['txn_id']}" class="btn-action btn-red">❌ Reject</a>
                </div>
            </div>
            """

    content = f"""
    <h2 style="font-size: 16px; margin-bottom: 12px; color:#065f46;">📋 Eeggattoota Approval (Pending Queue)</h2>
    {cards_html if cards_html else "<p style='text-align:center; padding:20px; color:#64748b; font-size:12px;'>Wanti eeggamaa jiru hin jiru.</p>"}
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
