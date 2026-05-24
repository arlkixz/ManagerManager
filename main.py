import os
import asyncio
import logging
import random
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai
import json

# ========== گرفتن کلیدها ==========
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELETHON_STRING = os.getenv("TELETHON_STRING")  # این مهمترین قسمت است

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ========== راه‌اندازی کلاینت با StringSession ==========
# ✅ این خط کلید حل مشکل است
user_client = TelegramClient(StringSession(TELETHON_STRING), API_ID, API_HASH)

# بات مدیریت
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ========== تنظیمات ==========
SETTINGS_FILE = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "persona_base_instructions": "تو یه آدم واقعی هستی، خودمانی و صمیمی صحبت کن، هیچوقت نگو ربات هستی.",
        "response_chance": 70,
        "enabled_chats": [],
        "blacklist_chats": []
    }

settings = load_settings()

# ========== پاسخ با هوش مصنوعی ==========
async def get_ai_response(message_text):
    try:
        prompt = f"{settings['persona_base_instructions']}\n\nپیام: {message_text}\n\nجواب بده (فقط متن جواب):"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"خطا: {e}")
        return None

# ========== گوش دادن به پیام‌ها ==========
@user_client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    try:
        if event.sender_id == (await user_client.get_me()).id:
            return
        
        msg = event.message.text
        if not msg:
            return
        
        chat_id = event.chat_id
        
        # چک کردن لیست سیاه
        if chat_id in settings.get('blacklist_chats', []):
            return
        
        # شانس پاسخ در گروه
        if event.is_group and random.randint(1, 100) > settings.get('response_chance', 70):
            return
        
        response = await get_ai_response(msg)
        if response:
            await asyncio.sleep(random.uniform(1, 2))
            await user_client.send_message(chat_id, response)
            logging.info(f"پاسخ به {chat_id}: {response[:50]}")
    except Exception as e:
        logging.error(f"خطا: {e}")

# ========== منوی بات ==========
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ دسترسی ندارید")
        return
    await message.reply("🤖 ربات فعال است!")

# ========== اجرای اصلی ==========
async def main():
    logging.info("🚀 در حال اتصال...")
    
    # اتصال با StringSession (بدون نیاز به کد)
    await user_client.start()
    logging.info("✅ اکانت شخصی متصل شد")
    
    # اطلاعات اکانت رو چاپ کن تا مطمئن شوی
    me = await user_client.get_me()
    logging.info(f"👤 وارد شدی به عنوان: {me.first_name} ({me.phone_number})")
    
    # اجرای بات
    from aiogram.utils.executor import start_webhook
    
    PORT = int(os.getenv("PORT", 8080))
    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost')}{WEBHOOK_PATH}"
    
    await bot.set_webhook(WEBHOOK_URL)
    
    await asyncio.gather(
        user_client.run_until_disconnected(),
        start_webhook(dispatcher=dp, webhook_path=WEBHOOK_PATH, bot=bot, host="0.0.0.0", port=PORT)
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
