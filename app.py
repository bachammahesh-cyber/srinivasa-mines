from flask import Flask, render_template, request, redirect, session
from functools import wraps
import sqlite3
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = "srinivasa-secret"

DB_PATH = os.path.join(BASE_DIR, "quarry.db")


# ---------- DATABASE INIT ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS truck_sales(
        date TEXT,
        vehicle_no TEXT,
        buyer_name TEXT,
        labour_group_code TEXT,
        sadaram REAL,
        total_amount REAL,
        paid REAL,
        balance REAL
    );

    CREATE TABLE IF NOT EXISTS labour_payments(
        date TEXT,
        labour_group_code TEXT,
        amount REAL,
        type TEXT
    );
    """)

    conn.commit()
    conn.close()


init_db()


def get_db():
    return sqlite3.connect(DB_PATH)


# ---------- LOGIN PROTECTION ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "role" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper


# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "maheshreddy" and password == "9440984550":
            session["role"] = "owner"
            return redirect("/dashboard")

        if username == "balesh" and password == "9010120863":
            session["role"] = "supervisor"
            return redirect("/dashboard")

        if username == "elisha" and password == "8096659221":
            session["role"] = "supervisor"
            return redirect("/dashboard")

    return render_template("login.html")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("home.html")


# ---------- TRUCK ENTRY ----------
@app.route("/truck-entry", methods=["GET", "POST"])
@login_required
def truck_entry():
    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        # --------- FORM DATA ----------
        supervisor = request.form["supervisor"]
        labour_code = request.form["labour_code"]
        vehicle = request.form["vehicle"]
        buyer = request.form["buyer"]
        stone_code = request.form["stone_code"]
        pieces = int(request.form["pieces"])
        rate = float(request.form["rate"])
        paid = float(request.form["paid"])

        # --------- STONE SIZE MAP (feet per piece) ----------
        stone_sizes = {
            "2x2": 4,
            "3x2": 6,
            "4x2": 8,
            "5x2": 10,
            "6x2": 12,
            "7x2": 14
        }

        feet = pieces * stone_sizes[stone_code]

        # --------- 98 FEET RULE ----------
        feet = pieces * stone_sizes[stone_code]

        total_sadaram = feet / 100
        sadaram = total_sadaram * 0.98

        total = sadaram * rate
        balance = total - paid

        date = datetime.now().strftime("%Y-%m-%d")

        # --------- INSERT ----------
        c.execute("""
        INSERT INTO truck_sales VALUES (?,?,?,?,?,?,?,?)
        """, (date, vehicle, buyer, labour_code, sadaram, total, paid, balance))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("truck_entry.html")


# ---------- PAY LABOUR ----------
@app.route("/pay-labour", methods=["GET", "POST"])
@login_required
def pay_labour():
    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        date = datetime.now().strftime("%Y-%m-%d")
        labour = request.form["labour"]
        amount = float(request.form["amount"])
        ptype = request.form["ptype"]

        c.execute("""
        INSERT INTO labour_payments VALUES (?,?,?,?)
        """, (date, labour, amount, ptype))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("pay_labour.html")


# ---------- SALES REPORT ----------
@app.route("/sales-report")
@login_required
def sales_report():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM truck_sales ORDER BY date DESC")
    rows = c.fetchall()

    conn.close()
    return render_template("sales_report.html", rows=rows)


# ---------- CREDIT REPORT ----------
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


# ---------- LABOUR DASHBOARD ----------
@app.route("/labour-dashboard")
@login_required
def labour_dashboard():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT labour_group_code,
               IFNULL(SUM(sadaram),0)
        FROM truck_sales
        GROUP BY labour_group_code
    """)

    rows = c.fetchall()

    conn.close()
    return render_template("labour_dashboard.html", rows=rows)


if __name__ == "__main__":
    app.run(debug=True)