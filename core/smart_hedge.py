"""
smart_hedge.py — نظام الـ Hedge الذكي لـ Trade Lak
=====================================================
يفتح صفقة عكسية محسوبة بناءً على نسبة الثقة لتغطية الخسارة
إذا فشل التنبؤ، مع تحقيق ربح صافٍ إذا نجح.

المبدأ:
- الصفقة الرئيسية: Long/Short بحجم كامل
- الصفقة العكسية: Short/Long بحجم مُحسَب = (SL_amount / TP_pct_hedge)
- حجم الـ Hedge يتناسب عكسياً مع نسبة الثقة
"""

import logging
from dataclasses import dataclass
from typing import Optional, Literal

logger = logging.getLogger(__name__)


@dataclass
class HedgeParams:
    """معاملات صفقة الـ Hedge"""
    should_hedge: bool          # هل يجب فتح hedge؟
    hedge_size_usd: float       # حجم الـ Hedge بالدولار
    hedge_direction: str        # 'long' أو 'short' (عكس الرئيسية)
    hedge_tp_pct: float         # هدف الربح للـ Hedge (%)
    hedge_sl_pct: float         # وقف الخسارة للـ Hedge (%)
    hedge_leverage: int         # الرافعة للـ Hedge
    confidence: float           # نسبة الثقة الأصلية
    hedge_ratio: float          # نسبة الـ Hedge من الصفقة الرئيسية
    expected_net_win: float     # الربح الصافي المتوقع إذا نجح التنبؤ
    expected_net_loss: float    # الخسارة الصافية المتوقعة إذا فشل (يجب أن تكون ≈ 0)
    reason: str                 # سبب القرار


class SmartHedgeCalculator:
    """
    حاسبة الـ Hedge الذكية
    
    الخوارزمية:
    1. حساب خسارة الصفقة الرئيسية عند وقف الخسارة = main_size * sl_pct
    2. حساب حجم الـ Hedge = main_loss / hedge_tp_pct
    3. التحقق من أن الربح الصافي عند نجاح التنبؤ > 0
    """
    
    # حد التذبذب: إذا كان ATR% أعلى من هذا الحد → لا Hedge
    # ATR% = (ATR / السعر) × 100
    MAX_ATR_PCT_FOR_HEDGE = 2.5   # 2.5% = تذبذب عالٍ جداً
    MEDIUM_ATR_PCT = 1.5          # 1.5% = تذبذب متوسط → تقليص الـ Hedge

    # جدول نسب الـ Hedge حسب الثقة
    HEDGE_RATIO_TABLE = {
        # (min_confidence, max_confidence): hedge_ratio
        # سياسة: Hedge فقط عند ثقة 90%+ بنسبة 50% ثابتة (3x رافعة)
        (0.90, 1.00): 0.50,   # ثقة 90%+ = hedge 50% من الصفقة الأصلية
    }
    
    # الحد الأدنى للثقة لفتح أي صفقة futures مع hedge
    MIN_CONFIDENCE_FOR_FUTURES = 0.90  # ثقة 90%+ فقط — سياسة المستخدم
    
    # الحد الأدنى لحجم الـ Hedge بالدولار
    MIN_HEDGE_SIZE_USD = 5.0
    
    # الحد الأقصى لنسبة الـ Hedge (لا نريد hedge أكبر من الصفقة الرئيسية)
    MAX_HEDGE_RATIO = 0.75
    
    def calculate(
        self,
        confidence: float,           # نسبة الثقة (0.0 - 1.0)
        main_size_usd: float,        # حجم الصفقة الرئيسية بالدولار
        main_direction: str,         # 'long' أو 'short'
        main_sl_pct: float,          # وقف الخسارة % (موجب، مثلاً 0.015 = 1.5%)
        main_tp_pct: float,          # هدف الربح % (موجب، مثلاً 0.03 = 3%)
        main_leverage: int = 3,      # الرافعة للصفقة الرئيسية
        symbol: str = "UNKNOWN",     # رمز العملة للسجل
        atr_pct: float = 0.0,        # ATR% = (ATR / السعر) × 100 — 0 = غير محسوب
        market_regime: str = '',     # نوع السوق من Regime Adapter
    ) -> HedgeParams:
        """
        حساب معاملات الـ Hedge المثلى
        
        Returns:
            HedgeParams مع جميع التفاصيل
        """
        
        # 0. فلتر ATR — منع الـ Hedge في التذبذب العالي
        if atr_pct > 0:
            if atr_pct >= self.MAX_ATR_PCT_FOR_HEDGE:
                return HedgeParams(
                    should_hedge=False,
                    hedge_size_usd=0,
                    hedge_direction='none',
                    hedge_tp_pct=0,
                    hedge_sl_pct=0,
                    hedge_leverage=1,
                    confidence=confidence,
                    hedge_ratio=0,
                    expected_net_win=main_size_usd * main_tp_pct,
                    expected_net_loss=-(main_size_usd * main_sl_pct),
                    reason=f"ATR {atr_pct:.2f}% > {self.MAX_ATR_PCT_FOR_HEDGE}% — تذبذب عالٍ جداً، لا Hedge"
                )
            elif atr_pct >= self.MEDIUM_ATR_PCT:
                # تذبذب متوسط: تقليص الـ Hedge إلى 50% من المعتاد
                hedge_ratio = self._get_hedge_ratio(confidence) * 0.5
                logger.info(f"[SmartHedge] {symbol} ATR {atr_pct:.2f}% متوسط — تقليص Hedge إلى {hedge_ratio:.0%}")
            else:
                hedge_ratio = self._get_hedge_ratio(confidence)
        else:
            hedge_ratio = self._get_hedge_ratio(confidence)

        # فلتر Regime — لا Hedge في السوق العرضي أو الانهيار
        if market_regime in ('RANGING', 'CRASH', 'DISTRIBUTION'):
            return HedgeParams(
                should_hedge=False,
                hedge_size_usd=0,
                hedge_direction='none',
                hedge_tp_pct=0,
                hedge_sl_pct=0,
                hedge_leverage=1,
                confidence=confidence,
                hedge_ratio=0,
                expected_net_win=main_size_usd * main_tp_pct,
                expected_net_loss=-(main_size_usd * main_sl_pct),
                reason=f"Regime={market_regime} — لا Hedge في هذا النوع من السوق"
            )

        # 1. التحقق من الحد الأدنى للثقة
        if confidence < self.MIN_CONFIDENCE_FOR_FUTURES:
            return HedgeParams(
                should_hedge=False,
                hedge_size_usd=0,
                hedge_direction='none',
                hedge_tp_pct=0,
                hedge_sl_pct=0,
                hedge_leverage=1,
                confidence=confidence,
                hedge_ratio=0,
                expected_net_win=0,
                expected_net_loss=0,
                reason=f"ثقة {confidence:.0%} أقل من الحد الأدنى {self.MIN_CONFIDENCE_FOR_FUTURES:.0%} — لا صفقة"
            )
        
        # 2. تحديد نسبة الـ Hedge (إذا لم تُحدَّد مسبقاً بفلتر ATR)
        if 'hedge_ratio' not in dir():
            hedge_ratio = self._get_hedge_ratio(confidence)
        
        # 3. حساب الخسارة المتوقعة للصفقة الرئيسية عند SL
        # الخسارة = الحجم × SL% × الرافعة (لكن نحسب بالقيمة الاسمية)
        main_loss_at_sl = main_size_usd * main_sl_pct  # الخسارة الفعلية بالدولار
        
        # 4. حساب حجم الـ Hedge بناءً على نسبة الثقة مباشرةً
        # نستخدم جدول HEDGE_RATIO_TABLE مباشرةً لتحديد الحجم
        actual_ratio = min(hedge_ratio, self.MAX_HEDGE_RATIO)
        hedge_size_usd = main_size_usd * actual_ratio
        
        # هدف ربح الـ Hedge يُحسب لتغطية خسارة الرئيسية بالكامل
        # hedge_size × hedge_tp_pct = main_loss_at_sl
        # hedge_tp_pct = main_loss_at_sl / hedge_size_usd
        hedge_tp_pct = main_loss_at_sl / hedge_size_usd  # يُغطي الخسارة بالكامل
        
        # 6. التحقق من الحد الأدنى للحجم
        if hedge_size_usd < self.MIN_HEDGE_SIZE_USD:
            return HedgeParams(
                should_hedge=False,
                hedge_size_usd=0,
                hedge_direction='none',
                hedge_tp_pct=0,
                hedge_sl_pct=0,
                hedge_leverage=1,
                confidence=confidence,
                hedge_ratio=0,
                expected_net_win=main_size_usd * main_tp_pct,
                expected_net_loss=-main_loss_at_sl,
                reason=f"حجم الـ Hedge ${hedge_size_usd:.2f} أقل من الحد الأدنى ${self.MIN_HEDGE_SIZE_USD}"
            )
        
        # 7. تحديد اتجاه الـ Hedge (عكس الرئيسية)
        hedge_direction = 'short' if main_direction == 'long' else 'long'
        
        # 8. حساب وقف الخسارة للـ Hedge
        # إذا تحرك السعر في اتجاه الصفقة الرئيسية بقوة، نوقف الـ Hedge
        hedge_sl_pct = main_tp_pct * 0.8  # وقف الـ Hedge عند 80% من TP الرئيسية
        
        # 9. الرافعة للـ Hedge (أقل من الرئيسية للحد من المخاطر)
        hedge_leverage = 3  # رافعة ثابتة 3x للـ Hedge — سياسة المستخدم
        
        # 10. حساب النتائج المتوقعة
        # إذا نجح التنبؤ (الرئيسية تصل TP):
        main_profit = main_size_usd * main_tp_pct
        hedge_loss_if_main_wins = hedge_size_usd * hedge_sl_pct  # الـ Hedge يصل SL
        expected_net_win = main_profit - hedge_loss_if_main_wins
        
        # إذا فشل التنبؤ (الرئيسية تصل SL):
        hedge_profit_if_main_loses = hedge_size_usd * hedge_tp_pct  # الـ Hedge يصل TP
        expected_net_loss = hedge_profit_if_main_loses - main_loss_at_sl
        
        # 11. التحقق النهائي: هل الـ Hedge منطقي؟
        if expected_net_win <= 0:
            return HedgeParams(
                should_hedge=False,
                hedge_size_usd=0,
                hedge_direction='none',
                hedge_tp_pct=0,
                hedge_sl_pct=0,
                hedge_leverage=1,
                confidence=confidence,
                hedge_ratio=0,
                expected_net_win=main_profit,
                expected_net_loss=-main_loss_at_sl,
                reason=f"الـ Hedge سيأكل الربح — الصافي المتوقع ${expected_net_win:.2f} سلبي"
            )
        
        reason = (
            f"ثقة {confidence:.0%} → Hedge {actual_ratio:.0%} | "
            f"إذا نجح: +${expected_net_win:.2f} | "
            f"إذا فشل: {'+' if expected_net_loss >= 0 else ''}{expected_net_loss:.2f}$"
        )
        
        logger.info(
            f"[SmartHedge] {symbol} | {main_direction.upper()} ${main_size_usd:.0f} | "
            f"Hedge {hedge_direction.upper()} ${hedge_size_usd:.0f} | {reason}"
        )
        
        return HedgeParams(
            should_hedge=True,
            hedge_size_usd=round(hedge_size_usd, 2),
            hedge_direction=hedge_direction,
            hedge_tp_pct=hedge_tp_pct,
            hedge_sl_pct=hedge_sl_pct,
            hedge_leverage=hedge_leverage,
            confidence=confidence,
            hedge_ratio=actual_ratio,
            expected_net_win=round(expected_net_win, 2),
            expected_net_loss=round(expected_net_loss, 2),
            reason=reason,
        )
    
    def _get_hedge_ratio(self, confidence: float) -> float:
        """تحديد نسبة الـ Hedge بناءً على الثقة"""
        for (min_c, max_c), ratio in self.HEDGE_RATIO_TABLE.items():
            if min_c <= confidence < max_c:
                return ratio
        # إذا كانت الثقة 100% (نادر)
        if confidence >= 1.0:
            return 0.10
        return 0.70  # افتراضي للثقة المنخفضة جداً
    
    def format_summary(self, params: HedgeParams, symbol: str) -> str:
        """تنسيق ملخص الـ Hedge للسجل وTelegram"""
        if not params.should_hedge:
            return f"[Hedge] {symbol}: لا hedge — {params.reason}"
        
        return (
            f"[Hedge] {symbol} | "
            f"Hedge {params.hedge_direction.upper()} ${params.hedge_size_usd:.0f} "
            f"({params.hedge_ratio:.0%} من الرئيسية) | "
            f"TP: {params.hedge_tp_pct:.1%} | SL: {params.hedge_sl_pct:.1%} | "
            f"إذا نجح التنبؤ: +${params.expected_net_win:.2f} | "
            f"إذا فشل: {'+' if params.expected_net_loss >= 0 else ''}{params.expected_net_loss:.2f}$"
        )


# ── Singleton للاستخدام في main.py ─────────────────────────────────────────
_hedge_calculator = SmartHedgeCalculator()


def calculate_hedge(
    confidence: float,
    main_size_usd: float,
    main_direction: str,
    main_sl_pct: float,
    main_tp_pct: float,
    main_leverage: int = 5,
    symbol: str = "UNKNOWN",
) -> HedgeParams:
    """
    دالة مساعدة للاستخدام المباشر من main.py
    
    مثال:
        hedge = calculate_hedge(
            confidence=0.72,
            main_size_usd=100,
            main_direction='long',
            main_sl_pct=0.015,
            main_tp_pct=0.03,
            main_leverage=5,
            symbol='BTC/USDT'
        )
        if hedge.should_hedge:
            # افتح الصفقة العكسية
            open_futures_order(
                symbol=symbol,
                direction=hedge.hedge_direction,
                size_usd=hedge.hedge_size_usd,
                tp_pct=hedge.hedge_tp_pct,
                sl_pct=hedge.hedge_sl_pct,
                leverage=hedge.hedge_leverage,
            )
    """
    return _hedge_calculator.calculate(
        confidence=confidence,
        main_size_usd=main_size_usd,
        main_direction=main_direction,
        main_sl_pct=main_sl_pct,
        main_tp_pct=main_tp_pct,
        main_leverage=main_leverage,
        symbol=symbol,
    )


# ── اختبار سريع ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    calc = SmartHedgeCalculator()
    
    print("=" * 65)
    print("اختبار نظام الـ Hedge الذكي")
    print("=" * 65)
    
    test_cases = [
        # (confidence, main_size, direction, sl_pct, tp_pct, leverage)
        (0.90, 100, 'long',  0.015, 0.030, 5),
        (0.80, 100, 'long',  0.015, 0.030, 5),
        (0.72, 100, 'long',  0.015, 0.030, 5),
        (0.65, 100, 'short', 0.015, 0.030, 5),
        (0.60, 100, 'long',  0.020, 0.040, 3),
        (0.55, 100, 'long',  0.015, 0.030, 5),  # تحت الحد — لا صفقة
    ]
    
    print("\n--- اختبار فلتر ATR ---")
    atr_tests = [
        (0.75, 100, 'long', 0.015, 0.030, 5, 0.8,  ''),   # ATR منخفض — Hedge طبيعي
        (0.75, 100, 'long', 0.015, 0.030, 5, 1.8,  ''),   # ATR متوسط — Hedge مُقلَّص
        (0.75, 100, 'long', 0.015, 0.030, 5, 2.8,  ''),   # ATR عالٍ — لا Hedge
        (0.75, 100, 'long', 0.015, 0.030, 5, 0.5, 'RANGING'),   # سوق عرضي — لا Hedge
        (0.75, 100, 'long', 0.015, 0.030, 5, 0.5, 'CRASH'),     # انهيار — لا Hedge
    ]
    for conf, size, direction, sl, tp, lev, atr, regime in atr_tests:
        params = calc.calculate(conf, size, direction, sl, tp, lev, 'BTC/USDT', atr, regime)
        label = f"ATR={atr}% Regime={regime or 'BULL'}"
        if params.should_hedge:
            print(f"  {label}: ✅ Hedge {params.hedge_direction.upper()} ${params.hedge_size_usd:.1f} ({params.hedge_ratio:.0%})")
        else:
            print(f"  {label}: ❌ {params.reason}")

    print("\n--- الاختبار الرئيسي ---")
    for conf, size, direction, sl, tp, lev in test_cases:
        params = calc.calculate(conf, size, direction, sl, tp, lev, 'BTC/USDT')
        print(f"\nثقة {conf:.0%} | {direction.upper()} ${size} | SL {sl:.1%} | TP {tp:.1%}")
        if params.should_hedge:
            print(f"  ✅ Hedge: {params.hedge_direction.upper()} ${params.hedge_size_usd:.1f} ({params.hedge_ratio:.0%})")
            print(f"  📈 إذا نجح التنبؤ: +${params.expected_net_win:.2f} (بعد خسارة الـ Hedge)")
            print(f"  📉 إذا فشل التنبؤ: {'+' if params.expected_net_loss >= 0 else ''}{params.expected_net_loss:.2f}$ (تغطية الخسارة)")
        else:
            print(f"  ❌ لا Hedge: {params.reason}")
