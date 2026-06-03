#!/usr/bin/env python3
"""
سكريبت التدريب الشامل لنماذج ML — Trade Lak Bot
يجمع بيانات من: OKX (OHLCV) + CoinGlass (OI History) + Fear & Greed
ويُدرّب نماذج RF + GB بـ 22 feature مطابقة لـ ml_model.py
"""

import sys
import os
import time
import math
import json
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ── إضافة مسار البوت ─────────────────────────────────────────────
BOT_DIR = Path('/root/trade_lak_bot')
sys.path.insert(0, str(BOT_DIR))

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib

# ── الإعدادات ─────────────────────────────────────────────────────
OKX_BASE = 'https://www.okx.com'
CG_KEY   = 'eaf8efd7876142b0bac70affb6f65f2a'
CG_BASE  = 'https://open-api-v3.coinglass.com'
MODELS_DIR = BOT_DIR / 'models'

SYMBOLS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP',
    'ADA', 'AVAX', 'DOT', 'LINK', 'MATIC',
    'NEAR', 'APT', 'ARB', 'OP', 'INJ',
    'SUI', 'TIA', 'JTO', 'PYTH', 'WIF',
]

CANDLE_LIMIT = 1440   # ~60 يوم بشموع ساعية
OI_LIMIT     = 1000   # ~42 يوم

print(f"\n{'='*60}")
print(f"  🤖 Trade Lak ML Training — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}\n")

# ══════════════════════════════════════════════════════════════════
# 1. جلب Fear & Greed التاريخي
# ══════════════════════════════════════════════════════════════════
def fetch_fear_greed(limit=200):
    """جلب مؤشر الخوف والجشع التاريخي من alternative.me"""
    try:
        r = requests.get(f'https://api.alternative.me/fng/?limit={limit}', timeout=10)
        data = r.json().get('data', [])
        fg_map = {}
        for item in data:
            ts = int(item['timestamp'])
            # تقريب إلى أقرب ساعة
            hour_ts = (ts // 3600) * 3600
            fg_map[hour_ts] = int(item['value'])
        print(f"  ✅ Fear & Greed: {len(fg_map)} نقطة")
        return fg_map
    except Exception as e:
        print(f"  ⚠️ Fear & Greed فشل: {e}")
        return {}

# ══════════════════════════════════════════════════════════════════
# 2. جلب OI History من CoinGlass
# ══════════════════════════════════════════════════════════════════
def fetch_oi_history(symbol, limit=OI_LIMIT):
    """جلب تاريخ Open Interest من CoinGlass"""
    try:
        url = f'{CG_BASE}/api/futures/openInterest/ohlc-aggregated-history'
        r = requests.get(url, headers={'CG-API-KEY': CG_KEY},
                         params={'symbol': symbol, 'interval': 'h1', 'limit': limit},
                         timeout=15)
        data = r.json().get('data', [])
        if not data:
            return {}
        oi_map = {}
        for item in data:
            ts = int(item['t'])
            oi_close = float(item.get('c', 0))
            oi_open  = float(item.get('o', 1))
            oi_change = (oi_close - oi_open) / oi_open if oi_open > 0 else 0
            oi_map[ts] = {'oi': oi_close, 'oi_change': oi_change}
        return oi_map
    except Exception as e:
        return {}

# ══════════════════════════════════════════════════════════════════
# 3. جلب OHLCV من OKX
# ══════════════════════════════════════════════════════════════════
def fetch_okx_candles(symbol, bar='1H', limit=CANDLE_LIMIT):
    """جلب الشموع التاريخية من OKX"""
    try:
        inst_id = f'{symbol}-USDT'
        url = f'{OKX_BASE}/api/v5/market/candles'
        all_candles = []
        after = None

        # جلب على دفعات (200 شمعة كحد أقصى لكل طلب)
        for _ in range(8):  # حتى 1600 شمعة
            params = {'instId': inst_id, 'bar': bar, 'limit': 200}
            if after:
                params['after'] = after
            r = requests.get(url, params=params, timeout=15)
            data = r.json().get('data', [])
            if not data:
                break
            all_candles.extend(data)
            if len(all_candles) >= limit:
                break
            after = data[-1][0]  # timestamp آخر شمعة
            time.sleep(0.3)

        if not all_candles:
            return []

        candles = []
        for c in all_candles[:limit]:
            candles.append({
                'timestamp': int(c[0]) // 1000,  # تحويل ms → s
                'open':   float(c[1]),
                'high':   float(c[2]),
                'low':    float(c[3]),
                'close':  float(c[4]),
                'volume': float(c[5]),
            })
        # ترتيب تصاعدي
        candles.sort(key=lambda x: x['timestamp'])
        return candles
    except Exception as e:
        return []

# ══════════════════════════════════════════════════════════════════
# 4. حساب الـ Features (مطابق تماماً لـ ml_model.py)
# ══════════════════════════════════════════════════════════════════
def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).fillna(50)

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    sig  = macd.ewm(span=signal).mean()
    return macd - sig  # histogram

def extract_features(df_window, coinglass_data=None):
    """
    استخراج 22 feature مطابقة لـ ml_model.py::extract_features()
    """
    features = []
    try:
        returns = df_window['close'].pct_change().fillna(0)
        features.append(float(returns.mean()))
        features.append(float(returns.std()))
        features.append(float(returns.iloc[-1]))

        price_min = df_window['close'].min()
        price_max = df_window['close'].max()
        norm_price = (df_window['close'].iloc[-1] - price_min) / (price_max - price_min + 1e-9)
        features.append(float(norm_price))

        today_chg = (df_window['close'].iloc[-1] - df_window['open'].iloc[-1]) / (df_window['open'].iloc[-1] + 1e-9)
        features.append(float(today_chg))

        vol_ma = df_window['volume'].rolling(5).mean()
        vol_ratio = df_window['volume'].iloc[-1] / (vol_ma.iloc[-1] + 1e-9)
        features.append(float(vol_ratio))

        rsi = calc_rsi(df_window['close'])
        features.append(float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0)

        hist = calc_macd(df_window['close'])
        features.append(float(hist.iloc[-1]) if not np.isnan(hist.iloc[-1]) else 0.0)

        hl_diff = df_window['high'].rolling(14).mean().iloc[-1] - df_window['low'].rolling(14).mean().iloc[-1]
        features.append(float(hl_diff))

        sma20 = df_window['close'].rolling(20).mean().iloc[-1]
        sma50 = df_window['close'].rolling(50).mean().iloc[-1]
        trend = (sma20 - sma50) / (sma50 + 1e-9)
        features.append(float(trend))

        # CoinGlass features (4 features)
        if coinglass_data:
            features.append(float(coinglass_data.get('funding_rate', 0)))
            features.append(float(coinglass_data.get('long_short_ratio', 0.5)))
            features.append(float(coinglass_data.get('liquidation_pressure', 0)))
            features.append(float(coinglass_data.get('open_interest_change', 0)))
        else:
            features.extend([0.0, 0.5, 0.0, 0.0])

        # Placeholders (whale + orderbook)
        features.append(0.0)
        features.append(0.0)

        # Level2 features (6 features)
        try:
            ema9  = df_window['close'].ewm(span=9).mean()
            ema21 = df_window['close'].ewm(span=21).mean()
            ema_cross = (ema9.iloc[-1] - ema21.iloc[-1]) / (ema21.iloc[-1] + 1e-9)
            features.append(float(ema_cross))

            bb_mid = df_window['close'].rolling(20).mean()
            bb_std = df_window['close'].rolling(20).std()
            bb_width = (2 * bb_std.iloc[-1]) / (bb_mid.iloc[-1] + 1e-9)
            features.append(float(bb_width))

            bb_upper = bb_mid.iloc[-1] + 2 * bb_std.iloc[-1]
            bb_lower = bb_mid.iloc[-1] - 2 * bb_std.iloc[-1]
            bb_range = bb_upper - bb_lower
            price_in_bb = (df_window['close'].iloc[-1] - bb_lower) / (bb_range + 1e-9)
            features.append(float(np.clip(price_in_bb, 0, 1)))

            vpc = df_window['close'].pct_change().tail(10).corr(df_window['volume'].pct_change().tail(10))
            features.append(float(vpc) if not math.isnan(float(vpc)) else 0.0)

            mom3 = (df_window['close'].iloc[-1] - df_window['close'].iloc[-4]) / (df_window['close'].iloc[-4] + 1e-9) if len(df_window) >= 4 else 0.0
            features.append(float(mom3))

            body = abs(df_window['close'].iloc[-1] - df_window['open'].iloc[-1])
            total_range = df_window['high'].iloc[-1] - df_window['low'].iloc[-1]
            body_ratio = body / (total_range + 1e-9)
            features.append(float(body_ratio))
        except Exception:
            features.extend([0.0, 0.0, 0.5, 0.0, 0.0, 0.5])

        return np.array(features, dtype=np.float32)
    except Exception as e:
        return np.zeros(22, dtype=np.float32)

# ══════════════════════════════════════════════════════════════════
# 5. توليد Labels (هل ارتفع السعر 1.5% خلال 4 ساعات؟)
# ══════════════════════════════════════════════════════════════════
def generate_label(df, idx, lookahead=4, target_pct=0.015):
    """1 = ارتفع السعر بـ 1.5%+ خلال 4 ساعات | 0 = لم يرتفع"""
    if idx + lookahead >= len(df):
        return None
    current_price = df['close'].iloc[idx]
    future_prices = df['close'].iloc[idx+1:idx+lookahead+1]
    max_future = future_prices.max()
    return 1 if (max_future - current_price) / current_price >= target_pct else 0

# ══════════════════════════════════════════════════════════════════
# 6. البرنامج الرئيسي
# ══════════════════════════════════════════════════════════════════
def main():
    print("📥 جلب Fear & Greed التاريخي...")
    fg_map = fetch_fear_greed(200)

    all_features = []
    all_labels   = []
    symbol_stats = {}

    for sym in SYMBOLS:
        print(f"\n  📊 معالجة {sym}...")

        # جلب الشموع
        candles = fetch_okx_candles(sym, bar='1H', limit=CANDLE_LIMIT)
        if len(candles) < 100:
            print(f"    ⚠️ بيانات غير كافية: {len(candles)} شمعة")
            continue
        time.sleep(0.5)

        # جلب OI History
        oi_map = fetch_oi_history(sym)
        time.sleep(0.3)

        df = pd.DataFrame(candles)
        df.set_index('timestamp', inplace=True)

        sym_features = 0
        sym_labels_1 = 0

        # نافذة 60 شمعة لكل نقطة
        window = 60
        for i in range(window, len(df) - 5):
            df_win = df.iloc[i-window:i+1].copy()
            ts = df.index[i]

            # CoinGlass data للنقطة الزمنية
            oi_entry = oi_map.get(ts, {})
            fg_val   = fg_map.get((ts // 3600) * 3600, 50)

            cg_data = {
                'funding_rate': 0.01,  # افتراضي معقول
                'long_short_ratio': 0.5,
                'liquidation_pressure': 0.0,
                'open_interest_change': oi_entry.get('oi_change', 0.0),
                'fear_greed': fg_val / 100.0,
            }

            feats = extract_features(df_win, cg_data)
            label = generate_label(df, i)

            if label is None or len(feats) != 22:
                continue

            all_features.append(feats)
            all_labels.append(label)
            sym_features += 1
            if label == 1:
                sym_labels_1 += 1

        symbol_stats[sym] = {
            'samples': sym_features,
            'positive': sym_labels_1,
            'candles': len(candles)
        }
        print(f"    ✅ {sym_features} عينة | إشارات شراء: {sym_labels_1} ({sym_labels_1/max(sym_features,1)*100:.1f}%)")

    print(f"\n{'='*60}")
    print(f"  📊 إجمالي البيانات: {len(all_features)} عينة")
    print(f"  📊 إشارات شراء: {sum(all_labels)} ({sum(all_labels)/max(len(all_labels),1)*100:.1f}%)")
    print(f"{'='*60}\n")

    if len(all_features) < 200:
        print("❌ بيانات غير كافية للتدريب (< 200 عينة)")
        return False

    X = np.array(all_features, dtype=np.float32)
    y = np.array(all_labels)

    print("🔧 تدريب النماذج...")

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    # Random Forest
    print("  🌲 تدريب Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_acc  = accuracy_score(y_test, rf_pred)
    rf_prec = precision_score(y_test, rf_pred, zero_division=0)
    rf_rec  = recall_score(y_test, rf_pred, zero_division=0)
    rf_f1   = f1_score(y_test, rf_pred, zero_division=0)

    # Gradient Boosting
    print("  🚀 تدريب Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        random_state=42
    )
    gb.fit(X_train, y_train)
    gb_pred = gb.predict(X_test)
    gb_acc  = accuracy_score(y_test, gb_pred)
    gb_prec = precision_score(y_test, gb_pred, zero_division=0)
    gb_rec  = recall_score(y_test, gb_pred, zero_division=0)
    gb_f1   = f1_score(y_test, gb_pred, zero_division=0)

    # حفظ النماذج
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(rf,     MODELS_DIR / 'rf_model.pkl')
    joblib.dump(gb,     MODELS_DIR / 'gb_model.pkl')
    joblib.dump(scaler, MODELS_DIR / 'scaler.pkl')

    # حفظ تقرير التدريب
    report = {
        'trained_at': datetime.now().isoformat(),
        'total_samples': len(all_features),
        'positive_ratio': float(sum(all_labels) / len(all_labels)),
        'symbols': list(symbol_stats.keys()),
        'n_features': 22,
        'rf': {'accuracy': rf_acc, 'precision': rf_prec, 'recall': rf_rec, 'f1': rf_f1},
        'gb': {'accuracy': gb_acc, 'precision': gb_prec, 'recall': gb_rec, 'f1': gb_f1},
        'symbol_stats': symbol_stats,
    }
    with open(MODELS_DIR / 'training_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  ✅ التدريب اكتمل!")
    print(f"{'='*60}")
    print(f"\n  🌲 Random Forest:")
    print(f"     Accuracy:  {rf_acc*100:.1f}%")
    print(f"     Precision: {rf_prec*100:.1f}%")
    print(f"     Recall:    {rf_rec*100:.1f}%")
    print(f"     F1-Score:  {rf_f1*100:.1f}%")
    print(f"\n  🚀 Gradient Boosting:")
    print(f"     Accuracy:  {gb_acc*100:.1f}%")
    print(f"     Precision: {gb_prec*100:.1f}%")
    print(f"     Recall:    {gb_rec*100:.1f}%")
    print(f"     F1-Score:  {gb_f1*100:.1f}%")
    print(f"\n  📁 النماذج محفوظة في: {MODELS_DIR}")
    print(f"  📊 عينات التدريب: {len(all_features):,}")
    print(f"  🎯 عملات مُدرَّبة: {len(symbol_stats)}")
    print(f"{'='*60}\n")

    return True

if __name__ == '__main__':
    start = time.time()
    success = main()
    elapsed = time.time() - start
    print(f"⏱️ الوقت الكلي: {elapsed/60:.1f} دقيقة")
    sys.exit(0 if success else 1)
