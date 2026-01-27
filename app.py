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
            session["role"] = "BALESH"
            return redirect("/dashboard")

        if username == "elisha" and password == "8096659221":
            session["role"] = "ELISHA"
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


# ---------- TRUCK ENTRY WITH QUARRY RULES ----------
@app.route("/truck-entry", methods=["GET", "POST"])
@login_required
def truck_entry():
    if request.method == "POST":
        conn = get_db()
        c = conn.cursor()

        date = datetime.now().strftime("%Y-%m-%d")

        labour = request.form["labour"]
        supervisor = request.form["supervisor"]
        vehicle = request.form["vehicle"]
        buyer = request.form["buyer"]

        feet_per_piece = float(request.form["stone_size"])
        pieces = int(request.form["pieces"])
        rate = float(request.form["rate"])
        paid = float(request.form["paid"])

        # ✅ QUARRY CALCULATION
        total_feet = pieces * feet_per_piece
        payable_feet = total_feet * 0.98
        sadaram = payable_feet / 100
        total_amount = sadaram * rate
        balance = total_amount - paid

        c.execute("""
        INSERT INTO truck_sales
        (date, vehicle_no, buyer_name, labour_group_code, sadaram, total_amount, paid, balance)
        VALUES (?,?,?,?,?,?,?,?)
        """, (date, vehicle, buyer, labour, sadaram, total_amount, paid, balance))

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

        c.execute("""
        INSERT INTO labour_payments VALUES (?,?,?)
        """, (date, labour, amount))

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

    c.execute("SELECT DISTINCT labour_group_code FROM truck_sales")
    groups = [g[0] for g in c.fetchall()]

    result = []

    for g in groups:
        c.execute("SELECT IFNULL(SUM(sadaram),0) FROM truck_sales WHERE labour_group_code=?", (g,))
        sadaram = c.fetchone()[0]

        c.execute("SELECT IFNULL(SUM(amount),0) FROM labour_payments WHERE labour_group_code=?", (g,))
        paid = c.fetchone()[0]

        result.append((g, sadaram, paid))

    conn.close()
    return render_template("labour_dashboard.html", rows=result)


if __name__ == "__main__":
    app.run(debug=True)