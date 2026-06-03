#!/usr/bin/env python3
"""
Bybit Scanner — وحدة مسح العملات الحصرية على Bybit
تعمل بالتوازي مع Trade Lak الرئيسي على OKX
تراقب العملات الموجودة على Bybit فقط وتبحث عن فرص تداول
"""
import time
import logging
import json
import os
import sys
import threading
import requests
from typing import Dict, List, Optional, Tuple

BOT_DIR = '/root/trade_lak_bot'
sys.path.insert(0, BOT_DIR)

logger = logging.getLogger('bybit_scanner')

# ─── العملات الحصرية على Bybit (حجم > $500K/يوم) ──────────
# مُحدَّثة تلقائياً من compare_exchanges.py
BYBIT_EXCLUSIVE_SYMBOLS = [
    'MNT', 'BILL', 'H', 'VVV', 'BSB', 'HOLO', 'NVDAX', 'COINX', 'OPG', 'IO',
    'CRCLX', 'HOODX', 'DRIFT', 'FF', 'ICNT', 'XDC', 'NEWT', 'BLAST', 'AERO', 'NOM',
    'AZTEC', 'SPX', 'APEX', 'BOBA', 'KAS', 'VET', 'DEEP', 'AXL', 'BBSOL', 'BAN',
    'HFT', 'HOME', 'TSLAX', 'POPCAT', 'LUNC', 'VTHO', 'JASMY', 'PORTAL', 'ZIG', 'STABLE'
]

# ─── إعدادات المسح ─────────────────────────────────────────
SCAN_INTERVAL = 30          # مسح كل 30 ثانية
MIN_VOLUME_24H = 500_000    # حجم تداول يومي أدنى $500K
MIN_SCORE = 6.0             # حد أدنى للـ Score للدخول
BYBIT_BASE_URL = 'https://api.bybit.com'

# ─── مؤشرات تقنية بسيطة ────────────────────────────────────
def calc_rsi(closes: List[float], period: int = 14) -> float:
    """حساب RSI"""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_ema(values: List[float], period: int) -> float:
    """حساب EMA"""
    if len(values) < period:
        return values[-1] if values else 0
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema

class BybitScanner:
    """
    يمسح العملات الحصرية على Bybit ويبحث عن فرص تداول
    يستخدم نماذج ML مخصصة لـ Bybit
    """
    MODELS_DIR = '/root/trade_lak_bot/models'

    def __init__(self, bybit_client, min_balance: float = 10.0):
        self.client = bybit_client
        self.min_balance = min_balance
        self._session = requests.Session()
        self._session.headers.update({'User-Agent': 'bybit-skill/1.4.1'})
        self._running = False
        self._thread = None
        self._last_scan_results = {}
        self._active_bybit_trades = {}  # symbol → trade info
        self._lock = threading.Lock()
        # تحميل نماذج ML الخاصة بـ Bybit
        self._rf_model = None
        self._gb_model = None
        self._scaler   = None
        self._ml_ready = False
        self._load_ml_models()

    def _load_ml_models(self):
        """تحميل نماذج ML المدرّبة على بيانات Bybit الحصرية"""
        try:
            import joblib
            rf_path  = f'{self.MODELS_DIR}/bybit_rf_model.pkl'
            gb_path  = f'{self.MODELS_DIR}/bybit_gb_model.pkl'
            sc_path  = f'{self.MODELS_DIR}/bybit_scaler.pkl'
            import os
            if all(os.path.exists(p) for p in [rf_path, gb_path, sc_path]):
                self._rf_model = joblib.load(rf_path)
                self._gb_model = joblib.load(gb_path)
                self._scaler   = joblib.load(sc_path)
                self._ml_ready = True
                logger.info('[Bybit Scanner] ✅ نماذج ML محمّلة (RF + GB)')
            else:
                logger.warning('[Bybit Scanner] ⚠️ نماذج ML غير موجودة — يعمل بدون ML')
        except Exception as e:
            logger.warning(f'[Bybit Scanner] ⚠️ خطأ تحميل ML: {e}')

    def _predict_ml(self, features_dict: dict) -> float:
        """تنبؤ ML — يُعيد احتمال الارتفاع (0.0 - 1.0)"""
        if not self._ml_ready:
            return 0.5
        try:
            import numpy as np
            feature_order = [
                'rsi14', 'ema9_21', 'ema21_50', 'price_ema9', 'bb_pos', 'bb_width',
                'macd', 'macd_hist', 'vol_ratio', 'atr_pct', 'ret1', 'ret3', 'ret7',
                'ret14', 'mom5_pct', 'mom10_pct', 'stoch_k', 'high_low_r',
                'close_high', 'close_low', 'vol_change', 'turnover_r'
            ]
            X = np.array([[features_dict.get(f, 0) for f in feature_order]])
            X_scaled = self._scaler.transform(X)
            rf_prob = self._rf_model.predict_proba(X_scaled)[0][1]
            gb_prob = self._gb_model.predict_proba(X_scaled)[0][1]
            return (rf_prob * 0.4 + gb_prob * 0.6)  # وزن أعلى لـ GB
        except Exception as e:
            logger.debug(f'[Bybit Scanner] خطأ ML predict: {e}')
            return 0.5

    def _get_klines(self, symbol: str, interval: str = '15', limit: int = 100) -> List:
        """جلب شموع Bybit"""
        try:
            sym = symbol + 'USDT'
            r = self._session.get(
                f'{BYBIT_BASE_URL}/v5/market/kline',
                params={'category': 'spot', 'symbol': sym, 'interval': interval, 'limit': limit},
                timeout=5
            )
            data = r.json()
            if data.get('retCode') == 0:
                # [timestamp, open, high, low, close, volume, turnover]
                return data.get('result', {}).get('list', [])
        except Exception as e:
            logger.debug(f"[Bybit] خطأ جلب شموع {symbol}: {e}")
        return []

    def _get_ticker(self, symbol: str) -> Optional[Dict]:
        """جلب ticker من Bybit"""
        try:
            sym = symbol + 'USDT'
            r = self._session.get(
                f'{BYBIT_BASE_URL}/v5/market/tickers',
                params={'category': 'spot', 'symbol': sym},
                timeout=3
            )
            data = r.json()
            if data.get('retCode') == 0:
                items = data.get('result', {}).get('list', [])
                if items:
                    return items[0]
        except Exception as e:
            logger.debug(f"[Bybit] خطأ ticker {symbol}: {e}")
        return None

    def _analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """تحليل عملة واحدة على Bybit"""
        try:
            # جلب ticker
            ticker = self._get_ticker(symbol)
            if not ticker:
                return None

            price = float(ticker.get('lastPrice', 0))
            volume_24h = float(ticker.get('turnover24h', 0))
            change_24h = float(ticker.get('price24hPcnt', 0)) * 100

            if price <= 0 or volume_24h < MIN_VOLUME_24H:
                return None

            # جلب شموع 15 دقيقة
            klines = self._get_klines(symbol, '15', 100)
            if len(klines) < 20:
                return None

            # استخراج الأسعار (الشموع مرتبة من الأحدث للأقدم)
            closes = [float(k[4]) for k in reversed(klines)]
            highs = [float(k[2]) for k in reversed(klines)]
            lows = [float(k[3]) for k in reversed(klines)]
            volumes = [float(k[5]) for k in reversed(klines)]

            # حساب المؤشرات
            rsi = calc_rsi(closes)
            ema20 = calc_ema(closes, 20)
            ema50 = calc_ema(closes, 50)
            avg_vol = sum(volumes[-20:]) / 20
            current_vol = volumes[-1]
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

            # حساب features لـ ML
            import numpy as np
            c = np.array(closes)
            h = np.array([float(k[2]) for k in reversed(klines)])
            l = np.array([float(k[3]) for k in reversed(klines)])
            v = np.array(volumes)
            t = np.array([float(k[6]) for k in reversed(klines)]) if len(klines[0]) > 6 else v * c
            ema9_arr  = calc_ema(closes, 9)
            ema21_arr = calc_ema(closes, 21)
            ema50_arr = calc_ema(closes, 50)
            sma20 = np.mean(c[-20:]) if len(c) >= 20 else c.mean()
            std20 = np.std(c[-20:]) if len(c) >= 20 else c.std()
            bb_upper = sma20 + 2*std20
            bb_lower = sma20 - 2*std20
            macd_val  = ema9_arr - ema21_arr
            atr_val   = np.mean(np.maximum(h[-14:]-l[-14:], np.abs(h[-14:]-c[-15:-1]))) if len(c) >= 15 else 0
            low14  = np.min(l[-14:]) if len(l) >= 14 else l.min()
            high14 = np.max(h[-14:]) if len(h) >= 14 else h.max()
            stoch_k = (c[-1]-low14)/(high14-low14+1e-10)
            vol_sma20 = np.mean(v[-20:]) if len(v) >= 20 else v.mean()
            t_sma20   = np.mean(t[-20:]) if len(t) >= 20 else t.mean()
            ml_features = {
                'rsi14':      rsi,
                'ema9_21':    (ema9_arr - ema21_arr) / (c[-1]+1e-10),
                'ema21_50':   (ema21_arr - ema50_arr) / (c[-1]+1e-10),
                'price_ema9': (c[-1] - ema9_arr) / (c[-1]+1e-10),
                'bb_pos':     (c[-1]-bb_lower)/(bb_upper-bb_lower+1e-10),
                'bb_width':   (bb_upper-bb_lower)/(sma20+1e-10),
                'macd':       macd_val/(c[-1]+1e-10),
                'macd_hist':  macd_val/(c[-1]+1e-10),
                'vol_ratio':  vol_ratio,
                'atr_pct':    atr_val/(c[-1]+1e-10),
                'ret1':       (c[-1]-c[-2])/(c[-2]+1e-10) if len(c)>=2 else 0,
                'ret3':       (c[-1]-c[-4])/(c[-4]+1e-10) if len(c)>=4 else 0,
                'ret7':       (c[-1]-c[-8])/(c[-8]+1e-10) if len(c)>=8 else 0,
                'ret14':      (c[-1]-c[-15])/(c[-15]+1e-10) if len(c)>=15 else 0,
                'mom5_pct':   (c[-1]-c[-6])/(c[-1]+1e-10) if len(c)>=6 else 0,
                'mom10_pct':  (c[-1]-c[-11])/(c[-1]+1e-10) if len(c)>=11 else 0,
                'stoch_k':    stoch_k,
                'high_low_r': (h[-1]-l[-1])/(c[-1]+1e-10),
                'close_high': (c[-1]-h[-1])/(c[-1]+1e-10),
                'close_low':  (c[-1]-l[-1])/(c[-1]+1e-10),
                'vol_change': (v[-1]-v[-2])/(v[-2]+1e-10) if len(v)>=2 else 0,
                'turnover_r': t[-1]/(t_sma20+1e-10),
            }
            ml_prob = self._predict_ml(ml_features)

            # حساب Score
            score = 5.0
            signals = []

            # RSI
            if 30 <= rsi <= 50:
                score += 1.0
                signals.append(f"RSI={rsi:.0f}✅")
            elif rsi < 30:
                score += 1.5
                signals.append(f"RSI={rsi:.0f}🔥")
            elif rsi > 70:
                score -= 1.0
                signals.append(f"RSI={rsi:.0f}⚠️")

            # EMA Trend
            if ema20 > ema50 and price > ema20:
                score += 1.0
                signals.append("EMA↑✅")
            elif price < ema50:
                score -= 0.5

            # Volume Surge
            if vol_ratio >= 2.0:
                score += 1.5
                signals.append(f"VOL×{vol_ratio:.1f}🔥")
            elif vol_ratio >= 1.5:
                score += 0.8
                signals.append(f"VOL×{vol_ratio:.1f}✅")

            # Price Change
            if 2 <= change_24h <= 15:
                score += 0.5
                signals.append(f"24h+{change_24h:.1f}%✅")
            elif change_24h > 15:
                score -= 0.5  # ربما متأخر
            elif change_24h < -10:
                score -= 1.0

            # ML Prediction (Bybit-specific models)
            if ml_prob >= 0.70:
                score += 2.0
                signals.append(f"ML={ml_prob:.0%}🤖🔥")
            elif ml_prob >= 0.55:
                score += 1.0
                signals.append(f"ML={ml_prob:.0%}🤖✅")
            elif ml_prob < 0.35:
                score -= 1.0
                signals.append(f"ML={ml_prob:.0%}🤖⚠️")

            return {
                'symbol': symbol,
                'price': price,
                'volume_24h': volume_24h,
                'change_24h': change_24h,
                'rsi': rsi,
                'ema20': ema20,
                'ema50': ema50,
                'vol_ratio': vol_ratio,
                'score': min(10.0, max(0.0, score)),
                'signals': signals,
            }
        except Exception as e:
            logger.debug(f"[Bybit] خطأ تحليل {symbol}: {e}")
            return None

    def scan_once(self) -> List[Dict]:
        """مسح واحد لجميع العملات الحصرية"""
        results = []
        for symbol in BYBIT_EXCLUSIVE_SYMBOLS:
            analysis = self._analyze_symbol(symbol)
            if analysis and analysis['score'] >= MIN_SCORE:
                results.append(analysis)
            time.sleep(0.1)  # تجنب rate limit

        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    def execute_bybit_trade(self, symbol: str, price: float, score: float) -> bool:
        """تنفيذ صفقة على Bybit"""
        if not self.client or not self.client.has_keys:
            logger.warning(f"[Bybit Scanner] لا توجد مفاتيح API للتداول")
            return False

        try:
            # جلب الرصيد
            balance = self.client.get_account_balance()
            usdt_balance = balance.get('USDT', 0) if balance else 0

            if usdt_balance < self.min_balance:
                logger.warning(f"[Bybit Scanner] رصيد غير كافٍ: ${usdt_balance:.2f}")
                return False

            # حجم الصفقة: 25% من الرصيد كحد أقصى 50 USDT
            trade_size = min(usdt_balance * 0.25, 50.0)
            if trade_size < self.min_balance:
                return False

            result = self.client.place_spot_order(
                symbol=f"{symbol}/USDT",
                side='Buy',
                qty=trade_size,
                market_unit='quoteCoin'
            )

            if result:
                order_id = result.get('orderId', '')
                logger.info(f"[Bybit Scanner] ✅ صفقة مفتوحة: {symbol}/USDT | ${trade_size:.2f} @ ${price:.6f} | Score: {score:.1f} | OrderID: {order_id}")
                with self._lock:
                    self._active_bybit_trades[symbol] = {
                        'entry_price': price,
                        'size_usdt': trade_size,
                        'score': score,
                        'time': time.time(),
                        'order_id': order_id,
                        'stop_loss': price * 0.98,   # -2%
                        'target1': price * 1.03,      # +3%
                        'target2': price * 1.05,      # +5%
                    }
                return True
        except Exception as e:
            logger.error(f"[Bybit Scanner] خطأ تنفيذ صفقة {symbol}: {e}")
        return False

    def _scan_loop(self):
        """حلقة المسح المستمرة"""
        logger.info(f"[Bybit Scanner] 🚀 بدأ المسح — {len(BYBIT_EXCLUSIVE_SYMBOLS)} عملة حصرية على Bybit")
        while self._running:
            try:
                opportunities = self.scan_once()
                with self._lock:
                    self._last_scan_results = {r['symbol']: r for r in opportunities}

                if opportunities:
                    top = opportunities[0]
                    logger.info(
                        f"[Bybit Scanner] أفضل فرصة: {top['symbol']}/USDT | "
                        f"Score={top['score']:.1f} | RSI={top['rsi']:.0f} | "
                        f"VOL×{top['vol_ratio']:.1f} | {' '.join(top['signals'])}"
                    )

                    # تنفيذ الصفقة إذا لم تكن مفتوحة مسبقاً
                    if (top['score'] >= 7.0 and
                            top['symbol'] not in self._active_bybit_trades and
                            self.client and self.client.has_keys):
                        self.execute_bybit_trade(top['symbol'], top['price'], top['score'])

            except Exception as e:
                logger.error(f"[Bybit Scanner] خطأ في المسح: {e}")

            time.sleep(SCAN_INTERVAL)

    def start(self):
        """تشغيل المسح في خيط منفصل"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="BybitScanner")
        self._thread.start()
        logger.info("[Bybit Scanner] ✅ تم التشغيل")

    def stop(self):
        self._running = False

    def get_top_opportunities(self, n: int = 5) -> List[Dict]:
        with self._lock:
            results = list(self._last_scan_results.values())
        return sorted(results, key=lambda x: x['score'], reverse=True)[:n]

    def update_symbols(self):
        """تحديث قائمة العملات الحصرية من Bybit ديناميكياً"""
        global BYBIT_EXCLUSIVE_SYMBOLS
        try:
            # جلب عملات OKX
            r_okx = requests.get('https://www.okx.com/api/v5/public/instruments?instType=SPOT', timeout=15)
            okx_coins = set()
            for item in r_okx.json().get('data', []):
                if item.get('quoteCcy') == 'USDT' and item.get('state') == 'live':
                    okx_coins.add(item.get('baseCcy', ''))

            # جلب عملات Bybit مع حجم التداول
            r_bybit = requests.get(f'{BYBIT_BASE_URL}/v5/market/tickers?category=spot', timeout=15)
            bybit_tickers = r_bybit.json().get('result', {}).get('list', [])

            EXCLUDED = {
                'USDC', 'BUSD', 'TUSD', 'DAI', 'FDUSD', 'USDP', 'USDD', 'USDG', 'RLUSD',
                'WBTC', 'WETH', 'WBNB', 'WMATIC', 'STETH', 'CBBTC', 'WEETH',
                'EUR', 'GBP', 'BRL', 'ARS', 'TRY', 'UAH',
                'SUSDE', 'USDE', 'PYUSD', 'GUSD', 'HUSD', 'LUSD', 'FRAX',
            }

            new_exclusive = []
            for t in bybit_tickers:
                sym = t.get('symbol', '')
                if not sym.endswith('USDT'):
                    continue
                base = sym[:-4]
                vol = float(t.get('turnover24h', 0) or 0)
                if base not in okx_coins and base not in EXCLUDED and vol >= MIN_VOLUME_24H:
                    new_exclusive.append(base)

            if new_exclusive:
                BYBIT_EXCLUSIVE_SYMBOLS = new_exclusive
                logger.info(f"[Bybit Scanner] ✅ تم تحديث القائمة: {len(new_exclusive)} عملة حصرية")
        except Exception as e:
            logger.warning(f"[Bybit Scanner] خطأ تحديث القائمة: {e}")


# ─── Singleton ─────────────────────────────────────────────
_scanner_instance: Optional[BybitScanner] = None

def get_bybit_scanner(bybit_client=None) -> Optional[BybitScanner]:
    global _scanner_instance
    if _scanner_instance is None and bybit_client is not None:
        _scanner_instance = BybitScanner(bybit_client)
    return _scanner_instance
