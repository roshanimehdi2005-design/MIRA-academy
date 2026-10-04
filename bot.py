import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


# ============================================================
# MIRA BOT - FINAL ARCHITECTURE
# ============================================================


BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
}

PORT = int(os.environ.get("PORT", "10000"))
DB_PATH = os.environ.get("DB_PATH", "mira.db")


# ============================================================
# CHANNELS
# ============================================================

CHANNEL_USERNAME = os.environ.get(
    "CHANNEL_USERNAME",
    "@miracampus"
).strip()

CHANNEL_URL = os.environ.get(
    "CHANNEL_URL",
    "https://t.me/miracampus"
).strip()


COURSE_CHANNEL_USERNAME = os.environ.get(
    "COURSE_CHANNEL_USERNAME",
    "@mirakunkorclss"
).strip()

COURSE_CHANNEL_URL = os.environ.get(
    "COURSE_CHANNEL_URL",
    "https://t.me/mirakunkorclss"
).strip()


CONSULTING_CHANNEL_USERNAME = os.environ.get(
    "CONSULTING_CHANNEL_USERNAME",
    "@miraprivatecahnnel"
).strip()

CONSULTING_CHANNEL_URL = os.environ.get(
    "CONSULTING_CHANNEL_URL",
    "https://t.me/miraprivatecahnnel"
).strip()


# ============================================================
# SUPPORT
# ============================================================

SUPPORT_USERNAME = os.environ.get(
    "SUPPORT_USERNAME",
    "@teammira_admin"
).strip()

SUPPORT_URL = (
    f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"
    if SUPPORT_USERNAME
    else ""
)


# ============================================================
# PAYMENT
# ============================================================

CARD_NUMBER = os.environ.get(
    "CARD_NUMBER",
    "6219861940398554"
).strip()

CARD_OWNER = os.environ.get(
    "CARD_OWNER",
    "محمد مهدی روشنی"
).strip()


# ============================================================
# RENDER
# ============================================================

RENDER_EXTERNAL_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    ""
).rstrip("/")


# ============================================================
# PLAN PRICES
# ============================================================

def env_price(name):
    value = os.environ.get(name, "").strip().replace(",", "")

    if not value:
        return 0

    try:
        return int(value)
    except ValueError:
        return 0


# ============================================================
# PLANS
# ============================================================

PLANS = {

    "task": {
        "name": "📚 تسک‌پلن | ۳ ماهه",

        "description": (
            "اگر می‌دانی باید بیشتر و بهتر درس بخوانی، اما نمی‌دانی "
            "هر روز دقیقاً چه کاری انجام بدهی، این پلن برای توست.\n\n"
            "▫️ برنامه روزانه و دقیق مطالعه\n"
            "▫️ تعیین تسک‌ها و اولویت‌های درسی\n"
            "▫️ مشخص‌کردن مسیر پیشروی"
        ),

        "price": env_price("PLAN_TASK_PRICE"),
    },


    "task_mentoring": {
        "name": "🎯 تسک‌پلن منتورینگ | ۳ ماهه",

        "description": (
            "فقط برنامه نمی‌گیری؛ در مسیر اجرا هم تنها نیستی. "
            "منتور عملکردت را دنبال می‌کند و بر اساس روند واقعی مطالعه‌ات، "
            "مسیر را اصلاح می‌کند.\n\n"
            "▫️ تمام امکانات تسک‌پلن\n"
            "▫️ پیگیری و نظارت منتور\n"
            "▫️ بررسی عملکرد و نقاط ضعف\n"
            "▫️ اصلاح مسیر بر اساس پیشرفت"
        ),

        "price": env_price("PLAN_TASK_MENTORING_PRICE"),
    },


    "360": {
        "name": "🚀 مشاوره ۳۶۰ | ۳ ماهه",

        "description": (
            "برای کسی که می‌خواهد مسیر کنکورش فقط برنامه‌ریزی نشود؛ "
            "بلکه به‌صورت کامل مدیریت، بررسی و هدایت شود.\n\n"
            "▫️ برنامه‌ریزی و تسک‌های روزانه\n"
            "▫️ منتورینگ و پیگیری مستمر\n"
            "▫️ تحلیل عملکرد و روند پیشرفت\n"
            "▫️ هدایت و اصلاح همه‌جانبه مسیر کنکور"
        ),

        "price": env_price("PLAN_360_PRICE"),
    },
}


# ============================================================
# CONSULTANTS
# ============================================================

CONSULTANTS = {

    "task": {
        "name": os.environ.get(
            "TASK_CONSULTANT_NAME",
            "تیم تسک‌پلن MIRA"
        ).strip(),

        "username": os.environ.get(
            "TASK_CONSULTANT_USERNAME",
            ""
        ).strip(),
    },


    "task_mentoring": {
        "name": os.environ.get(
            "TASK_MENTORING_CONSULTANT_NAME",
            "تیم منتورینگ MIRA"
        ).strip(),

        "username": os.environ.get(
            "TASK_MENTORING_CONSULTANT_USERNAME",
            ""
        ).strip(),
    },


    "360": {
        "name": os.environ.get(
            "PLAN_360_CONSULTANT_NAME",
            "تیم مشاوره ۳۶۰ MIRA"
        ).strip(),

        "username": os.environ.get(
            "PLAN_360_CONSULTANT_USERNAME",
            ""
        ).strip(),
    },
}


# ============================================================
# RUNTIME STATE
# ============================================================

states = {}

state_lock = threading.RLock()


membership_cache = {}

membership_cache_lock = threading.RLock()

MEMBERSHIP_CACHE_SECONDS = 60


# ============================================================
# TELEGRAM API
# ============================================================

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "MIRA-Bot/3.0"
})


def telegram(
    method,
    payload=None,
    files=None,
    timeout=10
):

    if not BOT_TOKEN:
        return None


    url = f"{API_URL}/{method}"


    try:

        if files:

            response = SESSION.post(
                url,
                data=payload or {},
                files=files,
                timeout=timeout
            )

        else:

            response = SESSION.post(
                url,
                json=payload or {},
                timeout=timeout
            )


        if response.status_code != 200:

            print(
                f"[MIRA] Telegram HTTP error {method}: "
                f"{response.status_code} "
                f"{response.text[:500]}",
                flush=True
            )

            return None


        data = response.json()


        if not data.get("ok"):

            print(
                f"[MIRA] Telegram API error {method}: "
                f"{data.get('description', 'unknown error')}",
                flush=True
            )

            return None


        return data.get("result")


    except requests.RequestException as exc:

        print(
            f"[MIRA] Telegram request error {method}: {exc}",
            flush=True
        )

        return None


    except Exception as exc:

        print(
            f"[MIRA] Telegram unexpected error {method}: {exc}",
            flush=True
        )

        return None


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def send_message(
    chat_id,
    text,
    reply_markup=None,
    parse_mode="HTML",
    disable_web_page_preview=True
):

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }


    if parse_mode:

        payload["parse_mode"] = parse_mode


    if reply_markup:

        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )


    return telegram(
        "sendMessage",
        payload,
        timeout=8
    )


def edit_message(
    chat_id,
    message_id,
    text,
    reply_markup=None,
    parse_mode="HTML"
):

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }


    if parse_mode:

        payload["parse_mode"] = parse_mode


    if reply_markup:

        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )


    return telegram(
        "editMessageText",
        payload,
        timeout=8
    )


def answer_callback(
    callback_id,
    text=None
):

    if not callback_id:
        return


    payload = {
        "callback_query_id": callback_id
    }


    if text:

        payload["text"] = text


    telegram(
        "answerCallbackQuery",
        payload,
        timeout=5
    )


def get_file(file_id):

    return telegram(
        "getFile",
        {
            "file_id": file_id
        },
        timeout=8
    )


def download_telegram_file(file_id):

    file_info = get_file(file_id)


    if not file_info:
        return None


    file_path = file_info.get("file_path")


    if not file_path:
        return None


    url = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_path}"
    )


    try:

        response = SESSION.get(
            url,
            timeout=15
        )


        if response.status_code != 200:
            return None


        return response.content


    except requests.RequestException as exc:

        print(
            f"[MIRA] File download error: {exc}",
            flush=True
        )

        return None


def send_photo(
    chat_id,
    photo,
    caption=None,
    reply_markup=None
):

    payload = {
        "chat_id": str(chat_id)
    }


    if caption:

        payload["caption"] = caption

        payload["parse_mode"] = "HTML"


    if reply_markup:

        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )


    files = {
        "photo": (
            "receipt.jpg",
            photo
        )
    }


    return telegram(
        "sendPhoto",
        payload,
        files=files,
        timeout=20
    )


# ============================================================
# DATABASE
# ============================================================

DB_LOCK = threading.RLock()


def get_db():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=15,
        check_same_thread=False
    )


    conn.row_factory = sqlite3.Row


    conn.execute(
        "PRAGMA journal_mode=WAL"
    )


    conn.execute(
        "PRAGMA synchronous=NORMAL"
    )


    conn.execute(
        "PRAGMA busy_timeout=15000"
    )


    return conn


def now_iso():

    return datetime.now().isoformat(
        timespec="seconds"
    )


def table_columns(
    conn,
    table_name
):

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()


    return {
        row["name"]
        for row in rows
    }


def add_column_if_missing(
    conn,
    table,
    column,
    definition
):

    columns = table_columns(
        conn,
        table
    )


    if column not in columns:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def migrate_old_database(conn):

    add_column_if_missing(
        conn,
        "mira_students",
        "student_number",
        "INTEGER"
    )


    add_column_if_missing(
        conn,
        "mira_students",
        "telegram_username",
        "TEXT"
    )


    rows = conn.execute(
        """
        SELECT chat_id
        FROM mira_students
        WHERE student_number IS NULL
        ORDER BY created_at ASC, chat_id ASC
        """
    ).fetchall()


    max_number_row = conn.execute(
        """
        SELECT MAX(student_number)
        AS max_number
        FROM mira_students
        """
    ).fetchone()


    next_number = (
        max_number_row["max_number"] or 0
    ) + 1


    for row in rows:

        conn.execute(
            """
            UPDATE mira_students
            SET student_number = ?
            WHERE chat_id = ?
            """,
            (
                next_number,
                row["chat_id"]
            )
        )


        next_number += 1


def init_db():

    with DB_LOCK:

        conn = get_db()


        try:

            conn.executescript(
                """

                CREATE TABLE IF NOT EXISTS mira_students (

                    chat_id INTEGER PRIMARY KEY,

                    student_number INTEGER UNIQUE,

                    telegram_username TEXT,

                    full_name TEXT NOT NULL,

                    phone TEXT,

                    grade TEXT,

                    field TEXT,

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS mira_leads (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    chat_id INTEGER NOT NULL,

                    full_name TEXT,

                    phone TEXT,

                    grade TEXT,

                    field TEXT,

                    created_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS mira_payment_requests (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    chat_id INTEGER NOT NULL,

                    plan_key TEXT NOT NULL,

                    plan_name TEXT NOT NULL,

                    amount INTEGER NOT NULL DEFAULT 0,

                    status TEXT NOT NULL DEFAULT 'PENDING',

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS mira_payments (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    request_id INTEGER,

                    chat_id INTEGER NOT NULL,

                    plan_key TEXT NOT NULL,

                    amount INTEGER NOT NULL DEFAULT 0,

                    receipt_file_id TEXT,

                    status TEXT NOT NULL DEFAULT 'PENDING',

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS mira_subscriptions (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    chat_id INTEGER NOT NULL,

                    plan_key TEXT NOT NULL,

                    plan_name TEXT NOT NULL,

                    status TEXT NOT NULL DEFAULT 'ACTIVE',

                    start_date TEXT NOT NULL,

                    expiration_date TEXT NOT NULL,

                    consultant TEXT,

                    updated_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS mira_support_requests (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    chat_id INTEGER NOT NULL,

                    message TEXT,

                    status TEXT NOT NULL DEFAULT 'OPEN',

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL

                );


                CREATE INDEX IF NOT EXISTS idx_students_created

                ON mira_students(created_at);


                CREATE INDEX IF NOT EXISTS idx_payments_chat

                ON mira_payments(chat_id);


                CREATE INDEX IF NOT EXISTS idx_payments_status

                ON mira_payments(status);


                CREATE INDEX IF NOT EXISTS idx_requests_status

                ON mira_payment_requests(status);


                CREATE INDEX IF NOT EXISTS idx_subscriptions_chat

                ON mira_subscriptions(chat_id);


                CREATE INDEX IF NOT EXISTS idx_subscriptions_status

                ON mira_subscriptions(status);


                CREATE INDEX IF NOT EXISTS idx_support_status

                ON mira_support_requests(status);

                """
            )


            migrate_old_database(conn)


            conn.commit()


        finally:

            conn.close()


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_student(chat_id):

    with DB_LOCK:

        conn = get_db()


        try:

            row = conn.execute(
                """
                SELECT *
                FROM mira_students
                WHERE chat_id = ?
                """,
                (chat_id,)
            ).fetchone()


            return (
                dict(row)
                if row
                else None
            )


        finally:

            conn.close()


def create_student(
    chat_id,
    full_name,
    grade,
    field,
    phone,
    username=None
):

    created_at = now_iso()


    with DB_LOCK:

        conn = get_db()


        try:

            row = conn.execute(
                """
                SELECT student_number
                FROM mira_students
                WHERE chat_id = ?
                """,
                (chat_id,)
            ).fetchone()


            if row:

                student_number = row["student_number"]


                conn.execute(
                    """
                    UPDATE mira_students

                    SET full_name = ?,

                        grade = ?,

                        field = ?,

                        phone = ?,

                        telegram_username = ?,

                        updated_at = ?

                    WHERE chat_id = ?
                    """,
                    (
                        full_name,
                        grade,
                        field,
                        phone,
                        username,
                        created_at,
                        chat_id
                    )
                )


            else:

                row = conn.execute(
                    """
                    SELECT
                        COALESCE(
                            MAX(student_number),
                            0
                        ) + 1 AS next_number

                    FROM mira_students
                    """
                ).fetchone()


                student_number = row[
                    "next_number"
                ]


                conn.execute(
                    """
                    INSERT INTO mira_students (

                        chat_id,

                        student_number,

                        telegram_username,

                        full_name,

                        phone,

                        grade,

                        field,

                        created_at,

                        updated_at

                    )

                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        chat_id,
                        student_number,
                        username,
                        full_name,
                        phone,
                        grade,
                        field,
                        created_at,
                        created_at
                    )
                )


            conn.execute(
                """
                INSERT INTO mira_leads (

                    chat_id,

                    full_name,

                    phone,

                    grade,

                    field,

                    created_at

                )

                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    full_name,
                    phone,
                    grade,
                    field,
                    created_at
                )
            )


            conn.commit()


            return student_number


        finally:

            conn.close()


def get_active_subscription(chat_id):

    with DB_LOCK:

        conn = get_db()


        try:

            row = conn.execute(
                """
                SELECT *

                FROM mira_subscriptions

                WHERE chat_id = ?

                AND status = 'ACTIVE'

                ORDER BY expiration_date DESC

                LIMIT 1
                """,
                (chat_id,)
            ).fetchone()


            if not row:
                return None


            data = dict(row)


            expiration = parse_datetime(
                data["expiration_date"]
            )


            if expiration <= datetime.now():

                conn.execute(
                    """
                    UPDATE mira_subscriptions

                    SET status = 'EXPIRED',

                        updated_at = ?

                    WHERE id = ?
                    """,
                    (
                        now_iso(),
                        data["id"]
                    )
                )


                conn.commit()


                return None


            return data


        finally:

            conn.close()


def create_payment_request(
    chat_id,
    plan_key
):

    plan = PLANS.get(plan_key)


    if not plan:
        return None


    created_at = now_iso()


    with DB_LOCK:

        conn = get_db()


        try:

            pending = conn.execute(
                """
                SELECT *

                FROM mira_payment_requests

                WHERE chat_id = ?

                AND status = 'PENDING'

                ORDER BY id DESC

                LIMIT 1
                """,
                (chat_id,)
            ).fetchone()


            if pending:

                if pending["plan_key"] == plan_key:

                    return dict(pending)


                conn.execute(
                    """
                    UPDATE mira_payment_requests

                    SET status = 'CANCELLED',

                        updated_at = ?

                    WHERE id = ?
                    """,
                    (
                        created_at,
                        pending["id"]
                    )
                )


            cursor = conn.execute(
                """
                INSERT INTO mira_payment_requests (

                    chat_id,

                    plan_key,

                    plan_name,

                    amount,

                    status,

                    created_at,

                    updated_at

                )

                VALUES (
                    ?, ?, ?, ?, 'PENDING', ?, ?
                )
                """,
                (
                    chat_id,
                    plan_key,
                    plan["name"],
                    plan["price"],
                    created_at,
                    created_at
                )
            )


            conn.commit()


            row = conn.execute(
                """
                SELECT *

                FROM mira_payment_requests

                WHERE id = ?
                """,
                (
                    cursor.lastrowid,
                )
            ).fetchone()


            return dict(row)


        finally:

            conn.close()


def create_payment(
    chat_id,
    request_id,
    plan_key,
    amount,
    file_id
):

    created_at = now_iso()


    with DB_LOCK:

        conn = get_db()


        try:

            cursor = conn.execute(
                """
                INSERT INTO mira_payments (

                    request_id,

                    chat_id,

                    plan_key,

                    amount,

                    receipt_file_id,

                    status,

                    created_at,

                    updated_at

                )

                VALUES (
                    ?, ?, ?, ?, ?, 'PENDING', ?, ?
                )
                """,
                (
                    request_id,
                    chat_id,
                    plan_key,
                    amount,
                    file_id,
                    created_at,
                    created_at
                )
            )


            conn.commit()


            return cursor.lastrowid


        finally:

            conn.close()


def approve_payment(
    payment_id,
    consultant=""
):

    with DB_LOCK:

        conn = get_db()


        try:

            payment = conn.execute(
                """
                SELECT *

                FROM mira_payments

                WHERE id = ?
                """,
                (
                    payment_id,
                )
            ).fetchone()


            if (
                not payment
                or payment["status"] != "PENDING"
            ):

                return None


            plan_key = payment["plan_key"]


            plan = PLANS.get(plan_key)


            if not plan:
                return None


            consultant_info = CONSULTANTS.get(
                plan_key,
                {}
            )


            consultant_name = (
                consultant.strip()
                if consultant
                else consultant_info.get(
                    "name",
                    ""
                )
            )


            start = datetime.now()


            active = conn.execute(
                """
                SELECT *

                FROM mira_subscriptions

                WHERE chat_id = ?

                AND status = 'ACTIVE'

                ORDER BY expiration_date DESC

                LIMIT 1
                """,
                (
                    payment["chat_id"],
                )
            ).fetchone()


            if active:

                old_expiration = parse_datetime(
                    active["expiration_date"]
                )


                if old_expiration > start:

                    start = old_expiration


                    conn.execute(
                        """
                        UPDATE mira_subscriptions

                        SET status = 'EXPIRED',

                            updated_at = ?

                        WHERE id = ?
                        """,
                        (
                            now_iso(),
                            active["id"]
                        )
                    )


            expiration = start + timedelta(
                days=90
            )


            # IMPORTANT:
            # plan_key must be the actual key:
            # task / task_mentoring / 360

            conn.execute(
                """
                INSERT INTO mira_subscriptions (

                    chat_id,

                    plan_key,

                    plan_name,

                    status,

                    start_date,

                    expiration_date,

                    consultant,

                    updated_at

                )

                VALUES (
                    ?, ?, ?, 'ACTIVE', ?, ?, ?, ?
                )
                """,
                (
                    payment["chat_id"],

                    plan_key,

                    plan["name"],

                    start.isoformat(
                        timespec="seconds"
                    ),

                    expiration.isoformat(
                        timespec="seconds"
                    ),

                    consultant_name or None,

                    now_iso()
                )
            )


            conn.execute(
                """
                UPDATE mira_payments

                SET status = 'APPROVED',

                    updated_at = ?

                WHERE id = ?
                """,
                (
                    now_iso(),
                    payment_id
                )
            )


            if payment["request_id"]:

                conn.execute(
                    """
                    UPDATE mira_payment_requests

                    SET status = 'APPROVED',

                        updated_at = ?

                    WHERE id = ?
                    """,
                    (
                        now_iso(),
                        payment["request_id"]
                    )
                )


            conn.commit()


            return {

                "chat_id":
                    payment["chat_id"],

                "plan_key":
                    plan_key,

                "plan_name":
                    plan["name"],

                "start":
                    start,

                "expiration":
                    expiration,

                "amount":
                    payment["amount"],

                "consultant":
                    consultant_name,
            }


        finally:

            conn.close()


def reject_payment(payment_id):

    with DB_LOCK:

        conn = get_db()


        try:

            payment = conn.execute(
                """
                SELECT *

                FROM mira_payments

                WHERE id = ?
                """,
                (
                    payment_id,
                )
            ).fetchone()


            if (
                not payment
                or payment["status"] != "PENDING"
            ):

                return None


            conn.execute(
                """
                UPDATE mira_payments

                SET status = 'REJECTED',

                    updated_at = ?

                WHERE id = ?
                """,
                (
                    now_iso(),
                    payment_id
                )
            )


            if payment["request_id"]:

                conn.execute(
                    """
                    UPDATE mira_payment_requests

                    SET status = 'REJECTED',

                        updated_at = ?

                    WHERE id = ?
                    """,
                    (
                        now_iso(),
                        payment["request_id"]
                    )
                )


            conn.commit()


            return dict(payment)


        finally:

            conn.close()


# ============================================================
# ADMIN DATA
# ============================================================

def get_admin_stats():

    with DB_LOCK:

        conn = get_db()


        try:

            total_students = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_students
                """
            ).fetchone()["c"]


            today = (
                datetime.now()
                .date()
                .isoformat()
            )


            new_today = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_students

                WHERE substr(
                    created_at,
                    1,
                    10
                ) = ?
                """,
                (
                    today,
                )
            ).fetchone()["c"]


            active = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_subscriptions

                WHERE status = 'ACTIVE'

                AND expiration_date > ?
                """,
                (
                    datetime.now().isoformat(),
                )
            ).fetchone()["c"]


            expired = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_subscriptions

                WHERE expiration_date <= ?
                """,
                (
                    datetime.now().isoformat(),
                )
            ).fetchone()["c"]


            pending_payments = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_payments

                WHERE status = 'PENDING'
                """
            ).fetchone()["c"]


            leads = conn.execute(
                """
                SELECT COUNT(*) AS c

                FROM mira_leads
                """
            ).fetchone()["c"]


            return {

                "total_students":
                    total_students,

                "new_today":
                    new_today,

                "active":
                    active,

                "expired":
                    expired,

                "pending_payments":
                    pending_payments,

                "leads":
                    leads,
            }


        finally:

            conn.close()


def get_recent_students(
    limit=15
):

    with DB_LOCK:

        conn = get_db()


        try:

            rows = conn.execute(
                """
                SELECT

                    student_number,

                    full_name,

                    phone,

                    grade,

                    field,

                    created_at

                FROM mira_students

                ORDER BY student_number DESC

                LIMIT ?
                """,
                (
                    limit,
                )
            ).fetchall()


            return [
                dict(row)
                for row in rows
            ]


        finally:

            conn.close()


def get_pending_payments(
    limit=15
):

    with DB_LOCK:

        conn = get_db()


        try:

            rows = conn.execute(
                """
                SELECT

                    p.*,

                    s.full_name,

                    s.student_number,

                    s.phone

                FROM mira_payments p

                LEFT JOIN mira_students s

                    ON s.chat_id = p.chat_id

                WHERE p.status = 'PENDING'

                ORDER BY p.id DESC

                LIMIT ?
                """,
                (
                    limit,
                )
            ).fetchall()


            return [
                dict(row)
                for row in rows
            ]


        finally:

            conn.close()


# ============================================================
# DATE / TEXT HELPERS
# ============================================================

def parse_datetime(value):

    if not value:
        return datetime.min


    try:

        return datetime.fromisoformat(
            value
        )

    except (
        ValueError,
        TypeError
    ):

        return datetime.min


def format_price(amount):

    if not amount:

        return (
            "قیمت هنوز تنظیم نشده"
        )


    return (
        f"{amount:,} تومان"
    )


def remaining_days(
    expiration
):

    delta = (
        parse_datetime(
            expiration
        )
        - datetime.now()
    )


    if delta.total_seconds() <= 0:

        return 0


    return (
        delta.days
        +
        (
            1
            if delta.seconds > 0
            else 0
        )
    )


def escape_html(value):

    if value is None:
        return ""


    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_date(value):

    dt = parse_datetime(
        value
    )


    if dt == datetime.min:

        return "-"


    return dt.strftime(
        "%Y/%m/%d"
    )


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():

    return {

        "keyboard": [

            [

                {
                    "text":
                        "📚 پلن‌های مشاوره"
                },

                {
                    "text":
                        "💳 پرداخت و تمدید"
                }

            ],

            [

                {
                    "text":
                        "🎓 کلاس‌های کنکوری"
                },

                {
                    "text":
                        "🆘 ارتباط با پشتیبان"
                }

            ],

            [

                {
                    "text":
                        "👤 پنل من"
                }

            ]

        ],

        "resize_keyboard":
            True
    }


def registration_start_keyboard():

    return {

        "inline_keyboard": [

            [

                {

                    "text":
                        "🚀 بزن بریم",

                    "callback_data":
                        "start_registration"

                }

            ]

        ]

    }


def admin_keyboard():

    return {

        "keyboard": [

            [

                {
                    "text":
                        "📊 داشبورد"
                },

                {
                    "text":
                        "👥 دانش‌آموزان"
                }

            ],

            [

                {
                    "text":
                        "💳 پرداخت‌های در انتظار"
                }

            ],

            [

                {
                    "text":
                        "🏠 خروج از پنل ادمین"
                }

            ]

        ],

        "resize_keyboard":
            True
    }


def membership_keyboard():

    return {

        "inline_keyboard": [

            [

                {

                    "text":
                        "📢 عضویت در کانال MIRA",

                    "url":
                        CHANNEL_URL

                }

            ],

            [

                {

                    "text":
                        "✅ بررسی عضویت",

                    "callback_data":
                        "check_membership"

                }

            ]

        ]

    }


def all_channels_keyboard():

    return {

        "inline_keyboard": [

            [

                {

                    "text":
                        "📢 کانال اصلی MIRA",

                    "url":
                        CHANNEL_URL

                }

            ],

            [

                {

                    "text":
                        "🎓 کانال کلاس‌ها",

                    "url":
                        COURSE_CHANNEL_URL

                }

            ],

            [

                {

                    "text":
                        "💎 کانال مشاوره",

                    "url":
                        CONSULTING_CHANNEL_URL

                }

            ],

            [

                {

                    "text":
                        "✅ بررسی عضویت هر ۳ کانال",

                    "callback_data":
                        "check_all_channels"

                }

            ]

        ]

    }


def contact_keyboard():

    return {

        "keyboard": [

            [

                {

                    "text":
                        "📱 ارسال شماره تلفن",

                    "request_contact":
                        True

                }

            ]

        ],

        "resize_keyboard":
            True,

        "one_time_keyboard":
            True
    }


def remove_keyboard():

    return {
        "remove_keyboard":
            True
    }


def grade_keyboard():

    return {

        "keyboard": [

            [

                {
                    "text":
                        "دهم"
                },

                {
                    "text":
                        "یازدهم"
                },

                {
                    "text":
                        "دوازدهم"
                }

            ],

            [

                {
                    "text":
                        "فارغ‌التحصیل"
                },

                {
                    "text":
                        "پشت‌کنکوری"
                }

            ]

        ],

        "resize_keyboard":
            True,

        "one_time_keyboard":
            True
    }


def field_keyboard():

    return {

        "keyboard": [

            [

                {
                    "text":
                        "تجربی"
                },

                {
                    "text":
                        "ریاضی"
                },

                {
                    "text":
                        "انسانی"
                }

            ],

            [

                {
                    "text":
                        "فنی‌وحرفه‌ای"
                },

                {
                    "text":
                        "هنر"
                }

            ],

            [

                {
                    "text":
                        "سایر"
                }

            ]

        ],

        "resize_keyboard":
            True,

        "one_time_keyboard":
            True
    }


# ============================================================
# MEMBERSHIP
# ============================================================

def check_single_channel(
    chat_id,
    channel_username,
    force=False
):

    cache_key = (
        f"{chat_id}:{channel_username}"
    )


    now = datetime.now()


    with membership_cache_lock:

        cached = membership_cache.get(
            cache_key
        )


        if (

            not force

            and cached

            and (
                now
                -
                cached["time"]
            ).total_seconds()

            < MEMBERSHIP_CACHE_SECONDS

        ):

            return cached["value"]


    result = telegram(

        "getChatMember",

        {

            "chat_id":
                channel_username,

            "user_id":
                chat_id

        },

        timeout=7
    )


    if result is None:

        value = False


    else:

        status = result.get(
            "status"
        )


        if status in {

            "member",

            "administrator",

            "creator"

        }:

            value = True


        elif status == "restricted":

            value = bool(
                result.get(
                    "is_member",
                    False
                )
            )


        else:

            value = False


    with membership_cache_lock:

        membership_cache[
            cache_key
        ] = {

            "value":
                value,

            "time":
                now

        }


    return value


def check_main_membership(
    chat_id,
    force=False
):

    return check_single_channel(

        chat_id,

        CHANNEL_USERNAME,

        force=force

    )


def check_all_channel_memberships(
    chat_id,
    force=False
):

    return {

        "main":
            check_single_channel(

                chat_id,

                CHANNEL_USERNAME,

                force=force

            ),

        "course":
            check_single_channel(

                chat_id,

                COURSE_CHANNEL_USERNAME,

                force=force

            ),

        "consulting":
            check_single_channel(

                chat_id,

                CONSULTING_CHANNEL_USERNAME,

                force=force

            )

    }


def require_main_membership(
    chat_id,
    force=False
):

    if check_main_membership(
        chat_id,
        force=force
    ):

        return True


    send_message(

        chat_id,

        (
            "برای استفاده از بات MIRA ابتدا باید "
            "عضو کانال اصلی MIRA باشی. 📢\n\n"
            "بعد از عضویت روی «بررسی عضویت» بزن."
        ),

        reply_markup=
            membership_keyboard()

    )


    return False


def show_all_channels_gate(
    chat_id,
    force=False
):

    statuses = (
        check_all_channel_memberships(
            chat_id,
            force=force
        )
    )


    if all(
        statuses.values()
    ):

        return True


    lines = [

        "<b>📢 تکمیل عضویت در کانال‌ها</b>",

        "",

        "برای ادامه ثبت‌نام باید عضو هر ۳ کانال MIRA باشی:",

        "",

        (
            "✅"
            if statuses["main"]
            else "❌"
        )
        + " کانال اصلی MIRA",

        (
            "✅"
            if statuses["course"]
            else "❌"
        )
        + " کانال کلاس‌های کنکوری",

        (
            "✅"
            if statuses["consulting"]
            else "❌"
        )
        + " کانال مشاوره",

        "",

        "بعد از عضویت، روی «بررسی عضویت هر ۳ کانال» بزن."

    ]


    send_message(

        chat_id,

        "\n".join(lines),

        reply_markup=
            all_channels_keyboard()

    )


    return False


# ============================================================
# STATE MANAGEMENT
# ============================================================

def set_state(
    chat_id,
    state,
    data=None
):

    with state_lock:

        states[chat_id] = {

            "state":
                state,

            "data":
                data or {}

        }


def get_state(chat_id):

    with state_lock:

        return states.get(
            chat_id
        )


def clear_state(chat_id):

    with state_lock:

        states.pop(
            chat_id,
            None
        )


# ============================================================
# STUDENT UI
# ============================================================

def welcome_text():

    return (

        "سلام 👋\n\n"

        "به تیم <b>MIRA</b> خوش اومدی.\n\n"

        "اینجا می‌تونی مسیر مناسب خودت رو انتخاب کنی "
        "و با مشاوره MIRA وارد یک مسیر منظم و قابل پیگیری بشی."

    )


def show_home(chat_id):

    student = get_student(
        chat_id
    )


    if not student:

        send_message(

            chat_id,

            welcome_text(),

            reply_markup=
                registration_start_keyboard()

        )

        return


    send_message(

        chat_id,

        (

            f"خوش اومدی "
            f"<b>{escape_html(student['full_name'])}</b> 👋\n\n"

            "از منوی زیر می‌تونی خدمات MIRA رو مدیریت کنی."

        ),

        reply_markup=
            main_keyboard()

    )


def show_registration_start(
    chat_id
):

    set_state(

        chat_id,

        "registration_name"

    )


    send_message(

        chat_id,

        (

            "بریم برای ساخت پنلت 🚀\n\n"

            "اول <b>نام و نام خانوادگی</b>ت رو وارد کن:"

        ),

        reply_markup=
            remove_keyboard()

    )


def show_registration_grade(
    chat_id,
    data
):

    set_state(

        chat_id,

        "registration_grade",

        data

    )


    send_message(

        chat_id,

        "مقطع تحصیلی‌ات رو انتخاب کن:",

        reply_markup=
            grade_keyboard()

    )


def show_registration_field(
    chat_id,
    data
):

    set_state(

        chat_id,

        "registration_field",

        data

    )


    send_message(

        chat_id,

        "رشته تحصیلی‌ات رو انتخاب کن:",

        reply_markup=
            field_keyboard()

    )


# ============================================================
# PLANS
# ============================================================

def show_plan_list(
    chat_id
):

    buttons = []


    for key, plan in PLANS.items():

        buttons.append(

            [

                {

                    "text":
                        plan["name"],

                    "callback_data":
                        f"plan:{key}"

                }

            ]

        )


    send_message(

        chat_id,

        (

            "<b>✨ پلن‌های مشاوره MIRA</b>\n\n"

            "مسیر مناسب خودت رو انتخاب کن تا جزئیاتش رو ببینی:"

        ),

        reply_markup={

            "inline_keyboard":
                buttons

        }

    )


def show_plan_details(
    chat_id,
    plan_key
):

    plan = PLANS.get(
        plan_key
    )


    if not plan:

        send_message(
            chat_id,
            "این پلن پیدا نشد."
        )

        return


    text = (

        f"<b>{plan['name']}</b>\n\n"

        f"{plan['description']}\n\n"

        f"💰 هزینه سه‌ماهه: "
        f"<b>{format_price(plan['price'])}</b>"

    )


    buttons = [

        [

            {

                "text":
                    "📢 عضویت در کانال مشاوره",

                "url":
                    CONSULTING_CHANNEL_URL

            }

        ],

        [

            {

                "text":
                    "💬 ارتباط مستقیم با پشتیبان",

                "url":
                    SUPPORT_URL

            }

        ],

        [

            {

                "text":
                    "💳 انتخاب این پلن",

                "callback_data":
                    f"select_plan:{plan_key}"

            }

        ]

    ]


    send_message(

        chat_id,

        text,

        reply_markup={

            "inline_keyboard":
                buttons

        }

    )


# ============================================================
# COURSES
# ============================================================

def show_course_channel(
    chat_id
):

    send_message(

        chat_id,

        (

            "<b>🎓 کلاس‌های کنکوری MIRA</b>\n\n"

            "برای اطلاع از کلاس‌ها، زمان شروع و "
            "اطلاعیه‌های مربوط به ثبت‌نام "
            "از کانال کلاس‌های کنکوری MIRA استفاده کن."

        ),

        reply_markup={

            "inline_keyboard": [

                [

                    {

                        "text":
                            "📢 کانال کلاس‌های کنکوری",

                        "url":
                            COURSE_CHANNEL_URL

                    }

                ]

            ]

        }

    )


# ============================================================
# STUDENT PANEL
# ============================================================

def show_my_panel(
    chat_id
):

    student = get_student(
        chat_id
    )


    if not student:

        send_message(

            chat_id,

            "هنوز ثبت‌نامت در MIRA کامل نشده.",

            reply_markup=
                registration_start_keyboard()

        )

        return


    subscription = (
        get_active_subscription(
            chat_id
        )
    )


    text = (

        "<b>👤 پنل من</b>\n\n"

        f"نام و نام خانوادگی: "
        f"<b>{escape_html(student['full_name'])}</b>\n"

        f"شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n"

        f"مقطع: "
        f"{escape_html(student['grade'] or '-')}\n"

        f"رشته: "
        f"{escape_html(student['field'] or '-')}\n"

    )


    if subscription:

        days = remaining_days(

            subscription[
                "expiration_date"
            ]

        )


        text += (

            "\n"

            f"📌 پلن فعال: "
            f"<b>{escape_html(subscription['plan_name'])}</b>\n"

            f"⏳ روزهای باقی‌مانده: "
            f"<b>{days} روز</b>\n"

            f"📅 پایان اشتراک: "
            f"<b>{format_date(subscription['expiration_date'])}</b>\n"

        )


        if subscription.get(
            "consultant"
        ):

            text += (

                f"👤 مشاور / تیم: "
                f"<b>{escape_html(subscription['consultant'])}</b>\n"

            )


    else:

        text += (

            "\n"

            "📌 اشتراک فعال: "
            "<b>نداری</b>\n"

        )


    send_message(

        chat_id,

        text,

        reply_markup={

            "inline_keyboard": [

                [

                    {

                        "text":
                            "📚 پلن‌های مشاوره",

                        "callback_data":
                            "plans"

                    }

                ],

                [

                    {

                        "text":
                            "💳 پرداخت / تمدید",

                        "callback_data":
                            "renew"

                    }

                ],

                [

                    {

                        "text":
                            "🆘 ارتباط با پشتیبان",

                        "url":
                            SUPPORT_URL

                    }

                ]

            ]

        }

    )


# ============================================================
# SUPPORT
# ============================================================

def show_support(
    chat_id
):

    send_message(

        chat_id,

        (

            "<b>🆘 ارتباط با پشتیبان MIRA</b>\n\n"

            "برای ارتباط مستقیم با پشتیبان "
            "روی دکمه زیر بزن."

        ),

        reply_markup={

            "inline_keyboard": [

                [

                    {

                        "text":
                            "💬 ارتباط با @teammira_admin",

                        "url":
                            SUPPORT_URL

                    }

                ]

            ]

        }

    )


# ============================================================
# REGISTRATION SUMMARY
# ============================================================

def registration_summary_text(
    chat_id,
    plan_key
):

    student = get_student(
        chat_id
    )


    plan = PLANS.get(
        plan_key
    )


    statuses = (
        check_all_channel_memberships(
            chat_id,
            force=True
        )
    )


    if not student or not plan:

        return None


    return (

        "<b>📋 خلاصه ثبت‌نام MIRA</b>\n\n"

        f"👤 نام: "
        f"<b>{escape_html(student['full_name'])}</b>\n"

        f"📚 مقطع: "
        f"<b>{escape_html(student['grade'] or '-')}</b>\n"

        f"🧪 رشته: "
        f"<b>{escape_html(student['field'] or '-')}</b>\n"

        f"🔢 شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n\n"

        f"📦 پلن انتخابی: "
        f"<b>{escape_html(plan['name'])}</b>\n"

        f"💰 هزینه: "
        f"<b>{format_price(plan['price'])}</b>\n\n"

        "<b>وضعیت عضویت کانال‌ها:</b>\n"

        f"{'✅' if statuses['main'] else '❌'} "
        "کانال اصلی\n"

        f"{'✅' if statuses['course'] else '❌'} "
        "کانال کلاس‌ها\n"

        f"{'✅' if statuses['consulting'] else '❌'} "
        "کانال مشاوره\n\n"

        "اگر اطلاعات بالا درست است، "
        "برای ادامه روی «تأیید و ادامه پرداخت» بزن."

    )


def show_registration_summary(
    chat_id,
    plan_key
):

    text = registration_summary_text(
        chat_id,
        plan_key
    )


    if not text:

        send_message(
            chat_id,
            "اطلاعات ثبت‌نام یا پلن پیدا نشد."
        )

        return


    set_state(

        chat_id,

        "selected_plan",

        {

            "plan_key":
                plan_key

        }

    )


    send_message(

        chat_id,

        text,

        reply_markup={

            "inline_keyboard": [

                [

                    {

                        "text":
                            "✅ تأیید و ادامه پرداخت",

                        "callback_data":
                            f"confirm_plan:{plan_key}"

                    }

                ],

                [

                    {

                        "text":
                            "🔙 بازگشت به پلن‌ها",

                        "callback_data":
                            "plans"

                    }

                ]

            ]

        }

    )


# ============================================================
# PAYMENT
# ============================================================

def start_payment(
    chat_id,
    plan_key
):

    plan = PLANS.get(
        plan_key
    )


    if not plan:

        send_message(
            chat_id,
            "این پلن در دسترس نیست."
        )

        return


    if not show_all_channels_gate(
        chat_id,
        force=True
    ):

        return


    if plan["price"] <= 0:

        send_message(

            chat_id,

            (

                "قیمت این پلن هنوز در تنظیمات بات ثبت نشده.\n\n"

                "لطفاً با پشتیبان ارتباط بگیر."

            )

        )

        return


    request = create_payment_request(

        chat_id,

        plan_key

    )


    if not request:

        send_message(

            chat_id,

            "در ایجاد درخواست پرداخت مشکلی پیش آمد. دوباره تلاش کن."

        )

        return


    set_state(

        chat_id,

        "waiting_receipt",

        {

            "request_id":
                request["id"],

            "plan_key":
                plan_key,

            "amount":
                plan["price"]

        }

    )


    send_message(

        chat_id,

        (

            f"<b>💳 پرداخت {escape_html(plan['name'])}</b>\n\n"

            f"💰 مبلغ ۳ ماهه:\n"
            f"<b>{format_price(plan['price'])}</b>\n\n"

            f"💳 شماره کارت:\n"
            f"<code>{escape_html(CARD_NUMBER)}</code>\n\n"

            f"👤 به نام:\n"
            f"<b>{escape_html(CARD_OWNER)}</b>\n\n"

            "بعد از واریز، "
            "<b>عکس رسید پرداخت</b> رو همینجا ارسال کن.\n\n"

            "پس از بررسی و تأیید پرداخت، "
            "اشتراکت فعال می‌شه."

        ),

        reply_markup={

            "inline_keyboard": [

                [

                    {

                        "text":
                            "❌ لغو پرداخت",

                        "callback_data":
                            "cancel_payment"

                    }

                ]

            ]

        }

    )


# ============================================================
# ADMIN UI
# ============================================================

def is_admin(
    chat_id
):

    return chat_id in ADMIN_CHAT_IDS


def show_admin_dashboard(
    chat_id
):

    stats = get_admin_stats()


    text = (

        "<b>📊 داشبورد MIRA</b>\n\n"

        f"👥 کل دانش‌آموزان: "
        f"<b>{stats['total_students']}</b>\n"

        f"🆕 ثبت‌نام‌های امروز: "
        f"<b>{stats['new_today']}</b>\n"

        f"📥 کل لیدها: "
        f"<b>{stats['leads']}</b>\n"

        f"🟢 اشتراک‌های فعال: "
        f"<b>{stats['active']}</b>\n"

        f"🔴 اشتراک‌های منقضی: "
        f"<b>{stats['expired']}</b>\n"

        f"💳 پرداخت‌های در انتظار: "
        f"<b>{stats['pending_payments']}</b>"

    )


    send_message(

        chat_id,

        text,

        reply_markup=
            admin_keyboard()

    )


def show_admin_students(
    chat_id
):

    students = get_recent_students(
        20
    )


    if not students:

        send_message(
            chat_id,
            "هنوز دانش‌آموزی ثبت نشده."
        )

        return


    lines = [

        "<b>👥 آخرین دانش‌آموزان</b>\n"

    ]


    for student in students:

        lines.append(

            f"#{student['student_number']} — "
            f"<b>{escape_html(student['full_name'])}</b>\n"

            f"مقطع: "
            f"{escape_html(student['grade'] or '-')}"
            f" | رشته: "
            f"{escape_html(student['field'] or '-')}\n"

            f"📱 "
            f"{escape_html(student['phone'] or '-')}\n"

        )


    send_message(

        chat_id,

        "\n".join(lines)

    )


def show_pending_payments(
    chat_id
):

    payments = get_pending_payments(
        15
    )


    if not payments:

        send_message(

            chat_id,

            "در حال حاضر پرداخت در انتظاری وجود ندارد."

        )

        return


    for payment in payments:

        plan = PLANS.get(
            payment["plan_key"]
        )


        plan_name = (

            plan["name"]

            if plan

            else payment["plan_key"]

        )


        text = (

            "<b>💳 درخواست پرداخت</b>\n\n"

            f"شماره دانش‌آموزی: "
            f"<b>{payment.get('student_number') or '-'}</b>\n"

            f"نام: "
            f"<b>{escape_html(payment.get('full_name') or '-')}</b>\n"

            f"پلن: "
            f"<b>{escape_html(plan_name)}</b>\n"

            f"مبلغ: "
            f"<b>{format_price(payment['amount'])}</b>\n"

            f"شناسه پرداخت: "
            f"<code>{payment['id']}</code>"

        )


        buttons = {

            "inline_keyboard": [

                [

                    {

                        "text":
                            "✅ تأیید",

                        "callback_data":
                            f"approve:{payment['id']}"

                    },

                    {

                        "text":
                            "❌ رد",

                        "callback_data":
                            f"reject:{payment['id']}"

                    }

                ]

            ]

        }


        send_message(

            chat_id,

            text,

            reply_markup=
                buttons

        )


# ============================================================
# ADMIN NOTIFICATIONS
# ============================================================

def notify_admins_about_registration(
    chat_id,
    plan_key=None
):

    student = get_student(
        chat_id
    )


    if not student:
        return


    statuses = (
        check_all_channel_memberships(
            chat_id,
            force=True
        )
    )


    plan = (
        PLANS.get(plan_key)
        if plan_key
        else None
    )


    text = (

        "<b>🆕 ثبت‌نام جدید MIRA</b>\n\n"

        f"🔢 شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n"

        f"👤 نام: "
        f"<b>{escape_html(student['full_name'])}</b>\n"

        f"📱 شماره: "
        f"<b>{escape_html(student['phone'] or '-')}</b>\n"

        f"📚 مقطع: "
        f"<b>{escape_html(student['grade'] or '-')}</b>\n"

        f"🧪 رشته: "
        f"<b>{escape_html(student['field'] or '-')}</b>\n"

    )


    if plan:

        text += (

            f"\n📦 پلن انتخابی: "
            f"<b>{escape_html(plan['name'])}</b>\n"

            f"💰 مبلغ: "
            f"<b>{format_price(plan['price'])}</b>\n"

        )


    text += (

        "\n<b>عضویت کانال‌ها:</b>\n"

        f"{'✅' if statuses['main'] else '❌'} اصلی\n"

        f"{'✅' if statuses['course'] else '❌'} کلاس‌ها\n"

        f"{'✅' if statuses['consulting'] else '❌'} مشاوره\n"

    )


    for admin_id in ADMIN_CHAT_IDS:

        send_message(
            admin_id,
            text
        )


def notify_admins_about_payment(
    payment_id,
    chat_id,
    plan_key,
    amount,
    photo_bytes=None
):

    student = get_student(
        chat_id
    )


    plan = PLANS.get(
        plan_key
    )


    student_name = (

        student["full_name"]

        if student

        else "نامشخص"

    )


    student_number = (

        student["student_number"]

        if student

        else "-"

    )


    text = (

        "<b>💳 رسید پرداخت جدید MIRA</b>\n\n"

        f"👤 نام: "
        f"<b>{escape_html(student_name)}</b>\n"

        f"🔢 شماره دانش‌آموزی: "
        f"<b>{student_number}</b>\n"

        f"📦 پلن: "
        f"<b>{escape_html(plan['name'] if plan else plan_key)}</b>\n"

        f"💰 مبلغ: "
        f"<b>{format_price(amount)}</b>\n"

        f"🆔 Payment ID: "
        f"<code>{payment_id}</code>"

    )


    buttons = {

        "inline_keyboard": [

            [

                {

                    "text":
                        "✅ تأیید پرداخت",

                    "callback_data":
                        f"approve:{payment_id}"

                },

                {

                    "text":
                        "❌ رد پرداخت",

                    "callback_data":
                        f"reject:{payment_id}"

                }

            ]

        ]

    }


    for admin_id in ADMIN_CHAT_IDS:

        if photo_bytes:

            send_photo(

                admin_id,

                photo_bytes,

                caption=text,

                reply_markup=
                    buttons

            )

        else:

            send_message(

                admin_id,

                text,

                reply_markup=
                    buttons

            )


def notify_consultant(
    chat_id,
    plan_key,
    result
):

    consultant = CONSULTANTS.get(
        plan_key,
        {}
    )


    username = (
        consultant.get(
            "username",
            ""
        )
        .strip()
    )


    student = get_student(
        chat_id
    )


    if not student:
        return


    text = (

        "<b>🎓 دانش‌آموز جدید برای اتصال</b>\n\n"

        f"👤 نام: "
        f"<b>{escape_html(student['full_name'])}</b>\n"

        f"🔢 شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n"

        f"📚 مقطع: "
        f"<b>{escape_html(student['grade'] or '-')}</b>\n"

        f"🧪 رشته: "
        f"<b>{escape_html(student['field'] or '-')}</b>\n"

        f"📦 پلن: "
        f"<b>{escape_html(result['plan_name'])}</b>\n"

        f"📱 شماره: "
        f"<b>{escape_html(student['phone'] or '-')}</b>\n"

    )


    if username:

        try:

            consultant_chat = (
                username.lstrip("@")
            )


            send_message(

                f"@{consultant_chat}",

                text

            )


        except Exception as exc:

            print(

                f"[MIRA] consultant notification error: {exc}",

                flush=True

            )


    for admin_id in ADMIN_CHAT_IDS:

        send_message(

            admin_id,

            (

                text

                + "\n"

                "ℹ️ لطفاً دانش‌آموز را به مشاور/منتور "
                "مربوط به این پلن متصل کنید."

            )

        )


# ============================================================
# REGISTRATION STATE
# ============================================================

def handle_registration_state(
    chat_id,
    message
):

    current = get_state(
        chat_id
    )


    if not current:
        return False


    state = current["state"]

    data = current["data"]

    text = message.get(
        "text",
        ""
    ).strip()


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if state == "registration_name":

        if len(text) < 3:

            send_message(

                chat_id,

                "لطفاً نام و نام خانوادگی کاملت رو وارد کن."

            )

            return True


        data["full_name"] = text


        show_registration_grade(

            chat_id,

            data

        )


        return True


    # --------------------------------------------------------
    # GRADE
    # --------------------------------------------------------

    if state == "registration_grade":

        valid_grades = {

            "دهم",

            "یازدهم",

            "دوازدهم",

            "فارغ‌التحصیل",

            "پشت‌کنکوری"

        }


        if text not in valid_grades:

            send_message(

                chat_id,

                "لطفاً یکی از گزینه‌های مقطع را انتخاب کن.",

                reply_markup=
                    grade_keyboard()

            )

            return True


        data["grade"] = text


        show_registration_field(

            chat_id,

            data

        )


        return True


    # --------------------------------------------------------
    # FIELD
    # --------------------------------------------------------

    if state == "registration_field":

        valid_fields = {

            "تجربی",

            "ریاضی",

            "انسانی",

            "فنی‌وحرفه‌ای",

            "هنر",

            "سایر"

        }


        if text not in valid_fields:

            send_message(

                chat_id,

                "لطفاً یکی از گزینه‌های رشته را انتخاب کن.",

                reply_markup=
                    field_keyboard()

            )

            return True


        data["field"] = text


        set_state(

            chat_id,

            "registration_phone",

            data

        )


        send_message(

            chat_id,

            (

                "آخرین مرحله 👌\n\n"

                "برای تکمیل ثبت‌نام، شماره تلفنت رو "
                "با دکمه زیر برای بات ارسال کن."

            ),

            reply_markup=
                contact_keyboard()

        )


        return True


    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    if state == "registration_phone":

        contact = message.get(
            "contact"
        )


        if not contact:

            send_message(

                chat_id,

                (

                    "برای تکمیل ثبت‌نام باید شماره تلفنت رو "
                    "با دکمه «ارسال شماره تلفن» ارسال کنی."

                ),

                reply_markup=
                    contact_keyboard()

            )

            return True


        contact_user_id = contact.get(
            "user_id"
        )


        if (
            contact_user_id
            and
            contact_user_id != chat_id
        ):

            send_message(

                chat_id,

                "لطفاً شماره تلفن خودت رو ارسال کن، نه شماره شخص دیگر."

            )

            return True


        phone = contact.get(
            "phone_number",
            ""
        ).strip()


        if not phone:

            send_message(

                chat_id,

                "شماره تلفن دریافت نشد. دوباره تلاش کن."

            )

            return True


        student_number = create_student(

            chat_id=chat_id,

            full_name=data["full_name"],

            grade=data["grade"],

            field=data["field"],

            phone=phone,

            username=message.get(
                "from",
                {}
            ).get(
                "username"
            )

        )


        clear_state(
            chat_id
        )


        send_message(

            chat_id,

            (

                "اطلاعاتت با موفقیت ثبت شد. ✅\n\n"

                f"🔢 شماره دانش‌آموزی تو: "
                f"<b>{student_number}</b>\n\n"

                "حالا برای ادامه باید عضویتت در "
                "هر ۳ کانال MIRA تأیید بشه."

            ),

            reply_markup=
                remove_keyboard()

        )


        show_all_channels_gate(

            chat_id,

            force=True

        )


        return True


    # --------------------------------------------------------
    # WAITING RECEIPT
    # --------------------------------------------------------

    if state == "waiting_receipt":

        photo = message.get(
            "photo"
        )


        if not photo:

            send_message(

                chat_id,

                (

                    "لطفاً عکس رسید پرداخت رو ارسال کن.\n\n"

                    "اگر قصد لغو داری، "
                    "از گزینه «لغو پرداخت» استفاده کن."

                )

            )

            return True


        largest_photo = photo[-1]


        file_id = largest_photo.get(
            "file_id"
        )


        if not file_id:

            send_message(

                chat_id,

                "دریافت رسید با مشکل مواجه شد. دوباره ارسال کن."

            )

            return True


        payment_id = create_payment(

            chat_id=chat_id,

            request_id=data.get(
                "request_id"
            ),

            plan_key=data.get(
                "plan_key"
            ),

            amount=data.get(
                "amount",
                0
            ),

            file_id=file_id

        )


        if not payment_id:

            send_message(

                chat_id,

                "ثبت رسید با مشکل مواجه شد. لطفاً دوباره تلاش کن."

            )

            return True


        clear_state(
            chat_id
        )


        send_message(

            chat_id,

            (

                "رسیدت با موفقیت دریافت شد. ✅\n\n"

                "رسید برای تیم MIRA ارسال شد و بعد از تأیید، "
                "اشتراکت فعال می‌شه."

            ),

            reply_markup=
                main_keyboard()

        )


        photo_bytes = download_telegram_file(
            file_id
        )


        notify_admins_about_payment(

            payment_id=payment_id,

            chat_id=chat_id,

            plan_key=data.get(
                "plan_key"
            ),

            amount=data.get(
                "amount",
                0
            ),

            photo_bytes=photo_bytes

        )


        return True


    return False


# ============================================================
# MESSAGE HANDLING
# ============================================================

def handle_message(
    message
):

    chat = message.get(
        "chat"
    )


    if not chat:
        return


    chat_id = chat.get(
        "id"
    )


    if not chat_id:
        return


    text = message.get(
        "text",
        ""
    )


    # ========================================================
    # ADMIN
    # ========================================================

    if is_admin(
        chat_id
    ):


        if text == "/admin":

            clear_state(
                chat_id
            )


            send_message(

                chat_id,

                "پنل مدیریت MIRA",

                reply_markup=
                    admin_keyboard()

            )


            return


        if text == "📊 داشبورد":

            show_admin_dashboard(
                chat_id
            )

            return


        if text == "👥 دانش‌آموزان":

            show_admin_students(
                chat_id
            )

            return


        if text == "💳 پرداخت‌های در انتظار":

            show_pending_payments(
                chat_id
            )

            return


        if text == "🏠 خروج از پنل ادمین":

            send_message(

                chat_id,

                "از پنل مدیریت خارج شدی.",

                reply_markup=
                    main_keyboard()

            )

            return


    # ========================================================
    # START
    # ========================================================

    if text.startswith(
        "/start"
    ):


        if not require_main_membership(
            chat_id
        ):

            return


        student = get_student(
            chat_id
        )


        clear_state(
            chat_id
        )


        if student:

            show_home(
                chat_id
            )

        else:

            send_message(

                chat_id,

                welcome_text(),

                reply_markup=
                    registration_start_keyboard()

            )


        return


    # ========================================================
    # MAIN CHANNEL GATE
    # ========================================================

    if not require_main_membership(
        chat_id
    ):

        return


    # ========================================================
    # STATES
    # ========================================================

    if handle_registration_state(

        chat_id,

        message

    ):

        return


    # ========================================================
    # REGISTRATION
    # ========================================================

    if text == "🚀 بزن بریم":

        show_registration_start(
            chat_id
        )

        return


    # ========================================================
    # PLANS
    # ========================================================

    if text == "📚 پلن‌های مشاوره":

        if not get_student(
            chat_id
        ):

            show_home(
                chat_id
            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        show_plan_list(
            chat_id
        )

        return


    # ========================================================
    # PAYMENT
    # ========================================================

    if text == "💳 پرداخت و تمدید":

        if not get_student(
            chat_id
        ):

            show_home(
                chat_id
            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        show_plan_list(
            chat_id
        )

        return


    # ========================================================
    # COURSES
    # ========================================================

    if text == "🎓 کلاس‌های کنکوری":

        show_course_channel(
            chat_id
        )

        return


    # ========================================================
    # SUPPORT
    # ========================================================

    if text == "🆘 ارتباط با پشتیبان":

        show_support(
            chat_id
        )

        return


    # ========================================================
    # MY PANEL
    # ========================================================

    if text == "👤 پنل من":

        show_my_panel(
            chat_id
        )

        return


    # ========================================================
    # FALLBACK
    # ========================================================

    send_message(

        chat_id,

        "از منوی زیر می‌تونی بخش موردنظرت رو انتخاب کنی. 👇",

        reply_markup=
            main_keyboard()

    )


# ============================================================
# CALLBACKS
# ============================================================

def handle_callback(
    callback
):

    callback_id = callback.get(
        "id"
    )

    data = callback.get(
        "data"
    )

    message = callback.get(
        "message"
    )


    if not message:

        answer_callback(
            callback_id
        )

        return


    chat = message.get(
        "chat"
    )


    if not chat:

        answer_callback(
            callback_id
        )

        return


    chat_id = chat.get(
        "id"
    )


    answer_callback(
        callback_id
    )


    # ========================================================
    # MAIN CHANNEL CHECK
    # ========================================================

    if data == "check_membership":


        if check_main_membership(

            chat_id,

            force=True

        ):


            student = get_student(
                chat_id
            )


            if student:

                show_home(
                    chat_id
                )

            else:

                send_message(

                    chat_id,

                    (

                        "عضویتت در کانال اصلی تأیید شد. ✅\n\n"

                        "برای شروع ثبت‌نام روی "
                        "«بزن بریم» بزن."

                    ),

                    reply_markup=
                        registration_start_keyboard()

                )


        else:

            send_message(

                chat_id,

                (

                    "هنوز عضویتت در کانال اصلی تأیید نشده.\n\n"

                    "اول عضو کانال شو و دوباره "
                    "«بررسی عضویت» رو بزن."

                ),

                reply_markup=
                    membership_keyboard()

            )


        return


    # ========================================================
    # MAIN MEMBERSHIP REQUIRED
    # ========================================================

    if not require_main_membership(
        chat_id
    ):

        return


    # ========================================================
    # START REGISTRATION
    # ========================================================

    if data == "start_registration":


        student = get_student(
            chat_id
        )


        if student:

            show_home(
                chat_id
            )

            return


        show_registration_start(
            chat_id
        )

        return


    # ========================================================
    # ALL CHANNELS
    # ========================================================

    if data == "check_all_channels":


        if show_all_channels_gate(

            chat_id,

            force=True

        ):


            clear_state(
                chat_id
            )


            send_message(

                chat_id,

                (

                    "عضویت هر ۳ کانال با موفقیت تأیید شد. "
                    "✅🎉\n\n"

                    "حالا می‌تونی پلن موردنظرت رو انتخاب کنی."

                ),

                reply_markup=
                    main_keyboard()

            )


            show_plan_list(
                chat_id
            )


        return


    # ========================================================
    # PLANS
    # ========================================================

    if data == "plans":


        if not get_student(
            chat_id
        ):

            send_message(

                chat_id,

                "ابتدا ثبت‌نامت رو کامل کن.",

                reply_markup=
                    registration_start_keyboard()

            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        show_plan_list(
            chat_id
        )

        return


    if data.startswith(
        "plan:"
    ):


        if not get_student(
            chat_id
        ):

            send_message(

                chat_id,

                "ابتدا ثبت‌نامت رو کامل کن.",

                reply_markup=
                    registration_start_keyboard()

            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        plan_key = data.split(
            ":",
            1
        )[1]


        show_plan_details(

            chat_id,

            plan_key

        )

        return


    # ========================================================
    # SELECT PLAN
    # ========================================================

    if data.startswith(
        "select_plan:"
    ):


        if not get_student(
            chat_id
        ):

            send_message(

                chat_id,

                "ابتدا ثبت‌نامت رو کامل کن.",

                reply_markup=
                    registration_start_keyboard()

            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        plan_key = data.split(
            ":",
            1
        )[1]


        if plan_key not in PLANS:

            send_message(
                chat_id,
                "این پلن پیدا نشد."
            )

            return


        show_registration_summary(

            chat_id,

            plan_key

        )

        return


    # ========================================================
    # CONFIRM PLAN
    # ========================================================

    if data.startswith(
        "confirm_plan:"
    ):


        if not get_student(
            chat_id
        ):

            send_message(

                chat_id,

                "اطلاعات ثبت‌نامت پیدا نشد.",

                reply_markup=
                    main_keyboard()

            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        plan_key = data.split(
            ":",
            1
        )[1]


        if plan_key not in PLANS:

            send_message(
                chat_id,
                "این پلن پیدا نشد."
            )

            return


        notify_admins_about_registration(

            chat_id,

            plan_key

        )


        start_payment(

            chat_id,

            plan_key

        )


        return


    # ========================================================
    # RENEW
    # ========================================================

    if data == "renew":


        if not get_student(
            chat_id
        ):

            show_home(
                chat_id
            )

            return


        if not show_all_channels_gate(

            chat_id,

            force=True

        ):

            return


        show_plan_list(
            chat_id
        )

        return


    # ========================================================
    # CANCEL PAYMENT
    # ========================================================

    if data == "cancel_payment":


        clear_state(
            chat_id
        )


        send_message(

            chat_id,

            "پرداخت لغو شد.",

            reply_markup=
                main_keyboard()

        )


        return


    # ========================================================
    # PAYMENT DIRECT
    # ========================================================

    if data.startswith(
        "pay:"
    ):


        plan_key = data.split(
            ":",
            1
        )[1]


        start_payment(

            chat_id,

            plan_key

        )


        return


    # ========================================================
    # APPROVE PAYMENT
    # ========================================================

    if data.startswith(
        "approve:"
    ):


        if not is_admin(
            chat_id
        ):

            return


        try:

            payment_id = int(

                data.split(
                    ":",
                    1
                )[1]

            )

        except ValueError:

            return


        result = approve_payment(
            payment_id
        )


        if not result:

            send_message(

                chat_id,

                "این پرداخت قبلاً بررسی شده یا پیدا نشد."

            )

            return


        user_chat_id = result[
            "chat_id"
        ]


        consultant = CONSULTANTS.get(

            result[
                "plan_key"
            ],

            {}

        )


        consultant_name = (
            result.get(
                "consultant"
            )
            or
            consultant.get(
                "name",
                "تیم MIRA"
            )
        )


        consultant_username = (
            consultant.get(
                "username",
                ""
            ).strip()
        )


        consultant_line = (

            f"👤 مشاور / تیم: "
            f"<b>{escape_html(consultant_name)}</b>\n"

        )


        if consultant_username:

            consultant_line += (

                f"💬 ارتباط مشاور: "
                f"<b>@{escape_html(consultant_username.lstrip('@'))}</b>\n"

            )


        send_message(

            user_chat_id,

            (

                "پرداختت تأیید شد. ✅🎉\n\n"

                f"پلن "
                f"<b>{escape_html(result['plan_name'])}</b> "
                "برای تو فعال شد.\n\n"

                f"📅 شروع: "
                f"<b>{format_date(result['start'].isoformat())}</b>\n"

                f"📅 پایان: "
                f"<b>{format_date(result['expiration'].isoformat())}</b>\n"

                f"{consultant_line}\n"

                "اطلاعاتت برای تیم مربوط به پلنت هم ارسال شد."

            ),

            reply_markup={

                "inline_keyboard": [

                    [

                        {

                            "text":
                                "💬 ارتباط با پشتیبان",

                            "url":
                                SUPPORT_URL

                        }

                    ]

                ]

            }

        )


        notify_consultant(

            user_chat_id,

            result[
                "plan_key"
            ],

            result

        )


        send_message(

            chat_id,

            (

                f"پرداخت #{payment_id} "
                "تأیید شد و اشتراک فعال شد. ✅\n\n"

                f"پلن: "
                f"<b>{escape_html(result['plan_name'])}</b>\n"

                f"مشاور/تیم: "
                f"<b>{escape_html(consultant_name)}</b>"

            )

        )


        return


    # ========================================================
    # REJECT PAYMENT
    # ========================================================

    if data.startswith(
        "reject:"
    ):


        if not is_admin(
            chat_id
        ):

            return


        try:

            payment_id = int(

                data.split(
                    ":",
                    1
                )[1]

            )

        except ValueError:

            return


        payment = reject_payment(
            payment_id
        )


        if not payment:

            send_message(

                chat_id,

                "این پرداخت قبلاً بررسی شده یا پیدا نشد."

            )

            return


        send_message(

            payment[
                "chat_id"
            ],

            (

                "رسید پرداختت توسط تیم MIRA تأیید نشد. ❌\n\n"

                "اگر فکر می‌کنی اشتباهی رخ داده، "
                "با پشتیبان مستقیم ارتباط بگیر."

            ),

            reply_markup={

                "inline_keyboard": [

                    [

                        {

                            "text":
                                "💬 ارتباط با پشتیبان",

                            "url":
                                SUPPORT_URL

                        }

                    ]

                ]

            }

        )


        send_message(

            chat_id,

            f"پرداخت #{payment_id} رد شد."

        )


        return


# ============================================================
# UPDATE PROCESSING
# ============================================================

def process_update(
    update
):

    try:

        if "message" in update:

            handle_message(
                update["message"]
            )


        elif "callback_query" in update:

            handle_callback(
                update["callback_query"]
            )


    except Exception as exc:

        print(

            f"[MIRA] update error: "
            f"{type(exc).__name__}: {exc}",

            flush=True

        )


# ============================================================
# WEBHOOK SERVER
# ============================================================

class WebhookHandler(
    BaseHTTPRequestHandler
):


    def log_message(
        self,
        format,
        *args
    ):

        return


    def do_GET(
        self
    ):

        if self.path == "/health":

            body = b"MIRA BOT OK"

        else:

            body = b"MIRA BOT"


        self.send_response(
            200
        )


        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )


        self.send_header(
            "Content-Length",
            str(len(body))
        )


        self.end_headers()


        self.wfile.write(
            body
        )


    def do_POST(
        self
    ):


        if self.path != "/telegram-webhook":

            self.send_response(
                404
            )

            self.end_headers()

            return


        try:

            content_length = int(

                self.headers.get(
                    "Content-Length",
                    "0"
                )

            )


            raw_body = self.rfile.read(
                content_length
            )


            update = json.loads(

                raw_body.decode(
                    "utf-8"
                )

            )


            self.send_response(
                200
            )


            self.send_header(
                "Content-Type",
                "text/plain"
            )


            self.end_headers()


            self.wfile.write(
                b"OK"
            )


            thread = threading.Thread(

                target=process_update,

                args=(update,),

                daemon=True

            )


            thread.start()


        except Exception as exc:

            print(

                f"[MIRA] webhook error: "
                f"{type(exc).__name__}: {exc}",

                flush=True

            )


            try:

                self.send_response(
                    500
                )

                self.end_headers()

            except Exception:

                pass


# ============================================================
# WEBHOOK SETUP
# ============================================================

def setup_webhook():

    if not RENDER_EXTERNAL_URL:

        print(

            "[MIRA] RENDER_EXTERNAL_URL is not set.",

            flush=True

        )

        return


    webhook_url = (
        f"{RENDER_EXTERNAL_URL}"
        f"/telegram-webhook"
    )


    result = telegram(

        "setWebhook",

        {

            "url":
                webhook_url,

            "drop_pending_updates":
                True,

            "allowed_updates": [

                "message",

                "callback_query"

            ]

        },

        timeout=15

    )


    if result:

        print(

            f"[MIRA] Webhook set: "
            f"{webhook_url}",

            flush=True

        )

    else:

        print(

            "[MIRA] Failed to set webhook.",

            flush=True

        )


# ============================================================
# CONFIG VALIDATION
# ============================================================

def validate_config():

    if not BOT_TOKEN:

        print(

            "[MIRA] ERROR: BOT_TOKEN is missing.",

            flush=True

        )


    if not ADMIN_CHAT_IDS:

        print(

            "[MIRA] WARNING: ADMIN_CHAT_IDS is empty.",

            flush=True

        )


    if not SUPPORT_USERNAME:

        print(

            "[MIRA] WARNING: SUPPORT_USERNAME is empty.",

            flush=True

        )


    missing_prices = []


    if PLANS["task"]["price"] <= 0:

        missing_prices.append(
            "PLAN_TASK_PRICE"
        )


    if PLANS["task_mentoring"]["price"] <= 0:

        missing_prices.append(
            "PLAN_TASK_MENTORING_PRICE"
        )


    if PLANS["360"]["price"] <= 0:

        missing_prices.append(
            "PLAN_360_PRICE"
        )


    if missing_prices:

        print(

            "[MIRA] WARNING: Plan prices "
            "are not configured: "
            + ", ".join(
                missing_prices
            ),

            flush=True

        )


    print(

        f"[MIRA] Main channel: "
        f"{CHANNEL_USERNAME}",

        flush=True

    )


    print(

        f"[MIRA] Course channel: "
        f"{COURSE_CHANNEL_USERNAME}",

        flush=True

    )


    print(

        f"[MIRA] Consulting channel: "
        f"{CONSULTING_CHANNEL_USERNAME}",

        flush=True

    )


    print(

        f"[MIRA] Support: "
        f"{SUPPORT_USERNAME}",

        flush=True

    )


# ============================================================
# STARTUP
# ============================================================

def main():

    print(
        "[MIRA] Starting MIRA Bot...",
        flush=True
    )


    validate_config()


    init_db()


    setup_webhook()


    server = ThreadingHTTPServer(

        ("0.0.0.0", PORT),

        WebhookHandler

    )


    print(

        f"[MIRA] Server running "
        f"on port {PORT}",

        flush=True

    )


    server.serve_forever()


if __name__ == "__main__":

    main()
