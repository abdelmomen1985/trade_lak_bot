"""
تحليل مؤشرات PEPE وقت الدخول (24 مايو 22:39 و25 مايو 01:53)
لفهم لماذا أخطأ البوت في قراءة التريند
"""
import ccxt, sys
import pandas as pd
import numpy as np
sys.path.insert(0, '/root/trade_lak_bot')
from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE

ex = ccxt.okx({'apiKey': OKX_API_KEY, 'secret': OKX_SECRET_KEY, 'password': OKX_PASSPHRASE})

def calc_ema(closes, period):
    closes = list(closes)
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def calc_rsi(closes, period=14):
    closes = list(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    if len(gains) < period:
        return 50
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyze_at_time(symbol, entry_time_desc, entry_price):
    print(f"\n{'='*60}")
    print(f"تحليل {symbol} — وقت الدخول: {entry_time_desc}")
    print(f"سعر الدخول: ${entry_price:.8f}")
    print('='*60)
    
    # جلب بيانات 1H (آخر 100 شمعة)
    ohlcv_1h = ex.fetch_ohlcv(symbol, '1h', limit=100)
    ohlcv_4h = ex.fetch_ohlcv(symbol, '4h', limit=50)
    ohlcv_15m = ex.fetch_ohlcv(symbol, '15m', limit=50)
    
    closes_1h = [c[4] for c in ohlcv_1h]
    closes_4h = [c[4] for c in ohlcv_4h]
    closes_15m = [c[4] for c in ohlcv_15m]
    volumes_1h = [c[5] for c in ohlcv_1h]
    
    # EMA على 1H
    ema20_1h = calc_ema(closes_1h[-20:], 20)
    ema50_1h = calc_ema(closes_1h[-50:], 50)
    ema200_1h = calc_ema(closes_1h, 200) if len(closes_1h) >= 200 else calc_ema(closes_1h, len(closes_1h))
    
    # EMA على 4H
    ema20_4h = calc_ema(closes_4h[-20:], 20)
    ema50_4h = calc_ema(closes_4h, 50) if len(closes_4h) >= 50 else calc_ema(closes_4h, len(closes_4h))
    
    # RSI
    rsi_1h = calc_rsi(closes_1h)
    rsi_4h = calc_rsi(closes_4h)
    rsi_15m = calc_rsi(closes_15m)
    
    # هيكل السوق (Higher Highs / Lower Lows)
    highs = [c[2] for c in ohlcv_1h[-20:]]
    lows = [c[3] for c in ohlcv_1h[-20:]]
    
    # فحص التريند
    recent_high = max(highs[-5:])
    prev_high = max(highs[-10:-5])
    recent_low = min(lows[-5:])
    prev_low = min(lows[-10:-5])
    
    if recent_high > prev_high and recent_low > prev_low:
        trend = "📈 صاعد (Higher Highs + Higher Lows)"
    elif recent_high < prev_high and recent_low < prev_low:
        trend = "📉 هابط (Lower Highs + Lower Lows)"
    else:
        trend = "↔️ عرضي (Range)"
    
    # Volume trend
    avg_vol = sum(volumes_1h[-20:]) / 20
    last_vol = volumes_1h[-1]
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
    
    # السعر الحالي vs EMA
    current = closes_1h[-1]
    above_ema20 = current > ema20_1h
    above_ema50 = current > ema50_1h
    
    print(f"\n📊 المؤشرات على 1H:")
    print(f"  التريند: {trend}")
    print(f"  السعر الحالي: ${current:.8f}")
    print(f"  EMA20: ${ema20_1h:.8f} | السعر {'فوق' if above_ema20 else 'تحت'} EMA20")
    print(f"  EMA50: ${ema50_1h:.8f} | السعر {'فوق' if above_ema50 else 'تحت'} EMA50")
    print(f"  RSI(14): {rsi_1h:.1f} {'🔴 ذعر بيع' if rsi_1h < 30 else '🟡 محايد' if rsi_1h < 50 else '🟢 قوة شراء'}")
    print(f"  Volume: {vol_ratio:.1f}x المتوسط")
    
    print(f"\n📊 المؤشرات على 4H:")
    print(f"  EMA20: ${ema20_4h:.8f} | السعر {'فوق' if current > ema20_4h else 'تحت'} EMA20")
    print(f"  EMA50: ${ema50_4h:.8f} | السعر {'فوق' if current > ema50_4h else 'تحت'} EMA50")
    print(f"  RSI(14): {rsi_4h:.1f}")
    
    print(f"\n📊 المؤشرات على 15m:")
    print(f"  RSI(14): {rsi_15m:.1f}")
    
    # تقييم قرار الدخول
    print(f"\n🔍 تقييم قرار الدخول:")
    problems = []
    
    if "هابط" in trend:
        problems.append("❌ التريند هابط على 1H — لا يجب الدخول في اتجاه معاكس للتريند")
    if not above_ema20:
        problems.append("❌ السعر تحت EMA20 — ضعف في الزخم")
    if not above_ema50:
        problems.append("❌ السعر تحت EMA50 — تريند هابط متوسط المدى")
    if current < ema20_4h:
        problems.append("❌ السعر تحت EMA20 على 4H — تريند هابط طويل المدى")
    if rsi_1h > 70:
        problems.append("⚠️ RSI فوق 70 — منطقة تشبع شراء")
    if rsi_4h < 40:
        problems.append("⚠️ RSI 4H ضعيف — لا زخم صاعد")
    
    if not problems:
        print("  ✅ المؤشرات كانت إيجابية — الدخول كان منطقياً")
    else:
        for p in problems:
            print(f"  {p}")

# تحليل PEPE
analyze_at_time('PEPE/USDT', '24 مايو 22:39 (الدخول الأول)', 0.000014)
analyze_at_time('PEPE/USDT', '25 مايو 01:53 (الدخول الثاني - LBC)', 0.000014)
