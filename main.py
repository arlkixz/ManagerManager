#!/usr/bin/env python3
import asyncio
import logging
import re
import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, BotCommand
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 6387049405))

# دیتابیس ساده با دیکشنری (بدون فایل)
settings_db = {}

def get_setting(chat_id, key, default=1):
    return settings_db.get((chat_id, key), default)

def set_setting(chat_id, key, value):
    settings_db[(chat_id, key)] = value

SPAM_KEYWORDS = ["join", "fast", "سایت", "🔞", "💰", "کلیک", "عضویت"]
FORBIDDEN_DOMAINS = ["bit.ly", "tinyurl.com", "t.me/+"]
BAD_WORDS = ["احمق", "خر", "گاو", "کودن", "نادان", "بی‌شعور", "ابله", "حیوان", "مادرجنده", "کصکش", "کیر", "کون", "جنده", "الاغ"]

warnings = {}

async def reply_msg(update, text, context, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    try:
        return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Reply error: {e}")
        return None

async def is_admin(update, context):
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

def get_target_user(update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

async def lock_cmd(update, context):
    if not await is_admin(update, context):
        await reply_msg(update, "❌ فقط ادمین‌ها!", context)
        return
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, ChatPermissions(can_send_messages=False))
        await reply_msg(update, "🔒 گروه قفل شد! فقط ادمین‌ها می‌تونن پیام بدن.", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def unlock_cmd(update, context):
    if not await is_admin(update, context):
        await reply_msg(update, "❌ فقط ادمین‌ها!", context)
        return
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, ChatPermissions(can_send_messages=True, can_send_other_messages=True, can_add_web_page_previews=True, can_send_polls=True))
        await reply_msg(update, "🔓 گروه باز شد! همه می‌تونن پیام بدن.", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def ban_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = get_target_user(update)
    if not target:
        await reply_msg(update, "❌ روی پیام کاربر reply کن یا ID بده", context)
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await reply_msg(update, f"🚫 {target.first_name} بن شد!", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def unban_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = get_target_user(update)
    if not target:
        await reply_msg(update, "❌ روی پیام کاربر reply کن یا ID بده", context)
        return
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await reply_msg(update, f"✅ {target.first_name} آنبن شد!", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def mute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = get_target_user(update)
    if not target:
        await reply_msg(update, "❌ روی پیام کاربر reply کن\nمثال: /mute 1h", context)
        return
    duration = context.args[0] if context.args else None
    try:
        if duration:
            match = re.match(r"(\d+)([smhd])", duration)
            if match:
                val, unit = int(match.group(1)), match.group(2)
                units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
                seconds = val * units.get(unit, 1)
                until = datetime.now() + timedelta(seconds=seconds)
                await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
                await reply_msg(update, f"🔇 {target.first_name} میوت شد برای {duration}!", context)
            else:
                await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False))
                await reply_msg(update, f"🔇 {target.first_name} میوت دائمی شد!", context)
        else:
            await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False))
            await reply_msg(update, f"🔇 {target.first_name} میوت دائمی شد!", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def unmute_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = get_target_user(update)
    if not target:
        await reply_msg(update, "❌ روی پیام کاربر reply کن", context)
        return
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        await reply_msg(update, f"🔊 {target.first_name} آنمیوت شد!", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def kick_cmd(update, context):
    if not await is_admin(update, context):
        return
    target = get_target_user(update)
    if not target:
        await reply_msg(update, "❌ روی پیام کاربر reply کن", context)
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await reply_msg(update, f"👢 {target.first_name} کیک شد!", context)
    except Exception as e:
        await reply_msg(update, f"❌ خطا: {e}", context)

async def purge_cmd(update, context):
    if not await is_admin(update, context):
        await reply_msg(update, "❌ فقط ادمین‌ها!", context)
        return
    chat_id = update.effective_chat.id
    current = update.message.message_id
    deleted = 0
    await reply_msg(update, "🧹 در حال پاکسازی...", context)
    for msg_id in range(current, max(current - 200, 1), -1):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted += 1
        except:
            pass
        await asyncio.sleep(0.05)
    await reply_msg(update, f"✅ پاکسازی تموم شد! {deleted} پیام حذف شد.", context)

async def purge_user_cmd(update, context):
    if not await is_admin(update, context):
        await reply_msg(update, "❌ فقط ادمین‌ها!", context)
        return
    if not update.message.reply_to_message:
        await reply_msg(update, "❌ روی پیام کاربر reply کن", context)
        return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    current = update.message.message_id
    deleted = 0
    for msg_id in range(current, max(current - 200, 1), -1):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted += 1
        except:
            pass
        await asyncio.sleep(0.05)
    await reply_msg(update, f"✅ {deleted} پیام از {target.first_name} حذف شد.", context)

async def start_cmd(update, context):
    buttons = [
        [InlineKeyboardButton("📋 راهنما", callback_data="menu_help")],
    ]
    await reply_msg(update, "🤖 **ربات مدیریت گروه یاشا**\n\nاز منوی زیر استفاده کن:", context, reply_markup=InlineKeyboardMarkup(buttons))

async def help_cmd(update, context):
    text = """
📋 **راهنمای ربات یاشا**

👮 دستورات مدیریتی:
/lock - قفل گروه
/unlock - باز کردن گروه
/ban - بن کاربر
/unban - آنبن کاربر
/mute - میوت کاربر
/unmute - آنمیوت کاربر
/kick - کیک کاربر

🧹 پاکسازی:
/purge - پاک کردن پیام‌ها
/purgeuser - پاک کردن پیام‌های کاربر

⚙️ عمومی:
/start - منوی اصلی
/help - راهنما
"""
    await reply_msg(update, text, context)

async def menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "menu_help":
        text = "/lock - قفل گروه\n/unlock - باز کردن گروه\n/ban - بن کاربر\n/unban - آنبن کاربر\n/mute - میوت کاربر\n/unmute - آنمیوت کاربر\n/kick - کیک کاربر\n/purge - پاکسازی پیام‌ها"
        await query.edit_message_text(text)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("kick", kick_cmd))
    app.add_handler(CommandHandler("purge", purge_cmd))
    app.add_handler(CommandHandler("purgeuser", purge_user_cmd))
    
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_)"))
    
    logger.info("ربات یاشا شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
