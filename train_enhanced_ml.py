#!/usr/bin/env python3
"""
سكريبت التدريب الشامل المحسّن
يدمج: OKX OHLCV + Bybit OHLCV + CoinGlass (OI + Funding + L/S) + Fear&Greed
يُنتج نموذجين منفصلين:
  - models/okx_rf_model.pkl / okx_gb_model.pkl  (للعملات المشتركة على OKX)
  - models/bybit_rf_model.pkl / bybit_gb_model.pkl (للعملات على Bybit)
"""
import sys, os, time, json, logging, warnings
warnings.filterwarnings('ignore')

import requests
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/root/trade_lak_bot/logs/enhanced_ml_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('enhanced_ml_trainer')

# ─── الإعدادات ───────────────────────────────────────────────
COINGLASS_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
CG_HEADERS    = {'CG-API-KEY': COINGLASS_KEY}
MODELS_DIR    = '/root/trade_lak_bot/models'
os.makedirs(MODELS_DIR, exist_ok=True)

# العملات الكبيرة المشتركة (تدعم CoinGlass)
MAJOR_SYMBOLS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX',
    'DOT', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH',
    'NEAR', 'APT', 'ARB', 'OP', 'SUI', 'INJ', 'TIA', 'SEI',
    'WLD', 'JUP', 'PYTH', 'STRK', 'MANTA', 'ALT', 'PIXEL'
]

# العملات الحصرية على Bybit (لا تدعم CoinGlass)
BYBIT_EXCLUSIVE = [
    'MNT', 'BILL', 'H', 'VVV', 'BSB', 'HOLO', 'IO',
    'DRIFT', 'FF', 'ICNT', 'XDC', 'BLAST', 'AERO', 'NOM',
    'SPX', 'APEX', 'BOBA', 'KAS', 'VET', 'DEEP', 'AXL', 'BBSOL', 'BAN',
    'HFT', 'HOME', 'POPCAT', 'LUNC', 'VTHO', 'JASMY', 'PORTAL', 'ZIG',
]

# ─── جلب Fear & Greed التاريخي ───────────────────────────────
def fetch_fear_greed(limit: int = 1000) -> Dict[int, float]:
    """يُعيد dict: {timestamp_day -> value}"""
    try:
        r = requests.get(f'https://api.alternative.me/fng/?limit={limit}&format=json', timeout=10)
        data = r.json().get('data', [])
        result = {}
        for item in data:
            ts_day = int(item['timestamp']) // 86400 * 86400
            result[ts_day] = float(item['value']) / 100.0
        logger.info(f"✅ Fear&Greed: {len(result)} يوم")
        return result
    except Exception as e:
        logger.warning(f"⚠️ Fear&Greed فشل: {e}")
        return {}

# ─── جلب OI History من CoinGlass ────────────────────────────
def fetch_oi_history(symbol: str, exchange: str = 'Bybit', limit: int = 500) -> Dict[int, float]:
    """يُعيد dict: {timestamp -> oi_change_pct}"""
    try:
        r = requests.get(
            'https://open-api-v3.coinglass.com/api/futures/openInterest/ohlc-history',
            params={'exchange': exchange, 'symbol': f'{symbol}USDT', 'interval': 'h1', 'limit': limit},
            headers=CG_HEADERS, timeout=10
        )
        data = r.json().get('data', [])
        result = {}
        for i, item in enumerate(data):
            if i == 0:
                result[item['t']] = 0.0
                continue
            prev_c = float(data[i-1].get('c', 1))
            curr_c = float(item.get('c', prev_c))
            change = (curr_c - prev_c) / (prev_c + 1e-10)
            result[item['t']] = max(-0.5, min(0.5, change))
        return result
    except Exception as e:
        logger.debug(f"OI {symbol}: {e}")
        return {}

# ─── جلب Funding Rate من CoinGlass ──────────────────────────
def fetch_funding_history(symbol: str, exchange: str = 'Bybit', limit: int = 200) -> Dict[int, float]:
    """يُعيد dict: {timestamp -> funding_rate}"""
    try:
        r = requests.get(
            'https://open-api-v3.coinglass.com/api/futures/fundingRate/ohlc-history',
            params={'exchange': exchange, 'symbol': f'{symbol}USDT', 'interval': 'h8', 'limit': limit},
            headers=CG_HEADERS, timeout=10
        )
        data = r.json().get('data', [])
        result = {}
        for item in data:
            # توزيع على 8 ساعات
            ts = item['t']
            val = float(item.get('c', 0))
            for h in range(8):
                result[ts + h*3600] = val
        return result
    except Exception as e:
        logger.debug(f"Funding {symbol}: {e}")
        return {}

# ─── جلب Long/Short Ratio من CoinGlass ──────────────────────
def fetch_ls_ratio(symbol: str, exchange: str = 'Bybit', limit: int = 500) -> Dict[int, float]:
    """يُعيد dict: {timestamp -> ls_ratio_normalized}"""
    try:
        r = requests.get(
            'https://open-api-v3.coinglass.com/api/futures/globalLongShortAccountRatio/history',
            params={'exchange': exchange, 'symbol': f'{symbol}USDT', 'interval': '1h', 'limit': limit},
            headers=CG_HEADERS, timeout=10
        )
        data = r.json().get('data', [])
        result = {}
        for item in data:
            ts = item.get('time', item.get('t', 0))
            long_pct = float(item.get('longAccount', item.get('longRatio', 0.5)))
            result[ts] = long_pct  # 0.0 - 1.0
        return result
    except Exception as e:
        logger.debug(f"L/S {symbol}: {e}")
        return {}

# ─── جلب OHLCV من Bybit ─────────────────────────────────────
def fetch_bybit_klines(symbol: str, interval: str = '60', limit: int = 1000) -> pd.DataFrame:
    try:
        r = requests.get(
            'https://api.bybit.com/v5/market/kline',
            params={'category': 'spot', 'symbol': f'{symbol}USDT',
                    'interval': interval, 'limit': limit},
            timeout=10
        )
        data = r.json()
        if data.get('retCode') != 0:
            return pd.DataFrame()
        rows = data.get('result', {}).get('list', [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.astype({'ts': int, 'open': float, 'high': float, 'low': float,
                        'close': float, 'volume': float, 'turnover': float})
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df.sort_values('ts').reset_index(drop=True)
    except Exception as e:
        logger.debug(f"Bybit klines {symbol}: {e}")
        return pd.DataFrame()

# ─── جلب OHLCV من OKX ───────────────────────────────────────
def fetch_okx_klines(symbol: str, bar: str = '1H', limit: int = 1000) -> pd.DataFrame:
    try:
        r = requests.get(
            'https://www.okx.com/api/v5/market/history-candles',
            params={'instId': f'{symbol}-USDT', 'bar': bar, 'limit': limit},
            timeout=10
        )
        data = r.json()
        if data.get('code') != '0':
            return pd.DataFrame()
        rows = data.get('data', [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'])
        df = df.astype({'ts': int, 'open': float, 'high': float, 'low': float,
                        'close': float, 'volume': float})
        df['turnover'] = df['volCcyQuote'].astype(float)
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df.sort_values('ts').reset_index(drop=True)
    except Exception as e:
        logger.debug(f"OKX klines {symbol}: {e}")
        return pd.DataFrame()

# ─── بناء الـ Features (22 تقني + 4 CoinGlass + 1 Fear&Greed = 27) ─
def build_features_enhanced(df: pd.DataFrame,
                              oi_map: Dict = None,
                              funding_map: Dict = None,
                              ls_map: Dict = None,
                              fg_map: Dict = None) -> pd.DataFrame:
    if len(df) < 50:
        return pd.DataFrame()

    closes = df['close'].values
    highs  = df['high'].values
    lows   = df['low'].values
    vols   = df['volume'].values
    turns  = df['turnover'].values if 'turnover' in df.columns else vols * closes

    def ema(arr, p):
        return pd.Series(arr).ewm(span=p, adjust=False).mean().values

    def rsi(arr, p=14):
        s = pd.Series(arr)
        delta = s.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_g = gain.ewm(com=p-1, adjust=False).mean()
        avg_l = loss.ewm(com=p-1, adjust=False).mean()
        rs = avg_g / (avg_l + 1e-10)
        return (100 - (100/(1+rs))).values

    def atr(h, l, c, p=14):
        tr = np.maximum(h[1:]-l[1:], np.maximum(abs(h[1:]-c[:-1]), abs(l[1:]-c[:-1])))
        tr = np.concatenate([[tr[0]], tr])
        return pd.Series(tr).rolling(p).mean().values

    ema9  = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    atr14 = atr(highs, lows, closes, 14)

    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    bb_width = (bb_upper - bb_lower) / (sma20 + 1e-10)
    bb_pos   = (closes - bb_lower) / (bb_upper - bb_lower + 1e-10)

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd  = ema12 - ema26
    macd_signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
    macd_hist   = macd - macd_signal

    vol_sma20 = pd.Series(vols).rolling(20).mean().values
    vol_ratio = vols / (vol_sma20 + 1e-10)
    turn_sma20 = pd.Series(turns).rolling(20).mean().values

    ret1  = pd.Series(closes).pct_change(1).values
    ret3  = pd.Series(closes).pct_change(3).values
    ret7  = pd.Series(closes).pct_change(7).values
    ret14 = pd.Series(closes).pct_change(14).values

    mom5  = closes - pd.Series(closes).shift(5).values
    mom10 = closes - pd.Series(closes).shift(10).values

    low14  = pd.Series(lows).rolling(14).min().values
    high14 = pd.Series(highs).rolling(14).max().values
    stoch_k = (closes - low14) / (high14 - low14 + 1e-10) * 100

    # ─── 22 feature تقنية ───────────────────────────────────
    features = {
        'rsi14':      rsi14,
        'ema9_21':    (ema9 - ema21) / (closes + 1e-10),
        'ema21_50':   (ema21 - ema50) / (closes + 1e-10),
        'price_ema9': (closes - ema9) / (closes + 1e-10),
        'bb_pos':     bb_pos,
        'bb_width':   bb_width,
        'macd':       macd / (closes + 1e-10),
        'macd_hist':  macd_hist / (closes + 1e-10),
        'vol_ratio':  vol_ratio,
        'atr_pct':    atr14 / (closes + 1e-10),
        'ret1':       ret1,
        'ret3':       ret3,
        'ret7':       ret7,
        'ret14':      ret14,
        'mom5_pct':   mom5 / (closes + 1e-10),
        'mom10_pct':  mom10 / (closes + 1e-10),
        'stoch_k':    stoch_k / 100,
        'high_low_r': (highs - lows) / (closes + 1e-10),
        'close_high': (closes - highs) / (closes + 1e-10),
        'close_low':  (closes - lows) / (closes + 1e-10),
        'vol_change': pd.Series(vols).pct_change(1).values,
        'turnover_r': turns / (turn_sma20 + 1e-10),
    }

    # ─── 4 features من CoinGlass ────────────────────────────
    n = len(closes)
    oi_feat      = np.zeros(n)
    funding_feat = np.zeros(n)
    ls_feat      = np.full(n, 0.5)
    fg_feat      = np.full(n, 0.5)

    if 'ts' in df.columns:
        timestamps = df['ts'].values
        for i, ts in enumerate(timestamps):
            ts_unix = int(pd.Timestamp(ts).timestamp())
            ts_day  = ts_unix // 86400 * 86400

            if oi_map:
                oi_feat[i] = oi_map.get(ts_unix, oi_map.get(ts_unix - 3600, 0.0))
            if funding_map:
                funding_feat[i] = funding_map.get(ts_unix, funding_map.get(ts_unix - 3600, 0.0))
            if ls_map:
                ls_feat[i] = ls_map.get(ts_unix, ls_map.get(ts_unix - 3600, 0.5))
            if fg_map:
                fg_feat[i] = fg_map.get(ts_day, fg_map.get(ts_day - 86400, 0.5))

    features['oi_change']    = oi_feat
    features['funding_rate'] = funding_feat
    features['ls_ratio']     = ls_feat
    features['fear_greed']   = fg_feat

    df_feat = pd.DataFrame(features)
    return df_feat

# ─── بناء Labels ────────────────────────────────────────────
def build_labels(closes: np.ndarray, forward_bars: int = 4, min_gain: float = 0.015) -> np.ndarray:
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - forward_bars):
        future_max = closes[i+1:i+forward_bars+1].max()
        if (future_max - closes[i]) / closes[i] >= min_gain:
            labels[i] = 1
    return labels

# ─── جمع بيانات العملات الكبيرة (مع CoinGlass) ──────────────
def collect_major_symbols(exchange: str = 'Bybit', fetch_fn=None) -> Tuple[np.ndarray, np.ndarray]:
    logger.info(f"\n{'='*55}")
    logger.info(f"جمع بيانات العملات الكبيرة ({exchange}) مع CoinGlass")
    logger.info(f"{'='*55}")

    # Fear & Greed مرة واحدة
    fg_map = fetch_fear_greed(1000)

    all_X, all_y = [], []
    success = 0

    for i, sym in enumerate(MAJOR_SYMBOLS):
        logger.info(f"[{i+1}/{len(MAJOR_SYMBOLS)}] {sym}/USDT ({exchange})...")

        # OHLCV
        if fetch_fn == 'okx':
            df = fetch_okx_klines(sym, '1H', 1000)
        else:
            df = fetch_bybit_klines(sym, '60', 1000)

        if len(df) < 60:
            logger.debug(f"  {sym}: بيانات غير كافية")
            time.sleep(0.1)
            continue

        # CoinGlass (للعملات الكبيرة فقط)
        oi_map      = fetch_oi_history(sym, exchange, 500)
        funding_map = fetch_funding_history(sym, exchange, 200)
        ls_map      = fetch_ls_ratio(sym, exchange, 500)
        time.sleep(0.3)  # تجنب rate limit CoinGlass

        # بناء features
        feats = build_features_enhanced(df, oi_map, funding_map, ls_map, fg_map)
        if feats.empty:
            continue

        labels = build_labels(df['close'].values)
        min_len = min(len(feats), len(labels))
        feats = feats.iloc[:min_len]
        labels = labels[:min_len]

        valid = feats.notna().all(axis=1) & np.isfinite(feats.values).all(axis=1)
        feats = feats[valid]
        labels = labels[valid]

        if len(feats) < 20:
            continue

        all_X.append(feats.values)
        all_y.append(labels)
        success += 1

    if not all_X:
        return np.array([]), np.array([])

    X = np.vstack(all_X)
    y = np.concatenate(all_y)
    logger.info(f"✅ {exchange} كبيرة: {len(X):,} عينة من {success} عملة | {y.mean()*100:.1f}% إيجابي")
    return X, y

# ─── جمع بيانات العملات الحصرية على Bybit (بدون CoinGlass) ──
def collect_bybit_exclusive() -> Tuple[np.ndarray, np.ndarray]:
    logger.info(f"\n{'='*55}")
    logger.info("جمع بيانات العملات الحصرية على Bybit")
    logger.info(f"{'='*55}")

    fg_map = fetch_fear_greed(500)
    all_X, all_y = [], []
    success = 0

    for i, sym in enumerate(BYBIT_EXCLUSIVE):
        logger.info(f"[{i+1}/{len(BYBIT_EXCLUSIVE)}] {sym}/USDT (Bybit حصري)...")

        df_1h  = fetch_bybit_klines(sym, '60', 1000)
        df_15m = fetch_bybit_klines(sym, '15', 1000)
        time.sleep(0.2)

        for df in [df_1h, df_15m]:
            if len(df) < 60:
                continue
            # بدون CoinGlass (عملات صغيرة)
            feats = build_features_enhanced(df, fg_map=fg_map)
            if feats.empty:
                continue

            labels = build_labels(df['close'].values)
            min_len = min(len(feats), len(labels))
            feats = feats.iloc[:min_len]
            labels = labels[:min_len]

            valid = feats.notna().all(axis=1) & np.isfinite(feats.values).all(axis=1)
            feats = feats[valid]
            labels = labels[valid]

            if len(feats) < 20:
                continue

            all_X.append(feats.values)
            all_y.append(labels)
            success += 1

    if not all_X:
        return np.array([]), np.array([])

    X = np.vstack(all_X)
    y = np.concatenate(all_y)
    logger.info(f"✅ Bybit حصرية: {len(X):,} عينة من {success} مجموعة | {y.mean()*100:.1f}% إيجابي")
    return X, y

# ─── تدريب وحفظ النماذج ─────────────────────────────────────
def train_and_save(X: np.ndarray, y: np.ndarray, prefix: str, symbols: list) -> dict:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    import joblib

    logger.info(f"\n{'='*55}")
    logger.info(f"تدريب نماذج {prefix.upper()} — {len(X):,} عينة × {X.shape[1]} feature")
    logger.info(f"{'='*55}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    results = {}

    # Random Forest
    logger.info("[1/2] Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=15, min_samples_split=8,
        min_samples_leaf=4, class_weight='balanced', random_state=42, n_jobs=-1
    )
    rf.fit(X_train_s, y_train)
    rf_pred = rf.predict(X_test_s)
    rf_acc  = accuracy_score(y_test, rf_pred)
    rf_prec = precision_score(y_test, rf_pred, zero_division=0)
    rf_f1   = f1_score(y_test, rf_pred, zero_division=0)
    logger.info(f"  RF: Accuracy={rf_acc:.3f} | Precision={rf_prec:.3f} | F1={rf_f1:.3f}")
    results['rf'] = {'accuracy': rf_acc, 'precision': rf_prec, 'f1': rf_f1}

    # Gradient Boosting
    logger.info("[2/2] Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=200, max_depth=7, learning_rate=0.05,
        subsample=0.8, min_samples_split=8, random_state=42
    )
    gb.fit(X_train_s, y_train)
    gb_pred = gb.predict(X_test_s)
    gb_acc  = accuracy_score(y_test, gb_pred)
    gb_prec = precision_score(y_test, gb_pred, zero_division=0)
    gb_f1   = f1_score(y_test, gb_pred, zero_division=0)
    logger.info(f"  GB: Accuracy={gb_acc:.3f} | Precision={gb_prec:.3f} | F1={gb_f1:.3f}")
    results['gb'] = {'accuracy': gb_acc, 'precision': gb_prec, 'f1': gb_f1}

    # حفظ
    import joblib
    joblib.dump(rf,     f'{MODELS_DIR}/{prefix}_rf_model.pkl')
    joblib.dump(gb,     f'{MODELS_DIR}/{prefix}_gb_model.pkl')
    joblib.dump(scaler, f'{MODELS_DIR}/{prefix}_scaler.pkl')

    metadata = {
        'trained_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'n_samples': len(X), 'n_features': X.shape[1],
        'symbols': symbols, 'model_version': f'{prefix}_v2_enhanced',
        'data_sources': ['OHLCV', 'CoinGlass_OI', 'CoinGlass_Funding', 'CoinGlass_LS', 'FearGreed'],
        'results': results,
    }
    with open(f'{MODELS_DIR}/{prefix}_model_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ حُفظ: {prefix}_rf={rf_acc:.1%} | {prefix}_gb={gb_acc:.1%}")
    return results

# ─── الدالة الرئيسية ─────────────────────────────────────────
def main():
    start = time.time()
    logger.info("="*60)
    logger.info("🚀 بدء التدريب الشامل المحسّن (v2 Enhanced)")
    logger.info("   مصادر: OKX + Bybit + CoinGlass (OI+Funding+L/S) + Fear&Greed")
    logger.info("="*60)

    # ─── 1. نماذج OKX ───────────────────────────────────────
    logger.info("\n📊 المرحلة 1/3: جمع بيانات OKX (العملات الكبيرة + CoinGlass)...")
    X_okx_major, y_okx_major = collect_major_symbols('OKX', 'okx')

    # إضافة عملات OKX الحصرية (بدون CoinGlass)
    logger.info("\n📊 إضافة عملات OKX الإضافية...")
    OKX_EXTRA = ['PEPE', 'FLOKI', 'SHIB', 'BONK', 'WIF', 'MEME', 'ORDI', 'SATS',
                 'RATS', 'NAKA', 'MYRO', 'BOME', 'SLERF', 'PONKE', 'MOG', 'TURBO']
    fg_map = fetch_fear_greed(500)
    extra_X, extra_y = [], []
    for sym in OKX_EXTRA:
        df = fetch_okx_klines(sym, '1H', 800)
        if len(df) < 60:
            continue
        feats = build_features_enhanced(df, fg_map=fg_map)
        if feats.empty:
            continue
        labels = build_labels(df['close'].values)
        min_len = min(len(feats), len(labels))
        feats = feats.iloc[:min_len]
        labels = labels[:min_len]
        valid = feats.notna().all(axis=1) & np.isfinite(feats.values).all(axis=1)
        feats = feats[valid]; labels = labels[valid]
        if len(feats) >= 20:
            extra_X.append(feats.values)
            extra_y.append(labels)
        time.sleep(0.1)

    if extra_X and len(X_okx_major) > 0:
        X_okx = np.vstack([X_okx_major] + extra_X)
        y_okx = np.concatenate([y_okx_major] + extra_y)
    elif len(X_okx_major) > 0:
        X_okx, y_okx = X_okx_major, y_okx_major
    else:
        X_okx = np.vstack(extra_X) if extra_X else np.array([])
        y_okx = np.concatenate(extra_y) if extra_y else np.array([])

    if len(X_okx) > 0:
        train_and_save(X_okx, y_okx, 'okx', MAJOR_SYMBOLS + OKX_EXTRA)
    else:
        logger.error("❌ لا توجد بيانات OKX كافية!")

    # ─── 2. نماذج Bybit ─────────────────────────────────────
    logger.info("\n📊 المرحلة 2/3: جمع بيانات Bybit (كبيرة + حصرية + CoinGlass)...")
    X_bybit_major, y_bybit_major = collect_major_symbols('Bybit', 'bybit')
    X_bybit_excl,  y_bybit_excl  = collect_bybit_exclusive()

    if len(X_bybit_major) > 0 and len(X_bybit_excl) > 0:
        X_bybit = np.vstack([X_bybit_major, X_bybit_excl])
        y_bybit = np.concatenate([y_bybit_major, y_bybit_excl])
    elif len(X_bybit_major) > 0:
        X_bybit, y_bybit = X_bybit_major, y_bybit_major
    elif len(X_bybit_excl) > 0:
        X_bybit, y_bybit = X_bybit_excl, y_bybit_excl
    else:
        X_bybit, y_bybit = np.array([]), np.array([])

    if len(X_bybit) > 0:
        train_and_save(X_bybit, y_bybit, 'bybit', MAJOR_SYMBOLS + BYBIT_EXCLUSIVE)
    else:
        logger.error("❌ لا توجد بيانات Bybit كافية!")

    elapsed = time.time() - start
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ اكتمل التدريب الشامل في {elapsed/60:.1f} دقيقة")
    logger.info(f"{'='*60}")

if __name__ == '__main__':
    main()
