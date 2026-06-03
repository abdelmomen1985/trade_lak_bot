#!/usr/bin/env python3
"""
تدريب نماذج ML على البيانات التاريخية للعملات الحصرية على Bybit
يُنشئ نماذج مخصصة لـ Bybit منفصلة عن نماذج OKX
"""
import sys, os, time, json, logging, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/root/trade_lak_bot')

import requests
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/root/trade_lak_bot/logs/bybit_ml_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bybit_ml_trainer')

# ─── العملات الحصرية على Bybit ──────────────────────────────
BYBIT_EXCLUSIVE = [
    'MNT', 'BILL', 'H', 'VVV', 'BSB', 'HOLO', 'NVDAX', 'COINX', 'OPG', 'IO',
    'CRCLX', 'HOODX', 'DRIFT', 'FF', 'ICNT', 'XDC', 'NEWT', 'BLAST', 'AERO', 'NOM',
    'AZTEC', 'SPX', 'APEX', 'BOBA', 'KAS', 'VET', 'DEEP', 'AXL', 'BBSOL', 'BAN',
    'HFT', 'HOME', 'TSLAX', 'POPCAT', 'LUNC', 'VTHO', 'JASMY', 'PORTAL', 'ZIG',
]

BYBIT_BASE = 'https://api.bybit.com'
MODELS_DIR = '/root/trade_lak_bot/models'
os.makedirs(MODELS_DIR, exist_ok=True)

# ─── جلب الشموع من Bybit ────────────────────────────────────
def fetch_bybit_klines(symbol: str, interval: str = '60', limit: int = 1000) -> pd.DataFrame:
    """جلب بيانات OHLCV التاريخية من Bybit"""
    try:
        r = requests.get(
            f'{BYBIT_BASE}/v5/market/kline',
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

        # [timestamp, open, high, low, close, volume, turnover]
        df = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.astype({'ts': int, 'open': float, 'high': float, 'low': float,
                        'close': float, 'volume': float, 'turnover': float})
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.sort_values('ts').reset_index(drop=True)
        return df
    except Exception as e:
        logger.debug(f"خطأ جلب {symbol}: {e}")
        return pd.DataFrame()

# ─── بناء المؤشرات التقنية ───────────────────────────────────
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """بناء 22 feature تقنية متوافقة مع ml_model.py"""
    if len(df) < 50:
        return pd.DataFrame()

    closes = df['close'].values
    highs  = df['high'].values
    lows   = df['low'].values
    vols   = df['volume'].values

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

    # Bollinger Bands
    sma20 = pd.Series(closes).rolling(20).mean().values
    std20 = pd.Series(closes).rolling(20).std().values
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    bb_width = (bb_upper - bb_lower) / (sma20 + 1e-10)
    bb_pos   = (closes - bb_lower) / (bb_upper - bb_lower + 1e-10)

    # MACD
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd  = ema12 - ema26
    macd_signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
    macd_hist   = macd - macd_signal

    # Volume indicators
    vol_sma20 = pd.Series(vols).rolling(20).mean().values
    vol_ratio = vols / (vol_sma20 + 1e-10)

    # Price change features
    ret1  = pd.Series(closes).pct_change(1).values
    ret3  = pd.Series(closes).pct_change(3).values
    ret7  = pd.Series(closes).pct_change(7).values
    ret14 = pd.Series(closes).pct_change(14).values

    # Momentum
    mom5  = closes - pd.Series(closes).shift(5).values
    mom10 = closes - pd.Series(closes).shift(10).values

    # Stochastic
    low14  = pd.Series(lows).rolling(14).min().values
    high14 = pd.Series(highs).rolling(14).max().values
    stoch_k = (closes - low14) / (high14 - low14 + 1e-10) * 100

    features = pd.DataFrame({
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
        'turnover_r': df['turnover'].values / (df['turnover'].rolling(20).mean().values + 1e-10),
    })
    return features

# ─── بناء التسميات (Labels) ─────────────────────────────────
def build_labels(df: pd.DataFrame, forward_bars: int = 4, min_gain: float = 0.015) -> np.ndarray:
    """
    Label = 1 إذا ارتفع السعر > 1.5% خلال 4 شموع قادمة
    Label = 0 إذا لم يرتفع
    """
    closes = df['close'].values
    labels = np.zeros(len(closes), dtype=int)
    for i in range(len(closes) - forward_bars):
        future_max = closes[i+1:i+forward_bars+1].max()
        if (future_max - closes[i]) / closes[i] >= min_gain:
            labels[i] = 1
    return labels

# ─── جلب البيانات لجميع العملات ─────────────────────────────
def collect_all_data() -> Tuple[np.ndarray, np.ndarray]:
    all_X, all_y = [], []
    success_count = 0

    for i, symbol in enumerate(BYBIT_EXCLUSIVE):
        logger.info(f"[{i+1}/{len(BYBIT_EXCLUSIVE)}] جلب {symbol}/USDT من Bybit...")

        # جلب شموع 1 ساعة (1000 شمعة = ~42 يوم)
        df_1h = fetch_bybit_klines(symbol, '60', 1000)
        # جلب شموع 15 دقيقة (1000 شمعة = ~10 أيام)
        df_15m = fetch_bybit_klines(symbol, '15', 1000)

        for df, label in [(df_1h, '1H'), (df_15m, '15m')]:
            if len(df) < 60:
                logger.debug(f"  {symbol} {label}: بيانات غير كافية ({len(df)} شمعة)")
                continue

            feats = build_features(df)
            if feats.empty:
                continue

            labels = build_labels(df)

            # مزامنة الطول
            min_len = min(len(feats), len(labels))
            feats = feats.iloc[:min_len]
            labels = labels[:min_len]

            # إزالة NaN
            valid = feats.notna().all(axis=1) & np.isfinite(feats.values).all(axis=1)
            feats = feats[valid]
            labels = labels[valid]

            if len(feats) < 20:
                continue

            all_X.append(feats.values)
            all_y.append(labels)
            success_count += 1

        time.sleep(0.2)  # تجنب rate limit

    if not all_X:
        logger.error("لم يتم جلب أي بيانات!")
        return np.array([]), np.array([])

    X = np.vstack(all_X)
    y = np.concatenate(all_y)
    logger.info(f"✅ تم جمع {len(X):,} عينة من {success_count} مجموعة بيانات")
    logger.info(f"   توزيع Labels: {y.sum():,} إيجابي ({y.mean()*100:.1f}%) | {(1-y).sum():,} سلبي")
    return X, y

# ─── التدريب ─────────────────────────────────────────────────
def train_models(X: np.ndarray, y: np.ndarray):
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    import joblib

    logger.info(f"\n{'='*50}")
    logger.info("بدء تدريب نماذج Bybit الحصرية...")
    logger.info(f"{'='*50}")

    # تقسيم البيانات
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # تطبيع البيانات
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    results = {}

    # ─── Random Forest ──────────────────────────────────────
    logger.info("\n[1/2] تدريب Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train_s, y_train)
    rf_pred = rf.predict(X_test_s)
    rf_acc  = accuracy_score(y_test, rf_pred)
    rf_prec = precision_score(y_test, rf_pred, zero_division=0)
    rf_rec  = recall_score(y_test, rf_pred, zero_division=0)
    rf_f1   = f1_score(y_test, rf_pred, zero_division=0)
    logger.info(f"  Accuracy={rf_acc:.3f} | Precision={rf_prec:.3f} | Recall={rf_rec:.3f} | F1={rf_f1:.3f}")
    results['rf'] = {'accuracy': rf_acc, 'precision': rf_prec, 'recall': rf_rec, 'f1': rf_f1}

    # ─── Gradient Boosting ──────────────────────────────────
    logger.info("\n[2/2] تدريب Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_split=10,
        random_state=42
    )
    gb.fit(X_train_s, y_train)
    gb_pred = gb.predict(X_test_s)
    gb_acc  = accuracy_score(y_test, gb_pred)
    gb_prec = precision_score(y_test, gb_pred, zero_division=0)
    gb_rec  = recall_score(y_test, gb_pred, zero_division=0)
    gb_f1   = f1_score(y_test, gb_pred, zero_division=0)
    logger.info(f"  Accuracy={gb_acc:.3f} | Precision={gb_prec:.3f} | Recall={gb_rec:.3f} | F1={gb_f1:.3f}")
    results['gb'] = {'accuracy': gb_acc, 'precision': gb_prec, 'recall': gb_rec, 'f1': gb_f1}

    # ─── حفظ النماذج ────────────────────────────────────────
    logger.info("\nحفظ نماذج Bybit...")
    joblib.dump(rf,     f'{MODELS_DIR}/bybit_rf_model.pkl')
    joblib.dump(gb,     f'{MODELS_DIR}/bybit_gb_model.pkl')
    joblib.dump(scaler, f'{MODELS_DIR}/bybit_scaler.pkl')

    # حفظ metadata
    metadata = {
        'trained_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'n_samples': len(X),
        'n_features': X.shape[1],
        'symbols': BYBIT_EXCLUSIVE,
        'model_version': 'bybit_v1',
        'results': results,
    }
    with open(f'{MODELS_DIR}/bybit_model_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"\n{'='*50}")
    logger.info("✅ تم حفظ نماذج Bybit:")
    logger.info(f"  bybit_rf_model.pkl  — Accuracy: {rf_acc:.1%}")
    logger.info(f"  bybit_gb_model.pkl  — Accuracy: {gb_acc:.1%}")
    logger.info(f"  bybit_scaler.pkl    — StandardScaler")
    logger.info(f"{'='*50}")
    return results

# ─── الدالة الرئيسية ─────────────────────────────────────────
def main():
    start = time.time()
    logger.info("="*60)
    logger.info("🚀 بدء تدريب نماذج ML لعملات Bybit الحصرية")
    logger.info(f"   العملات: {len(BYBIT_EXCLUSIVE)} عملة حصرية")
    logger.info("="*60)

    # جلب البيانات
    X, y = collect_all_data()
    if len(X) == 0:
        logger.error("❌ فشل جلب البيانات — إيقاف التدريب")
        return

    # التدريب
    results = train_models(X, y)

    elapsed = time.time() - start
    logger.info(f"\n✅ اكتمل التدريب في {elapsed/60:.1f} دقيقة")
    logger.info(f"   Random Forest: {results['rf']['accuracy']:.1%} دقة")
    logger.info(f"   Gradient Boosting: {results['gb']['accuracy']:.1%} دقة")

if __name__ == '__main__':
    main()
