#!/bin/bash

if [ -n "$CHANNEL_NAME" ] && [ -n "$POST_ID" ]; then
    echo "🎯 Starting bot for channel: $CHANNEL_NAME, post: $POST_ID"
    exec python bot.py -c "$CHANNEL_NAME" -pt "$POST_ID" -m list -p proxies.txt
else
    echo "❌ Please set CHANNEL_NAME and POST_ID in Variables"
    exec python bot.py --help
fi
