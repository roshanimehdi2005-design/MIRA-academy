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

CHANNEL_USERNAME = "@miracampus"
CHANNEL_URL = "https://t.me/miracampus"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


if not TOKEN:
    raise SystemExit("BOT_TOKEN is missing.")


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
        "question": "👤 نام و نام خانوادگی‌ات رو وارد کن:",
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
        "key": "goal",
        "question": "🎯 هدفت از مشاوره یا آموزش چیه؟",
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
        "question": (
            "📝 اگر توضیح یا نکته‌ای درباره شرایطت هست "
            "که فکر می‌کنی باید بدونیم، اینجا بنویس.\n\n"
            "اگر موردی نداری، بنویس «ندارم»."
        ),
        "type": "text"
    },
    {
        "key": "phone",
        "question": (
            "📞 برای اینکه ادمین MIRA بتونه باهات تماس بگیره، "
            "شماره تماست رو ارسال کن:"
        ),
        "type": "contact"
    }
]


LABELS = {
    "full_name": "نام و نام خانوادگی",
    "grade": "پایه تحصیلی",
    "field": "رشته",
    "goal": "هدف اصلی",
    "problem": "مهم‌ترین مشکل درسی",
    "extra": "توضیحات تکمیلی",
    "phone": "شماره تماس"
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
# TELEGRAM API
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


def answer_callback(callback_query_id, text=None):
    data = {
        "callback_query_id": callback_query_id
    }

    if text:
        data["text"] = text

    return telegram("answerCallbackQuery", data)


# =========================================================
# MEMBERSHIP
# =========================================================

def is_channel_member(chat_id):
    try:
        result = telegram(
            "getChatMember",
            {
                "chat_id": CHANNEL_USERNAME,
                "user_id": chat_id
            }
        )

        status = result["result"]["status"]

        return status in [
            "creator",
            "administrator",
            "member"
        ]

    except Exception:
        logging.exception(
            "Membership check failed for %s",
            chat_id
        )

        return False


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
        "سلام رفیق 👋\n\n"
        "برای استفاده از بات MIRA، ابتدا باید عضو "
        "کانال اصلی MIRA بشی. 📢\n\n"
        "بعد از عضویت، روی «✅ بررسی عضویت» بزن "
        "تا وارد بات بشی. 🚀",
        membership_keyboard()
    )


# =========================================================
# MAIN MENU
# =========================================================

def main_menu_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "📝 ثبت‌نام و درخواست مشاوره"
                }
            ],
            [
                {
                    "text": "🎓 معرفی دوره‌ها"
                }
            ],
            [
                {
                    "text": "💳 پرداخت و تمدید اشتراک"
                }
            ],
            [
                {
                    "text": "👤 پنل من"
                }
            ],
            [
                {
                    "text": "🆘 پشتیبانی"
                }
            ]
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


def check_membership_and_continue(chat_id):
    if is_channel_member(chat_id):
        send_main_menu(chat_id)
    else:
        send_membership_gate(chat_id)


# =========================================================
# COURSE MENU
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
                {
                    "text": "✅ تأیید و ارسال"
                }
            ],
            [
                {
                    "text": "✏️ اصلاح اطلاعات"
                },
                {
                    "text": "🔄 شروع دوباره"
                }
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

    if question["type"] == "options":

        if answer not in question["options"]:

            send(
                chat_id,
                "لطفاً یکی از گزینه‌های نمایش‌داده‌شده "
                "رو انتخاب کن. 👇",
                option_keyboard(question["options"])
            )

            return

    user["data"][question["key"]] = answer
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
        "اگر همه‌چیز درسته، "
        "«تأیید و ارسال» رو بزن. ✅\n"
        "اگر نیاز به تغییر داره، "
        "«اصلاح اطلاعات» رو بزن."
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

    telegram_user = msg.get(
        "from",
        {}
    )

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
# CALLBACK QUERIES
# =========================================================

def handle_callback_query(callback_query):

    callback_id = callback_query.get(
        "id"
    )

    data = callback_query.get(
        "data",
        ""
    )

    message = callback_query.get(
        "message"
    )

    if not message:
        return

    chat_id = message["chat"]["id"]


    # -----------------------------------------------------
    # MEMBERSHIP
    # -----------------------------------------------------

    if data == "check_membership":

        if is_channel_member(chat_id):

            answer_callback(
                callback_id,
                "عضویتت تأیید شد ✅"
            )

            send_main_menu(
                chat_id
            )

        else:

            answer_callback(
                callback_id,
                "هنوز عضویتت تأیید نشده ❌"
            )

            send(
                chat_id,
                "رفیق، هنوز عضویتت در کانال MIRA "
                "تأیید نشده. 👇\n\n"
                "اول عضو کانال شو و بعد دوباره "
                "«✅ بررسی عضویت» رو بزن.",
                membership_keyboard()
            )

        return


    # -----------------------------------------------------
    # BACK TO MAIN
    # -----------------------------------------------------

    if data == "back_to_main":

        answer_callback(
            callback_id,
            "برگشتیم به منوی اصلی 👌"
        )

        send_main_menu(
            chat_id
        )

        return


# =========================================================
# MAIN MENU ACTIONS
# =========================================================

def handle_main_menu_action(chat_id, text):


    # -----------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------

    if text == "📝 ثبت‌نام و درخواست مشاوره":

        if not is_channel_member(chat_id):

            send_membership_gate(
                chat_id
            )

            return True


        users[chat_id] = new_user()


        send(
            chat_id,
            "عالیه رفیق 👌\n\n"
            "برای اینکه تیم MIRA بتونه "
            "بهترین مسیر رو برات مشخص کنه، "
            "چند سؤال کوتاه ازت می‌پرسیم.\n\n"
            "در پایان، اطلاعاتت رو بررسی می‌کنی "
            "و بعد برای تیم MIRA ارسال می‌شه. 🚀"
        )


        ask_question(
            chat_id
        )

        return True


    # -----------------------------------------------------
    # COURSES
    # -----------------------------------------------------

    if text == "🎓 معرفی دوره‌ها":

        if not is_channel_member(chat_id):

            send_membership_gate(
                chat_id
            )

            return True

        send_courses_menu(
            chat_id
        )

        return True


    # -----------------------------------------------------
    # PAYMENT
    # -----------------------------------------------------

    if text == "💳 پرداخت و تمدید اشتراک":

        send(
            chat_id,
            "💳 پرداخت و تمدید اشتراک\n\n"
            "سیستم پرداخت و تمدید اشتراک MIRA "
            "در مرحله بعد راه‌اندازی می‌شه. 🔐\n\n"
            "در این بخش وضعیت اشتراک، کد تأیید، "
            "پرداخت و ارسال رسید مدیریت خواهد شد."
        )

        return True


    # -----------------------------------------------------
    # USER PANEL
    # -----------------------------------------------------

    if text == "👤 پنل من":

        send(
            chat_id,
            "👤 پنل من\n\n"
            "پنل شخصی MIRA در حال آماده‌سازی است. ✨\n\n"
            "در نسخه نهایی می‌تونی وضعیت اشتراک، "
            "دوره، مشاور، تاریخ شروع، تاریخ پایان "
            "و تعداد روزهای باقی‌مانده رو ببینی."
        )

        return True


    # -----------------------------------------------------
    # SUPPORT
    # -----------------------------------------------------

    if text == "🆘 پشتیبانی":

        send(
            chat_id,
            "🆘 پشتیبانی MIRA\n\n"
            "اگر سوال یا مشکلی داری، "
            "پیامت رو برای تیم MIRA ارسال کن.\n\n"
            "سیستم پشتیبانی در مرحله بعد "
            "به‌صورت کامل راه‌اندازی می‌شه. 🤝"
        )

        return True


    return False


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

        users.pop(
            chat_id,
            None
        )

        check_membership_and_continue(
            chat_id
        )

        return


    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if text == "/cancel":

        users.pop(
            chat_id,
            None
        )

        send(
            chat_id,
            "فرآیند متوقف شد.\n\n"
            "هر زمان خواستی دوباره /start رو بزن. 👋",
            main_menu_keyboard()
        )

        return


    # -----------------------------------------------------
    # OLD START BUTTON
    # -----------------------------------------------------

    if text == "🚀 بزن بریم":

        if not is_channel_member(chat_id):

            send_membership_gate(
                chat_id
            )

            return


        users[chat_id] = new_user()

        ask_question(
            chat_id
        )

        return


    # -----------------------------------------------------
    # MAIN MENU
    # -----------------------------------------------------

    if handle_main_menu_action(
        chat_id,
        text
    ):

        return


    # -----------------------------------------------------
    # NO ACTIVE USER FLOW
    # -----------------------------------------------------

    if chat_id not in users:

        if is_channel_member(chat_id):

            send(
                chat_id,
                "از منوی زیر انتخاب کن 👇",
                main_menu_keyboard()
            )

        else:

            send_membership_gate(
                chat_id
            )

        return


    # -----------------------------------------------------
    # CURRENT USER
    # -----------------------------------------------------

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

        ask_question(
            chat_id
        )

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

        ask_question(
            chat_id
        )

        return


    # -----------------------------------------------------
    # CONFIRM
    # -----------------------------------------------------

    if text == "✅ تأیید و ارسال":

        if not user.get("completed"):

            ask_question(
                chat_id
            )

            return


        data = user["data"]

        username = msg.get(
            "from",
            {}
        ).get(
            "username",
            ""
        )


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
                "گزارشت برای تیم MIRA ارسال شد و "
                "ادمین MIRA باهات تماس خواهد گرفت. 📩\n\n"
                "از اعتمادت ممنونیم رفیق. 🤍",
                main_menu_keyboard()
            )

        else:

            send(
                chat_id,
                "اطلاعاتت ثبت شد، اما در ارسال گزارش "
                "مشکلی پیش آمد.\n"
                "تیم MIRA در حال بررسی است. ⚠️",
                main_menu_keyboard()
            )


        users.pop(
            chat_id,
            None
        )

        return


    # -----------------------------------------------------
    # QUESTION FLOW
    # -----------------------------------------------------

    step = user["step"]

    if step >= len(QUESTIONS):

        return


    question = QUESTIONS[step]


    # -----------------------------------------------------
    # CONTACT
    # -----------------------------------------------------

    if question["type"] == "contact":

        contact = msg.get(
            "contact"
        )


        if not contact:

            send(
                chat_id,
                "لطفاً با دکمه زیر شماره تماس "
                "خودت رو ارسال کن. 📞",
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


        if (
            contact_user_id is not None
            and contact_user_id != sender_id
        ):

            send(
                chat_id,
                "لطفاً شماره تماس خودت "
                "رو ارسال کن. 📞",
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
                "شماره تماس دریافت نشد. "
                "دوباره امتحان کن. 📞",
                contact_keyboard()
            )

            return


        process_answer(
            chat_id,
            phone
        )

        return


    # -----------------------------------------------------
    # TEXT
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
# WEBHOOK
# =========================================================

WEBHOOK_PATH = "/telegram-webhook"


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path in [
            "/",
            "/health"
        ]:

            body = b"MIRA Bot is running"

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

            return


        self.send_response(
            404
        )

        self.end_headers()


    def do_POST(self):

        if self.path != WEBHOOK_PATH:

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

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )


            msg = update.get(
                "message"
            )

            callback_query = update.get(
                "callback_query"
            )


            if msg:

                handle_message(
                    msg
                )

            elif callback_query:

                handle_callback_query(
                    callback_query
                )


            self.send_response(
                200
            )

            self.end_headers()

            self.wfile.write(
                b"ok"
            )


        except Exception:

            logging.exception(
                "Webhook processing error"
            )

            self.send_response(
                500
            )

            self.end_headers()


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


    server = ThreadingHTTPServer(
        (
            "0.0.0.0",
            port
        ),
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
                        "message",
                        "callback_query"
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
