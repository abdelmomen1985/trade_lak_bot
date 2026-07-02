"""
Trade Lak — Breakout Signal System v4
نظام توصيات متكامل على قناة Trade Lak Signal

المسار الكامل:
  1. المرحلة 1 (1H): اختراق مقاومة + Volume قوي + OI يرتفع
     → يُحفظ في pending_breakouts (انتظار Retest)
  2. المرحلة 2 (Retest): السعر يرجع ويلمس مستوى الاختراق ويرتد منه
     → يُفعّل التأكيد الفني
  3. المرحلة 3 (تأكيد فني 15m + 5m): EMA + RSI + Volume + Funding + Liq
     → إرسال توصية الدخول على Trade Lak Signal

الرسائل المرسلة على Trade Lak Signal:
  📡 إشارة دخول مؤكدة — بعد اختراق + Retest + تأكيد فني
  ⚠️ إنذار سيولة — عند انخفاض OI أو تدهور الزخم بعد الدخول
  ✅/❌ نتيجة الإغلاق — عند وصول TP أو ضرب SL
"""

import requests
import logging
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── إعدادات ──────────────────────────────────────────────────────────────────
COINGLASS_API_KEY  = "eaf8efd7876142b0bac70affb6f65f2a"
TELEGRAM_BOT_TOKEN = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
SIGNAL_CHANNEL_ID  = "-1003834970832"   # Trade Lak Signal
COINGLASS_BASE     = "https://open-api.coinglass.com/public/v2"
OKX_BASE           = "https://www.okx.com/api/v5"

# ─── حدود المرحلة 1: الاختراق (1H) ──────────────────────────────────────────
RESISTANCE_LOOKBACK  = 24      # عدد الشموع للخلف لحساب المقاومة
BREAKOUT_CONFIRM_PCT = 0.003   # +0.3% فوق المقاومة
VOL_MULTIPLIER_MIN   = 1.5     # Volume أعلى من المتوسط بـ 1.5x
OI_RISE_MIN_H1       = 0.3     # OI ارتفع +0.3% في ساعة (مخفف للسوق الهابط)

# ─── حدود المرحلة 2: Retest ───────────────────────────────────────────────────
RETEST_TOUCH_PCT     = 0.008   # السعر يصل لمستوى الاختراق ±0.8%
RETEST_BOUNCE_PCT    = 0.003   # يرتد +0.3% من مستوى الـ Retest
RETEST_WINDOW_H      = 6       # نافذة انتظار الـ Retest (6 ساعات)
RETEST_MAX_CANDLES   = 12      # أقصى عدد شموع 30m للانتظار

# ─── حدود المرحلة 3: التأكيد الفني ───────────────────────────────────────────
RSI_MIN     = 50
RSI_MAX     = 75
EMA_FAST    = 20
EMA_SLOW    = 50
FUNDING_MAX = 0.01
VOL_15M_MIN = 1.2
LIQ_ABOVE_PCT = 0.005

# ─── مستويات الدخول ───────────────────────────────────────────────────────────
TP1_PCT = 0.03   # +3% — موحَّد
TP2_PCT = 0.06   # +6% — موحَّد
TP3_PCT = 0.08   # +8% — موحَّد (كان 10%)
SL_PCT  = 0.025  # 2.5% — موحَّد
MIN_SCORE_BREAKOUT  = 6   # حد أدنى لقوة الإشارة (كان 5)
SL_HIT_MEMORY_FILE  = "/root/trade_lak_bot/data/sl_hit_memory.json"
SL_HIT_MEMORY_HOURS = 48
SIGNALS_ACTIVE_FILE = "/root/trade_lak_bot/data/signal_channel_active.json"

# ─── إنذار السيولة ────────────────────────────────────────────────────────────
LIQ_WARN_OI_DROP    = -3.0
LIQ_WARN_VOL_DROP   = 0.3
LIQ_WARN_RSI_DROP   = 38
LIQ_WARN_COOLDOWN   = 12 * 60 * 60  # 12 ساعة

COOLDOWN_HOURS = 4
STATE_FILE = "/root/trade_lak_bot/breakout_state.json"

# ─── قائمة العملات ────────────────────────────────────────────────────────────
SECTORS = {
    "Layer1":         ["BTC", "ETH", "SOL", "ADA", "AVAX", "DOT", "ATOM", "NEAR", "APT", "SUI", "ICP", "HBAR", "TON"],
    "Layer2":         ["POL", "ARB", "OP", "LRC", "IMX"],
    "DeFi":           ["UNI", "AAVE", "DYDX", "GMX", "PENDLE"],
    "Meme":           ["DOGE", "PEPE", "FLOKI", "WIF"],
    "AI_Data":        ["FET", "RENDER", "GRT", "WLD"],
    "Infrastructure": ["LINK", "FIL"],
    "Exchange":       ["BNB", "OKB"],
    "Other":          ["XRP", "LTC", "TRX"],
}
COIN_SECTOR = {coin: s for s, coins in SECTORS.items() for coin in coins}

WATCH_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT",
    "LINK", "UNI", "ATOM", "NEAR", "APT", "SUI", "ARB", "OP", "PEPE",
    "FIL", "LTC", "TRX", "ICP", "AAVE", "HBAR", "TON", "WIF", "INJ",
]


# ─── أدوات مساعدة ─────────────────────────────────────────────────────────────
def format_price(price: float) -> str:
    if price is None: return "—"
    if price >= 1000:   return f"{price:,.2f}"
    elif price >= 1:    return f"{price:.4f}"
    elif price >= 0.01: return f"{price:.5f}"
    else:               return f"{price:.8f}"

def format_pct(pct: float) -> str:
    return f"{pct:+.2f}%"

def calc_ema(values: List[float], period: int) -> List[float]:
    if len(values) < period: return []
    k = 2 / (period + 1)
    ema = [sum(values[:period]) / period]
    for v in values[period:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema

def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1: return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    if not losses: return 100.0
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


class BreakoutSignalSystem:

    def __init__(self):
        self.cg_headers = {}  # Coinglass معطّل — نستخدم OKX API مباشرة
        self.state = self._load_state()
        logger.info("✅ Breakout Signal System v4 initialized (with Retest confirmation)")

    # ─── State ────────────────────────────────────────────────────────────────
    def _load_state(self) -> Dict:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"open_signals": {}, "pending_breakouts": {}}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"State save error: {e}")

    def _get_open_signals(self) -> Dict:
        return self.state.get("open_signals", {})

    def _get_pending_breakouts(self) -> Dict:
        return self.state.get("pending_breakouts", {})

    def _add_pending_breakout(self, symbol: str, p1: Dict):
        if "pending_breakouts" not in self.state:
            self.state["pending_breakouts"] = {}
        self.state["pending_breakouts"][symbol] = {
            "symbol": symbol,
            "sector": p1['sector'],
            "breakout_price": p1['price'],
            "resistance": p1['resistance'],
            "breakout_pct": p1['breakout_pct'],
            "vol_ratio_1h": p1['vol_ratio_1h'],
            "vol_usdt_1h": p1['vol_usdt_1h'],
            "avg_vol_1h": p1['avg_vol_1h'],
            "h1_oi_chg": p1['h1_oi_chg'],
            "oi_total": p1['oi_total'],
            "touches": p1['touches'],
            "breakout_time": time.time(),
            "retest_low": p1['price'],   # أدنى سعر وصل إليه بعد الاختراق
        }
        self._save_state()

    def _remove_pending_breakout(self, symbol: str):
        if "pending_breakouts" in self.state and symbol in self.state["pending_breakouts"]:
            del self.state["pending_breakouts"][symbol]
            self._save_state()

    def _add_open_signal(self, symbol: str, entry: float, tp1: float, tp2: float, tp3: float, sl: float):
        if "open_signals" not in self.state:
            self.state["open_signals"] = {}
        self.state["open_signals"][symbol] = {
            "entry": entry, "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl,
            "entry_time": time.time(),
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "liq_warned": False,
            "last_liq_warn": 0,
        }
        self._save_state()

    def _remove_open_signal(self, symbol: str):
        if "open_signals" in self.state and symbol in self.state["open_signals"]:
            del self.state["open_signals"][symbol]
            self._save_state()

    def _record_sl_hit(self, symbol: str, sl_price: float):
        """تسجيل ضربة SL في ذاكرة مشتركة للتنويه بإعادة الدخول لاحقاً"""
        try:
            memory = {}
            if os.path.exists(SL_HIT_MEMORY_FILE):
                with open(SL_HIT_MEMORY_FILE) as f:
                    memory = json.load(f)
            key = f"{symbol}/USDT"
            memory[key] = {"time": time.time(), "sl_price": sl_price}
            cutoff = time.time() - (SL_HIT_MEMORY_HOURS * 3600)
            memory = {k: v for k, v in memory.items() if v.get("time", 0) > cutoff}
            with open(SL_HIT_MEMORY_FILE, "w") as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
            logger.info(f"📝 [{key}] سُجِّل في sl_hit_memory.json")
        except Exception as e:
            logger.error(f"خطأ في _record_sl_hit: {e}")

    def _is_signal_active(self, symbol: str) -> bool:
        """فحص إذا كانت العملة لها إشارة مفتوحة في signal_channel_active.json"""
        try:
            if os.path.exists(SIGNALS_ACTIVE_FILE):
                with open(SIGNALS_ACTIVE_FILE) as f:
                    active = json.load(f)
                return f"{symbol}/USDT" in active or symbol in active
        except Exception:
            pass
        return False

    def _get_reentry_info(self, symbol: str):
        """فحص إذا كانت العملة ضربت SL مؤخراً"""
        try:
            if os.path.exists(SL_HIT_MEMORY_FILE):
                with open(SL_HIT_MEMORY_FILE) as f:
                    memory = json.load(f)
                key = f"{symbol}/USDT"
                if key in memory:
                    hours = (time.time() - memory[key].get("time", 0)) / 3600
                    return {"hours_since": hours, "sl_price": memory[key].get("sl_price", 0)}
        except Exception:
            pass
        return None

    # ─── جلب البيانات ─────────────────────────────────────────────────────────
    def _get_candles(self, symbol: str, bar: str = "1H", limit: int = 60) -> Optional[List[Dict]]:
        try:
            r = requests.get(
                f"{OKX_BASE}/market/candles",
                params={'instId': f"{symbol}-USDT", 'bar': bar, 'limit': str(limit)},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                return [{
                    'ts': int(c[0]), 'open': float(c[1]), 'high': float(c[2]),
                    'low': float(c[3]), 'close': float(c[4]),
                    'vol': float(c[5]), 'vol_usdt': float(c[7]),
                } for c in data['data']]
        except Exception as e:
            logger.error(f"Candles {symbol}/{bar}: {e}")
        return None

    def _get_current_price(self, symbol: str) -> Optional[float]:
        try:
            r = requests.get(
                f"{OKX_BASE}/market/ticker",
                params={'instId': f"{symbol}-USDT"},
                timeout=8
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                return float(data['data'][0]['last'])
        except Exception:
            pass
        return None

    def _get_oi_data(self, symbol: str) -> Optional[Dict]:
        """جلب Open Interest من OKX مباشرة (بدون Coinglass)"""
        try:
            # OI الحالي
            r = requests.get(
                f"{OKX_BASE}/public/open-interest",
                params={'instType': 'SWAP', 'instId': f"{symbol}-USDT-SWAP"},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                oi_now = float(data['data'][0].get('oiCcy', 0) or 0)
            else:
                return None

            # OI قبل ساعة (من تاريخ الشموع)
            r2 = requests.get(
                f"{OKX_BASE}/market/candles",
                params={'instId': f"{symbol}-USDT-SWAP", 'bar': '1H', 'limit': '3'},
                timeout=10
            )
            data2 = r2.json()
            oi_1h_ago = oi_now
            if data2.get('code') == '0' and data2.get('data') and len(data2['data']) >= 2:
                # نستخدم volume كمؤشر بديل لتغير OI
                vol_now  = float(data2['data'][0][5] or 0)
                vol_prev = float(data2['data'][1][5] or 0)
                if vol_prev > 0:
                    vol_change = (vol_now - vol_prev) / vol_prev * 100
                    # تقدير تغير OI بناءً على Volume
                    oi_chg_est = vol_change * 0.3  # تقريبي
                else:
                    oi_chg_est = 0.0
            else:
                oi_chg_est = 0.0

            # جلب تغير OI الفعلي من endpoint مخصص
            r3 = requests.get(
                f"{OKX_BASE}/rubik/stat/contracts/open-interest-volume",
                params={'ccy': symbol, 'period': '1H'},
                timeout=10
            )
            data3 = r3.json()
            if data3.get('code') == '0' and data3.get('data') and len(data3['data']) >= 2:
                oi_recent = float(data3['data'][0][1] or 0)
                oi_prev   = float(data3['data'][1][1] or 0)
                if oi_prev > 0:
                    oi_chg_est = (oi_recent - oi_prev) / oi_prev * 100

            return {
                'openInterest': oi_now,
                'h1OIChangePercent': oi_chg_est,
            }
        except Exception as e:
            logger.error(f"OI {symbol}: {e}")
        return None

    def _get_funding_rate(self, symbol: str) -> float:
        """جلب Funding Rate من OKX مباشرة (بدون Coinglass)"""
        try:
            r = requests.get(
                f"{OKX_BASE}/public/funding-rate",
                params={'instId': f"{symbol}-USDT-SWAP"},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                return float(data['data'][0].get('fundingRate', 0) or 0)
        except Exception as e:
            logger.debug(f"Funding {symbol}: {e}")
        return 0.0

    def _get_liquidation_heatmap(self, symbol: str, current_price: float) -> Dict:
        """تقدير مناطق السيولة من Order Book (بدون Coinglass)"""
        result = {'liq_above': 0.0, 'liq_below': 0.0, 'has_liq_above': False}
        try:
            r = requests.get(
                f"{OKX_BASE}/market/books",
                params={'instId': f"{symbol}-USDT", 'sz': '20'},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                book = data['data'][0]
                asks = book.get('asks', [])  # [price, size, ...]
                bids = book.get('bids', [])
                # تجميع السيولة فوق وتحت السعر الحالي
                liq_above = sum(float(a[1]) * float(a[0]) for a in asks
                                if float(a[0]) > current_price * (1 + LIQ_ABOVE_PCT))
                liq_below = sum(float(b[1]) * float(b[0]) for b in bids
                                if float(b[0]) < current_price * (1 - LIQ_ABOVE_PCT))
                result['liq_above'] = liq_above
                result['liq_below'] = liq_below
                result['has_liq_above'] = liq_above > liq_below * 0.5
        except Exception as e:
            logger.debug(f"Order book {symbol}: {e}")
        return result

    # ─── التحليل الفني ────────────────────────────────────────────────────────
    def _analyze_technical(self, symbol: str, bar: str) -> Optional[Dict]:
        candles = self._get_candles(symbol, bar=bar, limit=70)
        if not candles or len(candles) < EMA_SLOW + 5:
            return None
        closes = [c['close'] for c in reversed(candles)]
        vols   = [c['vol_usdt'] for c in reversed(candles)]
        ema_fast_s = calc_ema(closes, EMA_FAST)
        ema_slow_s = calc_ema(closes, EMA_SLOW)
        if not ema_fast_s or not ema_slow_s:
            return None
        ema_fast = ema_fast_s[-1]
        ema_slow = ema_slow_s[-1]
        rsi = calc_rsi(closes[-30:], 14)
        current_vol = vols[-1]
        avg_vol = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else current_vol
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        return {
            'bar': bar, 'close': closes[-1],
            'ema_fast': ema_fast, 'ema_slow': ema_slow,
            'ema_bullish': ema_fast > ema_slow,
            'rsi': rsi, 'vol_ratio': vol_ratio,
            'current_vol': current_vol, 'avg_vol': avg_vol,
        }

    # ─── المرحلة 1: كشف الاختراق ──────────────────────────────────────────────
    def _phase1_breakout(self, symbol: str) -> Optional[Dict]:
        candles_1h = self._get_candles(symbol, bar="1H", limit=50)
        if not candles_1h or len(candles_1h) < RESISTANCE_LOOKBACK + 2:
            return None
        oi_data = self._get_oi_data(symbol)
        current = candles_1h[0]
        current_price = current['close']
        current_vol_usdt = current['vol_usdt']
        lookback = candles_1h[1:RESISTANCE_LOOKBACK + 1]
        highs = [c['high'] for c in lookback]
        resistance = max(highs)
        touches = sum(1 for h in highs if abs(h - resistance) / resistance < 0.005)
        breakout_pct = (current_price - resistance) / resistance
        if breakout_pct < BREAKOUT_CONFIRM_PCT:
            return None
        avg_vol = sum(c['vol_usdt'] for c in candles_1h[1:21]) / 20
        vol_ratio = current_vol_usdt / avg_vol if avg_vol > 0 else 0
        if vol_ratio < VOL_MULTIPLIER_MIN:
            return None
        h1_oi_chg = 0.0
        oi_total = 0.0
        if oi_data:
            h1_oi_chg = float(oi_data.get('h1OIChangePercent', 0) or 0)
            oi_total  = float(oi_data.get('openInterest', 0) or 0)
        if h1_oi_chg < OI_RISE_MIN_H1:
            return None
        low_4h = min(c['low'] for c in candles_1h[:4])
        rise_from_low = ((current_price - low_4h) / low_4h) * 100
        return {
            'symbol': symbol, 'sector': COIN_SECTOR.get(symbol, 'Other'),
            'price': current_price, 'resistance': resistance,
            'breakout_pct': breakout_pct * 100, 'vol_ratio_1h': vol_ratio,
            'vol_usdt_1h': current_vol_usdt, 'avg_vol_1h': avg_vol,
            'h1_oi_chg': h1_oi_chg, 'oi_total': oi_total,
            'touches': touches, 'rise_from_low': rise_from_low,
        }

    # ─── المرحلة 2: فحص Retest ────────────────────────────────────────────────
    def _check_retest(self, symbol: str, pending: Dict) -> Optional[Dict]:
        """
        فحص إذا حصل Retest ناجح:
        - السعر رجع ولمس مستوى الاختراق (±RETEST_TOUCH_PCT)
        - ثم ارتد منه بـ +RETEST_BOUNCE_PCT على الأقل
        - بدون كسر مستوى الاختراق للأسفل
        """
        resistance = pending['resistance']
        breakout_price = pending['breakout_price']
        breakout_time = pending['breakout_time']

        # فحص انتهاء نافذة الانتظار
        elapsed_h = (time.time() - breakout_time) / 3600
        if elapsed_h > RETEST_WINDOW_H:
            logger.info(f"⏰ {symbol}: Retest window expired ({elapsed_h:.1f}h > {RETEST_WINDOW_H}h) — removing pending")
            return None  # None يعني انتهت الفرصة

        # جلب شموع 30 دقيقة منذ الاختراق
        candles_30m = self._get_candles(symbol, bar="30m", limit=RETEST_MAX_CANDLES + 2)
        if not candles_30m:
            return {"status": "waiting"}

        current_price = candles_30m[0]['close']
        retest_zone_high = resistance * (1 + RETEST_TOUCH_PCT)
        retest_zone_low  = resistance * (1 - RETEST_TOUCH_PCT)

        # البحث عن لمسة للـ Retest zone ثم ارتداد
        retest_low_seen = None
        for c in candles_30m[1:]:  # تخطي الشمعة الحالية
            low  = c['low']
            high = c['high']
            # هل لمس مستوى الاختراق؟
            if retest_zone_low <= low <= retest_zone_high or retest_zone_low <= high <= retest_zone_high:
                if retest_low_seen is None or low < retest_low_seen:
                    retest_low_seen = low

        if retest_low_seen is None:
            # لم يصل للـ Retest zone بعد
            return {"status": "waiting", "current_price": current_price}

        # هل كسر مستوى الاختراق للأسفل؟ (فشل الـ Retest)
        if retest_low_seen < resistance * (1 - RETEST_TOUCH_PCT * 2):
            logger.info(f"❌ {symbol}: Retest failed — price broke below resistance ({format_price(retest_low_seen)} < {format_price(resistance)})")
            return None  # None يعني فشل الـ Retest

        # هل ارتد بشكل كافٍ؟
        bounce_pct = (current_price - retest_low_seen) / retest_low_seen
        if bounce_pct >= RETEST_BOUNCE_PCT:
            logger.info(f"✅ {symbol}: Retest confirmed! Low={format_price(retest_low_seen)} Current={format_price(current_price)} Bounce={bounce_pct*100:.2f}%")
            return {
                "status": "confirmed",
                "current_price": current_price,
                "retest_low": retest_low_seen,
                "bounce_pct": bounce_pct * 100,
                "retest_level": resistance,
            }

        # لمس الـ Retest zone لكن لم يرتد بعد
        return {"status": "waiting", "current_price": current_price, "retest_low_seen": retest_low_seen}

    # ─── المرحلة 3: تأكيد فني ─────────────────────────────────────────────────
    def _phase3_confirm(self, symbol: str, current_price: float) -> Optional[Dict]:
        tf_15m = self._analyze_technical(symbol, "15m")
        time.sleep(0.3)
        tf_5m  = self._analyze_technical(symbol, "5m")
        if not tf_15m or not tf_5m:
            return None
        funding = self._get_funding_rate(symbol)
        liq = self._get_liquidation_heatmap(symbol, current_price)
        checks = {
            'ema_15m': {'met': tf_15m['ema_bullish'], 'icon': '✅' if tf_15m['ema_bullish'] else '❌'},
            'ema_5m':  {'met': tf_5m['ema_bullish'],  'icon': '✅' if tf_5m['ema_bullish']  else '❌'},
            'rsi_15m': {'met': RSI_MIN <= tf_15m['rsi'] <= RSI_MAX, 'icon': '✅' if RSI_MIN <= tf_15m['rsi'] <= RSI_MAX else '❌'},
            'rsi_5m':  {'met': RSI_MIN <= tf_5m['rsi']  <= RSI_MAX, 'icon': '✅' if RSI_MIN <= tf_5m['rsi']  <= RSI_MAX else '❌'},
            'vol_15m': {'met': tf_15m['vol_ratio'] >= VOL_15M_MIN,  'icon': '✅' if tf_15m['vol_ratio'] >= VOL_15M_MIN else '❌'},
            'funding': {'met': abs(funding) <= FUNDING_MAX,          'icon': '✅' if abs(funding) <= FUNDING_MAX else '❌'},
            'liq_above': {'met': liq['has_liq_above'],               'icon': '✅' if liq['has_liq_above'] else '⚠️'},
        }
        ema_ok = checks['ema_15m']['met'] and checks['ema_5m']['met']
        rsi_ok = checks['rsi_15m']['met'] or checks['rsi_5m']['met']
        met_count = sum(1 for c in checks.values() if c['met'])
        confirmed = ema_ok and rsi_ok and met_count >= MIN_SCORE_BREAKOUT
        return {
            'confirmed': confirmed, 'met_count': met_count,
            'checks': checks, 'tf_15m': tf_15m, 'tf_5m': tf_5m,
            'funding': funding, 'liq': liq,
        }

    # ─── صيغة رسالة الدخول ────────────────────────────────────────────────────
    def _format_entry_signal(self, pending: Dict, retest: Dict, p3: Dict,
                              entry: float, tp1: float, tp2: float, tp3: float, sl: float) -> str:
        now = datetime.now()
        symbol = pending['symbol']
        liq = p3['liq']
        # نقطة الدخول: عند مستوى الاختراق (الذي أصبح دعمًا بعد الاختراق)
        # الدخول المثالي: عند لمس مستوى المقاومة المخترقة (Retest level) وتأكيد الارتداد
        retest_level = retest['retest_level']        # مستوى المقاومة المخترقة = أدنى نقطة دخول
        entry_low  = retest_level                    # عند لمس مستوى الاختراق (الدخول الأمثل)
        entry_high = retest_level * 1.005            # +0.5% فوق مستوى الاختراق (تأكيد الارتداد)
        # وقف الخسارة الذكي: تحت أدنى نقطة Retest مع هامش يتجنب الذيول
        # يُراعي السيولة: إذا وجدت تصفيات تحت السعر نُبعد SL أكثر
        liq_buffer = 0.005 if liq['liq_below'] > liq['liq_above'] * 0.5 else 0.003
        sl_raw = retest['retest_low'] * (1 - liq_buffer)
        sl_pct_actual = ((entry - sl_raw) / entry) * 100
        # التأكد أن SL بين 1-2%
        if sl_pct_actual < 1.0:
            sl_raw = entry * 0.990   # -1%
            sl_pct_actual = 1.0
        elif sl_pct_actual > 2.0:
            sl_raw = entry * 0.980   # -2%
            sl_pct_actual = 2.0
        # الأهداف: موحَّدة TP1=3%, TP2=6%, TP3=8%
        tp1_pct = TP1_PCT   # 3%
        tp2_pct = TP2_PCT   # 6%
        tp3_pct = TP3_PCT   # 8%
        tp1_price = entry * (1 + tp1_pct)
        tp2_price = entry * (1 + tp2_pct)
        tp3_price = entry * (1 + tp3_pct)
        rr = tp2_pct / (sl_pct_actual / 100)
        score = p3['met_count']
        stars = "⭐" * min(score - 3, 4)
        liq_sl_note = "(تم تعديله بناءً على خريطة السيولة)" if liq['liq_below'] > 0 else ""
        return f"""📡 <b>إشارة دخول</b>  |  <b>{symbol}/USDT</b>
━━━━━━━━━━━━━━━━━━━━━
💰 <b>السعر الحالي:</b>  {format_price(entry)}

📥 <b>نقطة الدخول:</b>  {format_price(entry_low)} — {format_price(entry_high)}

🎯 <b>الهدف الأول:</b>   {format_price(tp1_price)}  <i>(+{tp1_pct*100:.1f}%)</i>
🎯 <b>الهدف الثاني:</b>  {format_price(tp2_price)}  <i>(+{tp2_pct*100:.1f}%)</i>
🎯 <b>الهدف الثالث:</b>  {format_price(tp3_price)}  <i>(+{tp3_pct*100:.1f}%)</i>

🛑 <b>وقف الخسارة:</b>  {format_price(sl_raw)}  <i>(-{sl_pct_actual:.1f}%)</i>  {liq_sl_note}
⚖️ <b>نسبة المخاطرة:</b>  1:{rr:.1f}
━━━━━━━━━━━━━━━━━━━━━
{stars}  قوة الإشارة ({score}/7)
━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>هذه الإشارة لأهداف تعليمية وليست نصيحة استثمارية بالبيع أو الشراء</i>
━━━━━━━━━━━━━━━━━━━━━
🕐 {now.strftime('%H:%M')}  |  📅 {now.strftime('%Y-%m-%d')}"""

    # ─── إنذار انخفاض السيولة ─────────────────────────────────────────────────
    def _format_liquidity_warning(self, symbol: str, sig: Dict, current_price: float,
                                   oi_chg: float, vol_ratio: float, rsi_5m: float,
                                   pnl_pct: float) -> str:
        now = datetime.now()
        entry = sig['entry']
        reasons = []
        if oi_chg <= LIQ_WARN_OI_DROP:
            reasons.append(f"OI انخفض {oi_chg:+.2f}% في ساعة")
        if vol_ratio <= LIQ_WARN_VOL_DROP:
            reasons.append(f"Volume ضعيف ({vol_ratio:.1f}x المتوسط)")
        if rsi_5m <= LIQ_WARN_RSI_DROP:
            reasons.append(f"RSI (5m) انخفض إلى {rsi_5m:.1f}")
        reasons_text = "\n  ⚠️ ".join(reasons)
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"
        return f"""⚠️ <b>إنذار — انخفاض السيولة</b>
━━━━━━━━━━━━━━━━━━━━━
💎 <b>{symbol}/USDT</b>
━━━━━━━━━━━━━━━━━━━━━
{pnl_icon} السعر الحالي: <b>{format_price(current_price)}</b>  ({pnl_pct:+.2f}%)
💰 سعر الدخول: {format_price(entry)}
━━━━━━━━━━━━━━━━━━━━━
🚨 <b>أسباب الإنذار:</b>
  ⚠️ {reasons_text}
━━━━━━━━━━━━━━━━━━━━━
💡 <b>يُنصح بمراجعة الصفقة أو تضييق SL لحماية الأرباح</b>
━━━━━━━━━━━━━━━━━━━━━
🕐 {now.strftime('%H:%M:%S')}  |  📅 {now.strftime('%Y-%m-%d')}"""

    # ─── نتيجة الإغلاق ────────────────────────────────────────────────────────
    def _format_close_result(self, symbol: str, sig: Dict, current_price: float,
                              close_reason: str) -> str:
        now = datetime.now()
        entry = sig['entry']
        pnl_pct = ((current_price - entry) / entry) * 100
        duration_h = (time.time() - sig['entry_time']) / 3600
        if close_reason == 'SL':
            icon = "❌"
            title = "صفقة خاسرة — ضُرب وقف الخسارة"
            result_line = f"🛑 <b>SL:</b> {format_price(sig['sl'])} | خسارة: <b>{pnl_pct:.2f}%</b>"
        elif close_reason == 'TP3':
            icon = "🏆"
            title = "صفقة رابحة — وصل TP3"
            result_line = f"🎯 <b>TP3 محقق:</b> {format_price(sig['tp3'])} | ربح: <b>+{pnl_pct:.2f}%</b>"
        elif close_reason == 'TP2':
            icon = "✅"
            title = "صفقة رابحة — وصل TP2"
            result_line = f"🎯 <b>TP2 محقق:</b> {format_price(sig['tp2'])} | ربح: <b>+{pnl_pct:.2f}%</b>"
        else:
            icon = "✅"
            title = "صفقة رابحة — وصل TP1"
            result_line = f"🎯 <b>TP1 محقق:</b> {format_price(sig['tp1'])} | ربح: <b>+{pnl_pct:.2f}%</b>"
        return f"""{icon} <b>{title}</b>
━━━━━━━━━━━━━━━━━━━━━
💎 <b>{symbol}/USDT</b>
━━━━━━━━━━━━━━━━━━━━━
💰 دخول: {format_price(entry)}
{result_line}
⏱ مدة الصفقة: {duration_h:.1f} ساعة
━━━━━━━━━━━━━━━━━━━━━
🕐 {now.strftime('%H:%M:%S')}  |  📅 {now.strftime('%Y-%m-%d')}"""

    # ─── Telegram ─────────────────────────────────────────────────────────────
    def _send_telegram(self, message: str) -> bool:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": SIGNAL_CHANNEL_ID, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    def _should_send_entry(self, symbol: str) -> bool:
        # فحص 1: Cooldown
        last = self.state.get(f"{symbol}_signal", 0)
        if (time.time() - last) <= (COOLDOWN_HOURS * 3600):
            return False
        # فحص 2: هل للعملة إشارة مفتوحة بالفعل في القناة
        if self._is_signal_active(symbol):
            logger.info(f"⏭️ {symbol}: لها إشارة مفتوحة بالفعل — لن تُرسل إشارة جديدة")
            return False
        return True

    def _mark_entry_sent(self, symbol: str):
        self.state[f"{symbol}_signal"] = time.time()
        self._save_state()

    # ─── مراقبة الصفقات المفتوحة ──────────────────────────────────────────────
    def _monitor_open_signals(self):
        """مراقبة التوصيات المفتوحة: TP / SL / إنذار السيولة"""
        open_signals = self._get_open_signals()
        if not open_signals:
            return

        to_close = []

        for symbol, sig in open_signals.items():
            try:
                current_price = self._get_current_price(symbol)
                if not current_price:
                    continue

                entry = sig['entry']
                pnl_pct = ((current_price - entry) / entry) * 100

                # ─── فحص TP / SL ──────────────────────────────────────────────
                close_reason = None
                if current_price <= sig['sl']:
                    close_reason = 'SL'
                elif current_price >= sig['tp3'] and not sig.get('tp3_hit'):
                    close_reason = 'TP3'
                    sig['tp3_hit'] = True
                elif current_price >= sig['tp2'] and not sig.get('tp2_hit'):
                    sig['tp2_hit'] = True
                    msg = self._format_close_result(symbol, sig, current_price, 'TP2')
                    self._send_telegram(msg)
                    logger.info(f"🎯 TP2 hit: {symbol} @ {current_price}")
                    self._save_state()
                elif current_price >= sig['tp1'] and not sig.get('tp1_hit'):
                    sig['tp1_hit'] = True
                    msg = self._format_close_result(symbol, sig, current_price, 'TP1')
                    self._send_telegram(msg)
                    logger.info(f"🎯 TP1 hit: {symbol} @ {current_price}")
                    self._save_state()

                if close_reason in ('SL', 'TP3'):
                    msg = self._format_close_result(symbol, sig, current_price, close_reason)
                    self._send_telegram(msg)
                    logger.info(f"{'❌' if close_reason == 'SL' else '🏆'} {close_reason}: {symbol} @ {current_price} ({pnl_pct:+.2f}%)")
                    # تسجيل SL في الذاكرة المشتركة للتنويه بإعادة الدخول لاحقاً
                    if close_reason == 'SL':
                        self._record_sl_hit(symbol, sig.get('sl', 0))
                    to_close.append(symbol)
                    continue

                # ─── إنذار انخفاض السيولة ─────────────────────────────────────
                last_warn = sig.get('last_liq_warn', 0)
                if (time.time() - last_warn) < LIQ_WARN_COOLDOWN:
                    continue

                oi_data = self._get_oi_data(symbol)
                tf_5m   = self._analyze_technical(symbol, "5m")

                if not oi_data or not tf_5m:
                    continue

                oi_chg    = float(oi_data.get('h1OIChangePercent', 0) or 0)
                candles_5m = self._get_candles(symbol, "5m", 25)
                vol_ratio = 1.0
                if candles_5m and len(candles_5m) >= 21:
                    vols = [c['vol_usdt'] for c in candles_5m]
                    avg_v = sum(vols[1:21]) / 20
                    vol_ratio = vols[0] / avg_v if avg_v > 0 else 1.0

                rsi_5m = tf_5m['rsi']

                warn_conditions = [
                    oi_chg <= LIQ_WARN_OI_DROP,
                    vol_ratio <= LIQ_WARN_VOL_DROP,
                    rsi_5m <= LIQ_WARN_RSI_DROP,
                ]

                if sum(warn_conditions) >= 3:
                    msg = self._format_liquidity_warning(
                        symbol, sig, current_price, oi_chg, vol_ratio, rsi_5m, pnl_pct
                    )
                    if self._send_telegram(msg):
                        sig['last_liq_warn'] = time.time()
                        self._save_state()
                        logger.info(f"⚠️ Liquidity warning sent: {symbol} (OI:{oi_chg:+.2f}% Vol:{vol_ratio:.1f}x RSI:{rsi_5m:.1f})")

            except Exception as e:
                logger.error(f"Monitor error {symbol}: {e}")

        for symbol in to_close:
            self._remove_open_signal(symbol)

    # ─── مراقبة الاختراقات المعلقة (انتظار Retest) ────────────────────────────
    def _monitor_pending_breakouts(self):
        """فحص الاختراقات المعلقة — هل حصل Retest ناجح؟"""
        pending = self._get_pending_breakouts()
        if not pending:
            return

        to_remove = []

        for symbol, pb in pending.items():
            # تخطي إذا كان لديه توصية مفتوحة بالفعل
            if symbol in self._get_open_signals():
                to_remove.append(symbol)
                continue

            try:
                retest_result = self._check_retest(symbol, pb)

                if retest_result is None:
                    # انتهت نافذة الانتظار أو فشل الـ Retest
                    to_remove.append(symbol)
                    continue

                if retest_result.get('status') == 'waiting':
                    # لا يزال ينتظر
                    logger.debug(f"⏳ {symbol}: waiting for retest (breakout={format_price(pb['breakout_price'])})")
                    continue

                if retest_result.get('status') == 'confirmed':
                    # Retest ناجح! → تأكيد فني
                    current_price = retest_result['current_price']
                    logger.info(f"🔄 {symbol}: Retest confirmed! Running Phase3 technical confirmation...")

                    if not self._should_send_entry(symbol):
                        logger.info(f"⏸ {symbol}: cooldown active")
                        to_remove.append(symbol)
                        continue

                    time.sleep(0.5)
                    p3 = self._phase3_confirm(symbol, current_price)

                    if not p3 or not p3['confirmed']:
                        if p3:
                            logger.info(f"⚠️ {symbol}: Phase3 failed {p3['met_count']}/7 after Retest")
                        to_remove.append(symbol)
                        continue

                    # ✅ كل الشروط مكتملة — إرسال التوصية
                    entry = current_price
                    tp1 = entry * (1 + TP1_PCT)
                    tp2 = entry * (1 + TP2_PCT)
                    tp3 = entry * (1 + TP3_PCT)
                    sl  = entry * (1 - SL_PCT)

                    msg = self._format_entry_signal(pb, retest_result, p3, entry, tp1, tp2, tp3, sl)
                    if self._send_telegram(msg):
                        self._mark_entry_sent(symbol)
                        self._add_open_signal(symbol, entry, tp1, tp2, tp3, sl)
                        to_remove.append(symbol)
                        logger.info(f"📡 Signal sent after Retest: {symbol} entry={format_price(entry)} ({p3['met_count']}/7)")

            except Exception as e:
                logger.error(f"Pending monitor error {symbol}: {e}")

        for symbol in to_remove:
            self._remove_pending_breakout(symbol)

    # ─── المسح الكامل ─────────────────────────────────────────────────────────
    def scan_all(self):
        # أولاً: مراقبة الصفقات المفتوحة (TP/SL/إنذار سيولة)
        self._monitor_open_signals()

        # ثانياً: فحص الاختراقات المعلقة (انتظار Retest)
        self._monitor_pending_breakouts()

        # ثالثاً: البحث عن اختراقات جديدة
        logger.info(f"🔍 Scanning {len(WATCH_COINS)} coins for new breakouts...")
        breakouts_found = 0

        for i, symbol in enumerate(WATCH_COINS):
            # تخطي إذا كان لديه توصية مفتوحة أو اختراق معلق
            if symbol in self._get_open_signals():
                continue
            if symbol in self._get_pending_breakouts():
                continue

            try:
                p1 = self._phase1_breakout(symbol)
                if not p1:
                    continue

                logger.info(f"⚡ Breakout detected: {symbol} +{p1['breakout_pct']:.2f}% vol {p1['vol_ratio_1h']:.1f}x OI +{p1['h1_oi_chg']:.2f}%")

                if not self._should_send_entry(symbol):
                    logger.info(f"⏸ {symbol}: cooldown active")
                    continue

                # حفظ الاختراق وانتظار الـ Retest
                self._add_pending_breakout(symbol, p1)
                breakouts_found += 1
                logger.info(f"⏳ {symbol}: Breakout saved — waiting for Retest (window: {RETEST_WINDOW_H}h)")

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

            if i % 5 == 4:
                time.sleep(1)

        pending_count = len(self._get_pending_breakouts())
        open_count = len(self._get_open_signals())
        logger.info(f"✅ Scan done. New breakouts: {breakouts_found} | Pending Retest: {pending_count} | Open signals: {open_count}")
        return breakouts_found


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler('/root/trade_lak_bot/breakout_signal.log'),
            logging.StreamHandler()
        ]
    )

    system = BreakoutSignalSystem()
    SCAN_INTERVAL = 5 * 60

    logger.info("🚀 Breakout Signal System v4 started")
    logger.info(f"📡 {len(WATCH_COINS)} coins | scan every {SCAN_INTERVAL//60}min")
    logger.info("📢 Trade Lak Signal channel:")
    logger.info("  📡 Entry signals (after Breakout + Retest + Technical confirmation)")
    logger.info("  ⚠️ Liquidity warnings | ✅❌ Close results")

    while True:
        try:
            system.scan_all()
        except Exception as e:
            logger.error(f"Scan error: {e}")
        logger.info(f"⏳ Next scan in {SCAN_INTERVAL//60} min...")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
