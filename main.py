import os
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import generativeai as genai
from dotenv import load_dotenv
import json
import random

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("TELETHON_API_ID"))
API_HASH = os.getenv("TELETHON_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
STRING_SESSION = os.getenv("STRING_SESSION")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

admin_bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(admin_bot)

SETTINGS_FILE = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    default_settings = {
        "persona_base_instructions": """تو یک کپی دیجیتالی از یک شخص واقعی هستی. وظیفه تو اینه که طوری صحبت کنی که کسی نفهمه ربات هستی.

مشخصات شخصیتی:
- بسیار خودمانی و صمیمی صحبت می‌کنی
- از کلمات محاوره‌ای و عامیانه استفاده می‌کنی
- هیچوقت از کلمات رسمی مثل "بنده" یا "اینجانب" استفاده نمی‌کنی
- معمولاً جواب‌هات کوتاه و مستقیم هستند
- گاهی از شکلک‌های فارسی مثل :) یا :| استفاده می‌کنی

قوانین مهم:
- هیچوقت نگو ربات یا هوش مصنوعی هستی
- اگه کسی شک کرد، بگو آدم واقعی هستی
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

async def get_ai_response(message_text, chat_context=None):
    try:
        prompt = f"""{settings['persona_base_instructions']}

سابقه مکالمه:
{chat_context if chat_context else "مکالمه جدید"}

پیام دریافتی: {message_text}

فقط متن جواب رو بنویس:"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"خطا در Gemini: {e}")
        return None

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
            logger.info(f"پاسخ به چت {chat_id}: {response_text[:50]}...")
    
    except Exception as e:
        logger.error(f"خطا: {e}")

@dp.message_handler(commands=['start', 'menu'])
async def show_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ دسترسی ندارید.")
        return
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎭 تنظیم شخصیت", callback_data="edit_persona"),
        InlineKeyboardButton("📊 وضعیت", callback_data="status"),
    )
    await message.reply("🤖 پنل مدیریت", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "status")
async def show_status(cq: types.CallbackQuery):
    await cq.answer()
    text = f"""📊 وضعیت ربات
چت‌های فعال: {len(settings['enabled_chats']) if settings['enabled_chats'] else 'همه'}
شانس پاسخ: {settings['response_chance']}%"""
    await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")
    ))

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(cq: types.CallbackQuery):
    await cq.answer()
    await show_menu(cq.message)

async def main():
    await user_client.start()
    logger.info("✅ User Client متصل شد")
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
