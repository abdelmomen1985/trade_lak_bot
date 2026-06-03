#!/usr/bin/env python3
"""Send official 30x plan approval notification to Trade Lak Signal channel."""
import re
import sys
import datetime
import requests

cfg = open('/root/trade_lak_bot/config/config.py').read()

token_match = re.search(r"TELEGRAM_BOT_TOKEN\s*=\s*[\"'](.*?)[\"']", cfg)
signal_match = re.search(r"TELEGRAM_SIGNAL_CHAT\s*=\s*[\"'](.*?)[\"']", cfg)

if not token_match or not signal_match:
    print("ERROR: Could not find TELEGRAM_BOT_TOKEN or TELEGRAM_SIGNAL_CHAT in config.py")
    sys.exit(1)

TOKEN = token_match.group(1)
CHAT_ID = signal_match.group(1)

today = datetime.date.today()
target_date = today + datetime.timedelta(weeks=13)

msg = (
    "🏆 <b>خطة المضاعفة 30× — مُعتمدة رسمياً</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📅 <b>تاريخ الاعتماد:</b> {today.strftime('%Y-%m-%d')}\n"
    f"🏁 <b>الموعد النهائي:</b> {target_date.strftime('%Y-%m-%d')}\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "💰 <b>رأس المال الابتدائي:</b> $1,412.25\n"
    "🚀 <b>الهدف:</b> $42,743 (×30)\n"
    "📈 <b>المعدل الأسبوعي المطلوب:</b> +30%\n"
    "📊 <b>المدة:</b> 13 أسبوعاً\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚙️ <b>الضوابط المُفعَّلة:</b>\n\n"
    "🛡️ إيقاف تلقائي عند خسارتين متتاليتين (24 ساعة راحة)\n"
    "📏 حجم الصفقة: $300 → يرتفع تلقائياً عند العتبات\n"
    "📋 تقرير أسبوعي كل أحد الساعة 8 صباحاً\n"
    "🔍 Liquidity Grab Analyzer — 5 مستويات\n"
    "🎯 DCA دخول تدريجي 3 شرائح\n"
    "🧠 منطق سحب السيولة (Liquidity Grab)\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🗓️ <b>جدول العتبات:</b>\n\n"
    "الأسبوع 1  (2 يونيو)   → $1,835\n"
    "الأسبوع 4  (23 يونيو)  → $4,031\n"
    "الأسبوع 7  (14 يوليو)  → $8,856\n"
    "الأسبوع 10 (4 أغسطس)  → $19,455\n"
    "الأسبوع 13 (25 أغسطس) → $42,743 ✅\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <b>Trade Lak يعمل الآن — الانطلاق رسمي</b>\n"
    "🔔 ستصل إشارات الصفقات على هذه القناة فور تنفيذها"
)

r = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
    timeout=15
)
print(f"Status: {r.status_code} | ok: {r.json().get('ok')} | msg_id: {r.json().get('result', {}).get('message_id')}")
