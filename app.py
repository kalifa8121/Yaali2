import os
import sqlite3
import datetime
import random
import shutil
import csv
import sys
import time
import atexit
from io import BytesIO, StringIO

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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BACKUP_FOLDER'] = BACKUP_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

NOTIFICATIONS = []

def compress_and_save_image(file_storage, target_filename, max_size=(300, 300), quality=35):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], target_filename)
    filename = file_storage.filename.lower()
    
    if filename.endswith('.pdf') or filename.endswith('.csv') or not HAS_PIL:
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

def get_db_connection(max_retries=10, delay=0.5):
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=60)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA mmap_size = 268435456;")
            return conn
        except sqlite3.OperationalError as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_commission(amount):
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
            ('officer1', 'officer123', 'LOAN_OFFICER', 'ACTIVE'),
            ('ext_agent1', 'agent123', 'EXTERNAL_AGENT', 'ACTIVE')
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
            pin TEXT DEFAULT '1234',
            created_at TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN pin TEXT DEFAULT '1234'")
    except sqlite3.OperationalError:
        pass

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS islamic_financing (
            loan_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            customer_name TEXT,
            financing_type TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            profit_margin REAL DEFAULT 0.0,
            total_repayment REAL NOT NULL,
            tenure_months INTEGER,
            monthly_installment REAL,
            status TEXT DEFAULT 'PENDING_MANAGER',
            manager_approved INTEGER DEFAULT 0,
            ceo_approved INTEGER DEFAULT 0,
            agent_notes TEXT,
            created_by TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

def get_bank_capital():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status='APPROVED' AND txn_type='DEPOSIT'")
    total_deposit = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status='APPROVED' AND txn_type IN ('WITHDRAWAL', 'T24_TRANSFER', 'WALLET_TRANSFER', 'BILL_PAYMENT')")
    total_withdraw = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(balance) FROM customers WHERE status='ACTIVE'")
    total_cust_balance = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(commission) FROM transactions WHERE status='APPROVED'")
    total_commission = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(balance) FROM customers WHERE status='ACTIVE' AND account_type='MUDARABA'")
    total_mudaraba_deposits = cursor.fetchone()[0] or 0.0

    mudaraba_gross_profit = total_mudaraba_deposits * 0.10
    mudaraba_ceo_share = mudaraba_gross_profit * 0.50
    mudaraba_customer_share = mudaraba_gross_profit * 0.50
    
    net_capital = total_deposit - total_withdraw + total_commission
    conn.close()
    return max(0.0, net_capital), total_deposit, total_withdraw, total_cust_balance, total_commission, total_mudaraba_deposits, mudaraba_gross_profit, mudaraba_ceo_share, mudaraba_customer_share

# --- HTML LAYOUT (STAFF) ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="om">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Imana Free Interest Microfinance - Staff</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #f8fafc; padding-bottom: 75px; color: #0f172a; }
        nav { background: linear-gradient(135deg, #065f46, #047857); color: white; padding: 12px 16px; position: sticky; top: 0; z-index: 50; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .logo-container { display: flex; align-items: center; gap: 10px; }
        nav h1 { font-size: 15px; font-weight: 800; letter-spacing: 0.3px; color: #ffffff; }
        .role-badge { background: #0284c7; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        .notification-bar { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 8px; font-size: 11px; margin-bottom: 12px; font-weight: bold; border: 1px solid #fde68a; }
        .card-net { background: linear-gradient(135deg, #064e3b, #047857); color: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(6,78,59,0.3); margin-bottom: 20px; }
        .net-title { font-size: 12px; opacity: 0.9; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
        .net-amount { font-size: 32px; font-weight: 800; color: #fbbf24; }
        .net-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.2); font-size: 12px; padding-top: 12px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .btn-card { background: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #334155; font-weight: bold; font-size: 13px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: 0.2s; }
        .btn-card:active { transform: scale(0.98); }
        .btn-card span.icon { font-size: 24px; margin-bottom: 8px; }
        .btn-card-ceo { background: #faf5ff; border-color: #e9d5ff; color: #581c87; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: white; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-around; padding: 10px 0; z-index: 50; }
        .bottom-nav a { text-align: center; color: #64748b; text-decoration: none; font-size: 11px; flex: 1; font-weight: 500; }
        .bottom-nav a span.icon { display: block; font-size: 18px; margin-bottom: 2px; }
        .box { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px; }
        .form-group { margin-bottom: 12px; position: relative; }
        .form-group label { display: block; font-size: 12px; font-weight: bold; color: #475569; margin-bottom: 4px; }
        .input-field { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; }
        .btn-submit { width: 100%; background: #047857; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }
    </style>
</head>
<body>
    <nav class="no-print">
        <div class="logo-container">
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
            <div class="notification-bar">
                🔔 NOTIFICATION: {{ notifications[0] }}
            </div>
        {% endif %}
        {% block content %}{% endblock %}
    </div>

    {% if session.get('role') %}
    <div class="bottom-nav">
        <a href="/"><span class="icon">🏠</span>Dashboard</a>
        {% if session['role'] in ['MANAGER', 'CEO'] %}
            <a href="/import_customers_csv"><span class="icon">📥</span>Import CSV</a>
        {% endif %}
        <a href="/customers"><span class="icon">👥</span>Maammiltoota</a>
    </div>
    {% endif %}
</body>
</html>
"""

# --- MOBILE LAYOUT (CUSTOMER) ---
MOBILE_LAYOUT = """
<!DOCTYPE html>
<html lang="om">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>IMANA Mobile Banking</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #f1f5f9; padding-bottom: 75px; color: #0f172a; }
        .mobile-header { background: linear-gradient(135deg, #065f46, #047857); color: white; padding: 18px 16px; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
        .header-top { display: flex; justify-content: space-between; align-items: center; }
        .app-title { font-size: 18px; font-weight: 800; color: #fbbf24; letter-spacing: 0.5px; }
        .user-greeting { font-size: 13px; margin-top: 10px; opacity: 0.95; }
        .app-container { padding: 16px; max-width: 480px; margin: 0 auto; }
        .balance-card { background: linear-gradient(135deg, #047857, #064e3b); color: white; border-radius: 18px; padding: 22px; box-shadow: 0 8px 20px rgba(6,78,59,0.3); margin-top: -15px; margin-bottom: 20px; text-align: center; }
        .balance-label { font-size: 12px; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.5px; }
        .balance-val { font-size: 32px; font-weight: 900; color: #fbbf24; margin: 6px 0; }
        .acc-number { font-size: 12px; background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 12px; display: inline-block; margin-top: 4px; }
        .quick-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
        .action-btn { background: white; padding: 16px 12px; border-radius: 16px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #1e293b; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.04); text-align: center; }
        .action-btn span.icon { font-size: 24px; margin-bottom: 6px; }
        .bottom-m-nav { position: fixed; bottom: 0; left: 0; right: 0; background: white; border-top: 1px solid #e2e8f0; display: flex; justify-around: space-around; padding: 12px 0; z-index: 100; box-shadow: 0 -2px 10px rgba(0,0,0,0.05); }
        .bottom-m-nav a { text-align: center; color: #64748b; text-decoration: none; font-size: 11px; font-weight: 600; flex: 1; }
        .bottom-m-nav a span.icon { display: block; font-size: 20px; margin-bottom: 2px; }
        .m-box { background: white; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 2px 6px rgba(0,0,0,0.04); margin-bottom: 16px; }
        .m-input { width: 100%; padding: 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 14px; outline: none; margin-top: 4px; }
        .m-btn { width: 100%; background: #047857; color: white; border: none; padding: 14px; border-radius: 12px; font-weight: bold; font-size: 15px; cursor: pointer; margin-top: 10px; }
        .m-txn-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
    </style>
</head>
<body>
    <div class="mobile-header">
        <div class="header-top">
            <span class="app-title">📱 IMANA MOBILE</span>
            {% if session.get('is_customer') %}
                <a href="/mobile/logout" style="color:#fca5a5; font-size:12px; text-decoration:none; font-weight:bold;">Logout</a>
            {% endif %}
        </div>
        {% if session.get('is_customer') %}
            <div class="user-greeting">Akkam, <b>{{ session['customer_name'] }}</b> 👋</div>
        {% endif %}
    </div>

    <div class="app-container">
        {% block content %}{% endblock %}
    </div>

    {% if session.get('is_customer') %}
    <div class="bottom-m-nav">
        <a href="/mobile/dashboard"><span class="icon">🏠</span>Duraa</a>
        <a href="/mobile/transfer"><span class="icon">🔄</span>Internal</a>
        <a href="/mobile/external_transfer"><span class="icon">🏦</span>Other Bank/Wallet</a>
        <a href="/mobile/pay_bills"><span class="icon">🛒</span>Bittaa/Bill</a>
        <a href="/mobile/statement"><span class="icon">📜</span>History</a>
    </div>
    {% endif %}
</body>
</html>
"""

# ==========================================
# 1. IMPORTING EXISTING CUSTOMERS (CSV)
# ==========================================

@app.route('/import_customers_csv', methods=['GET', 'POST'])
def import_customers_csv():
    if 'role' not in session or session['role'] not in ['CEO', 'MANAGER', 'MAKER']:
        return redirect('/login')

    msg = None
    msg_type = "green"

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            msg = "❌ Failiin CSV hin filatamne!"
            msg_type = "red"
        else:
            file = request.files['csv_file']
            if file.filename == '' or not file.filename.endswith('.csv'):
                msg = "❌ Maaloo failii CSV sirrii ta'e qofa fe'aa!"
                msg_type = "red"
            else:
                try:
                    stream = StringIO(file.stream.read().decode("UTF-8"), newline=None)
                    csv_reader = csv.DictReader(stream)
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    imported_count = 0
                    
                    for row in csv_reader:
                        cust_id = row.get('customer_id', '').strip()
                        full_name = row.get('full_name', '').strip()
                        phone = row.get('phone', '').strip()
                        gender = row.get('gender', 'Dhiira').strip()
                        acc_type = row.get('account_type', 'WADIA').strip()
                        balance = float(row.get('balance', 0.0))
                        pin = row.get('pin', '1234').strip()
                        status = row.get('status', 'ACTIVE').strip()
                        created_at = row.get('created_at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                        if cust_id and full_name:
                            cursor.execute("""
                                INSERT INTO customers (customer_id, full_name, phone, gender, account_type, balance, status, pin, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(customer_id) DO UPDATE SET
                                full_name=excluded.full_name,
                                phone=excluded.phone,
                                balance=excluded.balance,
                                pin=excluded.pin,
                                status=excluded.status
                            """, (cust_id, full_name, phone, gender, acc_type, balance, status, pin, created_at))
                            imported_count += 1

                    conn.commit()
                    conn.close()
                    msg = f"✅ Maammiltoonni {imported_count} milkaa'inaan gara Database ('web_banking.db') galfamiiru!"
                    add_notification(f"CSV Import: Maammiltoota {imported_count} galfaman.")
                except Exception as e:
                    msg = f"❌ Sodalamaa komputaraa: {str(e)}"
                    msg_type = "red"

    content = f"""
    <div class="box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:8px;">📥 Maammiltoota Duraanii CSV'n Galchuu</h2>
        <p style="font-size:12px; color:#64748b; margin-bottom:16px;">Failii CSV `existing_customers.csv` jedhamu ol fe'uudhaan maammiltoota duraanii database wajjin walqabsiisaa.</p>

        {f'<p style="background:{"#dcfce7" if msg_type=="green" else "#fee2e2"}; color:{"#166534" if msg_type=="green" else "#991b1b"}; padding:10px; border-radius:8px; font-size:12px; font-weight:bold; margin-bottom:12px;">{msg}</p>' if msg else ''}

        <form method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label>Failii CSV Filadhaa (.csv)</label>
                <input type="file" name="csv_file" accept=".csv" class="input-field" required>
            </div>
            <button type="submit" class="btn-submit">🚀 Deetaa Import Godhi</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

# ==========================================
# 2. OTHER BANK & WALLET TRANSFERS
# ==========================================

@app.route('/mobile/external_transfer', methods=['GET', 'POST'])
def mobile_external_transfer():
    if not session.get('is_customer'):
        return redirect('/mobile/login')

    msg = None
    msg_type = "green"
    cust_id = session['customer_id']

    if request.method == 'POST':
        destination_type = request.form.get('destination_type', '').strip()
        target_account = request.form.get('target_account', '').strip()
        amount = float(request.form.get('amount', 0.0))
        pin = request.form.get('pin', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, pin, freeze_status FROM customers WHERE customer_id = ?", (cust_id,))
        sender = cursor.fetchone()

        service_fee = 5.0
        total_deduction = amount + service_fee

        if sender['pin'] != pin:
            msg = "❌ PIN Dogoggoraa!"
            msg_type = "red"
        elif sender['freeze_status'] == 'FROZEN':
            msg = "🔒 Akkaawunttii keessan Uggurameera!"
            msg_type = "red"
        elif amount <= 0:
            msg = "❌ Hamma maallaqaa sirrii galchaa!"
            msg_type = "red"
        elif sender['balance'] < total_deduction:
            msg = f"❌ Balansii gahaa hin qabdan! (Kaffaltii tajaajilaa Birr {service_fee} waliin: Birr {total_deduction:,.2f} barbaachisa)"
            msg_type = "red"
        else:
            timestamp_str = int(datetime.datetime.now().timestamp())
            ft_ref = f"EXT{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("UPDATE customers SET balance = balance - ? WHERE customer_id = ?", (total_deduction, cust_id))

            cursor.execute("""
                INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, target_account, amount, commission, bank_name, ft_reference, status, created_by, timestamp)
                VALUES (?, 'WALLET_TRANSFER', ?, ?, ?, ?, ?, ?, ?, 'APPROVED', 'MOBILE_APP', ?)
            """, (f"TXN-EXT-{timestamp_str}", cust_id, session['customer_name'], target_account, amount, service_fee, destination_type, ft_ref, now))

            conn.commit()
            msg = f"✅ Birr {amount:,.2f} gara {destination_type} ({target_account}) milkaa'inaan ergameera! (Ref: {ft_ref})"
            add_notification(f"External Transfer: {cust_id} -> {destination_type} ({amount} Birr)")

        conn.close()

    content = f"""
    <div class="m-box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">🏦 Baankii Biraa & Wallet tti Ergi</h2>
        {f'<p style="background:{"#dcfce7" if msg_type=="green" else "#fee2e2"}; color:{"#166534" if msg_type=="green" else "#991b1b"}; padding:10px; border-radius:8px; font-size:12px; font-weight:bold; margin-bottom:12px;">{msg}</p>' if msg else ''}

        <form method="POST">
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Bakka Maallaqni Ergamu (Destination)</label>
                <select name="destination_type" class="m-input" required>
                    <option value="Telebirr">📱 Telebirr (Ethio Telecom)</option>
                    <option value="CBE Birr">🏦 CBE Birr</option>
                    <option value="eBirr">📲 eBirr Wallet</option>
                    <option value="Commercial Bank of Ethiopia (CBE)">🏦 Commercial Bank of Ethiopia (CBE)</option>
                    <option value="Awash Bank">🏦 Awash Bank</option>
                    <option value="Cooperative Bank of Oromia">🏦 Cooperative Bank of Oromia (Coop)</option>
                    <option value="Dashen Bank">🏦 Dashen Bank</option>
                </select>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Lakk. Account / Bilbila Fudhattuu</label>
                <input type="text" name="target_account" placeholder="Fkn: 0911... ykn Lakk. Acc CBE" class="m-input" required>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Hamma Qarshii (Birr)</label>
                <input type="number" step="0.01" min="1" name="amount" placeholder="0.00" class="m-input" required>
                <p style="font-size:10px; color:#64748b; margin-top:2px;">* Kaffaltii Tajaajila Gateway: Birr 5.00</p>
            </div>
            <div style="margin-bottom:16px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">PIN Keessan Galchaa</label>
                <input type="password" maxlength="4" name="pin" placeholder="****" class="m-input" style="text-align:center; letter-spacing:4px;" required>
            </div>
            <button type="submit" class="m-btn">🚀 Maallaqa Ergi</button>
        </form>
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

# ==========================================
# 3. SHOPPING & BILL PAYMENTS
# ==========================================

@app.route('/mobile/pay_bills', methods=['GET', 'POST'])
def mobile_pay_bills():
    if not session.get('is_customer'):
        return redirect('/mobile/login')

    msg = None
    msg_type = "green"
    cust_id = session['customer_id']

    if request.method == 'POST':
        bill_type = request.form.get('bill_type', '').strip()
        bill_reference = request.form.get('bill_reference', '').strip()
        amount = float(request.form.get('amount', 0.0))
        pin = request.form.get('pin', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, pin, freeze_status FROM customers WHERE customer_id = ?", (cust_id,))
        sender = cursor.fetchone()

        if sender['pin'] != pin:
            msg = "❌ PIN Dogoggoraa!"
            msg_type = "red"
        elif sender['freeze_status'] == 'FROZEN':
            msg = "🔒 Akkaawunttii keessan Uggurameera!"
            msg_type = "red"
        elif amount <= 0:
            msg = "❌ Hamma maallaqaa sirrii galchaa!"
            msg_type = "red"
        elif sender['balance'] < amount:
            msg = f"❌ Balansii gahaa hin qabdan! (Jiru: {sender['balance']:,.2f} Birr)"
            msg_type = "red"
        else:
            timestamp_str = int(datetime.datetime.now().timestamp())
            ft_ref = f"PAY{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("UPDATE customers SET balance = balance - ? WHERE customer_id = ?", (amount, cust_id))

            cursor.execute("""
                INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, target_account, amount, commission, bank_name, ft_reference, status, created_by, timestamp)
                VALUES (?, 'BILL_PAYMENT', ?, ?, ?, ?, 0.0, ?, ?, 'APPROVED', 'MOBILE_APP', ?)
            """, (f"TXN-BILL-{timestamp_str}", cust_id, session['customer_name'], bill_reference, amount, bill_type, ft_ref, now))

            conn.commit()
            msg = f"✅ Bittaa / Kaffaltii {bill_type} (Birr {amount:,.2f}) milkaa'inaan raawwatameera! (Ref: {ft_ref})"
            add_notification(f"Bill Payment: {cust_id} -> {bill_type} ({amount} Birr)")

        conn.close()

    content = f"""
    <div class="m-box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">🛒 Bittaa Garaagaraa & Kaffaltii (Bill Pay)</h2>
        {f'<p style="background:{"#dcfce7" if msg_type=="green" else "#fee2e2"}; color:{"#166534" if msg_type=="green" else "#991b1b"}; padding:10px; border-radius:8px; font-size:12px; font-weight:bold; margin-bottom:12px;">{msg}</p>' if msg else ''}

        <form method="POST">
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Gosa Bittaa / Kaffaltii</label>
                <select name="bill_type" class="m-input" required>
                    <option value="Airtime Topup">📱 Kardii Bilbilaa (Ethio Telecom Airtime)</option>
                    <option value="Ethio Telecom Bill">📞 Kaffaltii Postpaid Ethio Telecom</option>
                    <option value="Electricity Bill">⚡ Kaffaltii Ilectricii (EEU)</option>
                    <option value="Water Bill">🚰 Kaffaltii Bishaanii</option>
                    <option value="Merchant Till Payment">🏪 Bittaa Dukaanaa (Merchant Till No)</option>
                </select>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Lakk. Bilbilaa / Lakk. Till / Meter ID</label>
                <input type="text" name="bill_reference" placeholder="Fkn: 0911... ykn Lakk. Till Dukaanaa" class="m-input" required>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Hamma Qarshii (Birr)</label>
                <input type="number" step="0.01" min="1" name="amount" placeholder="0.00" class="m-input" required>
            </div>
            <div style="margin-bottom:16px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">PIN Keessan Galchaa</label>
                <input type="password" maxlength="4" name="pin" placeholder="****" class="m-input" style="text-align:center; letter-spacing:4px;" required>
            </div>
            <button type="submit" class="m-btn">💳 Kaffaltii Raawwadhu</button>
        </form>
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

# ==========================================
# STANDARD MOBILE ROUTES
# ==========================================

@app.route('/mobile/login', methods=['GET', 'POST'])
def mobile_login():
    error = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        pin = request.form.get('pin', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT customer_id, full_name, phone, balance, status, freeze_status, pin 
            FROM customers 
            WHERE (customer_id = ? OR phone = ?) AND pin = ?
        """, (identifier, identifier, pin))
        cust = cursor.fetchone()
        conn.close()

        if cust:
            if cust['status'] != 'ACTIVE':
                error = "Akkaawunttii keessan Mirkanaa'a jira (Pending Approval)."
            elif cust['freeze_status'] == 'FROZEN':
                error = "🔒 Akkaawunttii keessan Uggurameera!"
            else:
                session['is_customer'] = True
                session['customer_id'] = cust['customer_id']
                session['customer_name'] = cust['full_name']
                session['customer_phone'] = cust['phone']
                return redirect('/mobile/dashboard')
        else:
            error = "Lakkoofsa Bilbilaa/ID ykn PIN dogoggoraa!"

    content = f"""
    <div class="m-box" style="margin-top: 20px; text-align: center;">
        <div style="font-size: 42px; margin-bottom: 8px;">🏦</div>
        <h2 style="color:#065f46; font-size:18px;">IMANA Mobile Banking</h2>
        <p style="font-size:12px; color:#64748b; margin-bottom:16px;">Seensa Mobile Banking Maammilaa</p>

        {f'<p style="color:#dc2626; font-size:12px; font-weight:bold; margin-bottom:12px; background:#fee2e2; padding:8px; border-radius:8px;">{error}</p>' if error else ''}

        <form method="POST" style="text-align:left;">
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Lakk. Bilbilaa ykn ID Maammilaa</label>
                <input type="text" name="identifier" placeholder="Fkn: 100099008801" class="m-input" required>
            </div>
            <div style="margin-bottom:16px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">PIN Lakkoofsa 4</label>
                <input type="password" maxlength="4" name="pin" placeholder="****" class="m-input" style="letter-spacing:4px; font-size:18px; text-align:center;" required>
            </div>
            <button type="submit" class="m-btn">Seeni (Login)</button>
        </form>
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/mobile/dashboard')
def mobile_dashboard():
    if not session.get('is_customer'):
        return redirect('/mobile/login')

    cust_id = session['customer_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, balance, account_type FROM customers WHERE customer_id = ?", (cust_id,))
    cust = cursor.fetchone()

    cursor.execute("""
        SELECT txn_type, amount, timestamp, ft_reference 
        FROM transactions 
        WHERE (customer_id = ? OR target_account = ?) AND status = 'APPROVED' 
        ORDER BY timestamp DESC LIMIT 5
    """, (cust_id, cust_id))
    recent_txns = cursor.fetchall()
    conn.close()

    txns_html = ""
    for t in recent_txns:
        is_credit = t['txn_type'] == 'DEPOSIT' or (t['txn_type'] == 'T24_TRANSFER' and t['target_account'] == cust_id)
        color = "#16a34a" if is_credit else "#dc2626"
        sign = "+" if is_credit else "-"
        txns_html += f"""
        <div class="m-txn-item">
            <div>
                <b>{t['txn_type']}</b><br>
                <span style="font-size:10px; color:#64748b;">{t['timestamp']}</span>
            </div>
            <div style="font-weight:bold; color:{color}; text-align:right;">
                {sign}{t['amount']:,.2f} Birr<br>
                <span style="font-size:9px; color:#94a3b8;">{t['ft_reference']}</span>
            </div>
        </div>
        """

    empty_txn_msg = '<p style="font-size:12px; color:#94a3b8; text-align:center;">Socho\'iinsi raawwatame hin jiru.</p>'

    content = f"""
    <div class="balance-card">
        <div class="balance-label">Haftee Qarshii (Available Balance)</div>
        <div class="balance-val">{cust['balance']:,.2f} Birr</div>
        <div class="acc-number">Acc: {cust['customer_id']} ({cust['account_type']})</div>
    </div>

    <div class="quick-actions">
        <a href="/mobile/transfer" class="action-btn"><span class="icon">🔄</span><span>Internal Transfer</span></a>
        <a href="/mobile/external_transfer" class="action-btn"><span class="icon">🏦</span><span>Other Bank/Wallet</span></a>
        <a href="/mobile/pay_bills" class="action-btn"><span class="icon">🛒</span><span>Bittaa & Bills</span></a>
        <a href="/mobile/statement" class="action-btn"><span class="icon">📜</span><span>Mini Statement</span></a>
    </div>

    <div class="m-box">
        <h3 style="font-size:14px; color:#065f46; margin-bottom:10px;">🕒 Socho'iinsa Dhiyootti</h3>
        {txns_html if txns_html else empty_txn_msg}
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/mobile/transfer', methods=['GET', 'POST'])
def mobile_transfer():
    if not session.get('is_customer'):
        return redirect('/mobile/login')

    msg = None
    msg_type = "green"
    cust_id = session['customer_id']

    if request.method == 'POST':
        target_acc = request.form.get('target_account', '').strip()
        amount = float(request.form.get('amount', 0.0))
        pin = request.form.get('pin', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, pin, freeze_status FROM customers WHERE customer_id = ?", (cust_id,))
        sender = cursor.fetchone()

        cursor.execute("SELECT full_name, status FROM customers WHERE customer_id = ?", (target_acc,))
        receiver = cursor.fetchone()

        if sender['pin'] != pin:
            msg = "❌ PIN Dogoggoraa!"
            msg_type = "red"
        elif sender['freeze_status'] == 'FROZEN':
            msg = "🔒 Akkaawunttii keessan Uggurameera!"
            msg_type = "red"
        elif not receiver:
            msg = "❌ Lakk. Akkaawuntii Nama Fudhatuu Hin Argamne!"
            msg_type = "red"
        elif target_acc == cust_id:
            msg = "❌ Akkaawuntii mataa keessaniitti ergachuu hin dandeessan!"
            msg_type = "red"
        elif amount <= 0:
            msg = "❌ Hamma maallaqaa sirrii galchaa!"
            msg_type = "red"
        elif sender['balance'] < amount:
            msg = f"❌ Balansii gahaa hin qabdan! (Jiru: {sender['balance']:,.2f} Birr)"
            msg_type = "red"
        else:
            timestamp_str = int(datetime.datetime.now().timestamp())
            ft_ref = f"MOB{datetime.datetime.now().strftime('%y%j')}{random.randint(10000, 99999)}"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("UPDATE customers SET balance = balance - ? WHERE customer_id = ?", (amount, cust_id))
            cursor.execute("UPDATE customers SET balance = balance + ? WHERE customer_id = ?", (amount, target_acc))

            cursor.execute("""
                INSERT INTO transactions (txn_id, txn_type, customer_id, customer_name, target_account, amount, commission, bank_name, ft_reference, status, created_by, timestamp)
                VALUES (?, 'T24_TRANSFER', ?, ?, ?, ?, 0.0, 'Imana Mobile App', ?, 'APPROVED', 'MOBILE_APP', ?)
            """, (f"TXN-MOB-{timestamp_str}", cust_id, session['customer_name'], target_acc, amount, ft_ref, now))

            conn.commit()
            msg = f"✅ Birr {amount:,.2f} gara {receiver['full_name']} ({target_acc}) ergameera! (Ref: {ft_ref})"

        conn.close()

    content = f"""
    <div class="m-box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:12px;">💸 Qarshii Dabarsi (Internal Transfer)</h2>
        {f'<p style="background:{"#dcfce7" if msg_type=="green" else "#fee2e2"}; color:{"#166534" if msg_type=="green" else "#991b1b"}; padding:10px; border-radius:8px; font-size:12px; font-weight:bold; margin-bottom:12px;">{msg}</p>' if msg else ''}

        <form method="POST">
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Lakk. Akkaawuntii Nama Fudhatuu (Imana Acc)</label>
                <input type="text" name="target_account" placeholder="Fkn: 100099008801" class="m-input" required>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">Hamma Qarshii (Birr)</label>
                <input type="number" step="0.01" min="1" name="amount" placeholder="0.00" class="m-input" required>
            </div>
            <div style="margin-bottom:16px;">
                <label style="font-size:12px; font-weight:bold; color:#475569;">PIN Keessan Galchaa</label>
                <input type="password" maxlength="4" name="pin" placeholder="****" class="m-input" style="text-align:center; letter-spacing:4px;" required>
            </div>
            <button type="submit" class="m-btn">🚀 Dabarsi</button>
        </form>
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/mobile/statement')
def mobile_statement():
    if not session.get('is_customer'):
        return redirect('/mobile/login')

    cust_id = session['customer_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM customers WHERE customer_id = ?", (cust_id,))
    c = cursor.fetchone()

    cursor.execute("""
        SELECT txn_type, amount, timestamp, ft_reference, target_account, bank_name
        FROM transactions 
        WHERE (customer_id = ? OR target_account = ?) AND status = 'APPROVED'
        ORDER BY timestamp DESC
    """, (cust_id, cust_id))
    txns = cursor.fetchall()
    conn.close()

    txns_html = ""
    for t in txns:
        is_credit = t['txn_type'] == 'DEPOSIT' or (t['txn_type'] == 'T24_TRANSFER' and t['target_account'] == cust_id)
        color = "#16a34a" if is_credit else "#dc2626"
        sign = "+" if is_credit else "-"
        txns_html += f"""
        <div class="m-txn-item">
            <div>
                <b>{t['txn_type']}</b> ({t['bank_name'] or 'Internal'})<br>
                <span style="font-size:10px; color:#64748b;">Ref: {t['ft_reference']} | {t['timestamp']}</span>
            </div>
            <div style="font-weight:bold; color:{color}; text-align:right;">
                {sign}{t['amount']:,.2f} Birr
            </div>
        </div>
        """

    empty_stmt_msg = '<p style="font-size:12px; color:#94a3b8; text-align:center; padding:20px;">Socho\'iinsi raawwatame hin jiru.</p>'

    content = f"""
    <div class="m-box">
        <h2 style="font-size:16px; color:#065f46; margin-bottom:4px;">📜 Seenaa Herregaa (Mini Statement)</h2>
        <p style="font-size:12px; color:#64748b; margin-bottom:12px;">Haftee Amajji: <b>{c['balance']:,.2f} Birr</b></p>
        <div style="border-top:1px dashed #cbd5e1; padding-top:8px;">
            {txns_html if txns_html else empty_stmt_msg}
        </div>
    </div>
    """
    return render_template_string(MOBILE_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/mobile/logout')
def mobile_logout():
    session.clear()
    return redirect('/mobile/login')

# ==========================================
# STAFF SYSTEM ROUTES
# ==========================================

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
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect('/')
        else:
            error = "Username ykn Password dogoggoraa!"

    content = f"""
    <div class="box" style="margin-top: 30px; text-align: center;">
        <h2 style="font-size: 17px; margin-bottom: 4px; color:#065f46;">Imana Microfinance Staff Login</h2>
        {f'<p style="color:red; font-size:12px;">{error}</p>' if error else ''}
        <form method="POST">
            <div class="form-group" style="text-align:left;">
                <label>Username</label>
                <input type="text" name="username" class="input-field" required>
            </div>
            <div class="form-group" style="text-align:left;">
                <label>Password</label>
                <input type="password" name="password" class="input-field" required>
            </div>
            <button type="submit" class="btn-submit">Seeni</button>
        </form>
        <p style="margin-top:15px; font-size:12px;"><a href="/mobile/login" style="color:#047857; font-weight:bold;">📱 Mobile Banking Customer Login</a></p>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/')
def dashboard():
    if 'role' not in session:
        return redirect('/login')
    
    net_cap, deposits, withdraws, cust_bal, total_comm, mud_dep, mud_gross, mud_ceo, mud_cust = get_bank_capital()
    role = session['role']

    content = f"""
    <div class="card-net">
        <div class="net-title">Waliigala Kaabitaala Baankii (Net Capital)</div>
        <div class="net-amount">{net_cap:,.2f} Birr</div>
        <div class="net-grid">
            <div>📥 Deposit: <b>{deposits:,.2f} Birr</b></div>
            <div>📤 Withdraw/FT/Bills: <b>{withdraws:,.2f} Birr</b></div>
        </div>
    </div>

    <div class="grid-2">
        <a href="/import_customers_csv" class="btn-card"><span class="icon">📥</span><span>Import CSV Maammiltootaa</span></a>
        <a href="/customers" class="btn-card"><span class="icon">👥</span><span>Listii Maammiltootaa</span></a>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)

@app.route('/customers')
def customers_list():
    if 'role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, full_name, phone, account_type, balance, status, pin FROM customers ORDER BY created_at DESC")
    custs = cursor.fetchall()
    conn.close()

    cust_rows = ""
    for c in custs:
        cust_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; font-size: 12px;">
            <td style="padding: 8px;"><b>{c['customer_id']}</b></td>
            <td style="padding: 8px;">{c['full_name']}</td>
            <td style="padding: 8px;">{c['phone']}</td>
            <td style="padding: 8px;">{c['account_type']}</td>
            <td style="padding: 8px; font-weight:bold; color:#047857;">{c['balance']:,.2f} Birr</td>
            <td style="padding: 8px;">PIN: <b>{c['pin']}</b></td>
        </tr>
        """

    no_cust_msg = '<tr><td colspan="6" style="padding:15px; text-align:center;">Maammilli galmaa\'e hin jiru.</td></tr>'

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 12px;">👥 Maammiltoota Database Keessa Jiran</h2>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="background: #f1f5f9; font-size: 12px; color: #475569;">
                        <th style="padding: 8px;">ID</th>
                        <th style="padding: 8px;">Maqaa</th>
                        <th style="padding: 8px;">Bilbila</th>
                        <th style="padding: 8px;">Gosa</th>
                        <th style="padding: 8px;">Balansii</th>
                        <th style="padding: 8px;">PIN</th>
                    </tr>
                </thead>
                <tbody>
                    {cust_rows if cust_rows else no_cust_msg}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
