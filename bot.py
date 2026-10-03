import os
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_CHAT_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
]

DB_PATH = os.getenv("DB_PATH", "mira.db")

API = f"https://api.telegram.org/bot{TOKEN}"

CHANNEL_USERNAME = "@miracampus"
CHANNEL_URL = "https://t.me/miracampus"

WEBHOOK_PATH = "/telegram-webhook"

SUBSCRIPTION_DAYS = 90


# =========================================================
# COURSES
# =========================================================

COURSES = {
    "classes": {
        "name": "🎓 کلاس‌های آموزش از صفر کنکور MIRA",
        "url": "https://t.me/mirakunkorclss"
    },
    "counseling": {
        "name": "🧭 پلن مشاوره‌ای صفر تا صد تیم MIRA",
        "url": "https://t.me/miraprivatecahnnel"
    }
}


# =========================================================
# REGISTRATION QUESTIONS
# =========================================================

QUESTIONS = [
    {
        "key": "full_name",
        "text": "👤 نام و نام خانوادگی‌ات رو وارد کن:"
    },
    {
        "key": "grade",
        "text": "🎓 پایه تحصیلی‌ات رو انتخاب کن:",
        "options": [
            "دهم",
            "یازدهم",
            "دوازدهم",
            "فارغ‌التحصیل / پشت‌کنکوری",
            "دانشجو"
        ]
    },
    {
        "key": "field",
        "text": "📚 رشته تحصیلی‌ات چیه؟"
    },
    {
        "key": "goal",
        "text": "🎯 مهم‌ترین هدفت چیه؟",
        "options": [
            "موفقیت در مدرسه و امتحانات",
            "آمادگی برای کنکور",
            "رسیدن به رتبه و دانشگاه خوب",
            "تقویت دروس و رفع ضعف‌ها",
            "هنوز دقیق نمی‌دونم"
        ]
    },
    {
        "key": "problem",
        "text": "🧩 بزرگ‌ترین مشکلت در مسیر درس خوندن چیه؟",
        "options": [
            "یادگیری و فهم مطالب",
            "برنامه‌ریزی",
            "نظم و استمرار",
            "تست زدن",
            "تمرکز",
            "آزمون و تحلیل",
            "رفع اشکال",
            "نمی‌دونم"
        ]
    },
    {
        "key": "extra",
        "text": "📝 اگر نکته یا توضیح دیگه‌ای هست که فکر می‌کنی باید بدونیم، برامون بنویس.\n\nاگر موردی نداری، بنویس «ندارم»."
    },
    {
        "key": "phone",
        "text": "📱 برای اینکه ادمین MIRA بتونه باهات تماس بگیره، شماره تماست رو ارسال کن:"
    }
]


# =========================================================
# IN-MEMORY USER STATES
# =========================================================

users = {}


def new_user():
    return {
        "mode": None,
        "step": 0,
        "data": {}
    }


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Students
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_students (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            data_json TEXT,
            created_at TEXT
        )
    """)

    # Payment / renewal authentication requests
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            username TEXT,
            phone TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT
        )
    """)

    # Verification codes
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

    conn.commit()
    conn.close()


def save_student(chat_id, username, data):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO mira_students
        (chat_id, username, data_json, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        username,
        json.dumps(data, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat()
    ))

    conn.commit()
    conn.close()


def save_payment_request(chat_id, username, phone):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO mira_payment_requests
        (chat_id, username, phone, status, created_at)
        VALUES (?, ?, ?, 'PENDING', ?)
    """, (
        chat_id,
        username,
        phone,
        datetime.now(timezone.utc).isoformat()
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    return request_id


def save_verification_code(chat_id, request_id, code):
    conn = get_db()
    cur = conn.cursor()

    # Any previous active code for this user becomes inactive
    cur.execute("""
        UPDATE mira_payment_codes
        SET status = 'REPLACED'
        WHERE chat_id = ?
        AND status = 'ACTIVE'
    """, (chat_id,))

    cur.execute("""
        INSERT INTO mira_payment_codes
        (chat_id, request_id, code, status, created_at)
        VALUES (?, ?, ?, 'ACTIVE', ?)
    """, (
        chat_id,
        request_id,
        code,
        datetime.now(timezone.utc).isoformat()
    ))

    code_id = cur.lastrowid

    conn.commit()
    conn.close()

    return code_id


def verify_code(chat_id, code):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, request_id
        FROM mira_payment_codes
        WHERE chat_id = ?
        AND code = ?
        AND status = 'ACTIVE'
        ORDER BY id DESC
        LIMIT 1
    """, (
        chat_id,
        code
    ))

    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    code_id, request_id = row

    now = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        UPDATE mira_payment_codes
        SET status = 'USED',
            used_at = ?
        WHERE id = ?
    """, (
        now,
        code_id
    ))

    # Mark related payment request as approved
    if request_id:
        cur.execute("""
            UPDATE mira_payment_requests
            SET status = 'CODE_APPROVED'
            WHERE id = ?
        """, (request_id,))

    conn.commit()
    conn.close()

    return {
        "code_id": code_id,
        "request_id": request_id
    }


# =========================================================
# TELEGRAM API
# =========================================================

def telegram(method, data=None):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data or {},
            timeout=20
        )

        return response.json()

    except Exception as e:
        print("Telegram API error:", e)
        return None


def send(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram("sendMessage", data)


def answer_callback(callback_id, text=None):
    data = {
        "callback_query_id": callback_id
    }

    if text:
        data["text"] = text

    return telegram("answerCallbackQuery", data)


# =========================================================
# MEMBERSHIP
# =========================================================

def is_channel_member(chat_id):
    result = telegram(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": chat_id
        }
    )

    if not result or not result.get("ok"):
        return False

    status = result["result"].get("status")

    return status in [
        "creator",
        "administrator",
        "member"
    ]


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


def send_membership_gate(chat_id):
    send(
        chat_id,
        "برای استفاده از خدمات MIRA ابتدا باید عضو کانال اصلی ما بشی. 👇\n\n"
        "بعد از عضویت روی «✅ بررسی عضویت» بزن.",
        membership_keyboard()
    )


# =========================================================
# MAIN MENU
# =========================================================

def main_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "📝 ثبت‌نام و درخواست مشاوره"}],
            [{"text": "🎓 معرفی دوره‌ها"}],
            [{"text": "💳 پرداخت و تمدید اشتراک"}],
            [{"text": "👤 پنل من"}],
            [{"text": "🆘 پشتیبانی"}]
        ],
        "resize_keyboard": True
    }


def send_main_menu(chat_id):
    send(
        chat_id,
        "سلام رفیق 👋\n\n"
        "به MIRA خوش اومدی. ✨\n\n"
        "اینجا می‌تونی دوره‌های MIRA رو ببینی، "
        "برای مشاوره درخواست بدی، وضعیت اشتراکت رو بررسی کنی "
        "و با پشتیبانی در ارتباط باشی.\n\n"
        "چطور می‌تونم کمکت کنم؟ 🤍",
        main_menu_keyboard()
    )


# =========================================================
# COURSES
# =========================================================

def courses_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🎓 کلاس‌های آموزش از صفر کنکور MIRA",
                    "url": COURSES["classes"]["url"]
                }
            ],
            [
                {
                    "text": "🧭 پلن مشاوره‌ای صفر تا صد تیم MIRA",
                    "url": COURSES["counseling"]["url"]
                }
            ],
            [
                {
                    "text": "🔙 بازگشت به منوی اصلی",
                    "callback_data": "back_to_main"
                }
            ]
        ]
    }


def send_courses_menu(chat_id):
    send(
        chat_id,
        "🎓 دوره‌های MIRA\n\n"
        "برای مشاهده توضیحات کامل هر دوره، "
        "روی دوره موردنظرت بزن. 👇",
        courses_keyboard()
    )


# =========================================================
# REGISTRATION
# =========================================================

def ask_question(chat_id):
    user = users.get(chat_id)

    if not user:
        users[chat_id] = new_user()
        user = users[chat_id]

    step = user["step"]

    if step >= len(QUESTIONS):
        finish_registration(chat_id)
        return

    question = QUESTIONS[step]

    keyboard = None

    if "options" in question:
        keyboard = {
            "keyboard": [
                [{"text": option}]
                for option in question["options"]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }

    elif question["key"] == "phone":
        keyboard = {
            "keyboard": [
                [
                    {
                        "text": "📱 ارسال شماره تماس",
                        "request_contact": True
                    }
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }

    send(
        chat_id,
        question["text"],
        keyboard
    )


def start_registration(chat_id):
    users[chat_id] = new_user()
    users[chat_id]["mode"] = "registration"
    users[chat_id]["step"] = 0

    send(
        chat_id,
        "عالیه رفیق 👌\n\n"
        "برای اینکه بتونیم دقیق‌تر راهنماییت کنیم، "
        "چند سؤال کوتاه ازت می‌پرسیم.\n"
        "در آخر اطلاعاتت برای تیم MIRA ارسال می‌شه. 🤍"
    )

    ask_question(chat_id)


def finish_registration(chat_id):
    user = users.get(chat_id)

    if not user:
        return

    data = user["data"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT username FROM mira_students WHERE chat_id = ?",
        (chat_id,)
    )

    old = cur.fetchone()
    username = old[0] if old else ""

    conn.close()

    save_student(chat_id, username, data)

    summary = (
        "📥 درخواست جدید MIRA\n\n"
        f"👤 نام: {data.get('full_name', '-')}\n"
        f"🎓 پایه: {data.get('grade', '-')}\n"
        f"📚 رشته: {data.get('field', '-')}\n"
        f"🎯 هدف: {data.get('goal', '-')}\n"
        f"🧩 مشکل اصلی: {data.get('problem', '-')}\n"
        f"📝 توضیحات: {data.get('extra', '-')}\n"
        f"📱 شماره تماس: {data.get('phone', '-')}\n\n"
        f"🆔 Chat ID: {chat_id}"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send(admin_id, summary)

    send(
        chat_id,
        "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
        "ادمین MIRA باهات تماس خواهد گرفت.\n\n"
        "از اعتمادت ممنونیم رفیق 🤍",
        main_menu_keyboard()
    )

    users.pop(chat_id, None)


# =========================================================
# PAYMENT / RENEWAL
# =========================================================

def payment_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "🔐 ورود کد تأیید"}],
            [{"text": "📱 ثبت درخواست احراز هویت"}],
            [{"text": "🔙 بازگشت به منوی اصلی"}]
        ],
        "resize_keyboard": True
    }


def payment_start_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📱 ارسال شماره تماس",
                    "request_contact": True
                }
            ],
            [
                {
                    "text": "🔙 بازگشت به منوی اصلی"
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def send_payment_menu(chat_id):
    send(
        chat_id,
        "💳 پرداخت و تمدید اشتراک MIRA\n\n"
        "اشتراک‌های MIRA به‌صورت **۹۰ روزه** ارائه می‌شن.\n\n"
        "اگر قبلاً از ادمین یا مشاورت کد تأیید گرفتی، "
        "می‌تونی واردش کنی.\n\n"
        "اگر هنوز کد نداری، ابتدا درخواست احراز هویت ثبت کن. 👇",
        payment_menu_keyboard()
    )


def start_payment_request(chat_id):
    users[chat_id] = new_user()
    users[chat_id]["mode"] = "payment_authentication"

    send(
        chat_id,
        "💳 پرداخت و تمدید اشتراک MIRA\n\n"
        "اشتراک‌های MIRA به‌صورت **۹۰ روزه** ارائه می‌شن.\n\n"
        "برای شروع فرآیند پرداخت یا تمدید، "
        "ابتدا شماره تماست رو ارسال کن تا درخواستت برای "
        "تیم MIRA ثبت و احراز بشه.\n\n"
        "بعد از بررسی توسط ادمین یا مشاورت، "
        "کد تأیید در اختیارت قرار می‌گیره. 🔐",
        payment_start_keyboard()
    )


def handle_payment_phone(chat_id, username, phone):
    request_id = save_payment_request(
        chat_id=chat_id,
        username=username,
        phone=phone
    )

    if username:
        admin_message = (
            "🔐 درخواست احراز هویت پرداخت / تمدید\n\n"
            f"🆔 درخواست: #{request_id}\n"
            f"👤 Username: @{username}\n"
            f"📱 شماره تماس: {phone}\n"
            f"🆔 Chat ID: {chat_id}\n"
            f"⏳ وضعیت: در انتظار بررسی"
        )
    else:
        admin_message = (
            "🔐 درخواست احراز هویت پرداخت / تمدید\n\n"
            f"🆔 درخواست: #{request_id}\n"
            f"📱 شماره تماس: {phone}\n"
            f"🆔 Chat ID: {chat_id}\n"
            f"⏳ وضعیت: در انتظار بررسی"
        )

    for admin_id in ADMIN_CHAT_IDS:
        send(admin_id, admin_message)

    send(
        chat_id,
        "✅ درخواستت با موفقیت ثبت شد.\n\n"
        "اطلاعاتت برای تیم MIRA ارسال شد و بعد از بررسی، "
        "کد تأییدت رو از ادمین یا مشاورت دریافت می‌کنی. 🔐\n\n"
        "بعد از دریافت کد، از بخش «💳 پرداخت و تمدید اشتراک» "
        "می‌تونی کد رو وارد کنی. 🤍",
        main_menu_keyboard()
    )

    users.pop(chat_id, None)


# =========================================================
# CODE INPUT
# =========================================================

def start_code_input(chat_id):
    users[chat_id] = new_user()
    users[chat_id]["mode"] = "verification_code"

    send(
        chat_id,
        "🔐 ورود کد تأیید\n\n"
        "کدی که از ادمین یا مشاورت دریافت کردی رو همینجا وارد کن:",
    )


def handle_verification_code(chat_id, code):
    code = code.strip()

    if not code:
        send(
            chat_id,
            "❌ لطفاً کد تأیید رو وارد کن."
        )
        return

    result = verify_code(chat_id, code)

    if not result:
        send(
            chat_id,
            "❌ کد تأیید نامعتبره یا قبلاً استفاده شده.\n\n"
            "اگر مطمئنی کد درست رو وارد کردی، "
            "با ادمین یا مشاورت هماهنگ کن.",
            payment_menu_keyboard()
        )
        users.pop(chat_id, None)
        return

    send(
        chat_id,
        "✅ کد تأیید شد.\n\n"
        "احراز هویتت توسط تیم MIRA تأیید شد. 🔐\n\n"
        "در مرحله بعد اطلاعات پرداخت در اختیارت قرار می‌گیره.\n\n"
        "فعلاً این مرحله تکمیل شده؛ از اعتمادت ممنونیم رفیق 🤍",
        main_menu_keyboard()
    )

    for admin_id in ADMIN_CHAT_IDS:
        send(
            admin_id,
            "✅ کد تأیید توسط کاربر استفاده شد.\n\n"
            f"🆔 Chat ID: {chat_id}\n"
            f"🆔 Request ID: #{result['request_id']}\n"
            f"🔑 Code ID: #{result['code_id']}"
        )

    users.pop(chat_id, None)


# =========================================================
# ADMIN COMMAND — ISSUE CODE
# =========================================================

def issue_code(command_text, admin_chat_id):
    if admin_chat_id not in ADMIN_CHAT_IDS:
        return

    parts = command_text.strip().split()

    if len(parts) != 3:
        send(
            admin_chat_id,
            "فرمت صحیح:\n\n"
            "/issuecode CHAT_ID CODE\n\n"
            "مثال:\n"
            "/issuecode 123456789 MIRA7392"
        )
        return

    try:
        target_chat_id = int(parts[1])
    except ValueError:
        send(
            admin_chat_id,
            "❌ Chat ID باید عددی باشه."
        )
        return

    code = parts[2].strip()

    if not code:
        send(
            admin_chat_id,
            "❌ کد نمی‌تونه خالی باشه."
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM mira_payment_requests
        WHERE chat_id = ?
        AND status = 'PENDING'
        ORDER BY id DESC
        LIMIT 1
    """, (target_chat_id,))

    row = cur.fetchone()

    conn.close()

    if not row:
        send(
            admin_chat_id,
            "⚠️ برای این Chat ID درخواست پرداخت/تمدید در وضعیت «در انتظار بررسی» پیدا نشد."
        )
        return

    request_id = row[0]

    code_id = save_verification_code(
        target_chat_id,
        request_id,
        code
    )

    send(
        target_chat_id,
        "🔐 کد تأیید MIRA\n\n"
        f"کد تأیید شما:\n\n"
        f"`{code}`\n\n"
        "برای ادامه، وارد بخش «💳 پرداخت و تمدید اشتراک» شو "
        "و گزینه «🔐 ورود کد تأیید» رو انتخاب کن.",
        main_menu_keyboard()
    )

    send(
        admin_chat_id,
        "✅ کد تأیید با موفقیت صادر شد.\n\n"
        f"👤 Chat ID: {target_chat_id}\n"
        f"🆔 Request ID: #{request_id}\n"
        f"🔑 Code ID: #{code_id}\n"
        f"🔐 Code: {code}"
    )


# =========================================================
# USER PANEL
# =========================================================

def send_user_panel(chat_id):
    send(
        chat_id,
        "👤 پنل من\n\n"
        "بخش پنل شخصی MIRA در مرحله بعد تکمیل می‌شه. 🔐\n\n"
        "در این بخش اطلاعاتی مثل دوره، مشاور، "
        "تاریخ شروع، تاریخ پایان و روزهای باقی‌مانده "
        "اشتراک نمایش داده خواهد شد.",
        main_menu_keyboard()
    )


# =========================================================
# SUPPORT
# =========================================================

def send_support(chat_id):
    send(
        chat_id,
        "🆘 پشتیبانی MIRA\n\n"
        "اگر در مورد ثبت‌نام، دوره‌ها، مشاوره یا اشتراکت "
        "سؤالی داری، پیام بده تا تیم MIRA راهنماییت کنه. 🤍",
        main_menu_keyboard()
    )


# =========================================================
# TEXT HANDLER
# =========================================================

def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id:
        return

    username = chat.get("username", "")
    text = message.get("text", "")
    contact = message.get("contact")

    # -----------------------------------------------------
    # ADMIN COMMANDS
    # -----------------------------------------------------

    if text.startswith("/issuecode"):
        issue_code(text, chat_id)
        return

    # -----------------------------------------------------
    # /start
    # -----------------------------------------------------

    if text.startswith("/start"):
        users.pop(chat_id, None)

        if not is_channel_member(chat_id):
            send_membership_gate(chat_id)
            return

        send_main_menu(chat_id)
        return

    # -----------------------------------------------------
    # Membership gate
    # -----------------------------------------------------

    if not is_channel_member(chat_id):
        send_membership_gate(chat_id)
        return

    # -----------------------------------------------------
    # Existing user state
    # -----------------------------------------------------

    user = users.get(chat_id)

    if user:

        mode = user.get("mode")

        # ---------------------------------------------
        # Registration
        # ---------------------------------------------

        if mode == "registration":

            step = user["step"]
            question = QUESTIONS[step]
            key = question["key"]

            if key == "phone":

                if contact:
                    phone = contact.get("phone_number", "")
                else:
                    phone = text.strip()

                if not phone:
                    send(
                        chat_id,
                        "لطفاً شماره تماست رو ارسال کن. 📱"
                    )
                    return

                user["data"]["phone"] = phone
                user["step"] += 1

                finish_registration(chat_id)
                return

            if "options" in question:
                if text not in question["options"]:
                    send(
                        chat_id,
                        "لطفاً یکی از گزینه‌های مشخص‌شده رو انتخاب کن. 👇"
                    )
                    return

            if not text.strip():
                send(
                    chat_id,
                    "لطفاً پاسخ این سؤال رو وارد کن. 👇"
                )
                return

            user["data"][key] = text.strip()
            user["step"] += 1

            ask_question(chat_id)
            return

        # ---------------------------------------------
        # Payment authentication
        # ---------------------------------------------

        if mode == "payment_authentication":

            if contact:
                phone = contact.get("phone_number", "")
            else:
                phone = text.strip()

            if not phone:
                send(
                    chat_id,
                    "لطفاً شماره تماست رو ارسال کن. 📱"
                )
                return

            handle_payment_phone(
                chat_id=chat_id,
                username=username,
                phone=phone
            )
            return

        # ---------------------------------------------
        # Verification code
        # ---------------------------------------------

        if mode == "verification_code":

            if text in [
                "🔙 بازگشت به منوی اصلی",
                "💳 پرداخت و تمدید اشتراک"
            ]:
                users.pop(chat_id, None)
                send_payment_menu(chat_id)
                return

            handle_verification_code(
                chat_id,
                text
            )
            return

    # -----------------------------------------------------
    # Main menu
    # -----------------------------------------------------

    if text == "📝 ثبت‌نام و درخواست مشاوره":

        start_registration(chat_id)
        return

    if text == "🎓 معرفی دوره‌ها":

        send_courses_menu(chat_id)
        return

    if text == "💳 پرداخت و تمدید اشتراک":

        send_payment_menu(chat_id)
        return

    if text == "👤 پنل من":

        send_user_panel(chat_id)
        return

    if text == "🆘 پشتیبانی":

        send_support(chat_id)
        return

    # -----------------------------------------------------
    # Payment menu
    # -----------------------------------------------------

    if text == "🔐 ورود کد تأیید":

        start_code_input(chat_id)
        return

    if text == "📱 ثبت درخواست احراز هویت":

        start_payment_request(chat_id)
        return

    # -----------------------------------------------------
    # Back to main
    # -----------------------------------------------------

    if text == "🔙 بازگشت به منوی اصلی":

        send_main_menu(chat_id)
        return

    # -----------------------------------------------------
    # Unknown message
    # -----------------------------------------------------

    send(
        chat_id,
        "از منوی پایین می‌تونی بخش موردنظرت رو انتخاب کنی. 👇",
        main_menu_keyboard()
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

def handle_callback(callback_query):
    callback_id = callback_query.get("id")
    data = callback_query.get("data")

    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id:
        return

    # -----------------------------------------------------
    # Membership check
    # -----------------------------------------------------

    if data == "check_membership":

        if is_channel_member(chat_id):

            answer_callback(
                callback_id,
                "عضویتت تأیید شد ✅"
            )

            send_main_menu(chat_id)

        else:

            answer_callback(
                callback_id,
                "هنوز عضویتت تأیید نشده ❌"
            )

            send_membership_gate(chat_id)

        return

    # -----------------------------------------------------
    # Back to main
    # -----------------------------------------------------

    if data == "back_to_main":

        answer_callback(callback_id)

        send_main_menu(chat_id)

        return

    answer_callback(callback_id)


# =========================================================
# HTTP SERVER
# =========================================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path in ["/", "/health"]:
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.end_headers()

            self.wfile.write(
                b"MIRA Bot is running"
            )

            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):

        parsed = urlparse(self.path)

        if parsed.path != WEBHOOK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        try:

            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )

            if "message" in update:

                handle_message(
                    update["message"]
                )

            elif "callback_query" in update:

                handle_callback(
                    update["callback_query"]
                )

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.end_headers()

            self.wfile.write(
                b'{"ok":true}'
            )

        except Exception as e:

            print("Webhook error:", e)

            self.send_response(200)
            self.end_headers()

            self.wfile.write(
                b'{"ok":false}'
            )

    def log_message(self, format, *args):
        return


# =========================================================
# START
# =========================================================

def main():

    if not TOKEN:
        print("ERROR: BOT_TOKEN is not set.")
        return

    init_db()

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    external_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        ""
    ).strip()

    if external_url:

        webhook_url = (
            external_url.rstrip("/")
            + WEBHOOK_PATH
        )

        result = telegram(
            "setWebhook",
            {
                "url": webhook_url,
                "allowed_updates": [
                    "message",
                    "callback_query"
                ]
            }
        )

        print(
            "Webhook:",
            result
        )

    print(
        f"MIRA Bot running on port {port}"
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
