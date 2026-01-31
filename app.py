from flask import Flask, render_template, request, redirect, session
from functools import wraps
from datetime import datetime
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "srinivasa-secret"

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
        sadaram DOUBLE PRECISION,
        total_amount DOUBLE PRECISION,
        paid DOUBLE PRECISION,
        balance DOUBLE PRECISION
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

        if u == "maheshreddy" and p == "9440984550":
            session["role"] = "owner"
            return redirect("/dashboard")

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
        vehicle = request.form["vehicle"]
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
        INSERT INTO truck_sales(date, vehicle_no, buyer_name, labour_group_code,
                                sadaram, total_amount, paid, balance)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (date, vehicle, buyer, labour_code, sadaram, total, paid, balance))

        conn.commit()
        conn.close()

        return render_template("entry_success.html")

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
            INSERT INTO labour_payments VALUES (%s,%s,%s,%s)
        """, (date, labour, amount, ptype))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("pay_labour.html")


# ---------------- SALES REPORT (UPDATED) ----------------
@app.route("/sales-report")
@login_required
def sales_report():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT id, date, vehicle_no, buyer_name, labour_group_code,
               sadaram, total_amount, paid, balance
        FROM truck_sales
        ORDER BY date DESC
    """)

    rows = c.fetchall()
    conn.close()

    is_owner = session.get("role") == "owner"
    return render_template("sales_report.html", rows=rows, is_owner=is_owner)


# ---------------- CREDIT REPORT ----------------
@app.route("/credit-report")
@login_required
def credit_report():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT date, vehicle_no, buyer_name, balance
        FROM truck_sales
        WHERE balance > 0
        ORDER BY date ASC
    """)
    rows = c.fetchall()
    conn.close()

    return render_template("credit_report.html", rows=rows)


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


@app.route("/labour-details/<code>")
@login_required
def labour_details(code):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT date, vehicle_no, buyer_name, sadaram
        FROM truck_sales
        WHERE labour_group_code=%s
        ORDER BY date DESC
    """, (code,))

    rows = c.fetchall()
    conn.close()

    return render_template("labour_details.html", rows=rows)


# ---------------- OWNER EDIT / DELETE ----------------
@app.route("/edit-entry/<int:entry_id>", methods=["GET", "POST"])
@login_required
def edit_entry(entry_id):
    if session.get("role") != "owner":
        return redirect("/dashboard")

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        paid = float(request.form["paid"])

        c.execute("""
            UPDATE truck_sales
            SET paid=%s,
                balance = total_amount - %s
            WHERE id=%s
        """, (paid, paid, entry_id))

        conn.commit()
        conn.close()
        return redirect("/sales-report")

    c.execute("SELECT * FROM truck_sales WHERE id=%s", (entry_id,))
    row = c.fetchone()
    conn.close()

    return render_template("edit_entry.html", row=row)


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


# ---------------- PORT ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)