import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import google.generativeai as genai
import json

# ========== گرفتن کلیدها ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ========== راه‌اندازی ربات ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ========== تنظیمات شخصیت ==========
PERSONA = """تو یک کپی دیجیتالی از یک شخص واقعی هستی. طوری صحبت کن که کسی نفهمه ربات هستی.
- خودمانی و صمیمی صحبت کن
- از کلمات محاوره‌ای استفاده کن
- جواب‌هات کوتاه و مستقیم باشه
- هیچوقت نگو که ربات یا هوش مصنوعی هستی"""

# ========== پاسخ با هوش مصنوعی ==========
async def get_ai_response(message_text):
    try:
        prompt = f"{PERSONA}\n\nپیام کاربر: {message_text}\n\nجواب بده (فقط متن جواب، بدون توضیح اضافه):"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"خطا: {e}")
        return "چی بگم والا... نمی‌دونم."

# ========== هندلر پیام‌ها ==========
@dp.message_handler()
async def handle_message(message: types.Message):
    # فقط به پیام‌های خصوصی جواب بده
    if message.chat.type != "private":
        return
    
    # اگه می‌خوای فقط ادمین جواب بده، این خط رو فعال کن
    # if message.from_user.id != ADMIN_ID:
    #     await message.reply("⛔ دسترسی نداری")
    #     return
    
    # شبیه‌سازی تایپ کردن
    await bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(random.uniform(1, 2))
    
    # گرفتن پاسخ
    response = await get_ai_response(message.text)
    
    # ارسال پاسخ
    await message.reply(response)

# ========== منوی استارت ==========
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply("🤖 سلام! من فعال هستم. هر سوالی داری بپرس.")

# ========== اجرا (برای Railway) ==========
async def main():
    logging.info("🚀 ربات در حال راه‌اندازی...")
    
    # برای Railway از Webhook استفاده می‌کنیم
    from aiogram.utils.executor import start_webhook
    
    PORT = int(os.getenv("PORT", 8080))
    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost')}{WEBHOOK_PATH}"
    
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook تنظیم شد: {WEBHOOK_URL}")
    
    # اجرا
    await start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        bot=bot,
        host="0.0.0.0",
        port=PORT
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
