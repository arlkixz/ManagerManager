import asyncio
import os
import re
import tempfile
import logging
from pathlib import Path
from typing import List, Optional
from datetime import timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery, InputMediaVideo
)
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp
from youtube_search import YoutubeSearch  # pip install youtube-search

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ─── URL Detection ──────────────────────────────────────────────────────────
URL_PATTERN = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)
YOUTUBE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+',
    re.IGNORECASE
)

def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None

def is_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_PATTERN.match(url))

# ─── Download ───────────────────────────────────────────────────────────────
BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    },
}

def video_opts(output_path: str, quality: str = "best") -> dict:
    """دانلود ویدیو با کیفیت قابل تنظیم"""
    format_map = {
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
        "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
        "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
    }
    
    return {
        **BASE_OPTS,
        "format": format_map.get(quality, format_map["best"]),
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

def info_opts() -> dict:
    """تنها برای استخراج اطلاعات بدون دانلود"""
    return {
        **BASE_OPTS,
        "format": "best",
        "skip_download": True,
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
            return None, info, f"❌ حجم فایل {size_mb:.1f}MB از حد مجاز {MAX_FILE_SIZE_MB}MB بیشتره."

        return file_path, info, None

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in" in msg or "bot" in msg.lower():
            return None, None, "❌ یوتیوب نیاز به لاگین داره. لینک Shorts کار نمی‌کنه — لینک معمولی بفرست."
        if "private" in msg.lower():
            return None, None, "❌ این محتوا خصوصیه."
        if "not available" in msg:
            return None, None, "❌ این محتوا در دسترس نیست."
        if "Video unavailable" in msg:
            return None, None, "❌ ویدیو در دسترس نیست یا پاک شده."
        return None, None, f"❌ خطا در دانلود:\n`{msg[:200]}`"
    except Exception as e:
        logger.exception("Download error")
        return None, None, f"❌ خطای غیرمنتظره: `{str(e)[:150]}`"

async def get_info(url: str) -> dict | None:
    """دریافت اطلاعات ویدیو بدون دانلود"""
    try:
        loop = asyncio.get_event_loop()
        def _do():
            with yt_dlp.YoutubeDL(info_opts()) as ydl:
                return ydl.extract_info(url, download=False)
        return await loop.run_in_executor(None, _do)
    except Exception as e:
        logger.error(f"Info extraction error: {e}")
        return None

def cleanup(path: Path):
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

def format_duration(seconds: int) -> str:
    """تبدیل ثانیه به فرمت ساعت:دقیقه:ثانیه"""
    return str(timedelta(seconds=seconds))

def format_views(views: int) -> str:
    """فرمت کردن تعداد بازدیدها"""
    if views >= 1_000_000:
        return f"{views/1_000_000:.1f}M"
    elif views >= 1_000:
        return f"{views/1_000:.1f}K"
    return str(views)

# ─── YouTube Search ─────────────────────────────────────────────────────────
def search_youtube(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list:
    """جستجوی یوتیوب"""
    try:
        results = YoutubeSearch(query, max_results=max_results).to_dict()
        return results
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []

# ─── Bot ────────────────────────────────────────────────────────────────────
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ─── Keyboards ──────────────────────────────────────────────────────────────
def quality_keyboard(url: str) -> InlineKeyboardMarkup:
    """کیبورد انتخاب کیفیت"""
    builder = InlineKeyboardBuilder()
    qualities = [
        ("🎯 بهترین کیفیت", f"dl_best_{url}"),
        ("📱 1080p", f"dl_1080p_{url}"),
        ("📱 720p", f"dl_720p_{url}"),
        ("💾 480p", f"dl_480p_{url}"),
        ("💾 360p", f"dl_360p_{url}"),
        ("🎵 فقط صدا MP3", f"dl_audio_{url}"),
    ]
    
    for text, callback in qualities:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback[:64]))
    
    builder.adjust(2)
    return builder.as_markup()

def search_keyboard(results: list) -> InlineKeyboardMarkup:
    """کیبورد نتایج جستجو"""
    builder = InlineKeyboardBuilder()
    
    for i, result in enumerate(results[:MAX_SEARCH_RESULTS]):
        title = result.get('title', 'No Title')[:50]
        duration = result.get('duration', 'N/A')
        views = result.get('views', 'N/A')
        button_text = f"{i+1}. {title} ({duration})"
        callback = f"search_{i}"
        builder.add(InlineKeyboardButton(text=button_text, callback_data=callback))
    
    builder.adjust(1)
    return builder.as_markup()

# ─── /start ─────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        "👋 سلام! من ربات دانلود مدیا هستم.\n\n"
        "🎬 *قابلیت‌های یوتیوب:*\n"
        "• دانلود ویدیو با کیفیت‌های مختلف\n"
        "• دانلود فقط صدا (MP3)\n"
        "• جستجوی ویدیو\n"
        "• اطلاعات کامل ویدیو\n"
        "• پشتیبانی از پلی‌لیست\n\n"
        "📥 *دستورات:*\n"
        "• لینک بفرست — دانلود خودکار\n"
        "• `/audio لینک` — فقط صدا\n"
        "• `/info لینک` — اطلاعات ویدیو\n"
        "• `/yt متن` — جستجوی یوتیوب\n"
        "• `/formats لینک` — انتخاب کیفیت\n\n"
        "🌐 پشتیبانی از:\n"
        "YouTube • Instagram • TikTok • Twitter/X\n"
        "Facebook • Reddit • SoundCloud و بیشتر..."
    )

# ─── /help ──────────────────────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 *راهنمای کامل*\n\n"
        "🔗 *لینک بفرست* ← دانلود بهترین کیفیت\n\n"
        "📊 *دستورات:*\n"
        "`/yt متن` — جستجوی یوتیوب\n"
        "`/audio لینک` — فقط صدا MP3\n"
        "`/info لینک` — اطلاعات کامل ویدیو\n"
        "`/formats لینک` — انتخاب کیفیت\n"
        "`/playlist لینک` — لیست ویدیوهای پلی‌لیست\n\n"
        f"⚠️ حداکثر حجم: {MAX_FILE_SIZE_MB}MB\n"
        "🎯 ویدیوهای یوتیوب بدون نیاز به لاگین"
    )

# ─── /yt - جستجوی یوتیوب ──────────────────────────────────────────────────
@dp.message(Command("yt"))
async def cmd_youtube_search(msg: Message, command: CommandObject):
    if not command.args:
        await msg.reply("❗ مثال:\n`/yt موزیک بی کلام`")
        return
    
    await msg.bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    
    results = search_youtube(command.args)
    
    if not results:
        await msg.reply("❌ نتیجه‌ای پیدا نشد.")
        return
    
    # ذخیره نتایج در state (موقت)
    # برای سادگی، از حافظه موقت استفاده می‌کنیم
    if not hasattr(dp, 'search_cache'):
        dp.search_cache = {}
    dp.search_cache[msg.from_user.id] = results
    
    # ساخت پیام نتایج
    response = f"🔍 *نتایج جستجو برای:* `{command.args}`\n\n"
    for i, result in enumerate(results[:MAX_SEARCH_RESULTS], 1):
        title = result.get('title', 'No Title')
        duration = result.get('duration', 'N/A')
        views = result.get('views', '0')
        channel = result.get('channel', 'Unknown')
        
        response += f"{i}️⃣ *{title}*\n"
        response += f"   ⏱ {duration} | 👁 {views} | 📺 {channel}\n"
        response += f"   🔗 https://youtube.com{result.get('url_suffix', '')}\n\n"
    
    response += "👇 *برای دانلود یکی از لینک‌ها استفاده کن*"
    
    await msg.reply(response, disable_web_page_preview=True)

# ─── /info - اطلاعات ویدیو ─────────────────────────────────────────────────
@dp.message(Command("info"))
async def cmd_info(msg: Message, command: CommandObject):
    if not command.args:
        await msg.reply("❗ مثال:\n`/info https://youtube.com/watch?v=...`")
        return
    
    url = extract_url(command.args)
    if not url:
        await msg.reply("❗ لینک معتبر نیست.")
        return
    
    await msg.bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    
    info = await get_info(url)
    if not info:
        await msg.reply("❌ نتونستم اطلاعات ویدیو رو بگیرم.")
        return
    
    # ساخت پیام اطلاعات
    title = info.get('title', 'بدون عنوان')
    duration = info.get('duration', 0)
    views = info.get('view_count', 0)
    likes = info.get('like_count', 0)
    upload_date = info.get('upload_date', 'نامشخص')
    channel = info.get('channel', 'نامشخص')
    description = info.get('description', '')[:200]
    
    # کیفیت‌های موجود
    formats = info.get('formats', [])
    video_formats = [f for f in formats if f.get('vcodec') != 'none']
    heights = set()
    for f in video_formats:
        if f.get('height'):
            heights.add(f.get('height'))
    
    quality_list = " • ".join([f"{h}p" for h in sorted(heights, reverse=True)[:5]]) if heights else "نامشخص"
    
    response = (
        f"📹 *{title}*\n\n"
        f"📺 کانال: *{channel}*\n"
        f"⏱ مدت: {format_duration(duration)}\n"
        f"👁 بازدید: {format_views(views)}\n"
        f"👍 لایک: {format_views(likes)}\n"
        f"📅 تاریخ آپلود: {upload_date}\n"
        f"🎬 کیفیت‌های موجود: {quality_list}\n\n"
        f"📝 توضیحات: {description}...\n\n"
        f"🔗 {url}\n\n"
        f"👇 *برای دانلود از /formats استفاده کن*"
    )
    
    await msg.reply(response, disable_web_page_preview=True)

# ─── /formats - انتخاب کیفیت ──────────────────────────────────────────────
@dp.message(Command("formats"))
async def cmd_formats(msg: Message, command: CommandObject):
    if not command.args:
        await msg.reply("❗ مثال:\n`/formats https://youtube.com/watch?v=...`")
        return
    
    url = extract_url(command.args)
    if not url:
        await msg.reply("❗ لینک معتبر نیست.")
        return
    
    if not is_youtube_url(url):
        await msg.reply("❗ این قابلیت فقط برای یوتیوب هست.")
        return
    
    await msg.reply(
        "🎬 *کیفیت مورد نظر رو انتخاب کن:*",
        reply_markup=quality_keyboard(url)
    )

# ─── /audio - دانلود صدا ──────────────────────────────────────────────────
@dp.message(Command("audio"))
async def cmd_audio(msg: Message, command: CommandObject):
    if not command.args:
        await msg.reply("❗ مثال:\n`/audio https://youtube.com/watch?v=...`")
        return

    url = extract_url(command.args)
    if not url:
        await msg.reply("❗ لینک معتبر پیدا نشد.")
        return

    status = await msg.reply("⏳ در حال دانلود صدا...")
    await msg.bot.send_chat_action(msg.chat.id, ChatAction.UPLOAD_VOICE)
    
    file_path, info, error = await download(url, audio_opts(""))

    if error:
        await status.edit_text(error)
        return

    try:
        await status.edit_text("📤 آپلود صدا...")
        title = (info or {}).get("title", "audio")
        audio_file = FSInputFile(file_path, filename=f"{title[:50]}.mp3")
        me = (await bot.get_me()).username
        
        await msg.reply_audio(
            audio_file,
            caption=f"🎵 *{title}*\n@{me}",
            title=title,
            performer=info.get('channel', 'Unknown') if info else None
        )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(file_path)

# ─── /playlist - مشاهده پلی‌لیست ──────────────────────────────────────────
@dp.message(Command("playlist"))
async def cmd_playlist(msg: Message, command: CommandObject):
    if not command.args:
        await msg.reply("❗ مثال:\n`/playlist https://youtube.com/playlist?list=...`")
        return
    
    url = extract_url(command.args)
    if not url:
        await msg.reply("❗ لینک معتبر نیست.")
        return
    
    if "playlist" not in url.lower():
        await msg.reply("❗ این لینک پلی‌لیست نیست.")
        return
    
    await msg.bot.send_chat_action(msg.chat.id, ChatAction.TYPING)
    
    try:
        info = await get_info(url)
        if not info or 'entries' not in info:
            await msg.reply("❌ نتونستم پلی‌لیست رو بخونم.")
            return
        
        entries = info['entries']
        total = len(entries)
        
        response = f"📋 *{info.get('title', 'Playlist')}*\n\n"
        response += f"📊 تعداد ویدیوها: {total}\n\n"
        
        for i, entry in enumerate(entries[:10], 1):  # نمایش ۱۰ تای اول
            title = entry.get('title', 'No Title')[:50]
            duration = format_duration(entry.get('duration', 0))
            response += f"{i}. *{title}*\n   ⏱ {duration}\n\n"
        
        if total > 10:
            response += f"... و {total - 10} ویدیوی دیگر\n\n"
        
        response += "👇 *برای دانلود هر ویدیو لینکش رو بفرست*"
        
        await msg.reply(response)
        
    except Exception as e:
        await msg.reply(f"❌ خطا: `{str(e)[:200]}`")

# ─── Callback Handlers ──────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("dl_"))
async def handle_download_callback(callback: CallbackQuery):
    """هندل کردن دانلود از روی کیبورد کیفیت"""
    data = callback.data
    
    # استخراج نوع و URL
    if data.startswith("dl_best_"):
        quality = "best"
        url = data.replace("dl_best_", "")
    elif data.startswith("dl_audio_"):
        quality = "audio"
        url = data.replace("dl_audio_", "")
    elif data.startswith("dl_1080p_"):
        quality = "1080p"
        url = data.replace("dl_1080p_", "")
    elif data.startswith("dl_720p_"):
        quality = "720p"
        url = data.replace("dl_720p_", "")
    elif data.startswith("dl_480p_"):
        quality = "480p"
        url = data.replace("dl_480p_", "")
    elif data.startswith("dl_360p_"):
        quality = "360p"
        url = data.replace("dl_360p_", "")
    else:
        await callback.answer("❌ گزینه نامعتبر")
        return
    
    await callback.answer("⏳ شروع دانلود...")
    await callback.message.edit_text("⏳ در حال دانلود...", reply_markup=None)
    
    me = (await bot.get_me()).username
    
    if quality == "audio":
        # دانلود صدا
        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)
        file_path, info, error = await download(url, audio_opts(""))
        
        if error:
            await callback.message.edit_text(error)
            return
        
        try:
            title = (info or {}).get("title", "audio")
            audio_file = FSInputFile(file_path, filename=f"{title[:50]}.mp3")
            await callback.message.reply_audio(
                audio_file,
                caption=f"🎵 *{title}*\n@{me}",
                title=title
            )
            await callback.message.delete()
        except Exception as e:
            await callback.message.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
        finally:
            cleanup(file_path)
    else:
        # دانلود ویدیو
        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO)
        file_path, info, error = await download(url, video_opts("", quality))
        
        if error:
            if file_path is None and info:
                # حجم فایل زیاد بود - پیشنهاد کیفیت پایین‌تر
                size_mb = info.get('filesize_approx', 0) / (1024*1024)
                await callback.message.edit_text(
                    f"{error}\n\n💡 از کیفیت پایین‌تر استفاده کن: /formats لینک",
                    reply_markup=quality_keyboard(url)
                )
            else:
                await callback.message.edit_text(error)
            return
        
        try:
            video_file = FSInputFile(file_path, filename=file_path.name)
            title = (info or {}).get("title", "video")
            await callback.message.reply_video(
                video_file,
                caption=f"🎬 *{title}*\n@{me}",
                supports_streaming=True
            )
            await callback.message.delete()
        except Exception as e:
            await callback.message.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
        finally:
            cleanup(file_path)

# ─── URL Handler ────────────────────────────────────────────────────────────
@dp.message(F.text)
async def handle_url(msg: Message):
    url = extract_url(msg.text or "")
    if not url:
        if msg.chat.type == "private":
            await msg.reply(
                "❗ لینک معتبری پیدا نشد.\n\n"
                "💡 *می‌تونی از این دستورات استفاده کنی:*\n"
                "`/yt متن` — جستجوی یوتیوب\n"
                "`/help` — راهنمای کامل"
            )
        return

    # اگر یوتیوب بود، کیبورد کیفیت نشون بده
    if is_youtube_url(url):
        await msg.reply(
            "🎬 *لینک یوتیوب شناسایی شد!*\nکیفیت مورد نظر رو انتخاب کن:",
            reply_markup=quality_keyboard(url)
        )
        return
    
    # برای بقیه سایت‌ها، دانلود مستقیم
    status = await msg.reply("⏳ در حال دانلود...")
    await msg.bot.send_chat_action(msg.chat.id, ChatAction.UPLOAD_VIDEO)
    me = (await bot.get_me()).username

    vid_path, info, error = await download(url, video_opts(""))

    if error:
        await status.edit_text(error)
        return

    try:
        await status.edit_text("📤 آپلود ویدیو...")
        video_file = FSInputFile(vid_path, filename=vid_path.name)
        title = (info or {}).get("title", "video")
        await msg.reply_video(
            video_file,
            caption=f"🎬 *{title}*\n@{me}",
            supports_streaming=True
        )
        
        # استخراج و ارسال صدا
        await status.edit_text("🎵 در حال استخراج صدا...")
        aud_path, aud_info, aud_err = await download(url, audio_opts(""))
        if aud_path:
            audio_file = FSInputFile(aud_path, filename=f"{title[:50]}.mp3")
            await msg.reply_audio(
                audio_file,
                caption=f"🎵 *{title}*\n@{me}"
            )
            cleanup(aud_path)

        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ خطا در آپلود: `{str(e)[:200]}`")
    finally:
        cleanup(vid_path)

# ─── Main ────────────────────────────────────────────────────────────────────
async def main():
    # Initialize search cache
    if not hasattr(dp, 'search_cache'):
        dp.search_cache = {}
    
    logger.info("🚀 Bot started successfully!")
    logger.info(f"📁 Download directory: {DOWNLOAD_DIR}")
    logger.info(f"📦 Max file size: {MAX_FILE_SIZE_MB}MB")
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
