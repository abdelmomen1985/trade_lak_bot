#!/usr/bin/env python3
"""
Watchlist Monitor — يراقب عملات محددة ويُرسل تنبيهاً عند توفر فرصة دخول قوية
العملات: XRP, INJ, WLD, ARB, PARTI
"""
import sys, time, requests, numpy as np, logging, json, os
sys.path.insert(0, '/root/trade_lak_bot')
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_PRIVATE_CHAT, TELEGRAM_SIGNAL_CHAT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Watchlist] %(message)s',
    handlers=[
        logging.FileHandler('/root/trade_lak_bot/logs/watchlist_monitor.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# مسار ملف الإشارات النشطة (market_scanner)
SIGNAL_ACTIVE_FILE  = '/root/trade_lak_bot/data/signal_channel_active.json'
SL_HIT_MEMORY_FILE  = '/root/trade_lak_bot/data/sl_hit_memory.json'
SL_HIT_MEMORY_HOURS = 48

def get_active_signal_symbols():
    """جلب قائمة العملات التي لها إشارات مفتوحة في قناة Signal"""
    try:
        if os.path.exists(SIGNAL_ACTIVE_FILE):
            with open(SIGNAL_ACTIVE_FILE) as f:
                active = json.load(f)
            # استخراج الرموز بدون /USDT
            return set(k.replace('/USDT', '').upper() for k in active.keys())
    except Exception as e:
        log.error(f'خطأ في قراءة signal_channel_active: {e}')
    return set()

def get_reentry_info(symbol: str):
    """فحص إذا كانت العملة ضربت SL مؤخراً (للتنويه بإعادة الدخول)"""
    try:
        if os.path.exists(SL_HIT_MEMORY_FILE):
            import json as _json
            with open(SL_HIT_MEMORY_FILE) as f:
                memory = _json.load(f)
            key = f"{symbol}/USDT"
            if key in memory:
                hours = (time.time() - memory[key].get("time", 0)) / 3600
                return {"hours_since": hours}
    except Exception:
        pass
    return None

# العملات المراقبة مع شروط الدخول الخاصة بكل منها
WATCHLIST = {
    'XRP': {
        'symbol': 'XRP-USDT',
        'min_score': 6,
        'rsi4h_entry': 30,   # RSI 4H يجب أن يكون < هذه القيمة
        'note': 'RSI 4H كان 29.3 — قريب جداً من ذروة البيع'
    },
    'INJ': {
        'symbol': 'INJ-USDT',
        'min_score': 6,
        'rsi4h_entry': 28,
        'note': 'RSI 4H كان 24.7 — ذروة بيع قوية'
    },
    'WLD': {
        'symbol': 'WLD-USDT',
        'min_score': 6,
        'rsi4h_entry': 28,
        'note': 'RSI 4H كان 24.2 — ذروة بيع لكن OI هابط'
    },
    'ARB': {
        'symbol': 'ARB-USDT',
        'min_score': 6,
        'rsi4h_entry': 30,
        'note': 'RSI 4H كان 29.6 — ينتظر تأكيد'
    },
    'PARTI': {
        'symbol': 'PARTI-USDT',
        'min_score': 6,
        'rsi4h_entry': 30,
        'note': 'عملة جديدة — ينتظر RSI < 30 مع BB السفلي'
    },
    'NIGHT': {
        'symbol': 'NIGHT-USDT',
        'min_score': 6,
        'rsi4h_entry': 35,
        'note': 'RSI 4H=46 حالياً — ننتظر هبوطه للمنطقة 28-32'
    },
    "NEAR": {
        "symbol": "NEAR-USDT",
        "min_score": 6,
        "rsi4h_entry": 28,
        "note": "RSI 4H=24.4 ذروة بيع شديدة — فرصة قوية"
    },
    "ZBCN": {
        "symbol": "ZBCN-USDT",
        "min_score": 6,
        "rsi4h_entry": 35,
        "note": "مراقبة — RSI 4H=52 حالياً"
    },
    "BERA": {
        "symbol": "BERA-USDT",
        "min_score": 6,
        "rsi4h_entry": 35,
        "note": "RSI 4H=46 — ارتفع +4.4% اليوم، ننتظر تصحيحاً"
    },
    "SEI": {
        "symbol": "SEI-USDT",
        "min_score": 6,
        "rsi4h_entry": 30,
        "note": "RSI4H=21.5 + RSI1H=15.1 ذروة بيع شديدة جداً"
    },
    "AXS": {
        "symbol": "AXS-USDT",
        "min_score": 6,
        "rsi4h_entry": 32,
        "note": "RSI4H=28.8 عند BB Lower — فرصة قوية"
    },
    "ALGO": {
        "symbol": "ALGO-USDT",
        "min_score": 6,
        "rsi4h_entry": 35,
        "note": "SuperTrend 0.08528 — دعم قوي عند 0.08520"
    },
    "SUSHI": {
        "symbol": "SUSHI-USDT",
        "min_score": 6,
        "rsi4h_entry": 48,
        "note": "RSI 4H=48.6 محايد — ننتظر تصحيحاً لـ 0.148-0.150 مع R/R ≥ 1.5"
    },
    "PI": {
        "symbol": "PI-USDT",
        "min_score": 6,
        "rsi4h_entry": 35,
        "note": "RSI 4H=31.9 قريب من ذروة البيع — ننتظر تأكيد حجم وارتداد"
    },
    "PYTH": {
        "symbol": "PYTH-USDT",
        "min_score": 6,
        "rsi4h_entry": 55,
        "note": "RSI 4H=69 قرب ذروة شراء — ننتظر تصحيحاً لـ RSI < 55 مع دعم 0.034-0.035"
    },
    "BASED": {
        "symbol": "BASED-USDT",
        "min_score": 6,
        "rsi4h_entry": 55,
        "note": "ارتفع +29% — ننتظر تصحيحاً لـ RSI 4H < 55 وعودة السعر لـ EMA20 (~0.102)"
    },
    "BREV": {
        "symbol": "BREV-USDT",
        "min_score": 6,
        "rsi4h_entry": 35,
        "note": "عملة جديدة — RSI 4H=34.5 قريب من ذروة البيع، ننتظر تراجع السعر لـ EMA20 (0.0695) مع RSI 4H < 35"
    },
    "VIRTUAL": {
        "symbol": "VIRTUAL-USDT",
        "min_score": 5,
        "rsi4h_entry": 55,
        "note": "RSI 4H=66 تشبع شراء — ننتظر تصحيحاً لـ RSI 4H < 55 مع عودة السعر لمنطقة BB Mid (0.53-0.55)"
    },
    "AAVE": {
        "symbol": "AAVE-USDT",
        "min_score": 5,
        "rsi4h_entry": 45,
        "note": "RSI 4H=52 محايد، MACD+ — ننتظر تصحيحاً لـ RSI 4H < 45 مع عودة السعر لمنطقة BB Mid أو دونها (84-86)"
    },
    "RENDER": {
        "symbol": "RENDER-USDT",
        "min_score": 5,
        "rsi4h_entry": 50,
        "note": "RSI 4H=64 قرب BB Upper — ننتظر تصحيحاً لـ RSI 4H < 50 مع عودة السعر لمنطقة BB Mid (1.55-1.57)"
    },
}
# تتبع آخر تنبيه لكل عملة (لتجنب التكرار)
last_alert = {}
ALERT_COOLDOWN = 14400  # 4 ساعات بين كل تنبيهين لنفس العملة (موحَّد مع market_scanner)

def send_telegram(msg, chat_id=None):
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID
    """إرسال رسالة Telegram"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        r = requests.post(url, json={
            'chat_id': chat_id,
            'text': msg,
            'parse_mode': 'HTML'
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.error(f'خطأ في Telegram: {e}')
        return False

def get_ohlcv(symbol, bar='4H', limit=50):
    """جلب بيانات OHLCV"""
    try:
        r = requests.get(
            f'https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={bar}&limit={limit}',
            timeout=10
        )
        data = r.json()
        if data.get('code') == '0' and data.get('data'):
            return [float(c[4]) for c in reversed(data['data'])]
    except Exception as e:
        log.error(f'خطأ في جلب OHLCV {symbol}: {e}')
    return []

def get_ticker(symbol):
    """جلب السعر الحالي"""
    try:
        r = requests.get(
            f'https://www.okx.com/api/v5/market/ticker?instId={symbol}',
            timeout=10
        )
        data = r.json()
        if data.get('code') == '0' and data.get('data'):
            t = data['data'][0]
            return {
                'price': float(t['last']),
                'high24': float(t['high24h']),
                'low24': float(t['low24h']),
                'vol24': float(t['vol24h']),
                'change_pct': (float(t['last']) - float(t['sodUtc8'])) / float(t['sodUtc8']) * 100 if float(t.get('sodUtc8', 0)) > 0 else 0
            }
    except Exception as e:
        log.error(f'خطأ في جلب ticker {symbol}: {e}')
    return None

def calc_rsi(closes, period=14):
    """حساب RSI"""
    if len(closes) < period + 1:
        return 50
    closes = np.array(closes, dtype=float)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(closes, fast=12, slow=26, signal=9):
    """حساب MACD"""
    if len(closes) < slow + signal:
        return 0, 0, 0
    closes = np.array(closes, dtype=float)
    def ema(data, period):
        k = 2 / (period + 1)
        result = [data[0]]
        for v in data[1:]:
            result.append(v * k + result[-1] * (1 - k))
        return np.array(result)
    macd_line = ema(closes, fast) - ema(closes, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line[-1], signal_line[-1], histogram[-1]

def calc_bb(closes, period=20):
    """حساب Bollinger Bands"""
    if len(closes) < period:
        return None, None, None
    recent = np.array(closes[-period:], dtype=float)
    mid = np.mean(recent)
    std = np.std(recent)
    return mid - 2 * std, mid, mid + 2 * std

def analyze_coin(name, config):
    """تحليل عملة واحدة وإرجاع Score والأسباب"""
    symbol = config['symbol']
    ticker = get_ticker(symbol)
    if not ticker:
        return None

    closes_4h = get_ohlcv(symbol, '4H', 50)
    closes_1h = get_ohlcv(symbol, '1H', 50)

    if len(closes_4h) < 20 or len(closes_1h) < 14:
        return None

    price = ticker['price']
    rsi_4h = calc_rsi(closes_4h)
    rsi_1h = calc_rsi(closes_1h)
    macd_val, macd_sig, macd_hist = calc_macd(closes_4h)
    bb_lower, bb_mid, bb_upper = calc_bb(closes_4h)

    score = 0
    reasons = []

    # RSI 1H منخفض
    if rsi_1h < 35:
        score += 1
        reasons.append(f'RSI 1H={rsi_1h:.1f} (منخفض)')

    # RSI 4H منخفض
    if rsi_4h < 35:
        score += 2
        reasons.append(f'RSI 4H={rsi_4h:.1f} (منخفض)')

    # RSI 4H ذروة بيع
    if rsi_4h < 25:
        score += 1
        reasons.append(f'RSI 4H={rsi_4h:.1f} (ذروة بيع!)')

    # MACD يتحسن (histogram يتحول للأعلى)
    if macd_hist > 0 or (len(closes_4h) > 2 and macd_hist > -0.000001):
        score += 1
        reasons.append('MACD يتحسن')

    # قريب من BB السفلي
    if bb_lower and price <= bb_lower * 1.03:
        score += 2
        reasons.append(f'قريب من BB السفلي (${bb_lower:.5f})')

    # Volume مرتفع
    vol_avg = ticker['vol24'] / 24
    if vol_avg > 0:
        score += 1
        reasons.append('Volume مرتفع')

    # --- منطق التجميع ---
    acc_score = 0
    acc_reasons = []
    # RSI 4H في منطقة التجميع (35-50) — ليس ذروة بيع لكن يتراجع
    if 35 <= rsi_4h <= 50:
        acc_score += 2
        acc_reasons.append(f'RSI 4H={rsi_4h:.1f} (منطقة تجميع)')
    elif 30 <= rsi_4h < 35:
        acc_score += 3
        acc_reasons.append(f'RSI 4H={rsi_4h:.1f} (تجميع قوي)')
    # RSI 1H في منطقة التجميع
    if 35 <= rsi_1h <= 50:
        acc_score += 1
        acc_reasons.append(f'RSI 1H={rsi_1h:.1f} (منطقة تجميع)')
    # السعر بين BB Mid وBB Lower
    if bb_lower and bb_mid:
        if bb_lower <= price <= bb_mid:
            acc_score += 2
            acc_reasons.append('السعر بين BB Lower وBB Mid (منطقة تجميع)')
    # MACD Histogram يتحسن (أقل سلبية)
    if macd_hist > -0.0001:
        acc_score += 1
        acc_reasons.append('MACD يتعافى')
    # تغيير 24H سلبي طفيف (ضغط بيع خفيف = تجميع)
    if -5 <= ticker['change_pct'] <= -1:
        acc_score += 1
        acc_reasons.append(f'تراجع طفيف {ticker["change_pct"]:.1f}% (تجميع)')

    return {
        'name': name,
        'symbol': symbol,
        'price': price,
        'change_pct': ticker['change_pct'],
        'rsi_1h': rsi_1h,
        'rsi_4h': rsi_4h,
        'macd_hist': macd_hist,
        'bb_lower': bb_lower,
        'bb_mid': bb_mid,
        'score': score,
        'reasons': reasons,
        'acc_score': acc_score,
        'acc_reasons': acc_reasons,
        'min_score': config['min_score'],
        'note': config['note']
    }

def fp_price(v):
    if v < 0.001:
        s = '%.8f' % v
        return s.rstrip('0')
    if v < 1:
        s = '%.6f' % v
        return s.rstrip('0')
    if v < 1000:
        return '%.4f' % v
    return '%,.2f' % v


def check_and_alert(result):
    name = result['name']
    score = result['score']
    min_score = result['min_score']
    price = result['price']
    if score < min_score:
        return False
    active_signals = get_active_signal_symbols()
    if name in active_signals:
        log.info('skip %s - open signal' % name)
        return False
    now = time.time()
    if name in last_alert and (now - last_alert[name]) < ALERT_COOLDOWN:
        return False
    last_alert[name] = now
    tp1 = round(price * 1.03, 8)
    tp2 = round(price * 1.06, 8)
    tp3 = round(price * 1.08, 8)
    sl  = round(price * 0.975, 8)
    rr = (tp1 - price) / (price - sl) if (price - sl) > 0 else 0
    if rr < 1.5:
        log.info('skip %s: R/R=%.2f' % (name, rr))
        return False
    reentry = get_reentry_info(name)
    stars = chr(0x2B50) * min(score // 2, 5)
    sep = chr(0x2500) * 30
    if reentry:
        h = int(reentry['hours_since'])
        rb = chr(0x1F504) + ' <b>' + chr(0x625) + chr(0x639) + chr(0x627) + chr(0x62F) + chr(0x629) + ' ' + chr(0x62F) + chr(0x62E) + chr(0x648) + chr(0x644) + '</b> - SL ' + chr(0x636) + chr(0x64F) + chr(0x631) + chr(0x628) + ' ' + chr(0x645) + chr(0x646) + chr(0x630) + ' %d ' % h + chr(0x633) + chr(0x627) + chr(0x639) + chr(0x629) + chr(0xA)
        rb += chr(0x26A0) + chr(0xFE0F) + ' ' + chr(0x647) + chr(0x630) + chr(0x647) + ' ' + chr(0x635) + chr(0x641) + chr(0x642) + chr(0x629) + ' ' + chr(0x645) + chr(0x633) + chr(0x62A) + chr(0x642) + chr(0x644) + chr(0x629) + ' ' + chr(0x62C) + chr(0x62F) + chr(0x64A) + chr(0x62F) + chr(0x629) + chr(0xA)
        rb += sep + chr(0xA)
        title = chr(0x1F504) + ' <b>' + chr(0x625) + chr(0x639) + chr(0x627) + chr(0x62F) + chr(0x629) + ' ' + chr(0x62F) + chr(0x62E) + chr(0x648) + chr(0x644) + ' | ' + name + '/USDT</b>'
    else:
        rb = ''
        title = chr(0x1F4E1) + ' <b>' + chr(0x625) + chr(0x634) + chr(0x627) + chr(0x631) + chr(0x629) + ' ' + chr(0x62F) + chr(0x62E) + chr(0x648) + chr(0x644) + ' | ' + name + '/USDT</b>'
    from datetime import datetime
    lines = [
        title, sep, rb, '',
        chr(0x1F4B0) + ' <b>' + chr(0x627) + chr(0x644) + chr(0x633) + chr(0x639) + chr(0x631) + ' ' + chr(0x627) + chr(0x644) + chr(0x62D) + chr(0x627) + chr(0x644) + chr(0x64A) + ':</b>  ' + fp_price(price), '',
        chr(0x1F4E5) + ' <b>' + chr(0x646) + chr(0x642) + chr(0x637) + chr(0x629) + ' ' + chr(0x627) + chr(0x644) + chr(0x62F) + chr(0x62E) + chr(0x648) + chr(0x644) + ':</b>  ' + fp_price(price), '',
        chr(0x1F5C7) + ' <b>' + chr(0x627) + chr(0x644) + chr(0x647) + chr(0x62F) + chr(0x641) + ' ' + chr(0x627) + chr(0x644) + chr(0x623) + chr(0x648) + chr(0x644) + ':</b>   ' + fp_price(tp1) + ' <b>(+3.0%)</b>',
        chr(0x1F5C7) + ' <b>' + chr(0x627) + chr(0x644) + chr(0x647) + chr(0x62F) + chr(0x641) + ' ' + chr(0x627) + chr(0x644) + chr(0x62B) + chr(0x627) + chr(0x646) + chr(0x64A) + ':</b>  ' + fp_price(tp2) + ' <b>(+6.0%)</b>',
        chr(0x1F5C7) + ' <b>' + chr(0x627) + chr(0x644) + chr(0x647) + chr(0x62F) + chr(0x641) + ' ' + chr(0x627) + chr(0x644) + chr(0x62B) + chr(0x627) + chr(0x644) + chr(0x62B) + ':</b>  ' + fp_price(tp3) + ' <b>(+8.0%)</b>',
        '',
        chr(0x1F534) + ' <b>' + chr(0x648) + chr(0x642) + chr(0x641) + ' ' + chr(0x627) + chr(0x644) + chr(0x62E) + chr(0x633) + chr(0x627) + chr(0x631) + chr(0x629) + ':</b>  ' + fp_price(sl) + ' <b>(-2.5%)</b>',
        chr(0x2696) + chr(0xFE0F) + ' <b>' + chr(0x646) + chr(0x633) + chr(0x628) + chr(0x629) + ' ' + chr(0x627) + chr(0x644) + chr(0x645) + chr(0x62E) + chr(0x627) + chr(0x637) + chr(0x631) + chr(0x629) + ':</b>  %.1f:1' % rr,
        '', sep,
        stars + ' <b>' + chr(0x642) + chr(0x648) + chr(0x629) + ' ' + chr(0x627) + chr(0x644) + chr(0x625) + chr(0x634) + chr(0x627) + chr(0x631) + chr(0x629) + ' (%d/10)</b>' % score,
        '',
        chr(0x1F4CA) + ' RSI 4H: <b>%.0f</b>  |  RSI 1H: <b>%.0f</b>' % (result['rsi_4h'], result['rsi_1h']),
        '', sep,
        chr(0x26A0) + chr(0xFE0F) + ' ' + chr(0x647) + chr(0x630) + chr(0x647) + ' ' + chr(0x627) + chr(0x644) + chr(0x625) + chr(0x634) + chr(0x627) + chr(0x631) + chr(0x629) + ' ' + chr(0x644) + chr(0x623) + chr(0x647) + chr(0x62F) + chr(0x627) + chr(0x641) + ' ' + chr(0x62A) + chr(0x639) + chr(0x644) + chr(0x64A) + chr(0x645) + chr(0x64A) + chr(0x629),
        chr(0x648) + chr(0x644) + chr(0x64A) + chr(0x633) + chr(0x62A) + ' ' + chr(0x646) + chr(0x635) + chr(0x64A) + chr(0x62D) + chr(0x629) + ' ' + chr(0x627) + chr(0x633) + chr(0x62A) + chr(0x62B) + chr(0x645) + chr(0x627) + chr(0x631) + chr(0x64A) + chr(0x629),
        sep,
        chr(0x1F550) + ' ' + datetime.now().strftime('%H:%M  |  %Y/%m/%d'),
    ]
    msg = chr(0xA).join(lines)
    sent = send_telegram(msg, chat_id=TELEGRAM_SIGNAL_CHAT)
    if sent:
        log.info('signal sent: %s score=%d' % (name, score))
        try:
            try:
                with open(SIGNAL_ACTIVE_FILE) as f:
                    active = json.load(f)
            except Exception:
                active = {}
            active[name + '/USDT'] = {'entry': price, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl, 'sector': 'Watchlist', 'sent_at': int(now)}
            with open(SIGNAL_ACTIVE_FILE, 'w') as f:
                json.dump(active, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error('save error: %s' % e)
    return sent

def main():
    log.info('🚀 Watchlist Monitor بدأ العمل')
    log.info(f'العملات المراقبة: {", ".join(WATCHLIST.keys())}')

    # إرسال رسالة بدء
    send_telegram(
        '👁️ <b>Watchlist Monitor — بدأ العمل</b>\n'
        '━━━━━━━━━━━━━━━━━━\n'
        f'العملات المراقبة:\n'
        + '\n'.join([f'• {k} — {v["note"]}' for k, v in WATCHLIST.items()])
        + '\n━━━━━━━━━━━━━━━━━━\n'
        'سيُرسل تنبيه فوري عند Score ≥ 6\n'
        '⚠️ لن يُرسل تنبيه إذا كانت العملة لها إشارة مفتوحة في Signal'
    )

    CHECK_INTERVAL = 300  # كل 5 دقائق

    while True:
        try:
            log.info(f'--- فحص دوري ({len(WATCHLIST)} عملة) ---')
            alerts_sent = 0

            # جلب الإشارات المفتوحة مرة واحدة لكل دورة
            active_signals = get_active_signal_symbols()
            if active_signals:
                log.info(f'⚠️ إشارات مفتوحة في Signal (مُستثناة): {", ".join(sorted(active_signals))}')

            for name, config in WATCHLIST.items():
                try:
                    result = analyze_coin(name, config)
                    if result:
                        log.info(f'{name}: Score={result["score"]}/10 | RSI4H={result["rsi_4h"]:.1f} | Price=${result["price"]:.5f}')
                        if check_and_alert(result):
                            alerts_sent += 1
                    time.sleep(1)  # تجنب rate limiting
                except Exception as e:
                    log.error(f'خطأ في تحليل {name}: {e}')

            if alerts_sent == 0:
                log.info('لا توجد فرص حالياً — الانتظار 5 دقائق')

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            log.info('إيقاف Watchlist Monitor')
            break
        except Exception as e:
            log.error(f'خطأ عام: {e}')
            time.sleep(60)

if __name__ == '__main__':
    main()
