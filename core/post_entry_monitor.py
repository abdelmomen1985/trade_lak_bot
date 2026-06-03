# ============================================================
# Post-Entry Liquidity & Momentum Monitor
# مراقبة السيولة والزخم بعد الدخول في الصفقة
# يقرر: استمرار / تشديد Stop Loss / خروج مبكر
# ============================================================
import logging
import time
from collections import deque
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class PostEntryLiquidityMonitor:
    """
    يراقب كل صفقة مفتوحة بعد الدخول ويتتبع:
    1. Order Book Depth  — هل السيولة تتراجع؟
    2. Volume Momentum   — هل الزخم يتلاشى؟
    3. Open Interest     — هل الفائدة المفتوحة تنخفض؟
    4. Funding Rate      — هل يتحول ضد الصفقة؟
    5. Bid/Ask Imbalance — هل الضغط يتحول للبيع؟

    قرارات الخروج:
    - EARLY_EXIT   : تدهور شديد → خروج فوري
    - TIGHTEN_SL   : تدهور متوسط → تشديد Stop Loss
    - HOLD         : كل شيء طبيعي → استمرار
    """

    # ── حدود قرار الخروج ──
    LIQUIDITY_DROP_THRESHOLD    = 0.35   # 35% انخفاض في سيولة دفتر الأوامر
    VOLUME_DROP_THRESHOLD       = 0.40   # 40% انخفاض في الحجم
    OI_DROP_THRESHOLD           = 0.025  # 2.5% انخفاض في OI خلال ساعة
    FUNDING_FLIP_THRESHOLD      = 0.015  # 0.015% معدل تمويل عكسي خطير
    IMBALANCE_FLIP_THRESHOLD    = 0.40   # نسبة bid/ask أقل من 0.40 = ضغط بيع
    MOMENTUM_SCORE_EXIT         = -3     # نقاط زخم أقل من -3 = خروج
    MOMENTUM_SCORE_TIGHTEN      = -2     # نقاط زخم أقل من -2 = تشديد SL

    # ── تاريخ القراءات لكل عملة ──
    MAX_HISTORY = 10  # آخر 10 قراءات

    def __init__(self, okx_client, coinglass_client, ob_intel):
        self.okx = okx_client
        self.coinglass = coinglass_client
        self.ob_intel = ob_intel
        # تاريخ القراءات: {symbol: deque([{timestamp, ob_depth, volume, oi, funding, imbalance}])}
        self._history: Dict[str, deque] = {}
        # قراءة الدخول الأولى: {symbol: {ob_depth_entry, volume_entry, oi_entry}}
        self._entry_snapshot: Dict[str, dict] = {}

    # ================================================================
    # تسجيل لحظة الدخول
    # ================================================================
    def record_entry(self, symbol: str, market: str = 'spot'):
        """
        يُستدعى فور فتح الصفقة — يأخذ لقطة أولية للمقارنة لاحقاً
        """
        try:
            snapshot = self._take_snapshot(symbol, market)
            if snapshot:
                snapshot['timestamp'] = time.time()
                self._entry_snapshot[symbol] = snapshot
                self._history[symbol] = deque(maxlen=self.MAX_HISTORY)
                self._history[symbol].append(snapshot)
                logger.info(
                    f"📸 [PostEntry] لقطة الدخول لـ {symbol}: "
                    f"OB_depth={snapshot['ob_depth']:.0f} | "
                    f"vol={snapshot['volume']:.2f} | "
                    f"OI_change={snapshot['oi_change_1h']:.2%}"
                )
        except Exception as e:
            logger.debug(f"PostEntry record_entry error {symbol}: {e}")

    # ================================================================
    # المراقبة الدورية
    # ================================================================
    def check(self, symbol: str, market: str, trade: dict,
              current_price: float) -> Tuple[str, str]:
        """
        يُستدعى في كل دورة مراقبة للصفقة المفتوحة.

        Returns:
            (decision, reason)
            decision: 'HOLD' | 'TIGHTEN_SL' | 'EARLY_EXIT'
        """
        try:
            snapshot = self._take_snapshot(symbol, market)
            if not snapshot:
                return 'HOLD', ''

            # تخزين القراءة
            if symbol not in self._history:
                self._history[symbol] = deque(maxlen=self.MAX_HISTORY)
            self._history[symbol].append(snapshot)

            entry = self._entry_snapshot.get(symbol, snapshot)
            score = 0
            reasons = []

            # ── 1. Order Book Depth (سيولة دفتر الأوامر) ──
            if entry['ob_depth'] > 0:
                depth_change = (snapshot['ob_depth'] - entry['ob_depth']) / entry['ob_depth']
                if depth_change < -self.LIQUIDITY_DROP_THRESHOLD:
                    score -= 2
                    reasons.append(f"📉 سيولة OB انخفضت {depth_change:.0%}")
                elif depth_change < -0.20:
                    score -= 1
                    reasons.append(f"⚠️ سيولة OB تراجعت {depth_change:.0%}")

            # ── 2. Bid/Ask Imbalance (ضغط البيع) ──
            imb = snapshot.get('imbalance_ratio', 1.0)
            direction = trade.get('direction', 'SPOT_BUY')
            if direction in ('SPOT_BUY', 'LONG'):
                if imb < self.IMBALANCE_FLIP_THRESHOLD:
                    score -= 2
                    reasons.append(f"🔴 ضغط بيع قوي (bid/ask={imb:.2f})")
                elif imb < 0.55:
                    score -= 1
                    reasons.append(f"⚠️ ضغط بيع متوسط (bid/ask={imb:.2f})")
            else:  # SHORT
                if imb > (1 / self.IMBALANCE_FLIP_THRESHOLD):
                    score -= 2
                    reasons.append(f"🔴 ضغط شراء قوي ضد SHORT (bid/ask={imb:.2f})")

            # ── 3. Volume Momentum (زخم الحجم) ──
            if entry['volume'] > 0:
                vol_change = (snapshot['volume'] - entry['volume']) / entry['volume']
                if vol_change < -self.VOLUME_DROP_THRESHOLD:
                    score -= 1
                    reasons.append(f"📉 حجم تداول انخفض {vol_change:.0%}")
                elif vol_change > 0.50:
                    # ارتفاع الحجم في اتجاه عكسي؟
                    if snapshot.get('ob_signal') in ('SELL', 'STRONG_SELL', 'VERY_STRONG_SELL'):
                        score -= 2
                        reasons.append(f"🔴 حجم مرتفع مع ضغط بيع")
                    else:
                        score += 1  # حجم مرتفع في اتجاه الصفقة = إيجابي

            # ── 4. Open Interest (الفائدة المفتوحة) ──
            oi_change = snapshot.get('oi_change_1h', 0)
            if direction in ('SPOT_BUY', 'LONG') and oi_change < -self.OI_DROP_THRESHOLD:
                score -= 1
                reasons.append(f"📉 OI انخفض {oi_change:.2%} في ساعة")
            elif direction == 'SHORT' and oi_change > self.OI_DROP_THRESHOLD:
                score -= 1
                reasons.append(f"📉 OI ارتفع {oi_change:.2%} ضد SHORT")

            # ── 5. Funding Rate (معدل التمويل) ──
            funding = snapshot.get('funding_rate', 0)
            if direction in ('SPOT_BUY', 'LONG') and funding > self.FUNDING_FLIP_THRESHOLD:
                score -= 1
                reasons.append(f"⚠️ Funding مرتفع ({funding:.4%}) = ضغط على LONG")
            elif direction == 'SHORT' and funding < -self.FUNDING_FLIP_THRESHOLD:
                score -= 1
                reasons.append(f"⚠️ Funding سلبي ({funding:.4%}) = ضغط على SHORT")
            elif direction in ('SPOT_BUY', 'LONG') and funding < -0.005:
                score += 1  # Funding سلبي = دعم للصفقة الشرائية

            # ── 6. Price Momentum (زخم السعر) ──
            history_list = list(self._history[symbol])
            if len(history_list) >= 3:
                prices = [h.get('price', current_price) for h in history_list[-3:]]
                if all(prices[i] < prices[i-1] for i in range(1, len(prices))):
                    if direction in ('SPOT_BUY', 'LONG'):
                        score -= 1
                        reasons.append("📉 سعر في تراجع متواصل")
                elif all(prices[i] > prices[i-1] for i in range(1, len(prices))):
                    if direction in ('SPOT_BUY', 'LONG'):
                        score += 1  # زخم صاعد

            # ── القرار النهائي ──
            reason_str = ' | '.join(reasons) if reasons else 'كل المؤشرات طبيعية'

            # ── حماية: لا خروج مبكر إلا بشروط صارمة ──
            if score <= self.MOMENTUM_SCORE_EXIT:
                entry_snap = self._entry_snapshot.get(symbol, {})
                entry_price = entry_snap.get('price', current_price)
                price_vs_entry = (current_price - entry_price) / entry_price if entry_price > 0 else 0
                open_time = entry_snap.get('timestamp', time.time())
                minutes_open = (time.time() - open_time) / 60
                # الخروج المبكر مسموح فقط إذا:
                # 1. السعر انخفض أكثر من 0.3% عن الدخول (خسارة فعلية)
                # 2. أو الصفقة مفتوحة أكثر من 30 دقيقة (وقت كافٍ للتقييم)
                if price_vs_entry > -0.003 and minutes_open < 30:
                    logger.info(
                        f"⏸️ [PostEntry] {symbol} → حجب EARLY_EXIT "
                        f"(score={score}, ربح={price_vs_entry:.2%}, وقت={minutes_open:.1f}د) "
                        f"— السعر لم ينخفض بما يكفي بعد"
                    )
                    return 'HOLD', f"محجوب: السعر +{price_vs_entry:.2%} بعد {minutes_open:.1f}د"
                logger.warning(
                    f"🚨 [PostEntry] {symbol} → EARLY_EXIT "
                    f"(score={score}, ربح={price_vs_entry:.2%}, وقت={minutes_open:.1f}د) | {reason_str}"
                )
                return 'EARLY_EXIT', f"💧 تدهور السيولة والزخم: {reason_str}"

            elif score <= self.MOMENTUM_SCORE_TIGHTEN:
                logger.info(
                    f"⚠️ [PostEntry] {symbol} → TIGHTEN_SL "
                    f"(score={score}) | {reason_str}"
                )
                return 'TIGHTEN_SL', f"⚠️ تراجع السيولة: {reason_str}"

            else:
                if score > 0:
                    logger.debug(f"✅ [PostEntry] {symbol} → HOLD (score=+{score}) — زخم قوي")
                else:
                    logger.debug(f"✅ [PostEntry] {symbol} → HOLD (score={score})")
                return 'HOLD', reason_str

        except Exception as e:
            logger.debug(f"PostEntry check error {symbol}: {e}")
            return 'HOLD', ''

    # ================================================================
    # تنظيف عند إغلاق الصفقة
    # ================================================================
    def cleanup(self, symbol: str):
        """إزالة بيانات الصفقة المغلقة"""
        self._history.pop(symbol, None)
        self._entry_snapshot.pop(symbol, None)

    # ================================================================
    # أخذ لقطة فورية للبيانات
    # ================================================================
    def _take_snapshot(self, symbol: str, market: str) -> Optional[dict]:
        """أخذ لقطة شاملة لمؤشرات السيولة والزخم"""
        try:
            snap = {'timestamp': time.time(), 'symbol': symbol}

            # ── السعر والحجم ──
            ticker = self.okx.get_ticker(symbol, market)
            if ticker:
                snap['price'] = ticker.get('price', 0)
                snap['volume'] = ticker.get('volume', 0)
            else:
                snap['price'] = 0
                snap['volume'] = 0

            # ── Order Book ──
            ob = self.ob_intel.full_analysis(symbol, snap.get('volume'))
            if ob:
                # عمق دفتر الأوامر = مجموع حجم أوامر الشراء والبيع
                imb = ob.get('imbalance', {})
                bid_vol = imb.get('bid_volume', 0)
                ask_vol = imb.get('ask_volume', 0)
                snap['ob_depth'] = bid_vol + ask_vol
                snap['imbalance_ratio'] = (bid_vol / ask_vol) if ask_vol > 0 else 1.0
                snap['ob_signal'] = ob.get('signal', 'NEUTRAL')
            else:
                snap['ob_depth'] = 0
                snap['imbalance_ratio'] = 1.0
                snap['ob_signal'] = 'NEUTRAL'

            # ── Open Interest و Funding Rate (من CoinGlass) ──
            clean_sym = symbol.replace('/USDT', '')
            try:
                oi_data = self.coinglass.get_open_interest(clean_sym)
                snap['oi_change_1h'] = oi_data.get('change_1h', 0)
                snap['oi_current'] = oi_data.get('current', 0)
            except Exception:
                snap['oi_change_1h'] = 0
                snap['oi_current'] = 0

            try:
                funding = self.coinglass.get_funding_rate(clean_sym)
                snap['funding_rate'] = funding if funding else 0
            except Exception:
                snap['funding_rate'] = 0

            return snap

        except Exception as e:
            logger.debug(f"_take_snapshot error {symbol}: {e}")
            return None

    # ================================================================
    # تقرير ملخص للصفقة
    # ================================================================
    def get_summary(self, symbol: str) -> str:
        """ملخص نصي لحالة الصفقة"""
        history = list(self._history.get(symbol, []))
        if not history:
            return "لا توجد بيانات"
        latest = history[-1]
        entry = self._entry_snapshot.get(symbol, latest)
        depth_chg = 0
        if entry.get('ob_depth', 0) > 0:
            depth_chg = (latest['ob_depth'] - entry['ob_depth']) / entry['ob_depth'] * 100
        vol_chg = 0
        if entry.get('volume', 0) > 0:
            vol_chg = (latest['volume'] - entry['volume']) / entry['volume'] * 100
        return (
            f"OB Depth: {depth_chg:+.0f}% | "
            f"Volume: {vol_chg:+.0f}% | "
            f"OI 1h: {latest.get('oi_change_1h', 0):+.2%} | "
            f"Funding: {latest.get('funding_rate', 0):.4%} | "
            f"Imbalance: {latest.get('imbalance_ratio', 1):.2f} | "
            f"Signal: {latest.get('ob_signal', 'N/A')}"
        )
