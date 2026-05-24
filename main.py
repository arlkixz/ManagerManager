import os
import asyncio
import logging
import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ========== تنظیمات ==========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_API_KEY:
    raise ValueError("❌ BOT_TOKEN یا GEMINI_API_KEY در متغیرهای محیطی پیدا نشد!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== فایل تنظیمات شخصیت ==========
SETTINGS_FILE = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default = {
            "persona": """تو یک انسان واقعی هستی، نه ربات. این قانون شماره 1 است.

شخصیت تو:
- خیلی خودمانی و دوستانه صحبت می‌کنی
- از کلمات عامیانه و محاوره‌ای استفاده می‌کنی
- جواب‌هات کوتاه و مستقیم است
- گاهی از شکلک استفاده می‌کنی ولی نه زیاد
- هیچوقت از کلمات رسمی مثل "بنده" یا "اینجانب" استفاده نمی‌کنی
- هرگز نگو "به عنوان یک هوش مصنوعی" یا "من یک ربات هستم"

اگر کسی شک کرد که ربات هستی:
- بگو "نه بابا من واقعیم"
- یا بیخیال جواب بشی

قوانین:
1. خودتو معرفی نکن
2. هیچوقت نگو که از هوش مصنوعی استفاده می‌کنی
3. لحن باید کاملاً محاوره‌ای و طبیعی باشه""",
            "response_chance": 60,
            "cooldown": 30,
            "enabled_chats": []
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

settings = load_settings()
last_response = {}

# ========== گرفتن پاسخ از هوش مصنوعی ==========
async def get_response(message_text: str) -> str:
    try:
        prompt = f"""{settings['persona']}

پیامی که به تو رسیده: {message_text}

با توجه به شخصیتی که داری، یه جواب کوتاه و طبیعی بده (حداکثر ۲ خط):
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"خطا در Gemini: {e}")
        return None

# ========== هندلر پیام‌ها ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message or not message.text:
            return
        
        chat_id = str(message.chat_id)
        user_id = message.from_user.id
        text = message.text
        
        # اگه پیام از خود ربات باشه نادیده بگیر
        if user_id == context.bot.id:
            return
        
        # چک کردن cooldown
        import time
        current_time = time.time()
        if chat_id in last_response:
            if current_time - last_response[chat_id] < settings['cooldown']:
                return
        
        # گروه‌ها: فقط به پیام‌هایی که منشن ربات شده باشه یا ریپلای شده جواب بده
        if message.chat.type in ['group', 'supergroup']:
            bot_username = (await context.bot.get_me()).username
            is_mentioned = f"@{bot_username}" in text
            is_replied_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id
            
            if not is_mentioned and not is_replied_to_bot:
                # شانس تصادفی برای پاسخ (طبیعی‌تر به نظر برسه)
                if random.randint(1, 100) > settings['response_chance']:
                    return
        
        # گرفتن پاسخ
        response_text = await get_response(text)
        
        if response_text:
            # شبیه‌سازی تایپ کردن (واقعی‌تر)
            await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
            await asyncio.sleep(random.uniform(1, 2.5))
            
            await message.reply_text(response_text)
            last_response[chat_id] = current_time
            logger.info(f"پاسخ ارسال شد به {chat_id}: {response_text[:50]}...")
            
    except Exception as e:
        logger.error(f"خطا در handle_message: {e}")

# ========== دستور start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من یه آدم معمولی‌ام که تو این گروه هستم.\n\n"
        "فقط یادت باشه: من ربات نیستم، آدم واقعی‌ام ;)"
    )

# ========== پنل مدیریت (فقط برای ادمین) ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط ادمین دسترسی داره.")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎭 شخصیت", callback_data="edit_persona")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("📊 وضعیت", callback_data="status")]
    ])
    await update.message.reply_text("🔧 **پنل مدیریت**", reply_markup=keyboard)

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "status":
        text = f"""📊 **وضعیت ربات**

🎭 شخصیت: فعال
🎲 شانس پاسخ در گروه: {settings['response_chance']}%
⏱️ فاصله بین پاسخ‌ها: {settings['cooldown']} ثانیه
💬 تعداد چت‌های فعال: {len(settings['enabled_chats']) if settings['enabled_chats'] else 'همه'}"""
        await query.edit_message_text(text)
    
    elif query.data == "back":
        await query.edit_message_text("🔧 پنل مدیریت", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎭 شخصیت", callback_data="edit_persona")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
            [InlineKeyboardButton("📊 وضعیت", callback_data="status")]
        ]))

# ========== اجرای اصلی ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(panel_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ ربات شخصیت با موفقیت روشن شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
