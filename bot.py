import os
import sqlite3
import logging
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "8968943708:AAEN6x0Nu3a2v1ybkPTID3Ra5uv0hY4Ecug")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "8853488501").split(",") if x.strip().isdigit()]
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "miracampus").replace("@", "")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "teammira_admin").replace("@", "")
CLASS_CHANNEL = os.getenv("CLASS_CHANNEL", "mirakunkorclss").replace("@", "")
CARD_NUMBER = os.getenv("CARD_NUMBER", "6219861940398554")
CARD_NAME = os.getenv("CARD_NAME", "محمد مهدی روشنی")

logging.basicConfig(level=logging.INFO)
DB = "mira.db"

def db():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY,
        name TEXT, grade TEXT, field TEXT, phone TEXT,
        join_date TEXT, sub_days INTEGER DEFAULT 0,
        plan TEXT DEFAULT '-'
    )""")
    return con
CON = db()

def add_or_update_user(tid, name=None, grade=None, field=None, phone=None, plan=None):
    cur = CON.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (tid,))
    exists = cur.fetchone()
    if not exists:
        cur.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?)",
            (tid, name or "-", grade or "-", field or "-", phone or "-", datetime.now().strftime("%Y-%m-%d %H:%M"), 0, plan or "-"))
    else:
        if name: cur.execute("UPDATE users SET name=? WHERE telegram_id=?", (name, tid))
        if grade: cur.execute("UPDATE users SET grade=? WHERE telegram_id=?", (grade, tid))
        if field: cur.execute("UPDATE users SET field=? WHERE telegram_id=?", (field, tid))
        if phone: cur.execute("UPDATE users SET phone=? WHERE telegram_id=?", (phone, tid))
        if plan: cur.execute("UPDATE users SET plan=? WHERE telegram_id=?", (plan, tid))
    CON.commit()

def get_user(tid):
    cur = CON.cursor()
    cur.execute("SELECT name,grade,field,phone,join_date,sub_days,plan FROM users WHERE telegram_id=?", (tid,))
    return cur.fetchone()

def user_number(tid):
    cur = CON.cursor()
    cur.execute("SELECT telegram_id FROM users ORDER BY rowid")
    ids = [r[0] for r in cur.fetchall()]
    return ids.index(tid)+1 if tid in ids else 0

def main_menu():
    return ReplyKeyboardMarkup([
        ["📚 پلن‌های مشاوره", "💳 پرداخت و تمدید اشتراک"],
        ["🎓 کلاس‌های کنکوری", "☎️ ارتباط با پشتیبان"],
        ["👤 پنل من"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 آمار امروز", "👥 لیست آخر"],
        ["🏠 منوی دانش‌آموز"]
    ], resize_keyboard=True)

NAME, GRADE, FIELD, PHONE = range(4)

PLANS = {
    "task": {
        "title": "📚 تسک‌پلن | ۳ ماهه",
        "desc": "اگر می‌دانی باید بیشتر و بهتر درس بخوانی، اما نمی‌دانی هر روز دقیقاً چه کاری انجام بدهی، این پلن برای توست.\n\n▫️ برنامه روزانه و دقیق مطالعه\n▫️ تعیین تسک‌ها و اولویت‌های درسی\n▫️ مشخص‌کردن مسیر پیشروی\n\n💰 هزینه سه‌ماهه: ۲,۷۰۰,۰۰۰ تومان\nمعادل ماهانه ۹۰۰,۰۰۰ تومان",
        "price": "۲,۷۰۰,۰۰۰ تومان"
    },
    "mentor": {
        "title": "🎯 تسک‌پلن منتورینگ | ۳ ماهه",
        "desc": "فقط برنامه نمی‌گیری؛ در مسیر اجرا هم تنها نیستی. منتور عملکردت را دنبال می‌کند و بر اساس روند واقعی مطالعه‌ات، مسیر را اصلاح می‌کند.\n\n▫️ تمام امکانات تسک‌پلن\n▫️ پیگیری و نظارت منتور\n▫️ بررسی عملکرد و نقاط ضعف\n▫️ اصلاح مسیر بر اساس پیشرفت\n\n💰 هزینه سه‌ماهه: ۳,۶۰۰,۰۰۰ تومان\nمعادل ماهانه ۱,۲۰۰,۰۰۰ تومان",
        "price": "۳,۶۰۰,۰۰۰ تومان"
    },
    "p360": {
        "title": "🚀 مشاوره ۳۶۰ | ۳ ماهه",
        "desc": "برای کسی که می‌خواهد مسیر کنکورش فقط برنامه‌ریزی نشود؛ بلکه به‌صورت کامل مدیریت، بررسی و هدایت شود.\n\n▫️ برنامه‌ریزی و تسک‌های روزانه\n▫️ منتورینگ و پیگیری مستمر\n▫️ تحلیل عملکرد و روند پیشرفت\n▫️ هدایت و اصلاح همه‌جانبه مسیر کنکور\n\n💰 هزینه سه‌ماهه: ۴,۵۰۰,۰۰۰ تومان\nمعادل ماهانه ۱,۵۰۰,۰۰۰ تومان",
        "price": "۴,۵۰۰,۰۰۰ تومان"
    },
}

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        return True
    try:
        m = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        if m.status in ["member", "administrator", "creator"]:
            return True
    except:
        return True
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال میرا", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
    ])
    if update.message:
        await update.message.reply_text("🔒 برای استفاده از بات میرا، اول عضو کانال اصلی شو بعد دکمه عضو شدم رو بزن:", reply_markup=kb)
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        await update.message.reply_text("👑 سلام ادمین! به پنل میرا خوش اومدی.", reply_markup=admin_menu())
        return ConversationHandler.END
    if not await check_join(update, context):
        return ConversationHandler.END
    u = get_user(uid)
    if u and u[0] != "-":
        await update.message.reply_text(f"سلام {u[0]} عزیز! 👋\nبه تیم میرا خوش برگشتی ❤️", reply_markup=main_menu())
        return ConversationHandler.END
    await update.message.reply_text("سلام رفیق! 👋\nبه تیم میرا خوش اومدی 🎯\nاینجا کمتر از ۱ دقیقه ثبت‌نام می‌کنی و دوره‌ها رو می‌بینی.\n\n📝 اول نام و نام خانوادگیت رو بفرست:")
    return NAME

async def on_check_join_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        m = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", q.from_user.id)
        ok = m.status in ["member", "administrator", "creator"]
    except:
        ok = True
    if not ok:
        await q.answer("هنوز عضو نشدی!", show_alert=True)
        return ConversationHandler.END
    await q.message.reply_text("✅ عضویتت تایید شد! حالا نام و نام خانوادگیت رو بفرست:")
    return NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["دهم", "یازدهم"], ["دوازدهم", "پشت کنکور"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("پایه تحصیلیت رو انتخاب کن 👇", reply_markup=kb)
    return GRADE

async def reg_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["grade"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["تجربی", "ریاضی"], ["انسانی", "هنر / زبان"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("رشته‌ت چیه؟ 👇", reply_markup=kb)
    return FIELD

async def reg_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["field"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("برای احراز هویت، شماره تماست رو با دکمه زیر بفرست 👇", reply_markup=kb)
    return PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    phone = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    d = context.user_data
    add_or_update_user(uid, name=d.get("name"), grade=d.get("grade"), field=d.get("field"), phone=phone)
    await update.message.reply_text(f"🎉 پنلت ساخته شد {d.get('name')}!\n✅ ثبت‌نامت انجام شد و برای پشتیبان ما ثبت شد.\n\nاز منوی زیر انتخاب کن 👇", reply_markup=main_menu())
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid, f"🆕 ثبت‌نام جدید\n👤 {d.get('name')}\n🎓 {d.get('grade')} | {d.get('field')}\n📱 {phone}\n🆔 {uid}")
        except: pass
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لغو شد.", reply_markup=main_menu())
    return ConversationHandler.END

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    txt = update.message.text.strip()
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        if txt == "📊 آمار امروز":
            cur = CON.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users WHERE join_date LIKE ?", (datetime.now().strftime("%Y-%m-%d")+"%",))
            today = cur.fetchone()[0]
            await update.message.reply_text(f"📊 آمار میرا\n👥 کل دانش‌آموزان: {total}\n🆕 ورودی امروز: {today}\n🟢 در حال استفاده: {total}")
            return
        if txt == "👥 لیست آخر":
            cur = CON.cursor()
            cur.execute("SELECT telegram_id,name,grade,field FROM users ORDER BY rowid DESC LIMIT 10")
            rows = cur.fetchall()
            s = "👥 ۱۰ ثبت‌نام آخر:\n" + "\n".join([f"{r[0]} - {r[1]} ({r[2]}|{r[3]})" for r in rows]) if rows else "کسی ثبت‌نام نکرده"
            await update.message.reply_text(s)
            return
        if txt == "🏠 منوی دانش‌آموز":
            await update.message.reply_text("منوی دانش‌آموز:", reply_markup=main_menu())
            return
        return
    if txt == "📚 پلن‌های مشاوره":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 تسک‌پلن | ۳ ماهه", callback_data="plan_task")],
            [InlineKeyboardButton("🎯 منتورینگ | ۳ ماهه", callback_data="plan_mentor")],
            [InlineKeyboardButton("🚀 مشاوره ۳۶۰ | ۳ ماهه", callback_data="plan_p360")],
        ])
        await update.message.reply_text("📚 یکی از پلن‌های مشاوره میرا رو انتخاب کن:", reply_markup=kb)
    elif txt == "💳 پرداخت و تمدید اشتراک":
        await update.message.reply_text(f"💳 مبلغ پلنت رو به این کارت بزن و عکس رسید رو همینجا بفرست:\n\n`{CARD_NUMBER}`\n👤 به‌نام: {CARD_NAME}\n\n📸 منتظر رسیدتم!", parse_mode="Markdown")
    elif txt == "🎓 کلاس‌های کنکوری":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 کانال اخبار کلاس‌ها", url=f"https://t.me/{CLASS_CHANNEL}")]])
        await update.message.reply_text("🎓 کلاس‌های کنکوری هنوز شروع نشده (به‌زودی...)\nبرای اطلاع از آخرین اخبار وارد کانال شو 👇", reply_markup=kb)
    elif txt == "☎️ ارتباط با پشتیبان":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 چت با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")]])
        await update.message.reply_text("☎️ هر سوالی داری پشتیبان ما اینجاست 👇", reply_markup=kb)
    elif txt == "👤 پنل من":
        u = get_user(uid)
        if not u:
            await update.message.reply_text("هنوز ثبت‌نام نکردی! /start رو بزن.")
            return
        name, grade, field, phone, jdate, sub, plan = u
        num = user_number(uid)
        await update.message.reply_text(f"👤 پنل من\n\n📛 نام: {name}\n🎓 پایه: {grade}\n📖 رشته: {field}\n📱 شماره: {phone}\n🔢 تو {num}مین دانش‌آموز میرایی!\n📦 پلن: {plan}\n⏳ اشتراک باقی‌مانده: {sub} روز")

async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.replace("plan_", "")
    if key.startswith("buy_"):
        real = key.replace("buy_", "")
        add_or_update_user(q.from_user.id, plan=PLANS[real]["title"])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"pay_{real}")],
            [InlineKeyboardButton("☎️ مشاوره با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ])
        await q.message.reply_text(f"{PLANS[real]['title']} انتخاب شد ✅\nحالا پرداخت کن یا با پشتیبان صحبت کن 👇", reply_markup=kb)
        return
    if key.startswith("pay_"):
        real = key.replace("pay_", "")
        await q.message.reply_text(f"💳 مبلغ {PLANS[real]['price']} رو به این کارت بزن و عکس رسید رو بفرست:\n\n`{CARD_NUMBER}`\n👤 {CARD_NAME}", parse_mode="Markdown")
        return
    p = PLANS.get(key)
    if not p: return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 کانال اطلاعات بیشتر", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ انتخاب این پلن", callback_data=f"plan_buy_{key}")]
    ])
    await q.message.reply_text(f"{p['title']}\n\n{p['desc']}", reply_markup=kb)

async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_IDS: return
    u = get_user(uid)
    name = u[0] if u else "-"
    plan = u[6] if u else "-"
    cap = f"🧾 رسید جدید\n👤 {name}\n🆔 `{uid}`\n📦 پلن: {plan}\n\nفعال‌سازی: `/approve {uid} 90`"
    for aid in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(aid, update.message.photo[-1].file_id, caption=cap, parse_mode="Markdown")
            elif update.message.text:
                await context.bot.send_message(aid, cap, parse_mode="Markdown")
        except: pass
    await update.message.reply_text("✅ رسیدت رفت برای ادمین!\nبه‌زودی مشاورت بهت وصل میشه و کارت استارت می‌خوره 🚀", reply_markup=main_menu())

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        _, tid, days = update.message.text.split()
        tid, days = int(tid), int(days)
        cur = CON.cursor()
        cur.execute("UPDATE users SET sub_days=? WHERE telegram_id=?", (days, tid))
        CON.commit()
        await update.message.reply_text(f"✅ اشتراک {tid} شد {days} روز.")
        await context.bot.send_message(tid, f"🎉 اشتراکت {days} روز تمدید شد! موفق باشی ❤️")
    except:
        await update.message.reply_text("فرمت: `/approve ID ROOZ`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(on_check_join_btn, pattern="^check_join$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_grade)],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_field)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, reg_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(plan_callback, pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(plan_callback, pattern="^pay_"))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(MessageHandler(filters.PHOTO, receipt_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))
    print("Mira Bot Running...")
    app.run_polling()

flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Mira Bot is Alive!"

if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()
    main()
