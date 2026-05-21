import logging
import os
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# -------------------- تنظیمات اولیه --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- دیتابیس حروف و افکت‌های خلاقانه --------------------

# حروف انگلیسی با استایل‌های مختلف (میلیون‌ها ترکیب ممکن)
LETTER_STYLES = {
    "normal": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "bold": "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳",
    "italic": "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻",
    "bold_italic": "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛",
    "script": "𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏",
    "fraktur": "𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷",
    "monospace": "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣",
    "double_struck": "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫",
    "small_caps": "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ",
    "upside_down": "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz",
    "circled": "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
    "squared": "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉",
}

PREFIXES = ["★", "☆", "✧", "✦", "✩", "⍟", "⊹", "༺", "༻", "✿", "❀", "✾", "❁", "✽", "✼", "✻", "✺", "✹", "✸", "✦", "✧", "✨", "🌟", "⭐", "🌙", "☀️", "🔥", "💀", "👑", "🎭", "⚡", "❄️", "🌈", "🍃", "🌸"]
SUFFIXES = ["★", "☆", "✧", "✦", "✩", "⍟", "⊹", "༺", "༻", "✿", "❀", "✾", "❁", "✽", "✼", "✻", "✺", "✹", "✸", "✦", "✧", "✨", "🌟", "⭐", "🌙", "☀️", "🔥", "💀", "👑", "🎭", "⚡", "❄️", "🌈", "🍃", "🌸", "‏", "‌", "‍", "‎", "‏‏‎", "‌‌‎‎"]

WORD_PARTS = {
    "cool": ["Dark", "Shadow", "Night", "Storm", "Thunder", "Blaze", "Frost", "Ghost", "Phantom", "Crimson", "Silver", "Golden", "Iron", "Steel", "Crystal", "Midnight", "Dawn", "Dusk", "Eclipse", "Infinity"],
    "mystic": ["Moon", "Star", "Sky", "Cloud", "Wind", "Fire", "Water", "Earth", "Soul", "Spirit", "Oracle", "Mystic", "Arcane", "Ethereal", "Celestial", "Nebula", "Galaxy", "Void", "Abyss", "Eternity"],
    "action": ["Hunter", "Slayer", "Killer", "Warrior", "Knight", "Rogue", "Mage", "Wizard", "Assassin", "Guardian", "Defender", "Avenger", "Destroyer", "Conqueror", "Dominator", "Reaper", "Venom", "Fury", "Rage", "Wrath"],
    "nature": ["Wolf", "Raven", "Phoenix", "Dragon", "Tiger", "Eagle", "Falcon", "Hawk", "Lion", "Bear", "Fox", "Snake", "Spider", "Scorpion", "Crow", "Owl", "Bat", "Moth", "Butterfly", "Rose"],
    "myth": ["Zeus", "Odin", "Thor", "Loki", "Athena", "Apollo", "Artemis", "Hades", "Poseidon", "Ares", "Hermes", "Hera", "Demeter", "Aphrodite", "Dionysus", "Cronus", "Titan", "Nemesis", "Eros", "Nyx"],
    "dark": ["Darkness", "Shadow", "Nightmare", "Death", "Doom", "Gloom", "Despair", "Agony", "Pain", "Sorrow", "Grief", "Anguish", "Torment", "Misery", "Chaos", "Anarchy", "Ruin", "Destruction", "Oblivion", "Void"],
    "light": ["Light", "Hope", "Joy", "Peace", "Love", "Life", "Dream", "Destiny", "Fate", "Miracle", "Blessing", "Grace", "Mercy", "Truth", "Wisdom", "Honor", "Glory", "Victory", "Triumph", "Eden"]
}

# -------------------- توابع اصلی تولید اسم --------------------

def random_style_name(base_name: str) -> str:
    """تبدیل اسم معمولی به استایل‌های مختلف"""
    style = random.choice(list(LETTER_STYLES.keys()))
    mapping = LETTER_STYLES[style]
    
    # نگاشت حروف
    result = []
    for ch in base_name:
        if 'A' <= ch <= 'Z':
            idx = ord(ch) - ord('A')
            result.append(mapping[idx])
        elif 'a' <= ch <= 'z':
            idx = ord(ch) - ord('a') + 26
            result.append(mapping[idx])
        else:
            result.append(ch)
    return ''.join(result)

def generate_base_word() -> str:
    """تولید یک کلمه پایه تصادفی از بخش‌های مختلف"""
    category = random.choice(list(WORD_PARTS.keys()))
    return random.choice(WORD_PARTS[category])

def add_special_effects(name: str) -> str:
    """اضافه کردن افکت‌های خاص به اسم (نقطه، فاصله، خط تیره و...)"""
    effects = [
        lambda x: x,  # بدون تغییر
        lambda x: x.upper(),
        lambda x: x.lower(),
        lambda x: x.capitalize(),
        lambda x: '_'.join(x.split()),
        lambda x: '-'.join(x.split()),
        lambda x: '.'.join(x.split()),
        lambda x: x.replace(' ', '  '),
        lambda x: ' ' + x + ' ',
        lambda x: '.' + x + '.',
        lambda x: '..' + x + '..',
        lambda x: '...' + x + '...',
        lambda x: x.replace('a', '@').replace('e', '3').replace('i', '1').replace('o', '0').replace('s', '$'),
        lambda x: x.replace('A', 'Δ').replace('E', 'Σ').replace('I', 'Ι').replace('O', 'Ο').replace('S', 'Ϛ'),
    ]
    return random.choice(effects)(name)

def generate_name(style=None, length=None, has_space=True, has_dots=True, extra_long=False) -> str:
    """تولید اسم خلاقانه بر اساس پارامترها"""
    
    # انتخاب بخش‌ها
    parts_count = random.randint(1, 3)
    if extra_long:
        parts_count = random.randint(3, 5)
    
    name_parts = []
    for _ in range(parts_count):
        name_parts.append(generate_base_word())
    
    # اتصال بخش‌ها
    if has_space:
        separator = random.choice([' ', '_', '-', '.', '..', '...', '  ', ' . ', ' - ', ' _ '])
    else:
        separator = ''
    
    base_name = separator.join(name_parts)
    
    # محدودیت طول
    if length == "short" and len(base_name) > 8:
        base_name = base_name[:8]
    elif length == "medium" and len(base_name) > 12:
        base_name = base_name[:12]
    elif length == "long" and len(base_name) < 10:
        base_name = base_name + generate_base_word()
    
    # اضافه کردن افکت‌های نقطه
    if has_dots:
        base_name = add_special_effects(base_name)
    
    # استایل حروف
    if style == "bold":
        base_name = random_style_name(base_name)
    elif style == "fancy":
        base_name = random_style_name(base_name)
    
    # اضافه کردن پیشوند و پسوند
    if random.choice([True, False]):
        prefix = random.choice(PREFIXES)
        base_name = prefix + ' ' + base_name
    if random.choice([True, False]):
        suffix = random.choice(SUFFIXES)
        base_name = base_name + ' ' + suffix
    
    # حذف فاصله‌های اضافی
    base_name = re.sub(r'\s+', ' ', base_name).strip()
    
    return base_name

def get_names_list(count=20, **kwargs) -> list:
    """تولید لیستی از اسم‌ها با پارامترهای مشخص"""
    names = []
    for _ in range(count):
        names.append(generate_name(**kwargs))
    return list(set(names))[:count]  # حذف تکراری‌ها

# -------------------- هندلرهای ربات --------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🎨 **ربات اسم‌ساز حرفه‌ای**
━━━━━━━━━━━━━━━━━━━━━━

با این ربات می‌تونی اسم‌های **خاص و خلاقانه** برای تلگرام، بازی و... بسازی.

✨ **قابلیت‌ها:**
• اسم با حروف بزرگ/کوچک/شکسته
• فاصله، نقطه، خط تیره و... در اسم
• پیشوند/پسوند با علامت‌های خاص (★, ✧, ⋆, ༺, ❀ و...)
• استایل‌های مختلف (نرمال، بولد، ایتالیک، سایه‌دار و...)
• قابلیت اضافه کردن نقطه و خط تیره

🎯 **شروع کن:**
"""
    buttons = [
        [InlineKeyboardButton("🎲 اسم تصادفی", callback_data="random")],
        [InlineKeyboardButton("✨ اسم بولد (ضخیم)", callback_data="style_bold")],
        [InlineKeyboardButton("🖋 اسم فانتزی", callback_data="style_fancy")],
        [InlineKeyboardButton("📏 اسم کوتاه", callback_data="short")],
        [InlineKeyboardButton("📐 اسم بلند", callback_data="long")],
        [InlineKeyboardButton("🎨 همه استایل‌ها", callback_data="all_styles")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cmd = query.data
    names = []
    
    if cmd == "random":
        names = get_names_list(count=15)
        title = "🎲 **اسم‌های تصادفی:**"
    elif cmd == "style_bold":
        names = get_names_list(count=15, style="bold", has_space=True, has_dots=True)
        title = "✨ **اسم‌های بولد (ضخیم):**"
    elif cmd == "style_fancy":
        names = get_names_list(count=15, style="fancy", has_space=True, has_dots=True)
        title = "🖋 **اسم‌های فانتزی:**"
    elif cmd == "short":
        names = get_names_list(count=15, length="short", has_space=False, has_dots=False)
        title = "📏 **اسم‌های کوتاه (حداکثر 8 حرف):**"
    elif cmd == "long":
        names = get_names_list(count=10, extra_long=True, has_space=True, has_dots=True)
        title = "📐 **اسم‌های بلند (با فاصله و نقطه):**"
    elif cmd == "all_styles":
        all_names = []
        for _ in range(3):
            all_names.extend(get_names_list(count=5, style="bold", has_space=True, has_dots=True))
            all_names.extend(get_names_list(count=5, style="fancy", has_space=True,has_dots=True))
            all_names.extend(get_names_list(count=5, extra_long=True))
        names = list(set(all_names))[:20]
        title = "🎨 **همه استایل‌ها (بولد، فانتزی، بلند و...):**"
    
    if not names:
        names = get_names_list(count=10)
    
    # ساخت کیبورد اسم‌ها
    buttons = []
    for name in names[:20]:
        buttons.append([InlineKeyboardButton(f"📋 {name}", callback_data=f"copy_{name}")])
    
    buttons.append([InlineKeyboardButton("🔄 دوباره", callback_data=cmd)])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu")])
    
    text = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, name in enumerate(names[:20], 1):
        text += f"`{i}. {name}`\n"
    text += "\n⭐ روی هر اسم کلیک کن تا کپی کنی"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    name = query.data.replace("copy_", "")
    
    # ارسال اسم به صورت متن ساده برای کپی راحت
    await query.message.reply_text(f"✅ **اسم شما:** `{name}`\n\n✨ می‌تونی با لمس کردن، اون رو کپی کنی.", parse_mode=ParseMode.MARKDOWN)
    
    # یه دکمه برای بازگشت
    buttons = [[InlineKeyboardButton("🔙 برگشت", callback_data="menu")]]
    await query.message.reply_text("برای برگشت به منو، دکمه زیر رو بزن:", reply_markup=InlineKeyboardMarkup(buttons))

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await start_cmd(update, context)

# -------------------- Main --------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    
    app.add_handler(CallbackQueryHandler(generate_callback, pattern="^(random|style_bold|style_fancy|short|long|all_styles)$"))
    app.add_handler(CallbackQueryHandler(copy_callback, pattern="^copy_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))
    
    logger.info("ربات اسم‌ساز خلاق راه‌اندازی شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
