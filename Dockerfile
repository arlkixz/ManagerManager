FROM ghcr.io/railwayapp/nixpacks:ubuntu-1745885067

WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN python -m venv --copies /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install -r requirements.txt

# کپی کل پروژه
COPY . .

# تنظیم PATH برای محیط مجازی
ENV PATH="/opt/venv/bin:$PATH"

# اجرای ربات
CMD ["python", "bot.py"]
