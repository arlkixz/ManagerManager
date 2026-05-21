#!/usr/bin/env python3
"""
ربات دانلودر حرفه‌ای - نسخه نهایی با FFmpeg
"""

import asyncio
import logging
import os
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_PATH = "downloads/"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def create_download_dir():
    Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)

# ✅ تغییر مهم اینجاست: فرمت دانلود اصلاح شده
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'geo_bypass': True,
    'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # این خط حیاتی است
    'merge_output_format': 'mp4',  # خروجی نهایی MP4 باشد
}

def get_video_info(url: str):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Info error: {e}")
        return None

def get_qualities(info: dict):
    qualities = []
    if 'formats' in info:
        seen = set()
        for f in info['formats']:
            # فقط فرمت‌هایی که ویدیو و صدا همزمان دارند را نشان بده
            if f.get('height') and f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('height') not in seen:
                seen.add(f['height'])
                size_mb = f.get('filesize', 0) / (1024 * 1024) if f.get('filesize') else 0
                qualities.append({'quality': f"{f['height']}p", 'format_id': f['format_id'], 'size_mb': size_mb, 'type': 'video'})
        qualities.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    qualities.append({'quality': '🎵 MP3 (Audio)', 'format_id': 'bestaudio', 'size_mb': 0, 'type': 'audio'})
    return qualities[:8]

def build_keyboard(qualities: list):
    keyboard = []
    for i, q in enumerate(qualities):
        if q['type'] == 'video':
            size_text = f" [{q['size_mb']:.0f}MB]" if q['size_mb'] > 0 else ""
            keyboard.append([InlineKeyboardButton(f"🎥 {q['quality']}{size_text}", callback_data=f"vid_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"🎵 {q['quality']}", callback_data=f"aud_{i}")])
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def download_video(url: str, format_id: str):
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    opts['format'] = format_id  # کیفیت انتخابی کاربر
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # تصحیح پسوند
            if not filename.endswith('.mp4'):
                base = filename.rsplit('.', 1)[0]
                filename = base + '.mp4'
            return filename if os.path.exists(filename) else None
    except Exception as e:
        logger.error(f"Video error: {e}")
        return None

def download_audio(url: str):
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    opts['format'] = 'bestaudio/best'
    opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            return filename if os.path.exists(filename) else None
    except Exception as e:
        logger.error(f"Audio error: {e}")
        return None

async def send_media(context, chat_id, file_path, title, is_audio=False):
    try:
        with open(file_path, 'rb') as f:
            if is_audio or file_path.endswith('.mp3'):
                await context.bot.send_audio(chat_id=chat_id, audio=f, title=title[:50])
            else:
                await context.bot.send_video(chat_id=chat_id, video=f, caption=f"🎬 {title[:60]}", supports_streaming=True)
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

async def start_cmd(update, context):
    await update.message.reply_text("🎬 **ربات دانلودر حرفه‌ای**\n\nلینک ویدیو یا آهنگ رو بفرست، کیفیت رو انتخاب کن.\n\nویدیوها با **صدا و کیفیت بالا** ارسال می‌شن.", parse_mode=ParseMode.MARKDOWN)

async def handle_url(update, context):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ در حال بررسی...")
    info = await asyncio.to_thread(get_video_info, url)
    if not info:
        await msg.edit_text("❌ خطا! لینک معتبر نیست.")
        return
    title = info.get('title', 'Media')[:50]
    duration = info.get('duration', 0)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "نامشخص"
    qualities = get_qualities(info)
    if not qualities:
        await msg.edit_text("❌ هیچ کیفیتی یافت نشد!")
        return
    context.user_data.update({'url': url, 'qualities': qualities, 'title': title})
    await msg.edit_text(f"🎬 **{title}**\n⏱ {dur_str}\n\n**کیفیت رو انتخاب کن:**", reply_markup=build_keyboard(qualities), parse_mode=ParseMode.MARKDOWN)

async def quality_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "cancel":
        await query.edit_message_text("❌ لغو شد.")
        return
    is_audio = data.startswith("aud_")
    idx = int(data.split('_')[1])
    url = context.user_data.get('url')
    qualities = context.user_data.get('qualities')
    title = context.user_data.get('title')
    if not url or not qualities or idx >= len(qualities):
        await query.edit_message_text("❌ خطا! دوباره لینک رو بفرست.")
        return
    selected = qualities[idx]
    await query.edit_message_text(f"⏳ در حال دانلود {selected['quality']}...")
    if is_audio:
        file_path = await asyncio.to_thread(download_audio, url)
    else:
        file_path = await asyncio.to_thread(download_video, url, selected['format_id'])
    if not file_path:
        await query.edit_message_text("❌ دانلود ناموفق! (شاید سرور شلوغ باشه، دوباره تلاش کن)")
        return
    success = await send_media(context, query.message.chat_id, file_path, title, is_audio)
    await query.edit_message_text("✅ ویدیو با صدا دانلود و ارسال شد!" if success else "❌ خطا در ارسال!")

def main():
    create_download_dir()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern="^(vid_|aud_|cancel)"))
    logger.info("ربات دانلودر حرفه‌ای راه‌اندازی شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
