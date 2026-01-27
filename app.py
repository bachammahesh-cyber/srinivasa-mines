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


# ---------- LABOUR DASHBOARD ----------
@app.route("/labour-dashboard")
@login_required
def labour_dashboard():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT DISTINCT labour_group_code FROM truck_sales")
    groups = [g[0] for g in c.fetchall()]

    result = []

    for g in groups:
        # Work done
        c.execute("SELECT IFNULL(SUM(sadaram),0) FROM truck_sales WHERE labour_group_code=?", (g,))
        sadaram = c.fetchone()[0]

        # Advance taken
        c.execute("""
            SELECT IFNULL(SUM(amount),0)
            FROM labour_payments
            WHERE labour_group_code=? AND type='advance'
        """, (g,))
        advance = c.fetchone()[0]

        # Payments done
        c.execute("""
            SELECT IFNULL(SUM(amount),0)
            FROM labour_payments
            WHERE labour_group_code=? AND type='payment'
        """, (g,))
        payment = c.fetchone()[0]

        balance = sadaram - advance - payment

        result.append((g, sadaram, advance, payment, balance))

    conn.close()
    return render_template("labour_dashboard.html", rows=result)


if __name__ == "__main__":
    app.run(debug=True)