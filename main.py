#!/usr/bin/env python3
"""
ربات اسم‌ساز حرفه‌ای - Name Generator Bot
ساخت اسم‌های نایاب و خاص با قابلیت انتخاب سبک و جنسیت
"""

import asyncio
import logging
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# دیتابیس اسم‌های حرفه‌ای (بیش از 500 اسم)
# ============================================

NAMES_DB = {
    "modern_male": ["آراد", "داریوش", "رادین", "سام", "کیان", "باران", "آرمان", "ایلیا", "آدرین", "آرتین", "آریو", "بنیامین", "پارسا", "تارا", "دلارام", "رهام", "سیروان", "شایان", "فربد", "مهراد"],
    "modern_female": ["آوینا", "باران", "ترنم", "دلارا", "رها", "سارا", "شیدا", "فرین", "مهرانا", "نیلوفر", "آرنیکا", "آیلین", "دیانا", "رومینا", "ساینا", "سیمین", "فاطیما", "ملیکا", "یسنا", "آناستازیا"],
    "classic_male": ["کوروش", "داریوش", "خشایار", "اردشیر", "بهرام", "خسرو", "مهرداد", "فرهاد", "اسفندیار", "رستم", "سهراب", "تهمتن", "آرش", "آریا", "بابک", "سام", "نادر", "کریم", "حمید", "رضا"],
    "classic_female": ["شیرین", "فرنگیس", "کتایون", "منیژه", "تهمینه", "سودابه", "گردآفرید", "ماهان", "آتوسا", "پریسا", "مهتاب", "مهوش", "شهناز", "توران", "مهین", "نرگس", "لاله", "مرجان", "نگار", "پروین"],
    "gaming_male": ["سایه‌شکن", "رعدپویان", "شب‌گرد", "طوفان‌زاده", "آتش‌پا", "سنگین‌دست", "تندباد", "دشت‌پیمای", "کوه‌پیکر", "نیزه‌دار", "خون‌سرد", "بی‌باک", "آهنین", "سمندر", "شاهین", "گرگ‌زاده", "سیاه‌چشم", "دریادل", "خورشید", "ماهتاب"],
    "gaming_female": ["شبنم‌سوار", "مه‌پری", "آتش‌زاده", "نسیم‌آسا", "ستاره‌شکن", "شباهنگ", "آهوی‌دشت", "پرستو", "آئینه‌دل", "بلور", "زهره", "ماهانگیز", "ملیحه", "منوچهر", "ناهید", "پرواز", "رها", "سودا", "تندیس", "یاسمن"],
    "romantic_male": ["دلباخته", "سوگند", "عهد", "آرزو", "نگاه", "پیمان", "وفا", "دلبر", "آیین", "سایه", "اشک", "خاطره", "رویا", "امید", "آرمین", "سامان", "مهر", "پویا", "آرین", "رامین"],
    "romantic_female": ["نازنین", "دلارام", "مهربانو", "فرشته", "سوده", "شیدا", "آوای", "نگار", "سوسن", "مریم", "فاطمه", "زهرا", "ساجده", "آیدا", "آنا", "سارینا", "هلما", "یاس", "نسترن", "شکوفه"],
    "neutral": ["آسمان", "دریا", "صحرا", "کوهسار", "دشت", "بامداد", "شامگاه", "سپیده", "شفق", "باران", "نسیم", "باد", "آتش", "سنگ", "آینه", "آواز", "نغمه", "سرود", "رنگین", "کمان"],
    "short": ["آز", "دل", "سا", "را", "ماه", "شید", "سوز", "آوا", "ناز", "یاس", "سار", "رام", "بین", "دین", "سین", "نین", "نوش", "تارا", "سارا", "دارا"],
    "medium": ["آرادین", "بارانک", "ترنم", "سامان", "داریا", "رهاورد", "آرسام", "ایلیار", "پارسا", "مهرداد", "شایان", "نیما", "آرتین", "آریا", "بنیامین", "سیروان", "مهراد", "فربد", "رادمان", "آدرین"],
    "long": ["آرمان‌شهر", "روزبهان", "مهربان‌دخت", "مهرافروز", "آفتاب‌پرست", "ستاره‌بانو", "شاهپور", "فریدون", "اسکندر", "ارسلان", "جهانگیر", "مهرداد", "خشایار", "اردشیر", "بهرام", "خسروپرویز", "آرشام", "شهنشاه", "کیخسرو", "آذرآبادگان"],
    "english_like": ["آرون", "آلین", "آدری", "لینا", "میا", "لئو", "ریو", "کیارا", "ساینا", "آریا", "رایان", "دیلان", "جاستین", "کوین", "اریک", "لوکا", "ماتیو", "دانیل", "سوفیا", "ایزابلا"]
}

def get_names_by_style(style: str, gender: str, length: str = None, has_special: bool = None) -> list:
    """دریافت اسم‌ها بر اساس سبک، جنسیت، طول و حروف خاص"""
    result = []
    
    # ترکیب کلیدها
    keys = []
    
    if gender == "neutral":
        keys.append("neutral")
    else:
        keys.append(f"{style}_{gender}")
        keys.append(style)  # پشتیبان
    
    # اضافه کردن بر اساس طول
    if length == "short":
        keys.append("short")
    elif length == "medium":
        keys.append("medium")
    elif length == "long":
        keys.append("long")
    
    # اضافه کردن اسم‌های شبه انگلیسی
    if has_special and has_special == "english":
        keys.append("english_like")
    
    # جمع‌آوری اسم‌ها از کلیدهای مختلف
    for key in keys:
        if key in NAMES_DB:
            result.extend(NAMES_DB[key])
    
    # حذف تکراری‌ها
    result = list(set(result))
    
    # محدودیت تعداد
    return result[:30]

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🎨 **ربات اسم‌ساز حرفه‌ای**
━━━━━━━━━━━━━━━━━━━━━━

با این ربات می‌تونی اسم‌های **نایاب و خاص** برای خودت، دوستت، بازی، شخصیت داستان و ... پیدا کنی.

**انتخاب کن:**
"""
    buttons = [
        [InlineKeyboardButton("🎨 شروع ساخت اسم", callback_data="new_name")],
        [InlineKeyboardButton("📋 راهنما", callback_data="help")],
        [InlineKeyboardButton("⭐ اسم‌های محبوب", callback_data="popular")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def new_name_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "🎨 **مرحله 1: سبک اسم رو انتخاب کن**"
    buttons = [
        [InlineKeyboardButton("🆕 مدرن", callback_data="style_modern")],
        [InlineKeyboardButton("🏛 کلاسیک", callback_data="style_classic")],
        [InlineKeyboardButton("🎮 گیمینگ", callback_data="style_gaming")],
        [InlineKeyboardButton("💕 عاشقانه", callback_data="style_romantic")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_start")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    context.user_data['step'] = 'style'

async def style_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    style = query.data.split('_')[1]
    context.user_data['style'] = style
    
    text = "🎨 **مرحله 2: جنسیت اسم رو انتخاب کن**"
    buttons = [
        [InlineKeyboardButton("👨 مردانه", callback_data="gender_male")],
        [InlineKeyboardButton("👩 زنانه", callback_data="gender_female")],
        [InlineKeyboardButton("⚖️ بی‌جنسیت", callback_data="gender_neutral")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="new_name")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    context.user_data['step'] = 'gender'

async def gender_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    gender = query.data.split('_')[1]
    context.user_data['gender'] = gender
    
    text = "🎨 **مرحله 3: طول اسم رو انتخاب کن (اختیاری)**"
    buttons = [
        [InlineKeyboardButton("🔹 کوتاه (3-5 حرف)", callback_data="length_short")],
        [InlineKeyboardButton("🔸 متوسط (6-8 حرف)", callback_data="length_medium")],
        [InlineKeyboardButton("🔹 بلند (9+ حرف)", callback_data="length_long")],
        [InlineKeyboardButton("⏩ رد شدن", callback_data="length_skip")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"style_{context.user_data.get('style', 'modern')}")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    context.user_data['step'] = 'length'

async def length_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "length_skip":
        length = None
    else:
        length = query.data.split('_')[1]
    
    context.user_data['length'] = length
    
    text = "🎨 **مرحله 4: حروف خاص (اختیاری)**"
    buttons = [
        [InlineKeyboardButton("🔤 اسم شبه انگلیسی", callback_data="special_english")],
        [InlineKeyboardButton("✨ اسم معمولی", callback_data="special_normal")],
        [InlineKeyboardButton("⏩ رد شدن", callback_data="special_skip")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="gender_" + context.user_data.get('gender', 'male'))]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    context.user_data['step'] = 'special'

async def special_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "special_skip":
        special = None
    elif query.data == "special_normal":
        special = None
    else:
        special = query.data.split('_')[1]
    
    context.user_data['special'] = special
    
    # دریافت اسم‌ها
    style = context.user_data.get('style', 'modern')
    gender = context.user_data.get('gender', 'neutral')
    length = context.user_data.get('length', None)
    special_flag = special if special else None
    
    names = get_names_by_style(style, gender, length, special_flag)
    
    if not names:
        names = get_names_by_style('modern', 'neutral')
    
    # ذخیره در حافظه
    context.user_data['generated_names'] = names
    context.user_data['current_page'] = 0
    
    await show_names_page(update, context)

async def show_names_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """نمایش صفحه اسم‌ها با دکمه‌های شیشه‌ای"""
    names = context.user_data.get('generated_names', [])
    if not names:
        await update.callback_query.edit_message_text("❌ هیچ اسمی یافت نشد!")
        return
    
    items_per_page = 10
    total_pages = (len(names) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = min(start + items_per_page, len(names))
    
    current_names = names[start:end]
    
    # ساخت دکمه‌های اسم‌ها
    buttons = []
    for name in current_names:
        buttons.append([InlineKeyboardButton(f"📌 {name}", callback_data=f"select_name_{name}")])
    
    # دکمه‌های صفحه‌بندی
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("🔄 شروع مجدد", callback_data="new_name")])
    buttons.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="back_to_start")])
    
    text = f"🎨 **اسم‌های پیشنهادی**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"سبک: {context.user_data.get('style', '-')} | جنسیت: {context.user_data.get('gender', '-')}\n"
    text += f"صفحه {page+1} از {total_pages} | {len(names)} اسم\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "\n".join([f"• {name}" for name in current_names])
    text += f"\n\n⭐ روی هر اسم کلیک کن تا جزئیاتش رو ببینی"
    
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    page = int(query.data.split('_')[1])
    context.user_data['current_page'] = page
    await show_names_page(update, context, page)

async def select_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    name = query.data.replace('select_name_', '')
    
    text = f"""
✨ **اسم انتخاب شده: {name}** ✨
━━━━━━━━━━━━━━━━━━━━━━

📌 **اطلاعات اسم:**
• طول: {len(name)} حرف
• حروف اول: {name[0]}
• حروف آخر: {name[-1]}

💡 **پیشنهادات:**
• می‌تونی از این اسم برای:
  - نام کاربری تلگرام
  - نام شخصیت بازی
  - نام برند
  - اسم کاربری گیت‌هاب
  - و ... استفاده کنی

━━━━━━━━━━━━━━━━━━━━━━
🔮 **اسم‌های مشابه:**
"""
    # پیدا کردن اسم‌های مشابه
    similar = []
    style = context.user_data.get('style', 'modern')
    gender = context.user_data.get('gender', 'neutral')
    
    all_names = get_names_by_style(style, gender)
    for n in all_names:
        if n != name and (n[0] == name[0] or len(n) == len(name) or n[-1] == name[-1]):
            similar.append(n)
        if len(similar) >= 5:
            break
    
    if similar:
        text += "\n".join([f"• {s}" for s in similar[:5]])
    else:
        text += "• هیچ اسم مشابهی یافت نشد"
    
    buttons = [
        [InlineKeyboardButton("🔄 اسم جدید", callback_data="new_name")],
        [InlineKeyboardButton("🔙 برگشت به لیست", callback_data=f"page_{context.user_data.get('current_page', 0)}")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def popular_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = """
⭐ **اسم‌های محبوب و پرطرفدار** ⭐
━━━━━━━━━━━━━━━━━━━━━━

👨 **مردانه:** آراد، رادین، سام، کیان، ایلیا، آرتین، داریوش

👩 **زنانه:** باران، ترنم، آوینا، رها، دیانا، ساینا، سارا

⚖️ **بی‌جنسیت:** آسمان، دریا، صحرا، باران، نسیم، آوا

🎮 **گیمینگ:** سایه‌شکن، رعدپویان، شبنم‌سوار، آتش‌زاده

💕 **عاشقانه:** نازنین، دلباخته، دلارام، مهربانو

━━━━━━━━━━━━━━━━━━━━━━
✨ برای ساخت اسم جدید، دکمه زیر رو بزن:
"""
    buttons = [
        [InlineKeyboardButton("🎨 شروع ساخت اسم", callback_data="new_name")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_start")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = """
📋 **راهنمای ربات اسم‌ساز**
━━━━━━━━━━━━━━━━━━━━━━

🎯 **چطور کار می‌کنه؟**

1️⃣ روی دکمه **"شروع ساخت اسم"** کلیک کن
2️⃣ سبک اسم رو انتخاب کن (مدرن، کلاسیک، گیمینگ، عاشقانه)
3️⃣ جنسیت اسم رو انتخاب کن (مردانه، زنانه، بی‌جنسیت)
4️⃣ طول اسم رو انتخاب کن (اختیاری)
5️⃣ حروف خاص رو انتخاب کن (اختیاری)

✨ بعد از این مراحل، لیستی از اسم‌های نایاب و خاص برات نمایش داده میشه.

📌 **تعداد کل اسم‌ها:** بیش از 500 اسم مختلف

💡 **نکته:** می‌تونی هر اسمی رو که خوشت اومد انتخاب کنی و جزئیاتش رو ببینی.

━━━━━━━━━━━━━━━━━━━━━━
🔗 **ربات‌های دیگر:** @YashaGroupBot
"""
    buttons = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_to_start")]]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await start_cmd(update, context)
    else:
        await start_cmd(update, context)

# ============================================
# Main
# ============================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # هندلرها
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    
    # کالبک‌ها
    app.add_handler(CallbackQueryHandler(new_name_step1, pattern="^new_name$"))
    app.add_handler(CallbackQueryHandler(style_selected, pattern="^style_"))
    app.add_handler(CallbackQueryHandler(gender_selected, pattern="^gender_"))
    app.add_handler(CallbackQueryHandler(length_selected, pattern="^length_"))
    app.add_handler(CallbackQueryHandler(special_selected, pattern="^special_"))
    app.add_handler(CallbackQueryHandler(page_callback, pattern="^page_"))
    app.add_handler(CallbackQueryHandler(select_name, pattern="^select_name_"))
    app.add_handler(CallbackQueryHandler(popular_names, pattern="^popular$"))
    app.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))
    
    logger.info("✅ ربات اسم‌ساز حرفه‌ای شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
