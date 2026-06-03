#!/usr/bin/env python3
# ============================================================
# Flash Crash Sniper — Trade Lak Bot
# يراقب BTC/ETH/BNB كل 0.5 ثانية
# إذا انخفض السعر دون $5 (خلل تقني) → يشتري فوراً بكل السيولة
# ============================================================
import time
import logging
import json
import os
import sys
import requests
import ccxt

# ─── إعداد المسار ─────────────────────────────────────────
BOT_DIR = '/root/trade_lak_bot'
sys.path.insert(0, BOT_DIR)

from config.config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    TELEGRAM_BOT_TOKEN, DRY_RUN
)

# ─── إعداد اللوج ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BOT_DIR, 'logs', 'flash_crash_sniper.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('flash_crash_sniper')

# ─── الإعدادات ────────────────────────────────────────────
SIGNAL_CHANNEL_ID  = "-1003834970832"   # Trade Lak Signal
OWNER_CHAT_ID      = "6633826689"        # AGT LamoD — رسائل خاصة
CRASH_THRESHOLD    = 5.0                # السعر الذي يُعتبر خللاً تقنياً ($)
WATCH_SYMBOLS      = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']
POLL_INTERVAL      = 0.5               # فحص كل 0.5 ثانية
COOLDOWN_PER_SYM   = 3600             # ساعة كاملة بعد كل شراء لنفس العملة
STATE_FILE         = os.path.join(BOT_DIR, 'data', 'flash_crash_state.json')

# ─── حالة الـ Cooldown ────────────────────────────────────
_last_buy: dict = {}   # symbol → timestamp of last buy

def _load_state():
    global _last_buy
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                _last_buy = json.load(f)
    except Exception:
        _last_buy = {}

def _save_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(_last_buy, f)
    except Exception as e:
        logger.error(f"خطأ في حفظ الحالة: {e}")

def _can_buy(symbol: str) -> bool:
    last = _last_buy.get(symbol, 0)
    return (time.time() - last) > COOLDOWN_PER_SYM

def _mark_bought(symbol: str):
    _last_buy[symbol] = time.time()
    _save_state()

# ─── Telegram ─────────────────────────────────────────────
def _send_telegram(msg: str, chat_id: str = None):
    target = chat_id or SIGNAL_CHANNEL_ID
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": target, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"خطأ Telegram ({target}): {e}")
        return False

def _notify_all(msg: str):
    """إرسال رسالة خاصة للمالك فقط"""
    _send_telegram(msg, OWNER_CHAT_ID)

# ─── OKX Client ───────────────────────────────────────────
def _build_client():
    return ccxt.okx({
        'apiKey':    OKX_API_KEY,
        'secret':    OKX_SECRET_KEY,
        'password':  OKX_PASSPHRASE,
        'enableRateLimit': True,
        'options':   {'defaultType': 'spot'}
    })

def _get_price(client, symbol: str) -> float:
    """جلب السعر الحالي بسرعة قصوى"""
    try:
        ticker = client.fetch_ticker(symbol)
        return float(ticker.get('last') or ticker.get('ask') or 0)
    except Exception as e:
        logger.debug(f"خطأ جلب سعر {symbol}: {e}")
        return -1.0

def _get_usdt_balance(client) -> float:
    """جلب كامل رصيد USDT المتاح"""
    try:
        bal = client.fetch_balance()
        return float(bal['free'].get('USDT', 0))
    except Exception as e:
        logger.error(f"خطأ جلب الرصيد: {e}")
        return 0.0

def _execute_buy(client, symbol: str, price: float, usdt_amount: float) -> bool:
    """تنفيذ أمر شراء فوري بكل السيولة"""
    if DRY_RUN:
        logger.warning(f"[DRY RUN] سيتم شراء {symbol} بـ ${usdt_amount:.2f} عند ${price:.6f}")
        return True
    try:
        # حساب الكمية بناءً على السعر الحالي
        amount_coin = usdt_amount / price
        order = client.create_market_buy_order(symbol, amount_coin)
        logger.info(f"✅ تم الشراء: {symbol} | ${usdt_amount:.2f} | السعر: ${price:.6f} | Order: {order.get('id','?')}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل الشراء {symbol}: {e}")
        return False

# ─── رسالة التنبيه ────────────────────────────────────────
def _build_alert_msg(symbol: str, price: float, usdt_amount: float, success: bool) -> str:
    coin = symbol.replace('/USDT', '')
    now  = time.strftime('%H:%M:%S')
    date = time.strftime('%Y-%m-%d')
    status = "✅ تم الشراء بنجاح" if success else "❌ فشل تنفيذ الأمر"
    return (
        f"🚨 <b>Flash Crash Sniper — خلل تقني رُصد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💥 السعر الخاطئ: <b>${price:.6f}</b>  (أقل من ${CRASH_THRESHOLD})\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 المبلغ المستخدم: <b>${usdt_amount:.2f}</b>\n"
        f"📊 الحالة: {status}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>هذه صفقة استغلال خلل تقني — احتفظ بها وبِع يدوياً</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}  |  📅 {date}"
    )

# ─── الحلقة الرئيسية ──────────────────────────────────────
def run():
    logger.info("🚀 Flash Crash Sniper يعمل — يراقب: " + ", ".join(WATCH_SYMBOLS))
    logger.info(f"   الحد: ${CRASH_THRESHOLD} | الفحص كل {POLL_INTERVAL}s")

    _load_state()
    client = _build_client()

    # اختبار الاتصال
    try:
        client.load_markets()
        logger.info("✅ تم الاتصال بـ OKX بنجاح")
    except Exception as e:
        logger.critical(f"❌ فشل الاتصال بـ OKX: {e}")
        sys.exit(1)

    consecutive_errors = {s: 0 for s in WATCH_SYMBOLS}

    while True:
        for symbol in WATCH_SYMBOLS:
            try:
                price = _get_price(client, symbol)

                # تجاهل الأخطاء (price = -1)
                if price < 0:
                    consecutive_errors[symbol] += 1
                    if consecutive_errors[symbol] >= 10:
                        logger.warning(f"⚠️ {symbol}: 10 أخطاء متتالية في جلب السعر")
                        consecutive_errors[symbol] = 0
                    continue

                consecutive_errors[symbol] = 0

                # ─── الشرط الرئيسي: سعر أقل من $5 ──────────────
                if 0 < price < CRASH_THRESHOLD:
                    logger.warning(f"🚨 خلل تقني رُصد! {symbol} = ${price:.6f}")

                    if not _can_buy(symbol):
                        logger.info(f"⏸ {symbol}: cooldown نشط — تم الشراء مسبقاً")
                        continue

                    # جلب كامل السيولة المتاحة
                    usdt_balance = _get_usdt_balance(client)
                    if usdt_balance < 1.0:
                        logger.warning(f"⚠️ رصيد USDT غير كافٍ: ${usdt_balance:.2f}")
                        _notify_all(
                            f"⚠️ <b>Flash Crash Sniper</b>\n"
                            f"رُصد خلل في {symbol} (${price:.6f}) لكن الرصيد غير كافٍ: ${usdt_balance:.2f}"
                        )
                        continue

                    logger.info(f"💰 الرصيد المتاح: ${usdt_balance:.2f} — سيتم الشراء بالكامل")

                    # تنفيذ الشراء
                    success = _execute_buy(client, symbol, price, usdt_balance)

                    # إرسال التنبيه للقناة + رسالة خاصة
                    msg = _build_alert_msg(symbol, price, usdt_balance, success)
                    _notify_all(msg)

                    if success:
                        _mark_bought(symbol)
                        logger.info(f"✅ {symbol}: تم الشراء بـ ${usdt_balance:.2f} @ ${price:.6f}")
                    else:
                        logger.error(f"❌ {symbol}: فشل الشراء @ ${price:.6f}")

            except Exception as e:
                logger.error(f"خطأ في مراقبة {symbol}: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    run()
