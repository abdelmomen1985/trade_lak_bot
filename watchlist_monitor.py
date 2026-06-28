#!/usr/bin/env python3
"""
Watchlist Monitor — يراقب عملات محددة ويُرسل تنبيهاً عند توفر فرصة دخول قوية
العملات: XRP, INJ, WLD, ARB, PARTI
"""
import sys, time, requests, numpy as np, logging
sys.path.insert(0, '/root/trade_lak_bot')
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_PRIVATE_CHAT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Watchlist] %(message)s',
    handlers=[
        logging.FileHandler('/root/trade_lak_bot/logs/watchlist_monitor.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

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
    "TRX": {
        "symbol": "TRX-USDT",
        "min_score": 6,
        "rsi4h_entry": 30,
        "note": "RSI 4H=28.3 ذروة بيع + قرب BB Lower"
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
        "min_score": 5,
        "rsi4h_entry": 30,
        "note": "RSI4H=21.5 + RSI1H=15.1 ذروة بيع شديدة جداً"
    },
    "AXS": {
        "symbol": "AXS-USDT",
        "min_score": 5,
        "rsi4h_entry": 32,
        "note": "RSI4H=28.8 عند BB Lower — فرصة قوية"
    },
    "ALGO": {
        "symbol": "ALGO-USDT",
        "min_score": 5,
        "rsi4h_entry": 35,
        "note": "SuperTrend 0.08528 — دعم قوي عند 0.08520"
    },
}
# تتبع آخر تنبيه لكل عملة (لتجنب التكرار)
last_alert = {}
ALERT_COOLDOWN = 3600  # ساعة بين كل تنبيهين لنفس العملة

def send_telegram(msg):
    """إرسال رسالة Telegram"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        r = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
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

def check_and_alert(result):
    """إرسال تنبيه إذا توفرت الشروط"""
    name = result['name']
    score = result['score']
    min_score = result['min_score']

    if score < min_score:
        return False

    # تحقق من Cooldown
    now = time.time()
    if name in last_alert and (now - last_alert[name]) < ALERT_COOLDOWN:
        return False

    last_alert[name] = now

    # بناء الرسالة
    emoji = '🟢' if score >= 8 else '🟡'
    msg = f"""{emoji} <b>فرصة دخول — {name}/USDT</b>
━━━━━━━━━━━━━━━━━━
💰 السعر: ${result['price']:.5f} ({result['change_pct']:+.2f}%)
📊 Score: {score}/10
━━━━━━━━━━━━━━━━━━
📈 RSI 1H: {result['rsi_1h']:.1f}
📈 RSI 4H: {result['rsi_4h']:.1f}
📉 MACD: {'يتحسن ✅' if result['macd_hist'] > 0 else 'هابط ⚠️'}
"""
    if result['bb_lower']:
        msg += f"📉 BB Lower: ${result['bb_lower']:.5f}\n"

    msg += f"""━━━━━━━━━━━━━━━━━━
✅ الأسباب: {' | '.join(result['reasons'])}
━━━━━━━━━━━━━━━━━━
⚠️ للمراجعة والموافقة قبل الدخول"""

    sent = send_telegram(msg)
    if sent:
        log.info(f'✅ تنبيه أُرسل: {name} Score={score}')
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
        'سيُرسل تنبيه فوري عند Score ≥ 6'
    )

    CHECK_INTERVAL = 300  # كل 5 دقائق

    while True:
        try:
            log.info(f'--- فحص دوري ({len(WATCHLIST)} عملة) ---')
            alerts_sent = 0

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
