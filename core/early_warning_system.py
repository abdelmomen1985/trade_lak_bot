"""
Early Warning System — نظام الإنذار المبكر للانهيارات
=====================================================
يكتشف 3 مؤشرات تحذيرية تسبق الانهيار بـ 3-5 أيام:

1. OI Divergence Detector     — السعر يصعد لكن OI ينخفض
2. Long/Short Ratio Monitor   — نسبة Long/Short > 2.5 = خطر تصفية جماعية
3. Volume-Price Divergence    — صعود بحجم ضعيف = صعود مصطنع

درس من انهيار أكتوبر-نوفمبر 2025:
- OI بدأ ينخفض قبل السعر بـ 5 أيام
- Funding Rate وصل +0.08% قبل الانهيار بيومين
- Long/Short تجاوز 3:1 قبل التصفية الجماعية
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class WarningLevel(Enum):
    NONE    = "NONE"
    LOW     = "LOW"       # مراقبة
    MEDIUM  = "MEDIUM"    # تحذير — قلل الصفقات
    HIGH    = "HIGH"      # خطر — أوقف الدخول الجديد
    CRITICAL = "CRITICAL" # انهيار وشيك — أغلق الصفقات


@dataclass
class EarlyWarning:
    level: WarningLevel
    score: float                    # 0-100
    indicators_triggered: List[str]
    recommendation: str
    details: Dict
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "score": round(self.score, 1),
            "indicators_triggered": self.indicators_triggered,
            "recommendation": self.recommendation,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class EarlyWarningSystem:
    """
    نظام الإنذار المبكر — يراقب 3 مؤشرات تنبؤية للانهيار
    يُستدعى في كل دورة فحص لتقييم خطر الانهيار القادم
    """

    def __init__(self, coinglass_client=None, okx_client=None):
        self.cg = coinglass_client
        self.okx = okx_client

        # تاريخ OI لكل عملة (آخر 7 أيام)
        self._oi_history: Dict[str, List[float]] = {}
        # تاريخ Long/Short لكل عملة
        self._ls_history: Dict[str, List[float]] = {}
        # تاريخ حجم التداول لكل عملة
        self._volume_history: Dict[str, List[float]] = {}
        # تاريخ السعر
        self._price_history: Dict[str, List[float]] = {}

        # آخر تحذير صادر
        self._last_warning: Optional[EarlyWarning] = None
        self._warning_history: List[EarlyWarning] = []

        # إحصائيات الدقة
        self._predictions_made = 0
        self._predictions_correct = 0

        logger.info("✅ Early Warning System initialized — 3 pre-crash indicators active")

    # ─────────────────────────────────────────────
    # المؤشر #1: OI Divergence
    # ─────────────────────────────────────────────
    def _check_oi_divergence(self, symbol: str, current_price: float,
                              current_oi: float) -> Tuple[float, Optional[str]]:
        """
        يكتشف تباعد OI عن السعر:
        - السعر يصعد بينما OI ينخفض على مدى 3+ أيام = تحذير قوي
        - يعني: المتداولون يغلقون مراكزهم رغم صعود السعر = صعود مصطنع
        """
        key = symbol
        prices = self._price_history.get(key, [])
        ois = self._oi_history.get(key, [])

        if len(prices) < 6 or len(ois) < 6:
            return 0.0, None

        # فحص آخر 3 أيام (18 شمعة × 4 ساعات)
        price_change_3d = (prices[-1] - prices[-18]) / prices[-18] if len(prices) >= 18 else 0
        oi_change_3d = (ois[-1] - ois[-18]) / ois[-18] if len(ois) >= 18 else 0

        # فحص آخر 5 أيام
        price_change_5d = (prices[-1] - prices[-30]) / prices[-30] if len(prices) >= 30 else 0
        oi_change_5d = (ois[-1] - ois[-30]) / ois[-30] if len(ois) >= 30 else 0

        score = 0.0
        msg = None

        # تباعد 3 أيام: سعر يصعد + OI ينخفض
        if price_change_3d > 0.02 and oi_change_3d < -0.03:
            score = 35.0
            msg = (f"⚠️ OI Divergence (3d): السعر +{price_change_3d:.1%} "
                   f"لكن OI {oi_change_3d:.1%} — صعود مصطنع")

        # تباعد 5 أيام: أقوى
        if price_change_5d > 0.03 and oi_change_5d < -0.05:
            score = max(score, 55.0)
            msg = (f"🚨 OI Divergence (5d): السعر +{price_change_5d:.1%} "
                   f"لكن OI {oi_change_5d:.1%} — تحذير مبكر قوي")

        # تباعد شديد: سعر يصعد بقوة + OI ينخفض بقوة
        if price_change_5d > 0.08 and oi_change_5d < -0.08:
            score = 75.0
            msg = (f"🔴 OI Divergence CRITICAL: السعر +{price_change_5d:.1%} "
                   f"لكن OI {oi_change_5d:.1%} — انهيار وشيك!")

        return score, msg

    # ─────────────────────────────────────────────
    # المؤشر #2: Long/Short Ratio Monitor
    # ─────────────────────────────────────────────
    def _check_long_short_ratio(self, symbol: str,
                                 long_ratio: float) -> Tuple[float, Optional[str]]:
        """
        يراقب نسبة Long/Short:
        - > 2.5:1  = خطر تصفية جماعية وشيكة
        - > 3.0:1  = خطر شديد جداً (كما قبل انهيار أكتوبر 2025)
        - > 3.5:1  = انهيار وشيك جداً
        """
        if long_ratio <= 0:
            return 0.0, None

        score = 0.0
        msg = None

        if long_ratio > 3.5:
            score = 80.0
            msg = (f"🔴 Long/Short = {long_ratio:.2f}:1 — "
                   f"خطر تصفية جماعية وشيكة جداً! (مثل أكتوبر 2025)")
        elif long_ratio > 3.0:
            score = 60.0
            msg = (f"🚨 Long/Short = {long_ratio:.2f}:1 — "
                   f"خطر تصفية جماعية (عتبة انهيار أكتوبر 2025)")
        elif long_ratio > 2.5:
            score = 35.0
            msg = (f"⚠️ Long/Short = {long_ratio:.2f}:1 — "
                   f"الجميع يشتري بالرافعة = خطر متزايد")

        # فحص الاتجاه: هل النسبة ترتفع بسرعة؟
        ls_hist = self._ls_history.get(symbol, [])
        if len(ls_hist) >= 6:
            ls_change = long_ratio - ls_hist[-6]  # التغير خلال يوم
            if ls_change > 0.5 and long_ratio > 2.0:
                score = min(score + 20.0, 90.0)
                if msg:
                    msg += f" (ارتفع {ls_change:.1f} نقطة في يوم!)"

        return score, msg

    # ─────────────────────────────────────────────
    # المؤشر #3: Volume-Price Divergence
    # ─────────────────────────────────────────────
    def _check_volume_price_divergence(self, symbol: str,
                                        current_price: float,
                                        current_volume: float) -> Tuple[float, Optional[str]]:
        """
        يكتشف صعوداً بحجم ضعيف:
        - السعر يصعد لكن الحجم < 60% من المعدل = صعود مصطنع
        - السعر يصعد لكن الحجم يتناقص على مدى 5 أيام = نفاد الزخم
        """
        prices = self._price_history.get(symbol, [])
        volumes = self._volume_history.get(symbol, [])

        if len(prices) < 20 or len(volumes) < 20:
            return 0.0, None

        # متوسط الحجم (20 شمعة = ~3 أيام)
        avg_volume_20 = sum(volumes[-20:]) / 20
        if avg_volume_20 <= 0:
            return 0.0, None

        volume_ratio = current_volume / avg_volume_20
        price_change_3d = (prices[-1] - prices[-18]) / prices[-18] if len(prices) >= 18 else 0

        score = 0.0
        msg = None

        # صعود بحجم ضعيف جداً
        if price_change_3d > 0.03 and volume_ratio < 0.5:
            score = 40.0
            msg = (f"⚠️ Volume Divergence: السعر +{price_change_3d:.1%} "
                   f"لكن الحجم {volume_ratio:.0%} من المعدل — صعود مصطنع")

        # صعود بحجم ضعيف + اتجاه تناقصي
        if len(volumes) >= 30:
            avg_vol_recent = sum(volumes[-10:]) / 10
            avg_vol_old = sum(volumes[-30:-20]) / 10
            vol_trend = (avg_vol_recent - avg_vol_old) / avg_vol_old if avg_vol_old > 0 else 0

            if price_change_3d > 0.05 and vol_trend < -0.25:
                score = max(score, 55.0)
                msg = (f"🚨 Volume Trend Divergence: السعر +{price_change_3d:.1%} "
                       f"لكن الحجم تناقص {abs(vol_trend):.0%} — نفاد الزخم")

        return score, msg

    # ─────────────────────────────────────────────
    # المؤشر #4: Funding Rate Trend (مكافأة)
    # ─────────────────────────────────────────────
    def _check_funding_rate_trend(self, symbol: str,
                                   current_fr: float) -> Tuple[float, Optional[str]]:
        """
        يراقب اتجاه معدل التمويل:
        - FR > +0.05% = الجميع يشتري بالرافعة = خطر
        - FR يرتفع بسرعة = خطر متزايد
        درس من أكتوبر 2025: FR وصل +0.08% قبل الانهيار بيومين
        """
        score = 0.0
        msg = None

        if current_fr > 0.08:
            score = 50.0
            msg = (f"🔴 Funding Rate = {current_fr:.3%} — "
                   f"مستوى ما قبل انهيار أكتوبر 2025!")
        elif current_fr > 0.05:
            score = 30.0
            msg = f"⚠️ Funding Rate = {current_fr:.3%} — مرتفع جداً"
        elif current_fr > 0.03:
            score = 15.0
            msg = f"📊 Funding Rate = {current_fr:.3%} — مراقبة"

        return score, msg

    # ─────────────────────────────────────────────
    # التقييم الشامل
    # ─────────────────────────────────────────────
    def evaluate(self, symbol: str, market_data: Dict) -> EarlyWarning:
        """
        يُقيِّم خطر الانهيار المبكر لعملة معينة
        
        market_data يجب أن يحتوي على:
        - price: السعر الحالي
        - oi: Open Interest الحالي
        - long_ratio: نسبة Long (0-1 أو 0-100)
        - volume: حجم التداول الحالي
        - funding_rate: معدل التمويل الحالي
        """
        price = market_data.get('price', 0)
        oi = market_data.get('oi', 0)
        long_ratio = market_data.get('long_ratio', 0)
        volume = market_data.get('volume', 0)
        funding_rate = market_data.get('funding_rate', 0)

        # تحديث التاريخ
        self._update_history(symbol, price, oi, long_ratio, volume)

        # تشغيل المؤشرات الأربعة
        score1, msg1 = self._check_oi_divergence(symbol, price, oi)
        score2, msg2 = self._check_long_short_ratio(symbol, long_ratio)
        score3, msg3 = self._check_volume_price_divergence(symbol, price, volume)
        score4, msg4 = self._check_funding_rate_trend(symbol, funding_rate)

        # الدرجة الإجمالية (مرجّحة)
        total_score = (score1 * 0.35 +   # OI Divergence: أهم مؤشر
                       score2 * 0.30 +   # Long/Short Ratio
                       score3 * 0.20 +   # Volume Divergence
                       score4 * 0.15)    # Funding Rate Trend

        # جمع المؤشرات المُفعَّلة
        triggered = []
        details = {}
        if msg1:
            triggered.append(msg1)
            details['oi_divergence'] = {'score': score1, 'message': msg1}
        if msg2:
            triggered.append(msg2)
            details['long_short'] = {'score': score2, 'message': msg2}
        if msg3:
            triggered.append(msg3)
            details['volume_divergence'] = {'score': score3, 'message': msg3}
        if msg4:
            triggered.append(msg4)
            details['funding_rate'] = {'score': score4, 'message': msg4}

        # تحديد مستوى التحذير
        if total_score >= 65:
            level = WarningLevel.CRITICAL
            rec = "🚫 أوقف جميع الدخولات الجديدة — انهيار وشيك"
        elif total_score >= 45:
            level = WarningLevel.HIGH
            rec = "⛔ لا تدخل صفقات جديدة — خطر مرتفع"
        elif total_score >= 25:
            level = WarningLevel.MEDIUM
            rec = "⚠️ قلل الصفقات إلى 1 فقط — سوق خطر"
        elif total_score >= 10:
            level = WarningLevel.LOW
            rec = "📊 راقب السوق — مؤشرات تحذيرية خفيفة"
        else:
            level = WarningLevel.NONE
            rec = "✅ لا تحذيرات مبكرة"

        warning = EarlyWarning(
            level=level,
            score=total_score,
            indicators_triggered=triggered,
            recommendation=rec,
            details=details,
        )

        # تسجيل التحذيرات المهمة
        if level in (WarningLevel.HIGH, WarningLevel.CRITICAL):
            logger.warning(
                f"🚨 Early Warning [{level.value}] {symbol}: score={total_score:.0f} "
                f"— {len(triggered)} indicators triggered"
            )
            for t in triggered:
                logger.warning(f"   {t}")

        self._last_warning = warning
        self._warning_history.append(warning)
        if len(self._warning_history) > 500:
            self._warning_history = self._warning_history[-500:]

        return warning

    def evaluate_market(self, symbols_data: Dict[str, Dict]) -> Dict:
        """
        يُقيِّم خطر الانهيار لمجموعة من العملات
        يُعيد التحذير الأشد خطورة
        """
        results = {}
        max_score = 0.0
        worst_warning = None

        for symbol, data in symbols_data.items():
            warning = self.evaluate(symbol, data)
            results[symbol] = warning.to_dict()
            if warning.score > max_score:
                max_score = warning.score
                worst_warning = warning

        # التحذير الإجمالي للسوق (بناءً على BTC + ETH بشكل رئيسي)
        btc_score = results.get('BTC/USDT', {}).get('score', 0)
        eth_score = results.get('ETH/USDT', {}).get('score', 0)
        market_score = btc_score * 0.6 + eth_score * 0.4

        return {
            'market_score': round(market_score, 1),
            'worst_symbol': worst_warning.to_dict() if worst_warning else {},
            'symbol_results': results,
            'overall_level': worst_warning.level.value if worst_warning else 'NONE',
            'timestamp': datetime.now().isoformat(),
        }

    def _update_history(self, symbol: str, price: float, oi: float,
                         long_ratio: float, volume: float):
        """يحفظ البيانات في التاريخ (آخر 60 نقطة = 10 أيام بشمعات 4h)"""
        MAX_HISTORY = 60

        for hist, val in [
            (self._price_history, price),
            (self._oi_history, oi),
            (self._ls_history, long_ratio),
            (self._volume_history, volume),
        ]:
            if symbol not in hist:
                hist[symbol] = []
            if val > 0:
                hist[symbol].append(val)
            if len(hist[symbol]) > MAX_HISTORY:
                hist[symbol] = hist[symbol][-MAX_HISTORY:]

    def get_status(self) -> Dict:
        """يُعيد ملخص حالة النظام"""
        return {
            'symbols_tracked': list(self._price_history.keys()),
            'last_warning': self._last_warning.to_dict() if self._last_warning else None,
            'warnings_history_count': len(self._warning_history),
            'high_warnings_24h': sum(
                1 for w in self._warning_history[-100:]
                if w.level in (WarningLevel.HIGH, WarningLevel.CRITICAL)
                and (datetime.now() - w.timestamp).total_seconds() < 86400
            ),
        }
