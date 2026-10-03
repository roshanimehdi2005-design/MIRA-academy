import os
import json
import sqlite3
import secrets
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests


# =========================================================
# CONFIG
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
# RUNTIME STATE
# =========================================================

# Structure:
#
# users[chat_id] = {
#     "mode": "...",
#     "step": "...",
#     "data": {...}
# }
#
users = {}


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
            chat_id INTEGER PRIMARY KEY,
            data_json TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mira_payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            phone TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT
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

    conn.commit()
    conn.close()


# =========================================================
# TELEGRAM API
# =========================================================

def tg(method, data=None):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data or {},
            timeout=20
        )

        result = response.json()

        if not result.get("ok"):
            print(
                "Telegram API returned error:",
                method,
                result
            )

        return result

    except Exception as e:
        print(
            "Telegram API exception:",
            method,
            e
        )
        return {}


def send_message(
    chat_id,
    text,
    reply_markup=None
):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )

    return tg(
        "sendMessage",
        payload
    )


def edit_message(
    chat_id,
    message_id,
    text,
    reply_markup=None
):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }

    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False
        )

    return tg(
        "editMessageText",
        payload
    )


def answer_callback(callback_id):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )


def delete_message(
    chat_id,
    message_id
):
    return tg(
        "deleteMessage",
        {
            "chat_id": chat_id,
            "message_id": message_id
        }
    )


def get_chat_member(chat_id):
    return tg(
        "getChatMember",
        {
            "chat_id": CHANNEL_USERNAME,
            "user_id": chat_id
        }
    )


# =========================================================
# MEMBERSHIP
# =========================================================

def is_channel_member(chat_id):

    result = get_chat_member(chat_id)

    if not result.get("ok"):
        return False

    status = result.get(
        "result",
        {}
    ).get(
        "status"
    )

    return status in (
        "member",
        "administrator",
        "creator"
    )


# =========================================================
# STATE MANAGEMENT
# =========================================================

def clear_state(chat_id):
    users.pop(chat_id, None)


def set_state(
    chat_id,
    mode,
    step=None,
    data=None
):
    users[chat_id] = {
        "mode": mode,
        "step": step,
        "data": data or {}
    }


def get_state(chat_id):
    return users.get(chat_id)


# =========================================================
# COMMON KEYBOARDS
# =========================================================

def back_main_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🏠 منوی اصلی",
                    "callback_data": "main"
                }
            ]
        ]
    }


def cancel_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "❌ لغو",
                    "callback_data": "cancel"
                }
            ]
        ]
    }


# =========================================================
# MEMBERSHIP KEYBOARD
# =========================================================

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
                    "callback_data": "membership_check"
                }
            ]
        ]
    }


# =========================================================
# MAIN MENU
# =========================================================

def main_keyboard():

    buttons = [
        [
            {
                "text": "📝 ثبت‌نام و درخواست مشاوره",
                "callback_data": "registration"
            }
        ],
        [
            {
                "text": "🎓 معرفی دوره‌ها",
                "callback_data": "courses"
            }
        ],
        [
            {
                "text": "💳 پرداخت و تمدید اشتراک",
                "callback_data": "payment"
            }
        ],
        [
            {
                "text": "👤 پنل من",
                "callback_data": "profile"
            }
        ],
        [
            {
                "text": "🆘 پشتیبانی",
                "callback_data": "support"
            }
        ]
    ]

    if ADMIN_CHAT_IDS:
        # Admin gets a separate admin button.
        # It is only visible to admins.
        return {
            "inline_keyboard": buttons
        }

    return {
        "inline_keyboard": buttons
    }


def send_main_menu(chat_id):

    clear_state(chat_id)

    keyboard = main_keyboard()

    if is_admin(chat_id):

        keyboard["inline_keyboard"].append([
            {
                "text": "🛠 پنل مدیریت MIRA",
                "callback_data": "admin_main"
            }
        ])

    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "به MIRA خوش اومدی.\n\n"
        "چطور می‌تونم کمکت کنم؟",
        keyboard
    )


# =========================================================
# COURSES
# =========================================================

def courses_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": COURSES["classes"]["name"],
                    "url": COURSES["classes"]["url"]
                }
            ],
            [
                {
                    "text": COURSES["counseling"]["name"],
                    "url": COURSES["counseling"]["url"]
                }
            ],
            [
                {
                    "text": "🏠 منوی اصلی",
                    "callback_data": "main"
                }
            ]
        ]
    }


def send_courses(chat_id):

    clear_state(chat_id)

    send_message(
        chat_id,
        "🎓 دوره‌های MIRA\n\n"
        "برای مشاهده توضیحات کامل هر دوره، "
        "روی دوره موردنظرت بزن:",
        courses_keyboard()
    )


# =========================================================
# REGISTRATION
# =========================================================

def registration_cancel_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "registration_cancel"
                }
            ]
        ]
    }


def grade_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "دهم",
                    "callback_data": "reg_grade_10"
                },
                {
                    "text": "یازدهم",
                    "callback_data": "reg_grade_11"
                }
            ],
            [
                {
                    "text": "دوازدهم",
                    "callback_data": "reg_grade_12"
                }
            ],
            [
                {
                    "text": "فارغ‌التحصیل",
                    "callback_data": "reg_grade_grad"
                }
            ],
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "registration_cancel"
                }
            ]
        ]
    }


def field_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🧪 تجربی",
                    "callback_data": "reg_field_exp"
                },
                {
                    "text": "📐 ریاضی",
                    "callback_data": "reg_field_math"
                }
            ],
            [
                {
                    "text": "📚 انسانی",
                    "callback_data": "reg_field_human"
                },
                {
                    "text": "🎨 هنر",
                    "callback_data": "reg_field_art"
                }
            ],
            [
                {
                    "text": "💻 فنی‌وحرفه‌ای",
                    "callback_data": "reg_field_technical"
                }
            ],
            [
                {
                    "text": "📝 سایر",
                    "callback_data": "reg_field_other"
                }
            ],
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "registration_cancel"
                }
            ]
        ]
    }


GRADE_MAP = {
    "10": "دهم",
    "11": "یازدهم",
    "12": "دوازدهم",
    "grad": "فارغ‌التحصیل"
}


FIELD_MAP = {
    "exp": "تجربی",
    "math": "ریاضی",
    "human": "انسانی",
    "art": "هنر",
    "technical": "فنی‌وحرفه‌ای",
    "other": "سایر"
}


def start_registration(chat_id):

    set_state(
        chat_id,
        mode="registration",
        step="full_name",
        data={}
    )

    send_message(
        chat_id,
        "📝 ثبت‌نام و درخواست مشاوره\n\n"
        "برای اینکه تیم MIRA بتونه بهتر راهنماییت کنه، "
        "چند سؤال کوتاه ازت می‌پرسم.\n\n"
        "👤 **مرحله ۱ از ۷**\n\n"
        "نام و نام خانوادگی‌ت رو بفرست:",
        registration_cancel_keyboard()
    )


def registration_question(
    chat_id,
    text
):
    send_message(
        chat_id,
        text,
        registration_cancel_keyboard()
    )


def process_registration_text(
    chat_id,
    text
):

    state = get_state(chat_id)

    if not state:
        return False

    if state.get("mode") != "registration":
        return False

    step = state.get("step")
    data = state.setdefault(
        "data",
        {}
    )

    # -----------------------------------------------------
    # FULL NAME
    # -----------------------------------------------------

    if step == "full_name":

        if len(text) < 3:

            registration_question(
                chat_id,
                "❌ نام واردشده خیلی کوتاهه.\n\n"
                "لطفاً نام و نام خانوادگی کاملت رو بفرست:"
            )

            return True

        data["full_name"] = text

        state["step"] = "grade"

        send_message(
            chat_id,
            "👤 نام ثبت شد.\n\n"
            "🎓 **مرحله ۲ از ۷**\n\n"
            "پایه تحصیلی‌ت رو انتخاب کن:",
            grade_keyboard()
        )

        return True

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    if step == "grade":

        send_message(
            chat_id,
            "لطفاً پایه تحصیلی‌ت رو از دکمه‌های بالا انتخاب کن.",
            grade_keyboard()
        )

        return True

    # -----------------------------------------------------
    # FIELD
    # -----------------------------------------------------

    if step == "field":

        send_message(
            chat_id,
            "لطفاً رشته‌ت رو از دکمه‌های بالا انتخاب کن.",
            field_keyboard()
        )

        return True

    # -----------------------------------------------------
    # GOAL
    # -----------------------------------------------------

    if step == "goal":

        if len(text) < 2:

            registration_question(
                chat_id,
                "❌ لطفاً هدفت رو کمی واضح‌تر بنویس.\n\n"
                "مثلاً قبولی پزشکی، رتبه خوب، افزایش معدل و..."
            )

            return True

        data["goal"] = text

        state["step"] = "problem"

        registration_question(
            chat_id,
            "🎯 هدف ثبت شد.\n\n"
            "⚠️ **مرحله ۵ از ۷**\n\n"
            "بزرگ‌ترین مشکلت در مسیر درس خوندن چیه؟"
        )

        return True

    # -----------------------------------------------------
    # PROBLEM
    # -----------------------------------------------------

    if step == "problem":

        if len(text) < 2:

            registration_question(
                chat_id,
                "❌ لطفاً مشکلت رو کمی توضیح بده:"
            )

            return True

        data["problem"] = text

        state["step"] = "notes"

        registration_question(
            chat_id,
            "⚠️ مشکلت ثبت شد.\n\n"
            "📝 **مرحله ۶ از ۷**\n\n"
            "اگر نکته یا توضیح دیگه‌ای هست که "
            "دوست داری تیم MIRA بدونه، بنویس.\n\n"
            "اگر چیزی نداری بنویس: ندارد"
        )

        return True

    # -----------------------------------------------------
    # NOTES
    # -----------------------------------------------------

    if step == "notes":

        data["notes"] = text

        state["step"] = "phone"

        registration_question(
            chat_id,
            "📝 توضیحات ثبت شد.\n\n"
            "📱 **مرحله ۷ از ۷**\n\n"
            "در آخر شماره تماست رو بفرست:"
        )

        return True

    # -----------------------------------------------------
    # PHONE
    # -----------------------------------------------------

    if step == "phone":

        if len(text) < 8:

            registration_question(
                chat_id,
                "❌ شماره تماس معتبر به نظر نمی‌رسه.\n\n"
                "لطفاً شماره تماس رو دوباره وارد کن:"
            )

            return True

        data["phone"] = text

        save_student(
            chat_id,
            data
        )

        clear_state(chat_id)

        send_message(
            chat_id,
            "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
            "از اعتمادت ممنونیم رفیق ❤️\n\n"
            "ادمین MIRA باهات تماس خواهد گرفت."
        )

        notify_admins_new_lead(
            chat_id,
            data
        )

        send_main_menu(chat_id)

        return True

    return False


def save_student(
    chat_id,
    data
):

    conn = db()

    conn.execute(
        """
        INSERT OR REPLACE INTO mira_students
        (
            chat_id,
            data_json,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            chat_id,
            json.dumps(
                data,
                ensure_ascii=False
            ),
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def handle_registration_callback(
    chat_id,
    data
):

    state = get_state(chat_id)

    if not state:
        return False

    if state.get("mode") != "registration":
        return False

    step = state.get("step")

    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if data == "registration_cancel":

        clear_state(chat_id)

        send_message(
            chat_id,
            "❌ ثبت‌نام لغو شد."
        )

        send_main_menu(chat_id)

        return True

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    if data.startswith("reg_grade_"):

        if step != "grade":
            return True

        key = data.replace(
            "reg_grade_",
            "",
            1
        )

        grade = GRADE_MAP.get(key)

        if not grade:
            return True

        state["data"]["grade"] = grade
        state["step"] = "field"

        send_message(
            chat_id,
            f"🎓 پایه: {grade}\n\n"
            "📚 **مرحله ۳ از ۷**\n\n"
            "رشته‌ت رو انتخاب کن:",
            field_keyboard()
        )

        return True

    # -----------------------------------------------------
    # FIELD
    # -----------------------------------------------------

    if data.startswith("reg_field_"):

        if step != "field":
            return True

        key = data.replace(
            "reg_field_",
            "",
            1
        )

        field = FIELD_MAP.get(key)

        if not field:
            return True

        state["data"]["field"] = field
        state["step"] = "goal"

        registration_question(
            chat_id,
            f"📚 رشته: {field}\n\n"
            "🎯 **مرحله ۴ از ۷**\n\n"
            "هدف اصلیت از کنکور یا درس خوندن چیه؟"
        )

        return True

    return False


# =========================================================
# ADMIN LEAD NOTIFICATION
# =========================================================

def notify_admins_new_lead(
    chat_id,
    data
):

    text = (
        "📥 لید جدید MIRA\n\n"
        f"👤 نام: {data.get('full_name', '-')}\n"
        f"🎓 پایه: {data.get('grade', '-')}\n"
        f"📚 رشته: {data.get('field', '-')}\n"
        f"🎯 هدف: {data.get('goal', '-')}\n"
        f"⚠️ مشکل: {data.get('problem', '-')}\n"
        f"📝 توضیحات: {data.get('notes', '-')}\n"
        f"📱 شماره: {data.get('phone', '-')}\n"
        f"🆔 Chat ID: {chat_id}"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📥 مشاهده لیدها",
                    "callback_data": "admin_leads"
                }
            ]
        ]
    }

    for admin_id in ADMIN_CHAT_IDS:

        send_message(
            admin_id,
            text,
            keyboard
        )


# =========================================================
# PAYMENT MENU
# =========================================================

def payment_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📱 ثبت درخواست احراز هویت",
                    "callback_data": "payment_auth"
                }
            ],
            [
                {
                    "text": "🔐 ورود کد تأیید",
                    "callback_data": "payment_code"
                }
            ],
            [
                {
                    "text": "🏠 منوی اصلی",
                    "callback_data": "main"
                }
            ]
        ]
    }


def send_payment_menu(chat_id):

    clear_state(chat_id)

    send_message(
        chat_id,
        "💳 پرداخت و تمدید اشتراک\n\n"
        "برای شروع فرایند پرداخت ابتدا باید احراز هویت بشی.\n\n"
        "اگر قبلاً کد تأیید از تیم MIRA گرفتی، "
        "می‌تونی مستقیماً کدت رو وارد کنی.",
        payment_keyboard()
    )


# =========================================================
# PAYMENT AUTHENTICATION
# =========================================================

def start_payment_auth(chat_id):

    clear_state(chat_id)

    conn = db()

    cursor = conn.execute(
        """
        INSERT INTO mira_payment_requests
        (
            chat_id,
            phone,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            chat_id,
            "",
            "PENDING",
            datetime.now().isoformat()
        )
    )

    request_id = cursor.lastrowid

    conn.commit()
    conn.close()

    send_message(
        chat_id,
        "✅ درخواست احراز هویتت ثبت شد.\n\n"
        "تیم MIRA درخواستت رو بررسی می‌کنه و "
        "بعد از تأیید، کد مخصوص برات ارسال میشه.",
        back_main_keyboard()
    )

    notify_admins_payment_request(
        chat_id,
        request_id
    )


def notify_admins_payment_request(
    chat_id,
    request_id
):

    text = (
        "🔐 درخواست احراز هویت پرداخت / تمدید\n\n"
        f"🆔 درخواست: #{request_id}\n"
        f"🆔 Chat ID: {chat_id}\n"
        "⏳ وضعیت: در انتظار بررسی"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "👁 مشاهده درخواست",
                    "callback_data":
                        f"admin_payment_{request_id}"
                }
            ]
        ]
    }

    for admin_id in ADMIN_CHAT_IDS:

        send_message(
            admin_id,
            text,
            keyboard
        )


# =========================================================
# VERIFICATION CODE
# =========================================================

def normalize_code(code):
    return code.strip().upper()


def generate_code():

    return (
        "MIRA-"
        +
        "".join(
            secrets.choice(
                "0123456789"
            )
            for _ in range(6)
        )
    )


def save_verification_code(
    chat_id,
    request_id,
    code
):

    code = normalize_code(code)

    conn = db()

    conn.execute(
        """
        UPDATE mira_payment_codes
        SET status = 'REPLACED'
        WHERE request_id = ?
        AND status = 'ACTIVE'
        """,
        (
            request_id,
        )
    )

    conn.execute(
        """
        INSERT INTO mira_payment_codes
        (
            chat_id,
            request_id,
            code,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            request_id,
            code,
            "ACTIVE",
            datetime.now().isoformat()
        )
    )

    conn.execute(
        """
        UPDATE mira_payment_requests
        SET status = 'CODE_ISSUED'
        WHERE id = ?
        """,
        (
            request_id,
        )
    )

    conn.commit()
    conn.close()


def verify_code(
    chat_id,
    code
):

    code = normalize_code(code)

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM mira_payment_codes
        WHERE chat_id = ?
        AND code = ?
        AND status = 'ACTIVE'
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            chat_id,
            code
        )
    ).fetchone()

    if not row:

        conn.close()

        return False

    conn.execute(
        """
        UPDATE mira_payment_codes
        SET status = 'USED',
            used_at = ?
        WHERE id = ?
        """,
        (
            datetime.now().isoformat(),
            row["id"]
        )
    )

    if row["request_id"]:

        conn.execute(
            """
            UPDATE mira_payment_requests
            SET status = 'CODE_APPROVED'
            WHERE id = ?
            """,
            (
                row["request_id"],
            )
        )

    conn.commit()
    conn.close()

    return True


def start_code_input(chat_id):

    set_state(
        chat_id,
        mode="verification_code",
        step="code",
        data={}
    )

    send_message(
        chat_id,
        "🔐 ورود کد تأیید\n\n"
        "کدی که از تیم MIRA دریافت کردی رو "
        "همین‌جا وارد کن:",
        cancel_keyboard()
    )


def process_code_input(
    chat_id,
    text
):

    state = get_state(chat_id)

    if not state:
        return False

    if state.get("mode") != "verification_code":
        return False

    if state.get("step") != "code":
        return False

    if verify_code(
        chat_id,
        text
    ):

        clear_state(chat_id)

        send_message(
            chat_id,
            "✅ کد تأیید با موفقیت تأیید شد.\n\n"
            "احراز هویتت انجام شد."
        )

        send_payment_menu(chat_id)

    else:

        send_message(
            chat_id,
            "❌ این کد معتبر نیست یا قبلاً استفاده شده.\n\n"
            "کد رو دوباره بررسی کن.",
            cancel_keyboard()
        )

    return True


# =========================================================
# USER PROFILE
# =========================================================

def send_user_profile(chat_id):

    clear_state(chat_id)

    conn = db()

    student = conn.execute(
        """
        SELECT *
        FROM mira_students
        WHERE chat_id = ?
        """,
        (
            chat_id,
        )
    ).fetchone()

    payment = conn.execute(
        """
        SELECT *
        FROM mira_payment_requests
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            chat_id,
        )
    ).fetchone()

    conn.close()

    text = "👤 پنل من\n\n"

    if student:

        try:
            data = json.loads(
                student["data_json"]
            )
        except Exception:
            data = {}

        text += (
            f"👤 نام: {data.get('full_name', '-')}\n"
            f"🎓 پایه: {data.get('grade', '-')}\n"
            f"📚 رشته: {data.get('field', '-')}\n\n"
        )

    else:

        text += (
            "اطلاعات ثبت‌نامی هنوز ثبت نشده.\n\n"
        )

    if payment:

        status_map = {
            "PENDING": "⏳ در انتظار بررسی",
            "CODE_ISSUED": "🔐 کد صادر شده",
            "CODE_APPROVED": "🟢 احراز هویت شده",
            "PAYMENT_PENDING": "💳 در انتظار پرداخت",
            "RECEIPT_SENT": "📸 رسید ارسال شده",
            "ACTIVE": "✅ فعال",
            "REJECTED": "❌ رد شده"
        }

        status = status_map.get(
            payment["status"],
            payment["status"]
        )

        text += (
            f"💳 آخرین درخواست: #{payment['id']}\n"
            f"📌 وضعیت: {status}\n"
        )

    else:

        text += (
            "💳 هنوز درخواست پرداختی ثبت نکردی."
        )

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": [
                [
                    {
                        "text": "💳 پرداخت و تمدید",
                        "callback_data": "payment"
                    }
                ],
                [
                    {
                        "text": "🏠 منوی اصلی",
                        "callback_data": "main"
                    }
                ]
            ]
        }
    )


# =========================================================
# SUPPORT
# =========================================================

def send_support(chat_id):

    clear_state(chat_id)

    send_message(
        chat_id,
        "🆘 پشتیبانی MIRA\n\n"
        "برای ارتباط با تیم MIRA، "
        "پیامت رو همین‌جا ارسال کن.\n\n"
        "در مرحله بعد سیستم پشتیبانی رو کامل‌تر می‌کنیم.",
        back_main_keyboard()
    )


# =========================================================
# ADMIN
# =========================================================

def is_admin(chat_id):
    return chat_id in ADMIN_CHAT_IDS


def admin_main_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📥 لیدها",
                    "callback_data": "admin_leads"
                }
            ],
            [
                {
                    "text": "💳 درخواست‌های پرداخت",
                    "callback_data": "admin_payments"
                }
            ],
            [
                {
                    "text": "🔐 کدهای تأیید",
                    "callback_data": "admin_codes"
                }
            ],
            [
                {
                    "text": "👨‍🎓 پنل دانش‌آموز",
                    "callback_data": "admin_student"
                }
            ],
            [
                {
                    "text": "🏠 خروج از پنل مدیریت",
                    "callback_data": "main"
                }
            ]
        ]
    }


def send_admin_menu(chat_id):

    clear_state(chat_id)

    send_message(
        chat_id,
        "🛠 پنل مدیریت MIRA\n\n"
        "از این بخش می‌تونی لیدها، "
        "درخواست‌های پرداخت و کدهای تأیید رو مدیریت کنی.",
        admin_main_keyboard()
    )


# =========================================================
# ADMIN LEADS
# =========================================================

def send_admin_leads(chat_id):

    if not is_admin(chat_id):
        return

    clear_state(chat_id)

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM mira_students
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    if not rows:

        send_message(
            chat_id,
            "📥 هنوز هیچ لیدی ثبت نشده.",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 پنل مدیریت",
                            "callback_data": "admin_main"
                        }
                    ]
                ]
            }
        )

        return

    buttons = []

    for row in rows:

        try:
            data = json.loads(
                row["data_json"]
            )
        except Exception:
            data = {}

        name = data.get(
            "full_name",
            "بدون نام"
        )

        buttons.append([
            {
                "text": f"👤 {name}",
                "callback_data":
                    f"admin_lead_{row['chat_id']}"
            }
        ])

    buttons.append([
        {
            "text": "🔙 پنل مدیریت",
            "callback_data": "admin_main"
        }
    ])

    send_message(
        chat_id,
        "📥 لیدهای اخیر MIRA\n\n"
        "برای مشاهده جزئیات روی هر لید بزن:",
        {
            "inline_keyboard": buttons
        }
    )


def send_admin_lead_detail(
    chat_id,
    target_chat_id
):

    if not is_admin(chat_id):
        return

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM mira_students
        WHERE chat_id = ?
        """,
        (
            target_chat_id,
        )
    ).fetchone()

    conn.close()

    if not row:

        send_message(
            chat_id,
            "❌ این لید پیدا نشد.",
            back_main_keyboard()
        )

        return

    try:
        data = json.loads(
            row["data_json"]
        )
    except Exception:
        data = {}

    text = (
        "👤 جزئیات لید\n\n"
        f"🆔 Chat ID: {target_chat_id}\n"
        f"👤 نام: {data.get('full_name', '-')}\n"
        f"🎓 پایه: {data.get('grade', '-')}\n"
        f"📚 رشته: {data.get('field', '-')}\n"
        f"🎯 هدف: {data.get('goal', '-')}\n"
        f"⚠️ مشکل: {data.get('problem', '-')}\n"
        f"📝 توضیحات: {data.get('notes', '-')}\n"
        f"📱 شماره: {data.get('phone', '-')}\n"
        f"📅 ثبت: {row['created_at']}"
    )

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": [
                [
                    {
                        "text": "🔙 لیدها",
                        "callback_data": "admin_leads"
                    }
                ],
                [
                    {
                        "text": "🏠 پنل مدیریت",
                        "callback_data": "admin_main"
                    }
                ]
            ]
        }
    )


# =========================================================
# ADMIN PAYMENTS
# =========================================================

def send_admin_payments(chat_id):

    if not is_admin(chat_id):
        return

    clear_state(chat_id)

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM mira_payment_requests
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    if not rows:

        send_message(
            chat_id,
            "💳 هنوز هیچ درخواست پرداختی ثبت نشده.",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 پنل مدیریت",
                            "callback_data": "admin_main"
                        }
                    ]
                ]
            }
        )

        return

    status_map = {
        "PENDING": "⏳",
        "CODE_ISSUED": "🔐",
        "CODE_APPROVED": "🟢",
        "PAYMENT_PENDING": "💳",
        "RECEIPT_SENT": "📸",
        "ACTIVE": "✅",
        "REJECTED": "❌"
    }

    buttons = []

    for row in rows:

        icon = status_map.get(
            row["status"],
            "❔"
        )

        buttons.append([
            {
                "text":
                    f"{icon} درخواست #{row['id']}",
                "callback_data":
                    f"admin_payment_{row['id']}"
            }
        ])

    buttons.append([
        {
            "text": "🔙 پنل مدیریت",
            "callback_data": "admin_main"
        }
    ])

    send_message(
        chat_id,
        "💳 درخواست‌های پرداخت\n\n"
        "برای مشاهده جزئیات روی درخواست بزن:",
        {
            "inline_keyboard": buttons
        }
    )


def send_admin_payment_detail(
    chat_id,
    request_id
):

    if not is_admin(chat_id):
        return

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM mira_payment_requests
        WHERE id = ?
        """,
        (
            request_id,
        )
    ).fetchone()

    conn.close()

    if not row:

        send_message(
            chat_id,
            "❌ درخواست پیدا نشد.",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 درخواست‌ها",
                            "callback_data": "admin_payments"
                        }
                    ]
                ]
            }
        )

        return

    status_map = {
        "PENDING": "⏳ در انتظار بررسی",
        "CODE_ISSUED": "🔐 کد صادر شده",
        "CODE_APPROVED": "🟢 کد تأیید شده",
        "PAYMENT_PENDING": "💳 در انتظار پرداخت",
        "RECEIPT_SENT": "📸 رسید ارسال شده",
        "ACTIVE": "✅ فعال",
        "REJECTED": "❌ رد شده"
    }

    status_text = status_map.get(
        row["status"],
        row["status"]
    )

    text = (
        "💳 جزئیات درخواست پرداخت\n\n"
        f"🆔 درخواست: #{row['id']}\n"
        f"👤 Chat ID: {row['chat_id']}\n"
        f"📱 شماره: {row['phone'] or '-'}\n"
        f"📅 تاریخ: {row['created_at']}\n"
        f"📌 وضعیت: {status_text}"
    )

    buttons = []

    if row["status"] in (
        "PENDING",
        "REJECTED"
    ):

        buttons.append([
            {
                "text": "🔐 صدور کد تأیید",
                "callback_data":
                    f"admin_issue_{request_id}_{row['chat_id']}"
            }
        ])

    buttons.append([
        {
            "text": "🔙 درخواست‌ها",
            "callback_data": "admin_payments"
        }
    ])

    buttons.append([
        {
            "text": "🏠 پنل مدیریت",
            "callback_data": "admin_main"
        }
    ])

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": buttons
        }
    )


# =========================================================
# ADMIN ISSUE CODE
# =========================================================

def start_admin_issue_code(
    admin_chat_id,
    request_id,
    target_chat_id
):

    if not is_admin(admin_chat_id):
        return

    set_state(
        admin_chat_id,
        mode="admin_issue_code",
        step="code",
        data={
            "request_id": request_id,
            "target_chat_id": target_chat_id
        }
    )

    send_message(
        admin_chat_id,
        "🔐 صدور کد تأیید\n\n"
        "یک کد وارد کن یا بنویس «خودکار» "
        "تا سیستم خودش کد بسازه.",
        cancel_keyboard()
    )


def process_admin_issue_code(
    admin_chat_id,
    text
):

    if not is_admin(admin_chat_id):
        return False

    state = get_state(
        admin_chat_id
    )

    if not state:
        return False

    if state.get("mode") != "admin_issue_code":
        return False

    if state.get("step") != "code":
        return False

    if text == "لغو":

        clear_state(
            admin_chat_id
        )

        send_admin_menu(
            admin_chat_id
        )

        return True

    request_id = state["data"]["request_id"]
    target_chat_id = state["data"]["target_chat_id"]

    if text.strip() == "خودکار":

        code = generate_code()

    else:

        code = normalize_code(text)

        if len(code) < 4:

            send_message(
                admin_chat_id,
                "❌ کد خیلی کوتاهه.\n\n"
                "حداقل ۴ کاراکتر وارد کن.",
                cancel_keyboard()
            )

            return True

    save_verification_code(
        target_chat_id,
        request_id,
        code
    )

    clear_state(
        admin_chat_id
    )

    send_message(
        target_chat_id,
        "🔐 کد تأیید MIRA\n\n"
        f"کد تأیید شما:\n\n"
        f"👉 {code}\n\n"
        "این کد رو در بخش پرداخت و تمدید اشتراک وارد کن."
    )

    send_message(
        admin_chat_id,
        "✅ کد با موفقیت صادر شد.\n\n"
        f"🆔 درخواست: #{request_id}\n"
        f"🔐 کد: {code}\n\n"
        "📤 کد برای دانش‌آموز ارسال شد.",
        {
            "inline_keyboard": [
                [
                    {
                        "text": "💳 مشاهده درخواست",
                        "callback_data":
                            f"admin_payment_{request_id}"
                    }
                ],
                [
                    {
                        "text": "🛠 پنل مدیریت",
                        "callback_data": "admin_main"
                    }
                ]
            ]
        }
    )

    return True


# =========================================================
# ADMIN CODES
# =========================================================

def send_admin_codes(chat_id):

    if not is_admin(chat_id):
        return

    clear_state(chat_id)

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM mira_payment_codes
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    if not rows:

        send_message(
            chat_id,
            "🔐 هنوز هیچ کد تأییدی صادر نشده.",
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 پنل مدیریت",
                            "callback_data": "admin_main"
                        }
                    ]
                ]
            }
        )

        return

    lines = [
        "🔐 کدهای تأیید اخیر",
        ""
    ]

    for row in rows:

        lines.append(
            f"#{row['id']} | "
            f"درخواست #{row['request_id'] or '-'} | "
            f"{row['code']} | "
            f"{row['status']}"
        )

    send_message(
        chat_id,
        "\n".join(lines),
        {
            "inline_keyboard": [
                [
                    {
                        "text": "🏠 پنل مدیریت",
                        "callback_data": "admin_main"
                    }
                ]
            ]
        }
    )


# =========================================================
# ADMIN CALLBACK ROUTER
# =========================================================

def handle_admin_callback(
    chat_id,
    data
):

    if not is_admin(chat_id):
        return False

    if data == "admin_main":

        send_admin_menu(chat_id)

        return True

    if data == "admin_leads":

        send_admin_leads(chat_id)

        return True

    if data == "admin_payments":

        send_admin_payments(chat_id)

        return True

    if data == "admin_codes":

        send_admin_codes(chat_id)

        return True

    if data == "admin_student":

        send_main_menu(chat_id)

        return True

    if data.startswith("admin_lead_"):

        raw = data.replace(
            "admin_lead_",
            "",
            1
        )

        try:
            target_chat_id = int(raw)
        except ValueError:
            return True

        send_admin_lead_detail(
            chat_id,
            target_chat_id
        )

        return True

    if data.startswith("admin_payment_"):

        raw = data.replace(
            "admin_payment_",
            "",
            1
        )

        try:
            request_id = int(raw)
        except ValueError:
            return True

        send_admin_payment_detail(
            chat_id,
            request_id
        )

        return True

    if data.startswith("admin_issue_"):

        parts = data.split("_")

        if len(parts) != 4:
            return True

        try:
            request_id = int(parts[2])
            target_chat_id = int(parts[3])
        except ValueError:
            return True

        start_admin_issue_code(
            chat_id,
            request_id,
            target_chat_id
        )

        return True

    return False


# =========================================================
# GLOBAL CALLBACK ROUTER
# =========================================================

def handle_callback(callback_query):

    callback_id = callback_query.get("id")

    answer_callback(
        callback_id
    )

    message = callback_query.get(
        "message"
    )

    if not message:
        return

    chat_id = message["chat"]["id"]

    data = callback_query.get(
        "data",
        ""
    )

    # =====================================================
    # ADMIN
    # =====================================================

    if is_admin(chat_id):

        if handle_admin_callback(
            chat_id,
            data
        ):
            return

    # =====================================================
    # REGISTRATION
    # =====================================================

    if data == "registration_cancel":

        handle_registration_callback(
            chat_id,
            data
        )

        return

    if data.startswith("reg_grade_"):

        handle_registration_callback(
            chat_id,
            data
        )

        return

    if data.startswith("reg_field_"):

        handle_registration_callback(
            chat_id,
            data
        )

        return

    # =====================================================
    # GLOBAL CANCEL
    # =====================================================

    if data == "cancel":

        clear_state(chat_id)

        send_message(
            chat_id,
            "❌ عملیات لغو شد."
        )

        send_main_menu(chat_id)

        return

    # =====================================================
    # MEMBERSHIP
    # =====================================================

    if data == "membership_check":

        if is_channel_member(chat_id):

            clear_state(chat_id)

            send_message(
                chat_id,
                "✅ عضویتت تأیید شد.\n\n"
                "خوش اومدی رفیق 👋"
            )

            send_main_menu(chat_id)

        else:

            send_message(
                chat_id,
                "❌ هنوز عضویتت در کانال MIRA تأیید نشده.\n\n"
                "اول عضو کانال شو و بعد دوباره بررسی عضویت رو بزن.",
                membership_keyboard()
            )

        return

    # =====================================================
    # MAIN
    # =====================================================

    if data == "main":

        send_main_menu(chat_id)

        return

    # =====================================================
    # REGISTRATION
    # =====================================================

    if data == "registration":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        start_registration(chat_id)

        return

    # =====================================================
    # COURSES
    # =====================================================

    if data == "courses":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        send_courses(chat_id)

        return

    # =====================================================
    # PAYMENT
    # =====================================================

    if data == "payment":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        send_payment_menu(chat_id)

        return

    if data == "payment_auth":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        start_payment_auth(chat_id)

        return

    if data == "payment_code":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        start_code_input(chat_id)

        return

    # =====================================================
    # PROFILE
    # =====================================================

    if data == "profile":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        send_user_profile(chat_id)

        return

    # =====================================================
    # SUPPORT
    # =====================================================

    if data == "support":

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        send_support(chat_id)

        return


# =========================================================
# MEMBERSHIP GATE
# =========================================================

def send_membership_gate(chat_id):

    clear_state(chat_id)

    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "برای استفاده از بات MIRA ابتدا باید "
        "عضو کانال اصلی MIRA بشی.\n\n"
        "بعد از عضویت روی «بررسی عضویت» بزن.",
        membership_keyboard()
    )


# =========================================================
# MESSAGE ROUTER
# =========================================================

def handle_message(message):

    chat_id = message["chat"]["id"]

    text = message.get(
        "text",
        ""
    ).strip()

    if not text:
        return

    # =====================================================
    # START
    # =====================================================

    if text == "/start":

        clear_state(chat_id)

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

        else:

            send_main_menu(chat_id)

        return

    # =====================================================
    # ADMIN TEXT STATE
    # =====================================================

    if is_admin(chat_id):

        if process_admin_issue_code(
            chat_id,
            text
        ):
            return

    # =====================================================
    # VERIFICATION CODE STATE
    # =====================================================

    state = get_state(chat_id)

    if state:

        mode = state.get(
            "mode"
        )

        if mode == "verification_code":

            process_code_input(
                chat_id,
                text
            )

            return

        if mode == "registration":

            process_registration_text(
                chat_id,
                text
            )

            return

    # =====================================================
    # MEMBERSHIP
    # =====================================================

    if not is_channel_member(chat_id):

        send_membership_gate(chat_id)

        return

    # =====================================================
    # NO TEXT COMMANDS
    #
    # All actual menus are now inline.
    # =====================================================

    send_message(
        chat_id,
        "برای استفاده از MIRA از دکمه‌های منو استفاده کن 👇",
        main_keyboard()
    )


# =========================================================
# WEBHOOK
# =========================================================

class TelegramWebhookHandler(
    BaseHTTPRequestHandler
):

    def do_POST(self):

        parsed = urlparse(
            self.path
        )

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

            if "callback_query" in update:

                handle_callback(
                    update["callback_query"]
                )

            elif "message" in update:

                handle_message(
                    update["message"]
                )

        except Exception as e:

            print(
                "Webhook processing error:",
                e
            )

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"OK"
        )

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"MIRA BOT is running."
        )

    def log_message(
        self,
        format,
        *args
    ):
        return


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:

        print(
            "ERROR: BOT_TOKEN is not configured."
        )

    init_db()

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        TelegramWebhookHandler
    )

    print(
        "MIRA BOT running on port",
        port
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
