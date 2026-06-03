# ============================================================
# Trade Lak Bot - Order Book Intelligence
# وحدة ذكاء دفتر الأوامر — اكتشاف تحركات البوتات الكبيرة
# ============================================================
# تكتشف:
#   - الأوامر الضخمة (Iceberg Orders)
#   - عدم التوازن في دفتر الأوامر (Imbalance)
#   - ارتفاع الحجم المفاجئ (Volume Spike)
#   - جدران الشراء/البيع (Buy/Sell Walls)
#   - تقلص الفارق (Spread Compression) قبل الحركة الكبيرة
# ============================================================

import logging
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

# ---- عتبات الاكتشاف ----
LARGE_ORDER_MULTIPLIER  = 5.0   # الأمر الكبير = 5× متوسط الأوامر
IMBALANCE_THRESHOLD     = 0.65  # 65% من الأوامر في اتجاه واحد = اختلال
VOLUME_SPIKE_MULTIPLIER = 3.0   # ارتفاع الحجم 3× المتوسط = إشارة
WALL_SIZE_MULTIPLIER    = 8.0   # جدار = 8× متوسط الأوامر


class OrderBookIntel:
    """
    يحلل دفتر الأوامر لاكتشاف تحركات البوتات والأموال الكبيرة
    Analyzes order book to detect large bot and smart money movements
    """

    def __init__(self, okx_client):
        self.okx = okx_client
        self.volume_history = {}   # سجل حجم التداول لكل عملة
        self.price_history  = {}   # سجل الأسعار

    # ----------------------------------------------------------------
    # تحليل دفتر الأوامر / Order Book Analysis
    # ----------------------------------------------------------------

    def analyze_orderbook(self, symbol, depth=50):
        """
        تحليل شامل لدفتر الأوامر
        Comprehensive order book analysis
        """
        try:
            ob = self.okx.spot.fetch_order_book(symbol, limit=depth)
            bids = ob['bids']   # أوامر الشراء
            asks = ob['asks']   # أوامر البيع

            if not bids or not asks:
                return self._neutral_result()

            results = {}

            # 1. اختلال دفتر الأوامر
            results['imbalance'] = self._calculate_imbalance(bids, asks)

            # 2. اكتشاف الجدران
            results['walls'] = self._detect_walls(bids, asks)

            # 3. اكتشاف الأوامر الضخمة المخفية (Iceberg)
            results['iceberg'] = self._detect_iceberg_orders(bids, asks)

            # 4. تحليل الفارق (Spread)
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread_pct = ((best_ask - best_bid) / best_bid) * 100
            results['spread_pct'] = spread_pct
            results['spread_signal'] = "TIGHT" if spread_pct < 0.05 else "NORMAL"

            # 5. الإشارة الإجمالية
            results['signal'] = self._derive_signal(results)
            results['symbol'] = symbol

            logger.debug(
                f"Order Book {symbol}: {results['signal']} | "
                f"Imbalance: {results['imbalance']['ratio']:.2f} | "
                f"Spread: {spread_pct:.4f}%"
            )
            return results

        except Exception as e:
            logger.error(f"خطأ في تحليل دفتر الأوامر لـ {symbol}: {e}")
            return self._neutral_result()

    def _calculate_imbalance(self, bids, asks):
        """حساب اختلال دفتر الأوامر"""
        bid_volume = sum(b[1] for b in bids[:20])
        ask_volume = sum(a[1] for a in asks[:20])
        total = bid_volume + ask_volume

        if total == 0:
            return {"ratio": 0.5, "signal": "NEUTRAL", "bid_vol": 0, "ask_vol": 0}

        bid_ratio = bid_volume / total

        if bid_ratio > IMBALANCE_THRESHOLD:
            signal = "BUY_PRESSURE"    # ضغط شراء قوي
        elif bid_ratio < (1 - IMBALANCE_THRESHOLD):
            signal = "SELL_PRESSURE"   # ضغط بيع قوي
        else:
            signal = "BALANCED"

        return {
            "ratio":      bid_ratio,
            "signal":     signal,
            "bid_vol":    bid_volume,
            "ask_vol":    ask_volume,
        }

    def _detect_walls(self, bids, asks):
        """اكتشاف جدران الشراء والبيع"""
        if len(bids) < 5 or len(asks) < 5:
            return {"buy_wall": False, "sell_wall": False}

        avg_bid_size = np.mean([b[1] for b in bids[:20]])
        avg_ask_size = np.mean([a[1] for a in asks[:20]])

        # جدار شراء: أمر شراء ضخم جداً
        buy_wall  = False
        sell_wall = False
        buy_wall_price  = None
        sell_wall_price = None

        for bid in bids[:10]:
            if bid[1] > avg_bid_size * WALL_SIZE_MULTIPLIER:
                buy_wall = True
                buy_wall_price = bid[0]
                logger.info(
                    f"جدار شراء مكتشف عند {bid[0]:.6f} "
                    f"(الحجم: {bid[1]:.2f} = {bid[1]/avg_bid_size:.1f}× المتوسط)"
                )
                break

        for ask in asks[:10]:
            if ask[1] > avg_ask_size * WALL_SIZE_MULTIPLIER:
                sell_wall = True
                sell_wall_price = ask[0]
                logger.info(
                    f"جدار بيع مكتشف عند {ask[0]:.6f} "
                    f"(الحجم: {ask[1]:.2f} = {ask[1]/avg_ask_size:.1f}× المتوسط)"
                )
                break

        return {
            "buy_wall":        buy_wall,
            "sell_wall":       sell_wall,
            "buy_wall_price":  buy_wall_price,
            "sell_wall_price": sell_wall_price,
        }

    def _detect_iceberg_orders(self, bids, asks):
        """
        اكتشاف أوامر Iceberg (أوامر ضخمة مخفية تظهر تدريجياً)
        الأوامر الضخمة التي تتجدد بسرعة = بوت كبير يتراكم
        """
        bid_sizes = [b[1] for b in bids[:30]]
        ask_sizes = [a[1] for a in asks[:30]]

        avg_bid = np.mean(bid_sizes) if bid_sizes else 0
        avg_ask = np.mean(ask_sizes) if ask_sizes else 0
        std_bid = np.std(bid_sizes) if bid_sizes else 0
        std_ask = np.std(ask_sizes) if ask_sizes else 0

        # أوامر Iceberg = تباين عالٍ مع وجود أوامر ضخمة
        bid_iceberg = std_bid > avg_bid * LARGE_ORDER_MULTIPLIER
        ask_iceberg = std_ask > avg_ask * LARGE_ORDER_MULTIPLIER

        return {
            "bid_iceberg": bid_iceberg,
            "ask_iceberg": ask_iceberg,
            "signal": "ACCUMULATION" if bid_iceberg else
                      "DISTRIBUTION" if ask_iceberg else "NORMAL"
        }

    def _derive_signal(self, results):
        """استخلاص الإشارة الإجمالية من كل التحليلات"""
        score = 0

        imbalance = results.get('imbalance', {})
        walls     = results.get('walls', {})
        iceberg   = results.get('iceberg', {})

        if imbalance.get('signal') == 'BUY_PRESSURE':
            score += 2
        elif imbalance.get('signal') == 'SELL_PRESSURE':
            score -= 2

        if walls.get('buy_wall'):
            score += 1   # جدار شراء = دعم قوي
        if walls.get('sell_wall'):
            score -= 1   # جدار بيع = مقاومة قوية

        if iceberg.get('signal') == 'ACCUMULATION':
            score += 2
        elif iceberg.get('signal') == 'DISTRIBUTION':
            score -= 2

        if results.get('spread_signal') == 'TIGHT':
            score += 1   # فارق ضيق = سيولة عالية = حركة قادمة

        if score >= 3:
            return "STRONG_BUY"
        elif score >= 1:
            return "BUY"
        elif score <= -3:
            return "STRONG_SELL"
        elif score <= -1:
            return "SELL"
        else:
            return "NEUTRAL"

    # ----------------------------------------------------------------
    # اكتشاف ارتفاع الحجم / Volume Spike Detection
    # ----------------------------------------------------------------

    def detect_volume_spike(self, symbol, current_volume):
        """
        اكتشاف ارتفاع مفاجئ في حجم التداول
        Detects sudden volume spikes indicating large player entry
        """
        if symbol not in self.volume_history:
            self.volume_history[symbol] = deque(maxlen=20)

        history = self.volume_history[symbol]

        if len(history) < 5:
            history.append(current_volume)
            return {"spike": False, "ratio": 1.0, "signal": "NORMAL"}

        avg_volume = np.mean(list(history))
        ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        history.append(current_volume)

        if ratio >= VOLUME_SPIKE_MULTIPLIER:
            logger.info(
                f"ارتفاع حجم مفاجئ لـ {symbol}: "
                f"{ratio:.1f}× المتوسط — بوت/حوت كبير يدخل!"
            )
            return {"spike": True, "ratio": ratio, "signal": "LARGE_PLAYER_ENTRY"}
        elif ratio >= 2.0:
            return {"spike": True, "ratio": ratio, "signal": "ELEVATED_ACTIVITY"}
        else:
            return {"spike": False, "ratio": ratio, "signal": "NORMAL"}

    # ----------------------------------------------------------------
    # التحليل الشامل / Full Analysis
    # ----------------------------------------------------------------

    def full_analysis(self, symbol, current_volume=None):
        """
        تحليل شامل يدمج دفتر الأوامر + الحجم
        Full analysis combining order book + volume
        """
        ob_result = self.analyze_orderbook(symbol)

        volume_result = {"spike": False, "ratio": 1.0, "signal": "NORMAL"}
        if current_volume:
            volume_result = self.detect_volume_spike(symbol, current_volume)

        # دمج الإشارتين
        ob_signal  = ob_result.get('signal', 'NEUTRAL')
        vol_signal = volume_result.get('signal', 'NORMAL')

        # إذا كان هناك ارتفاع في الحجم + ضغط شراء = إشارة قوية جداً
        if vol_signal == 'LARGE_PLAYER_ENTRY' and ob_signal in ('BUY', 'STRONG_BUY'):
            combined_signal = "VERY_STRONG_BUY"
            combined_score  = 5
        elif vol_signal == 'LARGE_PLAYER_ENTRY' and ob_signal in ('SELL', 'STRONG_SELL'):
            combined_signal = "VERY_STRONG_SELL"
            combined_score  = -5
        elif ob_signal == 'STRONG_BUY':
            combined_signal = "STRONG_BUY"
            combined_score  = 3
        elif ob_signal == 'STRONG_SELL':
            combined_signal = "STRONG_SELL"
            combined_score  = -3
        elif ob_signal == 'BUY':
            combined_signal = "BUY"
            combined_score  = 2
        elif ob_signal == 'SELL':
            combined_signal = "SELL"
            combined_score  = -2
        else:
            combined_signal = "NEUTRAL"
            combined_score  = 0

        return {
            "signal":        combined_signal,
            "score":         combined_score,
            "orderbook":     ob_result,
            "volume":        volume_result,
        }

    def _neutral_result(self):
        return {
            "signal": "NEUTRAL", "score": 0,
            "imbalance": {"ratio": 0.5, "signal": "BALANCED"},
            "walls": {"buy_wall": False, "sell_wall": False},
            "iceberg": {"signal": "NORMAL"},
            "spread_pct": 0, "spread_signal": "NORMAL",
        }
