import os
import logging
import random
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

INPUT_DIR = "downloads/"
OUTPUT_DIR = "outputs/"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🎬 **ربات یکتاساز ویدیو (Uniquing Bot)**

📌 قابلیت‌ها:  
• تغییر تصادفی سرعت پخش  
• تغییر تصادفی کنتراست، اشباع، روشنایی  
• آینه‌ای کردن (Mirror/Flip)  
• تولید ویدیوهای یکتا برای تیک‌تاک، اینستاگرام، یوتیوب  

📥 نحوه استفاده:  
فقط یه ویدیو برام بفرست، ربات کارهات رو انجام میده.  
بعد از پردازش، ویدیوی نهایی رو برات میفرستم.
"""
    await update.message.reply_text(text)

def process_video(input_path, output_path):
    """اعمال تغییرات تصادفی روی ویدیو با FFmpeg"""
    
    # تولید مقادیر تصادفی برای افکت‌ها
    speed = random.uniform(0.95, 1.15)  # سرعت بین 0.95 تا 1.15
    contrast = random.uniform(0.9, 1.2)  # کنتراست
    brightness = random.uniform(0.05, 0.2)  # روشنایی
    saturation = random.uniform(0.8, 1.3)  # اشباع رنگ
    
    # فیلترهای FFmpeg
    filters = f"setpts={speed}*PTS, eq=contrast={contrast}:brightness={brightness}:saturation={saturation}"
    
    # تصمیم تصادفی برای آینه‌ای کردن (Flip)
    if random.choice([True, False]):
        filters += ", hflip"  # افقی
    if random.choice([True, False]):
        filters += ", vflip"  # عمودی
    
    # تغییر سرعت صدا (متناسب با سرعت ویدیو)
    audio_filter = f"atempo={speed}"
    
    # دستور نهایی FFmpeg
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", filters,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        "-y",
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr}")
        return False

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر ویدیوهای دریافتی"""
    if not update.message.video:
        return
    
    msg = await update.message.reply_text("⏳ دانلود ویدیو...")
    
    # دانلود ویدیو
    video_file = await update.message.video.get_file()
    input_path = os.path.join(INPUT_DIR, f"{update.message.message_id}.mp4")
    await video_file.download_to_drive(input_path)
    
    await msg.edit_text("🎨 در حال یکتاسازی ویدیو (ممکنه چند دقیقه طول بکشه)...")
    
    # پردازش ویدیو
    output_path = os.path.join(OUTPUT_DIR, f"unique_{update.message.message_id}.mp4")
    
    if await asyncio.to_thread(process_video, input_path, output_path):
        # ارسال ویدیوی نهایی
        with open(output_path, 'rb') as f:
            await update.message.reply_video(
                video=f,
                caption="✅ ویدیوی یکتاساز شده! قابل انتشار در تیک‌تاک و اینستاگرام.",
                supports_streaming=True
            )
    else:
        await msg.edit_text("❌ خطا در پردازش ویدیو!")
    
    # پاکسازی فایل‌های موقت
    try:
        os.remove(input_path)
        os.remove(output_path)
    except:
        pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    logger.info("✅ ربات یکتاساز ویدیو شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
