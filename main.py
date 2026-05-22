import asyncio
import aiohttp
import random
import sys
from colorama import init, Fore

init(autoreset=True)

async def send_view(session, url, proxy=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    try:
        async with session.get(url, headers=headers, proxy=proxy, timeout=10) as response:
            if response.status == 200:
                return True
    except:
        pass
    return False

async def main():
    print(Fore.CYAN + "Telegram Views Bot Starting...")
    
    channel = input("Enter channel/post link: ")
    count = int(input("Enter number of views: "))
    
    # ساخت URL مخصوص تلگرام
    if 't.me' in channel:
        view_url = channel.replace('t.me', 't.me/iv') + '?views'
    else:
        view_url = f"https://t.me/iv?url={channel}"
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(count):
            proxy = None
            # اگه پروکسی داری اینجا اضافه کن
            tasks.append(send_view(session, view_url, proxy))
            
            if len(tasks) >= 200:  # 200 تا همزمان
                await asyncio.gather(*tasks)
                tasks = []
            print(Fore.GREEN + f"Sent {i+1}/{count} views...")
        
        if tasks:
            await asyncio.gather(*tasks)
    
    print(Fore.GREEN + f"Done! Sent {count} views to {channel}")

if __name__ == "__main__":
    asyncio.run(main())
