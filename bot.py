import os
import sys
import telebot
from telebot import types
from PIL import Image, ImageDraw, ImageFont
import textwrap
import datetime

# ================= خواندن تنظیمات از Railway =================
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@test")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

# بررسی توکن
if not TOKEN:
    print("❌ خطا: توکن ربات تنظیم نشده!")
    print("لطفاً در Railway Variables یک متغیر به اسم BOT_TOKEN بسازید.")
    sys.exit(1)

print(f"✅ توکن دریافت شد: {TOKEN[:10]}...")
print(f"✅ کانال: {CHANNEL_ID}")

bot = telebot.TeleBot(TOKEN)

# ================= ساخت بنر =================
def create_banner(title, description, link, date, reserved_by):
    img = Image.new('RGB', (1200, 630), color=(10, 10, 20))
    draw = ImageDraw.Draw(img)

    for y in range(630):
        r = 20 + y // 10
        g = 10
        b = 80 + y // 8
        draw.line([(0, y), (1200, y)], fill=(r, g, b))

    draw.rectangle([30, 30, 1170, 600], outline=(100, 200, 255), width=8)

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 45)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((80, 80), title[:40], fill=(255, 255, 255), font=title_font)

    lines = textwrap.wrap(description, width=50)
    y = 200
    for line in lines[:4]:
        draw.text((80, y), line, fill=(220, 230, 255), font=text_font)
        y += 55

    draw.text((80, 420), f"Link: {link}", fill=(0, 255, 200), font=small_font)
    draw.text((80, 475), f"Date: {date}", fill=(255, 220, 100), font=small_font)
    draw.text((80, 530), f"By: {reserved_by}", fill=(180, 180, 255), font=small_font)

    try:
        logo_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        logo_font = ImageFont.load_default()
    draw.text((850, 520), "Linkdoni", fill=(100, 200, 255), font=logo_font)

    filename = f"banner_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(filename, "PNG")
    return filename

# ================= هندلرها =================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌟 رزرو لینک جدید", callback_data="new_reserve"))
    bot.send_message(message.chat.id, "👋 به ربات لینکدونی خوش آمدی!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "new_reserve":
        msg = bot.send_message(call.message.chat.id, "📌 عنوان بنر رو بفرست:")
        bot.register_next_step_handler(msg, get_title)

def get_title(message):
    title = message.text
    msg = bot.send_message(message.chat.id, "📝 توضیحات بنر:")
    bot.register_next_step_handler(msg, lambda m: get_description(m, title))

def get_description(message, title):
    desc = message.text
    msg = bot.send_message(message.chat.id, "🔗 لینک مورد نظر:")
    bot.register_next_step_handler(msg, lambda m: get_link(m, title, desc))

def get_link(message, title, desc):
    link = message.text
    msg = bot.send_message(message.chat.id, "📅 تاریخ رزرو:")
    bot.register_next_step_handler(msg, lambda m: get_date(m, title, desc, link))

def get_date(message, title, desc, link):
    date = message.text
    reserved_by = message.from_user.first_name

    filename = create_banner(title, desc, link, date, reserved_by)

    with open(filename, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption="✅ بنر شما آماده شد!")

    channel_caption = f"""
🌟 <b>رزرو جدید</b> 🌟

🎯 <b>{title}</b>
📄 {desc}

🔗 <b>لینک:</b> {link}
📅 <b>تاریخ:</b> {date}
👤 <b>توسط:</b> {reserved_by}
    """
    try:
        with open(filename, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo, caption=channel_caption, parse_mode='HTML')
        print(f"✅ بنر به کانال {CHANNEL_ID} ارسال شد")
    except Exception as e:
        print(f"⚠️ خطا در ارسال به کانال: {e}")

    os.remove(filename)

# ================= اجرا =================
if __name__ == "__main__":
    print("🤖 ربات لینکدونی شروع به کار کرد...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"❌ خطا: {e}")
