
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8853488501"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "teammira_admin").lstrip("@")
CONSULTANTS_CHANNEL_URL = os.getenv(
    "CONSULTANTS_CHANNEL_URL",
    "https://t.me/miraprivatecahnnel",
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

MENU_TEXT = (
    "به میرا آکادمی خوش اومدی! ⭐️\n\n"
    "برای ادامه، یکی از گزینه‌های زیر رو انتخاب کن:"
)

MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        "ارتباط با ادمین",
        url=f"https://t.me/{ADMIN_USERNAME}"
    )],
    [InlineKeyboardButton(
        "مشاورین و ثبت‌نام",
        url=CONSULTANTS_CHANNEL_URL
    )],
    [InlineKeyboardButton(
        "پیام‌ها و پیشنهادات",
        callback_data="feedback"
    )],
])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_feedback", None)
    if update.effective_message:
        await update.effective_message.reply_text(
            MENU_TEXT,
            reply_markup=MENU_KEYBOARD,
        )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    if query.data == "feedback":
        context.user_data["awaiting_feedback"] = True
        await query.message.reply_text(
            "پیام یا پیشنهادت رو به‌صورت متنی بفرست.\n"
            "برای لغو، دستور /cancel رو بزن."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_feedback", None)
    if update.effective_message:
        await update.effective_message.reply_text(
            "ارسال پیام لغو شد.",
            reply_markup=MENU_KEYBOARD,
        )


async def receive_feedback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    if message.chat.type != ChatType.PRIVATE:
        return

    text = (message.text or "").strip()
    if not text:
        await message.reply_text("لطفاً پیام رو به‌صورت متن ارسال کن.")
        return

    username = f"@{user.username}" if user.username else "ندارد"
    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    ) or "ثبت نشده"

    admin_text = (
        "📩 پیام جدید از طریق بات میرا\n\n"
        f"👤 نام: {full_name}\n"
        f"🔹 نام کاربری: {username}\n"
        f"🆔 آیدی عددی: {user.id}\n\n"
        f"متن پیام:\n{text}"
    )

    try:
        for i in range(0, len(admin_text), 3900):
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text[i:i + 3900],
            )
    except TelegramError:
        logger.exception("Could not forward feedback to admin")
        await message.reply_text(
            "ارسال پیام با مشکل مواجه شد. کمی بعد دوباره تلاش کن."
        )
        return

    context.user_data.pop("awaiting_feedback", None)
    await message.reply_text(
        "پیامت برای تیم میرا ارسال شد. ممنون از پیشنهادت! ⭐️",
        reply_markup=MENU_KEYBOARD,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_feedback"):
        await receive_feedback(update, context)
    elif update.effective_message:
        await update.effective_message.reply_text(
            "برای دیدن منو، دستور /start رو بزن.",
            reply_markup=MENU_KEYBOARD,
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled bot error", exc_info=context.error)


def main():
    if not BOT_TOKEN.strip():
        raise RuntimeError("BOT_TOKEN environment variable is empty.")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_error_handler(error_handler)

    logger.info("Mira Academy bot is starting.")
    application.run_polling()


if __name__ == "__main__":
    main()
