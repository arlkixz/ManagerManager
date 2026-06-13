import os
import sys
import telebot
from telebot import types
from PIL import Image, ImageDraw, ImageFont
import textwrap
import datetime

# ================= تنظیمات =================
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@test")

if not TOKEN:
    print("❌ توکن تنظیم نشده!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# ================= تابع ساخت بنر حرفه‌ای لینکدونی =================
def create_banner(title, description, link, date, reserved_by):
    # بک‌گراند تیره شیک
    img = Image.new('RGB', (1200, 630), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)
    
    # نوار رنگی سمت چپ (آبی-بنفش گرادیانی)
    for x in range(8):
        r = 88 + x * 5
        g = 101 + x * 3
        b = 242 - x * 2
        draw.rectangle([x, 0, x+1, 630], fill=(r, g, b))
    
    # کادر اصلی با گوشه‌های گرد (شبیه‌سازی)
    draw.rounded_rectangle([40, 40, 1160, 590], radius=20, outline=(60, 60, 80), width=3)
    
    # خط جداکننده بالایی
    draw.line([(60, 130), (1140, 130)], fill=(60, 60, 80), width=2)
    
    # دایره آیکن لینک
    draw.ellipse([60, 55, 110, 105], outline=(88, 101, 242), width=4)
    draw.text((72, 58), "🔗", fill=(255, 255, 255))
    
    # عنوان (کنار آیکن)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        desc_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except:
        title_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # عنوان اصلی
    draw.text((130, 65), title[:35], fill=(255, 255, 255), font=title_font)
    
    # بخش توضیحات (با کادر جدا)
    draw.rounded_rectangle([60, 150, 1140, 340], radius=15, fill=(30, 30, 40), outline=(50, 50, 65), width=2)
    
    lines = textwrap.wrap(description, width=45)
    y = 170
    for line in lines[:5]:
        draw.text((90, y), line, fill=(200, 210, 230), font=desc_font)
        y += 50
    
    # بخش لینک (کادر پایین)
    draw.rounded_rectangle([60, 370, 1140, 460], radius=12, fill=(25, 25, 35), outline=(88, 101, 242), width=3)
    draw.text((90, 390), f"🔗 {link}", fill=(88, 101, 242), font=small_font)
    
    # اطلاعات رزرو (پایین صفحه)
    draw.text((90, 500), f"📅 {date}", fill=(150, 150, 160), font=small_font)
    draw.text((400, 500), f"👤 {reserved_by}", fill=(150, 150, 160), font=small_font)
    
    # لوگو لینکدونی (بالا سمت راست)
    try:
        logo_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
    except:
        logo_font = ImageFont.load_default()
    
    # مستطیل لوگو
    draw.rounded_rectangle([920, 50, 1130, 110], radius=15, fill=(88, 101, 242))
    draw.text((945, 65), "LINKdoni", fill=(255, 255, 255), font=logo_font)
    
    # خط تزئینی پایین
    for i in range(3):
        y_pos = 580 + i
        alpha = 200 - i * 50
        draw.line([(60, y_pos), (300, y_pos)], fill=(88, 101, 242), width=2)
    
    # ذخیره
    filename = f"banner_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(filename, "PNG")
    return filename

# ================= هندلرها =================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌟 رزرو لینک جدید", callback_data="new_reserve"))
    markup.add(types.InlineKeyboardButton("📋 لیست رزروها", callback_data="list_reserve"))
    bot.send_message(
        message.chat.id,
        "👋 **به ربات لینکدونی خوش آمدی!**\n\n"
        "🔗 اینجا می‌تونی لینک خودت رو رزرو کنی\n"
        "🎨 یه بنر شیک و حرفه‌ای تحویل بگیری\n"
        "📤 و مستقیماً تو کانال لینکدونی پست بشه!\n\n"
        "برای شروع روی دکمه زیر کلیک کن 👇",
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "new_reserve":
        msg = bot.send_message(call.message.chat.id, "📌 **عنوان بنر رو بفرست:**\n(مثلاً: تخفیف ویژه امروز)")
        bot.register_next_step_handler(msg, get_title)
    elif call.data == "list_reserve":
        bot.answer_callback_query(call.id, "به زودی...")

def get_title(message):
    title = message.text
    msg = bot.send_message(message.chat.id, "📝 **توضیحات بنر رو بفرست:**\n(مثلاً: ۵۰٪ تخفیف برای ۱۰ نفر اول)")
    bot.register_next_step_handler(msg, lambda m: get_description(m, title))

def get_description(message, title):
    desc = message.text
    msg = bot.send_message(message.chat.id, "🔗 **لینک مورد نظر رو بفرست:**\n(مثلاً: https://t.me/yourchannel)")
    bot.register_next_step_handler(msg, lambda m: get_link(m, title, desc))

def get_link(message, title, desc):
    link = message.text
    msg = bot.send_message(message.chat.id, "📅 **تاریخ رزرو رو بفرست:**\n(مثلاً: ۱۴۰۵/۰۳/۲۵)")
    bot.register_next_step_handler(msg, lambda m: get_date(m, title, desc, link))

def get_date(message, title, desc, link):
    date = message.text
    reserved_by = message.from_user.first_name
    
    # پیام در حال ساخت
    wait_msg = bot.send_message(message.chat.id, "🎨 در حال ساخت بنر شیک شما...")
    
    try:
        # ساخت بنر
        filename = create_banner(title, desc, link, date, reserved_by)
        
        # ارسال به کاربر
        with open(filename, 'rb') as photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption=f"✅ **بنر شما با موفقیت ساخته شد!**\n\n🎯 عنوان: {title}\n🔗 لینک: {link}\n📅 تاریخ: {date}"
            )
        
        # ارسال به کانال
        channel_caption = f"""
🌟 **رزرو جدید لینکدونی** 🌟

🎯 **{title}**

📝 {desc}

🔗 **لینک:** {link}
📅 **تاریخ:** {date}
👤 **رزرو شده توسط:** {reserved_by}

💎 _@Linkdoni | لینکدونی_
        """
        with open(filename, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo, caption=channel_caption, parse_mode='Markdown')
        
        # پاک کردن پیام انتظار
        bot.delete_message(message.chat.id, wait_msg.message_id)
        
        # پاک کردن فایل
        os.remove(filename)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در ساخت بنر: {str(e)}")

# ================= اجرا =================
if __name__ == "__main__":
    print("🤖 ربات لینکدونی با بنر حرفه‌ای شروع به کار کرد...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
