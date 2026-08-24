import sqlite3
from flask import Flask, render_template_string, request, redirect, session, url_for
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'imaanaa_secure_banking_key_2026'

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect('imaanaa_bank.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')
    
    # Customers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            gender TEXT,
            account_type TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT
        )
    ''')

    # Transactions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ft_reference TEXT UNIQUE,
            customer_id TEXT,
            customer_name TEXT,
            txn_type TEXT,
            amount REAL,
            commission REAL DEFAULT 0.0,
            status TEXT,
            created_by TEXT,
            timestamp TEXT
        )
    ''')

    # Default CEO account
    cursor.execute("SELECT * FROM users WHERE username = 'ceo'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role, status) VALUES ('ceo', 'ceo123', 'CEO', 'ACTIVE')")
        
    conn.commit()
    conn.close()

init_db()

# Global Notifications List (in-memory)
NOTIFICATIONS = []

def add_notification(msg):
    global NOTIFICATIONS
    timestamp = datetime.now().strftime("%H:%M:%S")
    NOTIFICATIONS.insert(0, f"[{timestamp}] {msg}")
    if len(NOTIFICATIONS) > 10:
        NOTIFICATIONS.pop()

# --- HTML LAYOUT TEMPLATE ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="om">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IMANA - Core Sharia Banking</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f1f5f9; margin: 0; padding: 0; color: #1e293b; }
        .navbar { background: #065f46; color: white; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .navbar h1 { margin: 0; font-size: 16px; font-weight: bold; letter-spacing: 0.5px; }
        .nav-links { display: flex; gap: 12px; align-items: center; font-size: 13px; }
        .nav-links a { color: white; text-decoration: none; padding: 4px 8px; border-radius: 4px; background: rgba(255,255,255,0.1); }
        .nav-links a:hover { background: rgba(255,255,255,0.2); }
        .container { max-width: 600px; margin: 16px auto; padding: 0 12px; }
        .box { background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 4px; color: #475569; }
        .input-field { width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
        .btn-submit { background: #065f46; color: white; border: none; padding: 10px; width: 100%; font-weight: bold; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .btn-submit:hover { background: #044e38; }
        .badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
        .badge-wadia { background: #e0f2fe; color: #0369a1; }
        .badge-active { background: #dcfce7; color: #166534; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .btn-action { padding: 4px 8px; border-radius: 4px; border: none; font-size: 11px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-green { background: #10b981; color: white; }
        .btn-red { background: #ef4444; color: white; }
        .btn-purple { background: #8b5cf6; color: white; }
        .card-ceo-profit { background: linear-gradient(135deg, #065f46, #047857); color: white; padding: 16px; border-radius: 8px; text-align: center; margin-bottom: 16px; }
        .net-amount { font-size: 24px; font-weight: bold; margin-top: 4px; }
        .notifications-ticker { background: #fef3c7; border: 1px solid #f59e0b; color: #92400e; padding: 8px 12px; border-radius: 6px; font-size: 11px; margin-bottom: 14px; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>☪️ IMANA MICROFINANCE</h1>
        <div class="nav-links">
            {"" if 'role' not in session else f"<span>👤 {{session['username']}} ({{session['role']}})</span>"}
            {"" if 'role' not in session else '<a href="/dashboard">🏠 Home</a>'}
            {"" if 'role' not in session else '<a href="/logout">🚪 Bai\'i</a>'}
        </div>
    </div>
    
    <div class="container">
        {% if notifications %}
        <div class="notifications-ticker">
            <b>🔔 Beeksisa Yeroo Ammaa:</b> {{ notifications[0] }}
        </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def index():
    if 'role' in session:
        return redirect('/dashboard')
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            if user['status'] == 'BLOCKED':
                msg = "🚫 Accountii keetu uggurameera (Blocked). Bulchaa qunnami."
            else:
                session['username'] = user['username']
                session['role'] = user['role']
                add_notification(f"Hojjataan {user['username']} seeneera.")
                return redirect('/dashboard')
        else:
            msg = "❌ Username ykn Password sirrii miti!"

    content = f"""
    <div class="box" style="max-width: 380px; margin: 40px auto;">
        <h2 style="text-align: center; color: #065f46; margin-bottom: 4px;">Seensa Hojjattootaa</h2>
        <p style="text-align: center; font-size: 11px; color: #64748b; margin-bottom: 16px;">Imana Core Banking System</p>
        
        {f"<p style='background:#fee2e2; color:#991b1b; padding:8px; border-radius:4px; font-size:12px; text-align:center;'>{msg}</p>" if msg else ""}
        
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required class="input-field" placeholder="Fkn: ceo, maker1">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required class="input-field" placeholder="••••••••">
            </div>
            <button type="submit" class="btn-submit">Seeni (Login)</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=[])


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/dashboard')
def dashboard():
    if 'role' not in session:
        return redirect('/login')

    role = session['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt, SUM(balance) as tot FROM customers WHERE status='ACTIVE'")
    res = cursor.fetchone()
    total_cust = res['cnt'] or 0
    total_deposits = res['tot'] or 0.0
    conn.close()

    actions_html = ""
    if role in ['MAKER', 'CEO']:
        actions_html += '<a href="/register_customer" class="btn-action btn-green" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">➕ Maammila Haaraa Galmeessi</a>'
        actions_html += '<a href="/deposit" class="btn-action btn-green" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">📥 Maallaqa Galchu (Deposit)</a>'
        actions_html += '<a href="/withdraw" class="btn-action btn-purple" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">📤 Maallaqa Baasuu (Withdrawal)</a>'
    
    actions_html += '<a href="/customers" class="btn-action btn-purple" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">👥 Listii Maammiltootaa & Barbaadi</a>'
    
    if role == 'CEO':
        actions_html += '<a href="/manage_users" class="btn-action btn-red" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">⚙️ Bulchiinsa Hojjattootaa (Users)</a>'
        actions_html += '<a href="/ceo_commission" class="btn-action btn-green" style="padding:10px; font-size:12px; text-align:center; display:block; margin-bottom:8px;">💰 Comishina Waliigalaa (CEO Commission)</a>'

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 4px;">📊 Dashboard Waliigalaa</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Baga nagaan dhuftan, shoora <b>{role}</b> tiin seenteerta.</p>
        
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:16px;">
            <div style="background:#f0fdf4; padding:12px; border-radius:6px; border:1px solid #bbf7d0;">
                <div style="font-size:11px; color:#166534; font-weight:bold;">Waliigala Maammiltoota</div>
                <div style="font-size:18px; font-weight:bold; color:#14532d; margin-top:2px;">{total_cust}</div>
            </div>
            <div style="background:#eff6ff; padding:12px; border-radius:6px; border:1px solid #bfdbfe;">
                <div style="font-size:11px; color:#1e40af; font-weight:bold;">Waliigala Balansii</div>
                <div style="font-size:16px; font-weight:bold; color:#1e3a8a; margin-top:2px;">{total_deposits:,.2f} Birr</div>
            </div>
        </div>

        <h3 style="font-size:13px; color:#1e293b; margin-bottom:8px;">🚀 Gochoota Saffisaa (Quick Actions)</h3>
        {actions_html}
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
    if 'role' not in session or session['role'] not in ['MAKER', 'CEO']:
        return "🚫 Hayyama Hin Qabdu!", 403

    msg = None
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        gender = request.form.get('gender')
        account_type = request.form.get('account_type')
        initial_deposit = float(request.form.get('initial_deposit', 0.0))

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate Customer ID (Fkn: IMA2026001)
        cursor.execute("SELECT COUNT(*) as cnt FROM customers")
        cnt = cursor.fetchone()['cnt'] + 1
        customer_id = f"IMA2026{cnt:03d}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute("""
                INSERT INTO customers (customer_id, full_name, phone, gender, account_type, balance, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """, (customer_id, full_name, phone, gender, account_type, initial_deposit, created_at))

            if initial_deposit > 0:
                ft_ref = f"FT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cursor.execute("""
                    INSERT INTO transactions (ft_reference, customer_id, customer_name, txn_type, amount, status, created_by, timestamp)
                    VALUES (?, ?, ?, 'DEPOSIT', ?, 'APPROVED', ?, ?)
                """, (ft_ref, customer_id, full_name, initial_deposit, session['username'], created_at))

            conn.commit()
            msg = f"✅ Maammilli milkaa'inaan galmeeffame! Acc ID: {customer_id}"
            add_notification(f"Maammila haaraa galmeesse: {full_name} ({customer_id})")
        except Exception as e:
            msg = f"❌ Dogoggora: {e}"
        finally:
            conn.close()

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 4px;">➕ Galmee Maammila Haaraa (Sharia-Compliant)</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Herrega Wadia ykn Mudarabah banuu.</p>
        
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST">
            <div class="form-group">
                <label>Maqaa Guutuu (Full Name)</label>
                <input type="text" name="full_name" required class="input-field" placeholder="Fkn: Ahmed Usmaan Ali">
            </div>
            <div class="form-group">
                <label>Lakkoofsa Bilbilaa (Phone)</label>
                <input type="text" name="phone" required class="input-field" placeholder="09xxxxxxxx">
            </div>
            <div class="form-group">
                <label>Saala (Gender)</label>
                <select name="gender" class="input-field">
                    <option value="Dhiira">Dhiira (Male)</option>
                    <option value="Dhalaa">Dhalaa (Female)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Gosa Herregaa (Account Type)</label>
                <select name="account_type" class="input-field">
                    <option value="WADIA_SAVINGS">Wadia Savings (Amantaan Kan Qabame - No Interest)</option>
                    <option value="MUDARABAH">Mudarabah (Profit-Sharing Investment)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Maallaqa Jalqabaa (Initial Deposit - Birr)</label>
                <input type="number" step="0.01" name="initial_deposit" value="0.00" class="input-field" required>
            </div>
            <button type="submit" class="btn-submit">Maammila Galmeessi</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'role' not in session or session['role'] not in ['MAKER', 'CEO']:
        return "🚫 Hayyama Hin Qabdu!", 403

    msg = None
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '').strip()
        amount = float(request.form.get('amount', 0.0))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE customer_id = ? AND status='ACTIVE'", (customer_id,))
        cust = cursor.fetchone()

        if cust and amount > 0:
            new_balance = cust['balance'] + amount
            cursor.execute("UPDATE customers SET balance = ? WHERE customer_id = ?", (new_balance, customer_id))
            
            ft_ref = f"FT{datetime.now().strftime('%Y%m%d%H%M%S')}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO transactions (ft_reference, customer_id, customer_name, txn_type, amount, status, created_by, timestamp)
                VALUES (?, ?, ?, 'DEPOSIT', ?, 'APPROVED', ?, ?)
            """, (ft_ref, customer_id, cust['full_name'], amount, session['username'], timestamp))
            
            conn.commit()
            conn.close()
            return redirect(f"/receipt/{cursor.lastrowid}")
        else:
            msg = "❌ Customer ID sirrii miti ykn maallaqni galche dogoggoraadha!"
            conn.close()

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 4px;">📥 Maallaqa Herrega Maammilaatti Galchuu (Deposit)</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Kaffaltii qulqulluu Sharia-compliant.</p>
        
        {f"<p style='background:#fee2e2; color:#991b1b; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST">
            <div class="form-group">
                <label>Customer ID</label>
                <input type="text" name="customer_id" required class="input-field" placeholder="Fkn: IMA2026001">
            </div>
            <div class="form-group">
                <label>Hamma Maallaqaa (Amount - Birr)</label>
                <input type="number" step="0.01" name="amount" required class="input-field" placeholder="0.00">
            </div>
            <button type="submit" class="btn-submit">Maallaqa Galchi & Nagahee Maxxansi</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'role' not in session or session['role'] not in ['MAKER', 'CEO']:
        return "🚫 Hayyama Hin Qabdu!", 403

    msg = None
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '').strip()
        amount = float(request.form.get('amount', 0.0))
        # Commission policy fkn 1% withdrawal service fee
        commission = amount * 0.01 
        total_deduction = amount + commission

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE customer_id = ? AND status='ACTIVE'", (customer_id,))
        cust = cursor.fetchone()

        if cust:
            if cust['balance'] >= total_deduction:
                new_balance = cust['balance'] - total_deduction
                cursor.execute("UPDATE customers SET balance = ? WHERE customer_id = ?", (new_balance, customer_id))
                
                ft_ref = f"FT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute("""
                    INSERT INTO transactions (ft_reference, customer_id, customer_name, txn_type, amount, commission, status, created_by, timestamp)
                    VALUES (?, ?, ?, 'WITHDRAWAL', ?, ?, 'APPROVED', ?, ?)
                """, (ft_ref, customer_id, cust['full_name'], amount, commission, session['username'], timestamp))
                
                conn.commit()
                conn.close()
                return redirect(f"/receipt/{cursor.lastrowid}")
            else:
                msg = f"❌ Balansiin maammilaas gahaa miti! (Barbaachisaa: {total_deduction:,.2f} Birr waliin)"
        else:
            msg = "❌ Customer ID hin argamne!"
        conn.close()

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 4px;">📤 Maallaqa Maammilaaf Baasuu (Withdrawal)</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Tajaajila baasii (Commission 1% dabalata ta'a).</p>
        
        {f"<p style='background:#fee2e2; color:#991b1b; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST">
            <div class="form-group">
                <label>Customer ID</label>
                <input type="text" name="customer_id" required class="input-field" placeholder="Fkn: IMA2026001">
            </div>
            <div class="form-group">
                <label>Hamma Maallaqaa Baasuuf (Amount - Birr)</label>
                <input type="number" step="0.01" name="amount" required class="input-field" placeholder="0.00">
            </div>
            <button type="submit" class="btn-submit" style="background:#7c3aed;">Maallaqa Baasi & Nagahee Fudhachuu</button>
        </form>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/statement/<customer_id>')
def statement(customer_id):
    if 'role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    cust = cursor.fetchone()

    if not cust:
        conn.close()
        return "Maammilli Hin Argamne", 404

    cursor.execute("SELECT * FROM transactions WHERE customer_id = ? ORDER BY txn_id DESC", (customer_id,))
    txns = cursor.fetchall()
    conn.close()

    txns_html = ""
    for t in txns:
        color = "#166534" if t['txn_type'] == 'DEPOSIT' else "#991b1b"
        txns_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
            <td style="padding:8px;">{t['timestamp']}</td>
            <td style="padding:8px; font-weight:bold; color:{color};">{t['txn_type']}</td>
            <td style="padding:8px;">{t['amount']:,.2f} Birr</td>
            <td style="padding:8px;">{t['ft_reference']}</td>
            <td style="padding:8px; text-align:right;"><a href="/receipt/{t['txn_id']}" class="btn-action btn-purple" style="font-size:10px;">Nagahee</a></td>
        </tr>
        """

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 2px;">📜 Statementi Herregaa: {cust['full_name']}</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 10px;">Acc ID: <b>{cust['customer_id']}</b> | Balansii Ammaa: <b style="color:#065f46;">{cust['balance']:,.2f} Birr</b></p>
    </div>

    <div class="box" style="padding:0; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Guyyaa / Saatii</th>
                    <th style="padding:8px;">Gosa Txn</th>
                    <th style="padding:8px;">Hamma</th>
                    <th style="padding:8px;">FT Ref</th>
                    <th style="padding:8px; text-align:right;">Action</th>
                </tr>
            </thead>
            <tbody>
                {txns_html if txns_html else '<tr><td colspan="5" style="text-align:center; padding:15px; font-size:12px; color:#64748b;">Transactions hin jiran.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/customers', methods=['GET', 'POST'])
def customers_list():
    if 'role' not in session:
        return redirect('/login')

    search_query = request.args.get('q', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST' and session.get('role') == 'CEO':
        action = request.form.get('action')
        target_cust = request.form.get('customer_id')
        if action == 'freeze':
            cursor.execute("UPDATE customers SET status = 'FROZEN' WHERE customer_id = ?", (target_cust,))
            conn.commit()
            add_notification(f"CEO maammila uggure (Frozen): {target_cust}")
        elif action == 'unfreeze':
            cursor.execute("UPDATE customers SET status = 'ACTIVE' WHERE customer_id = ?", (target_cust,))
            conn.commit()
            add_notification(f"CEO maammila deebisee active godhe: {target_cust}")

    if search_query:
        cursor.execute("""
            SELECT * FROM customers 
            WHERE customer_id LIKE ? OR full_name LIKE ? OR phone LIKE ?
            ORDER BY created_at DESC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM customers ORDER BY created_at DESC LIMIT 50")
    
    customers = cursor.fetchall()
    conn.close()

    cust_html = ""
    for r in customers:
        status_badge = "badge-active" if r['status'] == 'ACTIVE' else "badge-danger"
        edit_btn = ""
        ceo_freeze_form = ""
        
        if session.get('role') == 'CEO':
            if r['status'] == 'ACTIVE':
                ceo_freeze_form = f"""
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="freeze">
                    <input type="hidden" name="customer_id" value="{r['customer_id']}">
                    <button type="submit" class="btn-action btn-red">🔒 Freeze</button>
                </form>
                """
            else:
                ceo_freeze_form = f"""
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="unfreeze">
                    <input type="hidden" name="customer_id" value="{r['customer_id']}">
                    <button type="submit" class="btn-action btn-green">🔓 Unfreeze</button>
                </form>
                """

        cust_html += f"""
        <div class="box" style="margin-bottom:10px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-size:11px; font-weight:bold; color:#065f46;">{r['customer_id']}</span>
                <span class="badge {status_badge}">{r['status']}</span>
            </div>
            <div style="font-size:13px; font-weight:bold; margin-bottom:2px;">{r['full_name']} ({r['gender']})</div>
            <div style="font-size:11px; color:#475569; margin-bottom:4px;">Bilbila: <b>{r['phone']}</b> | Balansii: <b style="color:#065f46;">{r['balance']:,.2f} Birr</b></div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                <div>
                    <a href="/statement/{r['customer_id']}" class="btn-action btn-purple" style="font-size:10px;">📜 Statement</a>
                    {edit_btn}
                </div>
                <div>
                    {ceo_freeze_form}
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#065f46; margin-bottom: 8px;">👥 Listii Maammiltoota Baankii</h2>
        <form method="GET" style="display:flex; gap:8px; margin-bottom:4px;">
            <input type="text" name="q" value="{search_query}" placeholder="Maqaa, Bilbila ykn Acc ID..." class="input-field">
            <button type="submit" class="btn-submit" style="width:100px;">Barbaadi</button>
        </form>
    </div>
    {cust_html if cust_html else "<p style='text-align:center; padding:20px; color:#64748b; font-size:12px;'>Maammilli argame hin jiru.</p>"}
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/receipt/<txn_id>')
def receipt(txn_id):
    if 'role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, c.phone, c.gender, c.account_type 
        FROM transactions t
        LEFT JOIN customers c ON t.customer_id = c.customer_id
        WHERE t.txn_id = ?
    """, (txn_id,))
    t = cursor.fetchone()
    conn.close()

    if not t:
        return "Nagaheen Hin Argamne", 404

    return f"""
    <!DOCTYPE html>
    <html lang="om">
    <head>
        <meta charset="UTF-8">
        <title>Nagahee Kaffaltii - {t['ft_reference']}</title>
        <style>
            body {{ font-family: monospace; padding: 20px; max-width: 400px; margin: 0 auto; color: #000; }}
            .center {{ text-align: center; }}
            .line {{ border-bottom: 1px dashed #000; margin: 10px 0; }}
            .btn {{ background: #065f46; color: white; border: none; padding: 10px; width: 100%; font-weight: bold; cursor: pointer; margin-top: 20px; border-radius: 4px; }}
            @media print {{ .btn {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="center">
            <h3 style="margin:0;">IMANA FREE INTEREST MICROFINANCE</h3>
            <p style="font-size:11px; margin:4px 0;">Sharia-Compliant Core Banking Receipt</p>
            <p style="font-size:10px;">Ref: <b>{t['ft_reference']}</b></p>
        </div>
        <div class="line"></div>
        <div style="font-size: 12px; line-height: 1.6;">
            <div><b>Guyyaa:</b> {t['timestamp']}</div>
            <div><b>Gosa Txn:</b> {t['txn_type']}</div>
            <div><b>Maqaa Maammilaa:</b> {t['customer_name']}</div>
            <div><b>Acc ID:</b> {t['customer_id']}</div>
            <div><b>Hamma Maallaqaa:</b> {t['amount']:,.2f} Birr</div>
            {f"<div><b>Commission:</b> {t['commission']:,.2f} Birr</div>" if t['commission'] > 0 else ""}
            <div><b>Status:</b> {t['status']}</div>
            <div><b>Hojjataa (Maker):</b> {t['created_by']}</div>
        </div>
        <div class="line"></div>
        <div class="center" style="font-size: 11px;">
            <p>Galatoomaa! Imana Microfinance - Amanamummaa & Haqa.</p>
        </div>
        <button onclick="window.print()" class="btn">🖨️ Nagahee Maxxansi (Print Receipt)</button>
    </body>
    </html>
    """


@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Hayyama CEO Qofa!", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    msg = None
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'MAKER')
            
            try:
                cursor.execute("INSERT INTO users (username, password, role, status) VALUES (?, ?, ?, 'ACTIVE')", (username, password, role))
                conn.commit()
                msg = f"✅ Hojjataa haaraan ({username} - {role}) milkaa'inaan uumameera!"
                add_notification(f"CEO hojjataa haaraa uumee jira: {username}")
            except sqlite3.IntegrityError:
                msg = f"❌ Username '{username}' duraanuu jira!"
        
        elif action == 'toggle_status':
            target_user = request.form.get('username')
            new_status = request.form.get('new_status')
            cursor.execute("UPDATE users SET status = ? WHERE username = ?", (new_status, target_user))
            conn.commit()
            msg = f"✅ Status hojjataa '{target_user}' gara '{new_status}' jijjiirameera."

    cursor.execute("SELECT username, role, status FROM users")
    users = cursor.fetchall()
    conn.close()

    users_html = ""
    for u in users:
        status_badge = "badge-active" if u['status'] == 'ACTIVE' else "badge-danger"
        toggle_btn = ""
        if u['username'] != 'ceo':
            if u['status'] == 'ACTIVE':
                toggle_btn = f"""
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="toggle_status">
                    <input type="hidden" name="username" value="{u['username']}">
                    <input type="hidden" name="new_status" value="BLOCKED">
                    <button type="submit" class="btn-action btn-red" style="font-size:10px; padding:3px 6px;">🚫 Ugguri (Block)</button>
                </form>
                """
            else:
                toggle_btn = f"""
                <form method="POST" style="display:inline;">
                    <input type="hidden" name="action" value="toggle_status">
                    <input type="hidden" name="username" value="{u['username']}">
                    <input type="hidden" name="new_status" value="ACTIVE">
                    <button type="submit" class="btn-action btn-green" style="font-size:10px; padding:3px 6px;">✅ Deebisi (Active)</button>
                </form>
                """

        users_html += f"""
        <tr style="border-bottom:1px solid #e2e8f0; font-size:12px;">
            <td style="padding:8px; font-weight:bold;">{u['username']}</td>
            <td style="padding:8px;"><span class="badge badge-wadia">{u['role']}</span></td>
            <td style="padding:8px;"><span class="badge {status_badge}">{u['status']}</span></td>
            <td style="padding:8px; text-align:right;">{toggle_btn}</td>
        </tr>
        """

    content = f"""
    <div class="box">
        <h2 style="font-size: 16px; color:#581c87; margin-bottom: 4px;">⚙️ Bulchiinsa Hojjattoota Baankii (CEO Users Management)</h2>
        <p style="font-size: 11px; color:#64748b; margin-bottom: 14px;">Hojjattoota haaraa galmeessi ykn kan jiran ugguri/block godhi.</p>
        
        {f"<p style='background:#dcfce7; color:#166534; padding:10px; border-radius:6px; font-size:12px; font-weight:bold; margin-bottom:12px;'>{msg}</p>" if msg else ""}

        <form method="POST" style="background:#faf5ff; padding:12px; border-radius:8px; border:1px solid #e9d5ff; margin-bottom:16px;">
            <input type="hidden" name="action" value="create">
            <h3 style="font-size:12px; color:#581c87; margin-bottom:8px;">➕ Hojjataa Haaraa Dabaluu</h3>
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required class="input-field" placeholder="Fkn: maker2, officer2">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required class="input-field" placeholder="Password">
            </div>
            <div class="form-group">
                <label>Shoora (Role)</label>
                <select name="role" class="input-field">
                    <option value="MAKER">MAKER (Teller / Galmee & Transaction)</option>
                    <option value="MANAGER">MANAGER (Approval)</option>
                    <option value="AUDITOR">AUDITOR (EOD & Reversal Request)</option>
                    <option value="LOAN_OFFICER">LOAN_OFFICER (Islamic Financing)</option>
                </select>
            </div>
            <button type="submit" class="btn-submit" style="background:#7c3aed;">Hojjataa Galmeessi</button>
        </form>
    </div>

    <div class="box" style="padding:0; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left;">
            <thead>
                <tr style="background:#f8fafc; font-size:11px; color:#64748b; border-bottom:1px solid #e2e8f0;">
                    <th style="padding:8px;">Username</th>
                    <th style="padding:8px;">Shoora (Role)</th>
                    <th style="padding:8px;">Status</th>
                    <th style="padding:8px; text-align:right;">Action</th>
                </tr>
            </thead>
            <tbody>
                {users_html}
            </tbody>
        </table>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


@app.route('/ceo_commission')
def ceo_commission():
    if 'role' not in session or session['role'] != 'CEO':
        return "🚫 Hayyama CEO Qofa!", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(commission) as total_comm, COUNT(*) as count_txns 
        FROM transactions 
        WHERE status = 'APPROVED' AND commission > 0
    """)
    res = cursor.fetchone()
    conn.close()

    total_comm = res['total_comm'] or 0.0
    count_txns = res['count_txns'] or 0

    content = f"""
    <div class="card-ceo-profit">
        <div class="net-title">💰 Comishina Waliigala Baankii (Total Withdrawal Commissions)</div>
        <div class="net-amount">{total_comm:,.2f} Birr</div>
        <p style="font-size:11px; opacity:0.9; margin-top:4px;">Waliigala transaction {count_txns} irraa comishiniin argame</p>
    </div>
    """
    return render_template_string(HTML_LAYOUT.replace("{% block content %}{% endblock %}", content), notifications=NOTIFICATIONS)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
