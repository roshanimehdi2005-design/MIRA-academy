import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


# ============================================================
# MIRA BOT - NEW ARCHITECTURE
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
}

PORT = int(os.environ.get("PORT", "10000"))
DB_PATH = os.environ.get("DB_PATH", "mira.db")

CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@miracampus")
CHANNEL_URL = os.environ.get(
    "CHANNEL_URL",
    "https://t.me/miracampus"
)

CARD_NUMBER = os.environ.get(
    "CARD_NUMBER",
    "6219861940398554"
)

CARD_OWNER = os.environ.get(
    "CARD_OWNER",
    "محمد مهدی روشنی"
)

COURSE_CHANNEL_URL = os.environ.get(
    "COURSE_CHANNEL_URL",
    "https://t.me/mirakunkorclss"
)

CONSULTING_CHANNEL_URL = os.environ.get(
    "CONSULTING_CHANNEL_URL",
    "https://t.me/miraprivatecahnnel"
)

RENDER_EXTERNAL_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    ""
).rstrip("/")


# ============================================================
# PLANS
# ============================================================
# قیمت‌ها از Environment Variable خوانده می‌شوند.
# این کار باعث می‌شود قیمت‌های قدیمی بات دوباره وارد سیستم نشوند.
#
# PLAN_TASK_PRICE
# PLAN_TASK_MENTORING_PRICE
# PLAN_360_PRICE
#
# اعداد به تومان هستند.

def env_price(name):
    value = os.environ.get(name, "").strip()

    if not value:
        return 0

    try:
        return int(value)
    except ValueError:
        return 0


PLANS = {
    "task": {
        "name": "پلن تسک‌محور",
        "description": (
            "مسیر مشاوره بر پایه تسک‌های مشخص و قابل پیگیری؛ "
            "برای دانش‌آموزی که می‌خواهد برنامه اجرایی و پیگیری منظم داشته باشد."
        ),
        "price": env_price("PLAN_TASK_PRICE"),
        "channel_url": CONSULTING_CHANNEL_URL,
    },

    "task_mentoring": {
        "name": "پلن تسک‌محور + منتورینگ",
        "description": (
            "ترکیب برنامه و تسک‌های اجرایی با همراهی و منتورینگ؛ "
            "برای دانش‌آموزی که علاوه بر برنامه، به پیگیری و همراهی بیشتری نیاز دارد."
        ),
        "price": env_price("PLAN_TASK_MENTORING_PRICE"),
        "channel_url": CONSULTING_CHANNEL_URL,
    },

    "360": {
        "name": "پلن 360",
        "description": (
            "جامع‌ترین مسیر مشاوره MIRA برای مدیریت کامل‌تر مسیر تحصیلی، "
            "برنامه‌ریزی، پیگیری و همراهی."
        ),
        "price": env_price("PLAN_360_PRICE"),
        "channel_url": CONSULTING_CHANNEL_URL,
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
    "User-Agent": "MIRA-Bot/2.0"
})


def telegram(method, payload=None, files=None, timeout=10):
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
            return None

        data = response.json()

        if not data.get("ok"):
            return None

        return data.get("result")

    except requests.RequestException:
        return None

    except Exception:
        return None


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


def answer_callback(callback_id):
    if not callback_id:
        return

    telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        },
        timeout=5
    )


def get_file(file_id):
    return telegram(
        "getFile",
        {"file_id": file_id},
        timeout=8
    )


def download_telegram_file(file_id):
    file_info = get_file(file_id)

    if not file_info:
        return None

    file_path = file_info.get("file_path")

    if not file_path:
        return None

    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    try:
        response = SESSION.get(
            url,
            timeout=15
        )

        if response.status_code != 200:
            return None

        return response.content

    except requests.RequestException:
        return None


def send_photo(chat_id, photo, caption=None, reply_markup=None):
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
        "photo": ("receipt.jpg", photo)
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

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")

    return conn


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


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


def table_columns(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def add_column_if_missing(conn, table, column, definition):
    columns = table_columns(conn, table)

    if column not in columns:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def migrate_old_database(conn):
    """
    Migration محافظه‌کارانه برای دیتابیس قدیمی.
    اطلاعات اصلی کاربران حفظ می‌شود.
    """

    # students
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

    # اگر دیتابیس قدیمی goal/problem/notes داشته باشد
    # دست نمی‌زنیم؛ حذفشان لازم نیست و روی عملکرد اثر خاصی ندارند.

    # اختصاص شماره دانش‌آموزی به کاربران قدیمی
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
        SELECT MAX(student_number) AS max_number
        FROM mira_students
        """
    ).fetchone()

    next_number = (
        (max_number_row["max_number"] or 0) + 1
        if max_number_row
        else 1
    )

    for row in rows:
        conn.execute(
            """
            UPDATE mira_students
            SET student_number = ?
            WHERE chat_id = ?
            """,
            (next_number, row["chat_id"])
        )

        next_number += 1

    # اطمینان از وجود جدول‌های جدید
    # در init_db ساخته شده‌اند.


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

            return dict(row) if row else None

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
                    SELECT COALESCE(MAX(student_number), 0) + 1 AS next_number
                    FROM mira_students
                    """
                ).fetchone()

                student_number = row["next_number"]

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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def get_latest_subscription(chat_id):
    with DB_LOCK:
        conn = get_db()

        try:
            row = conn.execute(
                """
                SELECT *
                FROM mira_subscriptions
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (chat_id,)
            ).fetchone()

            return dict(row) if row else None

        finally:
            conn.close()


def create_payment_request(chat_id, plan_key):
    plan = PLANS.get(plan_key)

    if not plan:
        return None

    created_at = now_iso()

    with DB_LOCK:
        conn = get_db()

        try:
            # جلوگیری از ایجاد چند درخواست همزمان برای یک کاربر
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
                return dict(pending)

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
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
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

            request_id = cursor.lastrowid

            conn.commit()

            row = conn.execute(
                """
                SELECT *
                FROM mira_payment_requests
                WHERE id = ?
                """,
                (request_id,)
            ).fetchone()

            return dict(row)

        finally:
            conn.close()


def create_payment(chat_id, request_id, plan_key, amount, file_id):
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
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
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

            payment_id = cursor.lastrowid

            conn.commit()

            return payment_id

        finally:
            conn.close()


def get_payment(payment_id):
    with DB_LOCK:
        conn = get_db()

        try:
            row = conn.execute(
                """
                SELECT *
                FROM mira_payments
                WHERE id = ?
                """,
                (payment_id,)
            ).fetchone()

            return dict(row) if row else None

        finally:
            conn.close()


def approve_payment(payment_id, consultant=""):
    with DB_LOCK:
        conn = get_db()

        try:
            payment = conn.execute(
                """
                SELECT *
                FROM mira_payments
                WHERE id = ?
                """,
                (payment_id,)
            ).fetchone()

            if not payment:
                return None

            if payment["status"] != "PENDING":
                return None

            request = None

            if payment["request_id"]:
                request = conn.execute(
                    """
                    SELECT *
                    FROM mira_payment_requests
                    WHERE id = ?
                    """,
                    (payment["request_id"],)
                ).fetchone()

            plan_key = payment["plan_key"]

            plan = PLANS.get(plan_key)

            if not plan:
                return None

            # قیمت فعلی پلن
            # مبلغ ذخیره‌شده در Payment همان مبلغ زمان درخواست است.
            amount = payment["amount"]

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
                (payment["chat_id"],)
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

            expiration = start + timedelta(days=90)

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
                VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
                """,
                (
                    payment["chat_id"],
                    plan["name"],
                    plan["name"],
                    start.isoformat(timespec="seconds"),
                    expiration.isoformat(timespec="seconds"),
                    consultant or None,
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

            if request:
                conn.execute(
                    """
                    UPDATE mira_payment_requests
                    SET status = 'APPROVED',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now_iso(),
                        request["id"]
                    )
                )

            conn.commit()

            return {
                "chat_id": payment["chat_id"],
                "plan_key": plan_key,
                "plan_name": plan["name"],
                "start": start,
                "expiration": expiration,
                "amount": amount,
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
                (payment_id,)
            ).fetchone()

            if not payment:
                return None

            if payment["status"] != "PENDING":
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
# ADMIN STATS
# ============================================================

def get_admin_stats():
    with DB_LOCK:
        conn = get_db()

        try:
            total_students = conn.execute(
                "SELECT COUNT(*) AS c FROM mira_students"
            ).fetchone()["c"]

            today = datetime.now().date().isoformat()

            new_today = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_students
                WHERE substr(created_at, 1, 10) = ?
                """,
                (today,)
            ).fetchone()["c"]

            active = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_subscriptions
                WHERE status = 'ACTIVE'
                  AND expiration_date > ?
                """,
                (datetime.now().isoformat(),)
            ).fetchone()["c"]

            expired = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_subscriptions
                WHERE expiration_date <= ?
                """,
                (datetime.now().isoformat(),)
            ).fetchone()["c"]

            pending_payments = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_payments
                WHERE status = 'PENDING'
                """
            ).fetchone()["c"]

            open_support = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_support_requests
                WHERE status = 'OPEN'
                """
            ).fetchone()["c"]

            leads = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mira_leads
                """
            ).fetchone()["c"]

            return {
                "total_students": total_students,
                "new_today": new_today,
                "active": active,
                "expired": expired,
                "pending_payments": pending_payments,
                "open_support": open_support,
                "leads": leads,
            }

        finally:
            conn.close()


def get_recent_students(limit=15):
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
                (limit,)
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()


def get_pending_payments(limit=15):
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
                (limit,)
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()


# ============================================================
# SUPPORT
# ============================================================

def create_support_request(chat_id, message):
    created_at = now_iso()

    with DB_LOCK:
        conn = get_db()

        try:
            cursor = conn.execute(
                """
                INSERT INTO mira_support_requests (
                    chat_id,
                    message,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 'OPEN', ?, ?)
                """,
                (
                    chat_id,
                    message,
                    created_at,
                    created_at
                )
            )

            request_id = cursor.lastrowid

            conn.commit()

            return request_id

        finally:
            conn.close()


# ============================================================
# DATE HELPERS
# ============================================================

def parse_datetime(value):
    if not value:
        return datetime.min

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def format_price(amount):
    if not amount:
        return "قیمت هنوز تنظیم نشده"

    return f"{amount:,} تومان"


def remaining_days(expiration):
    delta = parse_datetime(expiration) - datetime.now()

    if delta.total_seconds() <= 0:
        return 0

    return delta.days + (1 if delta.seconds > 0 else 0)


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📚 پلن‌های مشاوره"
                },
                {
                    "text": "💳 پرداخت و تمدید"
                }
            ],
            [
                {
                    "text": "🎓 کلاس‌های کنکوری"
                },
                {
                    "text": "🆘 ارتباط با پشتیبان"
                }
            ],
            [
                {
                    "text": "👤 پنل من"
                }
            ]
        ],
        "resize_keyboard": True
    }


def admin_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📊 داشبورد"
                },
                {
                    "text": "👥 دانش‌آموزان"
                }
            ],
            [
                {
                    "text": "💳 پرداخت‌های در انتظار"
                },
                {
                    "text": "🆘 درخواست‌های پشتیبانی"
                }
            ],
            [
                {
                    "text": "🏠 خروج از پنل ادمین"
                }
            ]
        ],
        "resize_keyboard": True
    }


def membership_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📢 عضویت در کانال MIRA",
                    "url": CHANNEL_URL
                }
            ],
            [
                {
                    "text": "✅ بررسی عضویت",
                    "callback_data": "check_membership"
                }
            ]
        ]
    }


def contact_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📱 ارسال شماره تلفن",
                    "request_contact": True
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def remove_keyboard():
    return {
        "remove_keyboard": True
    }


# ============================================================
# MEMBERSHIP
# ============================================================

def check_membership(chat_id, force=False):
    now = datetime.now()

    with membership_cache_lock:
        cached = membership_cache.get(chat_id)

        if (
            not force
            and cached
            and (now - cached["time"]).total_seconds()
            < MEMBERSHIP_CACHE_SECONDS
        ):
            return cached["value"]

    result = telegram(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": chat_id
        },
        timeout=7
    )

    if not result:
        value = False
    else:
        status = result.get("status")

        value = status in {
            "member",
            "administrator",
            "creator"
        }

    with membership_cache_lock:
        membership_cache[chat_id] = {
            "value": value,
            "time": now
        }

    return value


def require_membership(chat_id, force=False):
    if check_membership(chat_id, force=force):
        return True

    send_message(
        chat_id,
        (
            "برای استفاده از بات MIRA ابتدا باید عضو کانال اصلی MIRA باشید. 📢\n\n"
            "بعد از عضویت روی «بررسی عضویت» بزنید."
        ),
        reply_markup=membership_keyboard()
    )

    return False


# ============================================================
# STATE MANAGEMENT
# ============================================================

def set_state(chat_id, state, data=None):
    with state_lock:
        states[chat_id] = {
            "state": state,
            "data": data or {}
        }


def get_state(chat_id):
    with state_lock:
        return states.get(chat_id)


def clear_state(chat_id):
    with state_lock:
        states.pop(chat_id, None)


# ============================================================
# STUDENT UI
# ============================================================

def welcome_text():
    return (
        "سلام، خوبی؟ 👋\n\n"
        "به تیم <b>MIRA</b> خوش اومدی.\n\n"
        "اینجا کمتر از یک دقیقه می‌تونیم ثبت‌نامت کنیم "
        "و معرفی مسیرهای MIRA رو در اختیارت بذاریم."
    )


def show_home(chat_id):
    student = get_student(chat_id)

    if not student:
        send_message(
            chat_id,
            welcome_text(),
            reply_markup=main_keyboard()
        )

        send_message(
            chat_id,
            "برای شروع ثبت‌نام روی «ثبت‌نام» از منوی زیر بزن."
        )

        return

    send_message(
        chat_id,
        (
            f"خوش اومدی <b>{escape_html(student['full_name'])}</b> 👋\n\n"
            "از پنل زیر می‌تونی خدمات MIRA رو مدیریت کنی."
        ),
        reply_markup=main_keyboard()
    )


def show_registration_start(chat_id):
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
        reply_markup=remove_keyboard()
    )


def show_plan_list(chat_id):
    buttons = []

    for key, plan in PLANS.items():
        buttons.append([
            {
                "text": plan["name"],
                "callback_data": f"plan:{key}"
            }
        ])

    send_message(
        chat_id,
        (
            "<b>پلن‌های مشاوره MIRA</b>\n\n"
            "یکی از مسیرها رو انتخاب کن تا جزئیاتش رو ببینی:"
        ),
        reply_markup={
            "inline_keyboard": buttons
        }
    )


def show_plan_details(chat_id, plan_key):
    plan = PLANS.get(plan_key)

    if not plan:
        send_message(
            chat_id,
            "این پلن پیدا نشد."
        )
        return

    price_text = format_price(plan["price"])

    text = (
        f"<b>{plan['name']}</b>\n\n"
        f"{plan['description']}\n\n"
        f"💰 هزینه ۳ ماهه: <b>{price_text}</b>\n\n"
        "برای اطلاعات بیشتر می‌تونی کانال مربوط به مشاوره رو ببینی."
    )

    buttons = [
        [
            {
                "text": "📢 اطلاعات بیشتر",
                "url": plan["channel_url"]
            }
        ],
        [
            {
                "text": "💬 ارتباط با پشتیبان",
                "callback_data": f"support_plan:{plan_key}"
            }
        ]
    ]

    if plan["price"] > 0:
        buttons.append([
            {
                "text": "💳 پرداخت ۳ ماهه",
                "callback_data": f"pay:{plan_key}"
            }
        ])

    send_message(
        chat_id,
        text,
        reply_markup={
            "inline_keyboard": buttons
        }
    )


def show_course_channel(chat_id):
    send_message(
        chat_id,
        (
            "<b>🎓 کلاس‌های کنکوری MIRA</b>\n\n"
            "کلاس‌های کنکوری MIRA هنوز شروع نشده‌اند.\n\n"
            "به‌محض شروع ثبت‌نام و انتشار اطلاعیه‌ها، "
            "جزئیات در کانال مربوط به کلاس‌ها قرار می‌گیرد."
        ),
        reply_markup={
            "inline_keyboard": [
                [
                    {
                        "text": "📢 کانال کلاس‌های کنکوری",
                        "url": COURSE_CHANNEL_URL
                    }
                ]
            ]
        }
    )


def show_my_panel(chat_id):
    student = get_student(chat_id)

    if not student:
        send_message(
            chat_id,
            "هنوز ثبت‌نامت در MIRA کامل نشده.",
            reply_markup=main_keyboard()
        )
        return

    subscription = get_active_subscription(chat_id)

    text = (
        "<b>👤 پنل من</b>\n\n"
        f"نام و نام خانوادگی: "
        f"<b>{escape_html(student['full_name'])}</b>\n"
        f"شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n"
        f"مقطع: {escape_html(student['grade'] or '-')}\n"
        f"رشته: {escape_html(student['field'] or '-')}\n"
    )

    if subscription:
        days = remaining_days(
            subscription["expiration_date"]
        )

        text += (
            "\n"
            f"📌 پلن فعال: <b>{escape_html(subscription['plan_name'])}</b>\n"
            f"⏳ روزهای باقی‌مانده: <b>{days} روز</b>\n"
            f"📅 پایان اشتراک: "
            f"<b>{format_date(subscription['expiration_date'])}</b>\n"
        )

        if subscription.get("consultant"):
            text += (
                f"👤 مشاور: "
                f"<b>{escape_html(subscription['consultant'])}</b>\n"
            )

    else:
        text += (
            "\n"
            "📌 اشتراک فعال: <b>نداری</b>\n"
        )

    buttons = [
        [
            {
                "text": "📚 پلن‌های مشاوره",
                "callback_data": "plans"
            }
        ],
        [
            {
                "text": "💳 پرداخت / تمدید",
                "callback_data": "renew"
            }
        ]
    ]

    send_message(
        chat_id,
        text,
        reply_markup={
            "inline_keyboard": buttons
        }
    )


def show_payment_menu(chat_id):
    show_plan_list(chat_id)


def show_support(chat_id):
    set_state(
        chat_id,
        "support_message"
    )

    send_message(
        chat_id,
        (
            "<b>🆘 ارتباط با پشتیبان</b>\n\n"
            "پیامت رو همینجا ارسال کن تا درخواستت برای "
            "تیم پشتیبانی MIRA ثبت بشه."
        ),
        reply_markup=remove_keyboard()
    )


# ============================================================
# PAYMENT FLOW
# ============================================================

def start_payment(chat_id, plan_key):
    plan = PLANS.get(plan_key)

    if not plan:
        send_message(
            chat_id,
            "این پلن در دسترس نیست."
        )
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
            "request_id": request["id"],
            "plan_key": plan_key,
            "amount": plan["price"]
        }
    )

    send_message(
        chat_id,
        (
            f"<b>پرداخت {plan['name']}</b>\n\n"
            f"💰 مبلغ ۳ ماهه:\n"
            f"<b>{format_price(plan['price'])}</b>\n\n"
            f"💳 شماره کارت:\n"
            f"<code>{CARD_NUMBER}</code>\n\n"
            f"👤 به نام:\n"
            f"<b>{escape_html(CARD_OWNER)}</b>\n\n"
            "بعد از واریز، <b>عکس رسید پرداخت</b> رو همینجا ارسال کن.\n\n"
            "پس از بررسی و تأیید پرداخت، اشتراکت فعال می‌شه."
        ),
        reply_markup={
            "inline_keyboard": [
                [
                    {
                        "text": "❌ لغو پرداخت",
                        "callback_data": "cancel_payment"
                    }
                ]
            ]
        }
    )


# ============================================================
# ADMIN UI
# ============================================================

def is_admin(chat_id):
    return chat_id in ADMIN_CHAT_IDS


def show_admin_dashboard(chat_id):
    stats = get_admin_stats()

    text = (
        "<b>📊 داشبورد MIRA</b>\n\n"
        f"👥 کل دانش‌آموزان: <b>{stats['total_students']}</b>\n"
        f"🆕 ثبت‌نام‌های امروز: <b>{stats['new_today']}</b>\n"
        f"📥 کل لیدها: <b>{stats['leads']}</b>\n"
        f"🟢 اشتراک‌های فعال: <b>{stats['active']}</b>\n"
        f"🔴 اشتراک‌های منقضی: <b>{stats['expired']}</b>\n"
        f"💳 پرداخت‌های در انتظار: <b>{stats['pending_payments']}</b>\n"
        f"🆘 پشتیبانی‌های باز: <b>{stats['open_support']}</b>"
    )

    send_message(
        chat_id,
        text,
        reply_markup=admin_keyboard()
    )


def show_admin_students(chat_id):
    students = get_recent_students(20)

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
            f"مقطع: {escape_html(student['grade'] or '-')}"
            f" | رشته: {escape_html(student['field'] or '-')}\n"
            f"📱 {escape_html(student['phone'] or '-')}\n"
        )

    send_message(
        chat_id,
        "\n".join(lines)
    )


def show_pending_payments(chat_id):
    payments = get_pending_payments(15)

    if not payments:
        send_message(
            chat_id,
            "در حال حاضر پرداخت در انتظاری وجود ندارد."
        )
        return

    for payment in payments:
        text = (
            "<b>💳 درخواست پرداخت</b>\n\n"
            f"شماره دانش‌آموزی: "
            f"<b>{payment.get('student_number') or '-'}</b>\n"
            f"نام: <b>{escape_html(payment.get('full_name') or '-')}</b>\n"
            f"پلن: <b>{escape_html(payment['plan_key'])}</b>\n"
            f"مبلغ: <b>{format_price(payment['amount'])}</b>\n"
            f"شناسه پرداخت: <code>{payment['id']}</code>"
        )

        buttons = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ تأیید",
                        "callback_data": f"approve:{payment['id']}"
                    },
                    {
                        "text": "❌ رد",
                        "callback_data": f"reject:{payment['id']}"
                    }
                ]
            ]
        }

        send_message(
            chat_id,
            text,
            reply_markup=buttons
        )


# ============================================================
# ADMIN PAYMENT NOTIFICATION
# ============================================================

def notify_admins_about_payment(
    payment_id,
    chat_id,
    plan_key,
    amount,
    photo_bytes=None
):
    student = get_student(chat_id)
    plan = PLANS.get(plan_key)

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
        f"👤 نام: <b>{escape_html(student_name)}</b>\n"
        f"🔢 شماره دانش‌آموزی: <b>{student_number}</b>\n"
        f"📦 پلن: <b>{escape_html(plan['name'] if plan else plan_key)}</b>\n"
        f"💰 مبلغ: <b>{format_price(amount)}</b>\n"
        f"🆔 Payment ID: <code>{payment_id}</code>"
    )

    buttons = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ تأیید پرداخت",
                    "callback_data": f"approve:{payment_id}"
                },
                {
                    "text": "❌ رد پرداخت",
                    "callback_data": f"reject:{payment_id}"
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
                reply_markup=buttons
            )
        else:
            send_message(
                admin_id,
                text,
                reply_markup=buttons
            )


def notify_admins_about_registration(chat_id):
    student = get_student(chat_id)

    if not student:
        return

    text = (
        "<b>🆕 ثبت‌نام جدید MIRA</b>\n\n"
        f"🔢 شماره دانش‌آموزی: "
        f"<b>{student['student_number']}</b>\n"
        f"👤 نام: <b>{escape_html(student['full_name'])}</b>\n"
        f"📱 شماره: <b>{escape_html(student['phone'] or '-')}</b>\n"
        f"📚 مقطع: <b>{escape_html(student['grade'] or '-')}</b>\n"
        f"🧪 رشته: <b>{escape_html(student['field'] or '-')}</b>\n"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send_message(
            admin_id,
            text
        )


def notify_admins_about_support(chat_id, message):
    student = get_student(chat_id)

    name = (
        student["full_name"]
        if student
        else "کاربر ثبت‌نام‌نشده"
    )

    number = (
        student["student_number"]
        if student
        else "-"
    )

    text = (
        "<b>🆘 درخواست پشتیبانی جدید</b>\n\n"
        f"👤 نام: <b>{escape_html(name)}</b>\n"
        f"🔢 شماره دانش‌آموزی: <b>{number}</b>\n\n"
        f"💬 پیام:\n{escape_html(message)}"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send_message(
            admin_id,
            text
        )


# ============================================================
# MESSAGE HANDLING
# ============================================================

def handle_registration_state(chat_id, message):
    current = get_state(chat_id)

    if not current:
        return False

    state = current["state"]
    data = current["data"]

    text = message.get("text", "")

    if state == "registration_name":
        if not text or len(text.strip()) < 3:
            send_message(
                chat_id,
                "لطفاً نام و نام خانوادگی کاملت رو وارد کن."
            )
            return True

        data["full_name"] = text.strip()

        set_state(
            chat_id,
            "registration_grade",
            data
        )

        send_message(
            chat_id,
            "مقطع تحصیلی‌ات رو وارد کن:"
        )

        return True

    if state == "registration_grade":
        if not text.strip():
            send_message(
                chat_id,
                "لطفاً مقطع تحصیلی‌ات رو وارد کن."
            )
            return True

        data["grade"] = text.strip()

        set_state(
            chat_id,
            "registration_field",
            data
        )

        send_message(
            chat_id,
            "رشته تحصیلی‌ات رو وارد کن:"
        )

        return True

    if state == "registration_field":
        if not text.strip():
            send_message(
                chat_id,
                "لطفاً رشته تحصیلی‌ات رو وارد کن."
            )
            return True

        data["field"] = text.strip()

        set_state(
            chat_id,
            "registration_phone",
            data
        )

        send_message(
            chat_id,
            (
                "آخرین مرحله 👌\n\n"
                "برای تکمیل ثبت‌نام، شماره تلفنت رو با دکمه زیر "
                "برای بات ارسال کن."
            ),
            reply_markup=contact_keyboard()
        )

        return True

    if state == "registration_phone":
        contact = message.get("contact")

        if not contact:
            send_message(
                chat_id,
                (
                    "برای تکمیل ثبت‌نام باید شماره تلفنت رو "
                    "با دکمه «ارسال شماره تلفن» ارسال کنی."
                ),
                reply_markup=contact_keyboard()
            )
            return True

        contact_user_id = contact.get("user_id")

        # فقط Contact متعلق به همان کاربر پذیرفته شود.
        if contact_user_id and contact_user_id != chat_id:
            send_message(
                chat_id,
                "لطفاً شماره تلفن خودت رو ارسال کن، نه شماره شخص دیگر."
            )
            return True

        phone = contact.get("phone_number", "").strip()

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
            username=message.get("from", {}).get("username")
        )

        clear_state(chat_id)

        send_message(
            chat_id,
            (
                "ثبت‌نامت با موفقیت انجام شد. ✅\n\n"
                f"شماره دانش‌آموزی تو: "
                f"<b>{student_number}</b>\n\n"
                "پنلت ساخته شد و اطلاعات ثبت‌نام برای پشتیبان MIRA ارسال شد."
            ),
            reply_markup=main_keyboard()
        )

        notify_admins_about_registration(chat_id)

        return True

    if state == "support_message":
        if not text.strip():
            send_message(
                chat_id,
                "لطفاً پیام خودت رو بنویس."
            )
            return True

        create_support_request(
            chat_id,
            text.strip()
        )

        clear_state(chat_id)

        send_message(
            chat_id,
            (
                "پیامت برای پشتیبان MIRA ثبت شد. ✅\n\n"
                "در اولین فرصت بررسی می‌شه."
            ),
            reply_markup=main_keyboard()
        )

        notify_admins_about_support(
            chat_id,
            text.strip()
        )

        return True

    if state == "waiting_receipt":
        # رسید باید Photo باشد.
        photo = message.get("photo")

        if not photo:
            send_message(
                chat_id,
                (
                    "لطفاً عکس رسید پرداخت رو ارسال کن.\n\n"
                    "اگر قصد لغو داری، از گزینه «لغو پرداخت» استفاده کن."
                )
            )
            return True

        largest_photo = photo[-1]
        file_id = largest_photo.get("file_id")

        if not file_id:
            send_message(
                chat_id,
                "دریافت رسید با مشکل مواجه شد. دوباره ارسال کن."
            )
            return True

        payment_id = create_payment(
            chat_id=chat_id,
            request_id=data.get("request_id"),
            plan_key=data.get("plan_key"),
            amount=data.get("amount", 0),
            file_id=file_id
        )

        if not payment_id:
            send_message(
                chat_id,
                "ثبت رسید با مشکل مواجه شد. لطفاً دوباره تلاش کن."
            )
            return True

        clear_state(chat_id)

        send_message(
            chat_id,
            (
                "رسیدت با موفقیت دریافت شد. ✅\n\n"
                "رسید برای تیم MIRA ارسال شد و بعد از تأیید، "
                "اشتراکت فعال می‌شه."
            ),
            reply_markup=main_keyboard()
        )

        photo_bytes = download_telegram_file(file_id)

        notify_admins_about_payment(
            payment_id=payment_id,
            chat_id=chat_id,
            plan_key=data.get("plan_key"),
            amount=data.get("amount", 0),
            photo_bytes=photo_bytes
        )

        return True

    return False


def handle_message(message):
    chat = message.get("chat")

    if not chat:
        return

    chat_id = chat.get("id")

    if not chat_id:
        return

    text = message.get("text", "")

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if is_admin(chat_id):

        if text == "/admin":
            clear_state(chat_id)

            send_message(
                chat_id,
                "پنل مدیریت MIRA",
                reply_markup=admin_keyboard()
            )
            return

        if text == "📊 داشبورد":
            show_admin_dashboard(chat_id)
            return

        if text == "👥 دانش‌آموزان":
            show_admin_students(chat_id)
            return

        if text == "💳 پرداخت‌های در انتظار":
            show_pending_payments(chat_id)
            return

        if text == "🆘 درخواست‌های پشتیبانی":
            stats = get_admin_stats()

            send_message(
                chat_id,
                (
                    f"تعداد درخواست‌های باز پشتیبانی: "
                    f"<b>{stats['open_support']}</b>"
                )
            )
            return

        if text == "🏠 خروج از پنل ادمین":
            send_message(
                chat_id,
                "از پنل مدیریت خارج شدی.",
                reply_markup=main_keyboard()
            )
            return

    # --------------------------------------------------------
    # /start
    # --------------------------------------------------------

    if text.startswith("/start"):

        if not require_membership(chat_id):
            return

        student = get_student(chat_id)

        if student:
            clear_state(chat_id)
            show_home(chat_id)
            return

        clear_state(chat_id)

        send_message(
            chat_id,
            welcome_text(),
            reply_markup=main_keyboard()
        )

        send_message(
            chat_id,
            (
                "برای ساخت پنل شخصی، ثبت‌نامت رو شروع کن. 👇"
            )
        )

        # شروع مستقیم ثبت‌نام
        show_registration_start(chat_id)

        return

    # --------------------------------------------------------
    # MEMBERSHIP
    # --------------------------------------------------------

    if not require_membership(chat_id):
        return

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    if handle_registration_state(
        chat_id,
        message
    ):
        return

    # --------------------------------------------------------
    # REGISTRATION
    # --------------------------------------------------------

    if text == "📝 ثبت‌نام در MIRA":
        show_registration_start(chat_id)
        return

    # --------------------------------------------------------
    # PLANS
    # --------------------------------------------------------

    if text == "📚 پلن‌های مشاوره":
        show_plan_list(chat_id)
        return

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    if text == "💳 پرداخت و تمدید":
        show_payment_menu(chat_id)
        return

    # --------------------------------------------------------
    # COURSES
    # --------------------------------------------------------

    if text == "🎓 کلاس‌های کنکوری":
        show_course_channel(chat_id)
        return

    # --------------------------------------------------------
    # SUPPORT
    # --------------------------------------------------------

    if text == "🆘 ارتباط با پشتیبان":
        show_support(chat_id)
        return

    # --------------------------------------------------------
    # MY PANEL
    # --------------------------------------------------------

    if text == "👤 پنل من":
        show_my_panel(chat_id)
        return

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    send_message(
        chat_id,
        (
            "از منوی زیر می‌تونی بخش موردنظرت رو انتخاب کنی. 👇"
        ),
        reply_markup=main_keyboard()
    )


# ============================================================
# CALLBACKS
# ============================================================

def handle_callback(callback):
    callback_id = callback.get("id")
    data = callback.get("data")
    message = callback.get("message")

    if not message:
        answer_callback(callback_id)
        return

    chat = message.get("chat")

    if not chat:
        answer_callback(callback_id)
        return

    chat_id = chat.get("id")

    # پاسخ سریع به Callback
    answer_callback(callback_id)

    # --------------------------------------------------------
    # MEMBERSHIP CHECK
    # --------------------------------------------------------

    if data == "check_membership":
        if check_membership(
            chat_id,
            force=True
        ):
            send_message(
                chat_id,
                (
                    "عضویتت تأیید شد. ✅\n\n"
                    "به MIRA خوش اومدی."
                ),
                reply_markup=main_keyboard()
            )

            student = get_student(chat_id)

            if not student:
                show_registration_start(chat_id)
            else:
                show_home(chat_id)

        else:
            send_message(
                chat_id,
                (
                    "هنوز عضویتت در کانال تأیید نشده.\n\n"
                    "اول عضو کانال شو و دوباره «بررسی عضویت» رو بزن."
                ),
                reply_markup=membership_keyboard()
            )

        return

    # --------------------------------------------------------
    # ALL OTHER CALLBACKS REQUIRE MEMBERSHIP
    # --------------------------------------------------------

    if not require_membership(chat_id):
        return

    # --------------------------------------------------------
    # PLANS
    # --------------------------------------------------------

    if data == "plans":
        show_plan_list(chat_id)
        return

    if data.startswith("plan:"):
        plan_key = data.split(":", 1)[1]
        show_plan_details(chat_id, plan_key)
        return

    # --------------------------------------------------------
    # SUPPORT BEFORE PAYMENT
    # --------------------------------------------------------

    if data.startswith("support_plan:"):
        plan_key = data.split(":", 1)[1]

        plan = PLANS.get(plan_key)

        if not plan:
            send_message(
                chat_id,
                "این پلن پیدا نشد."
            )
            return

        set_state(
            chat_id,
            "support_message"
        )

        send_message(
            chat_id,
            (
                f"انتخابت: <b>{escape_html(plan['name'])}</b>\n\n"
                "اگر قبل از ثبت‌نام یا پرداخت سوالی داری، "
                "پیامت رو بنویس تا برای پشتیبان ارسال بشه."
            ),
            reply_markup=remove_keyboard()
        )

        return

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    if data.startswith("pay:"):
        plan_key = data.split(":", 1)[1]
        start_payment(
            chat_id,
            plan_key
        )
        return

    if data == "renew":
        show_plan_list(chat_id)
        return

    if data == "cancel_payment":
        clear_state(chat_id)

        send_message(
            chat_id,
            "پرداخت لغو شد.",
            reply_markup=main_keyboard()
        )

        return

    # --------------------------------------------------------
    # ADMIN PAYMENT
    # --------------------------------------------------------

    if data.startswith("approve:"):

        if not is_admin(chat_id):
            return

        try:
            payment_id = int(
                data.split(":", 1)[1]
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

        user_chat_id = result["chat_id"]

        send_message(
            user_chat_id,
            (
                "پرداختت تأیید شد. ✅🎉\n\n"
                f"پلن <b>{escape_html(result['plan_name'])}</b> "
                "برای تو فعال شد.\n\n"
                f"📅 شروع: <b>{format_date(result['start'].isoformat())}</b>\n"
                f"📅 پایان: <b>{format_date(result['expiration'].isoformat())}</b>\n\n"
                "از پنل من می‌تونی وضعیت اشتراکت رو ببینی."
            ),
            reply_markup=main_keyboard()
        )

        send_message(
            chat_id,
            f"پرداخت #{payment_id} تأیید و اشتراک فعال شد. ✅"
        )

        return

    if data.startswith("reject:"):

        if not is_admin(chat_id):
            return

        try:
            payment_id = int(
                data.split(":", 1)[1]
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
            payment["chat_id"],
            (
                "رسید پرداختت توسط تیم MIRA تأیید نشد. ❌\n\n"
                "لطفاً در صورت نیاز با پشتیبان ارتباط بگیر."
            ),
            reply_markup=main_keyboard()
        )

        send_message(
            chat_id,
            f"پرداخت #{payment_id} رد شد."
        )

        return


# ============================================================
# HTML ESCAPE
# ============================================================

def escape_html(value):
    if value is None:
        return ""

    value = str(value)

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_date(value):
    dt = parse_datetime(value)

    if dt == datetime.min:
        return "-"

    return dt.strftime("%Y/%m/%d")


# ============================================================
# UPDATE PROCESSING
# ============================================================

def process_update(update):
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
        # بات نباید به‌خاطر یک آپدیت خراب متوقف شود.
        print(
            f"[MIRA] update error: {type(exc).__name__}: {exc}",
            flush=True
        )


# ============================================================
# WEBHOOK SERVER
# ============================================================

class WebhookHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/health":
            body = b"MIRA BOT OK"

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(body))
            )
            self.end_headers()
            self.wfile.write(body)

            return

        body = b"MIRA BOT"

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/telegram-webhook":
            self.send_response(404)
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
                raw_body.decode("utf-8")
            )

            # پاسخ فوری به Telegram
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain"
            )
            self.end_headers()
            self.wfile.write(b"OK")

            # پردازش جداگانه برای جلوگیری از تأخیر Webhook
            thread = threading.Thread(
                target=process_update,
                args=(update,),
                daemon=True
            )

            thread.start()

        except Exception as exc:
            print(
                f"[MIRA] webhook error: {type(exc).__name__}: {exc}",
                flush=True
            )

            try:
                self.send_response(500)
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
        f"{RENDER_EXTERNAL_URL}/telegram-webhook"
    )

    result = telegram(
        "setWebhook",
        {
            "url": webhook_url,
            "drop_pending_updates": True,
            "allowed_updates": [
                "message",
                "callback_query"
            ]
        },
        timeout=15
    )

    if result:
        print(
            f"[MIRA] Webhook set: {webhook_url}",
            flush=True
        )
    else:
        print(
            "[MIRA] Failed to set webhook.",
            flush=True
        )


# ============================================================
# STARTUP
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

    missing_prices = []

    if PLANS["task"]["price"] <= 0:
        missing_prices.append("PLAN_TASK_PRICE")

    if PLANS["task_mentoring"]["price"] <= 0:
        missing_prices.append("PLAN_TASK_MENTORING_PRICE")

    if PLANS["360"]["price"] <= 0:
        missing_prices.append("PLAN_360_PRICE")

    if missing_prices:
        print(
            "[MIRA] WARNING: Plan prices are not configured: "
            + ", ".join(missing_prices),
            flush=True
        )


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
        f"[MIRA] Server running on port {PORT}",
        flush=True
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
