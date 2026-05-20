#!/usr/bin/env python3
import asyncio
import logging
import re
import os
from datetime import datetime, timedelta

from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import DeleteMessagesRequest
from telethon.tl.types import ChatBannedRights, MessageEntityCustomEmoji
from telethon.errors import UserNotParticipantError

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 6387049405))
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "https://t.me/dontworry80")
FORCE_SUB_USERNAME = os.getenv("FORCE_SUB_USERNAME", "@dontworry80")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("API_ID, API_HASH, BOT_TOKEN must be set!")

PREMIUM_EMOJIS = {
    "lock": ("🔒", "5377688663960331522"),
    "unlock": ("🔓", "5377855630813964361"),
    "ban": ("🚫", "5379995211722138153"),
    "mute": ("🔇", "5370897968478047651"),
    "kick": ("👢", "5379995211722138153"),
    "success": ("✅", "5208880351690112495"),
}

def get_emoji_len(emoji: str) -> int:
    return len(emoji.encode("utf-16-le")) // 2

async def send_with_emoji(event, text, emoji_key, buttons=None):
    emoji_char, emoji_id = PREMIUM_EMOJIS.get(emoji_key, ("✅", "5208880351690112495"))
    entities = [MessageEntityCustomEmoji(offset=0, length=get_emoji_len(emoji_char), custom_emoji_id=emoji_id)]
    await event.reply(f"{emoji_char} {text}", buttons=buttons, formatting_entities=entities)

bot = TelegramClient("yasha_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def check_force_sub(user_id):
    try:
        await bot.get_permissions(FORCE_SUB_USERNAME, user_id)
        return True
    except UserNotParticipantError:
        return False
    except:
        return True

async def is_admin(event):
    if event.sender_id == ADMIN_USER_ID:
        return True
    try:
        sender = await event.get_sender()
        permissions = await bot.get_permissions(event.chat_id, sender)
        return permissions.is_admin or permissions.is_creator
    except:
        return False

def get_target(event):
    if event.reply_to_msg_id:
        msg = await event.get_reply_message()
        return msg.sender_id if msg else None
    if event.raw_text and len(event.raw_text.split()) > 1:
        try:
            return int(event.raw_text.split()[1])
        except:
            return None
    return None

@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    if not await check_force_sub(event.sender_id):
        buttons = [[Button.url("📢 عضویت در کانال", FORCE_SUB_CHANNEL)], [Button.inline("🔄 بررسی عضویت", b"check_sub")]]
        await event.reply(f"🔒 برای استفاده از ربات باید عضو کانال {FORCE_SUB_USERNAME} بشی:", buttons=buttons)
        return
    
    buttons = [
        [Button.inline("📋 راهنما", b"menu_help")],
        [Button.inline("⚙️ تنظیمات", b"menu_settings")],
        [Button.url("📢 کانال ما", FORCE_SUB_CHANNEL)],
    ]
    await send_with_emoji(event, "ربات مدیریت گروه یاشا\n\nاز منوی زیر استفاده کن:", "unlock", buttons)

@bot.on(events.NewMessage(pattern="/help"))
async def help_cmd(event):
    text = """📋 راهنمای ربات یاشا

👮 دستورات مدیریتی:
/lock - قفل گروه
/unlock - باز کردن گروه
/ban - بن کاربر
/unban - آنبن کاربر
/mute - میوت کاربر
/unmute - آنمیوت کاربر
/kick - کیک کاربر

🧹 دستورات پاکسازی:
/purge - پاک کردن پیام‌ها
/purgeuser - پاک کردن پیام‌های کاربر

⚙️ دستورات عمومی:
/start - منوی اصلی
/help - راهنما
/join - بررسی عضویت"""
    await event.reply(text)

@bot.on(events.NewMessage(pattern="/lock"))
async def lock_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    rights = ChatBannedRights(until_date=None, send_messages=True, send_media=True, send_stickers=True, send_gifs=True)
    await bot(EditBannedRequest(event.chat_id, 0, rights))
    await send_with_emoji(event, "گروه قفل شد! فقط ادمین‌ها می‌تونن پیام بدن.", "lock")

@bot.on(events.NewMessage(pattern="/unlock"))
async def unlock_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    rights = ChatBannedRights(until_date=None)
    await bot(EditBannedRequest(event.chat_id, 0, rights))
    await send_with_emoji(event, "گروه باز شد! همه می‌تونن پیام بدن.", "unlock")

@bot.on(events.NewMessage(pattern="/ban ?(.*)"))
async def ban_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    target_id = get_target(event)
    if not target_id:
        return await event.reply("❌ روی پیام کاربر reply کن یا ID بده")
    
    try:
        rights = ChatBannedRights(until_date=None, view_messages=True)
        await bot(EditBannedRequest(event.chat_id, target_id, rights))
        await send_with_emoji(event, f"کاربر {target_id} بن شد!", "ban")
    except Exception as e:
        await event.reply(f"❌ خطا: {e}")

@bot.on(events.NewMessage(pattern="/unban ?(.*)"))
async def unban_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    target_id = get_target(event)
    if not target_id:
        return await event.reply("❌ روی پیام کاربر reply کن یا ID بده")
    
    try:
        rights = ChatBannedRights(until_date=None)
        await bot(EditBannedRequest(event.chat_id, target_id, rights))
        await send_with_emoji(event, f"کاربر {target_id} آنبن شد!", "success")
    except Exception as e:
        await event.reply(f"❌ خطا: {e}")

@bot.on(events.NewMessage(pattern="/mute ?(.*)"))
async def mute_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    target_id = get_target(event)
    if not target_id:
        return await event.reply("❌ روی پیام کاربر reply کن یا ID بده")
    
    parts = event.raw_text.split()
    duration_str = parts[1] if len(parts) > 1 else None
    
    seconds = 0
    if duration_str:
        match = re.match(r"(\d+)([smhd])", duration_str)
        if match:
            val, unit = int(match.group(1)), match.group(2)
            units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            seconds = val * units.get(unit, 1)
    
    until = datetime.now() + timedelta(seconds=seconds) if seconds else None
    rights = ChatBannedRights(until_date=until, send_messages=True)
    await bot(EditBannedRequest(event.chat_id, target_id, rights))
    
    time_text = f" برای {duration_str}" if seconds else " دائمی"
    await send_with_emoji(event, f"کاربر {target_id} میوت شد{time_text}!", "mute")

@bot.on(events.NewMessage(pattern="/unmute ?(.*)"))
async def unmute_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    target_id = get_target(event)
    if not target_id:
        return await event.reply("❌ روی پیام کاربر reply کن یا ID بده")
    
    try:
        rights = ChatBannedRights(until_date=None)
        await bot(EditBannedRequest(event.chat_id, target_id, rights))
        await send_with_emoji(event, f"کاربر {target_id} آنمیوت شد!", "success")
    except Exception as e:
        await event.reply(f"❌ خطا: {e}")

@bot.on(events.NewMessage(pattern="/kick ?(.*)"))
async def kick_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    target_id = get_target(event)
    if not target_id:
        return await event.reply("❌ روی پیام کاربر reply کن یا ID بده")
    
    try:
        await bot.kick_participant(event.chat_id, target_id)
        await send_with_emoji(event, f"کاربر {target_id} کیک شد!", "kick")
    except Exception as e:
        await event.reply(f"❌ خطا: {e}")

@bot.on(events.NewMessage(pattern="/purge"))
async def purge_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    
    chat_id = event.chat_id
    msg_ids = []
    async for msg in bot.iter_messages(chat_id, limit=100):
        msg_ids.append(msg.id)
    
    if msg_ids:
        await bot(DeleteMessagesRequest(chat_id, msg_ids))
        await send_with_emoji(event, f"{len(msg_ids)} پیام حذف شد!", "success")
    else:
        await event.reply("هیچ پیامی برای حذف وجود ندارد.")

@bot.on(events.NewMessage(pattern="/purgeuser"))
async def purge_user_cmd(event):
    if not event.is_group:
        return await event.reply("❌ این دستور فقط در گروه کار می‌کند.")
    if not await is_admin(event):
        return await event.reply("❌ فقط ادمین‌ها!")
    if not event.reply_to_msg_id:
        return await event.reply("❌ روی پیام کاربر reply کن")
    
    target = await event.get_reply_message()
    target_id = target.sender_id
    
    chat_id = event.chat_id
    msg_ids = []
    async for msg in bot.iter_messages(chat_id, from_user=target_id, limit=100):
        msg_ids.append(msg.id)
    
    if msg_ids:
        await bot(DeleteMessagesRequest(chat_id, msg_ids))
        await event.reply(f"✅ {len(msg_ids)} پیام از کاربر {target_id} حذف شد.")
    else:
        await event.reply("هیچ پیامی از این کاربر یافت نشد.")

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data
    if data == b"check_sub":
        if await check_force_sub(event.sender_id):
            await event.edit("✅ عضویت تأیید شد! حالا می‌تونی از ربات استفاده کنی.")
        else:
            await event.answer("❌ هنوز عضو نشدی!", alert=True)
    elif data == b"menu_help":
        await event.edit("📋 راهنمای ربات یاشا\n\n/lock - قفل گروه\n/unlock - باز کردن گروه\n/ban - بن کاربر\n/unban - آنبن کاربر\n/mute - میوت کاربر\n/unmute - آنمیوت کاربر\n/kick - کیک کاربر\n/purge - پاکسازی پیام‌ها")
    elif data == b"menu_settings":
        await event.edit("⚙️ تنظیمات گروه - به زودی اضافه می‌شود.")

@bot.on(events.NewMessage(pattern="/join"))
async def join_cmd(event):
    if await check_force_sub(event.sender_id):
        await event.reply("✅ عضویت شما تأیید شد!")
    else:
        buttons = [[Button.url("📢 عضویت در کانال", FORCE_SUB_CHANNEL)], [Button.inline("🔄 بررسی عضویت", b"check_sub")]]
        await event.reply(f"🔒 ابتدا عضو کانال {FORCE_SUB_USERNAME} بشو:", buttons=buttons)

async def main():
    logger.info("ربات پیشرفته یاشا با Telethon روشن شد!")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
