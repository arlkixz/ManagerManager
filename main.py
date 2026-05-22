import os
import logging
import random
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

INPUT_DIR = "downloads/"
OUTPUT_DIR = "outputs/"
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def process_video(input_path: str, output_path: str) -> tuple:
    """پردازش ویدیو و برگردوندن (success, error_message)"""
    
    # تغییرات تصادفی
    speed = round(random.uniform(0.97, 1.03), 2)
    contrast = round(random.uniform(0.92, 1.08), 2)
    brightness = round(random.uniform(0.05, 0.1), 2)
    saturation = round(random.uniform(0.9, 1.1), 2)
    
    video_filter = f"setpts={speed}*PTS, eq=contrast={contrast}:brightness={brightness}:saturation={saturation}"
    
    if random.choice([True, False]):
        video_filter += ", hflip"
    if random.choice([True, False]):
        video_filter += ", vflip"
    
    # بررسی وجود ffmpeg
    check_ffmpeg = await asyncio.create_subprocess_exec(
        "ffmpeg", "-version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await check_ffmpeg.communicate()
    
    if check_ffmpeg.returncode != 0:
        return False, "❌ FFmpeg روی سرور نصب نیست!"
    
    # دستور ساده‌تر FFmpeg (برای تست)
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", video_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        output_path
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return True, None
        else:
            error_msg = stderr.decode()[:500]
            return False, f"FFmpeg error: {error_msg}"
            
    except Exception as e:
        return False, f"Exception: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **ربات یکتاساز ویدیو**\n\n"
        "📌 یه ویدیو برام بفرست تا برات یه نسخه یکتا و جدید بسازم.\n"
        "✅ مناسب برای تیک‌تاک، اینستاگرام و یوتیوب\n\n"
        "⚠️ صبور باش، پردازش چند دقیقه طول میکشه.",
        parse_mode="Markdown"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        return
    
    msg = await update.message.reply_text("⏳ دریافت ویدیو...")
    
    # دانلود
    video_file = await update.message.video.get_file()
    input_path = os.path.join(INPUT_DIR, f"{update.message.message_id}.mp4")
    await video_file.download_to_drive(input_path)
    
    await msg.edit_text("🎨 در حال پردازش ویدیو (ممکنه 1-3 دقیقه طول بکشه)...")
    
    output_path = os.path.join(OUTPUT_DIR, f"unique_{update.message.message_id}.mp4")
    success, error = await process_video(input_path, output_path)
    
    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        with open(output_path, 'rb') as f:
            await update.message.reply_video(
                video=f,
                caption="✅ **ویدیو آماده است!**\n\nاین ویدیو برای تیک‌تاک یکتاسازی شده.",
                parse_mode="Markdown"
            )
        await msg.delete()
    else:
        error_text = f"❌ خطا در پردازش!\n\n{error}" if error else "❌ خطا نامشخص!"
        await msg.edit_text(error_text)
    
    # پاکسازی
    try:
        os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
    except:
        pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    logger.info("✅ ربات روشن شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
