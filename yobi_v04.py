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


def get_db():
    return psycopg.connect(
        os.environ["DATABASE_URL"]
    )


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


@app.route("/")
def home():

    user = current_user()

    if user:
        return redirect(
            url_for("people")
        )

    return redirect(
        url_for("profile")
    )


@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    existing = current_user()

    if existing:
        return redirect(
            url_for("people")
        )

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
            return "Please choose a name.", 400

        device_token = secrets.token_urlsafe(32)

        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO guest_users
                    (
                        device_token,
                        display_name,
                        bio
                    )

                    VALUES (%s, %s, %s)

                    RETURNING id
                    """,
                    (
                        device_token,
                        display_name[:40],
                        bio[:160]
                    )
                )

                cur.fetchone()

        session["device_token"] = device_token

        return redirect(
            url_for("people")
        )

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


@app.route("/people")
def people():

    me = current_user()

    if not me:
        return redirect(
            url_for("profile")
        )

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

    if not users:

        page += """
        <p>
            Nobody else is here yet.
        </p>
        """

    for user in users:

        user_id = user[0]

        name = html.escape(
            user[1]
        )

        bio = html.escape(
            user[2] or ""
        )

        page += f"""
        <div style="
            border:1px solid #ddd;
            border-radius:14px;
            padding:16px;
            margin:14px 0;
        ">

            <strong>
                {name}
            </strong>

            <p>
                {bio}
            </p>

            <a href="/chat/{user_id}">
                Message
            </a>

        </div>
        """

    page += """
        <br>

        <a href="/messages">
            My messages
        </a>

    </body>

    </html>
    """

    return page


@app.route(
    "/chat/<int:user_id>",
    methods=["GET", "POST"]
)
def chat(user_id):

    me = current_user()

    if not me:
        return redirect(
            url_for("profile")
        )

    my_id = me[0]

    if user_id == my_id:
        return "You cannot message yourself.", 400

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT display_name
                FROM guest_users
                WHERE id = %s
                """,
                (user_id,)
            )

            other = cur.fetchone()

    if not other:
        return "User not found.", 404

    if request.method == "POST":

        text = request.form.get(
            "message",
            ""
        ).strip()

        if text:

            with get_db() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO guest_messages
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
                            text[:2000]
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

                FROM guest_messages

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

            messages = cur.fetchall()

    other_name = html.escape(
        other[0]
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
            {other_name}
        </h2>
    """

    for message in messages:

        sender = message[0]

        text = html.escape(
            message[1]
        )

        if sender == my_id:
            who = "You"
        else:
            who = other_name

        page += f"""
        <p>
            <strong>
                {who}:
            </strong>

            {text}
        </p>
        """

    page += """
        <form method="post">

            <input
                name="message"
                maxlength="2000"
                placeholder="Message..."
                autocomplete="off"
                required
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

        <a href="/people">
            Back
        </a>

    </body>

    </html>
    """

    return page


@app.route("/messages")
def messages():

    me = current_user()

    if not me:
        return redirect(
            url_for("profile")
        )

    my_id = me[0]

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT DISTINCT

                    CASE
                        WHEN sender_id = %s
                        THEN receiver_id
                        ELSE sender_id
                    END

                FROM guest_messages

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

            ids = [
                row[0]
                for row in cur.fetchall()
            ]

    page = """
    <!doctype html>

    <html>

    <head>

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

    if not ids:

        page += """
        <p>
            No messages yet.
        </p>
        """

    with get_db() as conn:
        with conn.cursor() as cur:

            for other_id in ids:

                cur.execute(
                    """
                    SELECT display_name
                    FROM guest_users
                    WHERE id = %s
                    """,
                    (other_id,)
                )

                result = cur.fetchone()

                if result:

                    name = html.escape(
                        result[0]
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

        <a href="/people">
            People
        </a>

    </body>

    </html>
    """

    return page


@app.route("/reset-profile")
def reset_profile():

    session.clear()

    return redirect(
        url_for("profile")
    )


@app.route("/health")
def health():

    return {
        "ok": True,
        "version": "0.4-chat"
    }


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
