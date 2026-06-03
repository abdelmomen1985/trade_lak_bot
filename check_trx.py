import sys
sys.path.insert(0, '/root/trade_lak_bot')
import ccxt
from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE
from datetime import datetime

exchange = ccxt.okx({
    'apiKey': OKX_API_KEY,
    'secret': OKX_SECRET_KEY,
    'password': OKX_PASSPHRASE,
})

# جلب آخر صفقات TRX
try:
    trades = exchange.fetch_my_trades('TRX/USDT', limit=10)
    print('=== آخر صفقات TRX/USDT على OKX ===')
    for t in trades:
        dt = datetime.fromtimestamp(t['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')
        side = t['side'].upper()
        amount = t['amount']
        price = t['price']
        cost = t['cost']
        print(f"  {dt} | {side} | {amount:.2f} TRX @ ${price:.6f} | قيمة: ${cost:.2f}")
except Exception as e:
    print(f'خطأ في جلب الصفقات: {e}')

# جلب السعر الحالي وتحليل الاتجاه
try:
    ticker = exchange.fetch_ticker('TRX/USDT')
    current = ticker['last']
    high_24h = ticker['high']
    low_24h = ticker['low']
    change_24h = ticker.get('percentage', 0) or 0

    print()
    print('=== TRX/USDT الآن ===')
    print(f'  السعر الحالي: ${current:.6f}')
    print(f'  أعلى 24h: ${high_24h:.6f}')
    print(f'  أدنى 24h: ${low_24h:.6f}')
    print(f'  تغيير 24h: {change_24h:+.2f}%')

    # حساب الأهداف
    entry_est = current  # سنحدثه بعد رؤية سجل الشراء
    tp1 = current * 1.03
    tp2 = current * 1.06
    tp3 = current * 1.09
    sl  = current * 0.95

    print()
    print('=== تقدير الأهداف (بناءً على السعر الحالي) ===')
    print(f'  TP1 (+3%): ${tp1:.6f}')
    print(f'  TP2 (+6%): ${tp2:.6f}')
    print(f'  TP3 (+9%): ${tp3:.6f}')
    print(f'  SL  (-5%): ${sl:.6f}')

    # جلب بيانات الشموع لتحليل الاتجاه
    ohlcv = exchange.fetch_ohlcv('TRX/USDT', '1h', limit=24)
    if ohlcv:
        closes = [c[4] for c in ohlcv]
        avg_24h = sum(closes) / len(closes)
        trend = "صاعد" if closes[-1] > closes[-6] else "هابط"
        momentum = ((closes[-1] - closes[-6]) / closes[-6]) * 100
        print()
        print('=== تحليل الاتجاه (24 ساعة) ===')
        print(f'  متوسط 24h: ${avg_24h:.6f}')
        print(f'  الاتجاه: {trend}')
        print(f'  زخم 6h: {momentum:+.2f}%')

        # تقدير وقت الوصول للهدف
        if momentum > 0:
            rate_per_hour = momentum / 6
            hours_to_tp1 = (3.0 - ((current - entry_est) / entry_est * 100)) / rate_per_hour if rate_per_hour > 0 else 999
            print(f'  معدل الصعود: {rate_per_hour:+.3f}%/ساعة')
            if hours_to_tp1 > 0 and hours_to_tp1 < 200:
                print(f'  تقدير الوصول لـ TP1: ~{hours_to_tp1:.0f} ساعة')
            else:
                print(f'  تقدير الوصول لـ TP1: غير محدد (الاتجاه ضعيف)')
        else:
            print(f'  الزخم سلبي — قد يحتاج وقتاً أطول للوصول للهدف')

except Exception as e:
    print(f'خطأ في جلب السعر: {e}')
    import traceback
    traceback.print_exc()
