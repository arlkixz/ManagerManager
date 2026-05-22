import os
import logging
import random
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== راه‌اندازی اولیه ====================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

INPUT_DIR = "downloads/"
OUTPUT_DIR = "outputs/"
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== تابع اصلی تغییر ویدیو (دیگه شوخی نیست) ====================
async def process_video(input_path: str, output_path: str) -> bool:
    """
    با استفاده از FFmpeg تغییرات تصادفی و یکتا را روی ویدیو اعمال می‌کند.
    """
    # 1. تغییرات تصادفی در محدوده‌های منطقی
    # سرعت پخش (0.95 تا 1.05 - خیلی کم که چشم متوجه نشه ولی الگوریتم رو گول بزنه)
    speed = round(random.uniform(0.97, 1.03), 2)
    # کنتراست و روشنایی و اشباع
    contrast = round(random.uniform(0.92, 1.08), 2)
    brightness = round(random.uniform(0.05, 0.1), 2)
    saturation = round(random.uniform(0.9, 1.1), 2)
    
    # ساخت فیلتر ویدیو
    video_filter = f"setpts={speed}*PTS, eq=contrast={contrast}:brightness={brightness}:saturation={saturation}"
    
    # تصمیم‌گیری برای آینه‌ای کردن (قلاب کردن الگوریتم تیک‌تاک)
    if random.choice([True, False]):
        video_filter += ", hflip"  # آینه افقی
    if random.choice([True, False]):
        video_filter += ", vflip"  # آینه عمودی
        
    # تغییر سرعت صدا (متناسب با سرعت ویدیو)
    audio_filter = f"atempo={speed}"
    
    # دستور نهایی FFmpeg
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        "-y",
        output_path
    ]
    
    try:
        # اجرای دستور در یک پروسه جداگانه تا برنامه اصلی هنگ نکنه
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Video processing successful: {output_path}")
            return True
        else:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            return False
    except Exception as e:
        logger.error(f"Processing exception: {e}")
        return False

# ==================== بخش مربوط به ربات تلگرام ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! یه ویدیو برام بفرست تا باهاش یه ویدیوی یکتا و جدید برای تیک‌تاک بسازم.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        return
        
    msg = await update.message.reply_text("⏳ ویدیو رو دریافت کردم. دارم روش کار می‌کنم (چند دقیقه طول میکشه)...")
    
    # دانلود ویدیو
    video_file = await update.message.video.get_file()
    input_path = os.path.join(INPUT_DIR, f"{update.message.message_id}.mp4")
    await video_file.download_to_drive(input_path)
    
    # پردازش ویدیو
    output_path = os.path.join(OUTPUT_DIR, f"unique_{update.message.message_id}.mp4")
    success = await process_video(input_path, output_path)
    
    if success:
        # ارسال ویدیوی آماده
        with open(output_path, 'rb') as f:
            await update.message.reply_video(
                video=f,
                caption="✅ ویدیو آماده اس! الان دیگه واسه تیک‌تاک یه ویدیوی کاملاً جدیده."
            )
    else:
        await update.message.reply_text("❌ خطا تو پردازش ویدیو! میتونم لینکش رو واست بفرستم؟")
    
    # پاک کردن فایل‌های اضافی از سرور
    try:
        os.remove(input_path)
        os.remove(output_path)
    except: pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
