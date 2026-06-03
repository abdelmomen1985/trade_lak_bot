#!/usr/bin/env python3
"""
Train v3 — Enhanced ML + LSTM
يضيف Liquidations التاريخية من CoinGlass كـ feature جديد
ويدرّب نموذج LSTM للتعلم العميق
"""
import sys
sys.path.insert(0, '/root/trade_lak_bot')
sys.path.insert(0, '/root/trade_lak_bot/core')

import os
import json
import time
import logging
import numpy as np
import pandas as pd
import joblib
import requests
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ─── إعدادات ──────────────────────────────────────────────────────────────────
COINGLASS_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
CG_HEADERS = {'CG-API-KEY': COINGLASS_KEY}
CG_BASE = "https://open-api-v3.coinglass.com"

MODELS_DIR = '/root/trade_lak_bot/models'
os.makedirs(MODELS_DIR, exist_ok=True)

# العملات الكبيرة المشتركة (OKX + Bybit + CoinGlass)
MAJOR_SYMBOLS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX',
    'DOT', 'LINK', 'UNI', 'ATOM', 'LTC', 'NEAR', 'APT', 'ARB',
    'OP', 'SUI', 'INJ', 'TIA'
]

# ─── جلب بيانات OKX OHLCV ─────────────────────────────────────────────────────
def fetch_okx_ohlcv(symbol: str, bar: str = '1H', limit: int = 1000) -> list:
    """جلب شموع OKX"""
    try:
        url = "https://www.okx.com/api/v5/market/history-candles"
        params = {'instId': f'{symbol}-USDT', 'bar': bar, 'limit': str(limit)}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get('code') == '0' and data.get('data'):
            candles = []
            for c in reversed(data['data']):
                candles.append({
                    'timestamp': int(c[0]),
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5]),
                })
            return candles
    except Exception as e:
        logger.debug(f"OKX OHLCV {symbol}: {e}")
    return []

# ─── جلب بيانات Bybit OHLCV ───────────────────────────────────────────────────
def fetch_bybit_ohlcv(symbol: str, interval: str = '60', limit: int = 1000) -> list:
    """جلب شموع Bybit"""
    try:
        url = "https://api.bybit.com/v5/market/kline"
        params = {'symbol': f'{symbol}USDT', 'interval': interval, 'limit': str(limit)}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get('retCode') == 0 and data.get('result', {}).get('list'):
            candles = []
            for c in reversed(data['result']['list']):
                candles.append({
                    'timestamp': int(c[0]),
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5]),
                })
            return candles
    except Exception as e:
        logger.debug(f"Bybit OHLCV {symbol}: {e}")
    return []

# ─── جلب Liquidations من CoinGlass ───────────────────────────────────────────
def fetch_liquidations(symbol: str, interval: str = '1h', limit: int = 1000) -> dict:
    """جلب بيانات Liquidations التاريخية"""
    liq_map = {}
    try:
        r = requests.get(f"{CG_BASE}/api/futures/liquidation/aggregated-history",
            headers=CG_HEADERS,
            params={'symbol': symbol, 'interval': interval, 'limit': limit},
            timeout=10)
        data = r.json()
        if data.get('success') and data.get('data'):
            for item in data['data']:
                ts = item['t'] * 1000  # تحويل لـ milliseconds
                long_liq = float(item.get('longLiquidationUsd', 0))
                short_liq = float(item.get('shortLiquidationUsd', 0))
                liq_map[ts] = {
                    'long_liq': long_liq,
                    'short_liq': short_liq,
                    'total_liq': long_liq + short_liq,
                    'liq_ratio': long_liq / (short_liq + 1),  # نسبة Long/Short liquidations
                }
    except Exception as e:
        logger.debug(f"Liquidations {symbol}: {e}")
    return liq_map

# ─── جلب OI من CoinGlass ─────────────────────────────────────────────────────
def fetch_oi_history(symbol: str, interval: str = '1h', limit: int = 1000) -> dict:
    """جلب Open Interest التاريخي"""
    oi_map = {}
    try:
        r = requests.get(f"{CG_BASE}/api/futures/openInterest/ohlc-history",
            headers=CG_HEADERS,
            params={'symbol': symbol, 'interval': interval, 'limit': limit},
            timeout=10)
        data = r.json()
        if data.get('success') and data.get('data'):
            prev_oi = None
            for item in data['data']:
                ts = item['t'] * 1000
                oi = float(item.get('c', item.get('o', 0)))
                oi_change = (oi - prev_oi) / prev_oi if prev_oi and prev_oi > 0 else 0
                oi_map[ts] = {'oi': oi, 'oi_change': oi_change}
                prev_oi = oi
    except Exception as e:
        logger.debug(f"OI {symbol}: {e}")
    return oi_map

# ─── جلب Funding Rate من CoinGlass ───────────────────────────────────────────
def fetch_funding_history(symbol: str, limit: int = 500) -> dict:
    """جلب Funding Rate التاريخي"""
    fr_map = {}
    try:
        r = requests.get(f"{CG_BASE}/api/futures/fundingRate/ohlc-history",
            headers=CG_HEADERS,
            params={'symbol': symbol, 'interval': '8h', 'limit': limit},
            timeout=10)
        data = r.json()
        if data.get('success') and data.get('data'):
            for item in data['data']:
                ts = item['t'] * 1000
                fr = float(item.get('c', 0))
                fr_map[ts] = fr
    except Exception as e:
        logger.debug(f"Funding {symbol}: {e}")
    return fr_map

# ─── جلب Fear & Greed ─────────────────────────────────────────────────────────
def fetch_fear_greed(limit: int = 500) -> dict:
    """جلب مؤشر الخوف والجشع التاريخي"""
    fg_map = {}
    try:
        r = requests.get(f"https://api.alternative.me/fng/?limit={limit}&format=json", timeout=10)
        data = r.json()
        if data.get('data'):
            for item in data['data']:
                ts = int(item['timestamp']) * 1000
                fg_map[ts] = int(item['value'])
    except Exception as e:
        logger.debug(f"Fear&Greed: {e}")
    return fg_map

# ─── بناء الـ Features ────────────────────────────────────────────────────────
def build_features(candles: list, liq_map: dict = None, oi_map: dict = None,
                   fr_map: dict = None, fg_map: dict = None) -> pd.DataFrame:
    """بناء 28 feature من البيانات المتاحة"""
    if len(candles) < 50:
        return pd.DataFrame()
    
    df = pd.DataFrame(candles)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # ─── المؤشرات التقنية الأساسية (22 feature) ───
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # EMA
    df['ema9']  = close.ewm(span=9,  adjust=False).mean()
    df['ema21'] = close.ewm(span=21, adjust=False).mean()
    df['ema50'] = close.ewm(span=50, adjust=False).mean()
    df['ema_cross'] = (df['ema9'] > df['ema21']).astype(float)
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df['bb_upper'] = sma20 + 2 * std20
    df['bb_lower'] = sma20 - 2 * std20
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (sma20 + 1e-10)
    df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
    
    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_pct'] = df['atr'] / (close + 1e-10)
    
    # Volume
    df['vol_ma'] = volume.rolling(20).mean()
    df['vol_ratio'] = volume / (df['vol_ma'] + 1e-10)
    
    # Price changes
    df['price_change_1h'] = close.pct_change(1)
    df['price_change_4h'] = close.pct_change(4)
    df['price_change_24h'] = close.pct_change(24)
    
    # Stochastic
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    df['stoch_k'] = 100 * (close - low14) / (high14 - low14 + 1e-10)
    
    # ─── Features من CoinGlass (6 features جديدة) ───
    # Liquidations
    if liq_map:
        df['long_liq'] = df['timestamp'].map(lambda ts: liq_map.get(ts, {}).get('long_liq', 0))
        df['short_liq'] = df['timestamp'].map(lambda ts: liq_map.get(ts, {}).get('short_liq', 0))
        df['total_liq'] = df['long_liq'] + df['short_liq']
        df['liq_ratio'] = df['long_liq'] / (df['short_liq'] + 1)
        # تطبيع
        liq_max = df['total_liq'].quantile(0.99) + 1
        df['liq_normalized'] = df['total_liq'] / liq_max
    else:
        df['long_liq'] = 0
        df['short_liq'] = 0
        df['total_liq'] = 0
        df['liq_ratio'] = 1
        df['liq_normalized'] = 0
    
    # OI Change
    if oi_map:
        df['oi_change'] = df['timestamp'].map(lambda ts: oi_map.get(ts, {}).get('oi_change', 0))
    else:
        df['oi_change'] = 0
    
    # Funding Rate
    if fr_map:
        # أقرب funding rate (كل 8 ساعات)
        fr_timestamps = sorted(fr_map.keys())
        def get_nearest_fr(ts):
            if not fr_timestamps:
                return 0
            idx = min(range(len(fr_timestamps)), key=lambda i: abs(fr_timestamps[i] - ts))
            return fr_map[fr_timestamps[idx]]
        df['funding_rate'] = df['timestamp'].map(get_nearest_fr)
    else:
        df['funding_rate'] = 0
    
    # Fear & Greed
    if fg_map:
        fg_timestamps = sorted(fg_map.keys())
        def get_nearest_fg(ts):
            if not fg_timestamps:
                return 50
            idx = min(range(len(fg_timestamps)), key=lambda i: abs(fg_timestamps[i] - ts))
            return fg_map[fg_timestamps[idx]]
        df['fear_greed'] = df['timestamp'].map(get_nearest_fg)
    else:
        df['fear_greed'] = 50
    
    # ─── Target: هل سيرتفع السعر 1.5% خلال 4 ساعات؟ ───
    df['future_return'] = close.shift(-4) / close - 1
    df['target'] = (df['future_return'] > 0.015).astype(int)
    
    return df

# ─── Feature columns ──────────────────────────────────────────────────────────
FEATURE_COLS = [
    'rsi', 'ema_cross', 'macd', 'macd_hist', 'macd_signal',
    'bb_width', 'bb_position', 'atr_pct',
    'vol_ratio', 'price_change_1h', 'price_change_4h', 'price_change_24h',
    'stoch_k',
    'ema9', 'ema21', 'ema50',
    'bb_upper', 'bb_lower',
    # CoinGlass features
    'long_liq', 'short_liq', 'liq_normalized', 'liq_ratio',
    'oi_change', 'funding_rate', 'fear_greed',
    # Extra
    'vol_ma',
    'atr',
    'price_change_1h',
]

# إزالة التكرار
FEATURE_COLS = list(dict.fromkeys(FEATURE_COLS))

# ─── جمع البيانات ─────────────────────────────────────────────────────────────
def collect_training_data():
    """جمع بيانات التدريب من جميع المصادر"""
    logger.info("🚀 بدء جمع بيانات التدريب v3 (مع Liquidations)")
    
    # جلب Fear & Greed مرة واحدة
    logger.info("📊 جلب Fear & Greed التاريخي...")
    fg_map = fetch_fear_greed(500)
    logger.info(f"  ✅ {len(fg_map)} نقطة Fear & Greed")
    
    all_dfs = []
    
    for i, symbol in enumerate(MAJOR_SYMBOLS):
        logger.info(f"[{i+1}/{len(MAJOR_SYMBOLS)}] {symbol}...")
        
        # جلب OKX OHLCV
        candles = fetch_okx_ohlcv(symbol, '1H', 1000)
        if len(candles) < 100:
            candles = fetch_bybit_ohlcv(symbol, '60', 1000)
        
        if len(candles) < 100:
            logger.warning(f"  ⚠️ {symbol}: بيانات غير كافية ({len(candles)})")
            continue
        
        # جلب Liquidations
        liq_map = fetch_liquidations(symbol, '1h', 1000)
        
        # جلب OI
        oi_map = fetch_oi_history(symbol, '1h', 1000)
        
        # جلب Funding Rate
        fr_map = fetch_funding_history(symbol, 500)
        
        logger.info(f"  📦 {len(candles)} شمعة | Liq={len(liq_map)} | OI={len(oi_map)} | FR={len(fr_map)}")
        
        # بناء features
        df = build_features(candles, liq_map, oi_map, fr_map, fg_map)
        if df.empty or len(df) < 50:
            continue
        
        df['symbol'] = symbol
        all_dfs.append(df)
        time.sleep(0.3)  # تجنب rate limiting
    
    if not all_dfs:
        logger.error("❌ لا توجد بيانات كافية!")
        return pd.DataFrame()
    
    combined = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"✅ إجمالي البيانات: {len(combined):,} صف من {len(all_dfs)} عملة")
    return combined

# ─── تدريب النماذج التقليدية ──────────────────────────────────────────────────
def train_traditional_models(df: pd.DataFrame, prefix: str = 'okx'):
    """تدريب Random Forest + Gradient Boosting"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🤖 تدريب نماذج {prefix.upper()} v3")
    
    # تنظيف البيانات
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    df_clean = df[available_cols + ['target']].dropna()
    df_clean = df_clean[np.isfinite(df_clean).all(axis=1)]
    
    if len(df_clean) < 500:
        logger.error(f"❌ بيانات غير كافية: {len(df_clean)}")
        return None
    
    X = df_clean[available_cols].values
    y = df_clean['target'].values
    
    logger.info(f"📊 عينات: {len(X):,} | Features: {len(available_cols)} | Target ratio: {y.mean():.1%}")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scaler
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    results = {}
    
    # Random Forest
    logger.info("🌲 تدريب Random Forest...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=5,
                                 n_jobs=-1, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    rf_prec = precision_score(y_test, rf_pred, zero_division=0)
    logger.info(f"  ✅ RF: Accuracy={rf_acc:.1%} | Precision={rf_prec:.1%}")
    results['rf'] = {'model': rf, 'acc': rf_acc, 'prec': rf_prec}
    
    # Gradient Boosting
    logger.info("🚀 تدريب Gradient Boosting...")
    gb = GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                                     subsample=0.8, random_state=42)
    gb.fit(X_train_s, y_train)
    gb_pred = gb.predict(X_test_s)
    gb_acc = accuracy_score(y_test, gb_pred)
    gb_prec = precision_score(y_test, gb_pred, zero_division=0)
    logger.info(f"  ✅ GB: Accuracy={gb_acc:.1%} | Precision={gb_prec:.1%}")
    results['gb'] = {'model': gb, 'acc': gb_acc, 'prec': gb_prec}
    
    # حفظ النماذج
    model_path = f"{MODELS_DIR}/{prefix}_rf_model.pkl"
    gb_path = f"{MODELS_DIR}/{prefix}_gb_model.pkl"
    scaler_path = f"{MODELS_DIR}/{prefix}_scaler.pkl"
    meta_path = f"{MODELS_DIR}/{prefix}_model_meta.json"
    
    joblib.dump(rf, model_path)
    joblib.dump(gb, gb_path)
    joblib.dump(scaler, scaler_path)
    
    meta = {
        'version': 'v3_liquidations',
        'trained_at': datetime.now().isoformat(),
        'n_features': len(available_cols),
        'feature_names': available_cols,
        'n_samples': len(X),
        'rf_accuracy': rf_acc,
        'gb_accuracy': gb_acc,
        'rf_precision': rf_prec,
        'gb_precision': gb_prec,
        'symbols': list(df['symbol'].unique()) if 'symbol' in df.columns else [],
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    
    logger.info(f"💾 النماذج محفوظة في {MODELS_DIR}/{prefix}_*.pkl")
    return results

# ─── تدريب LSTM ───────────────────────────────────────────────────────────────
def train_lstm_model(df: pd.DataFrame, prefix: str = 'okx'):
    """تدريب نموذج LSTM للتعلم العميق"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🧠 تدريب نموذج LSTM {prefix.upper()}")
    
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        logger.info("✅ TensorFlow متاح")
    except ImportError:
        logger.warning("⚠️ TensorFlow غير متاح — تثبيت...")
        os.system('/root/trade_lak_bot/venv/bin/pip install tensorflow-cpu --quiet')
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
            from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        except ImportError:
            logger.error("❌ فشل تثبيت TensorFlow — سيتم استخدام نموذج بديل")
            return train_lstm_fallback(df, prefix)
    
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    df_clean = df[available_cols + ['target']].dropna()
    df_clean = df_clean[np.isfinite(df_clean).all(axis=1)]
    
    if len(df_clean) < 1000:
        logger.error(f"❌ بيانات غير كافية للـ LSTM: {len(df_clean)}")
        return None
    
    X = df_clean[available_cols].values
    y = df_clean['target'].values
    
    # تطبيع
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # بناء sequences (lookback = 24 ساعة)
    LOOKBACK = 24
    X_seq, y_seq = [], []
    for i in range(LOOKBACK, len(X_scaled)):
        X_seq.append(X_scaled[i-LOOKBACK:i])
        y_seq.append(y[i])
    
    X_seq = np.array(X_seq)
    y_seq = np.array(y_seq)
    
    split = int(len(X_seq) * 0.8)
    X_train, X_test = X_seq[:split], X_seq[split:]
    y_train, y_test = y_seq[:split], y_seq[split:]
    
    logger.info(f"📊 LSTM: {len(X_train):,} train | {len(X_test):,} test | shape={X_train.shape}")
    
    # بناء النموذج
    model = Sequential([
        LSTM(128, return_sequences=True, input_shape=(LOOKBACK, len(available_cols))),
        Dropout(0.2),
        BatchNormalization(),
        LSTM(64, return_sequences=False),
        Dropout(0.2),
        BatchNormalization(),
        Dense(32, activation='relu'),
        Dropout(0.1),
        Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    
    callbacks = [
        EarlyStopping(patience=5, restore_best_weights=True),
        ReduceLROnPlateau(patience=3, factor=0.5)
    ]
    
    logger.info("🏋️ تدريب LSTM...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=30,
        batch_size=64,
        callbacks=callbacks,
        verbose=0
    )
    
    # تقييم
    y_pred = (model.predict(X_test, verbose=0) > 0.5).astype(int).flatten()
    lstm_acc = accuracy_score(y_test, y_pred)
    lstm_prec = precision_score(y_test, y_pred, zero_division=0)
    
    logger.info(f"  ✅ LSTM: Accuracy={lstm_acc:.1%} | Precision={lstm_prec:.1%}")
    
    # حفظ النموذج
    lstm_path = f"{MODELS_DIR}/{prefix}_lstm_model.keras"
    model.save(lstm_path)
    
    lstm_meta = {
        'version': 'v3_lstm',
        'trained_at': datetime.now().isoformat(),
        'lookback': LOOKBACK,
        'n_features': len(available_cols),
        'feature_names': available_cols,
        'lstm_accuracy': lstm_acc,
        'lstm_precision': lstm_prec,
        'n_samples': len(X_seq),
    }
    with open(f"{MODELS_DIR}/{prefix}_lstm_meta.json", 'w') as f:
        json.dump(lstm_meta, f, indent=2)
    
    # حفظ scaler
    joblib.dump(scaler, f"{MODELS_DIR}/{prefix}_lstm_scaler.pkl")
    
    logger.info(f"💾 LSTM محفوظ في {lstm_path}")
    return {'acc': lstm_acc, 'prec': lstm_prec}

def train_lstm_fallback(df: pd.DataFrame, prefix: str = 'okx'):
    """بديل LSTM باستخدام ExtraTreesClassifier إذا فشل TensorFlow"""
    from sklearn.ensemble import ExtraTreesClassifier
    logger.info(f"🔄 استخدام ExtraTrees كبديل LSTM لـ {prefix}")
    
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    df_clean = df[available_cols + ['target']].dropna()
    df_clean = df_clean[np.isfinite(df_clean).all(axis=1)]
    
    X = df_clean[available_cols].values
    y = df_clean['target'].values
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    et = ExtraTreesClassifier(n_estimators=300, n_jobs=-1, random_state=42)
    et.fit(X_train, y_train)
    
    et_pred = et.predict(X_test)
    et_acc = accuracy_score(y_test, et_pred)
    et_prec = precision_score(y_test, et_pred, zero_division=0)
    
    logger.info(f"  ✅ ExtraTrees: Accuracy={et_acc:.1%} | Precision={et_prec:.1%}")
    
    joblib.dump(et, f"{MODELS_DIR}/{prefix}_lstm_model.pkl")
    
    meta = {
        'version': 'v3_extratrees_fallback',
        'trained_at': datetime.now().isoformat(),
        'n_features': len(available_cols),
        'feature_names': available_cols,
        'accuracy': et_acc,
        'precision': et_prec,
    }
    with open(f"{MODELS_DIR}/{prefix}_lstm_meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
    
    return {'acc': et_acc, 'prec': et_prec}

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    start = time.time()
    logger.info("=" * 70)
    logger.info("🚀 Trade Lak ML Training v3 — مع Liquidations + LSTM")
    logger.info("=" * 70)
    
    # جمع البيانات
    df = collect_training_data()
    
    if df.empty:
        logger.error("❌ فشل جمع البيانات!")
        sys.exit(1)
    
    # تدريب النماذج التقليدية
    results = train_traditional_models(df, 'okx')
    
    # تدريب LSTM
    lstm_results = train_lstm_model(df, 'okx')
    
    elapsed = time.time() - start
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ اكتمل التدريب في {elapsed/60:.1f} دقيقة")
    if results:
        logger.info(f"📊 RF: {results['rf']['acc']:.1%} | GB: {results['gb']['acc']:.1%}")
    if lstm_results:
        logger.info(f"🧠 LSTM/ET: {lstm_results['acc']:.1%}")
    logger.info(f"💾 النماذج محفوظة في: {MODELS_DIR}")
    logger.info("=" * 70)
