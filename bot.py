import os
import json
import sqlite3
import random
import string
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
}

PORT = int(os.environ.get("PORT", "10000"))
DB_PATH = os.environ.get("DB_PATH", "mira.db")

CHANNEL_USERNAME = "@miracampus"
CHANNEL_URL = "https://t.me/miracampus"

# Payment
CARD_NUMBER = "6219861940398554"
CARD_OWNER = "محمد مهدی روشنی"

# MIRA courses
COURSE_CHANNEL_URL = "https://t.me/mirakunkorclss"
CONSULTING_CHANNEL_URL = "https://t.me/miraprivatecahnnel"


# =========================================================
# MIRA CONSULTING PLANS
# =========================================================

PLANS = {
    "executive": {
        "name": "پلن اجرایی",
        "monthly_price": 900_000,
        "three_month_price": 2_700_000,
    },
    "mentoring": {
        "name": "پلن منتورینگ",
        "monthly_price": 1_200_000,
        "three_month_price": 3_600_000,
    },
    "360": {
        "name": "پلن 360°",
        "monthly_price": 1_500_000,
        "three_month_price": 4_500_000,
    },
}


# =========================================================
# TELEGRAM API
# =========================================================

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg(method, data=None, files=None):
    try:
        if files:
            response = requests.post(
                f"{API_URL}/{method}",
                data=data or {},
                files=files,
                timeout=30,
            )
        else:
            response = requests.post(
                f"{API_URL}/{method}",
                json=data or {},
                timeout=30,
            )

        return response.json()
    except Exception as e:
        print("Telegram API error:", e)
        return {"ok": False, "error": str(e)}


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    return tg("sendMessage", data)


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    return tg("editMessageText", data)


def answer_callback(callback_id, text=""):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": text,
        },
    )


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return {
        "keyboard": [
            [
                {"text": "📝 ثبت‌نام در MIRA"},
                {"text": "🧭 پلن‌های مشاوره"},
            ],
            [
                {"text": "🎓 کلاس‌های کنکوری"},
                {"text": "💳 پرداخت / تمدید"},
            ],
            [
                {"text": "👤 پنل من"},
                {"text": "🆘 پشتیبانی"},
            ],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def admin_keyboard():
    return {
        "keyboard": [
            [
                {"text": "👥 کاربران"},
                {"text": "📥 لیدها"},
            ],
            [
                {"text": "💳 درخواست‌های پرداخت"},
                {"text": "🔐 کدهای تأیید"},
            ],
            [
                {"text": "📊 اشتراک‌ها"},
                {"text": "👤 پنل دانش‌آموز"},
            ],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def membership_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📢 عضویت در کانال MIRA",
                    "url": CHANNEL_URL,
                }
            ],
            [
                {
                    "text": "✅ بررسی عضویت",
                    "callback_data": "check_membership",
                }
            ],
        ]
    }


def plan_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🟢 پلن اجرایی — ۲.۷ میلیون",
                    "callback_data": "plan_executive",
                }
            ],
            [
                {
                    "text": "🔵 پلن منتورینگ — ۳.۶ میلیون",
                    "callback_data": "plan_mentoring",
                }
            ],
            [
                {
                    "text": "🟣 پلن 360° — ۴.۵ میلیون",
                    "callback_data": "plan_360",
                }
            ],
        ]
    }


def admin_request_keyboard(request_id):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🔐 صدور کد تأیید",
                    "callback_data": f"issue_code:{request_id}",
                }
            ]
        ]
    }


def admin_payment_keyboard(payment_id):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ تأیید پرداخت",
                    "callback_data": f"approve_payment:{payment_id}",
                },
                {
                    "text": "❌ رد پرداخت",
                    "callback_data": f"reject_payment:{payment_id}",
                },
            ]
        ]
    }


def admin_consultant_keyboard(chat_id):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "👤 اتصال به مشاور",
                    "callback_data": f"assign_consultant:{chat_id}",
                }
            ]
        ]
    }


# =========================================================
# DATABASE
# =========================================================

db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_students (
                chat_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                grade TEXT,
                field TEXT,
                goal TEXT,
                problem TEXT,
                notes TEXT,
                consultant TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                full_name TEXT,
                phone TEXT,
                grade TEXT,
                field TEXT,
                goal TEXT,
                problem TEXT,
                notes TEXT,
                created_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_payment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                phone TEXT,
                plan_key TEXT,
                plan_name TEXT,
                amount INTEGER,
                status TEXT DEFAULT 'PENDING',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_payment_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                request_id INTEGER,
                code TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                created_at TEXT,
                used_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                chat_id INTEGER,
                plan_key TEXT,
                plan_name TEXT,
                amount INTEGER,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TEXT,
                approved_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS mira_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                plan_key TEXT,
                plan_name TEXT,
                status TEXT DEFAULT 'ACTIVE',
                start_date TEXT,
                expiration_date TEXT,
                consultant TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()


# =========================================================
# STATE
# =========================================================

states = {}


def set_state(chat_id, state, data=None):
    states[chat_id] = {
        "state": state,
        "data": data or {},
    }


def get_state(chat_id):
    return states.get(chat_id, {})


def clear_state(chat_id):
    states.pop(chat_id, None)


# =========================================================
# HELPERS
# =========================================================

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_price(amount):
    return f"{amount:,}".replace(",", "٬") + " تومان"


def is_admin(chat_id):
    return chat_id in ADMIN_CHAT_IDS


def generate_code():
    return "".join(random.choices(string.digits, k=6))


def get_student(chat_id):
    with db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM mira_students WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        conn.close()
        return row


def get_active_subscription(chat_id):
    with db_lock:
        conn = get_db()
        row = conn.execute(
            """
            SELECT *
            FROM mira_subscriptions
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        conn.close()

    if not row:
        return None

    try:
        expiration = datetime.strptime(
            row["expiration_date"],
            "%Y-%m-%d %H:%M:%S"
        )

        if expiration > datetime.now() and row["status"] == "ACTIVE":
            return row

    except Exception:
        pass

    return row


def subscription_text(chat_id):
    sub = get_active_subscription(chat_id)

    if not sub:
        return (
            "👤 <b>پنل شخصی MIRA</b>\n\n"
            "هنوز اشتراک فعالی برای شما ثبت نشده است.\n\n"
            "برای شروع مسیر، از بخش «🧭 پلن‌های مشاوره» پلن موردنظرت را انتخاب کن."
        )

    try:
        expiration = datetime.strptime(
            sub["expiration_date"],
            "%Y-%m-%d %H:%M:%S"
        )
        days = max(0, (expiration - datetime.now()).days)
    except Exception:
        days = 0

    status = "🟢 فعال" if days > 0 else "🔴 منقضی شده"

    consultant = sub["consultant"] or "هنوز تعیین نشده"

    return (
        "👤 <b>پنل شخصی MIRA</b>\n\n"
        f"📌 وضعیت: {status}\n"
        f"🧭 پلن: {sub['plan_name']}\n"
        f"📅 شروع: {sub['start_date']}\n"
        f"📅 پایان: {sub['expiration_date']}\n"
        f"⏳ روزهای باقی‌مانده: {days}\n"
        f"👨‍🏫 مشاور: {consultant}\n"
    )


# =========================================================
# MEMBERSHIP
# =========================================================

def check_membership(chat_id):
    result = tg(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": chat_id,
        },
    )

    if not result.get("ok"):
        return False

    status = result["result"]["status"]

    return status in {
        "member",
        "administrator",
        "creator",
    }


def require_membership(chat_id):
    if check_membership(chat_id):
        return True

    send_message(
        chat_id,
        "🔒 <b>قبل از شروع کار با MIRA</b>\n\n"
        "ابتدا باید عضو کانال اصلی MIRA شوی.\n\n"
        "بعد از عضویت روی «✅ بررسی عضویت» بزن.",
        membership_keyboard(),
    )

    return False


# =========================================================
# MAIN MENUS
# =========================================================

def show_home(chat_id):
    clear_state(chat_id)

    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "به <b>MIRA</b> خوش اومدی.\n"
        "چطور می‌تونم کمکت کنم؟",
        main_keyboard(),
    )


def show_admin_home(chat_id):
    clear_state(chat_id)

    send_message(
        chat_id,
        "🛠 <b>پنل مدیریت MIRA</b>\n\n"
        "از منوی پایین بخش موردنظر را انتخاب کن.",
        admin_keyboard(),
    )


# =========================================================
# REGISTRATION
# =========================================================

def start_registration(chat_id):
    set_state(chat_id, "reg_full_name")

    send_message(
        chat_id,
        "📝 <b>ثبت‌نام در MIRA</b>\n\n"
        "اول از همه نام و نام خانوادگی‌ات رو بفرست:"
    )


def process_registration(chat_id, text):
    state = get_state(chat_id).get("state")
    data = get_state(chat_id).get("data", {})

    if state == "reg_full_name":
        data["full_name"] = text
        set_state(chat_id, "reg_grade", data)
        send_message(chat_id, "🎓 پایه تحصیلی‌ات رو بفرست:")
        return

    if state == "reg_grade":
        data["grade"] = text
        set_state(chat_id, "reg_field", data)
        send_message(chat_id, "📚 رشته‌ات رو بفرست:")
        return

    if state == "reg_field":
        data["field"] = text
        set_state(chat_id, "reg_goal", data)
        send_message(chat_id, "🎯 مهم‌ترین هدفت از کنکور یا مسیر تحصیلی چیه؟")
        return

    if state == "reg_goal":
        data["goal"] = text
        set_state(chat_id, "reg_problem", data)
        send_message(
            chat_id,
            "⚠️ بزرگ‌ترین مشکل درسی یا مطالعاتی فعلیت چیه؟"
        )
        return

    if state == "reg_problem":
        data["problem"] = text
        set_state(chat_id, "reg_notes", data)
        send_message(
            chat_id,
            "📝 اگر توضیح یا نکته دیگه‌ای هست که فکر می‌کنی باید بدونیم، بفرست.\n"
            "اگر چیزی نیست، بنویس «ندارم»."
        )
        return

    if state == "reg_notes":
        data["notes"] = text

        set_state(chat_id, "reg_phone", data)

        send_message(
            chat_id,
            "📱 در آخر شماره تماس خودت رو بفرست:"
        )
        return

    if state == "reg_phone":
        data["phone"] = text

        timestamp = now_str()

        with db_lock:
            conn = get_db()

            conn.execute(
                """
                INSERT OR REPLACE INTO mira_students
                (chat_id, full_name, phone, grade, field, goal,
                 problem, notes, consultant, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE(
                            (SELECT consultant FROM mira_students WHERE chat_id = ?),
                            ''
                        ),
                        COALESCE(
                            (SELECT created_at FROM mira_students WHERE chat_id = ?),
                            ?
                        ),
                        ?)
                """,
                (
                    chat_id,
                    data["full_name"],
                    data["phone"],
                    data["grade"],
                    data["field"],
                    data["goal"],
                    data["problem"],
                    data["notes"],
                    chat_id,
                    chat_id,
                    timestamp,
                    timestamp,
                ),
            )

            conn.execute(
                """
                INSERT INTO mira_leads
                (chat_id, full_name, phone, grade, field,
                 goal, problem, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    data["full_name"],
                    data["phone"],
                    data["grade"],
                    data["field"],
                    data["goal"],
                    data["problem"],
                    data["notes"],
                    timestamp,
                ),
            )

            conn.commit()
            conn.close()

        # Notify admins
        admin_text = (
            "📥 <b>لید جدید MIRA</b>\n\n"
            f"👤 نام: {data['full_name']}\n"
            f"📱 شماره: {data['phone']}\n"
            f"🎓 پایه: {data['grade']}\n"
            f"📚 رشته: {data['field']}\n"
            f"🎯 هدف: {data['goal']}\n"
            f"⚠️ مشکل: {data['problem']}\n"
            f"📝 توضیحات: {data['notes']}\n"
            f"🆔 Chat ID: {chat_id}"
        )

        for admin_id in ADMIN_CHAT_IDS:
            send_message(admin_id, admin_text)

        clear_state(chat_id)

        send_message(
            chat_id,
            "✅ <b>اطلاعاتت با موفقیت ثبت شد.</b>\n\n"
            "ادمین MIRA اطلاعاتت رو بررسی می‌کنه و باهات تماس خواهد گرفت.\n\n"
            "از اعتمادت ممنونیم رفیق ❤️",
            main_keyboard(),
        )


# =========================================================
# PLANS
# =========================================================

def show_plans(chat_id):
    send_message(
        chat_id,
        "🧭 <b>پلن‌های مشاوره MIRA</b>\n\n"
        "برای مشاهده و انتخاب پلن، یکی از گزینه‌های زیر رو انتخاب کن:",
        plan_keyboard(),
    )


def show_plan_details(chat_id, plan_key):
    plan = PLANS[plan_key]

    text = (
        f"🧭 <b>{plan['name']}</b>\n\n"
        f"💰 هزینه ماهانه: {format_price(plan['monthly_price'])}\n"
        f"📅 اشتراک سه‌ماهه: <b>{format_price(plan['three_month_price'])}</b>\n\n"
        "⏳ مدت اشتراک: ۹۰ روز\n\n"
        "اگر این پلن موردنظرته، برای ادامه روی «💳 پرداخت این پلن» بزن."
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "💳 پرداخت این پلن",
                    "callback_data": f"pay_plan:{plan_key}",
                }
            ],
            [
                {
                    "text": "🔙 بازگشت به پلن‌ها",
                    "callback_data": "back_plans",
                }
            ],
        ]
    }

    send_message(chat_id, text, keyboard)


# =========================================================
# PAYMENT FLOW
# =========================================================

def start_payment(chat_id, plan_key):
    student = get_student(chat_id)

    if not student:
        send_message(
            chat_id,
            "⚠️ قبل از پرداخت، ابتدا ثبت‌نام MIRA رو تکمیل کن.\n\n"
            "از منوی پایین روی «📝 ثبت‌نام در MIRA» بزن.",
            main_keyboard(),
        )
        return

    plan = PLANS[plan_key]
    timestamp = now_str()

    with db_lock:
        conn = get_db()

        cursor = conn.execute(
            """
            INSERT INTO mira_payment_requests
            (chat_id, phone, plan_key, plan_name, amount,
             status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                chat_id,
                student["phone"],
                plan_key,
                plan["name"],
                plan["three_month_price"],
                timestamp,
                timestamp,
            ),
        )

        request_id = cursor.lastrowid

        conn.commit()
        conn.close()

    set_state(
        chat_id,
        "waiting_payment_code",
        {
            "request_id": request_id,
            "plan_key": plan_key,
        },
    )

    send_message(
        chat_id,
        "🔐 <b>درخواست پرداخت ثبت شد.</b>\n\n"
        f"🧭 پلن: {plan['name']}\n"
        f"💰 مبلغ: {format_price(plan['three_month_price'])}\n"
        "⏳ وضعیت: در انتظار تأیید ادمین\n\n"
        "ادمین MIRA درخواستت رو بررسی می‌کنه و بعد یک "
        "<b>کد تأیید</b> برات ارسال می‌شه.\n\n"
        "لطفاً تا دریافت کد صبر کن."
    )

    admin_text = (
        "🔐 <b>درخواست پرداخت / تمدید</b>\n\n"
        f"🆔 درخواست: #{request_id}\n"
        f"👤 نام: {student['full_name']}\n"
        f"📱 شماره تماس: {student['phone']}\n"
        f"🧭 پلن: {plan['name']}\n"
        f"💰 مبلغ: {format_price(plan['three_month_price'])}\n"
        f"🆔 Chat ID: {chat_id}\n"
        "⏳ وضعیت: در انتظار صدور کد"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send_message(
            admin_id,
            admin_text,
            admin_request_keyboard(request_id),
        )


def start_issue_code(admin_id, request_id):
    with db_lock:
        conn = get_db()
        request = conn.execute(
            """
            SELECT *
            FROM mira_payment_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        conn.close()

    if not request:
        send_message(admin_id, "❌ درخواست پیدا نشد.")
        return

    set_state(
        admin_id,
        "admin_issue_code",
        {
            "request_id": request_id,
            "student_chat_id": request["chat_id"],
        },
    )

    send_message(
        admin_id,
        "🔐 <b>صدور کد تأیید</b>\n\n"
        f"درخواست: #{request_id}\n\n"
        "کد موردنظر را وارد کن.\n"
        "یا برای ساخت کد تصادفی بنویس:\n"
        "<code>خودکار</code>"
    )


def process_issue_code(admin_id, text):
    state = get_state(admin_id)

    if state.get("state") != "admin_issue_code":
        return False

    data = state["data"]
    request_id = data["request_id"]
    student_chat_id = data["student_chat_id"]

    if text.strip() == "خودکار":
        code = generate_code()
    else:
        code = text.strip()

    if len(code) < 4:
        send_message(
            admin_id,
            "⚠️ کد باید حداقل ۴ کاراکتر داشته باشد."
        )
        return True

    timestamp = now_str()

    with db_lock:
        conn = get_db()

        conn.execute(
            """
            INSERT INTO mira_payment_codes
            (chat_id, request_id, code, status, created_at)
            VALUES (?, ?, ?, 'ACTIVE', ?)
            """,
            (
                student_chat_id,
                request_id,
                code,
                timestamp,
            ),
        )

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'CODE_SENT', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, request_id),
        )

        conn.commit()
        conn.close()

    clear_state(admin_id)

    send_message(
        student_chat_id,
        "🔐 <b>کد تأیید پرداخت MIRA</b>\n\n"
        f"کد شما:\n\n"
        f"<code>{code}</code>\n\n"
        "کد را دقیقاً همین‌طور برای من ارسال کن."
    )

    send_message(
        admin_id,
        "✅ کد با موفقیت صادر و برای دانش‌آموز ارسال شد.",
        admin_keyboard(),
    )

    return True


def verify_payment_code(chat_id, text):
    state = get_state(chat_id)

    if state.get("state") != "waiting_payment_code":
        return False

    request_id = state["data"]["request_id"]
    code = text.strip()

    with db_lock:
        conn = get_db()

        row = conn.execute(
            """
            SELECT *
            FROM mira_payment_codes
            WHERE chat_id = ?
            AND request_id = ?
            AND code = ?
            AND status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                chat_id,
                request_id,
                code,
            ),
        ).fetchone()

        if not row:
            conn.close()

            send_message(
                chat_id,
                "❌ <b>کد صحیح نیست.</b>\n\n"
                "لطفاً کدی که ادمین MIRA برایت ارسال کرده را دقیقاً وارد کن."
            )
            return True

        timestamp = now_str()

        conn.execute(
            """
            UPDATE mira_payment_codes
            SET status = 'USED', used_at = ?
            WHERE id = ?
            """,
            (timestamp, row["id"]),
        )

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'VERIFIED', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, request_id),
        )

        request = conn.execute(
            """
            SELECT *
            FROM mira_payment_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        conn.commit()
        conn.close()

    set_state(
        chat_id,
        "waiting_receipt",
        {
            "request_id": request_id,
            "plan_key": request["plan_key"],
            "amount": request["amount"],
        },
    )

    send_message(
        chat_id,
        "✅ <b>کد تأیید شد.</b>\n\n"
        f"🧭 پلن: {request['plan_name']}\n"
        f"💰 مبلغ: <b>{format_price(request['amount'])}</b>\n\n"
        "💳 <b>اطلاعات پرداخت</b>\n\n"
        f"شماره کارت:\n<code>{CARD_NUMBER}</code>\n\n"
        f"به نام: <b>{CARD_OWNER}</b>\n\n"
        "📌 عنوان پرداخت:\n"
        "هزینه اشتراک سه‌ماهه "
        f"{request['plan_name']} MIRA\n\n"
        "بعد از پرداخت، <b>عکس رسید پرداخت</b> را همین‌جا ارسال کن."
    )

    return True


def process_receipt(chat_id, photo):
    state = get_state(chat_id)

    if state.get("state") != "waiting_receipt":
        return False

    data = state["data"]

    file_id = photo[-1]["file_id"]
    request_id = data["request_id"]

    with db_lock:
        conn = get_db()

        request = conn.execute(
            """
            SELECT *
            FROM mira_payment_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        if not request:
            conn.close()
            send_message(chat_id, "❌ درخواست پرداخت پیدا نشد.")
            return True

        cursor = conn.execute(
            """
            INSERT INTO mira_payments
            (request_id, chat_id, plan_key, plan_name,
             amount, receipt_file_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                request_id,
                chat_id,
                request["plan_key"],
                request["plan_name"],
                request["amount"],
                file_id,
                now_str(),
            ),
        )

        payment_id = cursor.lastrowid

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'RECEIPT_SENT', updated_at = ?
            WHERE id = ?
            """,
            (now_str(), request_id),
        )

        conn.commit()
        conn.close()

    clear_state(chat_id)

    send_message(
        chat_id,
        "📸 <b>رسیدت دریافت شد.</b>\n\n"
        "رسید برای ادمین MIRA ارسال شد و بعد از بررسی، "
        "نتیجه از طریق همین بات بهت اعلام می‌شه.\n\n"
        "لطفاً کمی صبر کن. 🤝",
        main_keyboard(),
    )

    student = get_student(chat_id)

    for admin_id in ADMIN_CHAT_IDS:
        send_message(
            admin_id,
            "📸 <b>رسید پرداخت جدید</b>\n\n"
            f"🆔 پرداخت: #{payment_id}\n"
            f"🆔 درخواست: #{request_id}\n"
            f"👤 نام: {student['full_name'] if student else 'نامشخص'}\n"
            f"📱 شماره: {student['phone'] if student else 'نامشخص'}\n"
            f"🧭 پلن: {request['plan_name']}\n"
            f"💰 مبلغ: {format_price(request['amount'])}\n"
            f"🆔 Chat ID: {chat_id}",
            admin_payment_keyboard(payment_id),
        )

        tg(
            "sendPhoto",
            {
                "chat_id": admin_id,
                "photo": file_id,
                "caption": (
                    f"📸 رسید پرداخت #{payment_id}\n"
                    f"👤 {student['full_name'] if student else 'نامشخص'}\n"
                    f"🧭 {request['plan_name']}\n"
                    f"💰 {format_price(request['amount'])}"
                ),
            },
        )

    return True


# =========================================================
# APPROVE / REJECT PAYMENT
# =========================================================

def approve_payment(admin_id, payment_id):
    with db_lock:
        conn = get_db()

        payment = conn.execute(
            """
            SELECT *
            FROM mira_payments
            WHERE id = ?
            """,
            (payment_id,),
        ).fetchone()

        if not payment:
            conn.close()
            answer_callback("", "پرداخت پیدا نشد.")
            return

        if payment["status"] != "PENDING":
            conn.close()
            send_message(
                admin_id,
                "⚠️ این پرداخت قبلاً بررسی شده است."
            )
            return

        current_sub = conn.execute(
            """
            SELECT *
            FROM mira_subscriptions
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (payment["chat_id"],),
        ).fetchone()

        now = datetime.now()

        if current_sub:
            try:
                current_expiration = datetime.strptime(
                    current_sub["expiration_date"],
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                current_expiration = now

            if (
                current_sub["status"] == "ACTIVE"
                and current_expiration > now
            ):
                start_date = current_expiration
            else:
                start_date = now
        else:
            start_date = now

        expiration = start_date + timedelta(days=90)

        conn.execute(
            """
            INSERT INTO mira_subscriptions
            (chat_id, plan_key, plan_name, status,
             start_date, expiration_date, consultant, updated_at)
            VALUES (?, ?, ?, 'ACTIVE', ?, ?, '', ?)
            """,
            (
                payment["chat_id"],
                payment["plan_key"],
                payment["plan_name"],
                start_date.strftime("%Y-%m-%d %H:%M:%S"),
                expiration.strftime("%Y-%m-%d %H:%M:%S"),
                now_str(),
            ),
        )

        conn.execute(
            """
            UPDATE mira_payments
            SET status = 'APPROVED', approved_at = ?
            WHERE id = ?
            """,
            (now_str(), payment_id),
        )

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'PAID', updated_at = ?
            WHERE id = ?
            """,
            (now_str(), payment["request_id"]),
        )

        conn.commit()
        conn.close()

    send_message(
        payment["chat_id"],
        "🎉 <b>پرداختت با موفقیت تأیید شد!</b>\n\n"
        f"🧭 پلن: <b>{payment['plan_name']}</b>\n"
        "⏳ مدت اشتراک: <b>۹۰ روز</b>\n\n"
        "مرحله بعد، اتصال تو به <b>مشاور مربوطه</b> است.\n\n"
        "لطفاً کمی صبر کن تا ادمین MIRA تو را به مشاور مربوطه متصل کند. 🤝\n\n"
        "از اعتمادت به MIRA ممنونیم رفیق ❤️",
        main_keyboard(),
    )

    send_message(
        admin_id,
        "✅ پرداخت تأیید شد و اشتراک ۹۰ روزه فعال شد.\n\n"
        "حالا باید دانش‌آموز را به مشاور مربوطه متصل کنی.",
        admin_consultant_keyboard(payment["chat_id"]),
    )


def reject_payment(admin_id, payment_id):
    with db_lock:
        conn = get_db()

        payment = conn.execute(
            """
            SELECT *
            FROM mira_payments
            WHERE id = ?
            """,
            (payment_id,),
        ).fetchone()

        if not payment:
            conn.close()
            send_message(admin_id, "❌ پرداخت پیدا نشد.")
            return

        conn.execute(
            """
            UPDATE mira_payments
            SET status = 'REJECTED'
            WHERE id = ?
            """,
            (payment_id,),
        )

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'REJECTED', updated_at = ?
            WHERE id = ?
            """,
            (now_str(), payment["request_id"]),
        )

        conn.commit()
        conn.close()

    send_message(
        payment["chat_id"],
        "❌ <b>رسید پرداخت تأیید نشد.</b>\n\n"
        "لطفاً با پشتیبانی MIRA در ارتباط باش یا در صورت نیاز "
        "رسید صحیح را مجدداً ارسال کن.",
        main_keyboard(),
    )

    send_message(
        admin_id,
        "❌ پرداخت رد شد."
    )


# =========================================================
# CONSULTANT ASSIGNMENT
# =========================================================

def start_assign_consultant(admin_id, student_chat_id):
    set_state(
        admin_id,
        "admin_assign_consultant",
        {
            "student_chat_id": student_chat_id,
        },
    )

    send_message(
        admin_id,
        "👤 <b>اتصال دانش‌آموز به مشاور</b>\n\n"
        "نام مشاور مربوطه را وارد کن.\n\n"
        "مثلاً:\n"
        "<code>دکتر احمدی</code>"
    )


def process_assign_consultant(admin_id, text):
    state = get_state(admin_id)

    if state.get("state") != "admin_assign_consultant":
        return False

    student_chat_id = state["data"]["student_chat_id"]
    consultant = text.strip()

    if not consultant:
        send_message(admin_id, "⚠️ نام مشاور را وارد کن.")
        return True

    with db_lock:
        conn = get_db()

        conn.execute(
            """
            UPDATE mira_students
            SET consultant = ?, updated_at = ?
            WHERE chat_id = ?
            """,
            (
                consultant,
                now_str(),
                student_chat_id,
            ),
        )

        conn.execute(
            """
            UPDATE mira_subscriptions
            SET consultant = ?, updated_at = ?
            WHERE chat_id = ?
            AND id = (
                SELECT id
                FROM mira_subscriptions
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT 1
            )
            """,
            (
                consultant,
                now_str(),
                student_chat_id,
                student_chat_id,
            ),
        )

        conn.commit()
        conn.close()

    clear_state(admin_id)

    send_message(
        student_chat_id,
        "🤝 <b>اتصال به مشاور انجام شد!</b>\n\n"
        f"👨‍🏫 مشاور شما: <b>{consultant}</b>\n\n"
        "از اینجا مسیرت با تیم MIRA شروع می‌شه. 🚀\n\n"
        "برای شروع، منتظر ارتباط مشاورت باش.",
        main_keyboard(),
    )

    send_message(
        admin_id,
        "✅ دانش‌آموز با موفقیت به مشاور متصل شد.",
        admin_keyboard(),
    )

    return True


# =========================================================
# ADMIN LISTS
# =========================================================

def show_users(admin_id):
    with db_lock:
        conn = get_db()
        rows = conn.execute(
            """
            SELECT *
            FROM mira_students
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()

    if not rows:
        send_message(admin_id, "👥 هنوز کاربری ثبت نشده.")
        return

    text = "👥 <b>کاربران MIRA</b>\n\n"

    for row in rows:
        text += (
            f"👤 {row['full_name'] or 'بدون نام'}\n"
            f"📱 {row['phone'] or '-'}\n"
            f"🎓 {row['grade'] or '-'} | {row['field'] or '-'}\n"
            f"🆔 {row['chat_id']}\n"
            f"👨‍🏫 {row['consultant'] or 'تعیین نشده'}\n"
            "────────────\n"
        )

    send_message(admin_id, text)


def show_leads(admin_id):
    with db_lock:
        conn = get_db()
        rows = conn.execute(
            """
            SELECT *
            FROM mira_leads
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()

    if not rows:
        send_message(admin_id, "📥 هنوز لیدی ثبت نشده.")
        return

    text = "📥 <b>لیدهای MIRA</b>\n\n"

    for row in rows:
        text += (
            f"#{row['id']} — {row['full_name']}\n"
            f"📱 {row['phone']}\n"
            f"🎓 {row['grade']} | {row['field']}\n"
            f"🎯 {row['goal']}\n"
            f"🆔 {row['chat_id']}\n"
            "────────────\n"
        )

    send_message(admin_id, text)


def show_payment_requests(admin_id):
    with db_lock:
        conn = get_db()
        rows = conn.execute(
            """
            SELECT *
            FROM mira_payment_requests
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()

    if not rows:
        send_message(admin_id, "💳 درخواست پرداختی وجود ندارد.")
        return

    text = "💳 <b>درخواست‌های پرداخت</b>\n\n"

    for row in rows:
        text += (
            f"#{row['id']}\n"
            f"🧭 {row['plan_name']}\n"
            f"💰 {format_price(row['amount'])}\n"
            f"📱 {row['phone']}\n"
            f"📌 وضعیت: {row['status']}\n"
            f"🆔 {row['chat_id']}\n"
            "────────────\n"
        )

    send_message(admin_id, text)


def show_codes(admin_id):
    with db_lock:
        conn = get_db()
        rows = conn.execute(
            """
            SELECT *
            FROM mira_payment_codes
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()

    if not rows:
        send_message(admin_id, "🔐 هنوز کدی صادر نشده.")
        return

    text = "🔐 <b>کدهای تأیید</b>\n\n"

    for row in rows:
        text += (
            f"#{row['id']} — <code>{row['code']}</code>\n"
            f"🆔 Chat ID: {row['chat_id']}\n"
            f"📌 وضعیت: {row['status']}\n"
            "────────────\n"
        )

    send_message(admin_id, text)


def show_subscriptions(admin_id):
    with db_lock:
        conn = get_db()
        rows = conn.execute(
            """
            SELECT *
            FROM mira_subscriptions
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()

    if not rows:
        send_message(admin_id, "📊 هنوز اشتراکی ثبت نشده.")
        return

    text = "📊 <b>اشتراک‌های MIRA</b>\n\n"

    for row in rows:
        text += (
            f"🧭 {row['plan_name']}\n"
            f"🆔 {row['chat_id']}\n"
            f"📅 {row['start_date']}\n"
            f"📅 {row['expiration_date']}\n"
            f"👨‍🏫 {row['consultant'] or 'تعیین نشده'}\n"
            f"📌 {row['status']}\n"
            "────────────\n"
        )

    send_message(admin_id, text)


# =========================================================
# SUPPORT
# =========================================================

def show_support(chat_id):
    send_message(
        chat_id,
        "🆘 <b>پشتیبانی MIRA</b>\n\n"
        "اگر در ثبت‌نام، پرداخت، اشتراک یا مسیر مشاوره مشکلی داری، "
        "پیامت رو برای پشتیبانی ارسال کن.\n\n"
        "ادمین MIRA در اولین فرصت پیگیری می‌کنه. 🤝",
        main_keyboard(),
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

def handle_callback(query):
    callback_id = query["id"]
    data = query.get("data", "")
    message = query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    answer_callback(callback_id)

    # Membership
    if data == "check_membership":
        if check_membership(chat_id):
            edit_message(
                chat_id,
                message_id,
                "✅ عضویتت تأیید شد!\n\n"
                "حالا می‌تونی وارد MIRA بشی."
            )
            show_home(chat_id)
        else:
            answer_callback(
                callback_id,
                "هنوز عضویت شما در کانال تأیید نشده."
            )
        return

    # Plans
    if data == "back_plans":
        show_plans(chat_id)
        return

    if data.startswith("plan_"):
        plan_key = data.replace("plan_", "", 1)

        if plan_key in PLANS:
            show_plan_details(chat_id, plan_key)

        return

    # Payment plan
    if data.startswith("pay_plan:"):
        plan_key = data.split(":", 1)[1]

        if plan_key in PLANS:
            start_payment(chat_id, plan_key)

        return

    # Admin issue code
    if data.startswith("issue_code:"):
        if not is_admin(chat_id):
            return

        request_id = int(data.split(":", 1)[1])
        start_issue_code(chat_id, request_id)
        return

    # Admin payment approval
    if data.startswith("approve_payment:"):
        if not is_admin(chat_id):
            return

        payment_id = int(data.split(":", 1)[1])
        approve_payment(chat_id, payment_id)
        return

    if data.startswith("reject_payment:"):
        if not is_admin(chat_id):
            return

        payment_id = int(data.split(":", 1)[1])
        reject_payment(chat_id, payment_id)
        return

    # Consultant assignment
    if data.startswith("assign_consultant:"):
        if not is_admin(chat_id):
            return

        student_chat_id = int(data.split(":", 1)[1])
        start_assign_consultant(chat_id, student_chat_id)
        return


# =========================================================
# PHOTO HANDLER
# =========================================================

def handle_photo(chat_id, photo):
    if not require_membership(chat_id):
        return

    if process_receipt(chat_id, photo):
        return

    send_message(
        chat_id,
        "📸 در حال حاضر منتظر دریافت رسید پرداخت نیستم.\n\n"
        "اگر قصد پرداخت داری، از «💳 پرداخت / تمدید» شروع کن."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

def handle_text(chat_id, text):

    # Admin states must be checked first
    if is_admin(chat_id):

        admin_state = get_state(chat_id).get("state")

        if admin_state == "admin_issue_code":
            if process_issue_code(chat_id, text):
                return

        if admin_state == "admin_assign_consultant":
            if process_assign_consultant(chat_id, text):
                return

    # Student payment states
    student_state = get_state(chat_id).get("state")

    if student_state == "waiting_payment_code":
        if verify_payment_code(chat_id, text):
            return

    # Registration state
    if student_state and student_state.startswith("reg_"):
        if not require_membership(chat_id):
            return

        process_registration(chat_id, text)
        return

    # Admin menu
    if is_admin(chat_id):

        if text == "👥 کاربران":
            show_users(chat_id)
            return

        if text == "📥 لیدها":
            show_leads(chat_id)
            return

        if text == "💳 درخواست‌های پرداخت":
            show_payment_requests(chat_id)
            return

        if text == "🔐 کدهای تأیید":
            show_codes(chat_id)
            return

        if text == "📊 اشتراک‌ها":
            show_subscriptions(chat_id)
            return

        if text == "👤 پنل دانش‌آموز":
            show_home(chat_id)
            return

        # If admin is also using student panel,
        # continue below.

    # Membership gate
    if text == "/start":
        if is_admin(chat_id):
            show_admin_home(chat_id)
            return

        if require_membership(chat_id):
            show_home(chat_id)

        return

    if not require_membership(chat_id):
        return

    # Main menu
    if text == "📝 ثبت‌نام در MIRA":
        start_registration(chat_id)
        return

    if text == "🧭 پلن‌های مشاوره":
        show_plans(chat_id)
        return

    if text == "🎓 کلاس‌های کنکوری":
        send_message(
            chat_id,
            "🎓 <b>کلاس‌های کنکوری MIRA</b>\n\n"
            "🚧 دوره‌های کلاس‌های کنکوری MIRA به‌زودی فعال می‌شوند.\n\n"
            "به‌محض فعال شدن، اطلاع‌رسانی خواهد شد.",
            main_keyboard(),
        )
        return

    if text == "💳 پرداخت / تمدید":
        show_plans(chat_id)
        return

    if text == "👤 پنل من":
        send_message(
            chat_id,
            subscription_text(chat_id),
            main_keyboard(),
        )
        return

    if text == "🆘 پشتیبانی":
        show_support(chat_id)
        return

    # Admin can return to admin panel
    if is_admin(chat_id) and text == "/admin":
        show_admin_home(chat_id)
        return

    # Generic text
    send_message(
        chat_id,
        "برای ادامه، یکی از گزینه‌های منوی پایین رو انتخاب کن 👇",
        main_keyboard(),
    )


# =========================================================
# UPDATE HANDLER
# =========================================================

def process_update(update):
    try:
        if "callback_query" in update:
            handle_callback(update["callback_query"])
            return

        message = update.get("message")

        if not message:
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")

        if not chat_id:
            return

        if "photo" in message:
            handle_photo(
                chat_id,
                message["photo"],
            )
            return

        if "text" in message:
            handle_text(
                chat_id,
                message["text"].strip(),
            )
            return

    except Exception as e:
        print("Update error:", e)


# =========================================================
# WEBHOOK SERVER
# =========================================================

class WebhookHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"MIRA BOT is running.")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get("Content-Length", 0)
            )

            body = self.rfile.read(content_length)
            update = json.loads(body.decode("utf-8"))

            threading.Thread(
                target=process_update,
                args=(update,),
                daemon=True,
            ).start()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            print("Webhook error:", e)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


# =========================================================
# WEBHOOK SETUP
# =========================================================

def setup_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")

    if not render_url:
        print("WARNING: RENDER_EXTERNAL_URL is not set.")
        return

    webhook_url = f"{render_url}/telegram-webhook"

    result = tg(
        "setWebhook",
        {
            "url": webhook_url,
            "drop_pending_updates": False,
        },
    )

    print("Webhook setup:", result)


# =========================================================
# START
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    print("====================================")
    print("MIRA BOT STARTING")
    print("====================================")
    print("Admins:", ADMIN_CHAT_IDS)
    print("Port:", PORT)

    setup_webhook()

    server = HTTPServer(
        ("0.0.0.0", PORT),
        WebhookHandler,
    )

    print(f"MIRA BOT listening on port {PORT}")

    server.serve_forever()


if __name__ == "__main__":
    main()
