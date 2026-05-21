#!/usr/bin/env python3
"""
ربات دانلودر حرفه‌ای - نسخه نهایی با صدای کامل
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict, List

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
    """دریافت اطلاعات ویدیو"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def get_available_qualities(info: Dict) -> List[Dict]:
    """استخراج کیفیت‌های موجود با فرمت‌های کامل (ویدیو+صدا)"""
    qualities = []
    
    if 'formats' not in info:
        return qualities
    
    seen = set()
    for f in info['formats']:
        height = f.get('height')
        # فرمت‌هایی که هم ویدیو دارن هم صدا
        if height and height >= 144 and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
            if height not in seen:
                seen.add(height)
                size_mb = f.get('filesize', 0) / (1024 * 1024) if f.get('filesize') else 0
                qualities.append({
                    'quality': f"{height}p",
                    'format_id': f['format_id'],
                    'size_mb': size_mb,
                    'type': 'video'
                })
    
    # اگه فرمت کامل پیدا نشد، فرمت ویدیو بدون صدا رو با بهترین صدا ترکیب کن
    if not qualities:
        best_video = None
        best_audio = None
        
        for f in info['formats']:
            if f.get('height') and f.get('vcodec') != 'none':
                if not best_video or f.get('height', 0) > best_video.get('height', 0):
                    best_video = f
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                if not best_audio or f.get('abr', 0) > best_audio.get('abr', 0):
                    best_audio = f
        
        if best_video:
            size_mb = best_video.get('filesize', 0) / (1024 * 1024) if best_video.get('filesize') else 0
            qualities.append({
                'quality': f"{best_video.get('height', 720)}p (best)",
                'format_id': best_video['format_id'],
                'audio_id': best_audio['format_id'] if best_audio else None,
                'size_mb': size_mb,
                'type': 'video'
            })
    
    qualities.sort(key=lambda x: int(x['quality'].replace('p', '').split()[0]), reverse=True)
    
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

def download_video(url: str, quality: Dict) -> Optional[str]:
    """دانلود ویدیو با کیفیت انتخابی (با صدا)"""
    output_template = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = output_template
    opts['merge_output_format'] = 'mp4'
    
    if quality['type'] == 'audio':
        # فقط MP3
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # ویدیو با صدا
        if quality.get('audio_id'):
            opts['format'] = f"{quality['format_id']}+{quality['audio_id']}"
        else:
            opts['format'] = quality['format_id']
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if quality['type'] == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            else:
                # اطمینان از پسوند mp4
                if not filename.endswith('.mp4'):
                    base = filename.rsplit('.', 1)[0]
                    filename = base + '.mp4'
            
            if os.path.exists(filename):
                return filename
            
            # جستجو در پوشه
            for f in os.listdir(DOWNLOAD_PATH):
                if f.endswith('.mp4') or f.endswith('.mp3'):
                    return os.path.join(DOWNLOAD_PATH, f)
            return None
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def send_media(context, chat_id, file_path, title):
    """ارسال فایل"""
    try:
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
    
    await query.edit_message_text(
        f"⏳ **در حال دانلود...**\n\n📹 {title}\n🎯 {selected['quality']}\n\n_لطفاً صبر کنید..._",
        parse_mode=ParseMode.MARKDOWN
    )
    
    file_path = await asyncio.to_thread(download_video, url, selected)
    
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
