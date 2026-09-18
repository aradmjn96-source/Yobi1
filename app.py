import os
import secrets
import html

import psycopg
import requests
from flask import Flask, render_template, request, redirect, url_for, session


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

verification_codes = {}


# ---------------- DATABASE ----------------

def get_db():
    return psycopg.connect(os.environ["DATABASE_URL"])


def create_tables():
    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name VARCHAR(40),
                    bio VARCHAR(160),
                    profile_image TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    sender_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    receiver_id INTEGER NOT NULL
                        REFERENCES users(id) ON DELETE CASCADE,
                    message VARCHAR(2000) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- SIGN UP ----------------

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

    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        return "Email service is not configured.", 500

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "Yobi1 <onboarding@resend.dev>",
                "to": [email],
                "subject": "Your Yobi1 verification code",
                "html": (
                    "<h2>Welcome to Yobi1</h2>"
                    f"<p>Your verification code is "
                    f"<strong>{code}</strong></p>"
                    "<p>Do not share this code with anyone.</p>"
                )
            },
            timeout=15
        )

    except requests.RequestException:
        return "Could not connect to the email service.", 502

    if not response.ok:
        return "Could not send the verification email.", 502

    return redirect(url_for("verify"))


# ---------------- VERIFY EMAIL ----------------

@app.route("/verify", methods=["GET", "POST"])
def verify():

    email = session.get("signup_email")

    if not email:
        return redirect(url_for("signup"))

    if request.method == "POST":

        entered_code = request.form.get("code", "").strip()

        if verification_codes.get(email) != entered_code:
            return "Incorrect verification code.", 400

        verification_codes.pop(email, None)

        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO users (email)
                    VALUES (%s)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id
                    """,
                    (email,)
                )

                result = cur.fetchone()

                if result:
                    user_id = result[0]

                else:
                    cur.execute(
                        "SELECT id FROM users WHERE email = %s",
                        (email,)
                    )

                    result = cur.fetchone()

                    if not result:
                        return "Could not create account.", 500

                    user_id = result[0]

        session["user_id"] = user_id

        return redirect(url_for("profile"))

    safe_email = html.escape(email)

    return f"""
    <!doctype html>

    <html>

    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>Verify | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:500px;
        margin:60px auto;
        padding:20px;
        text-align:center;
    ">

        <h1>Yobi1</h1>

        <h2>Verify your email</h2>

        <p>
            Enter the 4-digit code sent to
            {safe_email}
        </p>

        <form method="post">

            <input
                name="code"
                inputmode="numeric"
                maxlength="4"
                pattern="[0-9]{{4}}"
                placeholder="0000"
                required
                style="
                    font-size:24px;
                    width:130px;
                    padding:12px;
                    text-align:center;
                "
            >

            <br><br>

            <button
                type="submit"
                style="
                    padding:12px 25px;
                    font-size:16px;
                "
            >
                Verify
            </button>

        </form>

    </body>

    </html>
    """


# ---------------- CREATE PROFILE ----------------

@app.route("/profile", methods=["GET", "POST"])
def profile():

    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("signup"))

    if request.method == "POST":

        display_name = request.form.get(
            "display_name",
            ""
        ).strip()

        bio = request.form.get(
            "bio",
            ""
        ).strip()

        if not display_name:
            return "Please choose a display name.", 400

        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE users
                    SET
                        display_name = %s,
                        bio = %s
                    WHERE id = %s
                    """,
                    (
                        display_name[:40],
                        bio[:160],
                        user_id
                    )
                )

        return redirect(url_for("users"))

    return """
    <!doctype html>

    <html>

    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>Create Profile | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:500px;
        margin:50px auto;
        padding:20px;
    ">

        <h1 style="text-align:center;">
            Yobi1
        </h1>

        <h2 style="text-align:center;">
            Create your profile
        </h2>

        <form method="post">

            <label>
                Display name
            </label>

            <br>

            <input
                name="display_name"
                maxlength="40"
                placeholder="Your name"
                required
                style="
                    width:100%;
                    padding:12px;
                    margin-top:8px;
                "
            >

            <br><br>

            <label>
                Bio
            </label>

            <br>

            <textarea
                name="bio"
                maxlength="160"
                placeholder="Tell people about yourself..."
                style="
                    width:100%;
                    height:100px;
                    padding:12px;
                    margin-top:8px;
                "
            ></textarea>

            <br><br>

            <button
                type="submit"
                style="
                    width:100%;
                    padding:14px;
                    font-size:16px;
                "
            >
                Create profile
            </button>

        </form>

    </body>

    </html>
    """


# ---------------- USERS ----------------

@app.route("/users")
def users():

    my_id = session.get("user_id")

    if not my_id:
        return redirect(url_for("signup"))

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    display_name,
                    bio
                FROM users
                WHERE
                    id != %s
                    AND display_name IS NOT NULL
                ORDER BY display_name
                """,
                (my_id,)
            )

            people = cur.fetchall()

    page = """
    <!doctype html>

    <html>

    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>People | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:600px;
        margin:40px auto;
        padding:20px;
    ">

        <h1>Yobi1</h1>

        <h2>People</h2>
    """

    if not people:

        page += """
        <p>
            No other users yet.
        </p>
        """

    for person in people:

        user_id = person[0]
        display_name = html.escape(person[1] or "User")
        bio = html.escape(person[2] or "")

        page += f"""
        <div style="
            border:1px solid #ddd;
            border-radius:12px;
            padding:15px;
            margin:15px 0;
        ">

            <strong>
                {display_name}
            </strong>

            <p>
                {bio}
            </p>

            <a href="/chat/{user_id}">
                Chat
            </a>

        </div>
        """

    page += """
        <br>

        <a href="/messages">
            Messages
        </a>

        &nbsp; | &nbsp;

        <a href="/logout">
            Log out
        </a>

    </body>

    </html>
    """

    return page


# ---------------- CHAT ----------------

@app.route(
    "/chat/<int:user_id>",
    methods=["GET", "POST"]
)
def chat(user_id):

    my_id = session.get("user_id")

    if not my_id:
        return redirect(url_for("signup"))

    if user_id == my_id:
        return "You cannot message yourself.", 400

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT display_name
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            other_user = cur.fetchone()

    if not other_user:
        return "User not found.", 404

    if request.method == "POST":

        message = request.form.get(
            "message",
            ""
        ).strip()

        if message:

            with get_db() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO messages
                        (
                            sender_id,
                            receiver_id,
                            message
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (
                            my_id,
                            user_id,
                            message[:2000]
                        )
                    )

        return redirect(
            url_for(
                "chat",
                user_id=user_id
            )
        )

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    sender_id,
                    message,
                    created_at
                FROM messages
                WHERE
                    (
                        sender_id = %s
                        AND receiver_id = %s
                    )
                    OR
                    (
                        sender_id = %s
                        AND receiver_id = %s
                    )
                ORDER BY created_at
                """,
                (
                    my_id,
                    user_id,
                    user_id,
                    my_id
                )
            )

            conversation = cur.fetchall()

    other_name = html.escape(
        other_user[0] or "User"
    )

    page = f"""
    <!doctype html>

    <html>

    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>Chat | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:600px;
        margin:40px auto;
        padding:20px;
    ">

        <h1>Yobi1</h1>

        <h2>
            Chat with {other_name}
        </h2>
    """

    if not conversation:

        page += """
        <p>
            No messages yet.
        </p>
        """

    for item in conversation:

        sender_id = item[0]
        text = html.escape(item[1])

        if sender_id == my_id:
            sender_name = "You"
        else:
            sender_name = other_name

        page += f"""
        <p>
            <strong>
                {sender_name}:
            </strong>

            {text}
        </p>
        """

    page += """
        <form method="post">

            <input
                name="message"
                maxlength="2000"
                placeholder="Write a message..."
                required
                autocomplete="off"
                style="
                    width:75%;
                    padding:12px;
                "
            >

            <button
                type="submit"
                style="
                    padding:12px;
                "
            >
                Send
            </button>

        </form>

        <br>

        <a href="/users">
            Back to people
        </a>

    </body>

    </html>
    """

    return page


# ---------------- MESSAGES ----------------

@app.route("/messages")
def messages():

    my_id = session.get("user_id")

    if not my_id:
        return redirect(url_for("signup"))

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT DISTINCT
                    CASE
                        WHEN sender_id = %s
                        THEN receiver_id
                        ELSE sender_id
                    END AS other_id

                FROM messages

                WHERE
                    sender_id = %s
                    OR receiver_id = %s
                """,
                (
                    my_id,
                    my_id,
                    my_id
                )
            )

            conversation_ids = [
                row[0]
                for row in cur.fetchall()
            ]

    page = """
    <!doctype html>

    <html>

    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>Messages | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:600px;
        margin:40px auto;
        padding:20px;
    ">

        <h1>Yobi1</h1>

        <h2>Messages</h2>
    """

    if not conversation_ids:

        page += """
        <p>
            No conversations yet.
        </p>
        """

    else:

        with get_db() as conn:
            with conn.cursor() as cur:

                for other_id in conversation_ids:

                    cur.execute(
                        """
                        SELECT display_name
                        FROM users
                        WHERE id = %s
                        """,
                        (other_id,)
                    )

                    result = cur.fetchone()

                    if result:

                        name = html.escape(
                            result[0] or "User"
                        )

                        page += f"""
                        <p>
                            <a href="/chat/{other_id}">
                                {name}
                            </a>
                        </p>
                        """

    page += """
        <br>

        <a href="/users">
            People
        </a>

    </body>

    </html>
    """

    return page


# ---------------- LOG OUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ---------------- HEALTH CHECK ----------------

@app.route("/health")
def health():

    return {
        "ok": True,
        "version": "0.4"
    }


# ---------------- STARTUP ----------------

create_tables()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )
            )
        
