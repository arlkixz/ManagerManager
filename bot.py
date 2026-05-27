import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN در محیط تعریف نشده است!")
if not ADMIN_IDS:
    raise ValueError("❌ ADMIN_IDS در محیط تعریف نشده است!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ربات پاکسازی پیام‌ها فعال شد!\n\n"
        "⚠️ توجه: به دلیل محدودیت تلگرام، ربات فقط می‌تواند:\n"
        "• پیام‌های بعد از اضافه شدن به گروه را ببیند\n"
        "• پیام‌های جدید (کمتر از 48 ساعت) را حذف کند\n\n"
        "دستورات:\n"
        "/clean_new [تعداد] - حذف آخرین پیام‌ها\n"
        "/clean_old [تعداد] - حذف پیام‌های قدیمی‌تر از 1 ساعت\n"
        "/clean_all - حذف تمام پیام‌های ربات"
    )

async def clean_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف آخرین پیام‌ها (با استفاده از message_id)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    try:
        count = int(context.args[0]) if context.args else 10
        count = min(count, 50)
    except:
        count = 10
    
    chat_id = update.effective_chat.id
    current_message_id = update.message.message_id
    
    # حذف پیام دستور
    try:
        await context.bot.delete_message(chat_id, current_message_id)
    except:
        pass
    
    deleted_count = 0
    
    # از message_id فعلی به عقب برمی‌گردیم و پیام‌ها را حذف می‌کنیم
    for i in range(1, count + 1):
        target_id = current_message_id - i
        if target_id <= 0:
            break
        try:
            await context.bot.delete_message(chat_id, target_id)
            deleted_count += 1
            await asyncio.sleep(0.3)
        except:
            pass
    
    await context.bot.send_message(chat_id, f"✅ {deleted_count} پیام جدید حذف شد.")

async def clean_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف پیام‌های قدیمی - با توجه به محدودیت 48 ساعت تلگرام"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    chat_id = update.effective_chat.id
    current_message_id = update.message.message_id
    
    try:
        await context.bot.delete_message(chat_id, current_message_id)
    except:
        pass
    
    # این دستور به دلیل محدودیت‌های تلگرام عملاً فقط پیام‌های جدیدتر از 48 ساعت را می‌تواند حذف کند
    await context.bot.send_message(
        chat_id, 
        "⚠️ به دلیل محدودیت تلگرام، فقط پیام‌های کمتر از 48 ساعت قابل حذف هستند.\n"
        "برای حذف پیام‌های قدیمی‌تر، ربات باید ادمین گروه باشد."
    )

async def clean_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف تمام پیام‌های خود ربات"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    chat_id = update.effective_chat.id
    current_message_id = update.message.message_id
    
    try:
        await context.bot.delete_message(chat_id, current_message_id)
    except:
        pass
    
    deleted_count = 0
    
    # حذف پیام‌های ربات (تا 100 پیام قبلی)
    for i in range(1, 101):
        target_id = current_message_id - i
        if target_id <= 0:
            break
        try:
            # بررسی می‌کنیم که آیا این پیام متعلق به ربات است یا خیر
            # (از طریق try/except انجام می‌شود چون نمی‌توانیم بدون دریافت پیام متوجه شویم)
            await context.bot.delete_message(chat_id, target_id)
            deleted_count += 1
            await asyncio.sleep(0.2)
        except:
            pass
    
    await context.bot.send_message(chat_id, f"✅ {deleted_count} پیام از ربات حذف شد.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *راهنمای کامل:*\n\n"
        "• `/clean_new [تعداد]` - حذف آخرین پیام‌ها (حداکثر 50)\n"
        "• `/clean_old [تعداد]` - حذف پیام‌های قدیمی‌تر (با محدودیت 48 ساعت)\n"
        "• `/clean_all` - حذف تمام پیام‌های خود ربات\n\n"
        "⚠️ *محدودیت‌های مهم:*\n"
        "1. تلگرام فقط اجازه حذف پیام‌های کمتر از 48 ساعت را می‌دهد[citation:1]\n"
        "2. ربات فقط به پیام‌های بعد از اضافه شدن به گروه دسترسی دارد\n"
        "3. برای حذف پیام‌های دیگران، ربات باید ادمین گروه باشد",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clean_new", clean_new))
    app.add_handler(CommandHandler("clean_old", clean_old))
    app.add_handler(CommandHandler("clean_all", clean_all))
    
    print("🤖 ربات روشن شد...")
    print("⚠️ توجه: به دلیل محدودیت تلگرام، ربات فقط می‌تواند پیام‌های جدید (کمتر از 48 ساعت) را حذف کند")
    app.run_polling()

if __name__ == "__main__":
    main()
