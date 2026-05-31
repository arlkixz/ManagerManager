#!/usr/bin/env python3
"""
🎬 Advanced Media Downloader Bot
📡 @aeohkl - Support & Updates
✅ Fixed: Duration float bug + Separate audio sending
"""

import asyncio
import os
import re
import json
import tempfile
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
import yt_dlp

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "aeohkl")
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "media_downloader_bot"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def extract_url(text: str) -> Optional[str]:
    """Extract URL from text"""
    pattern = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)
    match = pattern.search(text)
    return match.group(0) if match else None

def is_youtube(url: str) -> bool:
    """Check if URL is from YouTube"""
    return bool(re.search(r'(?:youtube\.com|youtu\.be)', url, re.IGNORECASE))

def safe_duration(duration) -> int:
    """
    ✅ FIX: Convert duration to int safely
    yt-dlp sometimes returns float (e.g., 95.6) but Telegram requires int
    """
    if duration is None:
        return 0
    try:
        return int(float(duration))
    except (ValueError, TypeError):
        return 0

def format_duration(seconds) -> str:
    """Format seconds to HH:MM:SS"""
    if not seconds:
        return "N/A"
    try:
        return str(timedelta(seconds=int(float(seconds))))
    except:
        return "N/A"

def format_number(num) -> str:
    """Format large numbers"""
    if not num:
        return "0"
    try:
        num = int(num)
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    except:
        return str(num)

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text"""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length-3] + "..."

def cleanup_file(path: Path):
    """Safely delete file"""
    try:
        if path and path.exists():
            path.unlink(missing_ok=True)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# YOUTUBE SEARCH (No external library needed)
# ═══════════════════════════════════════════════════════════════════════════

async def search_youtube(query: str, max_results: int = 5) -> List[Dict]:
    """Search YouTube without external libraries"""
    try:
        url = "https://www.youtube.com/results"
        params = {'search_query': query}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                html = await response.text()
                
                # Extract initial data
                pattern = re.compile(r'var ytInitialData = (.*?);</script>', re.DOTALL)
                match = pattern.search(html)
                
                if not match:
                    return []
                
                data = json.loads(match.group(1))
                results = []
                
                # Navigate YouTube's JSON structure
                contents = (
                    data.get('contents', {})
                    .get('twoColumnSearchResultsRenderer', {})
                    .get('primaryContents', {})
                    .get('sectionListRenderer', {})
                    .get('contents', [])
                )
                
                for section in contents:
                    items = (
                        section.get('itemSectionRenderer', {})
                        .get('contents', [])
                    )
                    
                    for item in items:
                        video = item.get('videoRenderer')
                        if not video:
                            continue
                        
                        video_id = video.get('videoId', '')
                        if not video_id:
                            continue
                        
                        results.append({
                            'id': video_id,
                            'url': f'https://youtube.com/watch?v={video_id}',
                            'title': video.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                            'duration': video.get('lengthText', {}).get('simpleText', 'N/A'),
                            'views': video.get('viewCountText', {}).get('simpleText', '0'),
                            'channel': video.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                        })
                        
                        if len(results) >= max_results:
                            break
                
                return results
                
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []

# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOAD MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class Downloader:
    """Media downloader using yt-dlp"""
    
    BASE_OPTS = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        },
    }
    
    QUALITY_MAP = {
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
        "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
        "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
    }
    
    @classmethod
    def video_opts(cls, output_path: str, quality: str = "best") -> dict:
        return {
            **cls.BASE_OPTS,
            "format": cls.QUALITY_MAP.get(quality, cls.QUALITY_MAP["best"]),
            "outtmpl": output_path,
            "merge_output_format": "mp4",
        }
    
    @classmethod
    def audio_opts(cls, output_path: str) -> dict:
        return {
            **cls.BASE_OPTS,
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    
    @classmethod
    async def download(cls, url: str, opts: dict) -> Tuple[Optional[Path], Optional[dict], Optional[str]]:
        """
        Download media
        Returns: (file_path, info_dict, error_message)
        """
        # Create temp file
        with tempfile.NamedTemporaryFile(dir=DOWNLOAD_DIR, delete=False, suffix="") as tmp:
            base_path = tmp.name
        
        opts = {**opts, "outtmpl": base_path + ".%(ext)s"}
        
        try:
            loop = asyncio.get_event_loop()
            
            def _download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=True)
            
            info = await loop.run_in_executor(None, _download)
            
            # Find downloaded files
            pattern = f"{Path(base_path).name}*"
            files = [f for f in DOWNLOAD_DIR.glob(pattern) if f.stat().st_size > 0]
            
            # Clean empty files
            for f in DOWNLOAD_DIR.glob(pattern):
                if f.stat().st_size == 0:
                    f.unlink(missing_ok=True)
            
            if not files:
                return None, None, "❌ فایل دانلود نشد یا خالی بود."
            
            # Get largest file
            file_path = max(files, key=lambda f: f.stat().st_size)
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if size_mb > MAX_FILE_SIZE_MB:
                file_path.unlink(missing_ok=True)
                return None, info, (
                    f"❌ حجم فایل ({size_mb:.1f}MB) از حد مجاز "
                    f"({MAX_FILE_SIZE_MB}MB) بیشتر است.\n\n"
                    f"💡 از کیفیت پایین‌تر استفاده کنید.\n"
                    f"📞 پشتیبانی: @{SUPPORT_USERNAME}"
                )
            
            return file_path, info, None
            
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).lower()
            if "sign in" in msg or "bot" in msg:
                return None, None, "❌ یوتیوب نیاز به احراز هویت دارد. لینک معمولی بفرستید."
            elif "private" in msg:
                return None, None, "❌ این محتوا خصوصی است."
            elif "not available" in msg or "unavailable" in msg:
                return None, None, "❌ این محتوا در دسترس نیست."
            else:
                return None, None, f"❌ خطا در دانلود:\n{truncate_text(str(e), 200)}"
        except Exception as e:
            logger.exception("Download error")
            return None, None, f"❌ خطای غیرمنتظره:\n{truncate_text(str(e), 150)}"

# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════

def quality_keyboard(url: str) -> InlineKeyboardMarkup:
    """Quality selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    buttons = [
        ("🎯 بهترین کیفیت", f"dl_best|{url}"),
        ("📺 1080p", f"dl_1080p|{url}"),
        ("📱 720p", f"dl_720p|{url}"),
        ("💾 480p", f"dl_480p|{url}"),
        ("📦 360p", f"dl_360p|{url}"),
        ("🎵 فقط صدا MP3", f"dl_audio|{url}"),
    ]
    
    for text, callback in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback[:64]))
    
    builder.adjust(2)
    
    # Support button
    builder.row(InlineKeyboardButton(
        text=f"📞 پشتیبانی @{SUPPORT_USERNAME}",
        url=f"https://t.me/{SUPPORT_USERNAME}"
    ))
    
    return builder.as_markup()

def search_keyboard(results: List[Dict]) -> InlineKeyboardMarkup:
    """Search results keyboard"""
    builder = InlineKeyboardBuilder()
    
    for i, video in enumerate(results[:MAX_SEARCH_RESULTS]):
        title = truncate_text(video.get('title', 'No Title'), 40)
        duration = video.get('duration', 'N/A')
        button_text = f"{i+1}. {title} ⏱{duration}"
        builder.add(InlineKeyboardButton(text=button_text, callback_data=f"search_{i}"))
    
    builder.adjust(1)
    return builder.as_markup()

# ═══════════════════════════════════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Store search results temporarily
search_cache: Dict[int, List[Dict]] = {}
# Track active downloads
active_downloads: Dict[int, bool] = {}

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 سلام <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>ربات دانلود مدیا</b>\n\n"
        "✨ <b>قابلیت‌ها:</b>\n"
        "• دانلود ویدیو با کیفیت‌های مختلف\n"
        "• دانلود فقط صدا (MP3)\n"
        "• ارسال خودکار صدا همراه ویدیو\n"
        "• جستجوی یوتیوب\n"
        "• پشتیبانی از ۲۰+ پلتفرم\n\n"
        "📥 <b>دستورات:</b>\n"
        "• لینک بفرستید — دانلود خودکار\n"
        "• <code>/yt عبارت</code> — جستجوی یوتیوب\n"
        "• <code>/audio لینک</code> — فقط صدا\n"
        "• <code>/formats لینک</code> — انتخاب کیفیت\n"
        "• <code>/info لینک</code> — اطلاعات ویدیو\n\n"
        f"📞 <b>پشتیبانی:</b> @{SUPPORT_USERNAME}\n"
        f"📦 <b>حداکثر حجم:</b> {MAX_FILE_SIZE_MB}MB"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>راهنما</b>\n\n"
        "🔗 <b>لینک بفرستید:</b>\n"
        "• یوتیوب: منوی کیفیت نشان داده میشه\n"
        "• بقیه سایت‌ها: دانلود مستقیم\n"
        "• صدا هم جداگانه ارسال میشه ✅\n\n"
        "🔍 <b>جستجوی یوتیوب:</b>\n"
        "<code>/yt عبارت مورد نظر</code>\n\n"
        "🎵 <b>فقط صدا:</b>\n"
        "<code>/audio لینک</code>\n\n"
        "📊 <b>اطلاعات:</b>\n"
        "<code>/info لینک</code>\n\n"
        f"📞 <b>پشتیبانی:</b> @{SUPPORT_USERNAME}"
    )

@dp.message(Command("yt"))
async def cmd_youtube_search(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❗ مثال:\n<code>/yt آهنگ شاد جدید</code>")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    results = await search_youtube(command.args, MAX_SEARCH_RESULTS)
    
    if not results:
        await message.reply(
            "❌ نتیجه‌ای پیدا نشد.\n\n"
            f"📞 پشتیبانی: @{SUPPORT_USERNAME}"
        )
        return
    
    # Save results
    search_cache[message.from_user.id] = results
    
    response = f"🔍 نتایج جستجو برای: <b>{command.args}</b>\n\n"
    
    for i, video in enumerate(results, 1):
        response += (
            f"{i}️⃣ <b>{truncate_text(video.get('title', 'Unknown'), 60)}</b>\n"
            f"   📺 {video.get('channel', 'Unknown')}\n"
            f"   ⏱ {video.get('duration', 'N/A')} | 👁 {video.get('views', '0')}\n"
            f"   🔗 <code>{video.get('url', '')}</code>\n\n"
        )
    
    response += "👇 برای دانلود، لینک رو کپی کن یا از دکمه زیر استفاده کن"
    
    await message.reply(
        response,
        reply_markup=search_keyboard(results),
        disable_web_page_preview=True
    )

@dp.message(Command("audio"))
async def cmd_audio(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❗ مثال:\n<code>/audio https://youtube.com/watch?v=...</code>")
        return
    
    url = extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await process_download(message, url, "audio", "best")

@dp.message(Command("formats"))
async def cmd_formats(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❗ مثال:\n<code>/formats https://youtube.com/watch?v=...</code>")
        return
    
    url = extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await message.reply(
        "🎬 <b>کیفیت مورد نظر رو انتخاب کن:</b>",
        reply_markup=quality_keyboard(url)
    )

@dp.message(Command("info"))
async def cmd_info(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❗ مثال:\n<code>/info https://youtube.com/watch?v=...</code>")
        return
    
    url = extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    # Get info without downloading
    try:
        loop = asyncio.get_event_loop()
        def _get_info():
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await loop.run_in_executor(None, _get_info)
        
        if not info:
            await message.reply("❌ نتونستم اطلاعات رو دریافت کنم.")
            return
        
        title = info.get('title', 'بدون عنوان')
        duration = format_duration(info.get('duration', 0))
        views = format_number(info.get('view_count', 0))
        channel = info.get('channel', info.get('uploader', 'نامشخص'))
        
        response = (
            f"ℹ️ <b>{truncate_text(title, 80)}</b>\n\n"
            f"📺 کانال: {channel}\n"
            f"⏱ مدت: {duration}\n"
            f"👁 بازدید: {views}\n"
            f"🔗 <code>{url}</code>"
        )
        
        await message.reply(response)
        
    except Exception as e:
        await message.reply(f"❌ خطا: {truncate_text(str(e), 200)}")

# ═══════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("dl_"))
async def handle_download_callback(callback: CallbackQuery):
    """Handle quality selection"""
    data = callback.data
    
    # Parse action and URL
    if "|" not in data:
        await callback.answer("❌ داده نامعتبر")
        return
    
    action, url = data.split("|", 1)
    
    # Map action to quality
    quality_map = {
        "dl_best": "best",
        "dl_1080p": "1080p",
        "dl_720p": "720p",
        "dl_480p": "480p",
        "dl_360p": "360p",
        "dl_audio": "audio",
    }
    
    action_key = action
    quality = quality_map.get(action_key)
    
    if not quality:
        await callback.answer("❌ گزینه نامعتبر")
        return
    
    await callback.answer("⏳ شروع دانلود...")
    await callback.message.edit_text("⏳ در حال دانلود...", reply_markup=None)
    
    if quality == "audio":
        await process_download(callback.message, url, "audio", "best", is_callback=True)
    else:
        await process_download(callback.message, url, "video", quality, is_callback=True)

@dp.callback_query(F.data.startswith("search_"))
async def handle_search_callback(callback: CallbackQuery):
    """Handle search result selection"""
    try:
        index = int(callback.data.replace("search_", ""))
    except ValueError:
        await callback.answer("❌ داده نامعتبر")
        return
    
    results = search_cache.get(callback.from_user.id, [])
    
    if not results or index >= len(results):
        await callback.answer("❌ نتایج منقضی شده. دوباره جستجو کنید.")
        return
    
    video = results[index]
    url = video.get('url', '')
    
    if not url:
        await callback.answer("❌ لینک پیدا نشد")
        return
    
    await callback.answer("⏳ آماده‌سازی...")
    
    await callback.message.edit_text(
        f"🎬 <b>{truncate_text(video.get('title', 'Video'), 80)}</b>\n\n"
        "کیفیت مورد نظر رو انتخاب کن:",
        reply_markup=quality_keyboard(url)
    )

# ═══════════════════════════════════════════════════════════════════════════
# URL HANDLER - MAIN DOWNLOAD FLOW
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.text)
async def handle_url(message: Message):
    """Handle incoming URLs"""
    text = message.text or ""
    url = extract_url(text)
    
    if not url:
        if message.chat.type == "private":
            await message.reply(
                "❌ لینکی پیدا نشد.\n\n"
                "💡 از <code>/yt</code> برای جستجو استفاده کن\n"
                "📖 <code>/help</code> برای راهنمای کامل"
            )
        return
    
    # For YouTube, show quality selection
    if is_youtube(url):
        await message.reply(
            f"🎬 <b>لینک یوتیوب</b>\n\n"
            f"کیفیت مورد نظر رو انتخاب کن:",
            reply_markup=quality_keyboard(url)
        )
    else:
        # For other platforms, download directly
        await process_download(message, url, "video", "best")

# ═══════════════════════════════════════════════════════════════════════════
# ✅ FIXED: DOWNLOAD PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════

async def process_download(
    message: Message,
    url: str,
    format_type: str = "video",
    quality: str = "best",
    is_callback: bool = False
):
    """
    Main download processor
    ✅ Fixed: duration now int, separate audio sending works
    """
    user_id = message.from_user.id
    
    # Prevent concurrent downloads
    if active_downloads.get(user_id):
        await message.reply("⏳ یک دانلود در حال انجامه. صبر کن...")
        return
    
    active_downloads[user_id] = True
    
    # Status message
    if is_callback:
        status_msg = message
    else:
        status_msg = await message.reply("⏳ در حال دانلود...")
    
    try:
        # ─── VIDEO DOWNLOAD ───
        if format_type == "video":
            # Download video
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
            
            if is_callback:
                await status_msg.edit_text("⏳ دانلود ویدیو...")
            else:
                await status_msg.edit_text("⏳ دانلود ویدیو...")
            
            vid_opts = Downloader.video_opts("", quality)
            vid_path, info, error = await Downloader.download(url, vid_opts)
            
            if error:
                await status_msg.edit_text(error)
                return
            
            if not vid_path:
                await status_msg.edit_text("❌ فایل دانلود نشد.")
                return
            
            # ✅ FIX: Convert duration to int
            title = info.get('title', 'video') if info else 'video'
            duration = safe_duration(info.get('duration', 0)) if info else 0
            file_size_mb = vid_path.stat().st_size / (1024 * 1024)
            
            # Send video
            if is_callback:
                await status_msg.edit_text("📤 آپلود ویدیو...")
            else:
                await status_msg.edit_text("📤 آپلود ویدیو...")
            
            try:
                video_file = FSInputFile(vid_path, filename=f"{truncate_text(title, 50)}.mp4")
                await message.reply_video(
                    video_file,
                    caption=(
                        f"🎬 <b>{truncate_text(title, 80)}</b>\n"
                        f"💾 حجم: {file_size_mb:.1f}MB\n"
                        f"📞 @{SUPPORT_USERNAME}"
                    ),
                    supports_streaming=True,
                    duration=duration  # ✅ Now it's always int
                )
                
                logger.info(f"✅ Video sent: {title[:50]}, duration={duration}s, size={file_size_mb:.1f}MB")
                
            except TelegramAPIError as e:
                if "duration" in str(e).lower():
                    # Fallback: send without duration
                    logger.warning(f"Duration error, retrying without duration. Value was: {duration}")
                    video_file2 = FSInputFile(vid_path, filename=f"{truncate_text(title, 50)}.mp4")
                    await message.reply_video(
                        video_file2,
                        caption=(
                            f"🎬 <b>{truncate_text(title, 80)}</b>\n"
                            f"💾 حجم: {file_size_mb:.1f}MB\n"
                            f"📞 @{SUPPORT_USERNAME}"
                        ),
                        supports_streaming=True
                        # No duration parameter
                    )
                else:
                    raise
            
            # ✅ FIXED: Also download and send audio separately
            if is_callback:
                await status_msg.edit_text("🎵 در حال استخراج صدا...")
            else:
                await status_msg.edit_text("🎵 در حال استخراج صدا...")
            
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            
            aud_opts = Downloader.audio_opts("")
            aud_path, aud_info, aud_error = await Downloader.download(url, aud_opts)
            
            if aud_path and not aud_error:
                try:
                    audio_file = FSInputFile(aud_path, filename=f"{truncate_text(title, 50)}.mp3")
                    aud_duration = safe_duration(
                        (aud_info or info or {}).get('duration', 0)
                    )
                    
                    await message.reply_audio(
                        audio_file,
                        caption=f"🎵 <b>{truncate_text(title, 80)}</b>\n📞 @{SUPPORT_USERNAME}",
                        title=title,
                        performer=(info or {}).get('channel', (info or {}).get('uploader', 'Unknown')) if info else None,
                        duration=aud_duration  # ✅ int
                    )
                    
                    logger.info(f"✅ Audio sent: {title[:50]}")
                    
                except TelegramAPIError as e:
                    if "duration" in str(e).lower():
                        # Fallback without duration
                        audio_file2 = FSInputFile(aud_path, filename=f"{truncate_text(title, 50)}.mp3")
                        await message.reply_audio(
                            audio_file2,
                            caption=f"🎵 <b>{truncate_text(title, 80)}</b>\n📞 @{SUPPORT_USERNAME}",
                            title=title,
                            performer=(info or {}).get('channel', 'Unknown') if info else None
                        )
                    else:
                        raise
                finally:
                    cleanup_file(aud_path)
            else:
                logger.warning(f"Audio extraction failed: {aud_error}")
                # Don't show error to user, video was already sent
            
            cleanup_file(vid_path)
        
        # ─── AUDIO ONLY DOWNLOAD ───
        else:
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            
            if is_callback:
                await status_msg.edit_text("⏳ دانلود صدا...")
            else:
                await status_msg.edit_text("⏳ دانلود صدا...")
            
            aud_opts = Downloader.audio_opts("")
            aud_path, info, error = await Downloader.download(url, aud_opts)
            
            if error:
                await status_msg.edit_text(error)
                return
            
            if not aud_path:
                await status_msg.edit_text("❌ فایل دانلود نشد.")
                return
            
            title = info.get('title', 'audio') if info else 'audio'
            duration = safe_duration(info.get('duration', 0)) if info else 0
            file_size_mb = aud_path.stat().st_size / (1024 * 1024)
            
            if is_callback:
                await status_msg.edit_text("📤 آپلود صدا...")
            else:
                await status_msg.edit_text("📤 آپلود صدا...")
            
            try:
                audio_file = FSInputFile(aud_path, filename=f"{truncate_text(title, 50)}.mp3")
                await message.reply_audio(
                    audio_file,
                    caption=(
                        f"🎵 <b>{truncate_text(title, 80)}</b>\n"
                        f"💾 حجم: {file_size_mb:.1f}MB\n"
                        f"📞 @{SUPPORT_USERNAME}"
                    ),
                    title=title,
                    performer=(info or {}).get('channel', (info or {}).get('uploader', 'Unknown')) if info else None,
                    duration=duration  # ✅ int
                )
                
                logger.info(f"✅ Audio sent: {title[:50]}")
                
            except TelegramAPIError as e:
                if "duration" in str(e).lower():
                    audio_file2 = FSInputFile(aud_path, filename=f"{truncate_text(title, 50)}.mp3")
                    await message.reply_audio(
                        audio_file2,
                        caption=f"🎵 <b>{truncate_text(title, 80)}</b>\n📞 @{SUPPORT_USERNAME}",
                        title=title,
                        performer=(info or {}).get('channel', 'Unknown') if info else None
                    )
                else:
                    raise
            finally:
                cleanup_file(aud_path)
        
        # Delete status message
        try:
            await status_msg.delete()
        except:
            pass
        
    except Exception as e:
        logger.exception(f"Download process error: {e}")
        error_text = f"❌ خطای غیرمنتظره:\n<code>{truncate_text(str(e), 200)}</code>\n\n📞 @{SUPPORT_USERNAME}"
        try:
            if is_callback:
                await status_msg.edit_text(error_text)
            else:
                await status_msg.edit_text(error_text)
        except:
            await message.reply(error_text)
    
    finally:
        # Cleanup
        active_downloads.pop(user_id, None)

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.errors()
async def error_handler(update, exception):
    """Global error handler"""
    logger.error(f"Update caused error: {exception}")
    
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ خطایی رخ داد. دوباره تلاش کنید.")
        elif hasattr(update, 'message') and update.message:
            await update.message.reply(f"❌ خطا:\n<code>{truncate_text(str(exception), 200)}</code>")
    except:
        pass
    
    return True

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set!")
        return
    
    logger.info("=" * 50)
    logger.info("🚀 Bot starting...")
    logger.info(f"📁 Download dir: {DOWNLOAD_DIR}")
    logger.info(f"📦 Max file size: {MAX_FILE_SIZE_MB}MB")
    logger.info(f"📞 Support: @{SUPPORT_USERNAME}")
    logger.info("=" * 50)
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
