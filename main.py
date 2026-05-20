#!/usr/bin/env python3
import asyncio
import logging
import re
import os
from datetime import datetime, timedelta

from database import init_db, get_setting, set_setting

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, BotCommand, MessageEntity
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
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "https://t.me/dontworry80")
FORCE_SUB_USERNAME = os.getenv("FORCE_SUB_USERNAME", "@dontworry80")

SPAM_KEYWORDS = ["join", "fast", "سایت", "🔞", "💰", "کلیک", "عضویت"]
FORBIDDEN_DOMAINS = ["bit.ly", "tinyurl.com", "t.me/+"]
BAD_WORDS = ["احمق", "خر", "گاو", "کودن", "نادان", "بی‌شعور", "ابله", "حیوان", "مادرجنده", "کصکش", "کیر", "کون", "جنده", "الاغ"]

warnings = {}

# ============================================
# توابع کمکی
# ============================================

def get_emoji_len(emoji: str) -> int:
    return len(emoji.encode('utf-16-le')) // 2

async def send_premium_emoji(chat_id, context, emoji_char, emoji_id, reply_to=None):
    entities = [MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=0, length=get_emoji_len(emoji_char), custom_emoji_id=emoji_id)]
    try:
        return await context.bot.send_message(chat_id=chat_id, text=emoji_char, entities=entities, reply_to_message_id=reply_to)
    except:
        return None

async def reply_msg(update, text, context, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    try:
        return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Reply error: {e}")
        return None

# ============================================
# عضویت اجباری
# ============================================

async def is_force_subscribed(user_id, context):
    return True  # فعلاً غیرفعال

async def force_sub_panel(update, context):
    await reply_msg(update, "✅ عضویت تأیید شد! به گروه خوش اومدی 🎉", context)

async def check_sub_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ عضویت تأیید شد!")

# ============================================
# ولکام و خداحافظی
# ============================================

welcome_counter = {}

async def welcome_member(update, context):
    if not update.message or not update.message.new_chat_members:
        return
    chat_id = update.effective_chat.id
    if not get_setting(chat_id, "welcome_enabled", 1):
        return
    if chat_id not in welcome_counter:
        welcome_counter[chat_id] = 0
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        welcome_counter[chat_id] += 1
        greeting = "خوش اومدی 🤗" if welcome_counter[chat_id] % 2 == 1 else "خوش اومدی 😊"
        text = f"👤 {member.first_name}\n🆔 {member.id}\n👋 {greeting}"
        await reply_msg(update, text, context)

async def goodbye_member(update, context):
    if not update.message or not update.message.left_chat_member:
        return
    chat_id = update.effective_chat.id
    if not get_setting(chat_id, "goodbye_enabled", 1):
        return
    member = update.message.left_chat_member
    text = f"😢 {member.first_name} از گروه خارج شد!"
    await reply_msg(update, text, context)

# ============================================
# آنتی اسپم و آنتی بدزبانی
# ============================================

async def anti_bad_words(update, context):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    msg_text = update.message.text.lower()
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except:
        pass
    for word in BAD_WORDS:
        if word in msg_text:
            key = (chat_id, user_id)
            warnings[key] = warnings.get(key, 0) + 1
            count = warnings[key]
            if count >= 5:
                try:
                    await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.now() + timedelta(hours=24))
                    await reply_msg(update, f"🔇 {update.effective_user.first_name} بعد از ۵ اخطار سکوت شد!", context)
                    warnings[key] = 0
                except:
                    pass
            else:
                await reply_msg(update, f"⚠️ {update.effective_user.first_name} اخطار {count}/5", context)
            await update.message.delete()
            return

async def anti_spam(update, context):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    msg_text = update.message.text.lower()
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except:
        pass
    if get_setting(chat_id, "delete_links", 1):
        for domain in FORBIDDEN_DOMAINS:
            if domain in msg_text:
                await update.message.delete()
                await reply_msg(update, f"⚠️ {update.effective_user.first_name} لینک ممنوع ارسال کرد!", context)
                return
    if get_setting(chat_id, "delete_spam", 1):
        for word in SPAM_KEYWORDS:
            if word in msg_text:
                await update.message.delete()
                return
    if get_setting(chat_id, "delete_stickers", 0) and update.message.sticker:
        await update.message.delete()
        return
    await anti_bad_words(update, context)

# ============================================
# بررسی ادمین
# ============================================

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

# ============================================
# دستورات مدیریتی
# ============================================

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
        await reply_msg(update, "❌ روی پیام کاربر reply کن", context)
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
        await reply_msg(update, "❌ روی پیام کاربر reply کن", context)
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

# ============================================
# تنظیمات
# ============================================

def build_settings_keyboard(chat_id):
    def btn(label, key):
        val = get_setting(chat_id, key, 1)
        return InlineKeyboardButton(f"{'✅' if val else '❌'} {label}", callback_data=f"toggle_{key}")
    return InlineKeyboardMarkup([
        [btn("ولکام", "welcome_enabled")],
        [btn("خداحافظی", "goodbye_enabled")],
        [btn("حذف لینک", "delete_links")],
        [btn("آنتی اسپم", "delete_spam")],
        [btn("حذف استیکر", "delete_stickers")],
        [InlineKeyboardButton("❌ بستن", callback_data="close_settings")],
    ])

async def settings_cmd(update, context):
    if not await is_admin(update, context):
        await reply_msg(update, "❌ فقط ادمین‌ها!", context)
        return
    await reply_msg(update, "⚙️ تنظیمات گروه", context, reply_markup=build_settings_keyboard(update.effective_chat.id))

async def settings_callback(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if query.data == "close_settings":
        await query.message.delete()
        return
    if query.data.startswith("toggle_"):
        key = query.data.replace("toggle_", "")
        current = get_setting(chat_id, key, 1)
        set_setting(chat_id, key, 0 if current else 1)
        await query.edit_message_reply_markup(reply_markup=build_settings_keyboard(chat_id))

# ============================================
# منو و استارت
# ============================================

def get_help_text():
    return """
📋 **راهنمای ربات یاشا**

👮 **دستورات مدیریتی:**
/lock - قفل گروه
/unlock - باز کردن گروه
/ban - بن کاربر
/unban - آنبن کاربر
/mute - میوت کاربر
/unmute - آنمیوت کاربر
/kick - کیک کاربر

🧹 **پاکسازی:**
/purge - پاک کردن پیام‌ها
/purgeuser - پاک کردن پیام‌های کاربر

⚙️ **عمومی:**
/start - منوی اصلی
/help - راهنما
/settings - تنظیمات
/join - بررسی عضویت
"""

async def start_cmd(update, context):
    buttons = [
        [InlineKeyboardButton("📋 راهنما", callback_data="menu_help")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu_settings")],
        [InlineKeyboardButton("📢 کانال ما", url=FORCE_SUB_CHANNEL)],
        [InlineKeyboardButton("❌ بستن", callback_data="close_menu")],
    ]
    await reply_msg(update, "🤖 **ربات مدیریت گروه یاشا**\n\nاز منوی زیر استفاده کن:", context, reply_markup=InlineKeyboardMarkup(buttons))

async def help_cmd(update, context):
    await reply_msg(update, get_help_text(), context)

async def join_cmd(update, context):
    await force_sub_panel(update, context)

async def menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "menu_help":
        await query.edit_message_text(get_help_text(), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "menu_settings":
        await settings_cmd(update, context)
    elif query.data == "close_menu":
        await query.message.delete()

# ============================================
# Main
# ============================================

async def set_bot_commands(app):
    commands = [
        BotCommand("start", "منوی اصلی"),
        BotCommand("help", "راهنما"),
        BotCommand("settings", "تنظیمات گروه"),
        BotCommand("join", "بررسی عضویت"),
        BotCommand("lock", "قفل گروه"),
        BotCommand("unlock", "باز کردن گروه"),
        BotCommand("ban", "بن کاربر"),
        BotCommand("unban", "آنبن کاربر"),
        BotCommand("mute", "میوت کاربر"),
        BotCommand("unmute", "آنمیوت کاربر"),
        BotCommand("kick", "کیک کاربر"),
        BotCommand("purge", "پاکسازی پیام‌ها"),
        BotCommand("purgeuser", "پاکسازی پیام‌های کاربر"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = set_bot_commands

    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("kick", kick_cmd))
    app.add_handler(CommandHandler("purge", purge_cmd))
    app.add_handler(CommandHandler("purgeuser", purge_user_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("join", join_cmd))

    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(toggle_|close_settings)"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_)"))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

    logger.info("ربات یاشا شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
