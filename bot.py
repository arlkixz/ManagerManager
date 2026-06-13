import telebot
from telebot import types
from PIL import Image, ImageDraw, ImageFont
import textwrap
import datetime
import os

# ================= تنظیمات =================
TOKEN = "YOUR_BOT_TOKEN_HERE"           # توکن ربات از BotFather
CHANNEL_ID = "@your_linkdoni_channel"   # آیدی کانال با @
ADMIN_ID = 123456789                    # (اختیاری) آیدی عددی ادمین برای گزارش

bot = telebot.TeleBot(TOKEN)

# ================= دیکشنری موقت رزروها =================
reservations = {}

# ================= تابع ساخت بنر شیک =================
def create_banner(title, description, link, date, reserved_by):
    # بوم با گرادیان
    img = Image.new('RGB', (1200, 630), color=(10, 10, 20))
    draw = ImageDraw.Draw(img)

    # گرادیان آبی-بنفش (بهینه‌تر)
    for y in range(630):
        r = 20 + y // 10
        g = 10
        b = 80 + y // 8
        draw.line([(0, y), (1200, y)], fill=(r, g, b))

    # حاشیه درخشان
    draw.rectangle([30, 30, 1170, 600], outline=(100, 200, 255), width=8)

    # فونت‌ها
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 80)
        text_font  = ImageFont.truetype(font_path, 45)
        small_font = ImageFont.truetype(font_path, 35)
    except:
        title_font = ImageFont.load_default()
        text_font  = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # عنوان
    draw.text((80, 80), title[:40], fill=(255, 255, 255), font=title_font)

    # توضیحات
    lines = textwrap.wrap(description, width=50)
    y = 200
    for line in lines[:4]:
        draw.text((80, y), line, fill=(220, 230, 255), font=text_font)
        y += 55

    # اطلاعات رزرو
    draw.text((80, 420), f"لینک: {link}", fill=(0, 255, 200), font=small_font)
    draw.text((80, 475), f"تاریخ: {date}", fill=(255, 220, 100), font=small_font)
    draw.text((80, 530), f"رزرو توسط: {reserved_by}", fill=(180, 180, 255), font=small_font)

    # لوگوی لینکدونی (دیگه resize نداره)
    try:
        logo_font = ImageFont.truetype(font_path, 60)
    except:
        logo_font = ImageFont.load_default()
    draw.text((850, 520), "لینکدونی", fill=(100, 200, 255), font=logo_font)

    # ذخیره‌ی فایل
    filename = f"banner_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(filename, "PNG")
    return filename

# ================= هندلرها =================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌟 رزرو لینک جدید", callback_data="new_reserve"))
    bot.send_message(
        message.chat.id,
        "👋 به ربات لینکدونی خوش آمدی!\n"
        "برای رزرو لینک و ارسال بنر به کانال، دکمه زیر رو بزن.",
        reply_markup=markup
    )

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
    msg = bot.send_message(message.chat.id, "📅 تاریخ رزرو (مثلاً ۱۴۰۵/۰۳/۲۵):")
    bot.register_next_step_handler(msg, lambda m: get_date(m, title, desc, link))

def get_date(message, title, desc, link):
    date = message.text
    reserved_by = message.from_user.first_name

    # ساخت بنر
    filename = create_banner(title, desc, link, date, reserved_by)

    # ذخیره رزرو
    reservations[link] = {
        "title": title,
        "desc": desc,
        "by": reserved_by,
        "date": date
    }

    # ارسال پیش‌نمایش به کاربر
    with open(filename, 'rb') as photo:
        bot.send_photo(
            message.chat.id,
            photo,
            caption="✅ بنر شما با موفقیت ساخته و به کانال ارسال شد!"
        )

    # ارسال شیک به کانال (با HTML برای ایموجی‌های پرمیوم)
    channel_caption = f"""
🌟 <b>رزرو جدید لینکدونی</b> 🌟

🎯 <b>{title}</b>

📄 {desc}

🔗 <b>لینک:</b> {link}
📅 <b>تاریخ:</b> {date}
👤 <b>رزرو شده توسط:</b> {reserved_by}
    """
    with open(filename, 'rb') as photo:
        bot.send_photo(
            CHANNEL_ID,
            photo,
            caption=channel_caption,
            parse_mode='HTML'   # ✅ با ایموجی‌ها سازگاره
        )

    # پاکسازی فایل
    os.remove(filename)

    # لاگ برای ادمین (اختیاری)
    if ADMIN_ID:
        bot.send_message(ADMIN_ID, f"📥 رزرو جدید:\nعنوان: {title}\nلینک: {link}\nکاربر: {reserved_by}")

# ================= استارت ربات =================
print("🤖 ربات لینکدونی روشن شد...")
bot.infinity_polling()
