import os
import json
import sqlite3
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", "10000"))

CHANNEL_USERNAME = "@miracampus"

ADMIN_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",")
    if x.strip()
}

DB_PATH = os.environ.get("DB_PATH", "mira.db")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================================================
# RUNTIME STATE
# =========================================================

# فقط وضعیت موقت گفتگوها
states = {}


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            grade TEXT,
            field TEXT,
            goal TEXT,
            problem TEXT,
            notes TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            phone TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_payment_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            request_id INTEGER,
            code TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            used_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# TELEGRAM API
# =========================================================

def telegram(method, data=None):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            json=data or {},
            timeout=30
        )
        return response.json()
    except Exception as e:
        print("Telegram error:", e)
        return {}


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:
        data["reply_markup"] = reply_markup

    return telegram("sendMessage", data)


def answer_callback(callback_id):
    telegram("answerCallbackQuery", {
        "callback_query_id": callback_id
    })


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }

    if reply_markup is not None:
        data["reply_markup"] = reply_markup

    return telegram("editMessageText", data)


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return {
        "keyboard": [
            [{"text": "📝 ثبت‌نام در MIRA"}],
            [{"text": "🎓 دوره‌های MIRA"}, {"text": "💳 تمدید / پرداخت"}],
            [{"text": "👤 پنل من"}, {"text": "🆘 پشتیبانی"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def registration_keyboard():
    return {
        "keyboard": [
            [{"text": "🎓 دهم"}, {"text": "🎓 یازدهم"}],
            [{"text": "🎓 دوازدهم"}, {"text": "🎓 فارغ‌التحصیل"}],
            [{"text": "❌ لغو ثبت‌نام"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def field_keyboard():
    return {
        "keyboard": [
            [{"text": "🧪 تجربی"}, {"text": "📐 ریاضی"}],
            [{"text": "💻 فنی‌وحرفه‌ای"}, {"text": "🎨 هنر"}],
            [{"text": "📚 انسانی"}, {"text": "🔹 سایر"}],
            [{"text": "❌ لغو ثبت‌نام"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def cancel_keyboard():
    return {
        "keyboard": [
            [{"text": "❌ لغو"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def phone_keyboard():
    return {
        "keyboard": [
            [{
                "text": "📱 ارسال شماره تلفن",
                "request_contact": True
            }],
            [{"text": "❌ لغو ثبت‌نام"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def admin_keyboard():
    return {
        "keyboard": [
            [{"text": "👥 کاربران"}, {"text": "📥 لیدها"}],
            [{"text": "💳 درخواست‌های پرداخت"}],
            [{"text": "🔐 کدهای تأیید"}],
            [{"text": "👨‍🎓 پنل دانش‌آموز"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def remove_keyboard():
    return {
        "remove_keyboard": True
    }


def membership_keyboard():
    return {
        "inline_keyboard": [
            [{
                "text": "📢 عضویت در کانال MIRA",
                "url": "https://t.me/miracampus"
            }],
            [{
                "text": "✅ بررسی عضویت",
                "callback_data": "check_membership"
            }]
        ]
    }


# =========================================================
# MEMBERSHIP
# =========================================================

def is_member(chat_id):
    result = telegram("getChatMember", {
        "chat_id": CHANNEL_USERNAME,
        "user_id": chat_id
    })

    if not result.get("ok"):
        print("Membership check failed:", result)
        return False

    status = result.get("result", {}).get("status")

    return status in {
        "creator",
        "administrator",
        "member"
    }


def show_membership_gate(chat_id):
    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "برای استفاده از امکانات MIRA ابتدا باید عضو کانال اصلی ما بشی.\n\n"
        "بعد از عضویت روی «بررسی عضویت» بزن.",
        membership_keyboard()
    )


# =========================================================
# USER DATA
# =========================================================

def get_student(chat_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM mira_students WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()
    conn.close()
    return row


def save_student(chat_id, data):
    conn = db()

    existing = conn.execute(
        "SELECT id FROM mira_students WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE mira_students
            SET full_name = ?,
                grade = ?,
                field = ?,
                goal = ?,
                problem = ?,
                notes = ?,
                phone = ?
            WHERE chat_id = ?
        """, (
            data.get("full_name"),
            data.get("grade"),
            data.get("field"),
            data.get("goal"),
            data.get("problem"),
            data.get("notes"),
            data.get("phone"),
            chat_id
        ))
    else:
        conn.execute("""
            INSERT INTO mira_students
            (chat_id, full_name, grade, field, goal, problem, notes, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            data.get("full_name"),
            data.get("grade"),
            data.get("field"),
            data.get("goal"),
            data.get("problem"),
            data.get("notes"),
            data.get("phone")
        ))

    conn.commit()
    conn.close()


# =========================================================
# MAIN MENU
# =========================================================

def show_main_menu(chat_id):
    states.pop(chat_id, None)

    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "به MIRA خوش اومدی.\n"
        "چطور می‌تونم کمکت کنم؟",
        main_keyboard()
    )


# =========================================================
# COURSES
# =========================================================

def show_courses(chat_id):
    send_message(
        chat_id,
        "🎓 دوره‌های MIRA\n\n"
        "برای ورود به هر دوره روی لینک مربوط به خودش بزن:",
        {
            "inline_keyboard": [
                [{
                    "text": "🎓 کلاس‌های آموزش از صفر کنکور MIRA",
                    "url": "https://t.me/mirakunkorclss"
                }],
                [{
                    "text": "🧭 پلن مشاوره‌ای صفر تا صد تیم MIRA",
                    "url": "https://t.me/miraprivatecahnnel"
                }]
            ]
        }
    )


# =========================================================
# REGISTRATION
# =========================================================

def start_registration(chat_id):
    states[chat_id] = {
        "flow": "registration",
        "step": "full_name",
        "data": {}
    }

    send_message(
        chat_id,
        "📝 ثبت‌نام در MIRA\n\n"
        "اول از همه اسم و فامیلیت رو برام بفرست.",
        cancel_keyboard()
    )


def registration_step(chat_id, message):
    state = states.get(chat_id)

    if not state or state.get("flow") != "registration":
        return False

    step = state.get("step")
    data = state["data"]

    # لغو
    if message == "❌ لغو ثبت‌نام":
        show_main_menu(chat_id)
        return True

    # نام
    if step == "full_name":
        data["full_name"] = message
        state["step"] = "grade"

        send_message(
            chat_id,
            "عالیه 👌\n\n"
            "پایه تحصیلیت رو انتخاب کن:",
            registration_keyboard()
        )
        return True

    # پایه
    if step == "grade":
        grades = {
            "🎓 دهم": "دهم",
            "🎓 یازدهم": "یازدهم",
            "🎓 دوازدهم": "دوازدهم",
            "🎓 فارغ‌التحصیل": "فارغ‌التحصیل"
        }

        if message not in grades:
            send_message(
                chat_id,
                "لطفاً یکی از گزینه‌های پایه رو انتخاب کن.",
                registration_keyboard()
            )
            return True

        data["grade"] = grades[message]
        state["step"] = "field"

        send_message(
            chat_id,
            "رشته‌ات رو انتخاب کن:",
            field_keyboard()
        )
        return True

    # رشته
    if step == "field":
        fields = {
            "🧪 تجربی": "تجربی",
            "📐 ریاضی": "ریاضی",
            "💻 فنی‌وحرفه‌ای": "فنی‌وحرفه‌ای",
            "🎨 هنر": "هنر",
            "📚 انسانی": "انسانی",
            "🔹 سایر": "سایر"
        }

        if message not in fields:
            send_message(
                chat_id,
                "لطفاً یکی از گزینه‌های رشته رو انتخاب کن.",
                field_keyboard()
            )
            return True

        data["field"] = fields[message]
        state["step"] = "goal"

        send_message(
            chat_id,
            "🎯 هدفت از کنکور یا استفاده از خدمات MIRA چیه؟\n\n"
            "به صورت کوتاه برام بنویس.",
            cancel_keyboard()
        )
        return True

    # هدف
    if step == "goal":
        data["goal"] = message
        state["step"] = "problem"

        send_message(
            chat_id,
            "بزرگ‌ترین مشکل درسی یا مطالعاتی‌ات الان چیه؟",
            cancel_keyboard()
        )
        return True

    # مشکل
    if step == "problem":
        data["problem"] = message
        state["step"] = "notes"

        send_message(
            chat_id,
            "اگر نکته یا توضیح دیگه‌ای داری برام بنویس.\n\n"
            "اگر چیزی نداری، بنویس «ندارم».",
            cancel_keyboard()
        )
        return True

    # توضیحات
    if step == "notes":
        data["notes"] = message
        state["step"] = "phone"

        send_message(
            chat_id,
            "📱 در مرحله آخر شماره تلفنت رو بفرست.\n\n"
            "می‌تونی از دکمه ارسال شماره استفاده کنی.",
            phone_keyboard()
        )
        return True

    # تلفن
    if step == "phone":
        data["phone"] = message
        finish_registration(chat_id)
        return True

    return True


def finish_registration(chat_id):
    state = states.get(chat_id)

    if not state:
        return

    data = state["data"]

    save_student(chat_id, data)

    # اطلاع به ادمین‌ها
    admin_text = (
        "📥 لید جدید MIRA\n\n"
        f"👤 نام: {data.get('full_name')}\n"
        f"🎓 پایه: {data.get('grade')}\n"
        f"📚 رشته: {data.get('field')}\n"
        f"🎯 هدف: {data.get('goal')}\n"
        f"⚠️ مشکل: {data.get('problem')}\n"
        f"📝 توضیحات: {data.get('notes')}\n"
        f"📱 شماره: {data.get('phone')}\n"
        f"🆔 Chat ID: {chat_id}"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send_message(admin_id, admin_text)

    states.pop(chat_id, None)

    send_message(
        chat_id,
        "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
        "ادمین MIRA باهات تماس خواهد گرفت.",
        main_keyboard()
    )


# =========================================================
# PAYMENT AUTHENTICATION
# =========================================================

def start_payment(chat_id):
    student = get_student(chat_id)

    if not student:
        send_message(
            chat_id,
            "برای ادامه ابتدا ثبت‌نامت رو کامل کن.",
            main_keyboard()
        )
        return

    conn = db()

    cur = conn.execute("""
        INSERT INTO mira_payment_requests
        (chat_id, phone, status)
        VALUES (?, ?, 'PENDING')
    """, (
        chat_id,
        student["phone"] or ""
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    text = (
        "🔐 درخواست احراز هویت پرداخت / تمدید\n\n"
        f"🆔 درخواست: #{request_id}\n"
        f"📱 شماره تماس: {student['phone'] or 'ثبت نشده'}\n"
        f"🆔 Chat ID: {chat_id}\n"
        "⏳ وضعیت: در انتظار بررسی"
    )

    for admin_id in ADMIN_CHAT_IDS:
        send_message(admin_id, text)

    send_message(
        chat_id,
        "🔐 درخواستت ثبت شد.\n\n"
        "بعد از بررسی توسط ادمین، یک کد تأیید برات ارسال میشه.",
        main_keyboard()
    )


# =========================================================
# ADMIN - PAYMENT REQUESTS
# =========================================================

def admin_payment_requests(chat_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM mira_payment_requests
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:
        send_message(
            chat_id,
            "💳 هنوز درخواست پرداختی ثبت نشده.",
            admin_keyboard()
        )
        return

    buttons = []

    for row in rows:
        buttons.append([{
            "text": f"#{row['id']} — {row['status']}",
            "callback_data": f"payment_request:{row['id']}"
        }])

    send_message(
        chat_id,
        "💳 درخواست‌های پرداخت:",
        {
            "inline_keyboard": buttons
        }
    )


def show_payment_request(chat_id, request_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    conn = db()

    row = conn.execute("""
        SELECT *
        FROM mira_payment_requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    conn.close()

    if not row:
        send_message(chat_id, "درخواست پیدا نشد.")
        return

    text = (
        "💳 جزئیات درخواست پرداخت\n\n"
        f"🆔 درخواست: #{row['id']}\n"
        f"👤 Chat ID: {row['chat_id']}\n"
        f"📱 شماره: {row['phone'] or 'ثبت نشده'}\n"
        f"📌 وضعیت: {row['status']}\n"
        f"🕐 زمان: {row['created_at']}"
    )

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": [
                [{
                    "text": "🔐 صدور کد تأیید",
                    "callback_data": f"issue_code:{row['id']}:{row['chat_id']}"
                }]
            ]
        }
    )


# =========================================================
# ADMIN - ISSUE CODE
# =========================================================

def start_issue_code(admin_chat_id, request_id, user_chat_id):
    states[admin_chat_id] = {
        "flow": "admin_issue_code",
        "request_id": request_id,
        "user_chat_id": user_chat_id
    }

    send_message(
        admin_chat_id,
        f"🔐 صدور کد برای درخواست #{request_id}\n\n"
        "کد موردنظر رو بفرست.\n\n"
        "یا بنویس «خودکار» تا کد تصادفی ساخته بشه.",
        cancel_keyboard()
    )


def process_issue_code(admin_chat_id, message):
    state = states.get(admin_chat_id)

    if not state or state.get("flow") != "admin_issue_code":
        return False

    if message == "❌ لغو":
        states.pop(admin_chat_id, None)
        send_message(
            admin_chat_id,
            "عملیات لغو شد.",
            admin_keyboard()
        )
        return True

    request_id = state["request_id"]
    user_chat_id = state["user_chat_id"]

    if message == "خودکار":
        code = str(secrets.randbelow(900000) + 100000)
    else:
        code = message.strip()

    if not code:
        send_message(
            admin_chat_id,
            "کد معتبر نیست. دوباره وارد کن.",
            cancel_keyboard()
        )
        return True

    conn = db()

    conn.execute("""
        INSERT INTO mira_payment_codes
        (chat_id, request_id, code, status)
        VALUES (?, ?, ?, 'ACTIVE')
    """, (
        user_chat_id,
        request_id,
        code
    ))

    conn.execute("""
        UPDATE mira_payment_requests
        SET status = 'CODE_SENT'
        WHERE id = ?
    """, (request_id,))

    conn.commit()
    conn.close()

    send_message(
        user_chat_id,
        "🔐 کد تأیید MIRA\n\n"
        f"کد شما: {code}\n\n"
        "این کد برای ادامه فرآیند پرداخت / تمدید استفاده میشه."
    )

    states.pop(admin_chat_id, None)

    send_message(
        admin_chat_id,
        f"✅ کد {code} برای درخواست #{request_id} ارسال شد.",
        admin_keyboard()
    )

    return True


# =========================================================
# CODE LIST
# =========================================================

def admin_codes(chat_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM mira_payment_codes
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:
        send_message(
            chat_id,
            "🔐 هنوز کدی صادر نشده.",
            admin_keyboard()
        )
        return

    text = "🔐 آخرین کدهای تأیید:\n\n"

    for row in rows:
        text += (
            f"#{row['id']} | "
            f"درخواست #{row['request_id']} | "
            f"Chat ID: {row['chat_id']} | "
            f"کد: {row['code']} | "
            f"{row['status']}\n"
        )

    send_message(
        chat_id,
        text,
        admin_keyboard()
    )


# =========================================================
# ADMIN - LEADS / USERS
# =========================================================

def admin_leads(chat_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM mira_students
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:
        send_message(
            chat_id,
            "📥 هنوز لیدی ثبت نشده.",
            admin_keyboard()
        )
        return

    text = "📥 آخرین لیدها:\n\n"

    for row in rows:
        text += (
            f"#{row['id']}\n"
            f"👤 {row['full_name']}\n"
            f"🎓 {row['grade']} | {row['field']}\n"
            f"📱 {row['phone'] or '-'}\n"
            f"🆔 {row['chat_id']}\n\n"
        )

    send_message(
        chat_id,
        text,
        admin_keyboard()
    )


def admin_users(chat_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    conn = db()

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM mira_students"
    ).fetchone()["count"]

    conn.close()

    send_message(
        chat_id,
        f"👥 کاربران MIRA\n\n"
        f"تعداد کاربران ثبت‌شده: {count}",
        admin_keyboard()
    )


# =========================================================
# STUDENT PANEL
# =========================================================

def student_panel(chat_id):
    student = get_student(chat_id)

    if not student:
        send_message(
            chat_id,
            "هنوز اطلاعاتی از شما ثبت نشده.\n\n"
            "از گزینه «📝 ثبت‌نام در MIRA» شروع کن.",
            main_keyboard()
        )
        return

    conn = db()

    payment = conn.execute("""
        SELECT *
        FROM mira_payment_requests
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (chat_id,)).fetchone()

    conn.close()

    text = (
        "👤 پنل من\n\n"
        f"👤 نام: {student['full_name'] or '-'}\n"
        f"🎓 پایه: {student['grade'] or '-'}\n"
        f"📚 رشته: {student['field'] or '-'}\n"
        f"📱 شماره: {student['phone'] or '-'}\n\n"
        "📌 وضعیت پرداخت: "
    )

    if payment:
        text += payment["status"]
    else:
        text += "درخواستی ثبت نشده"

    send_message(
        chat_id,
        text,
        main_keyboard()
    )


# =========================================================
# SUPPORT
# =========================================================

def support(chat_id):
    send_message(
        chat_id,
        "🆘 پشتیبانی MIRA\n\n"
        "اگر سوال یا مشکلی داری، پیام خودت رو همینجا بفرست.\n"
        "تیم MIRA در اولین فرصت پیگیری می‌کنه.",
        main_keyboard()
    )


# =========================================================
# ADMIN MENU
# =========================================================

def show_admin_menu(chat_id):
    if chat_id not in ADMIN_CHAT_IDS:
        return

    states.pop(chat_id, None)

    send_message(
        chat_id,
        "🛠 پنل مدیریت MIRA\n\n"
        "یکی از بخش‌های زیر رو انتخاب کن:",
        admin_keyboard()
    )


# =========================================================
# CALLBACK ROUTER
# =========================================================

def handle_callback(callback):
    callback_id = callback.get("id")
    data = callback.get("data", "")

    message = callback.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    answer_callback(callback_id)

    # بررسی عضویت
    if data == "check_membership":
        if is_member(chat_id):
            edit_message(
                chat_id,
                message_id,
                "✅ عضویتت تأیید شد.\n\n"
                "حالا می‌تونی از امکانات MIRA استفاده کنی."
            )
            show_main_menu(chat_id)
        else:
            edit_message(
                chat_id,
                message_id,
                "❌ هنوز عضویتت در کانال MIRA تأیید نشده.\n\n"
                "ابتدا عضو کانال شو و دوباره بررسی عضویت رو بزن.",
                membership_keyboard()
            )

        return

    # درخواست پرداخت
    if data.startswith("payment_request:"):
        if chat_id not in ADMIN_CHAT_IDS:
            return

        request_id = int(data.split(":")[1])
        show_payment_request(chat_id, request_id)
        return

    # صدور کد
    if data.startswith("issue_code:"):
        if chat_id not in ADMIN_CHAT_IDS:
            return

        parts = data.split(":")

        request_id = int(parts[1])
        user_chat_id = int(parts[2])

        start_issue_code(
            chat_id,
            request_id,
            user_chat_id
        )

        return


# =========================================================
# MESSAGE ROUTER
# =========================================================

def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id:
        return

    text = message.get("text", "")
    contact = message.get("contact")

    # =====================================================
    # ADMIN SPECIAL STATES
    # =====================================================

    if chat_id in ADMIN_CHAT_IDS:

        if states.get(chat_id, {}).get("flow") == "admin_issue_code":
            process_issue_code(chat_id, text)
            return

    # =====================================================
    # START
    # =====================================================

    if text == "/start":
        states.pop(chat_id, None)

        if not is_member(chat_id):
            show_membership_gate(chat_id)
            return

        if chat_id in ADMIN_CHAT_IDS:
            show_admin_menu(chat_id)
        else:
            show_main_menu(chat_id)

        return

    # =====================================================
    # MEMBERSHIP GATE
    # =====================================================

    if not is_member(chat_id):
        show_membership_gate(chat_id)
        return

    # =====================================================
    # REGISTRATION FLOW
    # =====================================================

    if states.get(chat_id, {}).get("flow") == "registration":

        if contact:
            phone = contact.get("phone_number", "")
            states[chat_id]["data"]["phone"] = phone
            finish_registration(chat_id)
            return

        registration_step(chat_id, text)
        return

    # =====================================================
    # ADMIN MENU
    # =====================================================

    if chat_id in ADMIN_CHAT_IDS:

        if text == "👥 کاربران":
            admin_users(chat_id)
            return

        if text == "📥 لیدها":
            admin_leads(chat_id)
            return

        if text == "💳 درخواست‌های پرداخت":
            admin_payment_requests(chat_id)
            return

        if text == "🔐 کدهای تأیید":
            admin_codes(chat_id)
            return

        if text == "👨‍🎓 پنل دانش‌آموز":
            show_main_menu(chat_id)
            return

    # =====================================================
    # MAIN MENU
    # =====================================================

    if text == "📝 ثبت‌نام در MIRA":
        start_registration(chat_id)
        return

    if text == "🎓 دوره‌های MIRA":
        show_courses(chat_id)
        return

    if text == "💳 تمدید / پرداخت":
        start_payment(chat_id)
        return

    if text == "👤 پنل من":
        student_panel(chat_id)
        return

    if text == "🆘 پشتیبانی":
        support(chat_id)
        return

    # =====================================================
    # ADMIN COMMAND
    # =====================================================

    if text == "/admin" and chat_id in ADMIN_CHAT_IDS:
        show_admin_menu(chat_id)
        return

    # =====================================================
    # DEFAULT
    # =====================================================

    send_message(
        chat_id,
        "از منوی پایین یکی از گزینه‌ها رو انتخاب کن 👇",
        admin_keyboard() if chat_id in ADMIN_CHAT_IDS else main_keyboard()
    )


# =========================================================
# WEBHOOK SERVER
# =========================================================

class WebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            update = json.loads(body.decode("utf-8"))

            if "callback_query" in update:
                handle_callback(update["callback_query"])

            elif "message" in update:
                handle_message(update["message"])

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            print("Webhook error:", e)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MIRA BOT IS RUNNING")


# =========================================================
# MAIN
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    init_db()

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)

    print(f"MIRA Bot running on port {PORT}")

    server.serve_forever()


if __name__ == "__main__":
    main()
