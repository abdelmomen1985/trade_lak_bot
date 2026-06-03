"""
Adaptive Learning & Outperformance Engine
==========================================
يتعلم من كل صفقة ويتفوق على البوتات الأخرى في جميع حالات السوق.

الميزات:
- تعلم تكيفي: يحسّن استراتيجياته بعد كل صفقة
- ذاكرة السوق: يتذكر ما نجح في كل حالة سوق
- محرك التفوق: يضيف تحسينات فوق الأنماط المكتشفة
- مراقبة الأداء: يقارن أداءه مع معايير السوق
"""

import logging
import json
import os
import time
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class AdaptiveLearningEngine:
    """
    محرك التعلم التكيفي — يتعلم ويتحسن باستمرار
    """

    MEMORY_FILE = "data/adaptive_memory.json"

    def __init__(self):
        # ذاكرة الأداء لكل حالة سوق
        self.regime_performance: Dict[str, List[Dict]] = defaultdict(list)

        # أفضل الاستراتيجيات لكل حالة سوق
        self.best_strategies: Dict[str, Dict] = {}

        # سجل التعلم
        self.learning_log: deque = deque(maxlen=500)

        # معاملات التكيف
        self.adaptation_weights: Dict[str, float] = {
            "momentum":      1.0,
            "mean_reversion": 1.0,
            "breakout":      1.0,
            "volume_profile": 1.0,
            "whale_entry":   1.0,
            "reversal":      1.0,
            "smart_money":   1.0,
        }

        # إحصائيات التفوق
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0.0
        self.benchmark_profit = 0.0  # أداء السوق كمرجع

        # تحميل الذاكرة
        self._load_memory()
        logger.info("✅ Adaptive Learning Engine initialized")

    def record_trade(self, trade_data: Dict):
        """تسجيل نتيجة صفقة وتحديث الذاكرة"""
        regime = trade_data.get("regime", "unknown")
        strategy = trade_data.get("strategy", "unknown")
        profit_pct = trade_data.get("profit_pct", 0)
        success = profit_pct > 0
        duration = trade_data.get("duration_minutes", 0)

        # تحديث الإحصائيات
        self.total_trades += 1
        if success:
            self.winning_trades += 1
        self.total_profit += profit_pct

        # تسجيل في ذاكرة حالة السوق
        self.regime_performance[regime].append({
            "strategy": strategy,
            "profit_pct": profit_pct,
            "success": success,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
        })

        # تحديث أوزان الاستراتيجيات
        self._update_strategy_weights(strategy, profit_pct, success)

        # تحديث أفضل الاستراتيجيات لهذه الحالة
        self._update_best_strategy(regime, strategy, profit_pct)

        # تسجيل في سجل التعلم
        self.learning_log.append({
            "regime": regime,
            "strategy": strategy,
            "profit_pct": profit_pct,
            "success": success,
            "lesson": self._extract_lesson(trade_data),
        })

        self._save_memory()
        logger.info(f"🧠 Trade recorded: {strategy} in {regime} → {profit_pct:+.1f}%")

    def _update_strategy_weights(self, strategy: str, profit_pct: float, success: bool):
        """تحديث أوزان الاستراتيجيات بناءً على الأداء"""
        if strategy not in self.adaptation_weights:
            self.adaptation_weights[strategy] = 1.0

        current_weight = self.adaptation_weights[strategy]
        learning_rate = 0.1

        if success and profit_pct > 3:
            # صفقة ناجحة جيداً — زيادة الوزن
            adjustment = learning_rate * (profit_pct / 10)
            self.adaptation_weights[strategy] = min(2.0, current_weight + adjustment)
        elif not success and profit_pct < -2:
            # صفقة خاسرة — تخفيض الوزن
            adjustment = learning_rate * (abs(profit_pct) / 10)
            self.adaptation_weights[strategy] = max(0.3, current_weight - adjustment)

    def _update_best_strategy(self, regime: str, strategy: str, profit_pct: float):
        """تحديث أفضل استراتيجية لحالة السوق"""
        history = self.regime_performance[regime]
        if len(history) < 3:
            return

        # حساب أداء كل استراتيجية في هذه الحالة
        strategy_profits: Dict[str, List[float]] = defaultdict(list)
        for trade in history[-50:]:  # آخر 50 صفقة
            strategy_profits[trade["strategy"]].append(trade["profit_pct"])

        best_strat = None
        best_avg = -999
        for strat, profits in strategy_profits.items():
            if len(profits) >= 2:
                avg = statistics.mean(profits)
                win_rate = sum(1 for p in profits if p > 0) / len(profits)
                score = avg * win_rate
                if score > best_avg:
                    best_avg = score
                    best_strat = strat

        if best_strat:
            self.best_strategies[regime] = {
                "strategy": best_strat,
                "avg_profit": best_avg,
                "sample_size": len(strategy_profits[best_strat]),
            }

    def _extract_lesson(self, trade_data: Dict) -> str:
        """استخلاص درس من الصفقة"""
        profit = trade_data.get("profit_pct", 0)
        regime = trade_data.get("regime", "")
        strategy = trade_data.get("strategy", "")
        rsi = trade_data.get("rsi", 50)

        if profit > 5:
            return f"نجاح كبير: {strategy} في {regime} مع RSI={rsi:.0f}"
        elif profit > 0:
            return f"نجاح معتدل: {strategy} في {regime}"
        elif profit > -2:
            return f"خسارة صغيرة: {strategy} في {regime} — راجع التوقيت"
        else:
            return f"خسارة كبيرة: {strategy} في {regime} مع RSI={rsi:.0f} — تجنب هذا الإعداد"

    def get_recommended_strategy(self, regime: str, available_strategies: List[str]) -> Dict:
        """الحصول على الاستراتيجية الموصى بها لحالة السوق الحالية"""
        # أولاً: تحقق من الذاكرة
        if regime in self.best_strategies:
            best = self.best_strategies[regime]
            if best["strategy"] in available_strategies and best["sample_size"] >= 5:
                return {
                    "strategy": best["strategy"],
                    "confidence": min(0.9, best["sample_size"] / 20),
                    "expected_profit": best["avg_profit"],
                    "source": "learned",
                    "message": f"تعلمت من {best['sample_size']} صفقة: {best['strategy']} هي الأفضل في {regime}",
                }

        # ثانياً: استخدام الأوزان المكتسبة
        weighted_strategies = []
        for strat in available_strategies:
            weight = self.adaptation_weights.get(strat, 1.0)
            weighted_strategies.append((strat, weight))

        weighted_strategies.sort(key=lambda x: x[1], reverse=True)
        best_strat, best_weight = weighted_strategies[0]

        return {
            "strategy": best_strat,
            "confidence": min(0.7, best_weight / 2),
            "expected_profit": 3.0,
            "source": "weighted",
            "message": f"استراتيجية مُرجَّحة: {best_strat} (وزن: {best_weight:.2f})",
        }

    def get_outperformance_adjustments(self, base_signal: Dict, regime: str) -> Dict:
        """
        تعديلات التفوق — يضيف تحسينات فوق الإشارة الأساسية
        للتفوق على البوتات الأخرى
        """
        adjustments = {}

        # 1. تعديل حجم الصفقة بناءً على الثقة
        confidence = base_signal.get("confidence", 0.5)
        regime_win_rate = self._get_regime_win_rate(regime)

        if confidence > 0.8 and regime_win_rate > 0.7:
            adjustments["position_size_multiplier"] = 1.3  # زيادة الحجم بـ 30%
            adjustments["reason"] = "ثقة عالية + معدل نجاح مرتفع في هذه الحالة"
        elif confidence < 0.5 or regime_win_rate < 0.4:
            adjustments["position_size_multiplier"] = 0.7  # تخفيض الحجم بـ 30%
            adjustments["reason"] = "ثقة منخفضة — حجم محافظ"
        else:
            adjustments["position_size_multiplier"] = 1.0
            adjustments["reason"] = "حجم عادي"

        # 2. تعديل أهداف الربح بناءً على التعلم
        avg_profit_in_regime = self._get_avg_profit_in_regime(regime)
        if avg_profit_in_regime > 0:
            adjustments["tp_adjustment"] = avg_profit_in_regime / 3.0  # نسبة التعديل
        else:
            adjustments["tp_adjustment"] = 1.0

        # 3. تعديل وقف الخسارة
        avg_loss_in_regime = self._get_avg_loss_in_regime(regime)
        if avg_loss_in_regime < -3:
            adjustments["sl_tighter"] = True  # وقف خسارة أضيق
        else:
            adjustments["sl_tighter"] = False

        # 4. توصية التوقيت
        best_hour = self._get_best_trading_hour(regime)
        adjustments["best_hour"] = best_hour

        return adjustments

    def _get_regime_win_rate(self, regime: str) -> float:
        history = self.regime_performance.get(regime, [])
        if len(history) < 5:
            return 0.5
        successes = sum(1 for t in history[-20:] if t["success"])
        return successes / min(20, len(history))

    def _get_avg_profit_in_regime(self, regime: str) -> float:
        history = self.regime_performance.get(regime, [])
        if not history:
            return 3.0
        profits = [t["profit_pct"] for t in history[-20:] if t["profit_pct"] > 0]
        return statistics.mean(profits) if profits else 3.0

    def _get_avg_loss_in_regime(self, regime: str) -> float:
        history = self.regime_performance.get(regime, [])
        if not history:
            return -2.0
        losses = [t["profit_pct"] for t in history[-20:] if t["profit_pct"] < 0]
        return statistics.mean(losses) if losses else -2.0

    def _get_best_trading_hour(self, regime: str) -> Optional[int]:
        """أفضل ساعة للتداول في هذه الحالة"""
        history = self.regime_performance.get(regime, [])
        if len(history) < 10:
            return None

        hour_profits: Dict[int, List[float]] = defaultdict(list)
        for trade in history:
            try:
                ts = datetime.fromisoformat(trade["timestamp"])
                hour_profits[ts.hour].append(trade["profit_pct"])
            except:
                pass

        if not hour_profits:
            return None

        best_hour = max(hour_profits.keys(), key=lambda h: statistics.mean(hour_profits[h]))
        return best_hour

    def get_performance_summary(self) -> Dict:
        """ملخص الأداء الكامل"""
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        avg_profit = self.total_profit / self.total_trades if self.total_trades > 0 else 0

        # أفضل وأسوأ حالة سوق
        regime_summaries = {}
        for regime, history in self.regime_performance.items():
            if history:
                profits = [t["profit_pct"] for t in history]
                regime_summaries[regime] = {
                    "trades": len(history),
                    "win_rate": sum(1 for p in profits if p > 0) / len(profits),
                    "avg_profit": statistics.mean(profits),
                }

        return {
            "total_trades": self.total_trades,
            "win_rate": win_rate,
            "avg_profit_per_trade": avg_profit,
            "total_profit": self.total_profit,
            "regime_performance": regime_summaries,
            "best_strategies": self.best_strategies,
            "strategy_weights": self.adaptation_weights,
            "lessons_learned": len(self.learning_log),
        }

    def _load_memory(self):
        try:
            if os.path.exists(self.MEMORY_FILE):
                with open(self.MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    self.regime_performance = defaultdict(list, data.get("regime_performance", {}))
                    self.best_strategies = data.get("best_strategies", {})
                    self.adaptation_weights = data.get("adaptation_weights", self.adaptation_weights)
                    self.total_trades = data.get("total_trades", 0)
                    self.winning_trades = data.get("winning_trades", 0)
                    self.total_profit = data.get("total_profit", 0.0)
                logger.info(f"✅ Loaded adaptive memory: {self.total_trades} trades")
        except Exception as e:
            logger.warning(f"Could not load memory: {e}")

    def _save_memory(self):
        try:
            os.makedirs("data", exist_ok=True)
            data = {
                "regime_performance": dict(self.regime_performance),
                "best_strategies": self.best_strategies,
                "adaptation_weights": self.adaptation_weights,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "total_profit": self.total_profit,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.MEMORY_FILE, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save memory: {e}")
