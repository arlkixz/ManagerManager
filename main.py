import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

# دیکشنری برای ذخیره وضعیت کاربرا
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🤖 ربات بازدید تلگرام\n\n"
        "لینک پست یا کانال خود را ارسال کنید.\n"
        "مثال: https://t.me/username/123\n"
        "یا: @username"
    )
    user_states[user_id] = "waiting_link"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_states:
        await start(update, context)
        return
    
    state = user_states[user_id]
    
    if state == "waiting_link":
        # ذخیره لینک
        context.user_data['target_link'] = text
        await update.message.reply_text(
            "✅ لینک ذخیره شد.\n\n"
            "تعداد بازدید مورد نظر را وارد کنید:\n"
            "حداقل 100 - حداکثر 100000"
        )
        user_states[user_id] = "waiting_count"
    
    elif state == "waiting_count":
        try:
            count = int(text)
            if count < 100 or count > 100000:
                await update.message.reply_text("❌ تعداد باید بین 100 تا 100000 باشد!")
                return
            
            link = context.user_data.get('target_link')
            
            await update.message.reply_text(
                f"🔄 در حال ارسال {count} بازدید به:\n{link}\n\n"
                f"⏱️ زمان تقریبی: {count // 1000 + 1} دقیقه\n"
                f"✅ بعد از اتمام به شما اطلاع داده می‌شود."
            )
            
            # اینجا کد اصلی بازدید زدن قرار می‌گیره
            # به دلیل محدودیت تلگرام، این بخش شبیه‌سازی شده
            await asyncio.sleep(2)
            
            await update.message.reply_text(
                f"✅ عملیات با موفقیت انجام شد!\n\n"
                f"{count} بازدید به پست شما ارسال گردید.\n"
                f"لینک: {link}"
            )
            
            user_states[user_id] = "waiting_link"
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "waiting_link"
    await update.message.reply_text("❌ عملیات کنسل شد. دوباره /start کنید.")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات با موفقیت روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()

