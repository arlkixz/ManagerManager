import json
import random
import urllib.request

# منبع پروکسی (سورس معتبر از روی گیت‌هاب) [citation:5]
PROXY_SOURCE_URL = "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/socks5.txt"

def fetch_proxy():
    try:
        print(f"در حال دریافت لیست پروکسی از {PROXY_SOURCE_URL}...")
        with urllib.request.urlopen(PROXY_SOURCE_URL, timeout=10) as response:
            data = response.read().decode('utf-8')
            proxies = data.strip().split('\n')
        
        # فیلتر کردن پروکسی‌های خالی و معتبر
        valid_proxies = [p.strip() for p in proxies if p.strip() and not p.startswith('#')]
        
        if valid_proxies:
            selected_proxy = random.choice(valid_proxies)
            print(f"پروکسی انتخاب شد: {selected_proxy}")
            return selected_proxy
        else:
            print("هیچ پروکسی معتبری در لیست یافت نشد.")
            return None
    except Exception as e:
        print(f"خطا در دریافت پروکسی: {e}")
        return None

if __name__ == "__main__":
    proxy = fetch_proxy()
    if proxy:
        # اینجا کدی که میخوای با پروکسی اجرا بشه رو قرار بده
        print(f"ربات با پروکسی {proxy} در حال اجراست...")
    else:
        print("ربات بدون پروکسی اجرا می‌شود (ریسک محدودیت).")
