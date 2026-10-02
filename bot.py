import os
import json
import sqlite3
import logging
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_CHAT_IDS = [
    x.strip()
    for x in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if x.strip()
]

DB_PATH = os.getenv("DB_PATH", "mira.db")

if not TOKEN:
    raise SystemExit("BOT_TOKEN is missing.")

API = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(level=logging.INFO)


# =========================
# QUESTIONS
# =========================

QUESTIONS = [
    (
        "full_name",
        "👤 نام و نام خانوادگی‌ات رو وارد کن:",
        None
    ),
    (
        "phone",
        "📞 شماره تماست رو ارسال کن:",
        "contact"
    ),
    (
        "age",
        "🎂 چند سالته؟",
        None
    ),
    (
        "grade",
        "📚 پایه تحصیلی‌ات کدومه؟",
        [
            "دهم",
            "یازدهم",
            "دوازدهم",
            "فارغ‌التحصیل / پشت‌کنکوری",
            "دانشجو"
        ]
    ),
    (
        "field",
        "🧪 رشته تحصیلی‌ات چیه؟",
        None
    ),
    (
        "school",
        "🏫 اسم مدرسه‌ات چیه؟",
        None
    ),
    (
        "city",
        "📍 در چه شهری زندگی می‌کنی؟",
        None
    ),
    (
        "gpa",
        "📊 معدل آخرین مقطع تحصیلی‌ات چند بوده؟",
        None
    ),
    (
        "goal",
        "🎯 هدف اصلیت از دریافت مشاوره یا آموزش چیه؟",
        [
            "موفقیت در مدرسه و امتحانات",
            "آمادگی برای کنکور",
            "رسیدن به رتبه و دانشگاه خوب",
            "تقویت دروس و رفع ضعف‌ها",
            "هنوز دقیق نمی‌دونم"
        ]
    ),
    (
        "study_hours",
        "⏱️ میانگین ساعت مطالعه مفید روزانه‌ات چقدره؟",
        [
            "کمتر از ۲ ساعت",
            "۲ تا ۴ ساعت",
            "۴ تا ۶ ساعت",
            "۶ تا ۸ ساعت",
            "بیشتر از ۸ ساعت",
            "دقیق نمی‌دونم"
        ]
    ),
    (
        "experience",
        "📚 تا حالا سابقه کلاس یا مشاوره داشتی؟",
        [
            "خیر، نداشتم",
            "کلاس آموزشی داشتم",
            "مشاوره داشتم",
            "هم کلاس داشتم هم مشاوره",
            "قبلاً داشتم ولی الان ندارم"
        ]
    ),
    (
        "problem",
        "🧩 مهم‌ترین مشکل درسی‌ات در حال حاضر چیه؟",
        [
            "یادگیری و فهم مطالب",
            "برنامه‌ریزی",
            "نظم و استمرار",
            "تست زدن",
            "تمرکز",
            "آزمون و تحلیل",
            "رفع اشکال",
            "نمی‌دونم"
        ]
    ),
    (
        "extra",
        "📝 اگر توضیح یا نکته‌ای هست که فکر می‌کنی باید درباره شرایطت بدونیم، اینجا بنویس.\n\nاگر موردی نداری، بنویس «ندارم».",
        None
    )
]


# =========================
# IN-MEMORY USER STATE
# =========================

state = {}


# =========================
# DATABASE
# =========================

def db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            data_json TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    return conn


def save_student(chat_id, msg, data):
    conn = db()

    username = msg.get("from", {}).get("username", "")

    conn.execute("""
        INSERT INTO students
        (chat_id, username, full_name, phone, data_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            phone = excluded.phone,
            data_json = excluded.data_json,
            created_at = excluded.created_at
    """, (
        chat_id,
        username,
        data.get("full_name", ""),
        data.get("phone", ""),
        json.dumps(data, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat()
    ))

    conn.commit()
    conn.close()


# =========================
# TELEGRAM API
# =========================

def tg(method, payload):
    response = requests.post(
        f"{API}/{method}",
        json=payload,
        timeout=35
    )

    response.raise_for_status()
    return response.json()


def send(chat_id, text, markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if markup:
        payload["reply_markup"] = markup

    return tg("sendMessage", payload)


# =========================
# KEYBOARDS
# =========================

def keyboard(options):
    rows = []

    for i in range(0, len(options), 2):
        rows.append([
            {"text": option}
            for option in options[i:i + 2]
        ])

    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def remove_keyboard():
    return {
        "remove_keyboard": True
    }


def contact_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📞 ارسال شماره تماس",
                    "request_contact": True
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def confirmation_keyboard():
    return {
        "keyboard": [
            [
                {"text": "✅ تأیید و ارسال"},
                {"text": "✏️ اصلاح اطلاعات"}
            ],
            [
                {"text": "🔄 شروع دوباره"}
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


# =========================
# REPORT
# =========================

LABELS = {
    "full_name": "نام و نام خانوادگی",
    "phone": "شماره تماس",
    "age": "سن",
    "grade": "پایه تحصیلی",
    "field": "رشته",
    "school": "نام مدرسه",
    "city": "شهر",
    "gpa": "معدل آخرین مقطع",
    "goal": "هدف اصلی",
    "study_hours": "میانگین ساعت مطالعه روزانه",
    "experience": "سابقه کلاس یا مشاوره",
    "problem": "مهم‌ترین مشکل درسی",
    "extra": "توضیحات تکمیلی"
}


def summary(data):
    lines = [
        "📋 اطلاعات ثبت‌شده در MIRA",
        ""
    ]

    for key, _question, _options in QUESTIONS:
        value = data.get(key, "ثبت نشده")

        lines.append(
            f"• {LABELS[key]}: {value}"
        )

    return "\n".join(lines)


def admin_report(chat_id, msg, data):
    username = msg.get("from", {}).get("username", "")

    lines = [
        "🔔 لید جدید MIRA",
        "",
        summary(data),
        "",
        "━━━━━━━━━━━━━━",
        f"🆔 Telegram ID: {chat_id}",
        f"🔗 Username: @{username}" if username else "🔗 Username: ندارد",
        "━━━━━━━━━━━━━━"
    ]

    return "\n".join(lines)


# =========================
# HANDLE MESSAGE
# =========================

def handle(msg):

    chat_id = msg["chat"]["id"]

    text = msg.get("text", "").strip()

    # -------------------------
    # START
    # -------------------------

    if text == "/start":

        state[chat_id] = {
            "index": 0,
            "data": {},
            "editing": False
        }

        send(
            chat_id,
            "درود 👋\n\n"
            "به MIRA خوش اومدی. ✨\n\n"
            "برای اینکه بتونیم شرایط، هدف و نیازهای تحصیلی‌ات رو بهتر بشناسیم، "
            "چند سؤال کوتاه ازت می‌پرسیم.\n\n"
            "در پایان، اطلاعاتت رو یک‌بار می‌بینی و بعد از تأیید، "
            "برای تیم MIRA ارسال می‌شه.\n\n"
            "بزن بریم 🚀",
            keyboard(["بزن بریم 🚀"])
        )

        return


    # -------------------------
    # USER DOESN'T HAVE STATE
    # -------------------------

    if chat_id not in state:

        send(
            chat_id,
            "برای شروع، /start رو بزن. 👋",
            remove_keyboard()
        )

        return


    user = state[chat_id]


    # -------------------------
    # RESTART
    # -------------------------

    if text == "🔄 شروع دوباره":

        state[chat_id] = {
            "index": 0,
            "data": {},
            "editing": False
        }

        send(
            chat_id,
            "از اول شروع می‌کنیم. 🔄",
            remove_keyboard()
        )

        send(
            chat_id,
            QUESTIONS[0][1]
        )

        return


    # -------------------------
    # START QUESTIONNAIRE
    # -------------------------

    if user["index"] == 0 and not user["data"]:

        if text != "بزن بریم 🚀":
            return

        send(
            chat_id,
            QUESTIONS[0][1],
            remove_keyboard()
        )

        return


    # -------------------------
    # CONTACT
    # -------------------------

    current_index = user["index"]

    if current_index < len(QUESTIONS):

        key, question, options = QUESTIONS[current_index]

        if options == "contact":

            contact = msg.get("contact")

            if not contact:

                send(
                    chat_id,
                    "لطفاً شماره خودت رو با دکمه زیر ارسال کن. 📞",
                    contact_keyboard()
                )

                return

            telegram_user_id = msg.get("from", {}).get("id")

            if (
                contact.get("user_id")
                and contact.get("user_id") != telegram_user_id
            ):

                send(
                    chat_id,
                    "لطفاً شماره تماس خودت رو ارسال کن. 📞",
                    contact_keyboard()
                )

                return

            user["data"]["phone"] = contact.get(
                "phone_number",
                ""
            )

            user["index"] += 1

            send_next_question(chat_id)

            return


    # -------------------------
    # NORMAL QUESTION
    # -------------------------

    if current_index < len(QUESTIONS):

        key, question, options = QUESTIONS[current_index]

        if options and options != "contact":

            if text not in options:

                send(
                    chat_id,
                    "لطفاً یکی از گزینه‌های نمایش‌داده‌شده رو انتخاب کن. 👇",
                    keyboard(options)
                )

                return

        user["data"][key] = text

        user["index"] += 1

        send_next_question(chat_id)

        return


    # -------------------------
    # CONFIRMATION
    # -------------------------

    if text == "✏️ اصلاح اطلاعات":

        user["index"] = 0
        user["data"] = {}

        send(
            chat_id,
            "حتماً. اطلاعات رو از اول وارد می‌کنیم. ✏️",
            remove_keyboard()
        )

        send(
            chat_id,
            QUESTIONS[0][1]
        )

        return


    if text == "✅ تأیید و ارسال":

        data = user["data"]

        save_student(chat_id, msg, data)

        report = admin_report(
            chat_id,
            msg,
            data
        )

        send(
            chat_id,
            "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
            "اطلاعات کامل برای تیم MIRA ارسال شد. 📩\n\n"
            "ممنون که وقت گذاشتی. 🌟",
            remove_keyboard()
        )

        for admin_id in ADMIN_CHAT_IDS:

            try:

                send(
                    admin_id,
                    report
                )

            except Exception:

                logging.exception(
                    "Failed to send report to admin %s",
                    admin_id
                )

        return


# =========================
# SEND NEXT QUESTION
# =========================

def send_next_question(chat_id):

    user = state[chat_id]

    index = user["index"]

    if index >= len(QUESTIONS):

        send(
            chat_id,
            "تقریباً تموم شد. 🔥\n\n"
            "اطلاعاتی که وارد کردی رو بررسی کن:\n\n"
            + summary(user["data"])
            + "\n\n"
            "اگر همه‌چیز درسته، «تأیید و ارسال» رو بزن. ✅",
            confirmation_keyboard()
        )

        return


    key, question, options = QUESTIONS[index]

    if options == "contact":

        send(
            chat_id,
            question,
            contact_keyboard()
        )

    elif options:

        send(
            chat_id,
            question,
            keyboard(options)
        )

    else:

        send(
            chat_id,
            question,
            remove_keyboard()
        )


# =========================
# WEBHOOK
# =========================

WEBHOOK_PATH = "/telegram-webhook"


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path in ("/", "/health"):

            body = b"MIRA Bot is running"

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

        else:

            self.send_response(404)
            self.end_headers()


    def do_POST(self):

        if self.path != WEBHOOK_PATH:

            self.send_response(404)
            self.end_headers()

            return

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            raw = self.rfile.read(length)

            update = json.loads(
                raw.decode("utf-8")
            )

            msg = update.get("message")

            if msg:

                handle(msg)

            self.send_response(200)
            self.end_headers()

            self.wfile.write(b"ok")

        except Exception:

            logging.exception(
                "Webhook error"
            )

            self.send_response(500)
            self.end_headers()


    def log_message(self, format, *args):
        return


# =========================
# MAIN
# =========================

def main():

    db()

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    public_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        ""
    ).strip().rstrip("/")


    if public_url:

        webhook_url = (
            public_url
            + WEBHOOK_PATH
        )

        try:

            result = tg(
                "setWebhook",
                {
                    "url": webhook_url,
                    "allowed_updates": [
                        "message"
                    ]
                }
            )

            logging.info(
                "Telegram webhook configured: %s",
                result
            )

        except Exception:

            logging.exception(
                "Failed to configure Telegram webhook"
            )


    logging.info(
        "MIRA Bot running on port %s",
        port
    )


    try:

        server.serve_forever()

    except KeyboardInterrupt:

        pass

    finally:

        server.server_close()


if __name__ == "__main__":

    main()
