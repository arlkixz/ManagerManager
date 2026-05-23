#!/bin/bash

# ببینیم آیا از قبل متغیر داریم یا نه
if [ -n "$CHANNEL_NAME" ] && [ -n "$POST_ID" ]; then
    echo "🎯 دارم میروم برای کانال $CHANNEL_NAME و پست $POST_ID بازدید میگیرم..."
    # اینجا دستور اصلی اجرا میشه
    python bot.py -c "$CHANNEL_NAME" -pt "$POST_ID" -m auto
else
    echo "⚠️  متغیرهای کانال و پست رو توی بخش Variables ست کن بعد دوباره دیپلوی کن."
    echo "مثال: CHANNEL_NAME = my_channel , POST_ID = 123"
    # اگه متغیر نبود، فقط یه پیام نشون بده که همه چی اوکیه
    python bot.py --help
fi
