#!/usr/bin/env python3
"""
ربات حرفه‌ای دانلودر با پشتیبانی از یوتیوب، اینستاگرام، تیک‌تاک و...
با پنل انتخاب کیفیت
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
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

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 6387049405))
DOWNLOAD_PATH = "downloads/"

# حداکثر حجم فایل برای ارسال مستقیم (50 مگ)
MAX_FILE_SIZE = 50 * 1024 * 1024

# تنظیمات yt-dlp
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
    'geo_bypass': True,
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
    """ایجاد پوشه دانلود اگر وجود نداشته باشد"""
    Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)

def get_platform(url: str) -> str:
    """تشخیص پلتفرم از روی لینک"""
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
    elif 'spotify.com' in url_lower:
        return 'spotify'
    elif 'pinterest.com' in url_lower:
        return 'pinterest'
    elif 'reddit.com' in url_lower:
        return 'reddit'
    else:
        return 'unknown'

async def get_video_info(url: str) -> Optional[Dict]:
    """دریافت اطلاعات ویدیو از لینک"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def get_available_qualities(info: Dict) -> List[Dict]:
    """استخراج کیفیت‌های موجود از اطلاعات ویدیو"""
    qualities = []
    
    # فرمت‌های ویدیویی
    if 'formats' in info:
        for f in info['formats']:
            if f.get('vcodec') != 'none' and f.get('height'):
                quality = f"{f['height']}p"
                if quality not in [q['quality'] for q in qualities]:
                    qualities.append({
                        'quality': quality,
                        'format_id': f['format_id'],
                        'ext': f.get('ext', 'mp4'),
                        'type': 'video'
                    })
    
    # مرتب‌سازی کیفیت‌ها از بالا به پایین
    qualities.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    
    # اضافه کردن گزینه صوتی
    qualities.append({
        'quality': 'MP3',
        'format_id': 'mp3',
        'ext': 'mp3',
        'type': 'audio'
    })
    
    return qualities[:8]  # حداکثر ۸ گزینه

def build_quality_keyboard(qualities: List[Dict], url: str) -> InlineKeyboardMarkup:
    """ساخت کیبورد شیشه‌ای برای انتخاب کیفیت"""
    keyboard = []
    row = []
    
    for i, q in enumerate(qualities):
        emoji = "🎥" if q['type'] == 'video' else "🎵"
        row.append(InlineKeyboardButton(
            f"{emoji} {q['quality']}",
            callback_data=f"dl_{i}_{url[:50]}"
        ))
        if len(row) == 2:  # دو دکمه در هر ردیف
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # دکمه لغو
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_download")])
    
    return InlineKeyboardMarkup(keyboard)

async def download_media(url: str, quality_info: Dict) -> Optional[Tuple[str, str]]:
    """دانلود فایل با کیفیت مشخص"""
    output_template = f"{DOWNLOAD_PATH}%(title)s.%(ext)s"
    
    opts = YDL_OPTS.copy()
    opts['outtmpl'] = output_template
    
    if quality_info['type'] == 'audio':
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['format'] = f"{quality_info['format_id']}+bestaudio/best"
        opts['merge_output_format'] = 'mp4'
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # برای فایل‌های صوتی، پسوند رو اصلاح کن
            if quality_info['type'] == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            # اگر فایل وجود ندارد، دنبال فایل با پسوندهای دیگر بگرد
            if not os.path.exists(filename):
                for ext in ['.mp4', '.webm', '.mkv', '.mp3']:
                    test_path = filename.rsplit('.', 1)[0] + ext
                    if os.path.exists(test_path):
                        filename = test_path
                        break
            
            return (filename, info.get('title', 'Unknown'))
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def send_large_file(context, chat_id, file_path, title):
    """ارسال فایل‌های بزرگ به صورت سند"""
    try:
        file_size = os.path.getsize(file_path)
        
        # برای فایل‌های کمتر از 50 مگ، مستقیم بفرست
        if file_size < MAX_FILE_SIZE:
            with open(file_path, 'rb') as f:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=f"✅ {title}",
                    supports_streaming=True
                )
        else:
            # برای فایل‌های بزرگ، به صورت سند بفرست
            with open(file_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=f"✅ {title}\n📦 حجم: {file_size // (1024*1024)} مگابایت"
                )
        return True
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        return False

# ============================================
# هندلرهای ربات
# ============================================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start"""
    text = """
🎬 **ربات دانلودر حرفه‌ای**
━━━━━━━━━━━━━━━━━━━━━━

📥 **قابلیت‌ها:**
• دانلود از یوتیوب، اینستاگرام، تیک‌تاک
• دانلود از توییتر، آپارات، ساندکلاود
• انتخاب کیفیت ویدیو (4K, 1080p, 720p, ...)
• استخراج MP3 از ویدیوها
• دانلود پلی‌لیست یوتیوب
• دریافت عکس از اینستاگرام

━━━━━━━━━━━━━━━━━━━━━━
🎯 **نحوه استفاده:**
فقط لینک ویدیو یا عکس رو برام بفرست، من کیفیت‌ها رو بهت نشون میدم.

💡 _پشتیبانی از یوتیوب، اینستاگرام، تیک‌تاک، توییتر، آپارات، ساندکلاود، اسپاتیفای_
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /help"""
    text = """
📋 **راهنما**

1️⃣ لینک ویدیو/عکس رو برام بفرست
2️⃣ کیفیت مورد نظرت رو انتخاب کن
3️⃣ منتظر بمون تا دانلود و ارسال بشه

🔗 **لینک‌های پشتیبانی شده:**
• YouTube (ویدیو، کوتاه، پلی‌لیست)
• Instagram (پست، ریلز، استوری)
• TikTok
• Twitter/X
• SoundCloud
• Aparat
• Spotify (آهنگ)
• Pinterest (عکس)
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر لینک‌های دریافتی"""
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # ارسال پیام اولیه
    status_msg = await update.message.reply_text("⏳ در حال بررسی لینک...")
    
    # تشخیص پلتفرم
    platform = get_platform(url)
    if platform == 'unknown':
        await status_msg.edit_text("❌ لینک نامعتبر یا پشتیبانی نمی‌شود!")
        return
    
    # دریافت اطلاعات
    info = await get_video_info(url)
    if not info:
        await status_msg.edit_text("❌ خطا در دریافت اطلاعات! لینک معتبر است؟")
        return
    
    # استخراج عنوان
    title = info.get('title', 'Unknown Video')[:60]
    duration = info.get('duration', 0)
    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "نامشخص"
    
    # استخراج کیفیت‌های موجود
    qualities = get_available_qualities(info)
    
    # ذخیره اطلاعات در context.user_data برای استفاده در کالبک
    context.user_data['current_url'] = url
    context.user_data['qualities'] = qualities
    context.user_data['title'] = title
    
    # ساخت کیبورد
    keyboard = build_quality_keyboard(qualities, url)
    
    # ارسال پیام با کیبورد
    await status_msg.edit_text(
        f"🎬 **{platform.upper()} Detected**\n━━━━━━━━━━━━━━━━━━━━━━\n📹 **{title}**\n⏱ مدت: {duration_str}\n\n🎯 **کیفیت مورد نظر را انتخاب کن:**",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به انتخاب کیفیت"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "cancel_download":
        await query.edit_message_text("❌ دانلود لغو شد.")
        return
    
    # استخراج ایندکس کیفیت از دیتا
    try:
        parts = data.split('_')
        if len(parts) >= 2 and parts[0] == 'dl':
            quality_index = int(parts[1])
        else:
            await query.edit_message_text("❌ خطا در انتخاب کیفیت!")
            return
    except:
        await query.edit_message_text("❌ خطا در انتخاب کیفیت!")
        return
    
    # دریافت اطلاعات ذخیره شده
    url = context.user_data.get('current_url')
    qualities = context.user_data.get('qualities')
    title = context.user_data.get('title', 'ویدیو')
    
    if not url or not qualities or quality_index >= len(qualities):
        await query.edit_message_text("❌ خطا! لطفاً دوباره لینک رو بفرست.")
        return
    
    selected = qualities[quality_index]
    
    # آپدیت پیام
    await query.edit_message_text(
        f"⏳ در حال دانلود: **{selected['quality']}**\n"
        f"🎬 **{title}**\n\n"
        f"این پروسه ممکن است چند دقیقه طول بکشد...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # دانلود فایل
    result = await download_media(url, selected)
    
    if not result:
        await query.edit_message_text("❌ دانلود ناموفق! لطفاً دوباره تلاش کن.")
        return
    
    file_path, file_title = result
    
    # ارسال فایل
    success = await send_large_file(context, chat_id, file_path, file_title)
    
    if success:
        await query.edit_message_text("✅ دانلود و ارسال شد!")
    else:
        await query.edit_message_text("❌ خطا در ارسال فایل!")
    
    # پاکسازی فایل دانلود شده
    try:
        os.remove(file_path)
    except:
        pass

# ============================================
# Main
# ============================================

def main():
    """تابع اصلی"""
    create_download_dir()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # هندلرها
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern="^(dl_|cancel_download)"))
    
    logger.info("✅ ربات دانلودر حرفه‌ای شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
