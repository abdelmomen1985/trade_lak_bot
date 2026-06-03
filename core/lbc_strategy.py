# ============================================================
# Trade Lak Bot — LBC Strategy (Liquidity → Break → Confirmation)
# استراتيجية: سيولة + كسر + تأكيد
# ============================================================
# المنطق:
#   المرحلة 1: تحديد السيولة (Liquidity Zones)
#              — قمم وقيعان واضحة فوق/تحت السعر
#   المرحلة 2: الكسر (Break)
#              — Fake Break (اصطياد سيولة) → إعداد انعكاس
#              — Breakout حقيقي → إعداد صعود/هبوط
#   المرحلة 3: التأكيد (Confirmation)
#              — Retest + شمعة تأكيد + OI صاعد + Volume مناسب
# ============================================================

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ─── ثوابت الاستراتيجية ──────────────────────────────────────────────────────

# المرحلة 1: السيولة
LIQUIDITY_LOOKBACK       = 50    # عدد الشموع للبحث عن مناطق السيولة
LIQUIDITY_ZONE_WIDTH     = 0.008 # ±0.8% عرض منطقة السيولة
MIN_ZONE_TOUCHES         = 2     # الحد الأدنى للمسات لاعتبار المنطقة قوية
BTC_TREND_LOOKBACK       = 20    # شموع لتحديد اتجاه BTC

# المرحلة 2: الكسر
FAKE_BREAK_MIN_PCT       = 0.001 # 0.1% أدنى اختراق يُعتبر Fake Break
FAKE_BREAK_MAX_PCT       = 0.025 # 2.5% أقصى اختراق يُعتبر Fake Break (أكثر = حقيقي)
REAL_BREAK_MIN_PCT       = 0.003 # 0.3% أدنى اختراق يُعتبر Breakout حقيقي
REAL_BREAK_VOLUME_MULT   = 1.5   # حجم تداول ≥ 1.5× المتوسط لتأكيد Breakout
REAL_BREAK_OI_CHANGE     = 0.005 # OI يرتفع +0.5% لتأكيد Breakout

# المرحلة 3: التأكيد
RETEST_ZONE_WIDTH        = 0.008 # ±0.8% نطاق قبول الـ Retest
RETEST_BOUNCE_MIN        = 0.003 # +0.3% ارتداد من أدنى نقطة الـ Retest
CONFIRM_VOLUME_MULT      = 1.0   # حجم تداول ≥ 1.0× المتوسط عند التأكيد
CONFIRM_OI_MIN_CHANGE    = -0.001 # OI لا ينهار (≥ −0.1%)
RETEST_WINDOW_CANDLES    = 12    # نافذة انتظار الـ Retest (12 شمعة = 6 ساعات على 30m)

# مستويات الخروج
TP1_R = 1.0   # TP1 = 1R (ربح سريع)
TP2_R = 2.0   # TP2 = 2R
TP3_R = 3.0   # TP3 = 3R أو ترند ممتد
SL_BUFFER_PCT = 0.003  # 0.3% مسافة أمان خلف الذيل

# إلغاء الصفقة إذا:
CANCEL_OI_DROP_PCT       = -0.02  # OI انخفض أكثر من 2% بعد الدخول
CANCEL_PRICE_RETURN_PCT  = 0.005  # السعر رجع داخل النطاق بأكثر من 0.5%

# ─── حالات الاستراتيجية ──────────────────────────────────────────────────────

class LBCSetupType:
    FAKE_BREAK_BUY  = "FAKE_BREAK_BUY"   # اصطياد سيولة تحت الدعم → شراء
    FAKE_BREAK_SELL = "FAKE_BREAK_SELL"  # اصطياد سيولة فوق المقاومة → بيع
    BREAKOUT_BUY    = "BREAKOUT_BUY"     # Breakout حقيقي فوق المقاومة → شراء
    BREAKOUT_SELL   = "BREAKOUT_SELL"    # Breakout حقيقي تحت الدعم → بيع

class LBCState:
    """حالة الإعداد المعلَّق لعملة معينة"""
    def __init__(self, symbol, setup_type, break_level, sl, tp1, tp2, tp3,
                 detected_at, candles_waited=0):
        self.symbol        = symbol
        self.setup_type    = setup_type
        self.break_level   = break_level   # مستوى الكسر
        self.sl            = sl
        self.tp1           = tp1
        self.tp2           = tp2
        self.tp3           = tp3
        self.detected_at   = detected_at   # وقت اكتشاف الكسر
        self.candles_waited = candles_waited
        self.confirmed     = False

# ─── المحرك الرئيسي ──────────────────────────────────────────────────────────

class LBCStrategy:
    """
    استراتيجية سيولة + كسر + تأكيد (Liquidity → Break → Confirmation)
    تعمل بشكل مستقل على Spot فقط
    """

    def __init__(self, okx_client, coinglass_client):
        self.okx        = okx_client
        self.cg         = coinglass_client
        # الإعدادات المعلَّقة (انتظار التأكيد)
        self.pending_setups: dict[str, LBCState] = {}
        logger.info("✅ LBC Strategy (Liquidity → Break → Confirmation) initialized")

    @staticmethod
    def _normalize_ohlcv(raw: list) -> list:
        """
        تحويل CCXT raw OHLCV (قائمة قوائم) إلى dicts.
        CCXT format: [timestamp, open, high, low, close, volume]
        """
        result = []
        for c in raw:
            if isinstance(c, dict):
                result.append(c)  # مسبقاً محوّل
            elif isinstance(c, (list, tuple)) and len(c) >= 6:
                result.append({
                    'timestamp': c[0],
                    'open':      float(c[1]),
                    'high':      float(c[2]),
                    'low':       float(c[3]),
                    'close':     float(c[4]),
                    'volume':    float(c[5]),
                })
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # المرحلة 1: تحديد السيولة
    # ══════════════════════════════════════════════════════════════════════════

    def _find_liquidity_zones(self, ohlcv: list) -> dict:
        """
        يبحث عن مناطق السيولة (قمم وقيعان واضحة) في آخر LIQUIDITY_LOOKBACK شمعة.
        يُعيد:
            resistance_zones: قائمة مستويات المقاومة (سيولة فوق السعر)
            support_zones:    قائمة مستويات الدعم (سيولة تحت السعر)
        """
        if not ohlcv or len(ohlcv) < LIQUIDITY_LOOKBACK:
            return {"resistance_zones": [], "support_zones": []}

        candles = ohlcv[-LIQUIDITY_LOOKBACK:]
        highs   = [c['high']  for c in candles]
        lows    = [c['low']   for c in candles]
        closes  = [c['close'] for c in candles]
        current_price = closes[-1]

        resistance_zones = []
        support_zones    = []

        # ── تحديد القمم (Swing Highs) ──
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] \
               and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                level = highs[i]
                if level > current_price:
                    # حساب عدد اللمسات
                    touches = sum(
                        1 for h in highs
                        if abs(h - level) / level <= LIQUIDITY_ZONE_WIDTH
                    )
                    if touches >= MIN_ZONE_TOUCHES:
                        resistance_zones.append({
                            "level": level,
                            "touches": touches,
                            "strength": min(touches / 5.0, 1.0),
                        })

        # ── تحديد القيعان (Swing Lows) ──
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] \
               and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                level = lows[i]
                if level < current_price:
                    touches = sum(
                        1 for l in lows
                        if abs(l - level) / level <= LIQUIDITY_ZONE_WIDTH
                    )
                    if touches >= MIN_ZONE_TOUCHES:
                        support_zones.append({
                            "level": level,
                            "touches": touches,
                            "strength": min(touches / 5.0, 1.0),
                        })

        # ترتيب: الأقرب للسعر أولاً
        resistance_zones.sort(key=lambda z: z["level"])
        support_zones.sort(key=lambda z: z["level"], reverse=True)

        return {
            "resistance_zones": resistance_zones[:3],
            "support_zones":    support_zones[:3],
            "current_price":    current_price,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # فحص اتجاه BTC (شرط السوق العام)
    # ══════════════════════════════════════════════════════════════════════════

    def _check_btc_market_condition(self) -> str:
        """
        يفحص حالة BTC:
        - UPTREND:  Higher Highs + Higher Lows
        - RANGE:    نطاق عرضي واضح
        - CHAOTIC:  سوق عشوائي → لا تتداول
        """
        try:
            ohlcv_raw = self.okx.get_ohlcv("BTC/USDT", timeframe="1h", limit=BTC_TREND_LOOKBACK + 5)
            if not ohlcv_raw or len(ohlcv_raw) < BTC_TREND_LOOKBACK:
                return "NEUTRAL"
            ohlcv = self._normalize_ohlcv(ohlcv_raw)
            if len(ohlcv) < BTC_TREND_LOOKBACK:
                return "NEUTRAL"

            closes = [c['close'] for c in ohlcv[-BTC_TREND_LOOKBACK:]]
            highs  = [c['high']  for c in ohlcv[-BTC_TREND_LOOKBACK:]]
            lows   = [c['low']   for c in ohlcv[-BTC_TREND_LOOKBACK:]]

            # ── EMA20 مقابل EMA50 ──
            ema20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
            ema50 = np.mean(closes)

            # ── Higher Highs / Higher Lows ──
            mid = len(highs) // 2
            hh = highs[-1] > max(highs[:mid])
            hl = lows[-1]  > min(lows[:mid])
            lh = highs[-1] < max(highs[:mid])
            ll = lows[-1]  < min(lows[:mid])

            # ── تقلب السوق (Volatility) ──
            price_range = (max(closes) - min(closes)) / min(closes)

            if hh and hl and ema20 > ema50:
                return "UPTREND"
            elif lh and ll and ema20 < ema50:
                return "DOWNTREND"
            elif price_range < 0.05:  # نطاق أقل من 5% = Range
                return "RANGE"
            else:
                return "CHAOTIC"

        except Exception as e:
            logger.warning(f"⚠️ LBC: فشل فحص BTC: {e}")
            return "UNKNOWN"

    # ══════════════════════════════════════════════════════════════════════════
    # المرحلة 2: كشف الكسر (Break Detection)
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_break(self, ohlcv: list, zones: dict) -> Optional[dict]:
        """
        يفحص آخر شمعتين لكشف:
        - Fake Break (اصطياد سيولة) → انعكاس
        - Breakout حقيقي → استمرار
        يُعيد dict بتفاصيل الكسر أو None
        """
        if not ohlcv or len(ohlcv) < 3:
            return None

        prev   = ohlcv[-2]   # الشمعة السابقة (شمعة الكسر)
        curr   = ohlcv[-1]   # الشمعة الحالية
        candles = ohlcv[-20:]
        avg_vol = np.mean([c['volume'] for c in candles[:-1]]) if len(candles) > 1 else 1

        current_price = curr['close']
        prev_high     = prev['high']
        prev_low      = prev['low']
        prev_close    = prev['close']
        prev_open     = prev['open']
        curr_vol      = curr['volume']

        # ── فحص Fake Break تحت الدعم (→ شراء) ──
        for zone in zones.get("support_zones", []):
            level = zone["level"]
            break_pct = (level - prev_low) / level  # كم اخترق تحت الدعم

            if FAKE_BREAK_MIN_PCT <= break_pct <= FAKE_BREAK_MAX_PCT:
                # تحقق من الرجوع: الإغلاق فوق الدعم
                if prev_close > level * (1 - LIQUIDITY_ZONE_WIDTH):
                    # شمعة تأكيد: ذيل طويل أو ابتلاعية صاعدة
                    body    = abs(prev_close - prev_open)
                    tail    = prev_open - prev_low if prev_close > prev_open else prev_close - prev_low
                    is_conf = (tail >= body * 1.5) or \
                              (prev_close > prev_open and curr['close'] > prev['high'])

                    if is_conf:
                        sl  = prev_low * (1 - SL_BUFFER_PCT)
                        risk = current_price - sl
                        return {
                            "type":        LBCSetupType.FAKE_BREAK_BUY,
                            "break_level": level,
                            "direction":   "LONG",
                            "sl":          sl,
                            "tp1":         current_price + risk * TP1_R,
                            "tp2":         current_price + risk * TP2_R,
                            "tp3":         current_price + risk * TP3_R,
                            "zone_strength": zone["strength"],
                            "break_pct":   break_pct,
                            "volume_ratio": curr_vol / avg_vol if avg_vol > 0 else 1,
                        }

        # ── فحص Fake Break فوق المقاومة (→ بيع) ──
        for zone in zones.get("resistance_zones", []):
            level = zone["level"]
            break_pct = (prev_high - level) / level

            if FAKE_BREAK_MIN_PCT <= break_pct <= FAKE_BREAK_MAX_PCT:
                if prev_close < level * (1 + LIQUIDITY_ZONE_WIDTH):
                    body = abs(prev_close - prev_open)
                    tail = prev_high - prev_open if prev_close < prev_open else prev_high - prev_close
                    is_conf = (tail >= body * 1.5) or \
                              (prev_close < prev_open and curr['close'] < prev['low'])

                    if is_conf:
                        sl   = prev_high * (1 + SL_BUFFER_PCT)
                        risk = sl - current_price
                        return {
                            "type":        LBCSetupType.FAKE_BREAK_SELL,
                            "break_level": level,
                            "direction":   "SHORT",
                            "sl":          sl,
                            "tp1":         current_price - risk * TP1_R,
                            "tp2":         current_price - risk * TP2_R,
                            "tp3":         current_price - risk * TP3_R,
                            "zone_strength": zone["strength"],
                            "break_pct":   break_pct,
                            "volume_ratio": curr_vol / avg_vol if avg_vol > 0 else 1,
                        }

        # ── فحص Breakout حقيقي فوق المقاومة (→ شراء) ──
        for zone in zones.get("resistance_zones", []):
            level = zone["level"]
            break_pct = (prev_close - level) / level  # إغلاق فوق المقاومة

            if break_pct >= REAL_BREAK_MIN_PCT:
                vol_ok = curr_vol >= avg_vol * REAL_BREAK_VOLUME_MULT
                if vol_ok:
                    sl   = level * (1 - SL_BUFFER_PCT)
                    risk = current_price - sl
                    return {
                        "type":        LBCSetupType.BREAKOUT_BUY,
                        "break_level": level,
                        "direction":   "LONG",
                        "sl":          sl,
                        "tp1":         current_price + risk * TP1_R,
                        "tp2":         current_price + risk * TP2_R,
                        "tp3":         current_price + risk * TP3_R,
                        "zone_strength": zone["strength"],
                        "break_pct":   break_pct,
                        "volume_ratio": curr_vol / avg_vol if avg_vol > 0 else 1,
                        "needs_retest": True,  # Breakout يحتاج Retest قبل الدخول
                    }

        # ── فحص Breakout حقيقي تحت الدعم (→ بيع) ──
        for zone in zones.get("support_zones", []):
            level = zone["level"]
            break_pct = (level - prev_close) / level

            if break_pct >= REAL_BREAK_MIN_PCT:
                vol_ok = curr_vol >= avg_vol * REAL_BREAK_VOLUME_MULT
                if vol_ok:
                    sl   = level * (1 + SL_BUFFER_PCT)
                    risk = sl - current_price
                    return {
                        "type":        LBCSetupType.BREAKOUT_SELL,
                        "break_level": level,
                        "direction":   "SHORT",
                        "sl":          sl,
                        "tp1":         current_price - risk * TP1_R,
                        "tp2":         current_price - risk * TP2_R,
                        "tp3":         current_price - risk * TP3_R,
                        "zone_strength": zone["strength"],
                        "break_pct":   break_pct,
                        "volume_ratio": curr_vol / avg_vol if avg_vol > 0 else 1,
                        "needs_retest": True,
                    }

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # المرحلة 3: التأكيد (Confirmation)
    # ══════════════════════════════════════════════════════════════════════════

    def _check_confirmation(self, symbol: str, setup: LBCState,
                            ohlcv: list, cg_data: dict) -> bool:
        """
        يتحقق من شروط التأكيد الكاملة:
        1. Retest: السعر لمس مستوى الكسر ثم ارتد
        2. شمعة تأكيد: Bullish/Bearish Engulfing أو رفض واضح
        3. Volume مستقر أو صاعد
        4. OI يستمر (لا ينهار)
        """
        if not ohlcv or len(ohlcv) < 3:
            return False

        curr          = ohlcv[-1]
        current_price = curr['close']
        break_level   = setup.break_level
        direction     = "LONG" if setup.setup_type in (
            LBCSetupType.FAKE_BREAK_BUY, LBCSetupType.BREAKOUT_BUY
        ) else "SHORT"

        candles = ohlcv[-10:]
        avg_vol = np.mean([c['volume'] for c in candles[:-1]]) if len(candles) > 1 else 1

        # ── 1. فحص الـ Retest ──
        retest_ok = False
        if direction == "LONG":
            # السعر يجب أن يلمس مستوى الكسر من فوق ثم يرتد
            recent_low  = min(c['low'] for c in ohlcv[-RETEST_WINDOW_CANDLES:])
            retest_zone_low  = break_level * (1 - RETEST_ZONE_WIDTH)
            retest_zone_high = break_level * (1 + RETEST_ZONE_WIDTH)
            touched = retest_zone_low <= recent_low <= retest_zone_high
            bounced = current_price >= recent_low * (1 + RETEST_BOUNCE_MIN)
            retest_ok = touched and bounced
        else:
            # SHORT: السعر يلمس مستوى الكسر من تحت ثم يهبط
            recent_high = max(c['high'] for c in ohlcv[-RETEST_WINDOW_CANDLES:])
            retest_zone_low  = break_level * (1 - RETEST_ZONE_WIDTH)
            retest_zone_high = break_level * (1 + RETEST_ZONE_WIDTH)
            touched = retest_zone_low <= recent_high <= retest_zone_high
            bounced = current_price <= recent_high * (1 - RETEST_BOUNCE_MIN)
            retest_ok = touched and bounced

        if not retest_ok:
            logger.debug(f"LBC {symbol}: Retest لم يكتمل بعد")
            return False

        # ── 2. شمعة التأكيد ──
        prev  = ohlcv[-2]
        body  = abs(curr['close'] - curr['open'])
        range_ = curr['high'] - curr['low']
        confirm_candle = False

        if direction == "LONG":
            # Bullish Engulfing أو شمعة صاعدة قوية
            bullish_engulf = (curr['close'] > curr['open'] and
                              curr['close'] > prev['high'] and
                              curr['open']  < prev['close'])
            strong_bull    = (curr['close'] > curr['open'] and
                              body >= range_ * 0.6)
            confirm_candle = bullish_engulf or strong_bull
        else:
            # Bearish Engulfing أو شمعة هابطة قوية
            bearish_engulf = (curr['close'] < curr['open'] and
                              curr['close'] < prev['low'] and
                              curr['open']  > prev['close'])
            strong_bear    = (curr['close'] < curr['open'] and
                              body >= range_ * 0.6)
            confirm_candle = bearish_engulf or strong_bear

        if not confirm_candle:
            logger.debug(f"LBC {symbol}: شمعة التأكيد لم تظهر بعد")
            return False

        # ── 3. Volume مناسب ──
        vol_ok = curr['volume'] >= avg_vol * CONFIRM_VOLUME_MULT
        if not vol_ok:
            logger.debug(f"LBC {symbol}: Volume ضعيف ({curr['volume']:.0f} vs avg {avg_vol:.0f})")
            return False

        # ── 4. OI من CoinGlass ──
        oi_change = cg_data.get("oi_change_1h", 0)
        oi_ok     = oi_change >= CONFIRM_OI_MIN_CHANGE
        if not oi_ok:
            logger.debug(f"LBC {symbol}: OI ينهار ({oi_change:.3%}) → رفض التأكيد")
            return False

        # ── 5. Funding Rate طبيعي ──
        funding = cg_data.get("funding_rate", 0)
        if direction == "LONG" and funding > 0.01:  # 1% = مرتفع جداً
            logger.debug(f"LBC {symbol}: Funding مرتفع جداً ({funding:.4f}%) → رفض Long")
            return False
        if direction == "SHORT" and funding < -0.01:
            logger.debug(f"LBC {symbol}: Funding سلبي جداً ({funding:.4f}%) → رفض Short")
            return False

        logger.info(
            f"✅ LBC {symbol}: تأكيد مكتمل! "
            f"Retest ✓ | Candle ✓ | Volume ✓ | OI={oi_change:.3%} ✓ | Funding={funding:.4f}%"
        )
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # فحص إلغاء الصفقة بعد الدخول
    # ══════════════════════════════════════════════════════════════════════════

    def should_cancel_trade(self, symbol: str, entry_price: float,
                             current_price: float, break_level: float,
                             direction: str, cg_data: dict) -> tuple[bool, str]:
        """
        يفحص شروط إلغاء الصفقة بعد الدخول:
        - OI انخفض أكثر من 2%
        - Volume ضعيف عند الاختراق
        - السعر رجع داخل النطاق
        - شموع رفض متكررة ضد الاتجاه
        """
        oi_change = cg_data.get("oi_change_1h", 0)
        if oi_change <= CANCEL_OI_DROP_PCT:
            return True, f"OI انهار ({oi_change:.3%}) بعد الدخول"

        if direction == "LONG":
            # السعر رجع تحت مستوى الكسر
            if current_price < break_level * (1 - CANCEL_PRICE_RETURN_PCT):
                return True, f"السعر رجع تحت مستوى الكسر ({break_level:.6f})"
        else:
            if current_price > break_level * (1 + CANCEL_PRICE_RETURN_PCT):
                return True, f"السعر رجع فوق مستوى الكسر ({break_level:.6f})"

        return False, ""

    # ══════════════════════════════════════════════════════════════════════════
    # الدالة الرئيسية: scan_symbol
    # ══════════════════════════════════════════════════════════════════════════

    def scan_symbol(self, symbol: str) -> Optional[dict]:
        """
        يفحص عملة واحدة عبر المراحل الثلاث.
        يُعيد إعداد جاهز للدخول أو None.

        الإعداد المُعاد:
        {
            "symbol":      str,
            "type":        LBCSetupType,
            "direction":   "LONG" | "SHORT",
            "entry_price": float,
            "sl":          float,
            "tp1":         float,
            "tp2":         float,
            "tp3":         float,
            "confidence":  float (0-100),
            "reasons":     list[str],
        }
        """
        try:
            # ── فحص اتجاه BTC ──
            btc_condition = self._check_btc_market_condition()
            if btc_condition == "CHAOTIC":
                logger.debug(f"LBC {symbol}: BTC في فوضى → تخطي")
                return None

            # ── شرط EMA50 على 4H (فلتر التريند الإلزامي) ──
            # درس مستفاد: لا دخول شراء إذا كان السعر تحت EMA50 على 4H (تريند هابط)
            try:
                ohlcv_4h_raw = self.okx.get_ohlcv(symbol, timeframe="4h", limit=60)
                if ohlcv_4h_raw and len(ohlcv_4h_raw) >= 50:
                    closes_4h = [c[4] if isinstance(c, (list, tuple)) else c['close'] for c in ohlcv_4h_raw]
                    k4 = 2 / (50 + 1)
                    ema50_4h = closes_4h[0]
                    for cv in closes_4h[1:]:
                        ema50_4h = cv * k4 + ema50_4h * (1 - k4)
                    current_p = closes_4h[-1]
                    if current_p < ema50_4h:
                        logger.debug(f"LBC {symbol}: سعر ({current_p:.6f}) تحت EMA50 4H ({ema50_4h:.6f}) — لا دخول شراء")
                        return None
            except Exception:
                pass  # عند الخطأ، لا نمنع الدخول
            # ── جلب OHLCV (1H للتحليل الرئيسي) ──
            ohlcv_raw = self.okx.get_ohlcv(symbol, timeframe="1h", limit=60)
            if not ohlcv_raw or len(ohlcv_raw) < 20:
                return None
            ohlcv_1h = self._normalize_ohlcv(ohlcv_raw)
            if len(ohlcv_1h) < 20:
                return None

            # ── المرحلة 1: مناطق السيولة ──
            zones = self._find_liquidity_zones(ohlcv_1h)
            if not zones["resistance_zones"] and not zones["support_zones"]:
                logger.debug(f"LBC {symbol}: لا مناطق سيولة واضحة")
                return None

            # ── المرحلة 2: كشف الكسر ──
            # فحص الإعدادات المعلَّقة أولاً (Breakout ينتظر Retest)
            if symbol in self.pending_setups:
                setup = self.pending_setups[symbol]
                setup.candles_waited += 1

                # انتهت نافذة الانتظار؟
                if setup.candles_waited > RETEST_WINDOW_CANDLES:
                    logger.info(f"LBC {symbol}: انتهت نافذة الـ Retest → إلغاء الإعداد")
                    del self.pending_setups[symbol]
                    return None

                # جلب بيانات CoinGlass
                cg_data = self._get_coinglass_data(symbol)

                # فحص التأكيد
                if self._check_confirmation(symbol, setup, ohlcv_1h, cg_data):
                    del self.pending_setups[symbol]
                    current_price = ohlcv_1h[-1]['close']
                    confidence    = self._calculate_confidence(setup, cg_data, btc_condition)
                    reasons       = self._build_reasons(setup, cg_data, btc_condition)
                    return {
                        "symbol":      symbol,
                        "type":        setup.setup_type,
                        "direction":   "LONG" if setup.setup_type in (
                            LBCSetupType.FAKE_BREAK_BUY, LBCSetupType.BREAKOUT_BUY
                        ) else "SHORT",
                        "entry_price": current_price,
                        "sl":          setup.sl,
                        "tp1":         setup.tp1,
                        "tp2":         setup.tp2,
                        "tp3":         setup.tp3,
                        "confidence":  confidence,
                        "reasons":     reasons,
                        "btc_condition": btc_condition,
                    }
                return None  # لا يزال ينتظر

            # ── كشف كسر جديد ──
            break_info = self._detect_break(ohlcv_1h, zones)
            if not break_info:
                return None

            # جلب بيانات CoinGlass للتحقق من OI عند الكسر
            cg_data = self._get_coinglass_data(symbol)

            # Fake Break: يحتاج تأكيد فوري (لا Retest منفصل)
            if break_info["type"] in (LBCSetupType.FAKE_BREAK_BUY, LBCSetupType.FAKE_BREAK_SELL):
                # تحقق من OI عند الكسر الكاذب
                oi_change = cg_data.get("oi_change_1h", 0)
                if oi_change < CONFIRM_OI_MIN_CHANGE:
                    logger.debug(f"LBC {symbol}: Fake Break لكن OI ينهار → تخطي")
                    return None

                current_price = ohlcv_1h[-1]['close']
                setup_state = LBCState(
                    symbol=symbol,
                    setup_type=break_info["type"],
                    break_level=break_info["break_level"],
                    sl=break_info["sl"],
                    tp1=break_info["tp1"],
                    tp2=break_info["tp2"],
                    tp3=break_info["tp3"],
                    detected_at=datetime.now(),
                )
                # Fake Break يُعيد النتيجة مباشرة إذا اكتمل التأكيد
                if self._check_confirmation(symbol, setup_state, ohlcv_1h, cg_data):
                    confidence = self._calculate_confidence(setup_state, cg_data, btc_condition)
                    reasons    = self._build_reasons(setup_state, cg_data, btc_condition)
                    direction  = "LONG" if break_info["type"] == LBCSetupType.FAKE_BREAK_BUY else "SHORT"
                    logger.info(
                        f"🎯 LBC {symbol}: إعداد {break_info['type']} مكتمل! "
                        f"Entry={current_price:.6f} | SL={break_info['sl']:.6f} | "
                        f"TP1={break_info['tp1']:.6f} | Confidence={confidence:.0f}%"
                    )
                    return {
                        "symbol":      symbol,
                        "type":        break_info["type"],
                        "direction":   direction,
                        "entry_price": current_price,
                        "sl":          break_info["sl"],
                        "tp1":         break_info["tp1"],
                        "tp2":         break_info["tp2"],
                        "tp3":         break_info["tp3"],
                        "confidence":  confidence,
                        "reasons":     reasons,
                        "btc_condition": btc_condition,
                    }

            # Breakout حقيقي: يحتاج Retest → يُحفظ في pending
            elif break_info.get("needs_retest"):
                # تحقق من OI عند الكسر
                oi_change = cg_data.get("oi_change_1h", 0)
                if oi_change < REAL_BREAK_OI_CHANGE:
                    logger.debug(
                        f"LBC {symbol}: Breakout لكن OI لم يرتفع "
                        f"({oi_change:.3%} < {REAL_BREAK_OI_CHANGE:.3%}) → تخطي"
                    )
                    return None

                self.pending_setups[symbol] = LBCState(
                    symbol=symbol,
                    setup_type=break_info["type"],
                    break_level=break_info["break_level"],
                    sl=break_info["sl"],
                    tp1=break_info["tp1"],
                    tp2=break_info["tp2"],
                    tp3=break_info["tp3"],
                    detected_at=datetime.now(),
                )
                logger.info(
                    f"⏳ LBC {symbol}: Breakout مكتشف عند {break_info['break_level']:.6f} "
                    f"→ انتظار Retest (نافذة {RETEST_WINDOW_CANDLES} شمعة)"
                )

        except Exception as e:
            import traceback
            logger.error(f"❌ LBC scan_symbol({symbol}): {e}\n{traceback.format_exc()}")

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # دوال مساعدة
    # ══════════════════════════════════════════════════════════════════════════

    def _get_coinglass_data(self, symbol: str) -> dict:
        """جلب بيانات CoinGlass الضرورية للتحقق"""
        clean = symbol.replace("/USDT", "").replace("-USDT", "").upper()
        try:
            oi_data      = self.cg.get_open_interest(clean)
            funding_rate = self.cg.get_funding_rate_v2(clean)
            if funding_rate == 0.0:
                funding_rate = self.cg.get_funding_rate(clean)
            liq_data     = self.cg.get_liquidation_data(clean)
            return {
                "oi_change_1h":  oi_data.get("change_1h", 0),
                "oi_change_4h":  oi_data.get("change_4h", 0),
                "oi_current":    oi_data.get("current", 0),
                "funding_rate":  funding_rate,
                "liq_long_1h":   liq_data.get("long_1h", 0),
                "liq_short_1h":  liq_data.get("short_1h", 0),
                "liq_long_24h":  liq_data.get("long_24h", 0),
                "liq_short_24h": liq_data.get("short_24h", 0),
            }
        except Exception as e:
            logger.warning(f"⚠️ LBC: فشل جلب CoinGlass لـ {symbol}: {e}")
            return {
                "oi_change_1h": 0, "oi_change_4h": 0, "oi_current": 0,
                "funding_rate": 0, "liq_long_1h": 0, "liq_short_1h": 0,
                "liq_long_24h": 0, "liq_short_24h": 0,
            }

    def _calculate_confidence(self, setup: LBCState, cg_data: dict,
                               btc_condition: str) -> float:
        """
        حساب نسبة الثقة (0-100) بناءً على:
        - نوع الإعداد
        - قوة منطقة السيولة
        - OI وFunding
        - اتجاه BTC
        """
        score = 50.0  # قاعدة

        # نوع الإعداد
        if setup.setup_type in (LBCSetupType.FAKE_BREAK_BUY, LBCSetupType.FAKE_BREAK_SELL):
            score += 10  # Fake Break أكثر موثوقية
        else:
            score += 5   # Breakout + Retest

        # OI صاعد
        oi = cg_data.get("oi_change_1h", 0)
        if oi > 0.02:
            score += 15
        elif oi > 0.005:
            score += 8
        elif oi > 0:
            score += 3

        # Funding طبيعي
        funding = abs(cg_data.get("funding_rate", 0))
        if funding < 0.001:
            score += 10  # طبيعي جداً
        elif funding < 0.003:
            score += 5

        # اتجاه BTC
        if btc_condition == "UPTREND":
            score += 10
        elif btc_condition == "RANGE":
            score += 5
        elif btc_condition == "DOWNTREND":
            score -= 10

        # سيولة قريبة تُستهدف
        direction = "LONG" if setup.setup_type in (
            LBCSetupType.FAKE_BREAK_BUY, LBCSetupType.BREAKOUT_BUY
        ) else "SHORT"
        liq_long  = cg_data.get("liq_long_1h", 0)
        liq_short = cg_data.get("liq_short_1h", 0)
        if direction == "LONG" and liq_short > liq_long * 1.5:
            score += 5  # سيولة Short تُستهدف = دعم للصعود
        elif direction == "SHORT" and liq_long > liq_short * 1.5:
            score += 5

        return min(max(score, 30), 95)

    def _build_reasons(self, setup: LBCState, cg_data: dict,
                       btc_condition: str) -> list:
        """بناء قائمة أسباب الدخول"""
        reasons = []
        type_map = {
            LBCSetupType.FAKE_BREAK_BUY:  "Fake Break تحت الدعم (اصطياد سيولة) → شراء",
            LBCSetupType.FAKE_BREAK_SELL: "Fake Break فوق المقاومة (اصطياد سيولة) → بيع",
            LBCSetupType.BREAKOUT_BUY:    "Breakout حقيقي فوق المقاومة + Retest → شراء",
            LBCSetupType.BREAKOUT_SELL:   "Breakout حقيقي تحت الدعم + Retest → بيع",
        }
        reasons.append(type_map.get(setup.setup_type, "LBC Setup"))
        reasons.append(f"BTC: {btc_condition}")

        oi = cg_data.get("oi_change_1h", 0)
        reasons.append(f"OI 1h: {oi:+.2%}")

        funding = cg_data.get("funding_rate", 0)
        reasons.append(f"Funding: {funding:.4f}%")

        liq_long  = cg_data.get("liq_long_1h", 0)
        liq_short = cg_data.get("liq_short_1h", 0)
        if liq_long > 0 or liq_short > 0:
            reasons.append(
                f"تصفيات 1h: Long=${liq_long:,.0f} | Short=${liq_short:,.0f}"
            )

        return reasons

    # ══════════════════════════════════════════════════════════════════════════
    # الدالة الرئيسية: scan_all
    # ══════════════════════════════════════════════════════════════════════════

    def scan_all(self, symbols: list) -> list:
        """
        يفحص قائمة العملات ويُعيد قائمة الإعدادات الجاهزة للدخول.
        مرتبة حسب الثقة تنازلياً.
        """
        results = []
        logger.info(f"🔎 LBC scan: {len(symbols)} عملة...")

        for symbol in symbols:
            setup = self.scan_symbol(symbol)
            if setup:
                results.append(setup)
                logger.info(
                    f"🎯 LBC إعداد: {symbol} | {setup['type']} | "
                    f"Confidence={setup['confidence']:.0f}% | "
                    f"Entry={setup['entry_price']:.6f}"
                )

        results.sort(key=lambda x: x["confidence"], reverse=True)
        logger.info(f"✅ LBC scan انتهى: {len(results)} إعداد جاهز")
        return results
