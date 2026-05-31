#!/usr/bin/env python3
"""
🎬 Media Downloader Bot v3.0
🎯 Focused on: YouTube • Instagram • TikTok • Facebook
📡 @aeohkl - Support
✅ Fixed: Black screen, no audio, merge issues
"""

import asyncio
import os
import re
import json
import tempfile
import logging
import shutil
import time
from pathlib import Path
from datetime import timedelta
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Dispatcher, F
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

# ═══════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "aeohkl")
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "media_downloader"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# PLATFORM DETECTOR
# ═══════════════════════════════════════════════

class Platform:
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    UNKNOWN = "unknown"
    
    # تشخیص URL هر پلتفرم
    PATTERNS = {
        YOUTUBE: [
            r'(?:https?://)?(?:www\.)?(?:m\.)?youtube\.com/(?:watch\?v=|shorts/|embed/|v/)[^\s&?]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[^\s?]+',
            r'(?:https?://)?(?:www\.)?music\.youtube\.com/watch\?v=[^\s&?]+',
        ],
        INSTAGRAM: [
            r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[^\s/?]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/[^\s/?]+/(?:p|reel|tv)/[^\s/?]+',
        ],
        TIKTOK: [
            r'(?:https?://)?(?:www\.)?(?:vm\.)?tiktok\.com/[^\s/?]+',
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[^\s/?]+/video/\d+',
        ],
        FACEBOOK: [
            r'(?:https?://)?(?:www\.)?(?:fb\.watch|facebook\.com)/(?:watch|reel|share|videos)/[^\s/?]+',
            r'(?:https?://)?(?:www\.)?(?:fb\.watch|facebook\.com)/[^\s/?]+/videos/[^\s/?]+',
            r'(?:https?://)?(?:www\.)?facebook\.com/\d+/videos/[^\s/?]+',
        ],
    }
    
    EMOJIS = {
        YOUTUBE: "🎬",
        INSTAGRAM: "📸",
        TIKTOK: "🎵",
        FACEBOOK: "👤",
        UNKNOWN: "🔗",
    }
    
    NAMES = {
        YOUTUBE: "YouTube",
        INSTAGRAM: "Instagram",
        TIKTOK: "TikTok",
        FACEBOOK: "Facebook",
        UNKNOWN: "Unknown",
    }

    @classmethod
    def detect(cls, url: str) -> str:
        """تشخیص پلتفرم از روی URL"""
        for platform, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return cls.UNKNOWN
    
    @classmethod
    def extract_url(cls, text: str) -> Optional[str]:
        """استخراج URL از متن"""
        # الگوی کلی URL
        url_pattern = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)
        match = url_pattern.search(text)
        return match.group(0) if match else None

# ═══════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════

def safe_int(value) -> int:
    """✅ تبدیل امن به int برای duration (رفع خطای fractional part)"""
    if value is None:
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def format_size(bytes_val) -> str:
    """فرمت حجم فایل"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def format_duration(seconds) -> str:
    """فرمت مدت زمان"""
    try:
        return str(timedelta(seconds=int(float(seconds))))
    except:
        return "N/A"

def truncate(text: str, max_len: int = 80) -> str:
    """کوتاه کردن متن"""
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len-3] + "..."

def sanitize_filename(text: str) -> str:
    """پاکسازی نام فایل از کاراکترهای غیرمجاز"""
    if not text:
        return "media"
    # حذف کاراکترهای غیرمجاز
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    # محدود کردن طول
    return text[:80]

def cleanup(path: Path):
    """حذف امن فایل"""
    try:
        if path and path.exists():
            path.unlink(missing_ok=True)
    except:
        pass

# ═══════════════════════════════════════════════
# YOUTUBE SEARCH
# ═══════════════════════════════════════════════

async def search_youtube(query: str, max_results: int = 5) -> List[Dict]:
    """جستجوی یوتیوب"""
    try:
        url = "https://www.youtube.com/results"
        params = {'search_query': query}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                html = await resp.text()
        
        # Extract ytInitialData
        pattern = re.compile(r'var ytInitialData = (.*?);</script>', re.DOTALL)
        match = pattern.search(html)
        if not match:
            return []
        
        data = json.loads(match.group(1))
        results = []
        
        # Navigate JSON
        contents = (data.get('contents', {})
                   .get('twoColumnSearchResultsRenderer', {})
                   .get('primaryContents', {})
                   .get('sectionListRenderer', {})
                   .get('contents', []))
        
        for section in contents:
            items = section.get('itemSectionRenderer', {}).get('contents', [])
            for item in items:
                video = item.get('videoRenderer')
                if not video:
                    continue
                
                vid = video.get('videoId', '')
                if not vid:
                    continue
                
                results.append({
                    'id': vid,
                    'url': f'https://youtube.com/watch?v={vid}',
                    'title': video.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                    'duration': video.get('lengthText', {}).get('simpleText', 'N/A'),
                    'views': video.get('viewCountText', {}).get('simpleText', '0'),
                    'channel': video.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# ═══════════════════════════════════════════════
# DOWNLOADER - ✅ FIXED FOR 4 PLATFORMS
# ═══════════════════════════════════════════════

class Downloader:
    """دانلودر بهینه‌شده برای ۴ پلتفرم"""
    
    # کوکی‌ها برای اینستاگرام و فیسبوک (اختیاری - کمک به دانلود بهتر)
    COOKIES_FILE = None  # می‌تونی فایل cookies.txt بدی
    
    @classmethod
    def _get_base_opts(cls, platform: str) -> dict:
        """تنظیمات پایه برای هر پلتفرم"""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "no_color": True,
            "no_progress": True,
            "ffmpeg_location": FFMPEG_PATH,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        }
        
        # تنظیمات خاص هر پلتفرم
        if platform == Platform.INSTAGRAM:
            opts.update({
                "extractor_args": {
                    "instagram": {
                        "include_headers": True,
                    }
                },
                # تلاش برای دانلود با کیفیت اصلی
                "format_sort": ["res:1080", "codec:h264"],
            })
        elif platform == Platform.FACEBOOK:
            opts.update({
                "extractor_args": {
                    "facebook": {
                        "include_headers": True,
                    }
                },
                "format_sort": ["res:1080", "codec:h264"],
            })
        elif platform == Platform.TIKTOK:
            opts.update({
                "format_sort": ["res:1080", "codec:h264"],
            })
        
        # اضافه کردن کوکی اگه موجود باشه
        if cls.COOKIES_FILE and os.path.exists(cls.COOKIES_FILE):
            opts["cookiefile"] = cls.COOKIES_FILE
        
        return opts
    
    @classmethod
    def _get_video_opts(cls, platform: str, output_path: str, quality: str = "best") -> dict:
        """
        ✅ تنظیمات ویدیو برای رفع مشکل تصویر سیاه و بی‌صدایی
        - کدک h264 برای سازگاری با تلگرام
        - مرج کردن video+audio
        - فرمت mp4
        """
        base = cls._get_base_opts(platform)
        
        # انتخاب کیفیت
        quality_map = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
            "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
            "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
            "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
        }
        
        video_opts = {
            **base,
            "format": quality_map.get(quality, quality_map["best"]),
            "outtmpl": output_path,
            "merge_output_format": "mp4",
            # ✅ کلید رفع مشکلات:
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                },
                {
                    "key": "FFmpegFixupM3u8",
                },
                {
                    "key": "FFmpegFixupM4a",
                },
            ],
            # ✅ اولویت با کدک‌های سازگار با تلگرام
            "format_sort": [
                "codec:h264",      # تلگرام h264 رو خوب پخش میکنه
                "ext:mp4",         # فرمت mp4
                "res:1080",        # حداکثر 1080p
                "hasaud",          # حتماً صدا داشته باشه
            ],
            # ❌ اینو نمی‌خوایم - باعث قطع شدن صدا میشه
            "extract_audio": False,
        }
        
        return video_opts
    
    @classmethod
    def _get_audio_opts(cls, platform: str, output_path: str) -> dict:
        """تنظیمات دانلود صدا"""
        base = cls._get_base_opts(platform)
        
        return {
            **base,
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    
    @classmethod
    async def download_video(
        cls,
        url: str,
        platform: str,
        quality: str = "best"
    ) -> Tuple[Optional[Path], Optional[dict], Optional[str]]:
        """دانلود ویدیو"""
        return await cls._download(url, platform, "video", quality)
    
    @classmethod
    async def download_audio(
        cls,
        url: str,
        platform: str
    ) -> Tuple[Optional[Path], Optional[dict], Optional[str]]:
        """دانلود صدا"""
        return await cls._download(url, platform, "audio", "best")
    
    @classmethod
    async def _download(
        cls,
        url: str,
        platform: str,
        media_type: str,
        quality: str = "best"
    ) -> Tuple[Optional[Path], Optional[dict], Optional[str]]:
        """
        دانلود اصلی
        Returns: (file_path, info_dict, error_message)
        """
        # ساخت فایل موقت
        suffix = ".mp3" if media_type == "audio" else ".mp4"
        with tempfile.NamedTemporaryFile(dir=DOWNLOAD_DIR, delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
        
        # حذف فایل موقت (yt-dlp خودش فایل نهایی رو میسازه)
        Path(temp_path).unlink(missing_ok=True)
        output_template = str(Path(temp_path).with_suffix(""))
        
        # تنظیمات
        if media_type == "audio":
            opts = cls._get_audio_opts(platform, output_template)
        else:
            opts = cls._get_video_opts(platform, output_template, quality)
        
        # اضافه کردن پسوند به خروجی
        opts["outtmpl"] = output_template + ".%(ext)s"
        
        try:
            loop = asyncio.get_event_loop()
            
            def _run():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=True)
            
            info = await loop.run_in_executor(None, _run)
            
            # پیدا کردن فایل دانلود شده
            pattern = f"{Path(output_template).name}*"
            files = [
                f for f in DOWNLOAD_DIR.glob(pattern)
                if f.stat().st_size > 0 and not f.name.endswith('.part') and not f.name.endswith('.ytdl')
            ]
            
            # حذف فایل‌های خالی و موقت
            for f in DOWNLOAD_DIR.glob(pattern):
                if f.stat().st_size == 0 or f.name.endswith(('.part', '.ytdl')):
                    f.unlink(missing_ok=True)
            
            if not files:
                return None, None, "❌ فایل دانلود نشد."
            
            # بزرگترین فایل
            file_path = max(files, key=lambda f: f.stat().st_size)
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            # ✅ بررسی اینکه فایل واقعاً قابل پخش باشه
            if media_type == "video" and file_path.suffix == ".mp4":
                # چک کردن داشتن video stream
                has_video = cls._check_video_stream(file_path)
                if not has_video:
                    return None, None, "❌ فایل ویدیو معتبر نیست (بدون video stream)."
            
            if size_mb > MAX_FILE_SIZE_MB:
                file_path.unlink(missing_ok=True)
                return None, info, (
                    f"❌ حجم فایل ({size_mb:.1f}MB) از حد مجاز "
                    f"({MAX_FILE_SIZE_MB}MB) بیشتر است.\n"
                    f"💡 کیفیت پایین‌تر رو انتخاب کنید.\n"
                    f"📞 @{SUPPORT_USERNAME}"
                )
            
            logger.info(f"✅ Downloaded: {file_path.name}, size={size_mb:.1f}MB, platform={platform}")
            return file_path, info, None
            
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).lower()
            if "sign in" in msg:
                return None, None, (
                    f"❌ {Platform.NAMES.get(platform, 'این پلتفرم')} نیاز به لاگین دارد.\n"
                    f"📞 @{SUPPORT_USERNAME}"
                )
            elif "private" in msg:
                return None, None, "❌ این محتوا خصوصی است."
            elif "not available" in msg or "unavailable" in msg:
                return None, None, "❌ محتوا در دسترس نیست (حذف شده یا محدودیت منطقه‌ای)."
            elif "copyright" in msg:
                return None, None, "❌ محتوا به دلیل کپی‌رایت قابل دانلود نیست."
            else:
                return None, None, f"❌ خطای دانلود:\n{truncate(str(e), 200)}"
        except Exception as e:
            logger.exception(f"Download error: {e}")
            return None, None, f"❌ خطا:\n{truncate(str(e), 150)}"
    
    @classmethod
    def _check_video_stream(cls, file_path: Path) -> bool:
        """✅ بررسی وجود video stream در فایل"""
        try:
            import subprocess
            result = subprocess.run(
                [FFMPEG_PATH, "-i", str(file_path)],
                capture_output=True, text=True, timeout=10
            )
            # چک کردن خروجی برای Video stream
            stderr = result.stderr.lower()
            return "video:" in stderr
        except:
            return True  # اگه نتونستیم چک کنیم، فرض می‌کنیم درسته

# ═══════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════

def quality_keyboard(url: str, platform: str) -> InlineKeyboardMarkup:
    """کیبورد انتخاب کیفیت"""
    builder = InlineKeyboardBuilder()
    
    if platform == Platform.YOUTUBE:
        buttons = [
            ("🎯 بهترین کیفیت", f"q_best|{url}"),
            ("📺 1080p Full HD", f"q_1080p|{url}"),
            ("📱 720p HD", f"q_720p|{url}"),
            ("💾 480p", f"q_480p|{url}"),
            ("📦 360p", f"q_360p|{url}"),
            ("🎵 فقط صدا MP3", f"q_audio|{url}"),
        ]
    else:
        buttons = [
            ("🎯 بهترین کیفیت", f"q_best|{url}"),
            ("🎵 فقط صدا MP3", f"q_audio|{url}"),
        ]
    
    for text, callback in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback[:64]))
    
    builder.adjust(2)
    
    # دکمه پشتیبانی
    builder.row(InlineKeyboardButton(
        text=f"📞 پشتیبانی @{SUPPORT_USERNAME}",
        url=f"https://t.me/{SUPPORT_USERNAME}"
    ))
    
    return builder.as_markup()

def search_keyboard(results: List[Dict]) -> InlineKeyboardMarkup:
    """کیبورد نتایج جستجو"""
    builder = InlineKeyboardBuilder()
    
    for i, video in enumerate(results[:5]):
        title = truncate(video.get('title', 'No Title'), 35)
        duration = video.get('duration', 'N/A')
        builder.add(InlineKeyboardButton(
            text=f"{i+1}. {title} ⏱{duration}",
            callback_data=f"s_{i}"
        ))
    
    builder.adjust(1)
    return builder.as_markup()

# ═══════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Cache
search_cache: Dict[int, List[Dict]] = {}
active_downloads: Dict[int, bool] = {}

# ═══════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"👋 سلام <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>دانلودر حرفه‌ای مدیا</b>\n\n"
        "🎯 <b>پلتفرم‌های پشتیبانی شده:</b>\n"
        "• 🎬 YouTube - ویدیو + صدا\n"
        "• 📸 Instagram - پست، ریلز، استوری\n"
        "• 🎵 TikTok - بدون واترمارک\n"
        "• 👤 Facebook - ویدیو و ریلز\n\n"
        "📥 <b>روش استفاده:</b>\n"
        "• لینک رو بفرست ← دانلود خودکار\n"
        "• <code>/yt متن</code> ← جستجوی یوتیوب\n"
        "• <code>/audio لینک</code> ← فقط صدا\n"
        "• <code>/formats لینک</code> ← انتخاب کیفیت\n\n"
        f"📞 <b>پشتیبانی:</b> @{SUPPORT_USERNAME}\n"
        f"📦 <b>حداکثر حجم:</b> {MAX_FILE_SIZE_MB}MB"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>راهنمای کامل</b>\n\n"
        "🎬 <b>YouTube:</b>\n"
        "• لینک معمولی، Shorts، Music\n"
        "• انتخاب کیفیت 360p تا 1080p\n"
        "• جستجو با <code>/yt</code>\n\n"
        "📸 <b>Instagram:</b>\n"
        "• پست، Reels، TV\n"
        "• دانلود با بهترین کیفیت\n\n"
        "🎵 <b>TikTok:</b>\n"
        "• بدون واترمارک\n"
        "• با صدا\n\n"
        "👤 <b>Facebook:</b>\n"
        "• ویدیو، Reels، Watch\n"
        "• کیفیت HD\n\n"
        f"📞 <b>پشتیبانی:</b> @{SUPPORT_USERNAME}"
    )

@dp.message(Command("yt"))
async def cmd_youtube_search(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("🔍 مثال:\n<code>/yt آهنگ جدید</code>")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    results = await search_youtube(command.args, 5)
    
    if not results:
        await message.reply("❌ نتیجه‌ای پیدا نشد.")
        return
    
    search_cache[message.from_user.id] = results
    
    text = f"🔍 نتایج: <b>{command.args}</b>\n\n"
    for i, v in enumerate(results, 1):
        text += (
            f"{i}️⃣ <b>{truncate(v['title'], 50)}</b>\n"
            f"   📺 {v['channel']} | ⏱ {v['duration']} | 👁 {v['views']}\n"
            f"   🔗 <code>{v['url']}</code>\n\n"
        )
    
    text += "👇 لینک رو کپی کن یا دکمه رو بزن"
    
    await message.reply(
        text,
        reply_markup=search_keyboard(results),
        disable_web_page_preview=True
    )

@dp.message(Command("audio"))
async def cmd_audio(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("🎵 مثال:\n<code>/audio https://youtube.com/watch?v=...</code>")
        return
    
    url = Platform.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await process_download(message, url, "audio", "best")

@dp.message(Command("formats"))
async def cmd_formats(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("🎬 مثال:\n<code>/formats لینک</code>")
        return
    
    url = Platform.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    platform = Platform.detect(url)
    
    await message.reply(
        f"{Platform.EMOJIS[platform]} <b>{Platform.NAMES[platform]}</b>\n\n"
        "کیفیت رو انتخاب کن:",
        reply_markup=quality_keyboard(url, platform)
    )

# ═══════════════════════════════════════════════
# URL HANDLER
# ═══════════════════════════════════════════════

@dp.message(F.text)
async def handle_url(message: Message):
    """پردازش لینک‌های ورودی"""
    text = message.text or ""
    url = Platform.extract_url(text)
    
    if not url:
        if message.chat.type == "private":
            await message.reply(
                "❌ لینکی پیدا نشد.\n\n"
                "🎯 <b>پلتفرم‌های پشتیبانی شده:</b>\n"
                "🎬 YouTube | 📸 Instagram\n"
                "🎵 TikTok | 👤 Facebook\n\n"
                "💡 <code>/yt</code> جستجوی یوتیوب\n"
                "📖 <code>/help</code> راهنما"
            )
        return
    
    platform = Platform.detect(url)
    
    if platform == Platform.UNKNOWN:
        await message.reply(
            "❌ این پلتفرم پشتیبانی نمیشه.\n\n"
            "🎯 <b>فقط این ۴ پلتفرم:</b>\n"
            "🎬 YouTube\n"
            "📸 Instagram\n"
            "🎵 TikTok\n"
            "👤 Facebook\n\n"
            f"📞 @{SUPPORT_USERNAME}"
        )
        return
    
    # نشون دادن کیبورد کیفیت
    await message.reply(
        f"{Platform.EMOJIS[platform]} <b>{Platform.NAMES[platform]}</b>\n\n"
        f"🔗 <code>{truncate(url, 60)}</code>\n\n"
        "کیفیت رو انتخاب کن:",
        reply_markup=quality_keyboard(url, platform)
    )

# ═══════════════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════════════

@dp.callback_query(F.data.startswith("q_"))
async def handle_quality(callback: CallbackQuery):
    """هندل کردن انتخاب کیفیت"""
    data = callback.data
    
    if "|" not in data:
        await callback.answer("❌ خطا")
        return
    
    action, url = data.split("|", 1)
    
    quality_map = {
        "q_best": "best",
        "q_1080p": "1080p",
        "q_720p": "720p",
        "q_480p": "480p",
        "q_360p": "360p",
        "q_audio": "audio",
    }
    
    quality = quality_map.get(action)
    if not quality:
        await callback.answer("❌ گزینه نامعتبر")
        return
    
    await callback.answer("⏳ شروع دانلود...")
    await callback.message.edit_text("⏳ در حال دانلود...", reply_markup=None)
    
    if quality == "audio":
        await process_download(callback.message, url, "audio", "best", is_callback=True)
    else:
        await process_download(callback.message, url, "video", quality, is_callback=True)

@dp.callback_query(F.data.startswith("s_"))
async def handle_search(callback: CallbackQuery):
    """هندل کردن انتخاب از نتایج جستجو"""
    try:
        index = int(callback.data.replace("s_", ""))
    except:
        await callback.answer("❌ خطا")
        return
    
    results = search_cache.get(callback.from_user.id, [])
    if not results or index >= len(results):
        await callback.answer("❌ نتایج منقضی شده. دوباره جستجو کن.")
        return
    
    video = results[index]
    url = video.get('url', '')
    
    await callback.answer("⏳ آماده‌سازی...")
    await callback.message.edit_text(
        f"🎬 <b>{truncate(video.get('title', 'Video'), 70)}</b>\n\n"
        "کیفیت رو انتخاب کن:",
        reply_markup=quality_keyboard(url, Platform.YOUTUBE)
    )

# ═══════════════════════════════════════════════
# MAIN DOWNLOAD PROCESSOR
# ═══════════════════════════════════════════════

async def process_download(
    message: Message,
    url: str,
    media_type: str = "video",
    quality: str = "best",
    is_callback: bool = False
):
    """
    ✅ پردازش اصلی دانلود
    - رفع مشکل تصویر سیاه
    - رفع مشکل بی‌صدایی
    - ارسال صدا جداگانه برای یوتیوب
    """
    user_id = message.from_user.id
    platform = Platform.detect(url)
    
    # جلوگیری از دانلود همزمان
    if active_downloads.get(user_id):
        await message.reply("⏳ یه دانلود در حال انجامه. صبر کن...")
        return
    
    active_downloads[user_id] = True
    
    # پیام وضعیت
    if is_callback:
        status = message
    else:
        status = await message.reply("⏳ در حال دانلود...")
    
    try:
        emoji = Platform.EMOJIS[platform]
        platform_name = Platform.NAMES[platform]
        
        # ─── دانلود ویدیو ───
        if media_type == "video":
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
            
            if is_callback:
                await status.edit_text(f"⏳ دانلود از {platform_name}...")
            else:
                await status.edit_text(f"⏳ دانلود از {platform_name}...")
            
            file_path, info, error = await Downloader.download_video(url, platform, quality)
            
            if error:
                await status.edit_text(error)
                return
            
            if not file_path:
                await status.edit_text("❌ فایل دانلود نشد.")
                return
            
            title = info.get('title', 'video') if info else 'video'
            duration = safe_int((info or {}).get('duration', 0))
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            # آپلود ویدیو
            if is_callback:
                await status.edit_text("📤 آپلود ویدیو...")
            else:
                await status.edit_text("📤 آپلود ویدیو...")
            
            try:
                filename = f"{sanitize_filename(title)}.mp4"
                video_file = FSInputFile(file_path, filename=filename)
                
                await message.reply_video(
                    video_file,
                    caption=(
                        f"{emoji} <b>{truncate(title, 80)}</b>\n"
                        f"📺 {platform_name}\n"
                        f"💾 {size_mb:.1f}MB | ⏱ {format_duration(duration)}\n"
                        f"📞 @{SUPPORT_USERNAME}"
                    ),
                    supports_streaming=True,
                    duration=duration
                )
                
                logger.info(f"✅ Video sent: {title[:50]}, platform={platform}")
                
            except TelegramAPIError as e:
                if "duration" in str(e):
                    # Fallback بدون duration
                    video_file2 = FSInputFile(file_path, filename=filename)
                    await message.reply_video(
                        video_file2,
                        caption=(
                            f"{emoji} <b>{truncate(title, 80)}</b>\n"
                            f"📺 {platform_name}\n"
                            f"💾 {size_mb:.1f}MB\n"
                            f"📞 @{SUPPORT_USERNAME}"
                        ),
                        supports_streaming=True
                    )
                else:
                    raise
            
            # ─── ارسال صدا جداگانه (فقط برای یوتیوب) ───
            if platform == Platform.YOUTUBE:
                if is_callback:
                    await status.edit_text("🎵 استخراج صدا...")
                else:
                    await status.edit_text("🎵 استخراج صدا...")
                
                await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
                
                aud_path, aud_info, aud_error = await Downloader.download_audio(url, platform)
                
                if aud_path and not aud_error:
                    try:
                        audio_file = FSInputFile(aud_path, filename=f"{sanitize_filename(title)}.mp3")
                        aud_duration = safe_int((aud_info or info or {}).get('duration', 0))
                        
                        await message.reply_audio(
                            audio_file,
                            caption=(
                                f"🎵 <b>{truncate(title, 80)}</b>\n"
                                f"📞 @{SUPPORT_USERNAME}"
                            ),
                            title=title,
                            performer=(info or {}).get('channel') or (info or {}).get('uploader') or platform_name,
                            duration=aud_duration
                        )
                        
                        logger.info(f"✅ Audio sent: {title[:50]}")
                        
                    except TelegramAPIError as e:
                        if "duration" in str(e):
                            audio_file2 = FSInputFile(aud_path, filename=f"{sanitize_filename(title)}.mp3")
                            await message.reply_audio(
                                audio_file2,
                                caption=f"🎵 <b>{truncate(title, 80)}</b>\n📞 @{SUPPORT_USERNAME}",
                                title=title,
                                performer=(info or {}).get('channel') or platform_name
                            )
                    finally:
                        cleanup(aud_path)
            
            # پاکسازی
            cleanup(file_path)
        
        # ─── دانلود فقط صدا ───
        else:
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            
            if is_callback:
                await status.edit_text(f"⏳ دانلود صدا از {platform_name}...")
            else:
                await status.edit_text(f"⏳ دانلود صدا از {platform_name}...")
            
            file_path, info, error = await Downloader.download_audio(url, platform)
            
            if error:
                await status.edit_text(error)
                return
            
            if not file_path:
                await status.edit_text("❌ فایل دانلود نشد.")
                return
            
            title = info.get('title', 'audio') if info else 'audio'
            duration = safe_int((info or {}).get('duration', 0))
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if is_callback:
                await status.edit_text("📤 آپلود صدا...")
            else:
                await status.edit_text("📤 آپلود صدا...")
            
            try:
                audio_file = FSInputFile(file_path, filename=f"{sanitize_filename(title)}.mp3")
                
                await message.reply_audio(
                    audio_file,
                    caption=(
                        f"🎵 <b>{truncate(title, 80)}</b>\n"
                        f"📺 {platform_name}\n"
                        f"💾 {size_mb:.1f}MB | ⏱ {format_duration(duration)}\n"
                        f"📞 @{SUPPORT_USERNAME}"
                    ),
                    title=title,
                    performer=(info or {}).get('channel') or (info or {}).get('uploader') or platform_name,
                    duration=duration
                )
                
                logger.info(f"✅ Audio sent: {title[:50]}")
                
            except TelegramAPIError as e:
                if "duration" in str(e):
                    audio_file2 = FSInputFile(file_path, filename=f"{sanitize_filename(title)}.mp3")
                    await message.reply_audio(
                        audio_file2,
                        caption=f"🎵 <b>{truncate(title, 80)}</b>\n📞 @{SUPPORT_USERNAME}",
                        title=title,
                        performer=(info or {}).get('channel') or platform_name
                    )
            finally:
                cleanup(file_path)
        
        # حذف پیام وضعیت
        try:
            await status.delete()
        except:
            pass
        
    except Exception as e:
        logger.exception(f"Process error: {e}")
        error_msg = f"❌ خطا:\n<code>{truncate(str(e), 200)}</code>\n\n📞 @{SUPPORT_USERNAME}"
        try:
            await status.edit_text(error_msg)
        except:
            await message.reply(error_msg)
    
    finally:
        active_downloads.pop(user_id, None)

# ═══════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════

@dp.errors()
async def error_handler(update, exception):
    logger.error(f"Global error: {exception}")
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ خطا. دوباره تلاش کن.")
    except:
        pass
    return True

# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set!")
        return
    
    logger.info("=" * 50)
    logger.info("🚀 Bot starting...")
    logger.info(f"📁 Downloads: {DOWNLOAD_DIR}")
    logger.info(f"📦 Max size: {MAX_FILE_SIZE_MB}MB")
    logger.info(f"🎯 Platforms: YouTube, Instagram, TikTok, Facebook")
    logger.info(f"📞 Support: @{SUPPORT_USERNAME}")
    logger.info("=" * 50)
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
