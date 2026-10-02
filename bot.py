import os
import json
import sqlite3
import logging
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_CHAT_IDS = [
    x.strip()
    for x in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if x.strip()
]

DB_PATH = os.getenv("DB_PATH", "mira.db")

API = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

if not TOKEN:
    raise SystemExit("BOT_TOKEN is missing.")


# =========================================================
# QUESTIONS
# =========================================================

QUESTIONS = [
    {
        "key": "full_name",
        "question": "👤 نام و نام خانوادگی‌ات رو وارد کن:",
        "type": "text"
    },
    {
        "key": "phone",
        "question": "📞 شماره تماست رو ارسال کن:",
        "type": "contact"
    },
    {
        "key": "age",
        "question": "🎂 چند سالته؟",
        "type": "text"
    },
    {
        "key": "grade",
        "question": "📚 پایه تحصیلی‌ات کدومه؟",
        "type": "options",
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
        "question": "🧪 رشته تحصیلی‌ات چیه؟",
        "type": "text"
    },
    {
        "key": "school",
        "question": "🏫 اسم مدرسه‌ات چیه؟",
        "type": "text"
    },
    {
        "key": "city",
        "question": "📍 در چه شهری زندگی می‌کنی؟",
        "type": "text"
    },
    {
        "key": "gpa",
        "question": "📊 معدل آخرین مقطع تحصیلی‌ات چند بوده؟",
        "type": "text"
    },
    {
        "key": "goal",
        "question": "🎯 هدف اصلیت از مشاوره یا آموزش چیه؟",
        "type": "options",
        "options": [
            "موفقیت در مدرسه و امتحانات",
            "آمادگی برای کنکور",
            "رسیدن به رتبه و دانشگاه خوب",
            "تقویت دروس و رفع ضعف‌ها",
            "هنوز دقیق نمی‌دونم"
        ]
    },
    {
        "key": "study_hours",
        "question": "⏱️ میانگین ساعت مطالعه مفید روزانه‌ات چقدره؟",
        "type": "options",
        "options": [
            "کمتر از ۲ ساعت",
            "۲ تا ۴ ساعت",
            "۴ تا ۶ ساعت",
            "۶ تا ۸ ساعت",
            "بیشتر از ۸ ساعت",
            "دقیق نمی‌دونم"
        ]
    },
    {
        "key": "experience",
        "question": "📚 تا حالا سابقه کلاس یا مشاوره داشتی؟",
        "type": "options",
        "options": [
            "خیر، نداشتم",
            "کلاس آموزشی داشتم",
            "مشاوره داشتم",
            "هم کلاس داشتم هم مشاوره",
            "قبلاً داشتم ولی الان ندارم"
        ]
    },
    {
        "key": "problem",
        "question": "🧩 مهم‌ترین مشکل درسی‌ات در حال حاضر چیه؟",
        "type": "options",
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
        "question": "📝 اگر توضیح یا نکته‌ای هست که فکر می‌کنی باید درباره شرایطت بدونیم، اینجا بنویس.\n\nاگر موردی نداری، بنویس «ندارم».",
        "type": "text"
    }
]


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


# =========================================================
# USER STATES
# =========================================================

users = {}


def new_user():
    return {
        "step": 0,
        "data": {},
        "completed": False
    }


# =========================================================
# DATABASE
# =========================================================

def init_db():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mira_students (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            data_json TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_student(chat_id, username, data):

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        INSERT INTO mira_students
        (chat_id, username, data_json, created_at)
        VALUES (?, ?, ?, ?)

        ON CONFLICT(chat_id) DO UPDATE SET
            username = excluded.username,
            data_json = excluded.data_json,
            created_at = excluded.created_at
    """, (
        chat_id,
        username,
        json.dumps(data, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# TELEGRAM
# =========================================================

def telegram(method, data):

    response = requests.post(
        f"{API}/{method}",
        json=data,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    return result


def send(chat_id, text, markup=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if markup is not None:
        data["reply_markup"] = markup

    return telegram("sendMessage", data)


# =========================================================
# KEYBOARDS
# =========================================================

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


def option_keyboard(options):

    rows = []

    for i in range(0, len(options), 2):

        row = []

        for option in options[i:i + 2]:
            row.append({
                "text": option
            })

        rows.append(row)

    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def confirmation_keyboard():

    return {
        "keyboard": [
            [
                {"text": "✅ تأیید و ارسال"}
            ],
            [
                {"text": "✏️ اصلاح اطلاعات"},
                {"text": "🔄 شروع دوباره"}
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


# =========================================================
# QUESTIONS FLOW
# =========================================================

def ask_question(chat_id):

    user = users.get(chat_id)

    if not user:
        return

    step = user["step"]

    # تمام سؤالات تمام شده
    if step >= len(QUESTIONS):

        show_summary(chat_id)

        return

    question = QUESTIONS[step]

    question_type = question["type"]

    if question_type == "contact":

        send(
            chat_id,
            question["question"],
            contact_keyboard()
        )

    elif question_type == "options":

        send(
            chat_id,
            question["question"],
            option_keyboard(question["options"])
        )

    else:

        send(
            chat_id,
            question["question"],
            remove_keyboard()
        )


def process_answer(chat_id, answer):

    user = users.get(chat_id)

    if not user:
        users[chat_id] = new_user()
        user = users[chat_id]

    step = user["step"]

    if step >= len(QUESTIONS):
        return

    question = QUESTIONS[step]

    # گزینه‌ای
    if question["type"] == "options":

        if answer not in question["options"]:

            send(
                chat_id,
                "لطفاً یکی از گزینه‌های نمایش داده‌شده رو انتخاب کن. 👇",
                option_keyboard(question["options"])
            )

            return

    # ذخیره پاسخ
    user["data"][question["key"]] = answer

    # رفتن به سؤال بعدی
    user["step"] += 1

    logging.info(
        "User %s answered %s",
        chat_id,
        question["key"]
    )

    ask_question(chat_id)


# =========================================================
# SUMMARY
# =========================================================

def build_summary(data):

    lines = [
        "📋 اطلاعات ثبت‌شده",
        ""
    ]

    for question in QUESTIONS:

        key = question["key"]

        value = data.get(
            key,
            "ثبت نشده"
        )

        lines.append(
            f"• {LABELS[key]}: {value}"
        )

    return "\n".join(lines)


def show_summary(chat_id):

    user = users.get(chat_id)

    if not user:
        return

    user["completed"] = True

    text = (
        "🔎 لطفاً اطلاعاتت رو بررسی کن:\n\n"
        + build_summary(user["data"])
        + "\n\n"
        "اگر همه‌چیز درست است، «تأیید و ارسال» را بزن. ✅\n"
        "اگر نیاز به تغییر دارد، «اصلاح اطلاعات» را بزن."
    )

    send(
        chat_id,
        text,
        confirmation_keyboard()
    )


# =========================================================
# ADMIN REPORT
# =========================================================

def build_admin_report(chat_id, msg, data):

    telegram_user = msg.get("from", {})

    username = telegram_user.get(
        "username",
        ""
    )

    lines = [
        "🔔 لید جدید MIRA",
        "",
        build_summary(data),
        "",
        "━━━━━━━━━━━━━━",
        f"🆔 Telegram ID: {chat_id}"
    ]

    if username:
        lines.append(
            f"🔗 Username: @{username}"
        )
    else:
        lines.append(
            "🔗 Username: ندارد"
        )

    lines.append(
        "━━━━━━━━━━━━━━"
    )

    return "\n".join(lines)


# =========================================================
# HANDLE MESSAGE
# =========================================================

def handle_message(msg):

    chat_id = msg["chat"]["id"]

    text = msg.get(
        "text",
        ""
    ).strip()

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    if text == "/start":

        users[chat_id] = new_user()

        send(
            chat_id,
            "درود 👋\n\n"
            "به MIRA خوش اومدی. ✨\n\n"
            "برای آشنایی بهتر با شرایط، هدف و نیازهای تحصیلی‌ات، "
            "چند سؤال کوتاه ازت می‌پرسیم.\n\n"
            "در پایان اطلاعاتت رو بررسی می‌کنی و فقط بعد از تأیید "
            "برای تیم MIRA ارسال می‌شه.\n\n"
            "🚀 بزن بریم!",
            {
                "keyboard": [
                    [{"text": "🚀 بزن بریم"}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        )

        return


    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if text == "/cancel":

        users.pop(chat_id, None)

        send(
            chat_id,
            "فرآیند متوقف شد.\n\n"
            "هر زمان خواستی دوباره /start رو بزن. 👋",
            remove_keyboard()
        )

        return


    # -----------------------------------------------------
    # START BUTTON
    # -----------------------------------------------------

    if text == "🚀 بزن بریم":

        users[chat_id] = new_user()

        ask_question(chat_id)

        return


    # -----------------------------------------------------
    # USER STATE
    # -----------------------------------------------------

    if chat_id not in users:

        send(
            chat_id,
            "برای شروع /start رو بزن. 👋",
            remove_keyboard()
        )

        return


    user = users[chat_id]


    # -----------------------------------------------------
    # RESTART
    # -----------------------------------------------------

    if text == "🔄 شروع دوباره":

        users[chat_id] = new_user()

        send(
            chat_id,
            "حتماً. از اول شروع می‌کنیم. 🔄"
        )

        ask_question(chat_id)

        return


    # -----------------------------------------------------
    # EDIT
    # -----------------------------------------------------

    if text == "✏️ اصلاح اطلاعات":

        users[chat_id] = new_user()

        send(
            chat_id,
            "حتماً. اطلاعات رو دوباره وارد می‌کنیم. ✏️"
        )

        ask_question(chat_id)

        return


    # -----------------------------------------------------
    # CONFIRM
    # -----------------------------------------------------

    if text == "✅ تأیید و ارسال":

        if not user.get("completed"):

            ask_question(chat_id)

            return

        data = user["data"]

        username = msg.get(
            "from",
            {}
        ).get(
            "username",
            ""
        )

        # ذخیره در SQLite
        try:

            save_student(
                chat_id,
                username,
                data
            )

        except Exception:

            logging.exception(
                "Database save failed"
            )


        # گزارش ادمین
        report = build_admin_report(
            chat_id,
            msg,
            data
        )

        sent_to_admin = False

        for admin_id in ADMIN_CHAT_IDS:

            try:

                send(
                    admin_id,
                    report
                )

                sent_to_admin = True

                logging.info(
                    "Report sent to admin %s",
                    admin_id
                )

            except Exception:

                logging.exception(
                    "Failed to send report to admin %s",
                    admin_id
                )


        if sent_to_admin:

            send(
                chat_id,
                "✅ اطلاعاتت با موفقیت ثبت شد.\n\n"
                "گزارشت برای تیم MIRA ارسال شد. 📩\n\n"
                "ممنون که وقت گذاشتی. 🌟",
                remove_keyboard()
            )

        else:

            send(
                chat_id,
                "اطلاعاتت ثبت شد، اما در ارسال گزارش مشکلی پیش آمد.\n"
                "تیم MIRA در حال بررسی است. ⚠️",
                remove_keyboard()
            )

        # فرم تمام شده
        users.pop(chat_id, None)

        return


    # -----------------------------------------------------
    # CONTACT
    # -----------------------------------------------------

    step = user["step"]

    if step >= len(QUESTIONS):
        return

    question = QUESTIONS[step]

    if question["type"] == "contact":

        contact = msg.get("contact")

        if not contact:

            send(
                chat_id,
                "لطفاً با دکمه زیر شماره تماس خودت رو ارسال کن. 📞",
                contact_keyboard()
            )

            return

        sender_id = msg.get(
            "from",
            {}
        ).get(
            "id"
        )

        contact_user_id = contact.get(
            "user_id"
        )

        # اگر شماره متعلق به خود کاربر نیست
        if (
            contact_user_id is not None
            and contact_user_id != sender_id
        ):

            send(
                chat_id,
                "لطفاً شماره تماس خودت رو ارسال کن. 📞",
                contact_keyboard()
            )

            return

        phone = contact.get(
            "phone_number",
            ""
        )

        if not phone:

            send(
                chat_id,
                "شماره تماس دریافت نشد. دوباره امتحان کن. 📞",
                contact_keyboard()
            )

            return

        process_answer(
            chat_id,
            phone
        )

        return


    # -----------------------------------------------------
    # NORMAL ANSWER
    # -----------------------------------------------------

    if not text:

        send(
            chat_id,
            "لطفاً پاسخ این سؤال رو وارد کن."
        )

        return

    process_answer(
        chat_id,
        text
    )


# =========================================================
# WEBHOOK SERVER
# =========================================================

WEBHOOK_PATH = "/telegram-webhook"


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path in ["/", "/health"]:

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

            return

        self.send_response(404)
        self.end_headers()


    def do_POST(self):

        if self.path != WEBHOOK_PATH:

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

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )

            msg = update.get("message")

            if msg:

                handle_message(msg)

            self.send_response(200)
            self.end_headers()

            self.wfile.write(b"ok")

        except Exception:

            logging.exception(
                "Webhook processing error"
            )

            self.send_response(500)
            self.end_headers()


    def log_message(self, format, *args):
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

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        Handler
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

            result = telegram(
                "setWebhook",
                {
                    "url": webhook_url,
                    "allowed_updates": [
                        "message"
                    ]
                }
            )

            logging.info(
                "Webhook configured: %s",
                result
            )

        except Exception:

            logging.exception(
                "Webhook configuration failed"
            )


    logging.info(
        "MIRA Bot started on port %s",
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
