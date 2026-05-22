import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus

# راه‌اندازی لاگ
logging.basicConfig(level=logging.INFO)

# متغیرها از Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "")  # یوزرنیم کانال بدون @
WELCOME_MSG = os.environ.get("WELCOME_MSG", "به گروه خوش اومدی! 🎉")
WELCOME_NOT_JOINED = os.environ.get("WELCOME_NOT_JOINED", "❗ برای استفاده از ربات، اول عضو کانال ما شو.")

app = Client("forcesub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# تابع بررسی عضویت در کانال
async def is_subscribed(user_id):
    try:
        member = await app.get_chat_member(CHANNEL, user_id)
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return True
        return False
    except:
        return False

# دستور استارت
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    if await is_subscribed(user_id):
        await message.reply_text(
            f"سلام {first_name}! {WELCOME_MSG}\n\n"
            "🎯 می‌تونی از ربات استفاده کنی.\n"
            "📋 برای دیدن راهنما /help رو بزن.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL}")
            ]])
        )
    else:
        await message.reply_text(
            f"سلام {first_name}!\n\n{WELCOME_NOT_JOINED}\n\n"
            f"🔗 لطفاً اول عضو کانال {CHANNEL} بشو، بعد دوباره /start رو بزن.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL}")
            ]])
        )

# دستور راهنما
@app.on_message(filters.command("help"))
async def help_command(client, message):
    user_id = message.from_user.id
    
    if await is_subscribed(user_id):
        await message.reply_text(
            "📋 **راهنمای ربات**\n\n"
            "/start - شروع کار با ربات\n"
            "/help - همین راهنما\n"
            "/info - اطلاعات کاربری\n\n"
            "🔗 برای استفاده از ربات، باید عضو کانال ما باشی.",
            disable_web_page_preview=True
        )
    else:
        await message.reply_text(
            f"❗ ابتدا عضو کانال {CHANNEL} بشو.\n"
            f"بعد از عضویت، دوباره /start رو بزن.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL}")
            ]])
        )

# دستور اطلاعات کاربر
@app.on_message(filters.command("info"))
async def info_command(client, message):
    user_id = message.from_user.id
    
    if await is_subscribed(user_id):
        user = message.from_user
        await message.reply_text(
            f"📌 **اطلاعات شما**\n\n"
            f"👤 نام: {user.first_name}\n"
            f"🆔 آیدی: `{user.id}`\n"
            f"📛 یوزرنیم: @{user.username if user.username else 'ندارد'}\n"
            f"✅ وضعیت عضویت: عضو کانال هستی",
            parse_mode="markdown"
        )
    else:
        await message.reply_text(
            f"❗ ابتدا عضو کانال {CHANNEL} بشو.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL}")
            ]])
        )

# بررسی پیام‌های عادی (اختیاری)
@app.on_message(filters.text & ~filters.command(["start", "help", "info"]))
async def normal_message(client, message):
    user_id = message.from_user.id
    
    if not await is_subscribed(user_id):
        await message.reply_text(
            f"❗ شما عضو کانال {CHANNEL} نیستی.\n"
            f"لطفاً اول عضو بشو، بعد پیام بفرست.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL}")
            ]])
        )

# بررسی کاربران جدید در گروه
@app.on_chat_member_updated()
async def on_member_join(client, chat_member_updated):
    if chat_member_updated.new_chat_member:
        user_id = chat_member_updated.from_user.id
        
        if not await is_subscribed(user_id):
            try:
                await app.restrict_chat_member(
                    chat_member_updated.chat.id,
                    user_id,
                    privileges=None  # میوت کامل
                )
                await app.send_message(
                    chat_member_updated.chat.id,
                    f"❗ {chat_member_updated.from_user.first_name} عزیز، تو گروه میوت شدی.\n"
                    f"برای آزاد شدن، اول عضو کانال {CHANNEL} بشو.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL}")
                    ]])
                )
            except:
                pass

# استارت ربات
print("🤖 ربات عضویت اجباری روشن شد!")
app.run()
