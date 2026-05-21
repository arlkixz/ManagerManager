#!/usr/bin/env python3
"""
ربات دانلودر حرفه‌ای - نسخه پایدار با yt-dlp
"""

import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# ============================================
# تنظیمات
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

DOWNLOAD_PATH = "downloads/"
MAX_FILE_SIZE = 50 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# ایجاد پوشه دانلود
# ============================================

def create_download_dir():
    Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)

# ============================================
# تنظیمات yt-dlp
# ============================================

YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
}

# ============================================
# توابع
# ============================================

def get_video_info(url: str) -> Optional[Dict]:
    """دریافت اطلاعات ویدیو با yt-dlp"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def get_available_qualities(info: Dict) -> List[Dict]:
    """استخراج کیفیت‌های موجود"""
    qualities = []
    
    if 'formats' not in info:
        return qualities
    
    seen_heights = set()
    for f in info['formats']:
        height = f.get('height')
        if height and height >= 144 and f.get('vcodec') != 'none':
            if height not in seen_heights:
                seen_heights.add(height)
                size_mb = f.get('filesize', 0) / (1024 * 1024) if f.get('filesize') else 0
                qualities.append({
                    'quality': f"{height}p",
                    'format_id': f['format_id'],
                    'size_mb': size_mb,
                    'type': 'video'
                })
    
    # مرتب‌سازی از بزرگ به کوچک
    qualities.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    
    # گزینه صوتی
    qualities.append({
        'quality': '🎵 MP3 (Audio Only)',
        'format_id': 'bestaudio',
        'size_mb': 0,
        'type': 'audio'
    })
    
    return qualities[:8]

def build_keyboard(qualities: List[Dict]) -> InlineKeyboardMarkup:
    """ساخت کیبورد انتخاب کیفیت"""
    keyboard = []
    for i, q in enumerate(qualities):
        if q['type'] == 'video':
            size_text = f" [{q['size_mb']:.0f}MB]" if q['size_mb'] > 0 else ""
            keyboard.append([InlineKeyboardButton(
                f"🎥 {q['quality']}{size_text}",
                callback_data=f"dl_{i}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{q['quality']}",
                callback_data=f"dl_{i}"
            )])
    
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def download_media(url: str, format_id: str, is_audio: bool = False) -> Optional[str]:
    """دانلود ویدیو یا صدا"""
    output_template = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = output_template
    
    if is_audio:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['format'] = f"{format_id}+bestaudio/best"
        opts['merge_output_format'] = 'mp4'
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if is_audio:
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            if os.path.exists(filename):
                return filename
            
            # جستجوی فایل در پوشه
            for f in os.listdir(DOWNLOAD_PATH):
                if f.endswith('.mp4') or f.endswith('.mp3'):
                    return os.path.join(DOWNLOAD_PATH, f)
            
            return None
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def send_media(context, chat_id, file_path, title):
    """ارسال فایل به کاربر"""
    try:
        file_size = os.path.getsize(file_path)
        
        if file_path.endswith('.mp3'):
            with open(file_path, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    title=title[:50],
                    performer="Yasha Bot"
                )
        else:
            with open(file_path, 'rb') as f:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=f"🎬 {title[:60]}",
                    supports_streaming=True
                )
        
        # حذف فایل بعد از ارسال
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"Send error: {e}")
        return False

# ============================================
# هندلرها
# ============================================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🎬 **ربات دانلودر حرفه‌ای**

📥 لینک ویدیو رو برام بفرست
🎯 کیفیت مورد نظرت رو انتخاب کن
📤 دانلود و ارسال میشه

🔗 پشتیبانی از یوتیوب، اینستاگرام، تیک‌تاک
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    msg = await update.message.reply_text("⏳ در حال بررسی لینک...")
    
    # دریافت اطلاعات در thread جداگانه (اجتناب از block)
    info = await asyncio.to_thread(get_video_info, url)
    
    if not info:
        await msg.edit_text("❌ خطا در دریافت اطلاعات! لینک معتبر است؟")
        return
    
    title = info.get('title', 'ویدیو')[:50]
    duration = info.get('duration', 0)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "نامشخص"
    
    qualities = get_available_qualities(info)
    if not qualities:
        await msg.edit_text("❌ هیچ کیفیتی یافت نشد!")
        return
    
    # ذخیره در حافظه
    context.user_data['url'] = url
    context.user_data['qualities'] = qualities
    context.user_data['title'] = title
    
    keyboard = build_keyboard(qualities)
    
    await msg.edit_text(
        f"🎬 **{title}**\n⏱ مدت: {dur_str}\n\n🎯 کیفیت را انتخاب کن:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("❌ لغو شد.")
        return
    
    try:
        idx = int(data.split('_')[1])
    except:
        await query.edit_message_text("❌ خطا!")
        return
    
    url = context.user_data.get('url')
    qualities = context.user_data.get('qualities')
    title = context.user_data.get('title', 'ویدیو')
    
    if not url or not qualities or idx >= len(qualities):
        await query.edit_message_text("❌ خطا! دوباره لینک رو بفرست.")
        return
    
    selected = qualities[idx]
    is_audio = selected['type'] == 'audio'
    
    await query.edit_message_text(
        f"⏳ **در حال دانلود...**\n\n"
        f"📹 {title}\n"
        f"🎯 {selected['quality']}\n\n"
        f"_لطفاً صبر کنید..._",
        parse_mode=ParseMode.MARKDOWN
    )
    
    format_id = selected['format_id'] if not is_audio else None
    
    # دانلود در thread جداگانه
    file_path = await asyncio.to_thread(download_media, url, format_id, is_audio)
    
    if not file_path:
        await query.edit_message_text("❌ دانلود ناموفق!")
        return
    
    success = await send_media(context, query.message.chat_id, file_path, title)
    
    if success:
        await query.edit_message_text("✅ دانلود و ارسال شد!")
    else:
        await query.edit_message_text("❌ خطا در ارسال فایل!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📹 لینک ویدیو رو بفرست تا برات دانلود کنم.")

# ============================================
# Main
# ============================================

def main():
    create_download_dir()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern="^(dl_|cancel)"))
    
    logger.info("✅ ربات دانلودر شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
