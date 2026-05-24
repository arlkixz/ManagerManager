import os
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import google.generativeai as genai
import json
import random
from datetime import datetime

# ========== گرفتن کلیدها از Environment Variables ==========
API_ID = int(os.getenv("API_ID"))                    # اصلاح شد
API_HASH = os.getenv("API_HASH")                      # اصلاح شد
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELETHON_STRING = os.getenv("TELETHON_STRING")        # اضافه شد - همین جا ذخیره کن

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ========== راه‌اندازی کلاینت‌ها ==========
# ✅ استفاده از StringSession به جای فایل - این دیگه کد نمیخواد
user_client = TelegramClient(StringSession(TELETHON_STRING), API_ID, API_HASH)

# Aiogram برای بات مدیریت
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ========== تنظیمات شخصیت ==========
SETTINGS_FILE = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_settings = {
            "persona_base_instructions": """تو یک کپی دیجیتالی از یک شخص واقعی هستی. وظیفه تو اینه که طوری صحبت کنی که کسی نفهمه ربات هستی.

مشخصات شخصیتی:
- بسیار خودمانی و صمیمی صحبت می‌کنی
- از کلمات محاوره‌ای و عامیانه استفاده می‌کنی
- هیچوقت از کلمات رسمی مثل "بنده" یا "اینجانب" استفاده نمی‌کنی
- معمولاً جواب‌هات کوتاه و مستقیم هستند
- گاهی از شکلک‌های فارسی مثل :) یا :| استفاده می‌کنی
- لحن صحبتت خودمانی و دوستانه‌ست

قوانین مهم:
- هیچوقت و تحت هیچ شرایطی به کسی نگو که ربات یا هوش مصنوعی هستی
- اگه کسی شک کرد، بگو آدم واقعی هستی
- به سوالاتی که جوابشون رو نمی‌دونی، بگو "نمی‌دونم والا" یا "خبر ندارم"
- هیچوقت جواب طولانی و کتابی نده""",
            "response_chance": 70,
            "enabled_chats": [],
            "blacklist_chats": [],
            "cooldown_seconds": 60
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4, ensure_ascii=False)
        return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

settings = load_settings()

# ========== مدیریت پاسخ با هوش مصنوعی ==========
async def get_ai_response(message_text, chat_context=None):
    try:
        prompt = f"""{settings['persona_base_instructions']}

سابقه مکالمه (برای درک بهتر متن):
{chat_context if chat_context else "مکالمه جدید"}

پیام دریافتی: {message_text}

با توجه به شخصیتی که داری، به این پیام جواب بده (فقط متن جواب رو بنویس، بدون توضیح اضافه):"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"خطا در دریافت پاسخ از Gemini: {e}")
        return None

# ========== لیسنر برای پیام‌های جدید ==========
@user_client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    try:
        if event.sender_id == (await user_client.get_me()).id:
            return
        
        chat_id = event.chat_id
        message_text = event.message.text
        
        if not message_text:
            return
        
        if settings['blacklist_chats'] and chat_id in settings['blacklist_chats']:
            return
        
        if settings['enabled_chats'] and chat_id not in settings['enabled_chats']:
            return
        
        if event.is_group:
            if random.randint(1, 100) > settings['response_chance']:
                return
        
        response_text = await get_ai_response(message_text)
        
        if response_text:
            async with user_client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 3))
            
            await user_client.send_message(chat_id, response_text)
            logging.info(f"پاسخ ارسال شد به چت {chat_id}: {response_text[:50]}...")
    
    except Exception as e:
        logging.error(f"خطا در هندلر پیام: {e}")

# ========== بات مدیریت ==========
@dp.message_handler(commands=['start', 'menu'])
async def show_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ شما دسترسی به این بات ندارید.")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎭 تنظیم شخصیت", callback_data="edit_persona"),
        InlineKeyboardButton("📊 وضعیت", callback_data="status"),
        InlineKeyboardButton("⚙️ تنظیمات عمومی", callback_data="general_settings"),
        InlineKeyboardButton("➕ اضافه کردن چت", callback_data="add_chat"),
        InlineKeyboardButton("❌ حذف چت", callback_data="remove_chat")
    )
    
    await message.reply("🤖 **پنل مدیریت ربات شخصیت**\n\nاز دکمه‌های زیر برای تنظیمات استفاده کن:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "status")
async def show_status(callback_query: types.CallbackQuery):
    await callback_query.answer()
    
    status_text = f"""📊 **وضعیت ربات**

🎭 شخصیت: فعال
📝 چت‌های فعال: {len(settings['enabled_chats']) if settings['enabled_chats'] else 'همه'}
🚫 چت‌های مسدود: {len(settings['blacklist_chats'])}
🎲 شانس پاسخ در گروه: {settings['response_chance']}%
⏱️ فاصله بین پاسخ‌ها: {settings['cooldown_seconds']} ثانیه"""
    
    await callback_query.message.edit_text(status_text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")
    ))

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await show_menu(callback_query.message)

# ========== اجرای اصلی ==========
async def main():
    # استارت کردن User Client با StringSession (بدون کد)
    await user_client.start()
    logging.info("✅ User Client (اکانت شخصی) با StringSession متصل شد")
    
    # استارت کردن Webhook برای Aiogram (سازگار با Railway)
    from aiogram.utils.executor import start_webhook
    
    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost')}{WEBHOOK_PATH}"
    
    await bot.set_webhook(WEBHOOK_URL)
    
    logging.info(f"✅ Webhook تنظیم شد: {WEBHOOK_URL}")
    
    # اجرای همزمان Telethon listener و Aiogram webhook
    await asyncio.gather(
        user_client.run_until_disconnected(),
        start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            bot=bot,
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8080))
        )
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
