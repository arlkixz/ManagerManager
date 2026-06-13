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
    img = Image.new('RGB', (1200, 630), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)
    
    # نوار رنگی سمت چپ
    for x in range(8):
        r = 88 + x * 5
        g = 101 + x * 3
        b = 242 - x * 2
        draw.rectangle([x, 0, x+1, 630], fill=(r, g, b))
    
    # کادر اصلی
    draw.rounded_rectangle([40, 40, 1160, 590], radius=20, outline=(60, 60, 80), width=3)
    
    # خط جداکننده
    draw.line([(60, 130), (1140, 130)], fill=(60, 60, 80), width=2)
    
    # دایره آیکن
    draw.ellipse([60, 55, 110, 105], outline=(88, 101, 242), width=4)
    
    try:
        icon_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        desc_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except:
        icon_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # متن داخل دایره
    draw.text((72, 62), "🔗", fill=(255, 255, 255), font=icon_font)
    
    # عنوان اصلی
    draw.text((130, 65), title[:35], fill=(255, 255, 255), font=title_font)
    
    # کادر توضیحات
    draw.rounded_rectangle([60, 150, 1140, 340], radius=15, fill=(30, 30, 40), outline=(50, 50, 65), width=2)
    
    lines = textwrap.wrap(description, width=45)
    y = 170
    for line in lines[:5]:
        draw.text((90, y), line, fill=(200, 210, 230), font=desc_font)
        y += 50
    
    # کادر لینک
    draw.rounded_rectangle([60, 370, 1140, 460], radius=12, fill=(25, 25, 35), outline=(88, 101, 242), width=3)
    draw.text((90, 390), f"🔗 {link}", fill=(88, 101, 242), font=small_font)
    
    # اطلاعات رزرو
    draw.text((90, 500), f"📅 {date}", fill=(150, 150, 160), font=small_font)
    draw.text((400, 500), f"👤 {reserved_by}", fill=(150, 150, 160), font=small_font)
    
    # لوگو لینکدونی
    try:
        logo_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
    except:
        logo_font = ImageFont.load_default()
    
    draw.rounded_rectangle([920, 50, 1130, 110], radius=15, fill=(88, 101, 242))
    draw.text((945, 65), "LINKdoni", fill=(255, 255, 255), font=logo_font)
    
    # خط تزئینی
    for i in range(3):
        y_pos = 580 + i
        draw.line([(60, y_pos), (300, y_pos)], fill=(88, 101, 242), width=2)
    
    filename = f"banner_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(filename, "PNG")
    return filename

# ================= هندلرها =================
@bot.message_handler(commands=['start'])
def start(message):
    # پاک کردن Markdown که مشکل ایجاد نکنه
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🌟 رزرو لینک جدید", callback_data="new_reserve")
    btn2 = types.InlineKeyboardButton("📋 رزروهای من", callback_data="my_reserves")
    btn3 = types.InlineKeyboardButton("ℹ️ راهنما", callback_data="help")
    btn4 = types.InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/YourSupportID")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    
    welcome_text = (
        "👋 به ربات لینکدونی خوش آمدی!\n\n"
        "🔗 اینجا می‌تونی لینک خودت رو رزرو کنی\n"
        "🎨 یه بنر شیک و حرفه‌ای تحویل بگیری\n"
        "📤 و مستقیماً تو کانال لینکدونی پست بشه!\n\n"
        "برای شروع روی دکمه زیر کلیک کن 👇"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "new_reserve":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "📌 عنوان بنر رو بفرست:\n(مثلاً: تخفیف ویژه امروز)"
        )
        bot.register_next_step_handler(msg, get_title)
    
    elif call.data == "my_reserves":
        bot.answer_callback_query(call.id, "به زودی اضافه میشه! 🚧")
    
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        help_text = (
            "📚 راهنمای ربات لینکدونی:\n\n"
            "1️⃣ روی 'رزرو لینک جدید' کلیک کن\n"
            "2️⃣ عنوان بنر رو بفرست\n"
            "3️⃣ توضیحات رو بنویس\n"
            "4️⃣ لینک مورد نظر رو بفرست\n"
            "5️⃣ تاریخ رزرو رو بگو\n\n"
            "✅ بنر به صورت خودکار به کانال ارسال میشه!"
        )
        bot.send_message(call.message.chat.id, help_text)

def get_title(message):
    title = message.text
    msg = bot.send_message(
        message.chat.id,
        "📝 توضیحات بنر رو بفرست:\n(مثلاً: ۵۰٪ تخفیف برای ۱۰ نفر اول)"
    )
    bot.register_next_step_handler(msg, lambda m: get_description(m, title))

def get_description(message, title):
    desc = message.text
    msg = bot.send_message(
        message.chat.id,
        "🔗 لینک مورد نظر رو بفرست:\n(مثلاً: https://t.me/yourchannel)"
    )
    bot.register_next_step_handler(msg, lambda m: get_link(m, title, desc))

def get_link(message, title, desc):
    link = message.text
    msg = bot.send_message(
        message.chat.id,
        "📅 تاریخ رزرو رو بفرست:\n(مثلاً: ۱۴۰۵/۰۳/۲۵)"
    )
    bot.register_next_step_handler(msg, lambda m: get_date(m, title, desc, link))

def get_date(message, title, desc, link):
    date = message.text
    reserved_by = message.from_user.first_name
    
    wait_msg = bot.send_message(message.chat.id, "🎨 در حال ساخت بنر شیک شما...")
    
    try:
        filename = create_banner(title, desc, link, date, reserved_by)
        
        # ارسال به کاربر
        with open(filename, 'rb') as photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption=(
                    "✅ بنر شما با موفقیت ساخته شد!\n\n"
                    f"🎯 عنوان: {title}\n"
                    f"🔗 لینک: {link}\n"
                    f"📅 تاریخ: {date}\n\n"
                    "📤 به کانال لینکدونی ارسال شد!"
                )
            )
        
        # ارسال به کانال
        channel_caption = (
            f"🌟 رزرو جدید لینکدونی 🌟\n\n"
            f"🎯 {title}\n\n"
            f"📝 {desc}\n\n"
            f"🔗 لینک: {link}\n"
            f"📅 تاریخ: {date}\n"
            f"👤 رزرو شده توسط: {reserved_by}\n\n"
            f"💎 @Linkdoni | لینکدونی"
        )
        
        with open(filename, 'rb') as photo:
            sent_msg = bot.send_photo(CHANNEL_ID, photo, caption=channel_caption)
            
            # اطلاع‌رسانی به کاربر که به کانال ارسال شد
            bot.send_message(
                message.chat.id,
                f"📤 بنر با موفقیت به کانال ارسال شد!\n"
                f"🔗 لینک پست: https://t.me/{CHANNEL_ID.replace('@', '')}/{sent_msg.message_id}"
            )
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        os.remove(filename)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {str(e)}")

# ================= اجرا =================
if __name__ == "__main__":
    print("🤖 ربات لینکدونی با دکمه‌های شیشه‌ای شروع به کار کرد...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
