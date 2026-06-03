"""
Portfolio Optimizer — المستوى 4
يوزع رأس المال بذكاء بين الصفقات المتزامنة بناءً على:
- قوة الإشارة (النقاط والثقة)
- تاريخ أداء كل عملة
- تنويع المخاطر (لا تركيز في عملة واحدة)
- حالة السوق الحالية

يستبدل التوزيع الثابت ($170 لكل صفقة) بتوزيع ديناميكي ذكي.
"""

import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ثوابت
MIN_TRADE_SIZE = 100.0       # الحد الأدنى لأي صفقة
MAX_TRADE_SIZE = 170.0       # الحد الأقصى لأي صفقة
MAX_SINGLE_EXPOSURE = 0.35   # أقصى تركيز في عملة واحدة (35% من الرصيد)
MIN_CONFIDENCE = 0.60        # الحد الأدنى للثقة للتخصيص


@dataclass
class TradeCandidate:
    """مرشح صفقة مع بياناته."""
    symbol: str
    score: float              # نقاط الإشارة (0-10)
    confidence: float         # الثقة (0-1)
    regime: str               # حالة السوق
    arb_boost: float = 0.0    # تعزيز Arbitrage
    win_rate: float = 0.5     # معدل الفوز التاريخي لهذه العملة
    avg_profit: float = 0.03  # متوسط الربح التاريخي


@dataclass
class AllocationResult:
    """نتيجة التخصيص لصفقة."""
    symbol: str
    allocated_usdt: float
    allocation_pct: float     # نسبة من الرصيد المتاح
    priority_rank: int        # الترتيب (1 = الأعلى أولوية)
    reason: str


class PortfolioOptimizer:
    """
    يوزع رأس المال بين الصفقات المتزامنة بذكاء.
    """

    def __init__(self, history_file: str = "data/trade_history.json"):
        self.history_file = history_file
        self._performance: Dict[str, dict] = {}  # {symbol: {wins, losses, total_profit}}
        self._load_history()
        logger.info("[PortfolioOpt] ✅ Portfolio Optimizer initialized")

    # ─── تحميل التاريخ ────────────────────────────────────────────────────────

    def _load_history(self):
        """تحميل تاريخ الأداء من الملف."""
        try:
            path = os.path.join(os.path.dirname(__file__), self.history_file)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                # بناء إحصائيات الأداء لكل عملة
                for trade in data.get("trades", []):
                    sym = trade.get("symbol", "")
                    if not sym:
                        continue
                    if sym not in self._performance:
                        self._performance[sym] = {"wins": 0, "losses": 0, "total_profit": 0.0}
                    pnl = trade.get("pnl_pct", 0)
                    if pnl > 0:
                        self._performance[sym]["wins"] += 1
                        self._performance[sym]["total_profit"] += pnl
                    else:
                        self._performance[sym]["losses"] += 1
        except Exception as e:
            logger.debug(f"[PortfolioOpt] لا يوجد تاريخ سابق: {e}")

    # ─── حساب معدل الفوز ─────────────────────────────────────────────────────

    def _get_symbol_stats(self, symbol: str) -> Tuple[float, float]:
        """
        يُرجع (win_rate, avg_profit) لعملة معينة.
        القيم الافتراضية: 50% win rate, 3% avg profit
        """
        perf = self._performance.get(symbol)
        if not perf:
            return 0.50, 0.030

        total = perf["wins"] + perf["losses"]
        if total < 3:  # بيانات غير كافية
            return 0.50, 0.030

        win_rate = perf["wins"] / total
        avg_profit = perf["total_profit"] / max(perf["wins"], 1) / 100
        return win_rate, avg_profit

    # ─── حساب الأولوية ───────────────────────────────────────────────────────

    def _calculate_priority_score(self, candidate: TradeCandidate) -> float:
        """
        يحسب درجة الأولوية الشاملة للصفقة.
        يجمع: قوة الإشارة + الثقة + الأداء التاريخي + Arbitrage
        """
        win_rate, avg_profit = self._get_symbol_stats(candidate.symbol)
        candidate.win_rate = win_rate
        candidate.avg_profit = avg_profit

        # Kelly Criterion مبسط: f = (p*b - q) / b
        # حيث p = win_rate, q = 1-p, b = avg_profit/avg_loss
        b = avg_profit / 0.02  # نفترض avg_loss = 2%
        kelly = (win_rate * b - (1 - win_rate)) / b
        kelly = max(0.1, min(kelly, 0.5))  # تقييد بين 10% و50%

        # الدرجة الشاملة
        priority = (
            candidate.score * 0.35 +           # 35% قوة الإشارة
            candidate.confidence * 10 * 0.30 + # 30% الثقة
            win_rate * 10 * 0.20 +             # 20% الأداء التاريخي
            kelly * 10 * 0.10 +                # 10% Kelly Criterion
            candidate.arb_boost * 0.05         # 5% تعزيز Arbitrage
        )

        return priority

    # ─── التخصيص الرئيسي ─────────────────────────────────────────────────────

    def allocate(
        self,
        candidates: List[TradeCandidate],
        available_capital: float,
        current_open_trades: int = 0
    ) -> List[AllocationResult]:
        """
        يوزع رأس المال بين المرشحين بذكاء.

        Args:
            candidates: قائمة الصفقات المرشحة
            available_capital: الرصيد المتاح
            current_open_trades: عدد الصفقات المفتوحة حالياً

        Returns:
            قائمة التخصيصات مرتبة حسب الأولوية
        """
        if not candidates or available_capital < MIN_TRADE_SIZE:
            return []

        # فلترة المرشحين بالحد الأدنى للثقة
        valid = [c for c in candidates if c.confidence >= MIN_CONFIDENCE]
        if not valid:
            return []

        # حساب الأولوية لكل مرشح
        scored = [(c, self._calculate_priority_score(c)) for c in valid]
        scored.sort(key=lambda x: x[1], reverse=True)

        # تحديد عدد الصفقات الممكنة
        max_new_trades = max(1, int(available_capital / MIN_TRADE_SIZE))
        max_new_trades = min(max_new_trades, len(scored))

        results = []
        remaining_capital = available_capital

        for rank, (candidate, priority) in enumerate(scored[:max_new_trades], 1):
            if remaining_capital < MIN_TRADE_SIZE:
                break

            # حساب الحجم الأمثل
            # الصفقة الأولى (الأعلى أولوية) تحصل على الحد الأقصى
            # الصفقات التالية تحصل على أقل تدريجياً
            if rank == 1:
                size_factor = 1.0
            elif rank == 2:
                size_factor = 0.85
            else:
                size_factor = 0.70

            # تعديل بناءً على حالة السوق
            regime_multiplier = {
                "recovery": 1.2,
                "bull_trend": 0.75,
                "sideways": 0.70,
                "bear_trend": 0.60,
                "crash": 0.50,
                "pump": 0.80,
            }.get(candidate.regime, 1.0)

            # الحجم المقترح
            base_size = MAX_TRADE_SIZE * size_factor * regime_multiplier
            allocated = max(MIN_TRADE_SIZE, min(base_size, remaining_capital, MAX_TRADE_SIZE))

            # فحص الحد الأقصى للتركيز في عملة واحدة
            max_allowed = available_capital * MAX_SINGLE_EXPOSURE
            allocated = min(allocated, max_allowed)
            allocated = round(allocated, 2)

            if allocated < MIN_TRADE_SIZE:
                continue

            allocation_pct = (allocated / available_capital) * 100
            reason = (
                f"أولوية #{rank} | نقاط={candidate.score:.1f} | "
                f"ثقة={candidate.confidence:.0%} | "
                f"WR={candidate.win_rate:.0%} | "
                f"Regime={candidate.regime}"
            )

            results.append(AllocationResult(
                symbol=candidate.symbol,
                allocated_usdt=allocated,
                allocation_pct=allocation_pct,
                priority_rank=rank,
                reason=reason
            ))

            remaining_capital -= allocated

        logger.info(
            f"[PortfolioOpt] خصصت {len(results)} صفقة من {len(candidates)} مرشح "
            f"| رأس المال: ${available_capital:.0f} "
            f"| متبقي: ${remaining_capital:.0f}"
        )

        return results

    # ─── تحديث التاريخ ───────────────────────────────────────────────────────

    def record_trade_result(self, symbol: str, pnl_pct: float):
        """تسجيل نتيجة صفقة لتحسين التخصيص المستقبلي."""
        if symbol not in self._performance:
            self._performance[symbol] = {"wins": 0, "losses": 0, "total_profit": 0.0}

        if pnl_pct > 0:
            self._performance[symbol]["wins"] += 1
            self._performance[symbol]["total_profit"] += pnl_pct
        else:
            self._performance[symbol]["losses"] += 1

        logger.debug(f"[PortfolioOpt] سُجِّلت نتيجة {symbol}: {pnl_pct:+.2f}%")

    def get_performance_summary(self) -> dict:
        """ملخص أداء كل عملة."""
        summary = {}
        for sym, perf in self._performance.items():
            total = perf["wins"] + perf["losses"]
            if total > 0:
                summary[sym] = {
                    "win_rate": f"{perf['wins']/total:.0%}",
                    "total_trades": total,
                    "avg_profit": f"{perf['total_profit']/max(perf['wins'],1):.2f}%"
                }
        return summary


# ─── Singleton ────────────────────────────────────────────────────────────────

_portfolio_optimizer: Optional[PortfolioOptimizer] = None


def get_portfolio_optimizer() -> PortfolioOptimizer:
    global _portfolio_optimizer
    if _portfolio_optimizer is None:
        _portfolio_optimizer = PortfolioOptimizer()
    return _portfolio_optimizer
