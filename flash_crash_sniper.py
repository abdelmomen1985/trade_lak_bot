#!/usr/bin/env python3
# ============================================================
# Flash Crash Sniper v2 — Trade Lak Bot
# يراقب BTC/ETH/BNB/SOL كل 0.5 ثانية على OKX + Bybit
# إذا انخفض السعر دون $5 (خلل تقني) → يشتري فوراً بكل السيولة
# ============================================================
import time
import logging
import json
import os
import sys
import subprocess
import base64
import requests
import ccxt

# ─── إعداد المسار ─────────────────────────────────────────
BOT_DIR = '/root/trade_lak_bot'
sys.path.insert(0, BOT_DIR)
from config.config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    TELEGRAM_BOT_TOKEN, DRY_RUN,
    BYBIT_API_KEY, BYBIT_API_PRIVATE_KEY_PATH
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
SIGNAL_CHANNEL_ID  = "-1003834970832"
OWNER_CHAT_ID      = "6633826689"
CRASH_THRESHOLD    = 5.0                # السعر الذي يُعتبر خللاً تقنياً ($)
# العملات المشتركة بين OKX وBybit
WATCH_SYMBOLS      = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']

# العملات الحصرية على Bybit فقط (لا تُراقَب على OKX)
BYBIT_ONLY_SYMBOLS = [
    'MNT', 'BILL', 'H', 'VVV', 'BSB', 'HOLO', 'NVDAX', 'COINX', 'OPG', 'IO',
    'CRCLX', 'HOODX', 'DRIFT', 'FF', 'ICNT', 'XDC', 'NEWT', 'BLAST', 'AERO', 'NOM',
    'AZTEC', 'SPX', 'APEX', 'BOBA', 'KAS', 'VET', 'DEEP', 'AXL', 'BBSOL', 'BAN',
    'HFT', 'HOME', 'TSLAX', 'POPCAT', 'LUNC', 'VTHO', 'JASMY', 'PORTAL', 'ZIG',
]
POLL_INTERVAL      = 0.5               # فحص كل 0.5 ثانية
COOLDOWN_PER_SYM   = 3600             # ساعة كاملة بعد كل شراء لنفس العملة
STATE_FILE         = os.path.join(BOT_DIR, 'data', 'flash_crash_state.json')

# ─── حالة الـ Cooldown ────────────────────────────────────
_last_buy: dict = {}

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

def _can_buy(key: str) -> bool:
    last = _last_buy.get(key, 0)
    return (time.time() - last) > COOLDOWN_PER_SYM

def _mark_bought(key: str):
    _last_buy[key] = time.time()
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
    _send_telegram(msg, OWNER_CHAT_ID)

# ─── OKX Client ───────────────────────────────────────────
def _build_okx_client():
    return ccxt.okx({
        'apiKey':    OKX_API_KEY,
        'secret':    OKX_SECRET_KEY,
        'password':  OKX_PASSPHRASE,
        'enableRateLimit': True,
        'options':   {'defaultType': 'spot'}
    })

def _get_okx_price(client, symbol: str) -> float:
    try:
        ticker = client.fetch_ticker(symbol)
        return float(ticker.get('last') or ticker.get('ask') or 0)
    except Exception as e:
        logger.debug(f"[OKX] خطأ جلب سعر {symbol}: {e}")
        return -1.0

def _get_okx_balance(client) -> float:
    try:
        bal = client.fetch_balance()
        return float(bal['free'].get('USDT', 0))
    except Exception as e:
        logger.error(f"[OKX] خطأ جلب الرصيد: {e}")
        return 0.0

def _execute_okx_buy(client, symbol: str, price: float, usdt_amount: float) -> bool:
    if DRY_RUN:
        logger.warning(f"[OKX DRY RUN] شراء {symbol} بـ ${usdt_amount:.2f} @ ${price:.6f}")
        return True
    try:
        amount_coin = usdt_amount / price
        order = client.create_market_buy_order(symbol, amount_coin)
        logger.info(f"[OKX] ✅ تم الشراء: {symbol} | ${usdt_amount:.2f} @ ${price:.6f} | Order: {order.get('id','?')}")
        return True
    except Exception as e:
        logger.error(f"[OKX] ❌ فشل الشراء {symbol}: {e}")
        return False

# ─── Bybit Client (RSA) ───────────────────────────────────
import urllib.request

BYBIT_BASE_URL = 'https://api.bybit.com'
_bybit_session = requests.Session()
_bybit_session.headers.update({
    'Content-Type': 'application/json',
    'User-Agent': 'bybit-skill/1.4.1',
    'X-Referer': 'bybit-skill',
})

def _bybit_rsa_sign(param_str: str) -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        with open(BYBIT_API_PRIVATE_KEY_PATH, 'rb') as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        sig = private_key.sign(param_str.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(sig).decode('utf-8')
    except Exception:
        result = subprocess.run(
            ['openssl', 'dgst', '-sha256', '-sign', BYBIT_API_PRIVATE_KEY_PATH, '-binary'],
            input=param_str.encode('utf-8'), capture_output=True
        )
        return base64.b64encode(result.stdout).decode('utf-8')

def _bybit_auth_headers(param_str: str, timestamp: str) -> dict:
    sign = _bybit_rsa_sign(param_str)
    return {
        'X-BAPI-API-KEY': BYBIT_API_KEY,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-SIGN': sign,
        'X-BAPI-RECV-WINDOW': '5000',
        'X-BAPI-SIGN-TYPE': '2',
    }

def _get_bybit_price(symbol: str) -> float:
    """جلب سعر من Bybit بدون مصادقة (public endpoint)"""
    try:
        sym = symbol.replace('/', '').replace('-', '')
        r = _bybit_session.get(
            f'{BYBIT_BASE_URL}/v5/market/tickers',
            params={'category': 'spot', 'symbol': sym},
            timeout=3
        )
        data = r.json()
        if data.get('retCode') == 0:
            items = data.get('result', {}).get('list', [])
            if items:
                return float(items[0]['lastPrice'])
    except Exception as e:
        logger.debug(f"[Bybit] خطأ جلب سعر {symbol}: {e}")
    return -1.0

def _get_bybit_balance() -> float:
    """جلب رصيد USDT من Bybit Unified Account"""
    try:
        ts = str(int(time.time() * 1000))
        rw = '5000'
        query = 'accountType=UNIFIED&coin=USDT'
        ps = f'{ts}{BYBIT_API_KEY}{rw}{query}'
        headers = _bybit_auth_headers(ps, ts)
        r = _bybit_session.get(
            f'{BYBIT_BASE_URL}/v5/account/wallet-balance',
            params={'accountType': 'UNIFIED', 'coin': 'USDT'},
            headers=headers,
            timeout=10
        )
        data = r.json()
        if data.get('retCode') == 0:
            coins = data.get('result', {}).get('list', [{}])[0].get('coin', [])
            for c in coins:
                if c.get('coin') == 'USDT':
                    return float(c.get('walletBalance', 0))
    except Exception as e:
        logger.error(f"[Bybit] خطأ جلب الرصيد: {e}")
    return 0.0

def _execute_bybit_buy(symbol: str, price: float, usdt_amount: float) -> bool:
    """تنفيذ أمر شراء فوري على Bybit"""
    if DRY_RUN:
        logger.warning(f"[Bybit DRY RUN] شراء {symbol} بـ ${usdt_amount:.2f} @ ${price:.6f}")
        return True
    try:
        import json as _json
        ts = str(int(time.time() * 1000))
        rw = '5000'
        sym = symbol.replace('/', '').replace('-', '')
        body = {
            'category': 'spot',
            'symbol': sym,
            'side': 'Buy',
            'orderType': 'Market',
            'qty': str(round(usdt_amount, 2)),
            'marketUnit': 'quoteCoin'  # qty بالـ USDT
        }
        body_str = _json.dumps(body, separators=(',', ':'))
        ps = f'{ts}{BYBIT_API_KEY}{rw}{body_str}'
        headers = _bybit_auth_headers(ps, ts)
        r = _bybit_session.post(
            f'{BYBIT_BASE_URL}/v5/order/create',
            data=body_str,
            headers=headers,
            timeout=10
        )
        data = r.json()
        if data.get('retCode') == 0:
            order_id = data.get('result', {}).get('orderId', '')
            logger.info(f"[Bybit] ✅ تم الشراء: {symbol} | ${usdt_amount:.2f} @ ${price:.6f} | OrderID: {order_id}")
            return True
        else:
            logger.error(f"[Bybit] ❌ فشل الشراء: {data.get('retMsg')}")
    except Exception as e:
        logger.error(f"[Bybit] ❌ خطأ: {e}")
    return False

# ─── رسالة التنبيه ────────────────────────────────────────
def _build_alert_msg(exchange: str, symbol: str, price: float, usdt_amount: float, success: bool) -> str:
    coin = symbol.replace('/USDT', '')
    now  = time.strftime('%H:%M:%S')
    date = time.strftime('%Y-%m-%d')
    status = "✅ تم الشراء بنجاح" if success else "❌ فشل تنفيذ الأمر"
    exchange_emoji = "🟡" if exchange == "OKX" else "🟠"
    return (
        f"🚨 <b>Flash Crash Sniper — خلل تقني رُصد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{exchange_emoji} <b>المنصة: {exchange}</b>\n"
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
    logger.info("🚀 Flash Crash Sniper v2 يعمل — يراقب: " + ", ".join(WATCH_SYMBOLS))
    logger.info(f"   الحد: ${CRASH_THRESHOLD} | الفحص كل {POLL_INTERVAL}s | المنصات: OKX + Bybit")
    _load_state()

    # ─── تهيئة OKX ────────────────────────────────────────
    okx_client = _build_okx_client()
    try:
        okx_client.load_markets()
        logger.info("✅ [OKX] تم الاتصال بنجاح")
    except Exception as e:
        logger.critical(f"❌ [OKX] فشل الاتصال: {e}")
        sys.exit(1)

    # ─── اختبار Bybit ─────────────────────────────────────
    bybit_enabled = False
    try:
        r = _bybit_session.get(f'{BYBIT_BASE_URL}/v5/market/time', timeout=5)
        if r.status_code == 200 and r.json().get('retCode') == 0:
            bybit_bal = _get_bybit_balance()
            logger.info(f"✅ [Bybit] متصل — رصيد USDT: ${bybit_bal:.2f}")
            bybit_enabled = bybit_bal >= 1.0
            if not bybit_enabled:
                logger.warning("[Bybit] رصيد غير كافٍ للتداول (< $1)")
        else:
            logger.warning("[Bybit] فشل اختبار الاتصال")
    except Exception as e:
        logger.warning(f"[Bybit] خطأ في الاتصال: {e}")

    logger.info(f"[Bybit] يراقب {len(BYBIT_ONLY_SYMBOLS)} عملة حصرية على Bybit")

    consecutive_errors = {s: 0 for s in WATCH_SYMBOLS}

    while True:
        for symbol in WATCH_SYMBOLS:
            try:
                # ─── مراقبة OKX ───────────────────────────
                okx_price = _get_okx_price(okx_client, symbol)
                if okx_price < 0:
                    consecutive_errors[symbol] += 1
                    if consecutive_errors[symbol] >= 10:
                        logger.warning(f"⚠️ [OKX] {symbol}: 10 أخطاء متتالية")
                        consecutive_errors[symbol] = 0
                else:
                    consecutive_errors[symbol] = 0
                    if 0 < okx_price < CRASH_THRESHOLD:
                        logger.warning(f"🚨 [OKX] خلل تقني! {symbol} = ${okx_price:.6f}")
                        cooldown_key = f"okx_{symbol}"
                        if _can_buy(cooldown_key):
                            usdt_balance = _get_okx_balance(okx_client)
                            if usdt_balance >= 1.0:
                                success = _execute_okx_buy(okx_client, symbol, okx_price, usdt_balance)
                                msg = _build_alert_msg("OKX", symbol, okx_price, usdt_balance, success)
                                _notify_all(msg)
                                if success:
                                    _mark_bought(cooldown_key)
                            else:
                                logger.warning(f"[OKX] رصيد غير كافٍ: ${usdt_balance:.2f}")
                                _notify_all(
                                    f"⚠️ <b>Flash Crash Sniper</b>\n"
                                    f"[OKX] رُصد خلل في {symbol} (${okx_price:.6f}) لكن الرصيد غير كافٍ: ${usdt_balance:.2f}"
                                )
                        else:
                            logger.info(f"[OKX] {symbol}: cooldown نشط")

                # ─── مراقبة Bybit (العملات المشتركة) ──────────
                if bybit_enabled:
                    bybit_price = _get_bybit_price(symbol)
                    if bybit_price > 0 and 0 < bybit_price < CRASH_THRESHOLD:
                        logger.warning(f"🚨 [Bybit] خلل تقني! {symbol} = ${bybit_price:.6f}")
                        cooldown_key = f"bybit_{symbol}"
                        if _can_buy(cooldown_key):
                            bybit_usdt = _get_bybit_balance()
                            if bybit_usdt >= 1.0:
                                success = _execute_bybit_buy(symbol, bybit_price, bybit_usdt)
                                msg = _build_alert_msg("Bybit", symbol, bybit_price, bybit_usdt, success)
                                _notify_all(msg)
                                if success:
                                    _mark_bought(cooldown_key)
                                    bybit_enabled = _get_bybit_balance() >= 1.0
                            else:
                                logger.warning(f"[Bybit] رصيد غير كافٍ: ${bybit_usdt:.2f}")
                                bybit_enabled = False
                        else:
                            logger.info(f"[Bybit] {symbol}: cooldown نشط")

            except Exception as e:
                logger.error(f"خطأ في مراقبة {symbol}: {e}")

        time.sleep(POLL_INTERVAL)

        # ─── مراقبة العملات الحصرية على Bybit ────────────────
        if bybit_enabled:
            for bybit_sym in BYBIT_ONLY_SYMBOLS:
                try:
                    bybit_price = _get_bybit_price(bybit_sym)
                    if bybit_price > 0 and 0 < bybit_price < CRASH_THRESHOLD:
                        logger.warning(f"🚨 [Bybit Exclusive] خلل تقني! {bybit_sym}/USDT = ${bybit_price:.6f}")
                        cooldown_key = f"bybit_excl_{bybit_sym}"
                        if _can_buy(cooldown_key):
                            bybit_usdt = _get_bybit_balance()
                            if bybit_usdt >= 1.0:
                                success = _execute_bybit_buy(f"{bybit_sym}/USDT", bybit_price, bybit_usdt)
                                msg = _build_alert_msg("Bybit", f"{bybit_sym}/USDT", bybit_price, bybit_usdt, success)
                                _notify_all(msg)
                                if success:
                                    _mark_bought(cooldown_key)
                                    bybit_enabled = _get_bybit_balance() >= 1.0
                            else:
                                bybit_enabled = False
                        else:
                            logger.info(f"[Bybit Exclusive] {bybit_sym}: cooldown نشط")
                except Exception as e:
                    logger.debug(f"[Bybit Exclusive] خطأ {bybit_sym}: {e}")

if __name__ == '__main__':
    run()
