import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import google.generativeai as genai

# ========== گرفتن کلیدها ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ========== راه‌اندازی ربات ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ========== شخصیت ربات ==========
PERSONA = """تو یه دوست صمیمی و خودمانی هستی که داره با یه نفر چت می‌کنه.
- کوتاه و مستقیم جواب بده
- از کلمات محاوره‌ای استفاده کن
- هیچوقت نگو که ربات یا هوش مصنوعی هستی
- اگه چیزی نمی‌دونی، بگو "نمی‌دونم والا"
- جواب‌هات بین 10 تا 50 کلمه باشه"""

# ========== گرفتن پاسخ از هوش مصنوعی ==========
async def get_ai_response(message_text):
    try:
        prompt = f"{PERSONA}\n\nپیام کاربر: {message_text}\n\nجواب بده (فقط متن جواب):"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"خطا: {e}")
        return "نتونستم جواب بدم، دوباره بپرس."

# ========== هندلر پیام‌ها ==========
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply("🤩 سلام! بپرس هر چی دوست داری.")

@dp.message_handler()
async def handle_message(message: types.Message):
    # فقط پیام‌های خصوصی
    if message.chat.type != "private":
        return
    
    # شبیه‌سازی تایپ کردن
    await bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(random.uniform(1, 2))
    
    # گرفتن پاسخ
    response = await get_ai_response(message.text)
    
    # ارسال پاسخ
    await message.reply(response)

# ========== اجرا با Polling (بدون Webhook) ==========
async def main():
    logging.info("🚀 ربات در حال روشن شدن...")
    
    # حذف webhook قبلی (اگه باشه)
    await bot.delete_webhook()
    
    # شروع Polling - این روش در Railway کار می‌کنه
    await dp.start_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
