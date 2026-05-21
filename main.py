#!/usr/bin/env python3
"""
ربات دانلودر حرفه‌ای - تبدیل ویدیو به MP4 با صدا
"""

import asyncio
import logging
import os
import subprocess
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

def convert_to_mp4_with_audio(input_path: str, output_path: str) -> bool:
    """تبدیل هر ویدیویی به MP4 با صدا با استفاده از ffmpeg"""
    try:
        # دستور ffmpeg برای تبدیل به MP4 با کدک‌های استاندارد
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:v", "libx264",      # کدک ویدیو
            "-c:a", "aac",           # کدک صدا (همیشه صدا داره)
            "-movflags", "+faststart",
            "-y",                    # بازنویسی فایل
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return False

# ============================================
# تنظیمات اصلی yt-dlp
# ============================================

YDL_OPTS = {
    'quiet': True,
    'no_warnings': False,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
    'socket_timeout': 30,
}

def get_video_info(url: str) -> Optional[Dict]:
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting info: {e}")
        return None

def get_available_qualities(info: Dict) -> List[Dict]:
    qualities = []
    
    if 'formats' not in info:
        if info.get('extractor', '').lower() in ['soundcloud', 'spotify']:
            qualities.append({
                'quality': '🎵 MP3 (Audio Only)',
                'format_id': 'bestaudio',
                'size_mb': 0,
                'type': 'audio'
            })
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
    
    qualities.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    
    qualities.append({
        'quality': '🎵 MP3 (Audio Only)',
        'format_id': 'bestaudio',
        'size_mb': 0,
        'type': 'audio'
    })
    
    return qualities[:10]

def build_keyboard(qualities: List[Dict]) -> InlineKeyboardMarkup:
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

def download_media(url: str, quality: Dict) -> Optional[str]:
    """دانلود و تبدیل به MP4 با صدا"""
    temp_template = f"{DOWNLOAD_PATH}temp_%(title)s.%(ext)s"
    final_template = f"{DOWNLOAD_PATH}%(title)s.mp4"
    
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = temp_template
    
    if quality['type'] == 'audio':
        # دانلود MP3 مستقیم
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        opts['outtmpl'] = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = filename.rsplit('.', 1)[0] + '.mp3'
                
                if os.path.exists(filename):
                    return filename
                return None
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            return None
    else:
        # دانلود ویدیو و تبدیل به MP4 با صدا
        opts['format'] = f"{quality['format_id']}+bestaudio/best"
        opts['merge_output_format'] = 'mp4'
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                temp_file = ydl.prepare_filename(info)
                
                # فایل نهایی MP4
                base_name = temp_file.rsplit('.', 1)[0]
                final_file = base_name + '.mp4'
                
                # اگه فایل نهایی وجود داره، برگردون
                if os.path.exists(final_file):
                    return final_file
                
                # اگه فایل دانلود شده با فرمت دیگست، تبدیل کن
                downloaded_files = []
                for f in os.listdir(DOWNLOAD_PATH):
                    if f.startswith(info.get('title', '')[:30]) or f.endswith('.mp4') or f.endswith('.webm') or f.endswith('.mkv'):
                        downloaded_files.append(os.path.join(DOWNLOAD_PATH, f))
                
                if not downloaded_files:
                    return None
                
                temp_video = downloaded_files[0]
                final_video = temp_video.rsplit('.', 1)[0] + '.mp4'
                
                # اگر ویدیو MP4 نیست، تبدیل کن
                if not temp_video.endswith('.mp4'):
                    if convert_to_mp4_with_audio(temp_video, final_video):
                        # حذف فایل موقت
                        try:
                            os.remove(temp_video)
                        except:
                            pass
                        return final_video
                    else:
                        return temp_video
                else:
                    return temp_video
        except Exception as e:
            logger.error(f"Video download error: {e}")
            return None

async def send_media(context, chat_id, file_path, title):
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

📥 **قابلیت‌ها:**
• دانلود از 1500+ سایت
• **تبدیل خودکار به MP4 با صدا** 🔈
• دانلود MP3 آهنگ‌ها
• انتخاب کیفیت دلخواه

🎯 **نحوه استفاده:**
فقط لینک رو بفرست، کیفیت رو انتخاب کن.
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📹 لینک ویدیو/آهنگ رو بفرست تا برات دانلود کنم.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    msg = await update.message.reply_text("⏳ در حال بررسی لینک...")
    
    info = await asyncio.to_thread(get_video_info, url)
    
    if not info:
        await msg.edit_text("❌ خطا در دریافت اطلاعات! لینک معتبر است؟")
        return
    
    extractor = info.get('extractor', 'Unknown')
    title = info.get('title', 'Media')[:50]
    duration = info.get('duration', 0)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "نامشخص"
    
    qualities = get_available_qualities(info)
    if not qualities:
        await msg.edit_text("❌ هیچ فرمت قابل دانلودی یافت نشد!")
        return
    
    context.user_data['url'] = url
    context.user_data['qualities'] = qualities
    context.user_data['title'] = title
    
    keyboard = build_keyboard(qualities)
    
    await msg.edit_text(
        f"📱 **پلتفرم:** {extractor}\n"
        f"🎬 **عنوان:** {title}\n"
        f"⏱ **مدت:** {dur_str}\n\n"
        f"🎯 **کیفیت را انتخاب کن (ویدیوها با صدا ارسال می‌شن):**",
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
    title = context.user_data.get('title', 'Media')
    
    if not url or not qualities or idx >= len(qualities):
        await query.edit_message_text("❌ خطا! دوباره لینک رو بفرست.")
        return
    
    selected = qualities[idx]
    
    await query.edit_message_text(
        f"⏳ **در حال دانلود و تبدیل به MP4...**\n\n"
        f"📹 {title}\n"
        f"🎯 {selected['quality']}\n\n"
        f"_لطفاً صبر کنید..._",
        parse_mode=ParseMode.MARKDOWN
    )
    
    file_path = await asyncio.to_thread(download_media, url, selected)
    
    if not file_path:
        await query.edit_message_text("❌ دانلود ناموفق!")
        return
    
    success = await send_media(context, query.message.chat_id, file_path, title)
    
    if success:
        await query.edit_message_text("✅ دانلود و ارسال شد!")
    else:
        await query.edit_message_text("❌ خطا در ارسال فایل!")

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
