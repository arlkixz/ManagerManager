#!/usr/bin/env python3
"""
🎬 Advanced Media Downloader Bot
📡 @aeohkl - Support & Updates
"""

import asyncio
import os
import re
import json
import tempfile
import logging
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

import aiohttp
import aiofiles
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery, InputMediaVideo,
    InputMediaAudio, BufferedInputFile
)
from aiogram.filters import CommandStart, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
import yt_dlp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """Application configuration"""
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "aeohkl")
    DOWNLOAD_DIR: Path = Path(tempfile.gettempdir()) / "media_downloader_bot"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # seconds
    ALLOWED_CHAT_TYPES: List[str] = field(default_factory=lambda: ["private", "group", "supergroup"])
    
    def __post_init__(self):
        self.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

config = Config()

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.DOWNLOAD_DIR / "bot.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class UserStats:
    """User statistics tracking"""
    downloads: int = 0
    total_size_mb: float = 0.0
    last_download: float = 0.0
    search_count: int = 0
    
    @property
    def can_download(self) -> bool:
        """Rate limiting check"""
        if time.time() - self.last_download < config.RATE_LIMIT_PERIOD:
            return False
        return True

@dataclass
class DownloadTask:
    """Download task information"""
    url: str
    quality: str = "best"
    format_type: str = "video"  # video/audio
    start_time: float = field(default_factory=time.time)
    status: str = "pending"

# ═══════════════════════════════════════════════════════════════════════════
# URL & PLATFORM DETECTION
# ═══════════════════════════════════════════════════════════════════════════

class PlatformDetector:
    """Detect and parse URLs from different platforms"""
    
    URL_PATTERN = re.compile(
        r'(https?://[^\s]+)',
        re.IGNORECASE
    )
    
    PLATFORMS = {
        'youtube': [
            r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)',
            r'(?:https?://)?(?:www\.)?(?:m\.)?youtube\.com/shorts'
        ],
        'instagram': [
            r'(?:https?://)?(?:www\.)?instagram\.com',
        ],
        'tiktok': [
            r'(?:https?://)?(?:www\.)?(?:vm\.)?tiktok\.com',
        ],
        'twitter': [
            r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)',
        ],
        'facebook': [
            r'(?:https?://)?(?:www\.)?(?:fb\.watch|facebook\.com)',
        ],
        'soundcloud': [
            r'(?:https?://)?(?:www\.)?soundcloud\.com',
        ],
        'reddit': [
            r'(?:https?://)?(?:www\.)?(?:v\.)?reddit\.com',
        ],
        'telegram': [
            r'(?:https?://)?(?:www\.)?t\.me',
        ],
        'pinterest': [
            r'(?:https?://)?(?:www\.)?(?:pin\.it|pinterest\.com)',
        ],
        'vimeo': [
            r'(?:https?://)?(?:www\.)?vimeo\.com',
        ],
        'dailymotion': [
            r'(?:https?://)?(?:www\.)?dailymotion\.com',
        ],
        'twitch': [
            r'(?:https?://)?(?:www\.)?(?:clips\.)?twitch\.tv',
        ],
        'aparat': [
            r'(?:https?://)?(?:www\.)?aparat\.com',
        ],
        'namasha': [
            r'(?:https?://)?(?:www\.)?namasha\.com',
        ],
    }
    
    @classmethod
    def extract_url(cls, text: str) -> Optional[str]:
        """Extract first URL from text"""
        match = cls.URL_PATTERN.search(text)
        return match.group(0) if match else None
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """Detect platform from URL"""
        for platform, patterns in cls.PLATFORMS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return None
    
    @classmethod
    def get_platform_emoji(cls, platform: str) -> str:
        """Get platform emoji icon"""
        emojis = {
            'youtube': '🎬',
            'instagram': '📸',
            'tiktok': '🎵',
            'twitter': '🐦',
            'facebook': '👤',
            'soundcloud': '☁️',
            'reddit': '🤖',
            'telegram': '✈️',
            'pinterest': '📌',
            'vimeo': '🎥',
            'dailymotion': '▶️',
            'twitch': '🎮',
            'aparat': '📺',
            'namasha': '🎞️',
        }
        return emojis.get(platform, '🔗')

# ═══════════════════════════════════════════════════════════════════════════
# CACHE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

class CacheManager:
    """Simple in-memory cache with TTL"""
    
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = config.CACHE_TTL
        self._cache[key] = (value, time.time() + ttl)
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()

# ═══════════════════════════════════════════════════════════════════════════
# YOUTUBE SEARCH (بدون نیاز به کتابخانه اضافی)
# ═══════════════════════════════════════════════════════════════════════════

class YouTubeSearcher:
    """Search YouTube without external libraries"""
    
    SEARCH_URL = "https://www.youtube.com/results"
    
    @staticmethod
    def _extract_video_data(html: str) -> List[Dict]:
        """Extract video data from YouTube search HTML"""
        results = []
        
        # Pattern for initial data in YouTube search results
        data_pattern = re.compile(r'var ytInitialData = (.*?);</script>', re.DOTALL)
        match = data_pattern.search(html)
        
        if not match:
            return results
        
        try:
            data = json.loads(match.group(1))
            
            # Navigate through YouTube's complex JSON structure
            contents = (data.get('contents', {})
                       .get('twoColumnSearchResultsRenderer', {})
                       .get('primaryContents', {})
                       .get('sectionListRenderer', {})
                       .get('contents', []))
            
            for section in contents:
                items = (section.get('itemSectionRenderer', {})
                        .get('contents', []))
                
                for item in items:
                    video_renderer = item.get('videoRenderer')
                    if not video_renderer:
                        continue
                    
                    video_id = video_renderer.get('videoId', '')
                    if not video_id:
                        continue
                    
                    title = (video_renderer.get('title', {})
                            .get('runs', [{}])[0].get('text', 'Unknown'))
                    
                    duration = (video_renderer.get('lengthText', {})
                               .get('simpleText', 'N/A'))
                    
                    views = (video_renderer.get('viewCountText', {})
                            .get('simpleText', '0 views'))
                    
                    channel = (video_renderer.get('ownerText', {})
                              .get('runs', [{}])[0].get('text', 'Unknown'))
                    
                    thumbnails = video_renderer.get('thumbnail', {}).get('thumbnails', [])
                    thumbnail = thumbnails[-1].get('url', '') if thumbnails else ''
                    
                    results.append({
                        'id': video_id,
                        'url': f'https://youtube.com/watch?v={video_id}',
                        'title': title,
                        'duration': duration,
                        'views': views,
                        'channel': channel,
                        'thumbnail': thumbnail,
                    })
                    
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Error parsing YouTube data: {e}")
        
        return results
    
    @staticmethod
    async def search(query: str, max_results: int = 5) -> List[Dict]:
        """Search YouTube videos"""
        try:
            params = {
                'search_query': query,
                'sp': 'CAASAhAE%3D',  # Filter for videos only
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    YouTubeSearcher.SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=10
                ) as response:
                    html = await response.text()
                    results = YouTubeSearcher._extract_video_data(html)
                    return results[:max_results]
                    
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return []

# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOAD MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class DownloadManager:
    """Advanced download manager with yt-dlp"""
    
    BASE_OPTIONS = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "no_color": True,
        "no_progress": True,
        "rm_cachedir": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    
    QUALITY_FORMATS = {
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "2160p": "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160][ext=mp4]",
        "1440p": "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440][ext=mp4]",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
        "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
        "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
        "240p": "bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240][ext=mp4]",
        "144p": "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/best[height<=144][ext=mp4]",
    }
    
    @staticmethod
    def get_video_options(output_path: str, quality: str = "best") -> dict:
        """Get video download options"""
        format_str = DownloadManager.QUALITY_FORMATS.get(
            quality,
            DownloadManager.QUALITY_FORMATS["best"]
        )
        
        return {
            **DownloadManager.BASE_OPTIONS,
            "format": format_str,
            "outtmpl": output_path,
            "merge_output_format": "mp4",
            "postprocessors": [{
                "key": "FFmpegFixupM4a",
            }] if quality != "best" else [],
        }
    
    @staticmethod
    def get_audio_options(output_path: str, quality: str = "192") -> dict:
        """Get audio download options"""
        return {
            **DownloadManager.BASE_OPTIONS,
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }],
        }
    
    @staticmethod
    def get_info_options() -> dict:
        """Get info extraction options"""
        return {
            **DownloadManager.BASE_OPTIONS,
            "format": "best",
            "skip_download": True,
            "writeinfojson": False,
        }
    
    @staticmethod
    async def download(
        url: str,
        options: dict,
        download_dir: Path
    ) -> Tuple[Optional[Path], Optional[dict], Optional[str]]:
        """
        Download media file
        Returns: (file_path, info_dict, error_message)
        """
        with tempfile.NamedTemporaryFile(dir=download_dir, delete=False, suffix="") as tmp:
            base_path = tmp.name
        
        options = {**options, "outtmpl": base_path + ".%(ext)s"}
        
        try:
            loop = asyncio.get_event_loop()
            
            def _download():
                with yt_dlp.YoutubeDL(options) as ydl:
                    return ydl.extract_info(url, download=True)
            
            info = await loop.run_in_executor(None, _download)
            
            # Find downloaded files
            pattern = f"{Path(base_path).name}*"
            files = [
                f for f in download_dir.glob(pattern)
                if f.stat().st_size > 0
            ]
            
            # Clean empty files
            for f in download_dir.glob(pattern):
                if f.stat().st_size == 0:
                    f.unlink(missing_ok=True)
            
            if not files:
                return None, None, "❌ فایل دانلود نشد یا خالی بود."
            
            # Get largest file
            file_path = max(files, key=lambda f: f.stat().st_size)
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if size_mb > config.MAX_FILE_SIZE_MB:
                file_path.unlink(missing_ok=True)
                return None, info, (
                    f"❌ حجم فایل ({size_mb:.1f}MB) از حد مجاز "
                    f"({config.MAX_FILE_SIZE_MB}MB) بیشتر است.\n\n"
                    f"💡 راه حل:\n"
                    f"• از کیفیت پایین‌تر استفاده کنید\n"
                    f"• با پشتیبانی تماس بگیرید: @{config.SUPPORT_USERNAME}"
                )
            
            return file_path, info, None
            
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            
            if "sign in" in error_msg or "bot" in error_msg:
                return None, None, (
                    "❌ یوتیوب نیاز به احراز هویت دارد.\n\n"
                    "🔄 لینک معمولی بفرستید (نه Shorts)\n"
                    f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}"
                )
            elif "private" in error_msg:
                return None, None, "❌ این محتوا خصوصی است و قابل دانلود نیست."
            elif "not available" in error_msg or "unavailable" in error_msg:
                return None, None, (
                    "❌ این محتوا در دسترس نیست.\n"
                    "• ممکن است حذف شده باشد\n"
                    "• یا در منطقه شما مسدود باشد\n"
                    f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}"
                )
            elif "copyright" in error_msg:
                return None, None, "❌ این محتوا به دلیل کپی‌رایت قابل دانلود نیست."
            elif "age" in error_msg:
                return None, None, "❌ این محتوا محدودیت سنی دارد."
            else:
                return None, None, f"❌ خطا در دانلود:\n`{str(e)[:200]}`"
                
        except Exception as e:
            logger.exception("Unexpected download error")
            return None, None, (
                f"❌ خطای غیرمنتظره:\n`{str(e)[:150]}`\n\n"
                f"📞 لطفاً به پشتیبانی اطلاع دهید: @{config.SUPPORT_USERNAME}"
            )
    
    @staticmethod
    async def get_info(url: str) -> Optional[dict]:
        """Get media info without downloading"""
        try:
            loop = asyncio.get_event_loop()
            
            def _get_info():
                with yt_dlp.YoutubeDL(DownloadManager.get_info_options()) as ydl:
                    return ydl.extract_info(url, download=False)
            
            return await loop.run_in_executor(None, _get_info)
            
        except Exception as e:
            logger.error(f"Info extraction error: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════
# FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

class Formatters:
    """Utility formatters for display"""
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format seconds to HH:MM:SS"""
        if not seconds:
            return "N/A"
        return str(timedelta(seconds=int(seconds)))
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def format_number(num: int) -> str:
        """Format large numbers with K/M/B suffixes"""
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    
    @staticmethod
    def format_date(date_str: str) -> str:
        """Format YYYYMMDD to readable date"""
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.strftime("%d %B %Y")
        except:
            return date_str or "نامشخص"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

class KeyboardBuilder:
    """Advanced inline keyboard builders"""
    
    @staticmethod
    def quality_selection(url: str, platform: str = "youtube") -> InlineKeyboardMarkup:
        """Build quality selection keyboard"""
        builder = InlineKeyboardBuilder()
        
        if platform == "youtube":
            qualities = [
                ("🎯 بهترین کیفیت", f"q_best|{url}"),
                ("📺 1080p Full HD", f"q_1080p|{url}"),
                ("📱 720p HD", f"q_720p|{url}"),
                ("💾 480p", f"q_480p|{url}"),
                ("📦 360p", f"q_360p|{url}"),
                ("🎵 فقط صدا MP3", f"q_audio|{url}"),
                ("ℹ️ اطلاعات ویدیو", f"q_info|{url}"),
            ]
        else:
            qualities = [
                ("🎯 بهترین کیفیت", f"q_best|{url}"),
                ("🎵 فقط صدا MP3", f"q_audio|{url}"),
                ("ℹ️ اطلاعات", f"q_info|{url}"),
            ]
        
        for text, callback in qualities:
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=callback[:64]  # Telegram limit
            ))
        
        builder.adjust(2, 2, 2, 1) if platform == "youtube" else builder.adjust(1)
        
        # Add support button
        builder.row(InlineKeyboardButton(
            text=f"📞 پشتیبانی @{config.SUPPORT_USERNAME}",
            url=f"https://t.me/{config.SUPPORT_USERNAME}"
        ))
        
        return builder.as_markup()
    
    @staticmethod
    def search_results(results: List[Dict]) -> InlineKeyboardMarkup:
        """Build search results keyboard"""
        builder = InlineKeyboardBuilder()
        
        for i, result in enumerate(results[:config.MAX_SEARCH_RESULTS]):
            title = Formatters.truncate_text(result.get('title', 'No Title'), 40)
            duration = result.get('duration', 'N/A')
            button_text = f"{i+1}. {title} ⏱{duration}"
            callback = f"s_{i}"
            
            builder.add(InlineKeyboardButton(
                text=button_text,
                callback_data=callback
            ))
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Build main menu keyboard"""
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="🔍 جستجوی یوتیوب",
            switch_inline_query_current_chat="/yt "
        ))
        builder.add(InlineKeyboardButton(
            text="ℹ️ راهنما",
            callback_data="help_menu"
        ))
        builder.add(InlineKeyboardButton(
            text=f"📞 پشتیبانی",
            url=f"https://t.me/{config.SUPPORT_USERNAME}"
        ))
        
        builder.adjust(2, 1)
        return builder.as_markup()
    
    @staticmethod
    def help_menu() -> InlineKeyboardMarkup:
        """Build help menu keyboard"""
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="🔙 بازگشت به منو",
            callback_data="main_menu"
        ))
        builder.add(InlineKeyboardButton(
            text="📞 پشتیبانی",
            url=f"https://t.me/{config.SUPPORT_USERNAME}"
        ))
        
        builder.adjust(1)
        return builder.as_markup()

# ═══════════════════════════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════════════════════════

class DownloadStates(StatesGroup):
    """FSM states for download flow"""
    waiting_for_url = State()
    selecting_quality = State()
    downloading = State()

# ═══════════════════════════════════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Global state
cache = CacheManager()
user_stats: Dict[int, UserStats] = defaultdict(UserStats)
active_downloads: Dict[int, DownloadTask] = {}
search_results_cache: Dict[int, List[Dict]] = {}

# ═══════════════════════════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════

@router.message()
async def rate_limit_middleware(message: Message, next_handler):
    """Rate limiting middleware"""
    user_id = message.from_user.id
    
    if not user_stats[user_id].can_download:
        wait_time = config.RATE_LIMIT_PERIOD - (time.time() - user_stats[user_id].last_download)
        await message.reply(
            f"⏳ لطفاً {wait_time:.0f} ثانیه صبر کنید...\n"
            f"📊 محدودیت: {config.RATE_LIMIT_REQUESTS} درخواست در {config.RATE_LIMIT_PERIOD} ثانیه"
        )
        return
    
    return await next_handler(message)

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Start command handler"""
    user = message.from_user
    
    welcome_text = f"""
👋 سلام <b>{user.first_name}</b> عزیز!

🎬 به ربات دانلود مدیا خوش آمدید!

<blockquote expandable>
✨ <b>قابلیت‌های اصلی:</b>
• دانلود از یوتیوب، اینستاگرام، تیک‌تاک
• پشتیبانی از ۲۰+ پلتفرم مختلف
• انتخاب کیفیت (144p تا 4K)
• دانلود فقط صدا (MP3 با کیفیت عالی)
• جستجوی یوتیوب
• اطلاعات کامل ویدیوها
• پشتیبانی از پلی‌لیست
• بدون نیاز به لاگین
</blockquote>

🎯 <b>برای شروع:</b>
• لینک ویدیو رو بفرستید
• از دستور /yt برای جستجو استفاده کنید
• /help برای راهنمای کامل

📞 <b>پشتیبانی:</b> @{config.SUPPORT_USERNAME}
⚡️ <b>حداکثر حجم:</b> {config.MAX_FILE_SIZE_MB}MB
"""
    
    await message.answer(
        welcome_text,
        reply_markup=KeyboardBuilder.main_menu()
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    help_text = f"""
📖 <b>راهنمای کامل ربات</b>

<b>📥 دانلود مدیا:</b>
• لینک بفرستید ← دانلود خودکار
• برای یوتیوب، منوی کیفیت نمایش داده میشه

<b>🔍 جستجوی یوتیوب:</b>
• <code>/yt عبارت مورد نظر</code>
• مثال: <code>/yt آهنگ شاد جدید</code>

<b>🎵 دانلود صدا:</b>
• <code>/audio لینک</code>
• خروجی: MP3 با کیفیت 320kbps

<b>📊 اطلاعات ویدیو:</b>
• <code>/info لینک</code>
• نمایش جزئیات کامل

<b>📋 پلی‌لیست:</b>
• <code>/playlist لینک</code>
• نمایش همه ویدیوها

<b>🎬 انتخاب کیفیت:</b>
• <code>/formats لینک</code>
• از 144p تا 4K

<b>⚙️ تنظیمات:</b>
• حداکثر حجم فایل: {config.MAX_FILE_SIZE_MB}MB
• محدودیت: {config.RATE_LIMIT_REQUESTS} دانلود در {config.RATE_LIMIT_PERIOD} ثانیه

<b>🌐 پلتفرم‌های پشتیبانی شده:</b>
YouTube • Instagram • TikTok • Twitter/X
Facebook • Reddit • SoundCloud • Vimeo
Twitch • Pinterest • Aparat • Namasha
و بسیاری دیگر...

📞 <b>پشتیبانی:</b> @{config.SUPPORT_USERNAME}
"""
    
    await message.answer(
        help_text,
        reply_markup=KeyboardBuilder.help_menu()
    )

@dp.message(Command("yt"))
async def cmd_youtube_search(message: Message, command: CommandObject):
    """YouTube search command"""
    if not command.args:
        await message.reply(
            "🔍 <b>جستجوی یوتیوب</b>\n\n"
            "لطفاً عبارت مورد نظر را وارد کنید:\n"
            "<code>/yt عبارت جستجو</code>\n\n"
            "مثال:\n"
            "<code>/yt آموزش پایتون</code>\n"
            "<code>/yt موزیک بی کلام</code>"
        )
        return
    
    query = command.args.strip()
    
    # Send typing action
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    # Check cache
    cache_key = f"search:{query}"
    cached_results = cache.get(cache_key)
    
    if cached_results:
        results = cached_results
    else:
        results = await YouTubeSearcher.search(query, config.MAX_SEARCH_RESULTS)
        cache.set(cache_key, results)
    
    if not results:
        await message.reply(
            "❌ نتیجه‌ای پیدا نشد.\n\n"
            "💡 راهنمایی:\n"
            "• عبارت جستجو را کوتاه‌تر کنید\n"
            "• املای کلمات را بررسی کنید\n"
            "• از کلمات کلیدی متفاوت استفاده کنید\n\n"
            f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}"
        )
        return
    
    # Save results for callback
    search_results_cache[message.from_user.id] = results
    
    # Build response
    response = f"🔍 نتایج جستجو برای: <b>{query}</b>\n\n"
    
    for i, video in enumerate(results, 1):
        title = video.get('title', 'بدون عنوان')
        channel = video.get('channel', 'نامشخص')
        duration = video.get('duration', 'N/A')
        views = video.get('views', '0')
        url = video.get('url', '')
        
        response += (
            f"{i}️⃣ <b>{Formatters.truncate_text(title, 60)}</b>\n"
            f"   📺 {channel}\n"
            f"   ⏱ {duration} | 👁 {views}\n"
            f"   🔗 <code>{url}</code>\n\n"
        )
    
    response += "👇 <b>برای دانلود، روی دکمه زیر کلیک کنید یا لینک را کپی و ارسال کنید</b>"
    
    await message.reply(
        response,
        reply_markup=KeyboardBuilder.search_results(results),
        disable_web_page_preview=True
    )
    
    # Update stats
    user_stats[message.from_user.id].search_count += 1

@dp.message(Command("audio"))
async def cmd_audio(message: Message, command: CommandObject):
    """Download audio only"""
    if not command.args:
        await message.reply(
            "🎵 <b>دانلود صدا</b>\n\n"
            "لینک ویدیو را وارد کنید:\n"
            "<code>/audio لینک</code>\n\n"
            "مثال:\n"
            "<code>/audio https://youtube.com/watch?v=...</code>"
        )
        return
    
    url = PlatformDetector.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await process_download(message, url, "audio", "best")

@dp.message(Command("info"))
async def cmd_info(message: Message, command: CommandObject):
    """Get video info"""
    if not command.args:
        await message.reply(
            "ℹ️ <b>اطلاعات ویدیو</b>\n\n"
            "لینک را وارد کنید:\n"
            "<code>/info لینک</code>"
        )
        return
    
    url = PlatformDetector.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    info = await DownloadManager.get_info(url)
    if not info:
        await message.reply(
            "❌ نتونستم اطلاعات رو دریافت کنم.\n"
            f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}"
        )
        return
    
    # Build info message
    platform = PlatformDetector.detect_platform(url)
    emoji = PlatformDetector.get_platform_emoji(platform or "")
    
    title = info.get('title', 'بدون عنوان')
    duration = Formatters.format_duration(info.get('duration', 0))
    views = Formatters.format_number(info.get('view_count', 0) or 0)
    likes = Formatters.format_number(info.get('like_count', 0) or 0)
    channel = info.get('channel', info.get('uploader', 'نامشخص'))
    upload_date = Formatters.format_date(info.get('upload_date', ''))
    
    # Available formats
    formats = info.get('formats', [])
    heights = set()
    for f in formats:
        if f.get('height'):
            heights.add(f.get('height'))
    
    quality_list = " • ".join([f"{h}p" for h in sorted(heights, reverse=True)[:8]]) if heights else "نامشخص"
    
    description = info.get('description', '')
    if description:
        description = Formatters.truncate_text(description, 200)
    
    response = f"""
{emoji} <b>{Formatters.truncate_text(title, 100)}</b>

📺 <b>کانال:</b> {channel}
⏱ <b>مدت:</b> {duration}
👁 <b>بازدید:</b> {views}
👍 <b>لایک:</b> {likes}
📅 <b>تاریخ:</b> {upload_date}
🎬 <b>کیفیت‌ها:</b> {quality_list}

📝 <b>توضیحات:</b>
{description or 'ندارد'}

🔗 <code>{url}</code>
"""
    
    await message.reply(
        response,
        reply_markup=KeyboardBuilder.quality_selection(url, platform or "other"),
        disable_web_page_preview=True
    )

@dp.message(Command("formats"))
async def cmd_formats(message: Message, command: CommandObject):
    """Show format selection"""
    if not command.args:
        await message.reply(
            "🎬 <b>انتخاب کیفیت</b>\n\n"
            "لینک را وارد کنید:\n"
            "<code>/formats لینک</code>"
        )
        return
    
    url = PlatformDetector.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    platform = PlatformDetector.detect_platform(url)
    
    await message.reply(
        f"🎬 <b>کیفیت مورد نظر را انتخاب کنید:</b>\n\n"
        f"🔗 <code>{url}</code>",
        reply_markup=KeyboardBuilder.quality_selection(url, platform or "other")
    )

@dp.message(Command("playlist"))
async def cmd_playlist(message: Message, command: CommandObject):
    """Show playlist info"""
    if not command.args:
        await message.reply(
            "📋 <b>اطلاعات پلی‌لیست</b>\n\n"
            "لینک پلی‌لیست را وارد کنید:\n"
            "<code>/playlist لینک</code>"
        )
        return
    
    url = PlatformDetector.extract_url(command.args)
    if not url:
        await message.reply("❌ لینک معتبر نیست.")
        return
    
    if "playlist" not in url.lower():
        await message.reply("❌ این لینک پلی‌لیست نیست.")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    info = await DownloadManager.get_info(url)
    if not info or 'entries' not in info:
        await message.reply("❌ نتونستم پلی‌لیست رو بخونم.")
        return
    
    entries = info['entries']
    total = len(entries)
    title = info.get('title', 'پلی‌لیست')
    
    response = f"📋 <b>{title}</b>\n\n"
    response += f"📊 <b>تعداد ویدیوها:</b> {total}\n"
    response += f"⏱ <b>مدت کل:</b> {Formatters.format_duration(sum(e.get('duration', 0) or 0 for e in entries))}\n\n"
    
    response += "<b>📺 ویدیوها:</b>\n\n"
    for i, entry in enumerate(entries[:15], 1):
        video_title = Formatters.truncate_text(entry.get('title', 'بدون عنوان'), 50)
        duration = Formatters.format_duration(entry.get('duration', 0) or 0)
        response += f"{i}. {video_title}\n   ⏱ {duration}\n\n"
    
    if total > 15:
        response += f"... و {total - 15} ویدیوی دیگر\n\n"
    
    response += (
        "👇 <b>برای دانلود هر ویدیو:</b>\n"
        "• لینک آن را کپی و ارسال کنید\n"
        "• یا از /formats استفاده کنید"
    )
    
    await message.reply(response)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show user statistics"""
    user_id = message.from_user.id
    stats = user_stats[user_id]
    
    stats_text = f"""
📊 <b>آمار شما</b>

📥 تعداد دانلود: {stats.downloads}
💾 حجم کل: {stats.total_size_mb:.1f} MB
🔍 تعداد جستجو: {stats.search_count}

⚡️ <b>محدودیت‌ها:</b>
• {config.RATE_LIMIT_REQUESTS} دانلود در {config.RATE_LIMIT_PERIOD} ثانیه
• حداکثر حجم: {config.MAX_FILE_SIZE_MB}MB
"""
    
    await message.reply(stats_text)

# ═══════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("q_"))
async def handle_quality_callback(callback: CallbackQuery):
    """Handle quality selection callbacks"""
    data = callback.data
    
    # Parse callback data
    parts = data.split("|", 1)
    if len(parts) != 2:
        await callback.answer("❌ داده نامعتبر")
        return
    
    action = parts[0]
    url = parts[1]
    
    # Map actions
    if action == "q_best":
        quality = "best"
        format_type = "video"
    elif action == "q_1080p":
        quality = "1080p"
        format_type = "video"
    elif action == "q_720p":
        quality = "720p"
        format_type = "video"
    elif action == "q_480p":
        quality = "480p"
        format_type = "video"
    elif action == "q_360p":
        quality = "360p"
        format_type = "video"
    elif action == "q_audio":
        quality = "best"
        format_type = "audio"
    elif action == "q_info":
        # Show info instead
        await callback.answer("در حال دریافت اطلاعات...")
        info = await DownloadManager.get_info(url)
        if info:
            await callback.message.reply(
                f"ℹ️ اطلاعات ویدیو:\n\n"
                f"عنوان: {info.get('title', 'N/A')}\n"
                f"مدت: {Formatters.format_duration(info.get('duration', 0))}\n"
                f"کانال: {info.get('channel', info.get('uploader', 'N/A'))}"
            )
        else:
            await callback.answer("❌ خطا در دریافت اطلاعات")
        return
    else:
        await callback.answer("❌ گزینه نامعتبر")
        return
    
    await callback.answer("⏳ شروع دانلود...")
    await callback.message.edit_text(
        "⏳ در حال دانلود...",
        reply_markup=None
    )
    
    await process_download(callback.message, url, format_type, quality, is_callback=True)

@dp.callback_query(F.data.startswith("s_"))
async def handle_search_callback(callback: CallbackQuery):
    """Handle search result selection"""
    try:
        index = int(callback.data.replace("s_", ""))
    except ValueError:
        await callback.answer("❌ داده نامعتبر")
        return
    
    user_id = callback.from_user.id
    results = search_results_cache.get(user_id, [])
    
    if not results or index >= len(results):
        await callback.answer("❌ نتایج جستجو منقضی شده. دوباره جستجو کنید.")
        return
    
    video = results[index]
    url = video.get('url', '')
    
    if not url:
        await callback.answer("❌ لینک پیدا نشد")
        return
    
    await callback.answer("⏳ در حال آماده‌سازی...")
    
    # Show quality selection
    await callback.message.edit_text(
        f"🎬 <b>{video.get('title', 'ویدیو')}</b>\n\n"
        f"کیفیت مورد نظر را انتخاب کنید:",
        reply_markup=KeyboardBuilder.quality_selection(url, "youtube")
    )

@dp.callback_query(F.data == "help_menu")
async def handle_help_callback(callback: CallbackQuery):
    """Handle help menu callback"""
    await callback.answer()
    await cmd_help(callback.message)

@dp.callback_query(F.data == "main_menu")
async def handle_main_menu_callback(callback: CallbackQuery):
    """Handle main menu callback"""
    await callback.answer()
    await callback.message.edit_text(
        "🏠 <b>منوی اصلی</b>\n\n"
        "از دکمه‌های زیر استفاده کنید:",
        reply_markup=KeyboardBuilder.main_menu()
    )

# ═══════════════════════════════════════════════════════════════════════════
# URL HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.text)
async def handle_url_message(message: Message):
    """Handle incoming URLs"""
    text = message.text or ""
    url = PlatformDetector.extract_url(text)
    
    if not url:
        # Not a URL message in private chat
        if message.chat.type == "private":
            await message.reply(
                "❌ لینکی در پیام شما پیدا نشد.\n\n"
                "💡 <b>راهنمایی:</b>\n"
                "• لینک ویدیو را بفرستید\n"
                "• از /yt برای جستجو استفاده کنید\n"
                "• /help برای راهنمای کامل\n\n"
                f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}",
                reply_markup=KeyboardBuilder.main_menu()
            )
        return
    
    platform = PlatformDetector.detect_platform(url)
    
    # For YouTube, show quality selection
    if platform == "youtube":
        await message.reply(
            f"🎬 <b>لینک یوتیوب شناسایی شد!</b>\n\n"
            f"🔗 <code>{Formatters.truncate_text(url, 80)}</code>\n\n"
            f"کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=KeyboardBuilder.quality_selection(url, "youtube")
        )
    else:
        # For other platforms, start download directly
        await process_download(message, url, "video", "best")

# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOAD PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════

async def process_download(
    message: Message,
    url: str,
    format_type: str = "video",
    quality: str = "best",
    is_callback: bool = False
):
    """Main download processor"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Rate limiting
    if user_id in active_downloads:
        await message.reply("⏳ یک دانلود در حال انجام است. لطفاً صبر کنید...")
        return
    
    # Update stats
    user_stats[user_id].last_download = time.time()
    
    # Create download task
    task = DownloadTask(url=url, quality=quality, format_type=format_type)
    active_downloads[user_id] = task
    
    # Status message
    if is_callback:
        status_msg = message
        await status_msg.edit_text("⏳ در حال دانلود...")
    else:
        status_msg = await message.reply("⏳ در حال دانلود...")
    
    # Send chat action
    action = ChatAction.UPLOAD_VOICE if format_type == "audio" else ChatAction.UPLOAD_VIDEO
    await message.bot.send_chat_action(chat_id, action)
    
    try:
        # Prepare download options
        if format_type == "audio":
            options = DownloadManager.get_audio_options("")
            file_type = "audio"
        else:
            options = DownloadManager.get_video_options("", quality)
            file_type = "video"
        
        # Download
        file_path, info, error = await DownloadManager.download(
            url, options, config.DOWNLOAD_DIR
        )
        
        if error:
            await status_msg.edit_text(
                error,
                reply_markup=KeyboardBuilder.quality_selection(url) if "حجم" in error else None
            )
            return
        
        if not file_path or not info:
            await status_msg.edit_text(
                "❌ خطا در دانلود فایل.\n"
                f"📞 پشتیبانی: @{config.SUPPORT_USERNAME}"
            )
            return
        
        # Upload file
        await status_msg.edit_text(f"📤 در حال آپلود {file_type}...")
        
        title = info.get('title', file_type)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        
        if format_type == "audio":
            # Send as audio
            audio_file = FSInputFile(file_path, filename=f"{title[:50]}.mp3")
            
            await message.reply_audio(
                audio_file,
                caption=(
                    f"🎵 <b>{Formatters.truncate_text(title, 80)}</b>\n"
                    f"💾 حجم: {file_size_mb:.1f}MB\n"
                    f"📞 @{config.SUPPORT_USERNAME}"
                ),
                title=title,
                performer=info.get('channel', info.get('uploader', 'Unknown')),
                duration=info.get('duration', 0)
            )
        else:
            # Send as video
            video_file = FSInputFile(file_path, filename=f"{title[:50]}.mp4")
            
            await message.reply_video(
                video_file,
                caption=(
                    f"🎬 <b>{Formatters.truncate_text(title, 80)}</b>\n"
                    f"💾 حجم: {file_size_mb:.1f}MB\n"
                    f"📞 @{config.SUPPORT_USERNAME}"
                ),
                supports_streaming=True,
                duration=info.get('duration', 0)
            )
        
        # Delete status message
        if is_callback:
            await status_msg.delete()
        else:
            await status_msg.delete()
        
        # Update stats
        user_stats[user_id].downloads += 1
        user_stats[user_id].total_size_mb += file_size_mb
        
        logger.info(
            f"Download complete: user={user_id}, "
            f"url={url[:50]}, size={file_size_mb:.1f}MB, "
            f"type={format_type}"
        )
        
    except Exception as e:
        logger.exception(f"Download process error: {e}")
        await status_msg.edit_text(
            f"❌ خطای غیرمنتظره:\n<code>{str(e)[:200]}</code>\n\n"
            f"📞 لطفاً به پشتیبانی اطلاع دهید: @{config.SUPPORT_USERNAME}"
        )
    
    finally:
        # Cleanup
        if 'file_path' in locals() and file_path:
            try:
                file_path.unlink(missing_ok=True)
            except:
                pass
        
        # Remove from active downloads
        active_downloads.pop(user_id, None)

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.errors()
async def error_handler(update, exception):
    """Global error handler"""
    logger.error(f"Update {update} caused error: {exception}")
    
    # Send error to support
    try:
        if hasattr(update, 'callback_query'):
            await update.callback_query.answer(
                "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید."
            )
        elif hasattr(update, 'message'):
            await update.message.reply(
                "❌ خطایی رخ داد.\n"
                f"📞 لطفاً به پشتیبانی اطلاع دهید: @{config.SUPPORT_USERNAME}"
            )
    except:
        pass
    
    return True

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Please set it in environment variables.")
        return
    
    logger.info("=" * 60)
    logger.info("🎬 Media Downloader Bot Starting...")
    logger.info(f"📁 Download directory: {config.DOWNLOAD_DIR}")
    logger.info(f"📦 Max file size: {config.MAX_FILE_SIZE_MB}MB")
    logger.info(f"⚡ Rate limit: {config.RATE_LIMIT_REQUESTS}/{config.RATE_LIMIT_PERIOD}s")
    logger.info(f"📞 Support: @{config.SUPPORT_USERNAME}")
    logger.info("=" * 60)
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
    finally:
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
