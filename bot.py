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
        "دستورات:\n"
        "/clean_new [تعداد] - حذف پیام‌های جدید\n"
        "/clean_old [تعداد] - حذف پیام‌های قدیمی‌تر از 1 ساعت\n"
        "/clean_week - حذف پیام‌های هفته گذشته (7 روز پیش)\n"
        "/clean_month - حذف پیام‌های ماه گذشته\n"
        "/clean_all - حذف تمام پیام‌های ربات"
    )

async def clean_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    chat_id = update.effective_chat.id
    
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except:
        pass
    
    one_week_ago = datetime.now() - timedelta(days=7)
    deleted_count = 0
    checked_count = 0
    
    status_msg = await context.bot.send_message(chat_id, "🔄 در حال بررسی پیام‌های هفته گذشته...")
    
    try:
        # روش درست برای دریافت تاریخچه پیام‌ها
        async for message in context.bot.get_chat(chat_id).iterate_messages(limit=500):
            checked_count += 1
            
            if checked_count % 50 == 0:
                await status_msg.edit_text(f"🔄 بررسی شد: {checked_count} پیام | حذف شد: {deleted_count}")
            
            if message.date.replace(tzinfo=None) < one_week_ago:
                try:
                    await context.bot.delete_message(chat_id, message.message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.2)
                except:
                    pass
                    
    except Exception as e:
        await status_msg.edit_text(f"❌ خطا: {str(e)}")
        return
    
    await status_msg.edit_text(f"✅ {deleted_count} پیام از هفته گذشته حذف شد.\n📊 کل بررسی شده: {checked_count}")

async def clean_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    chat_id = update.effective_chat.id
    
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except:
        pass
    
    one_month_ago = datetime.now() - timedelta(days=30)
    deleted_count = 0
    checked_count = 0
    
    status_msg = await context.bot.send_message(chat_id, "🔄 در حال بررسی پیام‌های ماه گذشته...")
    
    try:
        async for message in context.bot.get_chat(chat_id).iterate_messages(limit=500):
            checked_count += 1
            if checked_count % 50 == 0:
                await status_msg.edit_text(f"🔄 بررسی شد: {checked_count} پیام | حذف شد: {deleted_count}")
            
            if message.date.replace(tzinfo=None) < one_month_ago:
                try:
                    await context.bot.delete_message(chat_id, message.message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.2)
                except:
                    pass
                    
    except Exception as e:
        await status_msg.edit_text(f"❌ خطا: {str(e)}")
        return
    
    await status_msg.edit_text(f"✅ {deleted_count} پیام از ماه گذشته حذف شد.")

async def clean_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    try:
        count = int(context.args[0]) if context.args else 10
        count = min(count, 100)
    except:
        count = 10
    
    chat_id = update.effective_chat.id
    
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except:
        pass
    
    deleted_count = 0
    one_hour_ago = datetime.now() - timedelta(hours=1)
    
    try:
        async for message in context.bot.get_chat(chat_id).iterate_messages(limit=count+10):
            if message.date.replace(tzinfo=None) > one_hour_ago:
                try:
                    await context.bot.delete_message(chat_id, message.message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")
        return
    
    await update.message.reply_text(f"✅ {deleted_count} پیام جدید حذف شد.")

async def clean_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    try:
        count = int(context.args[0]) if context.args else 50
        count = min(count, 200)
    except:
        count = 50
    
    chat_id = update.effective_chat.id
    
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except:
        pass
    
    one_hour_ago = datetime.now() - timedelta(hours=1)
    deleted_count = 0
    
    try:
        async for message in context.bot.get_chat(chat_id).iterate_messages(limit=count+10):
            if message.date.replace(tzinfo=None) < one_hour_ago:
                try:
                    await context.bot.delete_message(chat_id, message.message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")
        return
    
    await update.message.reply_text(f"✅ {deleted_count} پیام قدیمی (بیشتر از 1 ساعت) حذف شد.")

async def clean_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند از این دستور استفاده کند.")
        return
    
    chat_id = update.effective_chat.id
    
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except:
        pass
    
    deleted_count = 0
    
    try:
        async for message in context.bot.get_chat(chat_id).iterate_messages(limit=100):
            if message.from_user and message.from_user.id == context.bot.id:
                try:
                    await context.bot.delete_message(chat_id, message.message_id)
                    deleted_count += 1
                    await asyncio.sleep(0.2)
                except:
                    pass
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")
        return
    
    await context.bot.send_message(chat_id, f"✅ {deleted_count} پیام از ربات حذف شد.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *راهنمای کامل:*\n\n"
        "• `/clean_new [تعداد]` - حذف پیام‌های جدید (کمتر از 1 ساعت)\n"
        "• `/clean_old [تعداد]` - حذف پیام‌های قدیمی (بیشتر از 1 ساعت)\n"
        "• `/clean_week` - حذف پیام‌های هفته گذشته (قدیمی‌تر از 7 روز)\n"
        "• `/clean_month` - حذف پیام‌های ماه گذشته (قدیمی‌تر از 30 روز)\n"
        "• `/clean_all` - حذف تمام پیام‌های خود ربات\n\n"
        "⚠️ محدودیت تلگرام: پیام‌های بیشتر از 48 ساعت را فقط ادمین می‌تواند حذف کند.",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clean_new", clean_new))
    app.add_handler(CommandHandler("clean_old", clean_old))
    app.add_handler(CommandHandler("clean_week", clean_week))
    app.add_handler(CommandHandler("clean_month", clean_month))
    app.add_handler(CommandHandler("clean_all", clean_all))
    
    print("🤖 ربات روشن شد...")
    print(f"👑 ادمین‌ها: {ADMIN_IDS}")
    app.run_polling()

if __name__ == "__main__":
    main()
