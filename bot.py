import asyncio
import os
import re
import tempfile
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import yt_dlp

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))   # Telegram limit for bots
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ─── URL Detection ──────────────────────────────────────────────────────────
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)',
    re.IGNORECASE
)

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be",
    "instagram.com",
    "twitter.com", "x.com",
    "tiktok.com",
    "facebook.com", "fb.watch",
    "reddit.com",
    "dailymotion.com",
    "vimeo.com",
    "soundcloud.com",
    "spotify.com",
    "pinterest.com",
    "twitch.tv",
    "aparat.com",
]

def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None

def is_supported(url: str) -> bool:
    return any(domain in url.lower() for domain in SUPPORTED_DOMAINS)

# ─── Download Logic ─────────────────────────────────────────────────────────
COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    },
}

def get_ydl_opts(output_path: str, audio_only: bool = False) -> dict:
    if audio_only:
        return {
            **COMMON_OPTS,
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        }
    return {
        **COMMON_OPTS,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

async def download_media(url: str, audio_only: bool = False) -> tuple[Path | None, str | None]:
    """Returns (file_path, error_message)"""
    suffix = ".%(ext)s"
    with tempfile.NamedTemporaryFile(dir=DOWNLOAD_DIR, delete=False, suffix="") as tmp:
        base_path = tmp.name

    output_template = base_path + suffix
    opts = get_ydl_opts(output_template, audio_only=audio_only)

    try:
        loop = asyncio.get_event_loop()
        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        info = await loop.run_in_executor(None, _download)

        # Find the downloaded file - skip empty files
        all_files = list(DOWNLOAD_DIR.glob(Path(base_path).name + "*"))
        downloaded = [f for f in all_files if f.stat().st_size > 0]
        for f in all_files:
            if f.stat().st_size == 0:
                f.unlink(missing_ok=True)

        if not downloaded:
            return None, "❌ دانلود ناموفق بود — فایل خالی."

        file_path = max(downloaded, key=lambda f: f.stat().st_size)
        size_mb = file_path.stat().st_size / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            file_path.unlink(missing_ok=True)
            return None, f"❌ حجم فایل {size_mb:.1f}MB از حد مجاز {MAX_FILE_SIZE_MB}MB بیشتره."

        return file_path, None

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Private" in msg or "private" in msg:
            return None, "❌ این محتوا خصوصیه و قابل دانلود نیست."
        if "not available" in msg:
            return None, "❌ این محتوا در دسترس نیست (ممکنه حذف شده باشه)."
        return None, f"❌ خطا در دانلود:\n`{msg[:200]}`"
    except Exception as e:
        logger.exception("Unexpected download error")
        return None, f"❌ خطای غیرمنتظره: `{str(e)[:200]}`"

def cleanup(path: Path):
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

# ─── Bot Setup ───────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# ─── Handlers ────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        "👋 سلام! من ربات دانلود مدیا هستم.\n\n"
        "📥 *کافیه لینک بفرستی، بقیه‌اش با منه!*\n\n"
        "پشتیبانی از:\n"
        "🎬 YouTube • Instagram • TikTok\n"
        "🐦 Twitter/X • Facebook • Reddit\n"
        "🎵 SoundCloud • Spotify • و بیشتر...\n\n"
        "📎 برای دانلود فقط صدا: `/audio [لینک]`\n"
        "📎 برای دانلود ویدیو: فقط لینک بفرست"
    )

@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 *راهنما*\n\n"
        "• لینک ویدیو بفرست ← ویدیو با بهترین کیفیت\n"
        "• `/audio [لینک]` ← فقط صدا (MP3 320kbps)\n\n"
        f"⚠️ حداکثر حجم: {MAX_FILE_SIZE_MB}MB"
    )

@dp.message(Command("audio"))
async def cmd_audio(msg: Message):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.reply("❗ مثال: `/audio https://youtube.com/watch?v=...`")
        return

    url = extract_url(args[1])
    if not url:
        await msg.reply("❗ لینک معتبر پیدا نشد.")
        return

    status = await msg.reply("⏳ در حال دانلود صدا...")
    file_path, error = await download_media(url, audio_only=True)

    if error:
        await status.edit_text(error)
        return

    try:
        await status.edit_text("📤 در حال آپلود...")
        audio_file = FSInputFile(file_path, filename=file_path.name)
        await msg.reply_audio(audio_file, caption="🎵 دانلود شد با @" + (await bot.get_me()).username)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(file_path)

@dp.message(F.text)
async def handle_url(msg: Message):
    url = extract_url(msg.text or "")
    if not url:
        # در پیوی پیام راهنما بده، در گروه سکوت کن
        if msg.chat.type == "private":
            await msg.reply("❗ لینک معتبری پیدا نشد.\nیک لینک بفرست تا دانلودش کنم!")
        return

    status = await msg.reply("⏳ در حال پردازش لینک...")
    file_path, error = await download_media(url, audio_only=False)

    if error:
        await status.edit_text(error)
        return

    try:
        await status.edit_text("📤 در حال آپلود...")
        ext = file_path.suffix.lower()

        if ext in (".mp3", ".m4a", ".ogg", ".flac", ".wav", ".opus"):
            media_file = FSInputFile(file_path, filename=file_path.name)
            await msg.reply_audio(media_file, caption="🎵 @" + (await bot.get_me()).username)
        else:
            media_file = FSInputFile(file_path, filename=file_path.name)
            await msg.reply_video(
                media_file,
                caption="🎬 @" + (await bot.get_me()).username,
                supports_streaming=True,
            )

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(file_path)

# ─── Main ────────────────────────────────────────────────────────────────────
async def main():
    logger.info("Bot started ✅")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
