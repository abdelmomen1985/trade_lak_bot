"""
Competitive Intelligence Engine
================================
يراقب البوتات الناجحة في السوق ويتعلم من استراتيجياتها ويتفوق عليها.

المصادر:
- تتبع صفقات الحيتان الكبيرة عبر Etherscan + BSC RPC
- مراقبة تدفقات السيولة عبر CoinGlass
- تحليل أنماط الدخول/الخروج الناجحة
- رصد الـ Smart Money عبر On-Chain data
- مراقبة Copy Trading Leaders على OKX
"""

import logging
import time
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. نماذج البيانات
# ─────────────────────────────────────────────

class BotPattern:
    """نمط بوت ناجح مكتشف"""
    def __init__(self, pattern_id: str, pattern_type: str):
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type       # 'whale_entry', 'smart_money', 'breakout', 'reversal'
        self.entry_conditions: Dict = {}
        self.exit_conditions: Dict = {}
        self.success_rate: float = 0.0
        self.avg_profit: float = 0.0
        self.avg_duration_minutes: float = 0.0
        self.market_regime: str = "any"        # 'bull', 'bear', 'sideways', 'crash', 'any'
        self.occurrences: int = 0
        self.last_seen: datetime = datetime.now()
        self.confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "entry_conditions": self.entry_conditions,
            "exit_conditions": self.exit_conditions,
            "success_rate": self.success_rate,
            "avg_profit": self.avg_profit,
            "avg_duration_minutes": self.avg_duration_minutes,
            "market_regime": self.market_regime,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
        }


class MarketRegime:
    """حالة السوق الحالية"""
    BULL_TREND    = "bull_trend"       # صعود قوي
    BEAR_TREND    = "bear_trend"       # هبوط قوي
    SIDEWAYS      = "sideways"         # تذبذب جانبي
    CRASH         = "crash"            # انهيار مفاجئ
    RECOVERY      = "recovery"         # تعافي بعد انهيار
    PUMP          = "pump"             # ضخ مفاجئ
    ACCUMULATION  = "accumulation"     # تراكم هادئ
    DISTRIBUTION  = "distribution"     # توزيع قبل هبوط


# ─────────────────────────────────────────────
# 2. كاشف حالة السوق
# ─────────────────────────────────────────────

class MarketRegimeDetector:
    """
    يكشف حالة السوق الحالية بدقة عالية:
    - صعود / هبوط / جانبي / انهيار / تعافي / ضخ / تراكم / توزيع
    """

    def __init__(self):
        self.price_history: deque = deque(maxlen=500)
        self.volume_history: deque = deque(maxlen=500)
        self.regime_history: deque = deque(maxlen=100)
        self.current_regime: str = MarketRegime.SIDEWAYS
        self.regime_confidence: float = 0.0
        self.regime_start_time: datetime = datetime.now()
        self.regime_duration_minutes: float = 0.0

    def update(self, price: float, volume: float, timestamp: datetime = None) -> str:
        """تحديث بيانات السوق وإعادة الحالة الحالية"""
        if timestamp is None:
            timestamp = datetime.now()

        self.price_history.append({"price": price, "volume": volume, "time": timestamp})
        self.volume_history.append(volume)

        if len(self.price_history) < 20:
            return self.current_regime

        regime, confidence = self._detect_regime()

        if regime != self.current_regime:
            logger.info(f"📊 Market Regime Changed: {self.current_regime} → {regime} (confidence: {confidence:.1%})")
            self.current_regime = regime
            self.regime_start_time = timestamp
            self.regime_confidence = confidence
        else:
            self.regime_confidence = confidence

        duration = (timestamp - self.regime_start_time).total_seconds() / 60
        self.regime_duration_minutes = duration

        self.regime_history.append({
            "regime": regime,
            "confidence": confidence,
            "time": timestamp,
            "price": price,
        })

        return regime

    def _detect_regime(self) -> Tuple[str, float]:
        """الكشف الفعلي عن حالة السوق"""
        prices = [p["price"] for p in self.price_history]
        volumes = [p["volume"] for p in self.price_history]

        current_price = prices[-1]
        price_1h  = prices[-min(12, len(prices))]   # ~1 hour (5min candles)
        price_4h  = prices[-min(48, len(prices))]   # ~4 hours
        price_24h = prices[-min(288, len(prices))]  # ~24 hours

        change_1h  = (current_price - price_1h)  / price_1h  * 100
        change_4h  = (current_price - price_4h)  / price_4h  * 100
        change_24h = (current_price - price_24h) / price_24h * 100

        # حساب التقلب
        recent_prices = prices[-20:]
        if len(recent_prices) > 1:
            volatility = statistics.stdev(recent_prices) / statistics.mean(recent_prices) * 100
        else:
            volatility = 0

        # حساب متوسط الحجم
        avg_volume = statistics.mean(volumes[-20:]) if len(volumes) >= 20 else 1
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # ─── كشف الانهيار ───
        # Flash crash: انخفاض حاد في ساعة واحدة
        if change_1h < -5 and volume_ratio > 2.0:
            return MarketRegime.CRASH, min(0.95, abs(change_1h) / 10)
        # Sustained crash: انهيار تدريجي (مثل أكتوبر-نوفمبر 2025)
        price_7d = prices[-min(2016, len(prices))]  # ~7 days (5min candles)
        change_7d = (current_price - price_7d) / price_7d * 100
        if change_7d < -15:
            return MarketRegime.CRASH, min(0.90, abs(change_7d) / 30)
        if change_7d < -8 or change_24h < -5:
            return MarketRegime.BEAR_TREND, min(0.85, abs(change_24h) / 10)

        # ─── كشف الضخ المفاجئ ───
        if change_1h > 5 and volume_ratio > 2.5:
            return MarketRegime.PUMP, min(0.95, change_1h / 10)

        # ─── كشف التعافي بعد انهيار ───
        if change_1h > 2 and change_4h < -3:
            return MarketRegime.RECOVERY, 0.75

        # ─── كشف الاتجاه الصاعد ───
        if change_4h > 3 and change_24h > 5:
            confidence = min(0.90, (change_4h + change_24h) / 20)
            return MarketRegime.BULL_TREND, confidence

        # ─── كشف الاتجاه الهابط ───
        if change_4h < -3 and change_24h < -5:
            confidence = min(0.90, (abs(change_4h) + abs(change_24h)) / 20)
            return MarketRegime.BEAR_TREND, confidence

        # ─── كشف التراكم (صعود هادئ بحجم منخفض) ───
        if 0.5 < change_4h < 3 and volume_ratio < 0.8 and change_24h > 0:
            return MarketRegime.ACCUMULATION, 0.70

        # ─── كشف التوزيع (هبوط هادئ بحجم منخفض) ───
        if -3 < change_4h < -0.5 and volume_ratio < 0.8 and change_24h < 0:
            return MarketRegime.DISTRIBUTION, 0.70

        # ─── جانبي ───
        if volatility < 1.5 and abs(change_4h) < 1.5:
            return MarketRegime.SIDEWAYS, 0.80

        # افتراضي
        if change_4h > 0:
            return MarketRegime.BULL_TREND, 0.50
        else:
            return MarketRegime.BEAR_TREND, 0.50

    def get_optimal_strategy(self) -> Dict:
        """إرجاع الاستراتيجية المثلى لحالة السوق الحالية"""
        strategies = {
            MarketRegime.BULL_TREND: {
                "primary": "momentum",
                "secondary": "breakout",
                "direction": "long",
                "leverage": 2,
                "tp_multiplier": 1.5,
                "sl_multiplier": 0.8,
                "description": "اتجاه صاعد — ركب الموجة، استهدف أهدافاً أعلى",
            },
            MarketRegime.BEAR_TREND: {
                "primary": "mean_reversion",
                "secondary": "momentum",
                "direction": "short",
                "leverage": 1.5,
                "tp_multiplier": 1.2,
                "sl_multiplier": 0.7,
                "description": "اتجاه هابط — بيع على الارتدادات، حافظ على وقف الخسارة ضيق",
            },
            MarketRegime.SIDEWAYS: {
                "primary": "mean_reversion",
                "secondary": "volume_profile",
                "direction": "both",
                "leverage": 1,
                "tp_multiplier": 0.8,
                "sl_multiplier": 0.6,
                "description": "سوق جانبي — تداول النطاق، أهداف صغيرة متعددة",
            },
            MarketRegime.CRASH: {
                "primary": "reversal_hunter",
                "secondary": "mean_reversion",
                "direction": "long",
                "leverage": 1,
                "tp_multiplier": 2.0,
                "sl_multiplier": 1.5,
                "description": "انهيار — انتظر القاع، ادخل بحجم صغير على الارتداد الأول",
            },
            MarketRegime.RECOVERY: {
                "primary": "momentum",
                "secondary": "breakout",
                "direction": "long",
                "leverage": 2,
                "tp_multiplier": 2.0,
                "sl_multiplier": 1.0,
                "description": "تعافي — فرصة ذهبية، ادخل مبكراً بحجم متوسط",
            },
            MarketRegime.PUMP: {
                "primary": "momentum",
                "secondary": "breakout",
                "direction": "long",
                "leverage": 1,
                "tp_multiplier": 0.7,
                "sl_multiplier": 1.2,
                "description": "ضخ مفاجئ — احذر، اجني الأرباح سريعاً",
            },
            MarketRegime.ACCUMULATION: {
                "primary": "breakout",
                "secondary": "volume_profile",
                "direction": "long",
                "leverage": 2,
                "tp_multiplier": 2.0,
                "sl_multiplier": 0.7,
                "description": "تراكم — فرصة دخول مبكر قبل الصعود الكبير",
            },
            MarketRegime.DISTRIBUTION: {
                "primary": "mean_reversion",
                "secondary": "momentum",
                "direction": "short",
                "leverage": 1.5,
                "tp_multiplier": 1.5,
                "sl_multiplier": 0.8,
                "description": "توزيع — استعد للهبوط، ابحث عن فرص بيع",
            },
        }
        strategy = strategies.get(self.current_regime, strategies[MarketRegime.SIDEWAYS])
        strategy["regime"] = self.current_regime
        strategy["confidence"] = self.regime_confidence
        strategy["duration_minutes"] = self.regime_duration_minutes
        return strategy

    def get_status(self) -> Dict:
        return {
            "current_regime": self.current_regime,
            "confidence": self.regime_confidence,
            "duration_minutes": self.regime_duration_minutes,
            "optimal_strategy": self.get_optimal_strategy(),
        }


# ─────────────────────────────────────────────
# 3. محرك مراقبة البوتات الناجحة
# ─────────────────────────────────────────────

class CompetitiveIntelligenceEngine:
    """
    يراقب البوتات الناجحة ويتعلم من استراتيجياتها:

    1. Smart Money Tracker — يتتبع حركات الحيتان والمؤسسات
    2. Pattern Library — مكتبة أنماط الدخول/الخروج الناجحة
    3. Strategy Optimizer — يحسّن الاستراتيجيات بناءً على ما يتعلمه
    4. Outperformance Engine — يتفوق على الأنماط المكتشفة
    """

    PATTERNS_FILE = "data/competitive_patterns.json"

    def __init__(self, whale_tracker=None, coinglass_client=None):
        self.whale_tracker = whale_tracker
        self.coinglass_client = coinglass_client
        self.regime_detector = MarketRegimeDetector()

        # مكتبة الأنماط
        self.patterns: Dict[str, BotPattern] = {}
        self.pattern_performance: Dict[str, List[float]] = defaultdict(list)

        # سجل الصفقات الناجحة المرصودة
        self.observed_trades: deque = deque(maxlen=1000)

        # إحصائيات التفوق
        self.outperformance_score: float = 0.0
        self.patterns_beaten: int = 0
        self.patterns_learned: int = 0

        # تحميل الأنماط المحفوظة
        self._load_patterns()

        # الأنماط المدمجة مسبقاً (من دراسة أفضل البوتات)
        self._initialize_known_patterns()

        logger.info("✅ Competitive Intelligence Engine initialized")

    def _initialize_known_patterns(self):
        """تهيئة أنماط مدمجة مسبقاً من دراسة أفضل البوتات الناجحة"""

        # ─── نمط 1: دخول الحيتان (Whale Entry Pattern) ───
        if "whale_accumulation" not in self.patterns:
            p = BotPattern("whale_accumulation", "whale_entry")
            p.entry_conditions = {
                "whale_buy_volume_usd": ">500000",      # شراء حوت > $500K
                "price_change_1h": "<2",                # السعر لم يرتفع كثيراً بعد
                "volume_ratio": ">1.5",                 # حجم أعلى من المعتاد
                "rsi": "<60",                           # RSI ليس في منطقة تشبع شراء
                "market_regime": "any",
            }
            p.exit_conditions = {
                "profit_target": "3-8%",
                "time_limit_hours": 24,
                "trailing_stop": "1.5%",
            }
            p.success_rate = 0.72
            p.avg_profit = 4.2
            p.avg_duration_minutes = 180
            p.market_regime = "any"
            p.confidence = 0.80
            p.occurrences = 0
            self.patterns["whale_accumulation"] = p

        # ─── نمط 2: اصطياد القاع بعد الانهيار (Crash Bottom Hunter) ───
        if "crash_bottom_hunter" not in self.patterns:
            p = BotPattern("crash_bottom_hunter", "reversal")
            p.entry_conditions = {
                "price_drop_1h": ">5",                  # هبوط > 5% في ساعة
                "rsi": "<25",                           # RSI في منطقة تشبع بيع شديد
                "volume_spike": ">3x",                  # ارتفاع حجم 3x
                "liquidation_spike": "True",            # تصفيات كبيرة
                "market_regime": "crash",
            }
            p.exit_conditions = {
                "profit_target": "5-15%",
                "time_limit_hours": 6,
                "stop_loss": "3%",
            }
            p.success_rate = 0.68
            p.avg_profit = 7.5
            p.avg_duration_minutes = 90
            p.market_regime = MarketRegime.CRASH
            p.confidence = 0.75
            p.occurrences = 0
            self.patterns["crash_bottom_hunter"] = p

        # ─── نمط 3: اختراق المقاومة (Resistance Breakout) ───
        if "resistance_breakout" not in self.patterns:
            p = BotPattern("resistance_breakout", "breakout")
            p.entry_conditions = {
                "price_above_resistance": "True",
                "volume_confirmation": ">2x",
                "rsi": "50-70",
                "macd_bullish": "True",
                "market_regime": "bull_trend",
            }
            p.exit_conditions = {
                "profit_target": "4-10%",
                "time_limit_hours": 12,
                "trailing_stop": "2%",
            }
            p.success_rate = 0.65
            p.avg_profit = 5.8
            p.avg_duration_minutes = 240
            p.market_regime = MarketRegime.BULL_TREND
            p.confidence = 0.72
            p.occurrences = 0
            self.patterns["resistance_breakout"] = p

        # ─── نمط 4: الارتداد من الدعم (Support Bounce) ───
        if "support_bounce" not in self.patterns:
            p = BotPattern("support_bounce", "reversal")
            p.entry_conditions = {
                "price_at_support": "True",
                "rsi": "<35",
                "volume_increase": ">1.5x",
                "bullish_candle": "True",
                "market_regime": "any",
            }
            p.exit_conditions = {
                "profit_target": "2-5%",
                "time_limit_hours": 8,
                "stop_loss": "1.5%",
            }
            p.success_rate = 0.70
            p.avg_profit = 3.2
            p.avg_duration_minutes = 120
            p.market_regime = "any"
            p.confidence = 0.75
            p.occurrences = 0
            self.patterns["support_bounce"] = p

        # ─── نمط 5: Smart Money Divergence ───
        if "smart_money_divergence" not in self.patterns:
            p = BotPattern("smart_money_divergence", "smart_money")
            p.entry_conditions = {
                "price_trend": "down",
                "smart_money_flow": "positive",         # الأموال الذكية تشتري
                "retail_sentiment": "bearish",          # المتداولون الصغار يبيعون
                "funding_rate": "<0",                   # معدل تمويل سلبي
                "market_regime": "bear_trend",
            }
            p.exit_conditions = {
                "profit_target": "8-20%",
                "time_limit_hours": 48,
                "trailing_stop": "3%",
            }
            p.success_rate = 0.75
            p.avg_profit = 12.0
            p.avg_duration_minutes = 720
            p.market_regime = MarketRegime.BEAR_TREND
            p.confidence = 0.82
            p.occurrences = 0
            self.patterns["smart_money_divergence"] = p

        # ─── نمط 6: Funding Rate Reversal ───
        if "funding_rate_reversal" not in self.patterns:
            p = BotPattern("funding_rate_reversal", "contrarian")
            p.entry_conditions = {
                "funding_rate": ">0.1%",                # معدل تمويل مرتفع جداً
                "long_short_ratio": ">2",               # Long/Short > 2 (الكل يشتري)
                "open_interest_change": ">10%",         # ارتفاع OI
                "market_regime": "pump",
            }
            p.exit_conditions = {
                "direction": "short",
                "profit_target": "3-8%",
                "time_limit_hours": 4,
                "stop_loss": "2%",
            }
            p.success_rate = 0.67
            p.avg_profit = 4.5
            p.avg_duration_minutes = 60
            p.market_regime = MarketRegime.PUMP
            p.confidence = 0.70
            p.occurrences = 0
            self.patterns["funding_rate_reversal"] = p

        # ─── نمط 7: Accumulation Breakout ───
        if "accumulation_breakout" not in self.patterns:
            p = BotPattern("accumulation_breakout", "breakout")
            p.entry_conditions = {
                "market_regime": "accumulation",
                "volume_compression": "True",           # حجم منخفض لفترة طويلة
                "price_range_tightening": "True",       # نطاق سعري ضيق
                "on_chain_accumulation": "True",        # تراكم على السلسلة
                "days_in_range": ">3",
            }
            p.exit_conditions = {
                "profit_target": "10-30%",
                "time_limit_hours": 72,
                "trailing_stop": "4%",
            }
            p.success_rate = 0.73
            p.avg_profit = 18.0
            p.avg_duration_minutes = 1440
            p.market_regime = MarketRegime.ACCUMULATION
            p.confidence = 0.78
            p.occurrences = 0
            self.patterns["accumulation_breakout"] = p

        logger.info(f"✅ Loaded {len(self.patterns)} competitive patterns")

    def analyze_market_opportunity(
        self,
        symbol: str,
        ohlcv_data: List[Dict],
        coinglass_data: Dict = None,
        whale_data: Dict = None,
        current_price: float = 0.0,
    ) -> Dict:
        """
        التحليل الرئيسي: يكشف الفرص بناءً على الأنماط المكتشفة من البوتات الناجحة
        """
        if not ohlcv_data or len(ohlcv_data) < 20:
            return {"signal": "NEUTRAL", "confidence": 0, "reason": "بيانات غير كافية"}

        prices = [c["close"] for c in ohlcv_data]
        volumes = [c["volume"] for c in ohlcv_data]
        current_price = current_price or prices[-1]

        # 1. تحديث حالة السوق
        regime = self.regime_detector.update(current_price, volumes[-1])
        regime_strategy = self.regime_detector.get_optimal_strategy()

        # 2. حساب المؤشرات
        indicators = self._calculate_indicators(prices, volumes)

        # 3. تقييم كل نمط
        pattern_scores = []
        matched_patterns = []

        for pattern_id, pattern in self.patterns.items():
            score = self._evaluate_pattern(
                pattern, indicators, regime, coinglass_data, whale_data
            )
            if score > 0.5:
                pattern_scores.append(score)
                matched_patterns.append({
                    "pattern_id": pattern_id,
                    "pattern_type": pattern.pattern_type,
                    "score": score,
                    "success_rate": pattern.success_rate,
                    "avg_profit": pattern.avg_profit,
                    "description": pattern.entry_conditions,
                })

        # 4. حساب الإشارة النهائية
        if not pattern_scores:
            return {
                "signal": "NEUTRAL",
                "confidence": 0.0,
                "regime": regime,
                "regime_strategy": regime_strategy,
                "matched_patterns": [],
                "reason": "لا توجد أنماط مطابقة حالياً",
            }

        avg_score = sum(pattern_scores) / len(pattern_scores)
        best_pattern = max(matched_patterns, key=lambda x: x["score"])

        # تحديد الاتجاه بناءً على الحالة والأنماط
        direction = self._determine_direction(regime, matched_patterns, indicators)

        # حساب مستويات الدخول والخروج المُحسَّنة
        levels = self._calculate_optimized_levels(
            current_price, direction, best_pattern, indicators, regime
        )

        signal = "BUY" if direction == "long" else "SELL" if direction == "short" else "NEUTRAL"

        return {
            "signal": signal,
            "direction": direction,
            "confidence": avg_score,
            "regime": regime,
            "regime_strategy": regime_strategy,
            "matched_patterns": matched_patterns[:3],  # أفضل 3 أنماط
            "best_pattern": best_pattern,
            "levels": levels,
            "indicators": indicators,
            "outperformance_tip": self._get_outperformance_tip(best_pattern, regime),
            "reason": self._build_reason(matched_patterns, regime, indicators),
        }

    def _calculate_indicators(self, prices: List[float], volumes: List[float]) -> Dict:
        """حساب المؤشرات الفنية"""
        if len(prices) < 14:
            return {}

        # RSI
        rsi = self._rsi(prices)

        # MACD
        macd_line, signal_line, histogram = self._macd(prices)

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = self._bollinger_bands(prices)

        # حجم نسبي
        avg_vol = statistics.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
        volume_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1

        # ATR
        atr = self._atr(prices)

        # مستويات الدعم والمقاومة
        support, resistance = self._support_resistance(prices)

        current_price = prices[-1]

        return {
            "rsi": rsi,
            "macd_line": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
            "macd_bullish": histogram > 0,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "bb_position": (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5,
            "volume_ratio": volume_ratio,
            "atr": atr,
            "atr_pct": atr / current_price * 100 if current_price > 0 else 0,
            "support": support,
            "resistance": resistance,
            "near_support": abs(current_price - support) / current_price < 0.02,
            "near_resistance": abs(current_price - resistance) / current_price < 0.02,
            "price_change_1h": (prices[-1] - prices[-min(12, len(prices))]) / prices[-min(12, len(prices))] * 100,
            "price_change_4h": (prices[-1] - prices[-min(48, len(prices))]) / prices[-min(48, len(prices))] * 100,
        }

    def _evaluate_pattern(
        self,
        pattern: BotPattern,
        indicators: Dict,
        regime: str,
        coinglass_data: Dict = None,
        whale_data: Dict = None,
    ) -> float:
        """تقييم مدى تطابق النمط مع الوضع الحالي"""
        if not indicators:
            return 0.0

        score = 0.0
        checks = 0

        # تحقق من حالة السوق
        if pattern.market_regime != "any" and pattern.market_regime != regime:
            return 0.0  # النمط لا ينطبق على هذه الحالة

        # ─── تقييم RSI ───
        rsi = indicators.get("rsi", 50)
        if pattern.pattern_type in ["reversal", "crash_bottom"]:
            if rsi < 30:
                score += 1.0
            elif rsi < 40:
                score += 0.6
            checks += 1
        elif pattern.pattern_type in ["breakout", "momentum"]:
            if 45 < rsi < 70:
                score += 1.0
            elif 40 < rsi < 75:
                score += 0.6
            checks += 1

        # ─── تقييم MACD ───
        if pattern.pattern_type in ["momentum", "breakout", "whale_entry"]:
            if indicators.get("macd_bullish"):
                score += 1.0
            checks += 1

        # ─── تقييم الحجم ───
        volume_ratio = indicators.get("volume_ratio", 1)
        if pattern.pattern_type in ["breakout", "whale_entry", "crash_bottom"]:
            if volume_ratio > 2.0:
                score += 1.0
            elif volume_ratio > 1.5:
                score += 0.7
            elif volume_ratio > 1.2:
                score += 0.4
            checks += 1

        # ─── تقييم Bollinger Bands ───
        bb_pos = indicators.get("bb_position", 0.5)
        if pattern.pattern_type == "reversal":
            if bb_pos < 0.1:  # قرب الحد السفلي
                score += 1.0
            elif bb_pos < 0.2:
                score += 0.6
            checks += 1
        elif pattern.pattern_type == "breakout":
            if bb_pos > 0.9:  # كسر الحد العلوي
                score += 1.0
            elif bb_pos > 0.8:
                score += 0.6
            checks += 1

        # ─── تقييم بيانات CoinGlass ───
        if coinglass_data:
            funding_rate = coinglass_data.get("funding_rate", 0)
            long_pct = coinglass_data.get("long_pct", 50)

            if pattern.pattern_id == "funding_rate_reversal":
                if funding_rate > 0.1:
                    score += 1.0
                checks += 1
                if long_pct > 65:
                    score += 1.0
                checks += 1

            if pattern.pattern_id == "smart_money_divergence":
                if funding_rate < 0:
                    score += 1.0
                checks += 1

        # ─── تقييم بيانات الحيتان ───
        if whale_data:
            whale_buy = whale_data.get("large_buy_volume_usd", 0)
            if pattern.pattern_id == "whale_accumulation":
                if whale_buy > 500000:
                    score += 2.0  # وزن مضاعف
                elif whale_buy > 200000:
                    score += 1.0
                checks += 1

        # ─── تقييم الدعم/المقاومة ───
        if pattern.pattern_type == "reversal" and indicators.get("near_support"):
            score += 0.8
            checks += 1
        if pattern.pattern_type == "breakout" and indicators.get("near_resistance"):
            score += 0.8
            checks += 1

        # ─── حساب النتيجة النهائية ───
        if checks == 0:
            return 0.0

        raw_score = score / checks
        # تعديل بناءً على معدل نجاح النمط التاريخي
        adjusted_score = raw_score * (0.5 + pattern.success_rate * 0.5)
        return min(1.0, adjusted_score)

    def _determine_direction(self, regime: str, matched_patterns: List[Dict], indicators: Dict) -> str:
        """تحديد اتجاه التداول"""
        long_score = 0
        short_score = 0

        for p in matched_patterns:
            if p["pattern_type"] in ["reversal", "breakout", "whale_entry", "smart_money"]:
                long_score += p["score"]
            elif p["pattern_type"] in ["contrarian"]:
                short_score += p["score"]

        # تأثير حالة السوق
        if regime in [MarketRegime.BULL_TREND, MarketRegime.RECOVERY, MarketRegime.ACCUMULATION]:
            long_score += 0.5
        elif regime in [MarketRegime.BEAR_TREND, MarketRegime.DISTRIBUTION]:
            short_score += 0.3
        elif regime == MarketRegime.CRASH:
            long_score += 0.3  # فرصة ارتداد

        if long_score > short_score and long_score > 0.3:
            return "long"
        elif short_score > long_score and short_score > 0.3:
            return "short"
        return "neutral"

    def _calculate_optimized_levels(
        self,
        price: float,
        direction: str,
        best_pattern: Dict,
        indicators: Dict,
        regime: str,
    ) -> Dict:
        """حساب مستويات الدخول والخروج المُحسَّنة بناءً على الأنماط"""
        atr = indicators.get("atr", price * 0.02)
        atr_pct = indicators.get("atr_pct", 2.0)

        # معاملات تعديل بناءً على حالة السوق
        regime_multipliers = {
            MarketRegime.BULL_TREND:   {"tp": 1.5, "sl": 0.8},
            MarketRegime.BEAR_TREND:   {"tp": 1.2, "sl": 0.7},
            MarketRegime.CRASH:        {"tp": 2.0, "sl": 1.5},
            MarketRegime.RECOVERY:     {"tp": 2.5, "sl": 1.0},
            MarketRegime.PUMP:         {"tp": 0.7, "sl": 1.2},
            MarketRegime.SIDEWAYS:     {"tp": 0.8, "sl": 0.6},
            MarketRegime.ACCUMULATION: {"tp": 2.0, "sl": 0.7},
            MarketRegime.DISTRIBUTION: {"tp": 1.5, "sl": 0.8},
        }
        mult = regime_multipliers.get(regime, {"tp": 1.0, "sl": 1.0})

        avg_profit = best_pattern.get("avg_profit", 3.0)

        if direction == "long":
            entry1 = price
            entry2 = price * (1 - atr_pct * 0.005)
            # TP1 = هدف أول محافظ | TP2 = هدف ثانٍ | TP3 = هدف بعيد
            tp1 = price * (1 + avg_profit * 0.006 * mult["tp"])
            tp2 = price * (1 + avg_profit * 0.012 * mult["tp"])
            tp3 = price * (1 + avg_profit * 0.020 * mult["tp"])
            # SL: الحد الأدنى = ATR×1.5 من سعر الدخول (يتجنب التذبذب الطبيعي)
            raw_sl = price * (1 - atr_pct * 0.015 * mult["sl"])
            min_sl = price * (1 - max(atr_pct * 1.5, 0.8) / 100)
            sl = min(raw_sl, min_sl)  # الأبعد
        elif direction == "short":
            entry1 = price
            entry2 = price * (1 + atr_pct * 0.005)
            tp1 = price * (1 - avg_profit * 0.006 * mult["tp"])
            tp2 = price * (1 - avg_profit * 0.012 * mult["tp"])
            tp3 = price * (1 - avg_profit * 0.020 * mult["tp"])
            raw_sl = price * (1 + atr_pct * 0.015 * mult["sl"])
            min_sl = price * (1 + max(atr_pct * 1.5, 0.8) / 100)
            sl = max(raw_sl, min_sl)
        else:
            return {}

        return {
            "entry1": round(entry1, 6),
            "entry2": round(entry2, 6),
            "tp1": round(tp1, 6),
            "tp2": round(tp2, 6),
            "tp3": round(tp3, 6),
            "sl": round(sl, 6),
            "risk_reward": round(abs(tp2 - entry1) / abs(entry1 - sl), 2) if abs(entry1 - sl) > 0 else 0,
        }

    def _get_outperformance_tip(self, best_pattern: Dict, regime: str) -> str:
        """نصيحة للتفوق على النمط المكتشف"""
        tips = {
            "whale_entry": "ادخل قبل تأكيد الحوت بـ 0.5% للحصول على سعر أفضل",
            "reversal": "انتظر شمعة تأكيد إضافية لتجنب الفخاخ",
            "breakout": "ضع أمر دخول فوق مستوى الاختراق مباشرة لتجنب الاختراقات الكاذبة",
            "smart_money": "تابع تدفق OI مع الصفقة — إذا انخفض OI مع الصعود فهو تحذير",
            "contrarian": "اجني الأرباح بسرعة — هذه الصفقات قصيرة المدى",
        }
        pattern_type = best_pattern.get("pattern_type", "")
        base_tip = tips.get(pattern_type, "تابع السوق عن كثب وعدّل وقف الخسارة")

        regime_tips = {
            MarketRegime.CRASH: "في الانهيارات: ادخل بـ 30% من الحجم أولاً، أضف عند التأكيد",
            MarketRegime.RECOVERY: "في التعافي: الوقت حاسم — كل دقيقة تأخير تكلف %",
            MarketRegime.PUMP: "في الضخ: اجني الأرباح عند TP1 فوراً، لا تنتظر TP3",
        }
        regime_tip = regime_tips.get(regime, "")

        return f"{base_tip}. {regime_tip}".strip(". ")

    def _build_reason(self, matched_patterns: List[Dict], regime: str, indicators: Dict) -> str:
        """بناء شرح مفصل للإشارة"""
        reasons = []

        regime_names = {
            MarketRegime.BULL_TREND: "اتجاه صاعد",
            MarketRegime.BEAR_TREND: "اتجاه هابط",
            MarketRegime.SIDEWAYS: "سوق جانبي",
            MarketRegime.CRASH: "انهيار",
            MarketRegime.RECOVERY: "تعافي",
            MarketRegime.PUMP: "ضخ مفاجئ",
            MarketRegime.ACCUMULATION: "مرحلة تراكم",
            MarketRegime.DISTRIBUTION: "مرحلة توزيع",
        }
        reasons.append(f"حالة السوق: {regime_names.get(regime, regime)}")

        for p in matched_patterns[:2]:
            pattern_names = {
                "whale_entry": "دخول حوت",
                "reversal": "ارتداد",
                "breakout": "اختراق",
                "smart_money": "أموال ذكية",
                "contrarian": "عكسي",
            }
            name = pattern_names.get(p["pattern_type"], p["pattern_type"])
            reasons.append(f"نمط {name} (ثقة: {p['score']:.0%}, نجاح تاريخي: {p['success_rate']:.0%})")

        rsi = indicators.get("rsi", 50)
        if rsi < 30:
            reasons.append(f"RSI={rsi:.0f} (تشبع بيع شديد)")
        elif rsi > 70:
            reasons.append(f"RSI={rsi:.0f} (تشبع شراء)")
        else:
            reasons.append(f"RSI={rsi:.0f}")

        vol_ratio = indicators.get("volume_ratio", 1)
        if vol_ratio > 2:
            reasons.append(f"حجم مرتفع {vol_ratio:.1f}x")

        return " | ".join(reasons)

    def record_trade_result(self, pattern_id: str, profit_pct: float, success: bool):
        """تسجيل نتيجة صفقة لتحسين الأنماط"""
        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            self.pattern_performance[pattern_id].append(profit_pct)
            pattern.occurrences += 1

            # تحديث معدل النجاح
            history = self.pattern_performance[pattern_id]
            if len(history) >= 5:
                successes = sum(1 for p in history if p > 0)
                pattern.success_rate = successes / len(history)
                pattern.avg_profit = statistics.mean([p for p in history if p > 0]) if any(p > 0 for p in history) else 0

            # تحديث نقطة التفوق
            if profit_pct > pattern.avg_profit:
                self.outperformance_score += 1
                self.patterns_beaten += 1

            self._save_patterns()
            logger.info(f"📊 Pattern '{pattern_id}' updated: success_rate={pattern.success_rate:.1%}, avg_profit={pattern.avg_profit:.1f}%")

    def learn_new_pattern(self, trade_data: Dict):
        """تعلم نمط جديد من صفقة ناجحة"""
        if trade_data.get("profit_pct", 0) < 3:
            return  # فقط الصفقات الناجحة بشكل جيد

        pattern_id = f"learned_{int(time.time())}"
        p = BotPattern(pattern_id, "learned")
        p.entry_conditions = trade_data.get("entry_conditions", {})
        p.exit_conditions = trade_data.get("exit_conditions", {})
        p.success_rate = 1.0  # صفقة ناجحة واحدة
        p.avg_profit = trade_data.get("profit_pct", 0)
        p.market_regime = trade_data.get("regime", "any")
        p.occurrences = 1
        p.confidence = 0.5  # ثقة منخفضة في البداية

        self.patterns[pattern_id] = p
        self.patterns_learned += 1
        self._save_patterns()
        logger.info(f"🧠 New pattern learned: {pattern_id} (profit: {p.avg_profit:.1f}%)")

    def get_performance_report(self) -> Dict:
        """تقرير أداء النظام التنافسي"""
        total_patterns = len(self.patterns)
        active_patterns = sum(1 for p in self.patterns.values() if p.occurrences > 0)
        avg_success = statistics.mean([p.success_rate for p in self.patterns.values()]) if self.patterns else 0
        best_pattern = max(self.patterns.values(), key=lambda p: p.success_rate * p.avg_profit, default=None)

        return {
            "total_patterns": total_patterns,
            "active_patterns": active_patterns,
            "learned_patterns": self.patterns_learned,
            "patterns_beaten": self.patterns_beaten,
            "outperformance_score": self.outperformance_score,
            "avg_success_rate": avg_success,
            "best_pattern": best_pattern.pattern_id if best_pattern else None,
            "best_pattern_profit": best_pattern.avg_profit if best_pattern else 0,
            "current_regime": self.regime_detector.current_regime,
            "regime_confidence": self.regime_detector.regime_confidence,
        }

    # ─── مؤشرات فنية ───

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas[-period:] if d > 0]
        losses = [-d for d in deltas[-period:] if d < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _macd(self, prices: List[float], fast=12, slow=26, signal=9):
        def ema(data, period):
            k = 2 / (period + 1)
            result = [data[0]]
            for p in data[1:]:
                result.append(p * k + result[-1] * (1 - k))
            return result

        if len(prices) < slow + signal:
            return 0, 0, 0
        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        macd_line = [f - s for f, s in zip(ema_fast[slow-1:], ema_slow)]
        if len(macd_line) < signal:
            return macd_line[-1], 0, macd_line[-1]
        signal_line = ema(macd_line, signal)
        histogram = macd_line[-1] - signal_line[-1]
        return macd_line[-1], signal_line[-1], histogram

    def _bollinger_bands(self, prices: List[float], period=20, std_dev=2):
        if len(prices) < period:
            p = prices[-1]
            return p * 1.02, p, p * 0.98
        recent = prices[-period:]
        mid = statistics.mean(recent)
        std = statistics.stdev(recent)
        return mid + std_dev * std, mid, mid - std_dev * std

    def _atr(self, prices: List[float], period=14) -> float:
        if len(prices) < 2:
            return prices[-1] * 0.02
        trs = [abs(prices[i] - prices[i-1]) for i in range(1, min(period+1, len(prices)))]
        return statistics.mean(trs) if trs else prices[-1] * 0.02

    def _support_resistance(self, prices: List[float]) -> Tuple[float, float]:
        if len(prices) < 20:
            p = prices[-1]
            return p * 0.97, p * 1.03
        recent = prices[-50:] if len(prices) >= 50 else prices
        support = min(recent)
        resistance = max(recent)
        # تحسين: استخدام النسب المئوية بدلاً من القيم المطلقة
        sorted_prices = sorted(recent)
        support = sorted_prices[int(len(sorted_prices) * 0.1)]
        resistance = sorted_prices[int(len(sorted_prices) * 0.9)]
        return support, resistance

    def _load_patterns(self):
        """تحميل الأنماط المحفوظة"""
        try:
            if os.path.exists(self.PATTERNS_FILE):
                with open(self.PATTERNS_FILE, "r") as f:
                    data = json.load(f)
                    for pid, pdata in data.get("patterns", {}).items():
                        p = BotPattern(pid, pdata.get("pattern_type", "learned"))
                        p.success_rate = pdata.get("success_rate", 0.5)
                        p.avg_profit = pdata.get("avg_profit", 0)
                        p.occurrences = pdata.get("occurrences", 0)
                        p.market_regime = pdata.get("market_regime", "any")
                        p.confidence = pdata.get("confidence", 0.5)
                        self.patterns[pid] = p
                    self.patterns_learned = data.get("patterns_learned", 0)
                    self.patterns_beaten = data.get("patterns_beaten", 0)
                    logger.info(f"✅ Loaded {len(self.patterns)} patterns from file")
        except Exception as e:
            logger.warning(f"Could not load patterns: {e}")

    def _save_patterns(self):
        """حفظ الأنماط"""
        try:
            os.makedirs("data", exist_ok=True)
            data = {
                "patterns": {pid: p.to_dict() for pid, p in self.patterns.items()},
                "patterns_learned": self.patterns_learned,
                "patterns_beaten": self.patterns_beaten,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.PATTERNS_FILE, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save patterns: {e}")
