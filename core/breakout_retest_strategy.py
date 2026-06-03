# ============================================================
# Trade Lak — Breakout+Retest Strategy Engine
# استراتيجية الاختراق والـ Retest لتنفيذ صفقات Spot حقيقية
# ============================================================
#
# المسار الكامل (3 مراحل):
#   1. المرحلة 1 (1H): اختراق مقاومة + Volume قوي + OI يرتفع
#      → يُحفظ في pending_breakouts (انتظار Retest)
#   2. المرحلة 2 (Retest): السعر يرجع ويلمس مستوى الاختراق ويرتد منه
#      → يُفعّل التأكيد الفني
#   3. المرحلة 3 (تأكيد فني 15m + 5m): EMA + RSI + Volume + Funding + Liq
#      → إرجاع BreakoutSignal مع signal_score (1-7) للـ Position Sizing
#
# Position Sizing الديناميكي:
#   score 5/7 → حجم عادي × 1.2
#   score 6/7 → حجم عادي × 1.5
#   score 7/7 → حجم عادي × 2.0
# ============================================================

import logging
import time
import json
import os
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── إعدادات المرحلة 1: الاختراق (1H) ───────────────────────────────────────
RESISTANCE_LOOKBACK   = 24      # عدد الشموع للخلف لحساب المقاومة
BREAKOUT_CONFIRM_PCT  = 0.003   # +0.3% فوق المقاومة
VOL_MULTIPLIER_MIN    = 1.5     # Volume أعلى من المتوسط بـ 1.5x
OI_RISE_MIN_H1        = 0.5     # OI ارتفع +0.5% في ساعة

# ─── إعدادات المرحلة 2: Retest ───────────────────────────────────────────────
RETEST_TOUCH_PCT      = 0.008   # السعر يصل لمستوى الاختراق ±0.8%
RETEST_BOUNCE_PCT     = 0.003   # يرتد +0.3% من مستوى الـ Retest
RETEST_WINDOW_H       = 6       # نافذة انتظار الـ Retest (6 ساعات)
RETEST_MAX_CANDLES    = 12      # أقصى عدد شموع 30m للانتظار

# ─── إعدادات المرحلة 3: التأكيد الفني ───────────────────────────────────────
RSI_MIN       = 50
RSI_MAX       = 75
EMA_FAST      = 20
EMA_SLOW      = 50
FUNDING_MAX   = 0.01
VOL_15M_MIN   = 1.2
LIQ_ABOVE_PCT = 0.005

# ─── Position Sizing Multipliers ─────────────────────────────────────────────
SCORE_MULTIPLIERS = {
    5: 1.2,   # 5/7 شروط → حجم عادي × 1.2
    6: 1.5,   # 6/7 شروط → حجم عادي × 1.5
    7: 2.0,   # 7/7 شروط → حجم عادي × 2.0
}

# ─── مستويات الدخول والخروج ───────────────────────────────────────────────────
TP1_PCT = 0.03    # +3%
TP2_PCT = 0.055   # +5.5%
TP3_PCT = 0.075   # +7.5%
SL_PCT  = 0.018   # -1.8% (ضمن نطاق 1-2%)

# ─── State File ──────────────────────────────────────────────────────────────
STATE_FILE = "/root/trade_lak_bot/data/breakout_retest_state.json"

# ─── APIs ────────────────────────────────────────────────────────────────────
OKX_BASE       = "https://www.okx.com/api/v5"
COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"


@dataclass
class BreakoutSignal:
    """
    إشارة اختراق + Retest مؤكدة — جاهزة للتنفيذ
    """
    symbol: str                    # مثال: "BTC-USDT"
    coin: str                      # مثال: "BTC"
    entry_price: float             # سعر الدخول (عند مستوى الاختراق)
    entry_low: float               # أدنى نطاق الدخول
    entry_high: float              # أعلى نطاق الدخول (+0.5%)
    stop_loss: float               # وقف الخسارة
    take_profit_1: float           # الهدف الأول
    take_profit_2: float           # الهدف الثاني
    take_profit_3: float           # الهدف الثالث
    signal_score: int              # 1-7 (عدد الشروط المحققة)
    position_multiplier: float     # معامل حجم الصفقة (1.0 / 1.2 / 1.5 / 2.0)
    resistance_level: float        # مستوى المقاومة المخترقة
    retest_low: float              # أدنى سعر في الـ Retest
    bounce_pct: float              # نسبة الارتداد من الـ Retest
    vol_ratio: float               # نسبة Volume إلى المتوسط
    oi_change_pct: float           # تغير OI في آخر ساعة
    funding_rate: float            # معدل التمويل
    ema_bullish_15m: bool          # EMA20 > EMA50 على 15m
    ema_bullish_5m: bool           # EMA20 > EMA50 على 5m
    rsi_15m: float                 # RSI على 15m
    rsi_5m: float                  # RSI على 5m
    has_liq_above: bool            # يوجد سيولة فوق السعر
    sector: str                    # القطاع
    timestamp: float = field(default_factory=time.time)
    reasoning: str = ""


class BreakoutRetestStrategy:
    """
    استراتيجية الاختراق + Retest لـ Trade Lak
    تعمل بشكل مستقل وتُعيد BreakoutSignal عند اكتمال الشروط
    """

    def __init__(self, coinglass_api_key: str):
        self.cg_headers = {
            'accept': 'application/json',
            'coinglassSecret': coinglass_api_key
        }
        self.state = self._load_state()
        logger.info("✅ BreakoutRetestStrategy initialized")

    # ─── State Management ────────────────────────────────────────────────────

    def _load_state(self) -> Dict:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"pending_breakouts": {}, "executed_signals": {}}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"State save error: {e}")

    def get_pending_breakouts(self) -> Dict:
        return self.state.get("pending_breakouts", {})

    def add_pending_breakout(self, symbol: str, data: Dict):
        if "pending_breakouts" not in self.state:
            self.state["pending_breakouts"] = {}
        self.state["pending_breakouts"][symbol] = data
        self._save_state()

    def remove_pending_breakout(self, symbol: str):
        if symbol in self.state.get("pending_breakouts", {}):
            del self.state["pending_breakouts"][symbol]
            self._save_state()

    def mark_executed(self, symbol: str, signal: BreakoutSignal):
        if "executed_signals" not in self.state:
            self.state["executed_signals"] = {}
        self.state["executed_signals"][symbol] = {
            "entry_price": signal.entry_price,
            "executed_at": time.time(),
            "signal_score": signal.signal_score,
        }
        self._save_state()

    def was_recently_executed(self, symbol: str, cooldown_hours: float = 4.0) -> bool:
        """هل تم تنفيذ إشارة لهذه العملة مؤخراً؟"""
        executed = self.state.get("executed_signals", {})
        if symbol not in executed:
            return False
        elapsed = (time.time() - executed[symbol].get("executed_at", 0)) / 3600
        return elapsed < cooldown_hours

    # ─── جلب البيانات ────────────────────────────────────────────────────────

    def _get_candles(self, symbol: str, bar: str = "1H", limit: int = 60) -> Optional[List[Dict]]:
        """جلب شموع OKX"""
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
                    'vol': float(c[5]), 'vol_usdt': float(c[7]) if len(c) > 7 else float(c[5]),
                } for c in data['data']]
        except Exception as e:
            logger.error(f"Candles {symbol}/{bar}: {e}")
        return None

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """جلب السعر الحالي من OKX"""
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
        """جلب بيانات Open Interest من CoinGlass"""
        try:
            r = requests.get(
                f"{COINGLASS_BASE}/open_interest",
                headers=self.cg_headers,
                params={'symbol': symbol},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                items = data['data']
                return items[0] if isinstance(items, list) else items
        except Exception as e:
            logger.debug(f"OI {symbol}: {e}")
        return None

    def _get_funding_rate(self, symbol: str) -> float:
        """جلب معدل التمويل من CoinGlass"""
        try:
            r = requests.get(
                f"{COINGLASS_BASE}/funding_rates_chart",
                headers=self.cg_headers,
                params={'symbol': symbol, 'exchange': 'OKX'},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                d = data['data']
                if isinstance(d, list) and d:
                    return float(d[-1].get('fundingRate', 0) or 0)
                elif isinstance(d, dict):
                    return float(d.get('fundingRate', 0) or 0)
        except Exception:
            pass
        return 0.0

    def _get_liq_above(self, symbol: str, current_price: float) -> bool:
        """هل يوجد سيولة فوق السعر الحالي؟"""
        try:
            r = requests.get(
                f"{COINGLASS_BASE}/liquidation_map",
                headers=self.cg_headers,
                params={'symbol': symbol, 'range': '12h'},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                d = data['data']
                prices = d.get('prices', [])
                shorts = d.get('shorts', [])
                if prices and shorts:
                    above = sum(s for p, s in zip(prices, shorts)
                                if float(p) > current_price * (1 + LIQ_ABOVE_PCT))
                    return above > 0
        except Exception:
            pass
        return False

    # ─── الحسابات الفنية ─────────────────────────────────────────────────────

    @staticmethod
    def _calc_ema(values: List[float], period: int) -> List[float]:
        if len(values) < period:
            return []
        k = 2 / (period + 1)
        ema = [sum(values[:period]) / period]
        for v in values[period:]:
            ema.append(v * k + ema[-1] * (1 - k))
        return ema

    @staticmethod
    def _calc_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains  = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        if not losses:
            return 100.0
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + avg_gain / avg_loss))

    def _analyze_technical(self, symbol: str, bar: str) -> Optional[Dict]:
        """تحليل EMA + RSI + Volume على timeframe معين"""
        candles = self._get_candles(symbol, bar=bar, limit=70)
        if not candles or len(candles) < EMA_SLOW + 5:
            return None
        closes = [c['close'] for c in reversed(candles)]
        vols   = [c['vol_usdt'] for c in reversed(candles)]
        ema_fast_s = self._calc_ema(closes, EMA_FAST)
        ema_slow_s = self._calc_ema(closes, EMA_SLOW)
        ema_bullish = (len(ema_fast_s) > 0 and len(ema_slow_s) > 0
                       and ema_fast_s[-1] > ema_slow_s[-1])
        rsi = self._calc_rsi(closes)
        avg_vol = sum(vols[-20:]) / 20 if len(vols) >= 20 else sum(vols) / len(vols)
        vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 0
        return {
            'ema_bullish': ema_bullish,
            'ema_fast': ema_fast_s[-1] if ema_fast_s else 0,
            'ema_slow': ema_slow_s[-1] if ema_slow_s else 0,
            'rsi': rsi,
            'vol_ratio': vol_ratio,
        }

    # ─── المرحلة 1: كشف الاختراق (1H) ───────────────────────────────────────

    def phase1_breakout(self, symbol: str) -> Optional[Dict]:
        """
        فحص اختراق المقاومة على الـ 1H:
        - السعر يتجاوز أعلى مستوى في آخر 24 ساعة بـ +0.3%
        - Volume أعلى من المتوسط بـ 1.5x
        - OI ارتفع +0.5% في آخر ساعة
        """
        candles_1h = self._get_candles(symbol, bar="1H", limit=RESISTANCE_LOOKBACK + 5)
        if not candles_1h or len(candles_1h) < RESISTANCE_LOOKBACK + 2:
            return None

        current_candle = candles_1h[0]
        current_price  = current_candle['close']
        current_vol_usdt = current_candle['vol_usdt']

        # حساب مستوى المقاومة (أعلى high في آخر RESISTANCE_LOOKBACK شمعة)
        lookback = candles_1h[1:RESISTANCE_LOOKBACK + 1]
        highs = [c['high'] for c in lookback]
        resistance = max(highs)
        touches = sum(1 for h in highs if abs(h - resistance) / resistance < 0.005)

        # هل كسر المقاومة بـ +0.3%؟
        breakout_pct = (current_price - resistance) / resistance
        if breakout_pct < BREAKOUT_CONFIRM_PCT:
            return None

        # هل Volume قوي؟
        avg_vol = sum(c['vol_usdt'] for c in candles_1h[1:21]) / 20
        vol_ratio = current_vol_usdt / avg_vol if avg_vol > 0 else 0
        if vol_ratio < VOL_MULTIPLIER_MIN:
            return None

        # هل OI يرتفع؟
        oi_data = self._get_oi_data(symbol)
        h1_oi_chg = 0.0
        oi_total  = 0.0
        if oi_data:
            h1_oi_chg = float(oi_data.get('h1OIChangePercent', 0) or 0)
            oi_total  = float(oi_data.get('openInterest', 0) or 0)
        if h1_oi_chg < OI_RISE_MIN_H1:
            return None

        logger.info(
            f"🚀 {symbol}: Breakout detected! Price={current_price:.6f} "
            f"Resistance={resistance:.6f} (+{breakout_pct*100:.2f}%) "
            f"Vol={vol_ratio:.1f}x OI={h1_oi_chg:+.2f}%"
        )

        return {
            'symbol': symbol,
            'price': current_price,
            'resistance': resistance,
            'breakout_pct': breakout_pct * 100,
            'vol_ratio_1h': vol_ratio,
            'vol_usdt_1h': current_vol_usdt,
            'avg_vol_1h': avg_vol,
            'h1_oi_chg': h1_oi_chg,
            'oi_total': oi_total,
            'touches': touches,
            'breakout_time': time.time(),
        }

    # ─── المرحلة 2: فحص Retest ───────────────────────────────────────────────

    def phase2_retest(self, symbol: str, pending: Dict) -> Optional[Dict]:
        """
        فحص إذا حصل Retest ناجح:
        - السعر رجع ولمس مستوى الاختراق (±RETEST_TOUCH_PCT)
        - ثم ارتد منه بـ +RETEST_BOUNCE_PCT على الأقل
        - بدون كسر مستوى الاختراق للأسفل
        
        Returns:
            None: انتهت الفرصة (فشل أو انتهى الوقت)
            {"status": "waiting"}: لم يحصل Retest بعد
            {"status": "confirmed", ...}: Retest مؤكد ✅
        """
        resistance    = pending['resistance']
        breakout_time = pending['breakout_time']

        # فحص انتهاء نافذة الانتظار
        elapsed_h = (time.time() - breakout_time) / 3600
        if elapsed_h > RETEST_WINDOW_H:
            logger.info(f"⏰ {symbol}: Retest window expired ({elapsed_h:.1f}h) — removing")
            return None

        candles_30m = self._get_candles(symbol, bar="30m", limit=RETEST_MAX_CANDLES + 2)
        if not candles_30m:
            return {"status": "waiting"}

        current_price    = candles_30m[0]['close']
        retest_zone_high = resistance * (1 + RETEST_TOUCH_PCT)
        retest_zone_low  = resistance * (1 - RETEST_TOUCH_PCT)

        # البحث عن لمسة للـ Retest zone ثم ارتداد
        retest_low_seen = None
        for c in candles_30m[1:]:
            low  = c['low']
            high = c['high']
            if (retest_zone_low <= low <= retest_zone_high or
                    retest_zone_low <= high <= retest_zone_high):
                if retest_low_seen is None or low < retest_low_seen:
                    retest_low_seen = low

        if retest_low_seen is None:
            return {"status": "waiting", "current_price": current_price}

        # هل كسر مستوى الاختراق للأسفل؟ (فشل الـ Retest)
        if retest_low_seen < resistance * (1 - RETEST_TOUCH_PCT * 2):
            logger.info(f"❌ {symbol}: Retest failed — broke below resistance")
            return None

        # هل ارتد بشكل كافٍ؟
        bounce_pct = (current_price - retest_low_seen) / retest_low_seen
        if bounce_pct >= RETEST_BOUNCE_PCT:
            logger.info(
                f"✅ {symbol}: Retest confirmed! "
                f"Low={retest_low_seen:.6f} Current={current_price:.6f} "
                f"Bounce={bounce_pct*100:.2f}%"
            )
            return {
                "status": "confirmed",
                "current_price": current_price,
                "retest_low": retest_low_seen,
                "bounce_pct": bounce_pct * 100,
                "retest_level": resistance,
            }

        return {"status": "waiting", "current_price": current_price, "retest_low_seen": retest_low_seen}

    # ─── المرحلة 3: التأكيد الفني ────────────────────────────────────────────

    def phase3_confirm(self, symbol: str, current_price: float) -> Optional[Dict]:
        """
        التأكيد الفني على 15m و5m:
        7 شروط: EMA15m، EMA5m، RSI15m، RSI5m، Vol15m، Funding، Liq_above
        يجب أن تتحقق EMA على كلا الـ timeframes + RSI على أحدهما + 5 شروط إجمالاً
        """
        tf_15m = self._analyze_technical(symbol, "15m")
        time.sleep(0.3)
        tf_5m  = self._analyze_technical(symbol, "5m")

        if not tf_15m or not tf_5m:
            return None

        funding     = self._get_funding_rate(symbol)
        has_liq_above = self._get_liq_above(symbol, current_price)

        checks = {
            'ema_15m':   tf_15m['ema_bullish'],
            'ema_5m':    tf_5m['ema_bullish'],
            'rsi_15m':   RSI_MIN <= tf_15m['rsi'] <= RSI_MAX,
            'rsi_5m':    RSI_MIN <= tf_5m['rsi']  <= RSI_MAX,
            'vol_15m':   tf_15m['vol_ratio'] >= VOL_15M_MIN,
            'funding':   abs(funding) <= FUNDING_MAX,
            'liq_above': has_liq_above,
        }

        ema_ok = checks['ema_15m'] and checks['ema_5m']
        rsi_ok = checks['rsi_15m'] or checks['rsi_5m']
        met_count = sum(1 for v in checks.values() if v)
        confirmed = ema_ok and rsi_ok and met_count >= 5

        return {
            'confirmed': confirmed,
            'met_count': met_count,
            'checks': checks,
            'ema_bullish_15m': tf_15m['ema_bullish'],
            'ema_bullish_5m':  tf_5m['ema_bullish'],
            'rsi_15m':   tf_15m['rsi'],
            'rsi_5m':    tf_5m['rsi'],
            'vol_ratio': tf_15m['vol_ratio'],
            'funding':   funding,
            'has_liq_above': has_liq_above,
        }

    # ─── بناء الإشارة النهائية ────────────────────────────────────────────────

    def build_signal(self, symbol: str, pending: Dict,
                     retest: Dict, p3: Dict) -> BreakoutSignal:
        """
        بناء BreakoutSignal مع حساب Position Sizing الديناميكي
        """
        coin = symbol.replace('-USDT', '').replace('/USDT', '')
        resistance = pending['resistance']
        current_price = retest['current_price']

        # نقطة الدخول: عند مستوى الاختراق (الذي أصبح دعماً)
        entry_low  = resistance
        entry_high = resistance * 1.005  # +0.5%
        entry_price = (entry_low + entry_high) / 2

        # مستويات الخروج
        tp1 = entry_price * (1 + TP1_PCT)
        tp2 = entry_price * (1 + TP2_PCT)
        tp3 = entry_price * (1 + TP3_PCT)
        sl  = entry_price * (1 - SL_PCT)

        # تعديل SL بناءً على خريطة السيولة (تجنب اصطياده)
        # إذا كان SL قريباً جداً من مستوى سيولة، نبعده قليلاً
        sl = min(sl, resistance * 0.985)  # SL أسفل المقاومة بـ 1.5%

        # Position Sizing
        score = p3['met_count']
        multiplier = SCORE_MULTIPLIERS.get(score, 1.0)
        if score < 5:
            multiplier = 1.0  # حجم عادي للإشارات الأضعف

        # بناء reasoning
        checks = p3['checks']
        check_icons = {k: '✅' if v else '❌' for k, v in checks.items()}
        reasoning = (
            f"Breakout +{pending['breakout_pct']:.2f}% | "
            f"Vol {pending['vol_ratio_1h']:.1f}x | "
            f"OI {pending['h1_oi_chg']:+.2f}% | "
            f"Retest bounce {retest['bounce_pct']:.2f}% | "
            f"Score {score}/7 | "
            f"EMA15m:{check_icons['ema_15m']} EMA5m:{check_icons['ema_5m']} "
            f"RSI15m:{check_icons['rsi_15m']} RSI5m:{check_icons['rsi_5m']} "
            f"Vol15m:{check_icons['vol_15m']} Funding:{check_icons['funding']} "
            f"Liq:{check_icons['liq_above']}"
        )

        return BreakoutSignal(
            symbol=f"{coin}-USDT",
            coin=coin,
            entry_price=entry_price,
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            signal_score=score,
            position_multiplier=multiplier,
            resistance_level=resistance,
            retest_low=retest['retest_low'],
            bounce_pct=retest['bounce_pct'],
            vol_ratio=pending['vol_ratio_1h'],
            oi_change_pct=pending['h1_oi_chg'],
            funding_rate=p3['funding'],
            ema_bullish_15m=p3['ema_bullish_15m'],
            ema_bullish_5m=p3['ema_bullish_5m'],
            rsi_15m=p3['rsi_15m'],
            rsi_5m=p3['rsi_5m'],
            has_liq_above=p3['has_liq_above'],
            sector=pending.get('sector', 'Other'),
            reasoning=reasoning,
        )

    # ─── الدالة الرئيسية: فحص عملة واحدة ────────────────────────────────────

    def scan_symbol(self, symbol: str) -> Optional[BreakoutSignal]:
        """
        فحص عملة واحدة عبر المراحل الثلاث.
        
        Returns:
            BreakoutSignal إذا اكتملت جميع الشروط
            None إذا لم تكتمل الشروط
        """
        # تجنب إعادة تنفيذ إشارة مؤخراً
        if self.was_recently_executed(symbol):
            return None

        pending_breakouts = self.get_pending_breakouts()

        if symbol not in pending_breakouts:
            # ── شرط EMA50 على 4H (فلتر التريند الإلزامي) ──
            # درس مستفاد: لا دخول شراء إذا كان السعر تحت EMA50 على 4H (تريند هابط)
            try:
                candles_4h = self._get_candles(symbol, bar="4H", limit=60)
                if candles_4h and len(candles_4h) >= 50:
                    closes_4h = [c['close'] for c in candles_4h]  # معكوسة (الأحدث أولاً)
                    k4 = 2 / (50 + 1)
                    ema50_4h = closes_4h[-1]  # نبدأ من الأقدم
                    for cv in reversed(closes_4h[:-1]):
                        ema50_4h = cv * k4 + ema50_4h * (1 - k4)
                    current_p = closes_4h[0]  # الأحدث (index 0 في بيانات OKX)
                    if current_p < ema50_4h:
                        logger.debug(f"{symbol}: سعر ({current_p:.6f}) تحت EMA50 4H ({ema50_4h:.6f}) — لا دخول شراء")
                        return None
            except Exception:
                pass  # عند الخطأ، لا نمنع الدخول
            # ─── المرحلة 1: فحص الاختراق ───
            p1 = self.phase1_breakout(symbol)
            if p1:
                self.add_pending_breakout(symbol, p1)
                logger.info(f"📌 {symbol}: Breakout saved — waiting for Retest")
            return None

        else:
            # ─── المرحلة 2: فحص Retest ───
            pending = pending_breakouts[symbol]
            retest = self.phase2_retest(symbol, pending)

            if retest is None:
                # انتهت الفرصة (فشل أو انتهى الوقت)
                self.remove_pending_breakout(symbol)
                return None

            if retest.get('status') != 'confirmed':
                # لا يزال ينتظر
                return None

            # ─── المرحلة 3: التأكيد الفني ───
            current_price = retest['current_price']
            p3 = self.phase3_confirm(symbol, current_price)

            if not p3 or not p3['confirmed']:
                score = p3['met_count'] if p3 else 0
                logger.info(
                    f"⚠️ {symbol}: Technical confirmation failed "
                    f"({score}/7 conditions met)"
                )
                # لا نحذف الـ pending — قد يتحسن لاحقاً
                return None

            # ─── بناء الإشارة النهائية ───
            signal = self.build_signal(symbol, pending, retest, p3)
            logger.info(
                f"🎯 {symbol}: BREAKOUT+RETEST CONFIRMED! "
                f"Score={signal.signal_score}/7 "
                f"Multiplier={signal.position_multiplier}x "
                f"Entry={signal.entry_price:.6f} "
                f"SL={signal.stop_loss:.6f} "
                f"TP1={signal.take_profit_1:.6f}"
            )

            # حذف من pending وتسجيل التنفيذ
            self.remove_pending_breakout(symbol)
            self.mark_executed(symbol, signal)

            return signal

    # ─── فحص قائمة عملات ────────────────────────────────────────────────────

    def scan_symbols(self, symbols: List[str], delay: float = 0.5) -> List[BreakoutSignal]:
        """
        فحص قائمة عملات وإعادة جميع الإشارات المؤكدة
        
        Args:
            symbols: قائمة أسماء العملات (مثال: ["BTC", "ETH", "SOL"])
            delay: تأخير بين كل عملة (ثانية)
        
        Returns:
            قائمة BreakoutSignal المؤكدة
        """
        confirmed_signals = []
        for coin in symbols:
            try:
                signal = self.scan_symbol(coin)
                if signal:
                    confirmed_signals.append(signal)
            except Exception as e:
                logger.error(f"Error scanning {coin}: {e}")
            if delay > 0:
                time.sleep(delay)
        return confirmed_signals

    # ─── حساب حجم الصفقة الديناميكي ─────────────────────────────────────────

    @staticmethod
    def calculate_dynamic_position_size(
        base_position_size: float,
        signal: BreakoutSignal,
        max_multiplier: float = 2.0
    ) -> float:
        """
        حساب حجم الصفقة الديناميكي بناءً على جودة الإشارة.
        
        Args:
            base_position_size: الحجم الأساسي المحسوب من risk management
            signal: إشارة الاختراق مع signal_score
            max_multiplier: الحد الأقصى للمعامل
        
        Returns:
            حجم الصفقة المعدّل بالدولار
        """
        multiplier = min(signal.position_multiplier, max_multiplier)
        adjusted_size = base_position_size * multiplier
        logger.info(
            f"📊 Position Sizing: base=${base_position_size:.2f} "
            f"× {multiplier:.1f} (score {signal.signal_score}/7) "
            f"= ${adjusted_size:.2f}"
        )
        return adjusted_size
