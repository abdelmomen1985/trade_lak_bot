"""
fake_break_detector.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
استراتيجية: دعم + كسر كاذب + تأكيد (Fake Break / Liquidity Grab)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

المنطق الأساسي:
1. تحديد الاتجاه (4H/1H): صاعد → نبحث عن شراء فقط
2. رسم منطقة S/R: آخر قاع قوي = دعم، آخر قمة قوية = مقاومة
3. كشف Liquidity Grab: السعر يخترق المنطقة ثم يرجع بسرعة
4. تأكيد الشمعة: ابتلاعية أو ذيل طويل أو إغلاق قوي داخل المنطقة
5. الدخول بعد إغلاق شمعة التأكيد فقط

الوزن في weighted_score: 0.30 (30%) — أعلى وزن في النظام
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# ثوابت الاستراتيجية
# ══════════════════════════════════════════════════════════════════

# نسبة اختراق المنطقة المسموح بها (Fake Break)
FAKE_BREAK_MIN_PCT = 0.001   # 0.1% أدنى حد للاختراق (يُعدّ اختراقاً حقيقياً)
FAKE_BREAK_MAX_PCT = 0.025   # 2.5% أقصى حد (أكثر من ذلك = اختراق حقيقي)

# عرض منطقة S/R كنسبة من السعر
SR_ZONE_WIDTH_PCT = 0.008    # 0.8% عرض المنطقة

# الحد الأدنى لطول الذيل كنسبة من جسم الشمعة
TAIL_RATIO_MIN = 1.5         # الذيل يجب أن يكون 1.5× الجسم على الأقل

# عدد الشموع للنظر خلفاً لتحديد S/R
SR_LOOKBACK = 50             # 50 شمعة للخلف

# عدد الشموع لتحديد الاتجاه
TREND_LOOKBACK = 20          # 20 شمعة لتحديد الاتجاه

# الحد الأدنى لقوة منطقة S/R (عدد مرات الارتداد)
MIN_SR_TOUCHES = 2           # يجب أن تُختبر المنطقة مرتين على الأقل


class FakeBreakDetector:
    """
    كاشف الكسر الكاذب (Liquidity Grab) — قلب استراتيجية Trade Lak

    يكشف عن:
    - Liquidity Grab عند الدعم (فرصة شراء)
    - Liquidity Grab عند المقاومة (فرصة بيع)
    - قوة منطقة S/R
    - تأكيد الشمعة الانعكاسية
    """

    def __init__(self):
        self.name = "FakeBreakDetector"

    # ══════════════════════════════════════════════════════════════
    # الدالة الرئيسية
    # ══════════════════════════════════════════════════════════════

    def analyze(self, ohlcv: List[Dict]) -> Dict:
        """
        التحليل الكامل للاستراتيجية

        Args:
            ohlcv: قائمة شموع بتنسيق {'open', 'high', 'low', 'close', 'volume', 'timestamp'}

        Returns:
            {
                'signal': 1 (شراء) | -1 (بيع) | 0 (انتظار),
                'score': -1.0 إلى +1.0,
                'confidence': 0-100,
                'direction': 'LONG' | 'SHORT' | 'NEUTRAL',
                'fake_break_detected': bool,
                'sr_zone': {'support': float, 'resistance': float},
                'entry_price': float,
                'stop_loss': float,
                'tp1': float, 'tp2': float, 'tp3': float,
                'reason': str,
                'details': dict
            }
        """
        if not ohlcv or len(ohlcv) < 30:
            return self._neutral("بيانات غير كافية")

        try:
            # 1. تحديد الاتجاه
            trend = self._detect_trend(ohlcv)

            # 2. رسم منطقة S/R
            sr_zones = self._find_sr_zones(ohlcv)
            if not sr_zones:
                return self._neutral("لا توجد مناطق S/R واضحة")

            # 3. كشف Liquidity Grab
            current_candle = ohlcv[-1]
            prev_candle = ohlcv[-2]
            current_price = current_candle['close']

            grab_result = self._detect_liquidity_grab(
                ohlcv, sr_zones, trend
            )

            if not grab_result['detected']:
                return self._neutral(
                    f"لا يوجد Liquidity Grab | اتجاه: {trend['direction']}",
                    extra={'trend': trend, 'sr_zones': sr_zones}
                )

            # 4. تأكيد الشمعة
            confirmation = self._confirm_candle(
                ohlcv, grab_result['zone_type']
            )

            if not confirmation['confirmed']:
                return self._neutral(
                    f"Liquidity Grab موجود لكن لا تأكيد شمعة | {confirmation['reason']}",
                    extra={'trend': trend, 'grab': grab_result}
                )

            # 5. حساب الدخول والأهداف
            entry_data = self._calculate_entry(
                ohlcv, grab_result, sr_zones, trend
            )

            # 6. حساب النقاط والثقة
            score, confidence = self._calculate_score(
                trend, grab_result, confirmation, sr_zones
            )

            signal = 1 if grab_result['zone_type'] == 'support' else -1

            reason = (
                f"✅ Liquidity Grab عند {'الدعم' if signal == 1 else 'المقاومة'} | "
                f"اتجاه: {trend['direction']} | "
                f"تأكيد: {confirmation['candle_type']} | "
                f"قوة المنطقة: {grab_result['zone_strength']}x"
            )

            logger.info(f"🎯 FakeBreak: {reason} | نقاط={score:.2f} | ثقة={confidence:.0f}%")

            return {
                'signal': signal,
                'score': score,
                'confidence': confidence,
                'direction': 'LONG' if signal == 1 else 'SHORT',
                'fake_break_detected': True,
                'sr_zone': sr_zones,
                'entry_price': entry_data['entry'],
                'stop_loss': entry_data['stop_loss'],
                'tp1': entry_data['tp1'],
                'tp2': entry_data['tp2'],
                'tp3': entry_data['tp3'],
                'reason': reason,
                'details': {
                    'trend': trend,
                    'grab': grab_result,
                    'confirmation': confirmation,
                    'entry_data': entry_data,
                }
            }

        except Exception as e:
            logger.error(f"❌ FakeBreakDetector error: {e}")
            return self._neutral(f"خطأ: {e}")

    # ══════════════════════════════════════════════════════════════
    # 1. تحديد الاتجاه
    # ══════════════════════════════════════════════════════════════

    def _detect_trend(self, ohlcv: List[Dict]) -> Dict:
        """
        تحديد الاتجاه: صاعد / هابط / عرضي
        يعتمد على: قمم وقيعان متصاعدة/متنازلة + EMA
        """
        candles = ohlcv[-TREND_LOOKBACK:]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]

        # EMA 20
        ema = self._ema(closes, 20)
        current_price = closes[-1]

        # تحليل القمم والقيعان
        swing_highs = self._find_swing_highs(highs)
        swing_lows = self._find_swing_lows(lows)

        uptrend_score = 0
        downtrend_score = 0

        # قمم أعلى = صاعد
        if len(swing_highs) >= 2 and swing_highs[-1] > swing_highs[-2]:
            uptrend_score += 2
        elif len(swing_highs) >= 2 and swing_highs[-1] < swing_highs[-2]:
            downtrend_score += 2

        # قيعان أعلى = صاعد
        if len(swing_lows) >= 2 and swing_lows[-1] > swing_lows[-2]:
            uptrend_score += 2
        elif len(swing_lows) >= 2 and swing_lows[-1] < swing_lows[-2]:
            downtrend_score += 2

        # السعر فوق EMA = صاعد
        if current_price > ema:
            uptrend_score += 1
        else:
            downtrend_score += 1

        # تغيير السعر خلال الفترة
        price_change_pct = (closes[-1] - closes[0]) / closes[0] * 100
        if price_change_pct > 2:
            uptrend_score += 1
        elif price_change_pct < -2:
            downtrend_score += 1

        if uptrend_score >= 4:
            direction = 'UPTREND'
        elif downtrend_score >= 4:
            direction = 'DOWNTREND'
        else:
            direction = 'SIDEWAYS'

        return {
            'direction': direction,
            'uptrend_score': uptrend_score,
            'downtrend_score': downtrend_score,
            'ema': ema,
            'price_change_pct': price_change_pct,
            'swing_highs': swing_highs[-3:] if swing_highs else [],
            'swing_lows': swing_lows[-3:] if swing_lows else [],
        }

    # ══════════════════════════════════════════════════════════════
    # 2. رسم مناطق S/R
    # ══════════════════════════════════════════════════════════════

    def _find_sr_zones(self, ohlcv: List[Dict]) -> Optional[Dict]:
        """
        إيجاد أقوى منطقة دعم ومقاومة
        يعتمد على: أعلى قمة وأدنى قاع مع عدد مرات الاختبار
        """
        candles = ohlcv[-SR_LOOKBACK:]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        current_price = ohlcv[-1]['close']

        # إيجاد أقوى مستويات الدعم والمقاومة
        swing_highs = self._find_swing_highs(highs, window=3)
        swing_lows = self._find_swing_lows(lows, window=3)

        if not swing_highs or not swing_lows:
            return None

        # أقرب مقاومة فوق السعر الحالي
        resistances_above = [h for h in swing_highs if h > current_price * 1.001]
        # أقرب دعم تحت السعر الحالي
        supports_below = [l for l in swing_lows if l < current_price * 0.999]

        if not resistances_above or not supports_below:
            return None

        nearest_resistance = min(resistances_above)
        nearest_support = max(supports_below)

        # حساب عرض المنطقة
        support_zone_top = nearest_support * (1 + SR_ZONE_WIDTH_PCT)
        support_zone_bottom = nearest_support * (1 - SR_ZONE_WIDTH_PCT)
        resistance_zone_top = nearest_resistance * (1 + SR_ZONE_WIDTH_PCT)
        resistance_zone_bottom = nearest_resistance * (1 - SR_ZONE_WIDTH_PCT)

        # حساب قوة المنطقة (عدد مرات الاختبار)
        support_touches = sum(
            1 for l in swing_lows
            if support_zone_bottom <= l <= support_zone_top
        )
        resistance_touches = sum(
            1 for h in swing_highs
            if resistance_zone_bottom <= h <= resistance_zone_top
        )

        return {
            'support': nearest_support,
            'support_zone': (support_zone_bottom, support_zone_top),
            'support_touches': support_touches,
            'resistance': nearest_resistance,
            'resistance_zone': (resistance_zone_bottom, resistance_zone_top),
            'resistance_touches': resistance_touches,
            'sr_ratio': (nearest_resistance - nearest_support) / nearest_support * 100,
        }

    # ══════════════════════════════════════════════════════════════
    # 3. كشف Liquidity Grab
    # ══════════════════════════════════════════════════════════════

    def _detect_liquidity_grab(
        self, ohlcv: List[Dict], sr_zones: Dict, trend: Dict
    ) -> Dict:
        """
        كشف Liquidity Grab (الكسر الكاذب)

        شراء: السعر ينزل تحت الدعم ثم يرجع فوقه
        بيع: السعر يرتفع فوق المقاومة ثم يرجع تحتها
        """
        # فحص آخر 3 شموع
        recent = ohlcv[-4:]
        if len(recent) < 3:
            return {'detected': False, 'reason': 'بيانات غير كافية'}

        current = recent[-1]
        prev1 = recent[-2]
        prev2 = recent[-3]

        support = sr_zones['support']
        resistance = sr_zones['resistance']
        support_bottom = sr_zones['support_zone'][0]
        resistance_top = sr_zones['resistance_zone'][1]

        # ── فحص Liquidity Grab عند الدعم (فرصة شراء) ──
        if trend['direction'] in ('UPTREND', 'SIDEWAYS'):
            # الشمعة السابقة أو قبلها اخترقت الدعم
            for check_candle in [prev1, prev2]:
                broke_below = check_candle['low'] < support_bottom
                if broke_below:
                    # حساب نسبة الاختراق
                    break_pct = (support_bottom - check_candle['low']) / support_bottom

                    # الاختراق يجب أن يكون في النطاق المسموح
                    if FAKE_BREAK_MIN_PCT <= break_pct <= FAKE_BREAK_MAX_PCT:
                        # السعر الحالي عاد فوق الدعم
                        if current['close'] > support:
                            zone_strength = sr_zones.get('support_touches', 1)
                            return {
                                'detected': True,
                                'zone_type': 'support',
                                'break_pct': break_pct * 100,
                                'zone_level': support,
                                'zone_strength': zone_strength,
                                'grab_low': check_candle['low'],
                                'recovery_close': current['close'],
                                'reason': f"اختراق دعم {break_pct*100:.2f}% ثم عودة"
                            }

        # ── فحص Liquidity Grab عند المقاومة (فرصة بيع) ──
        if trend['direction'] in ('DOWNTREND', 'SIDEWAYS'):
            for check_candle in [prev1, prev2]:
                broke_above = check_candle['high'] > resistance_top
                if broke_above:
                    break_pct = (check_candle['high'] - resistance_top) / resistance_top

                    if FAKE_BREAK_MIN_PCT <= break_pct <= FAKE_BREAK_MAX_PCT:
                        if current['close'] < resistance:
                            zone_strength = sr_zones.get('resistance_touches', 1)
                            return {
                                'detected': True,
                                'zone_type': 'resistance',
                                'break_pct': break_pct * 100,
                                'zone_level': resistance,
                                'zone_strength': zone_strength,
                                'grab_high': check_candle['high'],
                                'recovery_close': current['close'],
                                'reason': f"اختراق مقاومة {break_pct*100:.2f}% ثم عودة"
                            }

        return {'detected': False, 'reason': 'لا يوجد Liquidity Grab في آخر 3 شموع'}

    # ══════════════════════════════════════════════════════════════
    # 4. تأكيد الشمعة
    # ══════════════════════════════════════════════════════════════

    def _confirm_candle(self, ohlcv: List[Dict], zone_type: str) -> Dict:
        """
        تأكيد الشمعة الانعكاسية:
        - ابتلاعية Engulfing
        - ذيل طويل Pin Bar
        - إغلاق قوي داخل المنطقة
        """
        current = ohlcv[-1]
        prev = ohlcv[-2]

        open_c = current['open']
        close_c = current['close']
        high_c = current['high']
        low_c = current['low']
        body = abs(close_c - open_c)
        candle_range = high_c - low_c

        if candle_range == 0:
            return {'confirmed': False, 'reason': 'شمعة دوجي'}

        if zone_type == 'support':
            # نبحث عن شمعة صاعدة
            lower_wick = open_c - low_c if close_c >= open_c else close_c - low_c
            upper_wick = high_c - max(open_c, close_c)

            # 1. Pin Bar: ذيل سفلي طويل
            if lower_wick > 0 and body > 0:
                tail_ratio = lower_wick / body
                if tail_ratio >= TAIL_RATIO_MIN and close_c > open_c:
                    return {
                        'confirmed': True,
                        'candle_type': f'Pin Bar صاعد (ذيل={tail_ratio:.1f}x)',
                        'strength': min(tail_ratio / 2, 1.0)
                    }

            # 2. Engulfing صاعد
            prev_body = abs(prev['close'] - prev['open'])
            if (close_c > open_c and  # شمعة خضراء
                prev['close'] < prev['open'] and  # الشمعة السابقة حمراء
                close_c > prev['open'] and  # إغلاق فوق فتح السابقة
                open_c < prev['close'] and  # فتح تحت إغلاق السابقة
                body > prev_body * 0.8):  # الجسم أكبر من السابقة
                return {
                    'confirmed': True,
                    'candle_type': 'ابتلاعية صاعدة',
                    'strength': min(body / prev_body, 1.0)
                }

            # 3. إغلاق قوي داخل المنطقة (جسم > 60% من النطاق)
            body_pct = body / candle_range
            if close_c > open_c and body_pct >= 0.6:
                return {
                    'confirmed': True,
                    'candle_type': f'إغلاق قوي ({body_pct*100:.0f}%)',
                    'strength': body_pct
                }

        elif zone_type == 'resistance':
            # نبحث عن شمعة هابطة
            upper_wick = high_c - max(open_c, close_c)
            lower_wick = min(open_c, close_c) - low_c

            # 1. Pin Bar: ذيل علوي طويل
            if upper_wick > 0 and body > 0:
                tail_ratio = upper_wick / body
                if tail_ratio >= TAIL_RATIO_MIN and close_c < open_c:
                    return {
                        'confirmed': True,
                        'candle_type': f'Pin Bar هابط (ذيل={tail_ratio:.1f}x)',
                        'strength': min(tail_ratio / 2, 1.0)
                    }

            # 2. Engulfing هابط
            prev_body = abs(prev['close'] - prev['open'])
            if (close_c < open_c and  # شمعة حمراء
                prev['close'] > prev['open'] and  # الشمعة السابقة خضراء
                close_c < prev['open'] and
                open_c > prev['close'] and
                body > prev_body * 0.8):
                return {
                    'confirmed': True,
                    'candle_type': 'ابتلاعية هابطة',
                    'strength': min(body / prev_body, 1.0)
                }

            # 3. إغلاق قوي هابط
            body_pct = body / candle_range
            if close_c < open_c and body_pct >= 0.6:
                return {
                    'confirmed': True,
                    'candle_type': f'إغلاق هابط قوي ({body_pct*100:.0f}%)',
                    'strength': body_pct
                }

        return {'confirmed': False, 'reason': 'لا تأكيد شمعة انعكاسية'}

    # ══════════════════════════════════════════════════════════════
    # 5. حساب الدخول والأهداف
    # ══════════════════════════════════════════════════════════════

    def _calculate_entry(
        self, ohlcv: List[Dict], grab: Dict, sr_zones: Dict, trend: Dict
    ) -> Dict:
        """
        حساب نقطة الدخول، وقف الخسارة، والأهداف الثلاثة
        """
        current_price = ohlcv[-1]['close']
        zone_type = grab['zone_type']

        if zone_type == 'support':
            entry = current_price  # الدخول بعد إغلاق شمعة التأكيد
            # وقف الخسارة: خلف الذيل + مسافة أمان 0.3%
            grab_low = grab.get('grab_low', sr_zones['support_zone'][0])
            stop_loss = grab_low * (1 - 0.003)

            # الأهداف
            resistance = sr_zones['resistance']
            move_size = resistance - entry
            tp1 = entry + move_size * 0.30   # 30% من الحركة
            tp2 = entry + move_size * 0.60   # 60% من الحركة
            tp3 = resistance * 0.998          # قبل المقاومة بقليل

        else:  # resistance
            entry = current_price
            grab_high = grab.get('grab_high', sr_zones['resistance_zone'][1])
            stop_loss = grab_high * (1 + 0.003)

            support = sr_zones['support']
            move_size = entry - support
            tp1 = entry - move_size * 0.30
            tp2 = entry - move_size * 0.60
            tp3 = support * 1.002

        # حساب Risk/Reward
        risk = abs(entry - stop_loss)
        reward_tp1 = abs(tp1 - entry)
        rr_ratio = reward_tp1 / risk if risk > 0 else 0

        return {
            'entry': entry,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'risk_pct': abs(entry - stop_loss) / entry * 100,
            'rr_ratio': rr_ratio,
        }

    # ══════════════════════════════════════════════════════════════
    # 6. حساب النقاط والثقة
    # ══════════════════════════════════════════════════════════════

    def _calculate_score(
        self, trend: Dict, grab: Dict, confirmation: Dict, sr_zones: Dict
    ) -> Tuple[float, float]:
        """
        حساب النقاط النهائية (−1 إلى +1) والثقة (0−100%)
        """
        score = 0.0
        confidence_factors = []

        # 1. قوة الاتجاه (30% من النقاط)
        if trend['direction'] == 'UPTREND' and grab['zone_type'] == 'support':
            score += 0.30
            confidence_factors.append(30)
        elif trend['direction'] == 'DOWNTREND' and grab['zone_type'] == 'resistance':
            score += 0.30
            confidence_factors.append(30)
        elif trend['direction'] == 'SIDEWAYS':
            score += 0.15
            confidence_factors.append(15)
        else:
            # عكس الاتجاه — خصم
            score -= 0.10
            confidence_factors.append(0)

        # 2. قوة الكسر الكاذب (25% من النقاط)
        break_pct = grab.get('break_pct', 0)
        if 0.3 <= break_pct <= 1.5:
            # اختراق مثالي (ليس صغيراً جداً ولا كبيراً جداً)
            score += 0.25
            confidence_factors.append(25)
        elif break_pct > 0:
            score += 0.12
            confidence_factors.append(12)

        # 3. قوة منطقة S/R (20% من النقاط)
        zone_strength = grab.get('zone_strength', 1)
        if zone_strength >= 3:
            score += 0.20
            confidence_factors.append(20)
        elif zone_strength >= 2:
            score += 0.12
            confidence_factors.append(12)
        else:
            score += 0.05
            confidence_factors.append(5)

        # 4. قوة شمعة التأكيد (25% من النقاط)
        candle_strength = confirmation.get('strength', 0)
        score += candle_strength * 0.25
        confidence_factors.append(int(candle_strength * 25))

        # تطبيق الإشارة (شراء = موجب، بيع = سالب)
        if grab['zone_type'] == 'resistance':
            score = -score

        # حساب الثقة
        confidence = sum(confidence_factors) / len(confidence_factors) * 4
        confidence = max(0, min(95, confidence))

        # مكافأة إضافية إذا كل العوامل متوافقة
        if (trend['direction'] != 'SIDEWAYS' and
            break_pct >= 0.3 and
            zone_strength >= 2 and
            candle_strength >= 0.6):
            confidence = min(95, confidence + 10)
            score = score * 1.15 if abs(score) < 1 else score

        return round(score, 3), round(confidence, 1)

    # ══════════════════════════════════════════════════════════════
    # أدوات مساعدة
    # ══════════════════════════════════════════════════════════════

    def _find_swing_highs(self, highs: List[float], window: int = 3) -> List[float]:
        """إيجاد القمم المحورية"""
        swing_highs = []
        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, window+1)):
                swing_highs.append(highs[i])
        return swing_highs

    def _find_swing_lows(self, lows: List[float], window: int = 3) -> List[float]:
        """إيجاد القيعان المحورية"""
        swing_lows = []
        for i in range(window, len(lows) - window):
            if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, window+1)):
                swing_lows.append(lows[i])
        return swing_lows

    def _ema(self, values: List[float], period: int) -> float:
        """حساب EMA"""
        if len(values) < period:
            return values[-1] if values else 0
        k = 2 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1 - k)
        return ema

    def _neutral(self, reason: str, extra: Dict = None) -> Dict:
        """إرجاع نتيجة محايدة"""
        result = {
            'signal': 0,
            'score': 0.0,
            'confidence': 0,
            'direction': 'NEUTRAL',
            'fake_break_detected': False,
            'reason': reason,
        }
        if extra:
            result['details'] = extra
        return result


# ══════════════════════════════════════════════════════════════════
# اختبار سريع
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    def make_candle(open_p, high_p, low_p, close_p, vol=1000):
        return {'open': open_p, 'high': high_p, 'low': low_p, 'close': close_p, 'volume': vol}

    # سيناريو واضح: اتجاه صاعد + Liquidity Grab عند الدعم
    # الاتجاه: قمم وقيعان صاعدة بوضوح
    candles = []
    # بناء اتجاه صاعد واضح: كل 5 شموع ترتفع
    bases = [100, 101, 100.5, 102, 101.5, 103, 102.5, 104, 103.5, 105]
    for b in bases:
        for j in range(4):
            candles.append(make_candle(b+j*0.2, b+j*0.2+0.3, b+j*0.2-0.2, b+j*0.2+0.15))

    # منطقة دعم قوية: 3 ارتدادات عند 100
    candles[2]  = make_candle(100.2, 100.8, 99.8, 100.5)  # ارتداد 1
    candles[6]  = make_candle(100.1, 100.7, 99.9, 100.4)  # ارتداد 2
    candles[10] = make_candle(100.0, 100.6, 99.85, 100.3) # ارتداد 3

    # منطقة مقاومة عند 105
    candles[18] = make_candle(104.8, 105.2, 104.5, 104.9)
    candles[22] = make_candle(104.9, 105.3, 104.6, 105.0)

    # الوضع الحالي: السعر عند ~103
    # Liquidity Grab: اختراق الدعم 100 ثم عودة
    candles[-3] = make_candle(100.5, 100.8, 100.2, 100.6)  # نزول نحو الدعم
    candles[-2] = make_candle(100.3, 100.4, 99.5, 100.2)   # اختراق الدعم (Grab)
    candles[-1] = make_candle(100.2, 101.8, 100.0, 101.6)  # شمعة ابتلاعية صاعدة قوية

    detector = FakeBreakDetector()
    result = detector.analyze(candles)

    print("\n" + "="*60)
    print("🎯 نتيجة FakeBreakDetector:")
    print(f"  الإشارة: {'🟢 شراء' if result['signal']==1 else '🔴 بيع' if result['signal']==-1 else '⚪ انتظار'}")
    print(f"  النقاط: {result['score']}")
    print(f"  الثقة: {result['confidence']}%")
    print(f"  السبب: {result['reason']}")
    if result.get('entry_price'):
        print(f"  الدخول: {result['entry_price']:.4f}")
        print(f"  وقف الخسارة: {result['stop_loss']:.4f}")
        print(f"  TP1: {result['tp1']:.4f} | TP2: {result['tp2']:.4f} | TP3: {result['tp3']:.4f}")
    print("="*60)
