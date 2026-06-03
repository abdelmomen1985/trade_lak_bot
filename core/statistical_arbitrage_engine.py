"""
Statistical Arbitrage Engine — المستوى 4
يرصد الفروق السعرية بين OKX وBinance ويستغلها كإشارة تأكيد إضافية.

المنطق:
- إذا كان سعر OKX أعلى من Binance بنسبة > 0.15% → إشارة بيع (السعر مبالغ فيه في OKX)
- إذا كان سعر OKX أقل من Binance بنسبة > 0.15% → إشارة شراء (السعر مخفض في OKX)
- يُستخدم كمؤشر تأكيد إضافي في Intelligence Engine
"""

import time
import logging
import requests
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ثوابت
BINANCE_API = "https://api.binance.com/api/v3"
MIN_SPREAD_PCT = 0.15        # الحد الأدنى للفرق السعري المعتبر (0.15%)
MAX_SPREAD_PCT = 2.0         # الحد الأقصى (فوق هذا = بيانات خاطئة)
CACHE_TTL = 10               # ثواني صلاحية الكاش
SIGNAL_SCORE_BOOST = 0.5     # نقاط إضافية عند تأكيد Arbitrage


class StatisticalArbitrageEngine:
    """
    يقارن أسعار OKX مع Binance ويُنتج إشارات تأكيد.
    لا يُنفذ صفقات Arbitrage مباشرة (يحتاج حسابين) —
    بل يستخدم الفرق السعري كمؤشر ذكاء إضافي.
    """

    def __init__(self):
        self._price_cache: Dict[str, dict] = {}   # {symbol: {price, ts}}
        self._stats: Dict[str, list] = {}          # {symbol: [spread_history]}
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "TradeLak/4.0"})
        logger.info("[StatArb] ✅ Statistical Arbitrage Engine initialized")

    # ─── جلب سعر Binance ─────────────────────────────────────────────────────

    def _get_binance_price(self, symbol: str) -> Optional[float]:
        """جلب السعر الحالي من Binance مع كاش 10 ثواني."""
        now = time.time()
        cached = self._price_cache.get(symbol)
        if cached and (now - cached["ts"]) < CACHE_TTL:
            return cached["price"]

        # تحويل رمز OKX إلى Binance (BTC/USDT → BTCUSDT)
        binance_symbol = symbol.replace("/", "")
        try:
            resp = self._session.get(
                f"{BINANCE_API}/ticker/price",
                params={"symbol": binance_symbol},
                timeout=3
            )
            if resp.status_code == 200:
                price = float(resp.json()["price"])
                self._price_cache[symbol] = {"price": price, "ts": now}
                return price
        except Exception as e:
            logger.debug(f"[StatArb] Binance price error {symbol}: {e}")
        return None

    # ─── حساب الفرق السعري ───────────────────────────────────────────────────

    def get_spread_signal(self, symbol: str, okx_price: float) -> dict:
        """
        يحسب الفرق بين OKX وBinance ويُنتج إشارة.

        Returns:
            {
                "signal": "BUY" | "SELL" | "NEUTRAL",
                "spread_pct": float,
                "score_boost": float,
                "reason": str
            }
        """
        result = {
            "signal": "NEUTRAL",
            "spread_pct": 0.0,
            "score_boost": 0.0,
            "reason": "لا بيانات Binance"
        }

        binance_price = self._get_binance_price(symbol)
        if binance_price is None or binance_price <= 0:
            return result

        # حساب الفرق
        spread_pct = ((okx_price - binance_price) / binance_price) * 100

        # تسجيل التاريخ
        if symbol not in self._stats:
            self._stats[symbol] = []
        self._stats[symbol].append(spread_pct)
        if len(self._stats[symbol]) > 100:
            self._stats[symbol].pop(0)

        result["spread_pct"] = round(spread_pct, 4)

        # تجاهل البيانات الخاطئة
        if abs(spread_pct) > MAX_SPREAD_PCT:
            result["reason"] = f"فرق كبير جداً ({spread_pct:.2f}%) — تجاهل"
            return result

        # إشارة شراء: OKX أرخص من Binance
        if spread_pct < -MIN_SPREAD_PCT:
            result["signal"] = "BUY"
            result["score_boost"] = min(SIGNAL_SCORE_BOOST, abs(spread_pct) * 0.3)
            result["reason"] = f"OKX أرخص من Binance بـ {abs(spread_pct):.3f}% → تأكيد شراء"
            logger.debug(f"[StatArb] {symbol} BUY signal: OKX={okx_price:.4f} Binance={binance_price:.4f} spread={spread_pct:.3f}%")

        # إشارة بيع: OKX أغلى من Binance
        elif spread_pct > MIN_SPREAD_PCT:
            result["signal"] = "SELL"
            result["score_boost"] = -min(SIGNAL_SCORE_BOOST, spread_pct * 0.3)
            result["reason"] = f"OKX أغلى من Binance بـ {spread_pct:.3f}% → تحذير بيع"
            logger.debug(f"[StatArb] {symbol} SELL signal: OKX={okx_price:.4f} Binance={binance_price:.4f} spread={spread_pct:.3f}%")

        else:
            result["signal"] = "NEUTRAL"
            result["reason"] = f"فرق طبيعي ({spread_pct:.3f}%) — لا إشارة"

        return result

    # ─── إحصائيات ─────────────────────────────────────────────────────────────

    def get_average_spread(self, symbol: str) -> float:
        """متوسط الفرق التاريخي لعملة معينة."""
        history = self._stats.get(symbol, [])
        if not history:
            return 0.0
        return sum(history) / len(history)

    def get_summary(self) -> dict:
        """ملخص حالة المحرك."""
        return {
            "cached_symbols": len(self._price_cache),
            "tracked_symbols": len(self._stats),
            "active": True
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_arb_engine: Optional[StatisticalArbitrageEngine] = None


def get_arb_engine() -> StatisticalArbitrageEngine:
    global _arb_engine
    if _arb_engine is None:
        _arb_engine = StatisticalArbitrageEngine()
    return _arb_engine
