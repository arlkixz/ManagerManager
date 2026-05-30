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
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ─── URL Detection ──────────────────────────────────────────────────────────
URL_PATTERN = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)

def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None

# ─── Download ───────────────────────────────────────────────────────────────
BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    },
}

def video_opts(output_path: str) -> dict:
    return {
        **BASE_OPTS,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "merge_output_format": "mp4",
    }

def audio_opts(output_path: str) -> dict:
    return {
        **BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

async def download(url: str, opts: dict) -> tuple[Path | None, dict | None, str | None]:
    """Returns (file_path, info, error)"""
    with tempfile.NamedTemporaryFile(dir=DOWNLOAD_DIR, delete=False, suffix="") as tmp:
        base_path = tmp.name

    opts = {**opts, "outtmpl": base_path + ".%(ext)s"}

    try:
        loop = asyncio.get_event_loop()
        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)
        info = await loop.run_in_executor(None, _do)

        files = [f for f in DOWNLOAD_DIR.glob(Path(base_path).name + "*") if f.stat().st_size > 0]
        # cleanup empty
        for f in DOWNLOAD_DIR.glob(Path(base_path).name + "*"):
            if f.stat().st_size == 0:
                f.unlink(missing_ok=True)

        if not files:
            return None, None, "❌ فایل دانلود نشد یا خالی بود."

        file_path = max(files, key=lambda f: f.stat().st_size)
        size_mb = file_path.stat().st_size / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            file_path.unlink(missing_ok=True)
            return None, None, f"❌ حجم فایل {size_mb:.1f}MB از حد مجاز {MAX_FILE_SIZE_MB}MB بیشتره."

        return file_path, info, None

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in" in msg or "bot" in msg.lower():
            return None, None, "❌ یوتیوب نیاز به لاگین داره. لینک Shorts کار نمی‌کنه — لینک معمولی بفرست."
        if "private" in msg.lower():
            return None, None, "❌ این محتوا خصوصیه."
        if "not available" in msg:
            return None, None, "❌ این محتوا در دسترس نیست."
        return None, None, f"❌ خطا در دانلود:\n`{msg[:200]}`"
    except Exception as e:
        logger.exception("Download error")
        return None, None, f"❌ خطای غیرمنتظره: `{str(e)[:150]}`"

def cleanup(path: Path):
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

# ─── Bot ────────────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# ─── /start ─────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        "👋 سلام! من ربات دانلود مدیا هستم.\n\n"
        "📥 *فقط لینک بفرست — بقیه با منه!*\n\n"
        "پشتیبانی از:\n"
        "🎬 YouTube • Instagram • TikTok\n"
        "🐦 Twitter/X • Facebook • Reddit\n"
        "🎵 SoundCloud • Aparat • و بیشتر...\n\n"
        "📌 برای فقط صدا: /audio لینک"
    )

# ─── /help ──────────────────────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 *راهنما*\n\n"
        "🔗 لینک بفرست ← ویدیو + صدا جداگانه\n"
        "🎵 /audio لینک ← فقط صدا MP3\n\n"
        f"⚠️ حداکثر حجم: {MAX_FILE_SIZE_MB}MB"
    )

# ─── /audio ─────────────────────────────────────────────────────────────────
@dp.message(Command("audio"))
async def cmd_audio(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("❗ مثال:\n`/audio https://youtube.com/watch?v=...`")
        return

    url = extract_url(parts[1])
    if not url:
        await msg.reply("❗ لینک معتبر پیدا نشد.")
        return

    status = await msg.reply("⏳ در حال دانلود صدا...")
    file_path, info, error = await download(url, audio_opts(""))

    if error:
        await status.edit_text(error)
        return

    try:
        await status.edit_text("📤 آپلود صدا...")
        title = (info or {}).get("title", "audio")
        audio_file = FSInputFile(file_path, filename=f"{title[:50]}.mp3")
        me = (await bot.get_me()).username
        await msg.reply_audio(audio_file, caption=f"🎵 @{me}")
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(file_path)

# ─── URL handler ─────────────────────────────────────────────────────────────
@dp.message(F.text)
async def handle_url(msg: Message):
    url = extract_url(msg.text or "")
    if not url:
        if msg.chat.type == "private":
            await msg.reply("❗ لینک معتبری پیدا نشد.")
        return

    status = await msg.reply("⏳ در حال دانلود...")
    me = (await bot.get_me()).username

    # دانلود ویدیو
    vid_path, info, error = await download(url, video_opts(""))

    if error:
        await status.edit_text(error)
        return

    ext = vid_path.suffix.lower()

    try:
        # اگه فایل صوتیه، فقط صدا بفرست
        if ext in (".mp3", ".m4a", ".ogg", ".flac", ".wav", ".opus"):
            await status.edit_text("📤 آپلود صدا...")
            audio_file = FSInputFile(vid_path, filename=vid_path.name)
            await msg.reply_audio(audio_file, caption=f"🎵 @{me}")
            await status.delete()
            return

        # فرستادن ویدیو
        await status.edit_text("📤 آپلود ویدیو...")
        video_file = FSInputFile(vid_path, filename=vid_path.name)
        await msg.reply_video(
            video_file,
            caption=f"🎬 @{me}",
            supports_streaming=True,
        )

        # فرستادن صدا جداگانه
        await status.edit_text("🎵 در حال استخراج صدا...")
        aud_path, aud_info, aud_err = await download(url, audio_opts(""))
        if aud_path:
            title = (aud_info or info or {}).get("title", "audio")
            audio_file = FSInputFile(aud_path, filename=f"{title[:50]}.mp3")
            await msg.reply_audio(audio_file, caption=f"🎵 @{me}")
            cleanup(aud_path)

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(vid_path)

# ─── Main ────────────────────────────────────────────────────────────────────
async def main():
    logger.info("Bot started ✅")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
