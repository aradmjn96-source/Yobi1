import os
import secrets
import html

import psycopg
from flask import Flask, request, redirect, url_for, session

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)


# ---------- DATABASE ----------

def get_db():
    return psycopg.connect(os.environ["DATABASE_URL"])


def create_tables():
    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS guest_users (
                    id SERIAL PRIMARY KEY,
                    device_token TEXT UNIQUE NOT NULL,
                    display_name VARCHAR(40) NOT NULL,
                    bio VARCHAR(160),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS guest_messages (
                    id SERIAL PRIMARY KEY,
                    sender_id INTEGER NOT NULL
                        REFERENCES guest_users(id)
                        ON DELETE CASCADE,
                    receiver_id INTEGER NOT NULL
                        REFERENCES guest_users(id)
                        ON DELETE CASCADE,
                    message VARCHAR(2000) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)


# ---------- CURRENT USER ----------

def current_user():

    token = session.get("device_token")

    if not token:
        return None

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id, display_name, bio
                FROM guest_users
                WHERE device_token = %s
                """,
                (token,)
            )

            return cur.fetchone()


# ---------- HOME ----------

@app.route("/")
def home():

    if current_user():
        return redirect(url_for("people"))

    return redirect(url_for("profile"))


# ---------- PROFILE ----------

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if current_user():
        return redirect(url_for("people"))

    if request.method == "POST":

        name = request.form.get(
            "display_name",
            ""
        ).strip()

        bio = request.form.get(
            "bio",
            ""
        ).strip()

        if not name:
            return "Please choose a name.", 400

        token = secrets.token_urlsafe(32)

        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO guest_users
                    (device_token, display_name, bio)

                    VALUES (%s, %s, %s)

                    RETURNING id
                    """,
                    (
                        token,
                        name[:40],
                        bio[:160]
                    )
                )

                cur.fetchone()

        session["device_token"] = token

        return redirect(url_for("people"))

    return """
    <!doctype html>

    <html>
    <head>

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:500px;
        margin:60px auto;
        padding:20px;
    ">

        <h1 style="text-align:center;">
            Yobi1
        </h1>

        <h2 style="text-align:center;">
            Create your profile
        </h2>

        <p style="text-align:center;color:#666;">
            No email. No sign up.
        </p>

        <form method="post">

            <input
                name="display_name"
                maxlength="40"
                placeholder="Your name"
                required
                style="
                    width:100%;
                    padding:14px;
                    box-sizing:border-box;
                "
            >

            <br><br>

            <textarea
                name="bio"
                maxlength="160"
                placeholder="Your bio..."
                style="
                    width:100%;
                    height:100px;
                    padding:14px;
                    box-sizing:border-box;
                "
            ></textarea>

            <br><br>

            <button
                type="submit"
                style="
                    width:100%;
                    padding:14px;
                "
            >
                Enter Yobi1
            </button>

        </form>

    </body>
    </html>
    """


# ---------- PEOPLE ----------

@app.route("/people")
def people():

    me = current_user()

    if not me:
        return redirect(url_for("profile"))

    my_id = me[0]

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id, display_name, bio
                FROM guest_users
                WHERE id != %s
                ORDER BY created_at DESC
                """,
                (my_id,)
            )

            users = cur.fetchall()

    page = """
    <!doctype html>

    <html>
    <head>

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1"
        >

        <title>People | Yobi1</title>

    </head>

    <body style="
        font-family:Arial;
        max-width:600px;
        margin:
