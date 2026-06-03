#!/usr/bin/env python3
"""
Trade Lak - Momentum Scalping Engine
يكتشف اندفاعات السعر القوية ويدخل صفقات سريعة 1-5 دقائق
"""
import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ScalpSignal:
    """إشارة Scalping"""
    symbol: str
    direction: str          # 'LONG' or 'SHORT'
    entry_price: float
    take_profit: float      # +0.8% إلى +1.5%
    stop_loss: float        # -0.4% إلى -0.6%
    confidence: float       # 0-1
    score: float            # 0-10
    reason: str
    momentum_strength: float
    volume_spike: float     # مضاعف الحجم عن المتوسط
    expected_duration_min: int  # الوقت المتوقع للصفقة بالدقائق


class MomentumScalpingEngine:
    """
    محرك Momentum Scalping
    يبحث عن:
    1. اندفاعات حجم مفاجئة (Volume Spike > 3x)
    2. كسر مستوى مقاومة/دعم قوي
    3. تسارع في الزخم (Momentum Acceleration)
    4. تأكيد Order Book
    """

    def __init__(self):
        self.min_volume_spike = 2.5      # الحجم يجب أن يكون 2.5x المتوسط
        self.min_momentum_pct = 0.004    # 0.4% حركة في آخر 3 شمعات
        self.min_confidence = 0.72       # 72% ثقة أدنى
        self.tp_pct = 0.010             # +1.0% TP
        self.sl_pct = 0.005             # -0.5% SL
        self.max_trade_duration = 8      # 8 دقائق أقصى
        self.cooldown_symbols: Dict[str, datetime] = {}
        self.cooldown_minutes = 15       # 15 دقيقة بين صفقتين على نفس العملة

    def _calculate_volume_spike(self, df: pd.DataFrame) -> float:
        """حساب مضاعف الحجم الحالي عن المتوسط"""
        if len(df) < 20:
            return 1.0
        avg_volume = df['volume'].tail(20).mean()
        current_volume = df['volume'].iloc[-1]
        return current_volume / avg_volume if avg_volume > 0 else 1.0

    def _calculate_momentum(self, df: pd.DataFrame, periods: int = 3) -> float:
        """حساب الزخم في آخر N شمعات"""
        if len(df) < periods + 1:
            return 0.0
        return (df['close'].iloc[-1] - df['close'].iloc[-periods - 1]) / df['close'].iloc[-periods - 1]

    def _detect_breakout(self, df: pd.DataFrame) -> Optional[str]:
        """
        اكتشاف كسر مستوى مهم
        يعود بـ 'bullish' أو 'bearish' أو None
        """
        if len(df) < 20:
            return None

        recent = df.tail(20)
        resistance = recent['high'].quantile(0.9)
        support = recent['low'].quantile(0.1)
        current = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]

        # كسر مقاومة
        if prev < resistance and current > resistance * 1.002:
            return 'bullish'
        # كسر دعم
        if prev > support and current < support * 0.998:
            return 'bearish'

        return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 7) -> float:
        """RSI سريع"""
        if len(prices) < period + 1:
            return 50.0
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

    def _is_in_cooldown(self, symbol: str) -> bool:
        """التحقق من Cooldown"""
        if symbol not in self.cooldown_symbols:
            return False
        elapsed = datetime.now() - self.cooldown_symbols[symbol]
        return elapsed.total_seconds() < self.cooldown_minutes * 60

    def analyze(self, symbol: str, df_1m: pd.DataFrame,
                orderbook_imbalance: float = 0.0) -> Optional[ScalpSignal]:
        """
        تحليل فرصة Scalping على الإطار الزمني 1 دقيقة
        
        df_1m: بيانات OHLCV على الإطار 1 دقيقة
        orderbook_imbalance: نسبة عدم التوازن في دفتر الأوامر (-1 إلى +1)
        """
        try:
            if len(df_1m) < 25:
                return None

            # تجاهل إذا كانت في Cooldown
            if self._is_in_cooldown(symbol):
                return None

            current_price = df_1m['close'].iloc[-1]

            # 1. فحص Volume Spike
            vol_spike = self._calculate_volume_spike(df_1m)
            if vol_spike < self.min_volume_spike:
                return None

            # 2. حساب الزخم
            momentum_3 = self._calculate_momentum(df_1m, 3)
            momentum_5 = self._calculate_momentum(df_1m, 5)

            if abs(momentum_3) < self.min_momentum_pct:
                return None

            # 3. تحديد الاتجاه
            direction = 'LONG' if momentum_3 > 0 else 'SHORT'

            # 4. RSI للتأكيد
            rsi = self._calculate_rsi(df_1m['close'])
            if direction == 'LONG' and rsi > 80:
                return None  # ذروة شراء
            if direction == 'SHORT' and rsi < 20:
                return None  # ذروة بيع

            # 5. فحص Breakout
            breakout = self._detect_breakout(df_1m)

            # 6. حساب الثقة
            confidence = 0.5

            # Volume Spike يرفع الثقة
            confidence += min(0.20, (vol_spike - 2.5) * 0.05)

            # Momentum قوي
            confidence += min(0.15, abs(momentum_3) * 20)

            # Breakout يرفع الثقة
            if breakout == direction.lower().replace('long', 'bullish').replace('short', 'bearish'):
                confidence += 0.10

            # Order Book يدعم الاتجاه
            if direction == 'LONG' and orderbook_imbalance > 0.2:
                confidence += 0.08
            elif direction == 'SHORT' and orderbook_imbalance < -0.2:
                confidence += 0.08

            # RSI في المنطقة المثالية
            if direction == 'LONG' and 45 < rsi < 65:
                confidence += 0.05
            elif direction == 'SHORT' and 35 < rsi < 55:
                confidence += 0.05

            confidence = min(0.95, confidence)

            if confidence < self.min_confidence:
                return None

            # 7. حساب TP/SL
            if direction == 'LONG':
                tp = current_price * (1 + self.tp_pct)
                sl = current_price * (1 - self.sl_pct)
            else:
                tp = current_price * (1 - self.tp_pct)
                sl = current_price * (1 + self.sl_pct)

            # 8. حساب النقاط
            score = confidence * 10 * (1 + (vol_spike - 2.5) * 0.1)
            score = min(10.0, score)

            reason_parts = [
                f"Volume Spike: {vol_spike:.1f}x",
                f"Momentum: {momentum_3:.2%}",
                f"RSI: {rsi:.0f}",
            ]
            if breakout:
                reason_parts.append(f"Breakout: {breakout}")

            signal = ScalpSignal(
                symbol=symbol,
                direction=direction,
                entry_price=current_price,
                take_profit=tp,
                stop_loss=sl,
                confidence=confidence,
                score=score,
                reason=" | ".join(reason_parts),
                momentum_strength=abs(momentum_3),
                volume_spike=vol_spike,
                expected_duration_min=min(self.max_trade_duration,
                                          max(1, int(3 / (abs(momentum_3) * 100))))
            )

            logger.info(
                f"[Scalp] 🎯 {symbol} {direction}: "
                f"ثقة={confidence:.0%} | Vol={vol_spike:.1f}x | "
                f"Mom={momentum_3:.2%} | TP={tp:.4f} | SL={sl:.4f}"
            )
            return signal

        except Exception as e:
            logger.error(f"[Scalp] ❌ خطأ في تحليل {symbol}: {e}")
            return None

    def register_trade(self, symbol: str) -> None:
        """تسجيل صفقة لتفعيل Cooldown"""
        self.cooldown_symbols[symbol] = datetime.now()

    def get_active_cooldowns(self) -> List[str]:
        """قائمة العملات في Cooldown"""
        now = datetime.now()
        return [
            s for s, t in self.cooldown_symbols.items()
            if (now - t).total_seconds() < self.cooldown_minutes * 60
        ]


# Singleton
_scalp_engine = None

def get_scalp_engine() -> MomentumScalpingEngine:
    global _scalp_engine
    if _scalp_engine is None:
        _scalp_engine = MomentumScalpingEngine()
    return _scalp_engine
