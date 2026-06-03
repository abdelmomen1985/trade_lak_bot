"""
market_regime_adapter.py — محوّل حالة السوق لـ Trade Lak
=============================================================
يربط نظام كشف حالة السوق (MarketRegimeDetector) بالمعاملات الفعلية
للتداول، مما يجعل Trade Lak يتكيف تلقائياً مع:
  - السوق الصعودي (BULL_TREND)
  - السوق الهابط (BEAR_TREND)
  - السوق العرضي (SIDEWAYS)
  - الانهيار (CRASH)
  - التعافي (RECOVERY)
  - التراكم (ACCUMULATION)
  - التوزيع (DISTRIBUTION)
  - الضخ المفاجئ (PUMP)
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger('trade_lak')


@dataclass
class RegimeParams:
    """معاملات التداول المُحسَّنة لكل نوع سوق"""
    # حدود الصفقات
    max_spot_trades: int = 3
    max_futures_trades: int = 0
    # مضاعفات SL/TP (تُطبَّق على القيم المحسوبة)
    sl_multiplier: float = 1.0      # 1.0 = بدون تغيير | 0.8 = أضيق | 1.3 = أوسع
    tp_multiplier: float = 1.0      # 1.0 = بدون تغيير | 1.5 = أهداف أعلى
    # حجم الصفقة
    position_size_multiplier: float = 1.0
    # Trailing Stop
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 0.015
    # OI 24h rejection threshold
    oi_24h_rejection_threshold: float = -8.0
    # Min confidence required
    min_confidence: float = 0.65
    # Min score
    min_score: float = 5.0
    # وصف
    description: str = ""
    arabic_name: str = ""


# ─── جدول المعاملات لكل نوع سوق ───────────────────────────────────────────
REGIME_PARAMS: Dict[str, RegimeParams] = {
    "bull_trend": RegimeParams(
        max_spot_trades=5,
        sl_multiplier=1.3,          # Backtest: SL أوسع لتجنب ذيول الشمعات
        tp_multiplier=1.5,
        position_size_multiplier=0.75,
        trailing_stop_enabled=True,
        trailing_stop_pct=0.025,    # Backtest: Trailing أوسع (2.5%)
        oi_24h_rejection_threshold=-10.0,
        min_confidence=0.60,
        min_score=7.0,
        description="اتجاه صاعد قوي (Backtest: SL أوسع + Trailing 2.5%)",
        arabic_name="سوق صعودي 📈",
    ),
    "bear_trend": RegimeParams(
        max_spot_trades=1,          # صفقة واحدة فقط
        sl_multiplier=0.85,          # SL أضيق بـ 30%
        tp_multiplier=0.85,          # أهداف أقرب (اجمع الأرباح سريعاً)
        position_size_multiplier=0.7,  # حجم أصغر
        trailing_stop_enabled=True,
        trailing_stop_pct=0.010,    # trailing أضيق جداً
        oi_24h_rejection_threshold=-5.0,  # أكثر صرامة
        min_confidence=0.75,        # ثقة أعلى مطلوبة
        min_score=6.0,              # نقاط أعلى مطلوبة
        description="اتجاه هابط — حجم أصغر، SL أضيق، ثقة أعلى",
        arabic_name="سوق هابط 📉",
    ),
    "sideways": RegimeParams(
        max_spot_trades=1,          # Backtest: WR 20% → تقليل إلى 1 صفقة
        sl_multiplier=0.85,          # Backtest: SL أضيق لتجنب الخسائر
        tp_multiplier=0.9,
        position_size_multiplier=0.7,  # Backtest: حجم أصغر
        trailing_stop_enabled=False,
        trailing_stop_pct=0.012,
        oi_24h_rejection_threshold=-5.0,
        min_confidence=0.82,        # Backtest: رفع معيار الثقة إلى 82%
        min_score=7.5,              # Backtest: نقاط أعلى مطلوبة
        description="سوق جانبي — شروط صارمة جداً (Backtest: WR 20%)",
        arabic_name="سوق عرضي ↔️",
    ),
    "crash": RegimeParams(
        max_spot_trades=0,          # إيقاف كامل للصفقات الجديدة
        sl_multiplier=1.0,
        tp_multiplier=1.0,
        position_size_multiplier=0.0,
        trailing_stop_enabled=False,
        trailing_stop_pct=0.015,
        oi_24h_rejection_threshold=-3.0,
        min_confidence=0.90,
        min_score=8.0,
        description="انهيار — إيقاف كامل للصفقات الجديدة",
        arabic_name="انهيار 💥",
    ),
    "recovery": RegimeParams(
        max_spot_trades=2,          # Crash Backtest: WR=9% → تقليل حاد         
        sl_multiplier=1.2,
        tp_multiplier=1.5,          # Crash Backtest: تقليل الهدف         
        position_size_multiplier=1.2,  # Crash Backtest: تقليل الحجم 
        trailing_stop_enabled=True,
        trailing_stop_pct=0.018,    # Backtest: Trailing أوسع
        oi_24h_rejection_threshold=-12.0,
        min_confidence=0.78,        # Crash Backtest: رفع الثقة بشكل كبير       
        min_score=4.0,
        description="تعافي — فرصة ذهبية (Backtest: WR 73%)",
        arabic_name="تعافي 🔄",
    ),
    "accumulation": RegimeParams(
        max_spot_trades=2,          # Crash Backtest: WR=30% → تقليل
        sl_multiplier=0.9,
        tp_multiplier=1.8,          # أهداف أعلى (الصعود قادم)
        position_size_multiplier=1.1,
        trailing_stop_enabled=True,
        trailing_stop_pct=0.013,
        oi_24h_rejection_threshold=-8.0,
        min_confidence=0.75,        # Crash Backtest: رفع الثقة
        min_score=5.0,
        description="تراكم — دخول مبكر قبل الصعود الكبير",
        arabic_name="تراكم 🏗️",
    ),
    "distribution": RegimeParams(
        max_spot_trades=1,
        sl_multiplier=0.75,
        tp_multiplier=0.85,
        position_size_multiplier=0.75,
        trailing_stop_enabled=True,
        trailing_stop_pct=0.010,
        oi_24h_rejection_threshold=-5.0,
        min_confidence=0.75,
        min_score=6.0,
        description="توزيع — استعد للهبوط",
        arabic_name="توزيع ⚠️",
    ),
    "pump": RegimeParams(
        max_spot_trades=2,
        sl_multiplier=1.2,          # SL أوسع للضخ
        tp_multiplier=0.7,          # اجمع الأرباح سريعاً
        position_size_multiplier=0.8,
        trailing_stop_enabled=True,
        trailing_stop_pct=0.020,    # trailing أوسع للضخ
        oi_24h_rejection_threshold=-8.0,
        min_confidence=0.70,
        min_score=5.5,
        description="ضخ مفاجئ — اجمع الأرباح سريعاً",
        arabic_name="ضخ 🚀",
    ),
    # fallback
    "unknown": RegimeParams(
        max_spot_trades=3,
        sl_multiplier=1.0,
        tp_multiplier=1.0,
        position_size_multiplier=1.0,
        trailing_stop_enabled=True,
        trailing_stop_pct=0.015,
        oi_24h_rejection_threshold=-8.0,
        min_confidence=0.65,
        min_score=5.0,
        description="غير محدد — معاملات افتراضية",
        arabic_name="غير محدد ❓",
    ),
}


class MarketRegimeAdapter:
    """
    يستمع لنظام كشف حالة السوق ويُحدِّث المعاملات الفعلية تلقائياً.
    يُستخدَم في main.py لضبط SL/TP/حجم الصفقة/عدد الصفقات.
    """

    def __init__(self):
        self._current_regime: str = "unknown"
        self._last_update: datetime = datetime.now()
        self._last_log_time: datetime = datetime.min
        self._regime_change_count: int = 0
        self._regime_history: list = []

    @property
    def current_regime(self) -> str:
        return self._current_regime

    @property
    def params(self) -> RegimeParams:
        return REGIME_PARAMS.get(self._current_regime, REGIME_PARAMS["unknown"])

    def update(self, regime: str) -> bool:
        """
        تحديث حالة السوق.
        يُعيد True إذا تغيرت الحالة.
        """
        if not regime or regime == self._current_regime:
            return False

        old_regime = self._current_regime
        self._current_regime = regime
        self._last_update = datetime.now()
        self._regime_change_count += 1
        self._regime_history.append({
            "from": old_regime,
            "to": regime,
            "time": self._last_update.isoformat(),
        })
        # احتفظ بآخر 50 تغيير فقط
        if len(self._regime_history) > 50:
            self._regime_history = self._regime_history[-50:]

        old_params = REGIME_PARAMS.get(old_regime, REGIME_PARAMS["unknown"])
        new_params = self.params

        logger.warning(
            f"\n{'='*60}\n"
            f"📊 تغيير حالة السوق: {old_params.arabic_name} → {new_params.arabic_name}\n"
            f"   الصفقات المسموحة: {old_params.max_spot_trades} → {new_params.max_spot_trades}\n"
            f"   مضاعف SL: {old_params.sl_multiplier:.1f}x → {new_params.sl_multiplier:.1f}x\n"
            f"   مضاعف TP: {old_params.tp_multiplier:.1f}x → {new_params.tp_multiplier:.1f}x\n"
            f"   حجم الصفقة: {old_params.position_size_multiplier:.1f}x → {new_params.position_size_multiplier:.1f}x\n"
            f"   Trailing Stop: {'✅' if new_params.trailing_stop_enabled else '❌'} ({new_params.trailing_stop_pct:.1%})\n"
            f"   {new_params.description}\n"
            f"{'='*60}"
        )
        return True

    def apply_to_sl_tp(
        self,
        entry_price: float,
        sl: float,
        tp: float,
        direction: str,
    ) -> Tuple[float, float]:
        """
        يُطبِّق مضاعفات SL/TP بناءً على حالة السوق.
        يُعيد (sl_adjusted, tp_adjusted).
        """
        p = self.params
        if p.sl_multiplier == 1.0 and p.tp_multiplier == 1.0:
            return sl, tp

        if direction in ("SPOT_BUY", "LONG"):
            # SL: بعيد عن سعر الدخول
            sl_distance = entry_price - sl
            sl_adjusted = entry_price - (sl_distance * p.sl_multiplier)
            # TP: بعيد عن سعر الدخول
            tp_distance = tp - entry_price
            tp_adjusted = entry_price + (tp_distance * p.tp_multiplier)
            # حماية: SL لا يتجاوز 5% من سعر الدخول
            sl_adjusted = max(sl_adjusted, entry_price * 0.95)
        else:
            sl_distance = sl - entry_price
            sl_adjusted = entry_price + (sl_distance * p.sl_multiplier)
            tp_distance = entry_price - tp
            tp_adjusted = entry_price - (tp_distance * p.tp_multiplier)
            sl_adjusted = min(sl_adjusted, entry_price * 1.05)

        if sl_adjusted != sl or tp_adjusted != tp:
            logger.info(
                f"🎛️ [RegimeAdapter] {self._current_regime} | "
                f"SL: {sl:.6f} → {sl_adjusted:.6f} (x{p.sl_multiplier}) | "
                f"TP: {tp:.6f} → {tp_adjusted:.6f} (x{p.tp_multiplier})"
            )
        return sl_adjusted, tp_adjusted

    def apply_to_position_size(self, amount_usdt: float) -> float:
        """يُطبِّق مضاعف حجم الصفقة"""
        p = self.params
        if p.position_size_multiplier == 1.0:
            return amount_usdt
        adjusted = amount_usdt * p.position_size_multiplier
        if adjusted != amount_usdt:
            logger.info(
                f"🎛️ [RegimeAdapter] حجم الصفقة: ${amount_usdt:.2f} → ${adjusted:.2f} "
                f"(x{p.position_size_multiplier} — {self._current_regime})"
            )
        return adjusted

    def get_max_spot_trades(self, default: int) -> int:
        """يُعيد الحد الأقصى للصفقات بناءً على حالة السوق"""
        return self.params.max_spot_trades

    def should_allow_new_trade(self) -> Tuple[bool, str]:
        """يتحقق إذا كان يجب السماح بصفقة جديدة"""
        p = self.params
        if p.max_spot_trades == 0:
            return False, f"❌ إيقاف الصفقات الجديدة — حالة السوق: {p.arabic_name}"
        return True, ""

    def get_oi_rejection_threshold(self) -> float:
        """يُعيد عتبة رفض OI 24h بناءً على حالة السوق"""
        return self.params.oi_24h_rejection_threshold

    def get_min_confidence(self) -> float:
        """يُعيد الحد الأدنى للثقة بناءً على حالة السوق"""
        return self.params.min_confidence

    def get_trailing_config(self) -> Tuple[bool, float]:
        """يُعيد إعدادات Trailing Stop"""
        p = self.params
        return p.trailing_stop_enabled, p.trailing_stop_pct

    def log_status(self, force: bool = False):
        """يطبع حالة السوق الحالية في السجل (مرة كل 30 دقيقة)"""
        now = datetime.now()
        if not force and (now - self._last_log_time).total_seconds() < 1800:
            return
        self._last_log_time = now
        p = self.params
        logger.info(
            f"📊 [MarketRegime] الحالة: {p.arabic_name} | "
            f"الصفقات: {p.max_spot_trades} | "
            f"SL: x{p.sl_multiplier} | TP: x{p.tp_multiplier} | "
            f"الحجم: x{p.position_size_multiplier} | "
            f"OI رفض: {p.oi_24h_rejection_threshold}%"
        )

    def get_status_report(self) -> Dict:
        """يُعيد تقرير الحالة الكاملة"""
        p = self.params
        return {
            "regime": self._current_regime,
            "arabic_name": p.arabic_name,
            "max_spot_trades": p.max_spot_trades,
            "sl_multiplier": p.sl_multiplier,
            "tp_multiplier": p.tp_multiplier,
            "position_size_multiplier": p.position_size_multiplier,
            "trailing_stop_enabled": p.trailing_stop_enabled,
            "trailing_stop_pct": p.trailing_stop_pct,
            "oi_24h_rejection_threshold": p.oi_24h_rejection_threshold,
            "min_confidence": p.min_confidence,
            "last_update": self._last_update.isoformat(),
            "regime_changes": self._regime_change_count,
            "description": p.description,
        }


# Singleton instance
_adapter_instance: Optional[MarketRegimeAdapter] = None


def get_regime_adapter() -> MarketRegimeAdapter:
    """يُعيد instance واحد مشترك"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MarketRegimeAdapter()
    return _adapter_instance
