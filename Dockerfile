FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن فایل جدید start.sh رو فراموش نکن
COPY bot.py start.sh ./

# به start.sh اجازه اجرا بده
RUN chmod +x start.sh

# حالا دیگه به جای خود bot.py، این اسکریپت رو اجرا کن
CMD ["/bin/bash", "start.sh"]
