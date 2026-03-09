from flask import Flask, render_template, request, redirect, session, send_file
from functools import wraps
from datetime import datetime
from io import BytesIO
import os
import psycopg2
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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


def resolve_telugu_font():
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"
    candidates = [
        os.path.join("assets", "fonts", "NotoSansTelugu-Regular.ttf"),
        os.path.join("assets", "fonts", "NotoSansTelugu.ttf"),
        os.path.join("assets", "fonts", "Nirmala.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf",
        "/usr/share/fonts/noto/NotoSansTelugu-Regular.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                if "Telugu-Regular" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("Telugu-Regular", path))
                # Reuse the same unicode-capable font for bold text too.
                if "Telugu-Bold" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("Telugu-Bold", path))
                font_name = "Telugu-Regular"
                bold_font_name = "Telugu-Bold"
                break
            except Exception:
                continue

    return font_name, bold_font_name


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


# ---------------- LABOUR DETAILS ----------------
@app.route("/labour-details/<code>")
@login_required
def labour_details(code):
    valid_codes = {"SV", "LK", "KD", "KP"}
    code = code.upper()

    if code not in valid_codes:
        return redirect("/labour-dashboard")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT date, buyer_name, stone_size, sadaram
        FROM truck_sales
        WHERE labour_group_code=%s
        ORDER BY date DESC, id DESC
    """, (code,))
    rows = c.fetchall()
    conn.close()

    return render_template("labour_details.html", rows=rows)


# ---------------- LABOUR DETAILS PDF ----------------
@app.route("/labour-details/<code>/pdf")
@login_required
def labour_details_pdf(code):
    groups = {
        "SV": "SIVANNA",
        "LK": "LAKSHMANNA",
        "KD": "KONDAYYA",
        "KP": "KUPENDRA"
    }
    code = code.upper()

    if code not in groups:
        return redirect("/labour-dashboard")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT date, buyer_name, stone_size, sadaram
        FROM truck_sales
        WHERE labour_group_code=%s
        ORDER BY date DESC, id DESC
    """, (code,))
    rows = c.fetchall()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    body_font, heading_font = resolve_telugu_font()

    y = height - 40
    p.setFont(heading_font, 14)
    p.drawString(40, y, f"Labour Group Report - {groups[code]} ({code})")

    y -= 24
    p.setFont(body_font, 10)
    p.drawString(40, y, f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

    y -= 26
    p.setFont(heading_font, 10)
    p.drawString(40, y, "Date")
    p.drawString(150, y, "Buyer")
    p.drawString(380, y, "Stone")
    p.drawRightString(555, y, "Sadaram")

    y -= 10
    p.line(40, y, 555, y)
    y -= 16

    p.setFont(body_font, 10)
    total_sadaram = 0.0

    for r in rows:
        if y < 60:
            p.showPage()
            y = height - 40
            p.setFont(heading_font, 10)
            p.drawString(40, y, "Date")
            p.drawString(150, y, "Buyer")
            p.drawString(380, y, "Stone")
            p.drawRightString(555, y, "Sadaram")
            y -= 10
            p.line(40, y, 555, y)
            y -= 16
            p.setFont(body_font, 10)

        date_text = format_date(r[0])
        buyer = (r[1] or "")[:34]
        stone = (r[2] or "")[:10]
        sadaram = float(r[3] or 0)
        total_sadaram += sadaram

        p.drawString(40, y, date_text)
        p.drawString(150, y, buyer)
        p.drawString(380, y, stone)
        p.drawRightString(555, y, f"{sadaram:.3f}")
        y -= 16

    if y < 70:
        p.showPage()
        y = height - 60

    p.setFont(heading_font, 11)
    p.line(40, y, 555, y)
    y -= 18
    p.drawRightString(555, y, f"Total Sadaram: {total_sadaram:.3f}")

    p.save()
    buffer.seek(0)

    filename = f"labour_{code}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# ---------------- RESET LABOUR ADVANCE ----------------
@app.route("/reset-labour/<code>")
@login_required
def reset_labour(code):
    if session.get("role") != "owner":
        return redirect("/labour-dashboard")

    valid_codes = {"SV", "LK", "KD", "KP"}
    code = code.upper()

    if code not in valid_codes:
        return redirect("/labour-dashboard")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        DELETE FROM labour_payments
        WHERE labour_group_code=%s AND type='advance'
    """, (code,))
    conn.commit()
    conn.close()

    return redirect("/labour-dashboard")


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
