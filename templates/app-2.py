from flask import Flask, render_template, request, redirect, url_for, session
import os, secrets, requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
verification_codes = {}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return "Please enter a valid email address.", 400
    code = f"{secrets.randbelow(10000):04d}"
    verification_codes[email] = code
    session["signup_email"] = email
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return "RESEND_API_KEY is not configured.", 500
    r = requests.post("https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}", "Content-Type":"application/json"},
        json={"from":"Yobi1 <onboarding@resend.dev>","to":[email],
              "subject":"Your Yobi1 verification code",
              "html":f"<h2>Yobi1 verification</h2><p>Your verification code is <strong>{code}</strong>.</p><p>Do not share this code with any person or application.</p>"},
        timeout=15)
    if not r.ok:
        return "Yobi1 could not send the verification email yet.", 502
    return redirect(url_for("verify"))

@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("signup_email")
    if not email:
        return redirect(url_for("signup"))
    if request.method == "POST":
        entered = request.form.get("code", "").strip()
        if verification_codes.get(email) == entered:
            verification_codes.pop(email, None)
            return "Email verified! Waiting for administrator approval."
        return "Incorrect verification code.", 400
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Verify | Yobi1</title></head>
<body style="font-family:Arial;text-align:center;padding:50px"><h1>Yobi1</h1><h2>Verify your email</h2>
<p>Enter the 4-digit code sent to {email}.</p><form method="post">
<input name="code" inputmode="numeric" maxlength="4" pattern="[0-9]{{4}}" placeholder="0000" required style="font-size:24px;text-align:center;padding:12px;width:160px"><br><br>
<button type="submit" style="padding:12px 30px">Verify</button></form></body></html>"""

@app.route("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
