import os
import json
import sqlite3
import secrets
from datetime import datetime
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
# IN-MEMORY STATES
# =========================================================

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
        return response.json()
    except Exception as e:
        print("Telegram API error:", e)
        return {}


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    return tg("sendMessage", payload)


def remove_keyboard():
    return {
        "remove_keyboard": True
    }


def answer_callback(callback_query_id):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_query_id
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

    status = result.get("result", {}).get("status")

    return status in [
        "member",
        "administrator",
        "creator"
    ]


# =========================================================
# KEYBOARDS
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
                    "callback_data": "check_membership"
                }
            ]
        ]
    }


def main_menu_keyboard():
    return {
        "keyboard": [
            [
                {"text": "📝 ثبت‌نام و درخواست مشاوره"}
            ],
            [
                {"text": "🎓 معرفی دوره‌ها"}
            ],
            [
                {"text": "💳 پرداخت و تمدید اشتراک"}
            ],
            [
                {"text": "👤 پنل من"}
            ],
            [
                {"text": "🆘 پشتیبانی"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def payment_menu_keyboard():
    return {
        "keyboard": [
            [
                {"text": "🔐 ورود کد تأیید"}
            ],
            [
                {"text": "📱 ثبت درخواست احراز هویت"}
            ],
            [
                {"text": "🔙 بازگشت به منوی اصلی"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def admin_menu_keyboard():
    return {
        "keyboard": [
            [
                {"text": "📥 لیدها"}
            ],
            [
                {"text": "💳 درخواست‌های پرداخت"}
            ],
            [
                {"text": "🔐 کدهای تأیید"}
            ],
            [
                {"text": "👨‍🎓 پنل دانش‌آموز"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def cancel_inline_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "cancel_registration"
                }
            ]
        ]
    }


def grade_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "دهم", "callback_data": "reg_grade_دهم"},
                {"text": "یازدهم", "callback_data": "reg_grade_یازدهم"},
                {"text": "دوازدهم", "callback_data": "reg_grade_دوازدهم"}
            ],
            [
                {"text": "فارغ‌التحصیل", "callback_data": "reg_grade_فارغ‌التحصیل"}
            ],
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "cancel_registration"
                }
            ]
        ]
    }


def field_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "🧪 تجربی", "callback_data": "reg_field_تجربی"},
                {"text": "📐 ریاضی", "callback_data": "reg_field_ریاضی"}
            ],
            [
                {"text": "📚 انسانی", "callback_data": "reg_field_انسانی"},
                {"text": "🎨 هنر", "callback_data": "reg_field_هنر"}
            ],
            [
                {"text": "💻 فنی‌وحرفه‌ای", "callback_data": "reg_field_فنی‌وحرفه‌ای"}
            ],
            [
                {"text": "📝 سایر", "callback_data": "reg_field_سایر"}
            ],
            [
                {
                    "text": "❌ لغو ثبت‌نام",
                    "callback_data": "cancel_registration"
                }
            ]
        ]
    }


def code_input_keyboard():
    return {
        "keyboard": [
            [
                {"text": "❌ لغو"}
            ]
        ],
        "resize_keyboard": True
    }


def admin_code_keyboard():
    return {
        "keyboard": [
            [
                {"text": "❌ لغو"}
            ]
        ],
        "resize_keyboard": True
    }


# =========================================================
# MENUS
# =========================================================

def send_membership_gate(chat_id):
    send_message(
        chat_id,
        "سلام رفیق 👋\n\n"
        "برای استفاده از بات MIRA ابتدا باید عضو کانال اصلی MIRA بشی.\n\n"
        "بعد از عضویت روی «بررسی عضویت» بزن.",
        membership_keyboard()
    )


def send_main_menu(chat_id):
    send_message(
        chat_id,
        "سلام رفیق 👋\n"
        "به MIRA خوش اومدی.\n\n"
        "چطور می‌تونم کمکت کنم؟",
        main_menu_keyboard()
    )


def send_admin_menu(chat_id):
    send_message(
        chat_id,
        "🛠 پنل مدیریت MIRA\n\n"
        "سلام ادمین 👋\n"
        "از این بخش می‌تونی لیدها و درخواست‌های پرداخت رو مدیریت کنی.",
        admin_menu_keyboard()
    )


def send_payment_menu(chat_id):
    send_message(
        chat_id,
        "💳 پرداخت و تمدید اشتراک\n\n"
        "برای شروع فرایند پرداخت ابتدا باید احراز هویت بشی.\n\n"
        "اگر کد تأیید از طرف تیم MIRA داری، می‌تونی همین‌جا واردش کنی.",
        payment_menu_keyboard()
    )


# =========================================================
# COURSES
# =========================================================

def send_courses(chat_id):
    keyboard = {
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
                    "text": "🔙 بازگشت",
                    "callback_data": "back_to_main"
                }
            ]
        ]
    }

    send_message(
        chat_id,
        "🎓 دوره‌های MIRA\n\n"
        "برای مشاهده توضیحات کامل هر دوره، روی دوره موردنظرت بزن:",
        keyboard
    )


# =========================================================
# REGISTRATION
# =========================================================

def start_registration(chat_id):

    users[chat_id] = {
        "mode": "registration",
        "step": "full_name",
        "data": {}
    }

    # حذف کامل منوی اصلی
    send_message(
        chat_id,
        "📝 ثبت‌نام و درخواست مشاوره\n\n"
        "مرحله ۱ از ۷\n\n"
        "👤 نام و نام خانوادگی‌ت رو برام بفرست:",
        remove_keyboard()
    )

    send_message(
        chat_id,
        "برای لغو ثبت‌نام می‌تونی از دکمه زیر استفاده کنی.",
        cancel_inline_keyboard()
    )


def send_registration_step(chat_id, text):
    """
    نمایش سؤال مربوط به state فعلی.
    """

    send_message(
        chat_id,
        text,
        cancel_inline_keyboard()
    )


def process_registration(chat_id, text):

    state = users.get(chat_id)

    if not state:
        return False

    if state.get("mode") != "registration":
        return False

    step = state.get("step")
    data = state.setdefault("data", {})

    # -----------------------------------------------------
    # FULL NAME
    # -----------------------------------------------------

    if step == "full_name":

        # جلوگیری از ثبت شدن گزینه‌های منو به عنوان نام
        forbidden = [
            "📝 ثبت‌نام و درخواست مشاوره",
            "🎓 معرفی دوره‌ها",
            "💳 پرداخت و تمدید اشتراک",
            "👤 پنل من",
            "🆘 پشتیبانی"
        ]

        if text in forbidden:
            send_registration_step(
                chat_id,
                "👤 هنوز نام و نام خانوادگی‌ت رو دریافت نکردم.\n\n"
                "لطفاً نام و نام خانوادگی رو به صورت متنی برام بفرست:"
            )
            return True

        if len(text) < 3:
            send_registration_step(
                chat_id,
                "❌ نام واردشده خیلی کوتاهه.\n\n"
                "لطفاً نام و نام خانوادگی کاملت رو بفرست:"
            )
            return True

        data["full_name"] = text
        state["step"] = "grade"

        send_message(
            chat_id,
            "مرحله ۲ از ۷\n\n"
            "🎓 پایه تحصیلی‌ت رو انتخاب کن:",
            grade_keyboard()
        )

        return True

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    if step == "grade":

        send_message(
            chat_id,
            "🎓 لطفاً پایه تحصیلی‌ت رو از بین گزینه‌های بالا انتخاب کن.",
            grade_keyboard()
        )

        return True

    # -----------------------------------------------------
    # FIELD
    # -----------------------------------------------------

    if step == "field":

        send_message(
            chat_id,
            "📚 لطفاً رشته‌ت رو از بین گزینه‌های بالا انتخاب کن.",
            field_keyboard()
        )

        return True

    # -----------------------------------------------------
    # GOAL
    # -----------------------------------------------------

    if step == "goal":

        if len(text) < 2:
            send_registration_step(
                chat_id,
                "❌ لطفاً هدفت رو کمی واضح‌تر بنویس.\n\n"
                "مثلاً: قبولی پزشکی، افزایش معدل، رتبه خوب کنکور و..."
            )
            return True

        data["goal"] = text
        state["step"] = "problem"

        send_registration_step(
            chat_id,
            "مرحله ۵ از ۷\n\n"
            "⚠️ بزرگ‌ترین مشکلت در مسیر درس خوندن چیه؟"
        )

        return True

    # -----------------------------------------------------
    # PROBLEM
    # -----------------------------------------------------

    if step == "problem":

        if len(text) < 2:
            send_registration_step(
                chat_id,
                "❌ لطفاً مشکلت رو کمی توضیح بده."
            )
            return True

        data["problem"] = text
        state["step"] = "notes"

        send_registration_step(
            chat_id,
            "مرحله ۶ از ۷\n\n"
            "📝 اگر نکته یا توضیح دیگه‌ای هست که دوست داری تیم MIRA بدونه، برام بنویس.\n\n"
            "اگر چیزی نداری بنویس: ندارد"
        )

        return True

    # -----------------------------------------------------
    # NOTES
    # -----------------------------------------------------

    if step == "notes":

        data["notes"] = text
        state["step"] = "phone"

        send_registration_step(
            chat_id,
            "مرحله ۷ از ۷\n\n"
            "📱 در آخر شماره تماست رو بفرست:"
        )

        return True

    # -----------------------------------------------------
    # PHONE
    # -----------------------------------------------------

    if step == "phone":

        if len(text) < 8:
            send_registration_step(
                chat_id,
                "❌ شماره تماس معتبر به نظر نمی‌رسه.\n\n"
                "لطفاً شماره تماس رو دوباره وارد کن:"
            )
            return True

        data["phone"] = text

        conn = db()

        conn.execute(
            """
            INSERT OR REPLACE INTO mira_students
            (chat_id, data_json, created_at)
            VALUES (?, ?, ?)
            """,
            (
                chat_id,
                json.dumps(data, ensure_ascii=False),
                datetime.now().isoformat()
            )
        )

        conn.commit()
        conn.close()

        users.pop(chat_id, None)

        send_message(
            chat_id,
            "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
            "از اعتمادت ممنونیم رفیق ❤️\n\n"
            "ادمین MIRA باهات تماس خواهد گرفت.",
            remove_keyboard()
        )

        notify_admins_new_lead(chat_id, data)

        send_main_menu(chat_id)

        return True

    return False


def handle_registration_callback(chat_id, data):

    state = users.get(chat_id)

    if not state:
        return False

    if state.get("mode") != "registration":
        return False

    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if data == "cancel_registration":

        users.pop(chat_id, None)

        send_message(
            chat_id,
            "❌ ثبت‌نام لغو شد.",
            remove_keyboard()
        )

        send_main_menu(chat_id)

        return True

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    if data.startswith("reg_grade_"):

        if state.get("step") != "grade":
            return True

        grade = data.replace(
            "reg_grade_",
            "",
            1
        )

        state["data"]["grade"] = grade
        state["step"] = "field"

        send_message(
            chat_id,
            f"🎓 پایه انتخاب‌شده: {grade}\n\n"
            "مرحله ۳ از ۷\n\n"
            "📚 رشته‌ت رو انتخاب کن:",
            field_keyboard()
        )

        return True

    # -----------------------------------------------------
    # FIELD
    # -----------------------------------------------------

    if data.startswith("reg_field_"):

        if state.get("step") != "field":
            return True

        field = data.replace(
            "reg_field_",
            "",
            1
        )

        state["data"]["field"] = field
        state["step"] = "goal"

        send_registration_step(
            chat_id,
            f"📚 رشته انتخاب‌شده: {field}\n\n"
            "مرحله ۴ از ۷\n\n"
            "🎯 هدف اصلیت از کنکور یا درس خوندن چیه؟"
        )

        return True

    return False


def notify_admins_new_lead(chat_id, data):

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

    for admin_id in ADMIN_CHAT_IDS:
        send_message(admin_id, text)


# =========================================================
# PAYMENT AUTHENTICATION
# =========================================================

def start_payment_auth(chat_id):

    conn = db()

    cursor = conn.execute(
        """
        INSERT INTO mira_payment_requests
        (chat_id, phone, status, created_at)
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
        "تیم MIRA درخواستت رو بررسی می‌کنه و بعد از تأیید، "
        "کد مخصوص برات ارسال میشه."
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
# VERIFICATION CODES
# =========================================================

def normalize_code(code):
    return code.strip().upper()


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
        (request_id,)
    )

    conn.execute(
        """
        INSERT INTO mira_payment_codes
        (chat_id, request_id, code, status, created_at)
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
        (request_id,)
    )

    conn.commit()
    conn.close()


def generate_code():

    return "MIRA-" + "".join(
        secrets.choice("0123456789")
        for _ in range(6)
    )


def verify_code(chat_id, code):

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
            (row["request_id"],)
        )

    conn.commit()
    conn.close()

    return True


def start_code_input(chat_id):

    users[chat_id] = {
        "mode": "enter_verification_code"
    }

    send_message(
        chat_id,
        "🔐 کد تأییدت رو وارد کن:",
        code_input_keyboard()
    )


# =========================================================
# ADMIN PANEL
# =========================================================

def is_admin(chat_id):
    return chat_id in ADMIN_CHAT_IDS


def send_admin_leads(chat_id):

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
            "📥 هنوز هیچ لیدی ثبت نشده."
        )

        return

    buttons = []

    for row in rows:

        try:
            data = json.loads(row["data_json"])
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
            "text": "🔙 بازگشت به پنل مدیریت",
            "callback_data": "admin_menu"
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

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM mira_students
        WHERE chat_id = ?
        """,
        (target_chat_id,)
    ).fetchone()

    conn.close()

    if not row:

        send_message(
            chat_id,
            "❌ این لید پیدا نشد."
        )

        return

    try:
        data = json.loads(row["data_json"])
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
                        "text": "🔙 بازگشت به لیدها",
                        "callback_data": "admin_leads"
                    }
                ],
                [
                    {
                        "text": "🏠 پنل مدیریت",
                        "callback_data": "admin_menu"
                    }
                ]
            ]
        }
    )


def send_admin_payment_requests(chat_id):

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
            "💳 هنوز هیچ درخواست پرداختی ثبت نشده."
        )

        return

    buttons = []

    status_map = {
        "PENDING": "⏳",
        "CODE_ISSUED": "🔐",
        "CODE_APPROVED": "🟢",
        "PAYMENT_PENDING": "💳",
        "RECEIPT_SENT": "📸",
        "ACTIVE": "✅",
        "REJECTED": "❌"
    }

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
            "text": "🔙 بازگشت به پنل مدیریت",
            "callback_data": "admin_menu"
        }
    ])

    send_message(
        chat_id,
        "💳 درخواست‌های پرداخت\n\n"
        "برای مشاهده جزئیات هر درخواست روی آن بزن:",
        {
            "inline_keyboard": buttons
        }
    )


def send_admin_payment_detail(
    chat_id,
    request_id
):

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM mira_payment_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    conn.close()

    if not row:

        send_message(
            chat_id,
            "❌ درخواست پیدا نشد."
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

    if row["status"] in [
        "PENDING",
        "REJECTED"
    ]:

        buttons.append([
            {
                "text": "🔐 صدور کد تأیید",
                "callback_data":
                    f"admin_issue_code_{request_id}_{row['chat_id']}"
            }
        ])

    buttons.append([
        {
            "text": "🔙 بازگشت به درخواست‌ها",
            "callback_data": "admin_payments"
        }
    ])

    buttons.append([
        {
            "text": "🏠 پنل مدیریت",
            "callback_data": "admin_menu"
        }
    ])

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": buttons
        }
    )


def start_admin_issue_code(
    admin_chat_id,
    request_id,
    target_chat_id
):

    users[admin_chat_id] = {
        "mode": "admin_issue_code",
        "request_id": request_id,
        "target_chat_id": target_chat_id
    }

    send_message(
        admin_chat_id,
        "🔐 صدور کد تأیید\n\n"
        "کدی که می‌خواهی برای این دانش‌آموز صادر بشه رو وارد کن.\n\n"
        "یا برای تولید خودکار یک کد امن، بنویس:\n"
        "«خودکار»",
        admin_code_keyboard()
    )


def process_admin_issue_code(
    admin_chat_id,
    text
):

    state = users.get(admin_chat_id)

    if not state:
        return False

    if state.get("mode") != "admin_issue_code":
        return False

    if text == "❌ لغو":

        users.pop(admin_chat_id, None)

        send_message(
            admin_chat_id,
            "❌ عملیات لغو شد.",
            remove_keyboard()
        )

        send_admin_menu(admin_chat_id)

        return True

    request_id = state["request_id"]
    target_chat_id = state["target_chat_id"]

    if text.strip() == "خودکار":

        code = generate_code()

    else:

        code = normalize_code(text)

        if len(code) < 4:

            send_message(
                admin_chat_id,
                "❌ کد خیلی کوتاهه.\n\n"
                "حداقل ۴ کاراکتر وارد کن.",
                admin_code_keyboard()
            )

            return True

    save_verification_code(
        target_chat_id,
        request_id,
        code
    )

    users.pop(admin_chat_id, None)

    send_message(
        target_chat_id,
        "🔐 کد تأیید MIRA\n\n"
        f"کد تأیید شما:\n\n"
        f"👉 {code}\n\n"
        "این کد رو در بخش «پرداخت و تمدید اشتراک» وارد کن."
    )

    send_message(
        admin_chat_id,
        "✅ کد با موفقیت صادر شد.\n\n"
        f"🆔 درخواست: #{request_id}\n"
        f"🔐 کد: {code}\n"
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
                        "text": "🏠 پنل مدیریت",
                        "callback_data": "admin_menu"
                    }
                ]
            ]
        }
    )

    return True


def send_admin_codes(chat_id):

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
            "🔐 هنوز هیچ کد تأییدی صادر نشده."
        )

        return

    lines = [
        "🔐 کدهای تأیید اخیر\n"
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
                        "callback_data": "admin_menu"
                    }
                ]
            ]
        }
    )


# =========================================================
# USER PANEL
# =========================================================

def send_user_panel(chat_id):

    conn = db()

    student = conn.execute(
        """
        SELECT *
        FROM mira_students
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    payment = conn.execute(
        """
        SELECT *
        FROM mira_payment_requests
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (chat_id,)
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

        text += (
            f"💳 آخرین درخواست پرداخت: #{payment['id']}\n"
            f"📌 وضعیت: {payment['status']}\n"
        )

    else:

        text += (
            "💳 هنوز درخواست پرداختی ثبت نکردی.\n"
        )

    send_message(
        chat_id,
        text,
        {
            "inline_keyboard": [
                [
                    {
                        "text": "💳 پرداخت و تمدید",
                        "callback_data": "payment_menu"
                    }
                ],
                [
                    {
                        "text": "🔙 منوی اصلی",
                        "callback_data": "back_to_main"
                    }
                ]
            ]
        }
    )


# =========================================================
# SUPPORT
# =========================================================

def send_support(chat_id):

    send_message(
        chat_id,
        "🆘 پشتیبانی MIRA\n\n"
        "برای ارتباط با تیم MIRA پیام خودت رو همین‌جا ارسال کن.\n\n"
        "پیامت برای تیم پشتیبانی ارسال خواهد شد.",
        {
            "keyboard": [
                [
                    {"text": "🔙 بازگشت به منوی اصلی"}
                ]
            ],
            "resize_keyboard": True
        }
    )


# =========================================================
# ADMIN CALLBACK HANDLER
# =========================================================

def handle_admin_callback(
    chat_id,
    data
):

    if not is_admin(chat_id):
        return False

    if data == "admin_menu":

        users.pop(chat_id, None)

        send_admin_menu(chat_id)

        return True

    if data == "admin_leads":

        send_admin_leads(chat_id)

        return True

    if data == "admin_payments":

        send_admin_payment_requests(chat_id)

        return True

    if data == "admin_codes":

        send_admin_codes(chat_id)

        return True

    if data.startswith("admin_lead_"):

        target_chat_id = int(
            data.replace(
                "admin_lead_",
                ""
            )
        )

        send_admin_lead_detail(
            chat_id,
            target_chat_id
        )

        return True

    if data.startswith("admin_payment_"):

        request_id = int(
            data.replace(
                "admin_payment_",
                ""
            )
        )

        send_admin_payment_detail(
            chat_id,
            request_id
        )

        return True

    if data.startswith("admin_issue_code_"):

        parts = data.split("_")

        request_id = int(parts[3])
        target_chat_id = int(parts[4])

        start_admin_issue_code(
            chat_id,
            request_id,
            target_chat_id
        )

        return True

    return False


# =========================================================
# CALLBACK HANDLER
# =========================================================

def handle_callback(callback_query):

    callback_id = callback_query.get("id")

    message = callback_query.get("message")

    if not message:
        return

    chat_id = message["chat"]["id"]

    data = callback_query.get(
        "data",
        ""
    )

    answer_callback(callback_id)

    # =====================================================
    # REGISTRATION CALLBACKS
    # =====================================================

    if data == "cancel_registration":

        if handle_registration_callback(
            chat_id,
            data
        ):
            return

    if data.startswith("reg_grade_"):

        if handle_registration_callback(
            chat_id,
            data
        ):
            return

    if data.startswith("reg_field_"):

        if handle_registration_callback(
            chat_id,
            data
        ):
            return

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
    # MEMBERSHIP
    # =====================================================

    if data == "check_membership":

        if is_channel_member(chat_id):

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

    if data == "back_to_main":

        users.pop(chat_id, None)

        send_main_menu(chat_id)

        return

    # =====================================================
    # PAYMENT
    # =====================================================

    if data == "payment_menu":

        users.pop(chat_id, None)

        send_payment_menu(chat_id)

        return


# =========================================================
# MESSAGE HANDLER
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
    # ADMIN STATE
    # =====================================================

    if is_admin(chat_id):

        if process_admin_issue_code(
            chat_id,
            text
        ):
            return

        if text == "/start":

            users.pop(chat_id, None)

            send_admin_menu(chat_id)

            return

        if text == "📥 لیدها":

            users.pop(chat_id, None)

            send_admin_leads(chat_id)

            return

        if text == "💳 درخواست‌های پرداخت":

            users.pop(chat_id, None)

            send_admin_payment_requests(chat_id)

            return

        if text == "🔐 کدهای تأیید":

            users.pop(chat_id, None)

            send_admin_codes(chat_id)

            return

        if text == "👨‍🎓 پنل دانش‌آموز":

            users.pop(chat_id, None)

            send_message(
                chat_id,
                "👨‍🎓 پنل دانش‌آموز فعال شد.",
                remove_keyboard()
            )

            send_main_menu(chat_id)

            return

        if text == "🛠 پنل مدیریت":

            users.pop(chat_id, None)

            send_admin_menu(chat_id)

            return

    # =====================================================
    # GLOBAL CANCEL
    # =====================================================

    if text == "❌ لغو ثبت‌نام":

        users.pop(chat_id, None)

        send_message(
            chat_id,
            "❌ ثبت‌نام لغو شد.",
            remove_keyboard()
        )

        send_main_menu(chat_id)

        return

    if text == "❌ لغو":

        users.pop(chat_id, None)

        send_message(
            chat_id,
            "❌ عملیات لغو شد.",
            remove_keyboard()
        )

        send_main_menu(chat_id)

        return

    # =====================================================
    # START
    # =====================================================

    if text == "/start":

        users.pop(chat_id, None)

        if not is_channel_member(chat_id):

            send_membership_gate(chat_id)

            return

        send_main_menu(chat_id)

        return

    # =====================================================
    # IMPORTANT:
    # MAIN MENU COMMANDS ARE CHECKED BEFORE STATES.
    # This prevents stale keyboards from becoming answers.
    # =====================================================

    if text == "📝 ثبت‌نام و درخواست مشاوره":

        start_registration(chat_id)

        return

    if text == "🎓 معرفی دوره‌ها":

        users.pop(chat_id, None)

        send_courses(chat_id)

        return

    if text == "💳 پرداخت و تمدید اشتراک":

        users.pop(chat_id, None)

        send_payment_menu(chat_id)

        return

    if text == "👤 پنل من":

        users.pop(chat_id, None)

        send_user_panel(chat_id)

        return

    if text == "🆘 پشتیبانی":

        users.pop(chat_id, None)

        send_support(chat_id)

        return

    if text == "🔙 بازگشت به منوی اصلی":

        users.pop(chat_id, None)

        send_message(
            chat_id,
            "🏠 برگشتیم به منوی اصلی.",
            remove_keyboard()
        )

        send_main_menu(chat_id)

        return

    # =====================================================
    # USER VERIFICATION CODE STATE
    # =====================================================

    state = users.get(chat_id)

    if (
        state
        and state.get("mode")
        == "enter_verification_code"
    ):

        if verify_code(
            chat_id,
            text
        ):

            users.pop(chat_id, None)

            send_message(
                chat_id,
                "✅ کد تأیید با موفقیت تأیید شد.\n\n"
                "حالا می‌تونی فرایند پرداخت رو ادامه بدی.",
                remove_keyboard()
            )

            send_payment_menu(chat_id)

        else:

            send_message(
                chat_id,
                "❌ این کد معتبر نیست یا قبلاً استفاده شده.\n\n"
                "کد رو دوباره بررسی کن.",
                code_input_keyboard()
            )

        return

    # =====================================================
    # REGISTRATION STATE
    # =====================================================

    state = users.get(chat_id)

    if (
        state
        and state.get("mode")
        == "registration"
    ):

        process_registration(
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
    # PAYMENT
    # =====================================================

    if text == "📱 ثبت درخواست احراز هویت":

        users.pop(chat_id, None)

        start_payment_auth(chat_id)

        return

    if text == "🔐 ورود کد تأیید":

        users.pop(chat_id, None)

        start_code_input(chat_id)

        return

    # =====================================================
    # FALLBACK
    # =====================================================

    send_message(
        chat_id,
        "متوجه نشدم رفیق 😅\n\n"
        "یکی از گزینه‌های منو رو انتخاب کن."
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

        content_length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        body = self.rfile.read(
            content_length
        )

        try:

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

        except Exception as e:

            print(
                "Webhook error:",
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
        "MIRA bot running on port",
        port
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
