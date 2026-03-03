from flask import Flask, render_template, request, redirect, session
from functools import wraps
from datetime import datetime
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "srinivasa-secret"

# ---------- GLOBAL DATE FORMAT ----------
@app.template_filter('datefmt')
def format_date(value):
    if not value:
        return ""

    if isinstance(value, str):
        try:
            d = datetime.strptime(value, "%Y-%m-%d")
            return d.strftime("%d-%m-%y")
        except:
            return value

    try:
        return value.strftime("%d-%m-%y")
    except:
        return str(value)


# ---------------- DATABASE ----------------
def get_db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS truck_sales(
        id SERIAL PRIMARY KEY,
        date DATE,
        vehicle_no TEXT,
        buyer_name TEXT,
        labour_group_code TEXT,
        stone_size TEXT,
        pieces INTEGER,
        rate DOUBLE PRECISION,
        sadaram DOUBLE PRECISION,
        total_amount DOUBLE PRECISION,
        paid DOUBLE PRECISION,
        balance DOUBLE PRECISION,
        remarks TEXT
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS labour_payments(
        date DATE,
        labour_group_code TEXT,
        amount DOUBLE PRECISION,
        type TEXT
    );
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- LOGIN ----------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "role" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        # OWNER
        if u == "maheshreddy" and p == "9440984550":
            session["role"] = "owner"
            return redirect("/dashboard")

        # SUPERVISORS
        if u == "balesh" and p == "9010120863":
            session["role"] = "supervisor"
            return redirect("/dashboard")

        if u == "elisha" and p == "8096659221":
            session["role"] = "supervisor"
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- HOME ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("home.html")


# ---------------- TRUCK ENTRY ----------------
@app.route("/truck-entry", methods=["GET", "POST"])
@login_required
def truck_entry():
    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        labour_code = request.form["labour_code"]
        buyer = request.form["buyer"]
        stone_code = request.form["stone_code"]
        pieces = int(request.form["pieces"])
        rate = float(request.form["rate"])
        paid = float(request.form["paid"])

        stone_sizes = {
            "2x2": 4,
            "3x2": 6,
            "4x2": 8,
            "5x2": 10,
            "6x2": 12,
            "7x2": 14
        }

        feet = pieces * stone_sizes[stone_code]
        sadaram = (feet / 100) * 0.98
        total = sadaram * rate
        balance = total - paid
        date = datetime.now().date()

        c.execute("""
        INSERT INTO truck_sales(
            date, buyer_name, labour_group_code,
            stone_size, pieces, rate,
            sadaram, total_amount, paid, balance, remarks
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            date, buyer, labour_code,
            stone_code, pieces, rate,
            sadaram, total, paid, balance, ""
        ))

        conn.commit()
        conn.close()

        return render_template(
            "entry_success.html",
            invoice_amount=total
        )

    return render_template("truck_entry.html")


# ---------------- PAY LABOUR ----------------
@app.route("/pay-labour", methods=["GET", "POST"])
@login_required
def pay_labour():
    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        date = datetime.now().date()
        labour = request.form["labour"]
        amount = float(request.form["amount"])
        ptype = request.form["ptype"]

        c.execute("""
            INSERT INTO labour_payments (date, labour_group_code, amount, type)
            VALUES (%s,%s,%s,%s)
        """, (date, labour, amount, ptype))

        conn.commit()
        conn.close()

        return redirect("/labour-dashboard")

    return render_template("pay_labour.html")


# ---------------- SALES REPORT ----------------
@app.route("/sales-report")
@login_required
def sales_report():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT id, date, buyer_name, labour_group_code,
               stone_size, pieces, rate,
               sadaram, total_amount, paid, balance
        FROM truck_sales
        ORDER BY date DESC
    """)

    rows = c.fetchall()
    conn.close()

    is_owner = session.get("role") == "owner"
    return render_template("sales_report.html", rows=rows, is_owner=is_owner)


# ---------------- CREDIT REPORT ----------------
@app.route("/credit-report", methods=["GET", "POST"])
@login_required
def credit_report():
    conn = get_db()
    c = conn.cursor()

    # -------- HANDLE PAYMENT --------
    if request.method == "POST" and session.get("role") == "owner":
        entry_id = int(request.form["entry_id"])
        amount = float(request.form["amount"])

        # Get current balance
        c.execute("SELECT balance FROM truck_sales WHERE id=%s", (entry_id,))
        result = c.fetchone()

        if result:
            current_balance = result[0]
            deduction = min(current_balance, amount)

            c.execute("""
                UPDATE truck_sales
                SET paid = paid + %s,
                    balance = balance - %s
                WHERE id=%s
            """, (deduction, deduction, entry_id))

            conn.commit()

    # -------- FETCH CREDIT ROWS --------
    c.execute("""
        SELECT id, date, buyer_name, balance
        FROM truck_sales
        WHERE balance > 0
        ORDER BY date ASC
    """)
    rows = c.fetchall()

    # -------- CALCULATE TOTAL DUE (DATABASE SIDE - BEST METHOD) --------
    c.execute("SELECT SUM(balance) FROM truck_sales WHERE balance > 0")
    total_due_result = c.fetchone()
    total_due = total_due_result[0] if total_due_result[0] else 0

    conn.close()

    is_owner = session.get("role") == "owner"

    return render_template(
        "credit_report.html",
        rows=rows,
        is_owner=is_owner,
        total_due=total_due
    )

# ---------------- DELETE CREDIT ENTRY ----------------
@app.route("/delete-credit/<int:entry_id>")
@login_required
def delete_credit(entry_id):
    if session.get("role") != "owner":
        return redirect("/credit-report")

    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM truck_sales WHERE id=%s", (entry_id,))

    conn.commit()
    conn.close()

    return redirect("/credit-report")

# ---------------- MANUAL CREDIT ENTRY ----------------
@app.route("/manual-credit-entry", methods=["GET", "POST"])
@login_required
def manual_credit_entry():
    if session.get("role") != "owner":
        return redirect("/credit-report")

    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        buyer = request.form["buyer"]
        amount = float(request.form["amount"])
        remarks = request.form.get("remarks", "")

        date = datetime.now().date()

        # Manual credit entry (no labour, no stones)
        c.execute("""
        INSERT INTO truck_sales(
            date, buyer_name, labour_group_code,
            stone_size, pieces, rate,
            sadaram, total_amount, paid, balance, remarks
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            date, buyer, "MANUAL",
            "", 0, 0,
            0, amount, 0, amount, remarks
        ))

        conn.commit()
        conn.close()

        return redirect("/credit-report")

    return render_template("manual_credit_entry.html")


# ---------------- LABOUR DASHBOARD ----------------
@app.route("/labour-dashboard")
@login_required
def labour_dashboard():
    conn = get_db()
    c = conn.cursor()

    groups = {
        "SV": "SIVANNA",
        "LK": "LAKSHMANNA",
        "KD": "KONDAYYA",
        "KP": "KUPENDRA"
    }

    colors = {
        "SV": "#2563eb",
        "LK": "#16a34a",
        "KD": "#ea580c",
        "KP": "#db2777"
    }

    groups_list = []

    for code, name in groups.items():
        c.execute("""
            SELECT COALESCE(SUM(sadaram),0)
            FROM truck_sales
            WHERE labour_group_code=%s
        """, (code,))
        sadaram = c.fetchone()[0]

        c.execute("""
            SELECT COALESCE(SUM(amount),0)
            FROM labour_payments
            WHERE labour_group_code=%s AND type='advance'
        """, (code,))
        advance = c.fetchone()[0]

        groups_list.append({
            "code": code,
            "name": name,
            "sadaram": sadaram,
            "advance": advance,
            "color": colors[code]
        })

    conn.close()
    return render_template("labour_dashboard.html", groups=groups_list)


# ---------------- FULL EDIT ENTRY ----------------
@app.route("/edit-entry/<int:entry_id>", methods=["GET", "POST"])
@login_required
def edit_entry(entry_id):
    if session.get("role") != "owner":
        return redirect("/dashboard")

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        date = request.form["date"]
        buyer = request.form["buyer"]
        labour = request.form["labour"]
        stone_size = request.form["stone_size"]
        pieces = int(request.form["pieces"])
        rate = float(request.form["rate"])
        paid = float(request.form["paid"])

        stone_sizes = {
            "2x2": 4,
            "3x2": 6,
            "4x2": 8,
            "5x2": 10,
            "6x2": 12,
            "7x2": 14
        }

        feet = pieces * stone_sizes.get(stone_size, 0)
        sadaram = (feet / 100) * 0.98
        total = sadaram * rate
        balance = total - paid

        c.execute("""
            UPDATE truck_sales
            SET date=%s,
                buyer_name=%s,
                labour_group_code=%s,
                stone_size=%s,
                pieces=%s,
                rate=%s,
                sadaram=%s,
                total_amount=%s,
                paid=%s,
                balance=%s
            WHERE id=%s
        """, (
            date, buyer, labour, stone_size,
            pieces, rate,
            sadaram, total,
            paid, balance,
            entry_id
        ))

        conn.commit()
        conn.close()

        return redirect("/sales-report")

    # GET request → load existing data
    c.execute("""
        SELECT id, date, buyer_name, labour_group_code,
               stone_size, pieces, rate, paid
        FROM truck_sales
        WHERE id=%s
    """, (entry_id,))
    row = c.fetchone()

    conn.close()

    return render_template("edit_entry.html", row=row)


# ---------------- DELETE ENTRY ----------------
@app.route("/delete-entry/<int:entry_id>")
@login_required
def delete_entry(entry_id):
    if session.get("role") != "owner":
        return redirect("/dashboard")

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM truck_sales WHERE id=%s", (entry_id,))
    conn.commit()
    conn.close()

    return redirect("/sales-report")

