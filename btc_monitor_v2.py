#!/usr/bin/env python3
"""
مراقبة BTC — انتظار التعادل مع حماية من الهبوط
"""
import sys, os, json, time, requests, hmac, hashlib, base64, logging
from datetime import datetime

sys.path.insert(0, '/root/trade_lak_bot')
from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    handlers=[
        logging.FileHandler('/root/trade_lak_bot/logs/btc_monitor_v2.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()

def okx_request(method, path, body=""):
    ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    msg = ts + method.upper() + path + (body if body else "")
    sig = base64.b64encode(hmac.new(OKX_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()).decode()
    headers = {
        'OK-ACCESS-KEY': OKX_API_KEY,
        'OK-ACCESS-SIGN': sig,
        'OK-ACCESS-TIMESTAMP': ts,
        'OK-ACCESS-PASSPHRASE': OKX_PASSPHRASE,
        'Content-Type': 'application/json'
    }
    url = "https://www.okx.com" + path
    if method == 'GET':
        r = requests.get(url, headers=headers, timeout=10)
    else:
        r = requests.post(url, headers=headers, data=body, timeout=10)
    return r.json()

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")

def get_btc_price():
    r = requests.get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT", timeout=10).json()
    return float(r['data'][0]['last'])

def get_btc_balance():
    bal = okx_request('GET', '/api/v5/account/balance?ccy=BTC')
    for d in bal.get('data', [{}])[0].get('details', []):
        if d.get('ccy') == 'BTC':
            return float(d.get('availBal', 0))
    return 0.0

def sell_btc_all(qty, price, reason):
    """بيع كل BTC فوراً"""
    body = json.dumps({
        "instId": "BTC-USDT",
        "tdMode": "cash",
        "side": "sell",
        "ordType": "market",
        "sz": f"{qty:.6f}"
    })
    result = okx_request('POST', '/api/v5/trade/order', body)
    usd_val = qty * price
    loss = (price - AVG_PRICE) * qty
    log.info(f"{'✅' if result.get('code')=='0' else '❌'} بيع {qty:.6f} BTC @ ${price:,.2f} = ${usd_val:.2f} | {loss:+.2f}$")
    send_telegram(
        f"🔔 <b>BTC بيع — {reason}</b>\n"
        f"الكمية: <b>{qty:.6f} BTC</b>\n"
        f"السعر: <b>${price:,.2f}</b>\n"
        f"القيمة: <b>${usd_val:.2f}</b>\n"
        f"الربح/الخسارة: <b>${loss:+.2f}</b>\n"
        f"Bybit: لا يوجد BTC هناك"
    )
    return result

def sell_btc_partial(qty, price, label):
    """بيع جزء من BTC"""
    body = json.dumps({
        "instId": "BTC-USDT",
        "tdMode": "cash",
        "side": "sell",
        "ordType": "market",
        "sz": f"{qty:.6f}"
    })
    result = okx_request('POST', '/api/v5/trade/order', body)
    usd_val = qty * price
    profit = (price - AVG_PRICE) * qty
    log.info(f"{'✅' if result.get('code')=='0' else '❌'} {label}: بيع {qty:.6f} BTC @ ${price:,.2f} | ربح: ${profit:+.2f}")
    send_telegram(
        f"✅ <b>BTC بيع جزئي — {label}</b>\n"
        f"الكمية: <b>{qty:.6f} BTC</b>\n"
        f"السعر: <b>${price:,.2f}</b>\n"
        f"القيمة: <b>${usd_val:.2f}</b>\n"
        f"الربح/الخسارة: <b>${profit:+.2f}</b>"
    )
    return result

# ===== الإعدادات =====
AVG_PRICE = 59894.78          # متوسط سعر الشراء
BREAKEVEN = AVG_PRICE * 1.005 # مستوى التعادل +0.5%
EMERGENCY_STOP = 57500.0      # حد الهبوط الطارئ (بيع الكل)

# مستويات البيع التدريجي عند الارتفاع
SELL_LEVELS = [
    (0.25, BREAKEVEN,          "تعادل +0.5%"),
    (0.25, AVG_PRICE * 1.010,  "ربح +1%"),
    (0.25, AVG_PRICE * 1.020,  "ربح +2%"),
    (0.25, AVG_PRICE * 1.030,  "ربح +3%"),
]

STATE_FILE = '/root/trade_lak_bot/data/btc_sell_state.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"sold_levels": []}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ===== بدء التشغيل =====
log.info("=" * 55)
log.info("🔍 BTC Monitor v2 — انتظار التعادل مع حماية الهبوط")
log.info(f"متوسط الشراء: ${AVG_PRICE:,.2f}")
log.info(f"مستوى التعادل: ${BREAKEVEN:,.2f}")
log.info(f"حد الهبوط الطارئ: ${EMERGENCY_STOP:,.2f}")
log.info("=" * 55)

send_telegram(
    f"🔍 <b>BTC — مراقبة نشطة</b>\n"
    f"متوسط الشراء: <b>${AVG_PRICE:,.2f}</b>\n"
    f"التعادل عند: <b>${BREAKEVEN:,.2f}</b>\n"
    f"⚠️ بيع طارئ إذا انخفض إلى: <b>${EMERGENCY_STOP:,.2f}</b>"
)

initial_qty = get_btc_balance()
log.info(f"الكمية الكلية: {initial_qty:.6f} BTC = ${initial_qty * get_btc_price():,.2f}")

check_count = 0
while True:
    try:
        state = load_state()
        price = get_btc_price()
        btc_bal = get_btc_balance()
        check_count += 1

        if btc_bal < 0.0001:
            log.info("✅ تم بيع كل BTC. إنهاء المراقبة.")
            break

        pnl = (price - AVG_PRICE) * btc_bal
        pnl_pct = (price / AVG_PRICE - 1) * 100

        # === حد الهبوط الطارئ ===
        if price <= EMERGENCY_STOP:
            log.warning(f"🚨 حد الهبوط الطارئ! السعر ${price:,.2f} <= ${EMERGENCY_STOP:,.2f}")
            sell_btc_all(btc_bal, price, "🚨 حد الهبوط الطارئ")
            break

        # === مستويات البيع التدريجي ===
        for i, (pct, target, label) in enumerate(SELL_LEVELS):
            level_key = f"level_{i}"
            if level_key in state["sold_levels"]:
                continue
            if price >= target:
                sell_qty = round(initial_qty * pct, 6)
                sell_qty = min(sell_qty, btc_bal)
                if sell_qty >= 0.00001:
                    result = sell_btc_partial(sell_qty, price, label)
                    if result.get('code') == '0':
                        state["sold_levels"].append(level_key)
                        save_state(state)

        # تسجيل كل 5 دقائق
        if check_count % 5 == 0:
            log.info(f"📊 BTC: ${price:,.2f} | رصيد: {btc_bal:.6f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%) | للتعادل: ${BREAKEVEN - price:+.2f}")

        time.sleep(60)

    except Exception as e:
        log.error(f"خطأ: {e}")
        time.sleep(30)
