#!/usr/bin/env python3
"""
ربات حرفه‌ای دانلودر با پشتیبانی از یوتیوب، اینستاگرام، تیک‌تاک و...
با پنل انتخاب کیفیت و دانلود فقط MP4
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# ============================================
# تنظیمات و متغیرهای محیطی
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

DOWNLOAD_PATH = "downloads/"

# حداکثر حجم فایل برای ارسال مستقیم
MAX_FILE_SIZE = 50 * 1024 * 1024

# تنظیمات yt-dlp - فقط MP4
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # فقط MP4
    'merge_output_format': 'mp4',
}

# ============================================
# تنظیمات لاگ
# ============================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# توابع کمکی
# ============================================

def create_download_dir():
    Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)

def get_platform(url: str) -> str:
    url_lower = url.lower()
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    elif 'soundcloud.com' in url_lower:
        return 'soundcloud'
    elif 'aparat.com' in url_lower:
        return 'aparat'
    else:
        return 'unknown'

async def get_video_info(url: str) -> Optional[Dict]:
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def get_available_qualities(info: Dict) -> List[Dict]:
    """استخراج کیفیت‌های موجود - فقط فرمت‌هایی که ویدیو+صدا دارند یا قابل ترکیب هستند"""
    qualities = []
    
    if 'formats' not in info:
        return qualities
    
    # جمع‌آوری کیفیت‌های ویدیویی
    video_formats = {}
    audio_formats = {}
    
    for f in info['formats']:
        # فرمت ویدیو
        if f.get('vcodec') != 'none' and f.get('height'):
            height = f['height']
            if height not in video_formats or video_formats[height].get('filesize', 0) < f.get('filesize', 0):
                video_formats[height] = {
                    'format_id': f['format_id'],
                    'height': height,
                    'ext': f.get('ext', 'mp4'),
                    'filesize': f.get('filesize', 0),
                    'vcodec': f.get('vcodec', '')
                }
        
        # فرمت صوتی
        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            bitrate = f.get('abr', 0)
            if bitrate not in audio_formats or bitrate < 0:
                audio_formats[bitrate] = {
                    'format_id': f['format_id'],
                    'bitrate': bitrate,
                    'ext': f.get('ext', 'm4a')
                }
    
    # بهترین فرمت صوتی
    best_audio = None
    if audio_formats:
        best_audio = audio_formats[max(audio_formats.keys())]
    
    # ساخت لیست کیفیت‌ها
    for height in sorted(video_formats.keys(), reverse=True):
        vf = video_formats[height]
        
        # تخمین حجم فایل (ویدیو + صدا)
        size_mb = 0
        if vf['filesize']:
            size_mb = vf['filesize'] / (1024 * 1024)
        if best_audio and best_audio.get('filesize'):
            size_mb += best_audio.get('filesize', 0) / (1024 * 1024)
        
        size_text = f" [{size_mb:.0f}MB]" if size_mb > 0 else ""
        
        qualities.append({
            'quality': f"{height}p",
            'format_id': vf['format_id'],
            'audio_id': best_audio['format_id'] if best_audio else None,
            'ext': 'mp4',
            'type': 'video',
            'size_mb': size_mb
        })
    
    # اضافه کردن گزینه صوتی
    if best_audio:
        qualities.append({
            'quality': '🎵 MP3 (Audio Only)',
            'format_id': best_audio['format_id'],
            'audio_id': None,
            'ext': 'mp3',
            'type': 'audio',
            'size_mb': 0
        })
    
    return qualities[:10]

def build_quality_keyboard(qualities: List[Dict], url: str, video_id: str = None) -> InlineKeyboardMarkup:
    keyboard = []
    for i, q in enumerate(qualities):
        if q['type'] == 'video':
            emoji = "🎥"
            size_text = f" {q['size_mb']:.0f}MB" if q['size_mb'] > 0 else ""
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {q['quality']}{size_text}",
                callback_data=f"dl_{i}_{video_id or 'video'}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{q['quality']}",
                callback_data=f"dl_{i}_{video_id or 'audio'}"
            )])
    
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_download")])
    return InlineKeyboardMarkup(keyboard)

async def download_media(url: str, quality_info: Dict) -> Optional[Tuple[str, str]]:
    """دانلود فایل با کیفیت مشخص - فقط MP4 برای ویدیو"""
    
    output_template = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = output_template
    
    if quality_info['type'] == 'audio':
        # فقط صدا
        opts['format'] = quality_info['format_id']
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # ویدیو: ترکیب فرمت ویدیو + بهترین فرمت صوتی
        if quality_info.get('audio_id'):
            opts['format'] = f"{quality_info['format_id']}+{quality_info['audio_id']}"
        else:
            opts['format'] = quality_info['format_id']
        opts['merge_output_format'] = 'mp4'
        opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # اصلاح پسوند برای فایل‌های صوتی
            if quality_info['type'] == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            # اگر فایل پیدا نشد، توی پوشه بگرد
            if not os.path.exists(filename):
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.startswith(info.get('title', '')[:30]) or f.endswith('.mp4') or f.endswith('.mp3'):
                        filename = os.path.join(DOWNLOAD_PATH, f)
                        break
            
            return (filename, info.get('title', 'Unknown Video'))
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def send_media(context, chat_id, file_path, title, is_video=True):
    """ارسال فایل - فقط ویدیو یا صدا، بدون فایل اضافی"""
    try:
        file_size = os.path.getsize(file_path)
        
        # فایل صوتی
        if file_path.endswith('.mp3') or not is_video:
            with open(file_path, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    title=title[:50],
                    performer="Yasha Downloader"
                )
            return True
        
        # فایل ویدیویی
        if file_size < MAX_FILE_SIZE:
            with open(file_path, 'rb') as f:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=f"🎬 {title[:60]}",
                    supports_streaming=True
                )
        else:
            with open(file_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=f"📁 {title[:60]}\nحجم: {file_size // (1024*1024)} MB"
                )
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

📥 **قابلیت‌ها:**
• دانلود ویدیو از یوتیوب با کیفیت انتخابی
• استخراج MP3 از ویدیوها
• پشتیبانی از YouTube Shorts
• فقط فرمت MP4 (بدون WEBM)

🎯 **نحوه استفاده:**
لینک ویدیو رو برام بفرست، کیفیت رو انتخاب کن.
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 لینک ویدیو رو بفرست، کیفیت رو انتخاب کن، دانلود بشه."
    await update.message.reply_text(text)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    status_msg = await update.message.reply_text("⏳ در حال بررسی لینک...")
    
    platform = get_platform(url)
    if platform == 'unknown':
        await status_msg.edit_text("❌ لینک پشتیبانی نمی‌شود!")
        return
    
    info = await get_video_info(url)
    if not info:
        await status_msg.edit_text("❌ خطا در دریافت اطلاعات!")
        return
    
    title = info.get('title', 'Unknown Video')[:60]
    duration = info.get('duration', 0)
    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "نامشخص"
    
    qualities = get_available_qualities(info)
    if not qualities:
        await status_msg.edit_text("❌ هیچ کیفیتی یافت نشد!")
        return
    
    video_id = info.get('id', str(hash(url))[:10])
    context.user_data['current_url'] = url
    context.user_data['qualities'] = qualities
    context.user_data['title'] = title
    
    keyboard = build_quality_keyboard(qualities, url, video_id)
    
    await status_msg.edit_text(
        f"🎬 **یوتیوب**\n━━━━━━━━━━━━━━━━━━━━━━\n📹 **{title}**\n⏱ مدت: {duration_str}\n\n🎯 **کیفیت مورد نظر را انتخاب کن:**",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "cancel_download":
        await query.edit_message_text("❌ لغو شد.")
        return
    
    try:
        parts = data.split('_')
        quality_index = int(parts[1])
    except:
        await query.edit_message_text("❌ خطا!")
        return
    
    url = context.user_data.get('current_url')
    qualities = context.user_data.get('qualities')
    title = context.user_data.get('title', 'ویدیو')
    
    if not url or not qualities or quality_index >= len(qualities):
        await query.edit_message_text("❌ خطا! دوباره لینک رو بفرست.")
        return
    
    selected = qualities[quality_index]
    
    await query.edit_message_text(
        f"⏳ **در حال دانلود...**\n\n"
        f"📹 {title[:40]}\n"
        f"🎯 کیفیت: {selected['quality']}\n\n"
        f"_لطفاً صبر کنید..._",
        parse_mode=ParseMode.MARKDOWN
    )
    
    result = await download_media(url, selected)
    
    if not result:
        await query.edit_message_text("❌ دانلود ناموفق!")
        return
    
    file_path, file_title = result
    is_video = selected['type'] == 'video'
    
    success = await send_media(context, chat_id, file_path, file_title, is_video)
    
    if success:
        await query.edit_message_text("✅ دانلود و ارسال شد!")
    else:
        await query.edit_message_text("❌ خطا در ارسال!")
    
    try:
        os.remove(file_path)
    except:
        pass

# ============================================
# Main
# ============================================

def main():
    create_download_dir()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern="^(dl_|cancel_download)"))
    
    logger.info("✅ ربات دانلودر شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
