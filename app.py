from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, qrcode, datetime, csv, io, os, base64

app = Flask(__name__)
app.secret_key = "secret123"

# Vercel Read-Only Filesystem Fix: Use /tmp for SQLite if root is not writable
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/attendance.db"
else:
    DB_PATH = "attendance.db"

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        username TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll TEXT,
        name TEXT,
        date TEXT,
        time TEXT
    )
    """)

    c.execute("INSERT OR IGNORE INTO admin VALUES('admin','admin123')")
    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    print(f"DB Init Error: {e}")

# ---------- INDEX (HOME PAGE) ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=? AND password=?", (u, p))
        if c.fetchone():
            session["admin"] = True
            return redirect("/admin")

    return render_template("index.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=? AND password=?", (u, p))
        if c.fetchone():
            session["admin"] = True
            return redirect("/admin")

    return render_template("login.html")

# ---------- ADMIN DASHBOARD ----------
@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/")
    return render_template("admin.html")

# ---------- GENERATE QR ----------
@app.route("/generate")
def generate():
    if "admin" not in session:
        return redirect("/")
    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=2)).strftime("%H:%M")
    url = f"{request.host_url}scan?exp={expiry}"

    # Generate QR in memory (Vercel cannot write to static/ folder)
    img = qrcode.make(url)
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_str = "data:image/png;base64," + base64.b64encode(img_io.getvalue()).decode()

    return render_template("admin.html", qr=True, qr_image=img_str, expiry=expiry)

# ---------- SCAN & MARK ----------
@app.route("/scan", methods=["GET", "POST"])
def scan():
    exp = request.args.get("exp")
    now = datetime.datetime.now().strftime("%H:%M")

    if exp and now > exp:
        return "QR Expired ❌"

    if request.method == "POST":
        roll = request.form["roll"]
        name = request.form["name"]
        date = datetime.date.today().isoformat()
        time = datetime.datetime.now().strftime("%H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT * FROM attendance WHERE roll=? AND date=?", (roll, date))
        if c.fetchone():
            return "Attendance Already Marked ⚠️"

        c.execute("INSERT INTO attendance VALUES(NULL,?,?,?,?)",
                  (roll, name, date, time))
        conn.commit()
        conn.close()

        return render_template("success.html")

    return render_template("scan.html")

# ---------- VIEW ----------
@app.route("/view")
def view():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    data = c.fetchall()
    conn.close()
    return render_template("view.html", data=data)

# ---------- EXPORT CSV ----------
@app.route("/export")
def export():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Roll", "Name", "Date", "Time"])
    writer.writerows(data)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="attendance.csv"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)