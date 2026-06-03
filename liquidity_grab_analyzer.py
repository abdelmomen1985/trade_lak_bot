# ============================================================
# Trade Lak — Liquidity Grab Analyzer
# محلل عمليات سحب السيولة (Liquidity Grab / Stop Hunt)
# ============================================================
#
# هذه الوحدة تُعلِّم Trade Lak منطق إدارة السيولة المتقدم:
# بدلاً من الاعتماد على RSI أو MACD فقط، يدمج Trade Lak
# أربعة مصادر بيانات مختلفة ليستنتج احتمالية Liquidity Grab:
#
#   1. Open Interest (OI)     — هل يرتفع بسرعة؟
#   2. Funding Rate           — هل موجب جداً (Long Bias مفرط)؟
#   3. Sell Wall / مقاومة     — هل هناك جدار بيع قريب؟
#   4. Liquidation Clusters   — هل السيولة مركزة فوق القمة الأخيرة؟
#
# إذا توافرت 3 من 4 شروط → احتمال Liquidity Grab مرتفع
# → Trade Lak يُعدِّل SL ويُقلِّل حجم الصفقة أو يُؤجِّل الدخول
#
# الاستخدام في main.py:
#   from liquidity_grab_analyzer import LiquidityGrabAnalyzer
#   analyzer = LiquidityGrabAnalyzer(coinglass_client, orderbook_intel)
#   risk = analyzer.analyze(symbol, current_price)
#   if risk['action'] == 'BLOCK':
#       continue  # لا تدخل
# ============================================================

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LiquidityGrabAnalyzer:
    """
    محلل عمليات سحب السيولة (Liquidity Grab / Stop Hunt)

    يُعلِّم Trade Lak أن يفهم السوق من زاوية صناع السوق:
    عندما يرى السعر عند مقاومة + OI يرتفع بسرعة + Funding موجب جداً
    + سيولة مركزة فوق القمة → هذا يعني أن "الحيتان" تُهيِّئ لصيد
    Stop-Loss الـ Long traders قبل هبوط حاد.

    Trade Lak يتعلم هذا النمط ويتجنبه.
    """

    # ── حدود الإشارة ──────────────────────────────────────────
    OI_SURGE_THRESHOLD = 0.03        # ارتفاع OI 3%+ = إشارة تحذير
    FUNDING_HIGH_THRESHOLD = 0.01    # Funding Rate 1%+ في 8h = إشارة
    FUNDING_EXTREME_THRESHOLD = 0.03 # Funding Rate 3%+ = إشارة قوية جداً
    LONG_BIAS_THRESHOLD = 0.65       # 65%+ Long = Long Bias مفرط
    LIQ_RATIO_THRESHOLD = 1.5        # تصفيات Long > 1.5x تصفيات Short = خطر

    def __init__(self, coinglass_client=None, orderbook_intel=None):
        """
        Args:
            coinglass_client: كائن CoinGlassClient (يوفر OI, Funding, Liquidations)
            orderbook_intel: كائن OrderBookIntel (يوفر Sell Walls, Distribution)
        """
        self.cg = coinglass_client
        self.ob = orderbook_intel
        logger.info("✅ LiquidityGrabAnalyzer initialized")

    # ──────────────────────────────────────────────────────────
    # الشروط الأربعة
    # ──────────────────────────────────────────────────────────

    def _check_oi_surge(self, symbol: str) -> Tuple[bool, float, str]:
        """
        الشرط 1: هل Open Interest يرتفع بسرعة؟

        OI يرتفع بسرعة + السعر عند مقاومة = أموال جديدة تدخل في Long
        عند مستوى خطر → الحيتان ستصطادهم.

        Returns: (is_triggered, oi_change_pct, description)
        """
        if not self.cg:
            return False, 0.0, "CoinGlass غير متاح"
        try:
            clean = symbol.replace('/USDT', '').replace('-USDT', '').upper()
            oi_data = self.cg.get_open_interest(clean)
            oi_change = oi_data.get('change_pct', 0.0)

            if oi_change >= self.OI_SURGE_THRESHOLD:
                return True, oi_change, f"OI ارتفع {oi_change*100:.1f}% بسرعة ⚠️ (أموال جديدة تدخل في Long عند مقاومة)"
            else:
                return False, oi_change, f"OI تغير {oi_change*100:.1f}% (طبيعي ✅)"
        except Exception as e:
            logger.debug(f"OI check error for {symbol}: {e}")
            return False, 0.0, f"خطأ في جلب OI: {e}"

    def _check_funding_rate(self, symbol: str) -> Tuple[bool, float, str]:
        """
        الشرط 2: هل Funding Rate موجب جداً؟

        Funding Rate الموجب جداً يعني: الجميع في Long → يدفعون رسوم
        للـ Short holders → الحيتان في Short ولديهم حافز لدفع السعر
        للأسفل بعد صيد السيولة فوق القمة.

        Returns: (is_triggered, funding_rate, description)
        """
        if not self.cg:
            return False, 0.0, "CoinGlass غير متاح"
        try:
            clean = symbol.replace('/USDT', '').replace('-USDT', '').upper()
            funding = self.cg.get_funding_rate(clean)
            # CoinGlass يُعيد الـ funding كنسبة مئوية (مثال: 0.01 = 1%)
            # لكن بعض الـ APIs تُعيده كـ 0.0001 = 0.01%
            # نتعامل مع كلا الحالتين
            if funding > 1.0:
                # القيمة بالنسبة المئوية (مثال: 1.5 = 1.5%)
                funding_pct = funding / 100.0
            else:
                funding_pct = funding

            if funding_pct >= self.FUNDING_EXTREME_THRESHOLD:
                return True, funding_pct, (
                    f"Funding Rate {funding_pct*100:.3f}% — مرتفع جداً 🔴\n"
                    f"  ↳ الجميع في Long → الحيتان في Short → سيصطادون السيولة فوق القمة"
                )
            elif funding_pct >= self.FUNDING_HIGH_THRESHOLD:
                return True, funding_pct, (
                    f"Funding Rate {funding_pct*100:.3f}% — مرتفع ⚠️ (Long Bias واضح)"
                )
            else:
                return False, funding_pct, f"Funding Rate {funding_pct*100:.3f}% — طبيعي ✅"
        except Exception as e:
            logger.debug(f"Funding check error for {symbol}: {e}")
            return False, 0.0, f"خطأ في جلب Funding Rate: {e}"

    def _check_sell_wall_or_resistance(self, symbol: str, current_price: float) -> Tuple[bool, str, str]:
        """
        الشرط 3: هل هناك جدار بيع (Sell Wall) أو مقاومة قوية قريبة؟

        جدار البيع في دفتر الأوامر = مقاومة قوية فورية.
        إذا كان السعر يقترب من جدار بيع ضخم → خطر Liquidity Grab.

        Returns: (is_triggered, wall_price, description)
        """
        if not self.ob:
            return False, "N/A", "OrderBook Intel غير متاح"
        try:
            ob_data = self.ob.full_analysis(symbol)
            walls = ob_data.get('walls', {})
            sell_wall = walls.get('sell_wall', False)
            sell_wall_price = walls.get('sell_wall_price')

            # فحص إشارة التوزيع (Distribution) من Iceberg analysis
            iceberg = ob_data.get('iceberg', {})
            is_distribution = iceberg.get('signal') == 'DISTRIBUTION'

            if sell_wall and sell_wall_price:
                distance = (sell_wall_price - current_price) / current_price
                if 0 < distance <= 0.02:  # جدار بيع على بُعد 2% أو أقل
                    return True, str(sell_wall_price), (
                        f"جدار بيع ضخم عند ${sell_wall_price:.4f} "
                        f"(على بُعد {distance*100:.1f}% فقط) ⚠️"
                    )

            if is_distribution:
                return True, "N/A", "إشارة توزيع (Distribution) في دفتر الأوامر 🔴"

            return False, "N/A", "لا توجد مقاومة قوية قريبة في دفتر الأوامر ✅"
        except Exception as e:
            logger.debug(f"Sell wall check error for {symbol}: {e}")
            return False, "N/A", f"خطأ في تحليل دفتر الأوامر: {e}"

    def _check_liquidity_above(self, symbol: str) -> Tuple[bool, float, str]:
        """
        الشرط 4: هل السيولة (Liquidations) مركزة فوق القمة الأخيرة؟

        إذا كانت تصفيات Long الأخيرة أكبر بكثير من تصفيات Short →
        هذا يعني أن كثيراً من الـ Long traders وضعوا Stop-Loss فوق
        القمة الأخيرة → الحيتان ستدفع السعر للأعلى لتصفيتهم ثم تهبط.

        Returns: (is_triggered, ratio, description)
        """
        if not self.cg:
            return False, 0.0, "CoinGlass غير متاح"
        try:
            clean = symbol.replace('/USDT', '').replace('-USDT', '').upper()
            liq_data = self.cg.get_liquidation_data(clean)

            long_liq_1h = liq_data.get('total_1h', 0)
            long_liq_4h = liq_data.get('total_4h', 0)
            long_liq_24h = liq_data.get('long_24h', 0)
            short_liq_24h = liq_data.get('short_24h', 0)

            # نسبة تصفيات Long إلى Short في 24h
            if short_liq_24h > 0:
                liq_ratio = long_liq_24h / short_liq_24h
            else:
                liq_ratio = 1.0

            # ارتفاع تصفيات Long في الساعة الأخيرة = سيولة تُصطاد الآن
            if long_liq_1h > 50000 and long_liq_1h > long_liq_4h * 0.4:
                return True, liq_ratio, (
                    f"تصفيات Long في آخر ساعة: ${long_liq_1h:,.0f} ⚠️\n"
                    f"  ↳ سيولة Long تُصطاد الآن — قد يكون Liquidity Grab جارياً"
                )

            if liq_ratio >= self.LIQ_RATIO_THRESHOLD:
                return True, liq_ratio, (
                    f"تصفيات Long ({long_liq_24h:,.0f}) > تصفيات Short ({short_liq_24h:,.0f}) "
                    f"بنسبة {liq_ratio:.1f}x ⚠️\n"
                    f"  ↳ سيولة Long مركزة فوق القمة = طُعم محتمل"
                )

            return False, liq_ratio, (
                f"توزيع التصفيات متوازن (Long/Short ratio: {liq_ratio:.1f}x) ✅"
            )
        except Exception as e:
            logger.debug(f"Liquidity check error for {symbol}: {e}")
            return False, 0.0, f"خطأ في جلب بيانات التصفيات: {e}"

    # ──────────────────────────────────────────────────────────
    # التحليل الكامل والاستنتاج
    # ──────────────────────────────────────────────────────────

    def analyze(self, symbol: str, current_price: float) -> Dict:
        """
        التحليل الكامل لاحتمالية Liquidity Grab

        يدمج الشروط الأربعة ويستنتج:
        - مستوى الخطر (HIGH / MEDIUM / LOW / NONE)
        - الإجراء المطلوب (BLOCK / REDUCE_SIZE / RAISE_SL / PROCEED)
        - التوصية بالعربية

        Args:
            symbol: رمز العملة (مثال: 'BTC/USDT' أو 'BTC-USDT')
            current_price: السعر الحالي

        Returns:
            dict مع مفاتيح: risk_level, probability, action, recommendation, details
        """
        logger.info(f"🔍 [LiquidityGrab] تحليل {symbol} @ ${current_price:.4f}")

        # تحليل الشروط الأربعة
        oi_triggered, oi_val, oi_desc = self._check_oi_surge(symbol)
        funding_triggered, funding_val, funding_desc = self._check_funding_rate(symbol)
        resistance_triggered, wall_price, resistance_desc = self._check_sell_wall_or_resistance(symbol, current_price)
        liquidity_triggered, liq_ratio, liq_desc = self._check_liquidity_above(symbol)

        conditions = [oi_triggered, funding_triggered, resistance_triggered, liquidity_triggered]
        conditions_triggered = sum(conditions)

        # أوزان الشروط (Funding له وزن أعلى لأنه أكثر موثوقية)
        weights = [0.25, 0.30, 0.20, 0.25]
        probability = sum(w for c, w in zip(conditions, weights) if c)

        # ── تحديد مستوى الخطر والإجراء ──
        if conditions_triggered >= 3 or probability >= 0.70:
            risk_level = 'HIGH'
            action = 'BLOCK'
            recommendation = (
                f"⛔ خطر Liquidity Grab مرتفع جداً! ({conditions_triggered}/4 شروط متوافرة)\n\n"
                f"التحليل:\n"
                f"  {'✅' if oi_triggered else '❌'} {oi_desc}\n"
                f"  {'✅' if funding_triggered else '❌'} {funding_desc}\n"
                f"  {'✅' if resistance_triggered else '❌'} {resistance_desc}\n"
                f"  {'✅' if liquidity_triggered else '❌'} {liq_desc}\n\n"
                f"الاستنتاج: السوق يُهيِّئ لصيد Stop-Loss قبل هبوط حاد.\n"
                f"القرار: لا تدخل في {symbol} الآن. انتظر حتى تنتهي عملية الصيد."
            )
        elif conditions_triggered == 2 or probability >= 0.45:
            risk_level = 'MEDIUM'
            action = 'REDUCE_SIZE'
            recommendation = (
                f"⚠️ خطر Liquidity Grab متوسط ({conditions_triggered}/4 شروط).\n\n"
                f"التحليل:\n"
                f"  {'✅' if oi_triggered else '❌'} {oi_desc}\n"
                f"  {'✅' if funding_triggered else '❌'} {funding_desc}\n"
                f"  {'✅' if resistance_triggered else '❌'} {resistance_desc}\n"
                f"  {'✅' if liquidity_triggered else '❌'} {liq_desc}\n\n"
                f"القرار: قلل حجم الصفقة 50% وارفع SL أقرب من نقطة الدخول (1% بدلاً من 1.5%)."
            )
        elif conditions_triggered == 1:
            risk_level = 'LOW'
            action = 'RAISE_SL'
            recommendation = (
                f"🟡 خطر Liquidity Grab منخفض ({conditions_triggered}/4 شروط).\n"
                f"القرار: ضع SL أضيق قليلاً (1.2% بدلاً من 1.5%)."
            )
        else:
            risk_level = 'NONE'
            action = 'PROCEED'
            recommendation = (
                f"✅ لا إشارات Liquidity Grab. يمكن الدخول بشكل طبيعي.\n"
                f"  {oi_desc}\n  {funding_desc}\n  {resistance_desc}\n  {liq_desc}"
            )

        result = {
            'symbol': symbol,
            'current_price': current_price,
            'risk_level': risk_level,
            'probability': round(probability, 3),
            'conditions_triggered': conditions_triggered,
            'action': action,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat(),
            'details': {
                'oi_surge': {
                    'triggered': oi_triggered,
                    'value_pct': round(oi_val * 100, 2),
                    'description': oi_desc
                },
                'funding_rate': {
                    'triggered': funding_triggered,
                    'value_pct': round(funding_val * 100, 4),
                    'description': funding_desc
                },
                'sell_wall': {
                    'triggered': resistance_triggered,
                    'wall_price': wall_price,
                    'description': resistance_desc
                },
                'liquidity_above': {
                    'triggered': liquidity_triggered,
                    'long_short_liq_ratio': round(liq_ratio, 2),
                    'description': liq_desc
                }
            }
        }

        # تسجيل النتيجة
        if risk_level in ('HIGH', 'MEDIUM'):
            logger.warning(
                f"🚨 [LiquidityGrab] {risk_level} | {symbol} @ ${current_price:.4f} | "
                f"Conditions: {conditions_triggered}/4 | Prob: {probability:.0%} | Action: {action}"
            )
        else:
            logger.info(
                f"✅ [LiquidityGrab] {risk_level} | {symbol} | "
                f"Conditions: {conditions_triggered}/4 | Action: {action}"
            )

        return result

    # ──────────────────────────────────────────────────────────
    # أدوات مساعدة للاستخدام في main.py
    # ──────────────────────────────────────────────────────────

    def get_adjusted_position_size(self, symbol: str, current_price: float,
                                    base_size: float) -> Tuple[float, str]:
        """
        حساب حجم الصفقة الآمن مع مراعاة خطر Liquidity Grab

        Args:
            symbol: رمز العملة
            current_price: السعر الحالي
            base_size: حجم الصفقة الأساسي (بالدولار)

        Returns:
            (adjusted_size, reason)
        """
        analysis = self.analyze(symbol, current_price)
        action = analysis['action']

        if action == 'BLOCK':
            return 0.0, f"⛔ صفقة محظورة — خطر Liquidity Grab مرتفع ({analysis['conditions_triggered']}/4)"
        elif action == 'REDUCE_SIZE':
            return base_size * 0.5, f"⚠️ حجم الصفقة مُخفَّض 50% — خطر Liquidity Grab متوسط"
        elif action == 'RAISE_SL':
            return base_size * 0.75, f"🟡 حجم الصفقة مُخفَّض 25% — خطر Liquidity Grab منخفض"
        else:
            return base_size, "✅ حجم الصفقة طبيعي"

    def get_adjusted_sl_pct(self, symbol: str, current_price: float,
                             base_sl_pct: float = 0.015) -> Tuple[float, str]:
        """
        حساب نسبة SL الآمنة مع مراعاة خطر Liquidity Grab

        Args:
            symbol: رمز العملة
            current_price: السعر الحالي
            base_sl_pct: نسبة SL الأساسية (1.5% افتراضياً)

        Returns:
            (sl_pct, reason)
        """
        analysis = self.analyze(symbol, current_price)
        action = analysis['action']

        if action == 'BLOCK':
            return 0.008, "⛔ SL ضيق جداً (0.8%) — خطر Liquidity Grab مرتفع"
        elif action == 'REDUCE_SIZE':
            return 0.010, "⚠️ SL مُضيَّق (1.0%) — خطر Liquidity Grab متوسط"
        elif action == 'RAISE_SL':
            return 0.012, "🟡 SL مُضيَّق قليلاً (1.2%) — خطر Liquidity Grab منخفض"
        else:
            return base_sl_pct, f"✅ SL طبيعي ({base_sl_pct*100:.1f}%)"
