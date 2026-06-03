#!/usr/bin/env python3
"""
Trade Lak - Grid Trading Engine
يعمل في الأسواق الجانبية (Sideways) لتحقيق أرباح من التذبذب
"""
import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """مستوى واحد في الشبكة"""
    price: float
    level_type: str   # 'buy' or 'sell'
    order_id: Optional[str] = None
    filled: bool = False
    profit: float = 0.0


@dataclass
class GridConfig:
    """إعدادات الشبكة"""
    symbol: str
    upper_price: float          # سقف الشبكة
    lower_price: float          # قاع الشبكة
    grid_count: int = 8         # عدد المستويات
    capital_per_grid: float = 20.0  # رأس مال لكل مستوى ($20 × 8 = $160)
    min_profit_pct: float = 0.008   # 0.8% ربح أدنى لكل شبكة (يغطي الرسوم)

    @property
    def grid_spacing(self) -> float:
        return (self.upper_price - self.lower_price) / self.grid_count

    @property
    def total_capital(self) -> float:
        return self.capital_per_grid * (self.grid_count // 2)


class GridTradingEngine:
    """
    محرك Grid Trading للأسواق الجانبية
    يضع أوامر شراء وبيع على مستويات ثابتة ويكسب من التذبذب
    """

    def __init__(self):
        self.active_grids: Dict[str, GridConfig] = {}
        self.grid_levels: Dict[str, List[GridLevel]] = {}
        self.total_profit: float = 0.0
        self.trade_count: int = 0

    def detect_sideways_range(self, df: pd.DataFrame, lookback: int = 48) -> Optional[Tuple[float, float]]:
        """
        اكتشاف نطاق السوق الجانبي
        يعود بـ (lower, upper) إذا كان السوق جانبياً، وإلا None
        """
        if len(df) < lookback:
            return None

        recent = df.tail(lookback)
        high = recent['high'].max()
        low = recent['low'].min()
        close = recent['close'].iloc[-1]

        # حساب نطاق التذبذب
        range_pct = (high - low) / low

        # شرط السوق الجانبي: نطاق بين 3% و 15%
        if range_pct < 0.03 or range_pct > 0.15:
            return None

        # التحقق من أن السعر داخل النطاق
        if close < low * 1.005 or close > high * 0.995:
            return None

        # التحقق من عدم وجود اتجاه قوي (EMA)
        ema20 = df['close'].ewm(span=20).mean()
        ema50 = df['close'].ewm(span=50).mean()
        ema_diff_pct = abs(ema20.iloc[-1] - ema50.iloc[-1]) / ema50.iloc[-1]

        # إذا كان الفرق بين EMA20 وEMA50 أكبر من 2% → يوجد اتجاه
        if ema_diff_pct > 0.02:
            return None

        # تضييق النطاق بنسبة 5% من كل طرف لتجنب الاختراقات
        buffer = (high - low) * 0.05
        return (low + buffer, high - buffer)

    def should_activate_grid(self, symbol: str, df: pd.DataFrame,
                              available_capital: float) -> Optional[GridConfig]:
        """
        تحديد ما إذا كان يجب تفعيل Grid على هذه العملة
        """
        # لا تفعيل إذا كانت الشبكة نشطة مسبقاً
        if symbol in self.active_grids:
            return None

        # رأس المال الأدنى للـ Grid
        if available_capital < 100:
            return None

        # اكتشاف النطاق
        range_result = self.detect_sideways_range(df)
        if not range_result:
            return None

        lower, upper = range_result
        range_pct = (upper - lower) / lower

        # حساب عدد المستويات بناءً على النطاق
        grid_count = min(10, max(5, int(range_pct / 0.015)))

        # رأس المال لكل مستوى
        capital_per_grid = min(25.0, available_capital / (grid_count * 2))
        if capital_per_grid < 15:
            return None

        config = GridConfig(
            symbol=symbol,
            upper_price=upper,
            lower_price=lower,
            grid_count=grid_count,
            capital_per_grid=capital_per_grid
        )

        logger.info(
            f"[Grid] 📊 {symbol}: نطاق {lower:.4f}–{upper:.4f} "
            f"({range_pct:.1%}) | {grid_count} مستويات | "
            f"${capital_per_grid:.1f}/مستوى"
        )
        return config

    def build_grid_levels(self, config: GridConfig) -> List[GridLevel]:
        """بناء مستويات الشبكة"""
        levels = []
        spacing = config.grid_spacing
        current_price_approx = (config.upper_price + config.lower_price) / 2

        for i in range(config.grid_count + 1):
            price = config.lower_price + (i * spacing)
            # مستويات تحت السعر الحالي = شراء، فوقه = بيع
            level_type = 'buy' if price < current_price_approx else 'sell'
            levels.append(GridLevel(price=round(price, 6), level_type=level_type))

        return levels

    def activate_grid(self, symbol: str, config: GridConfig) -> bool:
        """تفعيل الشبكة وتسجيلها"""
        try:
            levels = self.build_grid_levels(config)
            self.active_grids[symbol] = config
            self.grid_levels[symbol] = levels

            buy_levels = [l for l in levels if l.level_type == 'buy']
            sell_levels = [l for l in levels if l.level_type == 'sell']

            logger.info(
                f"[Grid] ✅ {symbol}: شبكة مفعّلة | "
                f"{len(buy_levels)} شراء + {len(sell_levels)} بيع | "
                f"رأس مال: ${config.total_capital:.1f}"
            )
            return True
        except Exception as e:
            logger.error(f"[Grid] ❌ خطأ في تفعيل {symbol}: {e}")
            return False

    def check_grid_triggers(self, symbol: str, current_price: float) -> List[Dict]:
        """
        فحص المستويات التي تم تجاوزها وإرجاع أوامر التنفيذ
        """
        if symbol not in self.active_grids:
            return []

        config = self.active_grids[symbol]
        levels = self.grid_levels[symbol]
        orders_to_execute = []

        for level in levels:
            if level.filled:
                continue

            # تحقق من تجاوز مستوى الشراء
            if level.level_type == 'buy' and current_price <= level.price * 1.001:
                orders_to_execute.append({
                    'action': 'buy',
                    'price': level.price,
                    'amount_usdt': config.capital_per_grid,
                    'symbol': symbol,
                    'grid_level': level,
                    'tp_price': level.price * (1 + config.min_profit_pct + 0.002),
                    'sl_price': config.lower_price * 0.99  # SL تحت قاع الشبكة
                })

            # تحقق من تجاوز مستوى البيع
            elif level.level_type == 'sell' and current_price >= level.price * 0.999:
                orders_to_execute.append({
                    'action': 'sell',
                    'price': level.price,
                    'amount_usdt': config.capital_per_grid,
                    'symbol': symbol,
                    'grid_level': level
                })

        return orders_to_execute

    def should_deactivate_grid(self, symbol: str, current_price: float) -> bool:
        """
        تحديد ما إذا كان يجب إيقاف الشبكة
        (عند كسر حدود النطاق)
        """
        if symbol not in self.active_grids:
            return False

        config = self.active_grids[symbol]
        buffer = config.grid_spacing

        # كسر فوق السقف أو تحت القاع
        if current_price > config.upper_price + buffer:
            logger.warning(f"[Grid] ⚠️ {symbol}: كسر فوق السقف {config.upper_price:.4f} — إيقاف الشبكة")
            return True
        if current_price < config.lower_price - buffer:
            logger.warning(f"[Grid] ⚠️ {symbol}: كسر تحت القاع {config.lower_price:.4f} — إيقاف الشبكة")
            return True

        return False

    def deactivate_grid(self, symbol: str) -> None:
        """إيقاف الشبكة"""
        if symbol in self.active_grids:
            del self.active_grids[symbol]
        if symbol in self.grid_levels:
            del self.grid_levels[symbol]
        logger.info(f"[Grid] 🔴 {symbol}: شبكة مُوقَفة")

    def get_grid_summary(self) -> Dict:
        """ملخص حالة جميع الشبكات"""
        return {
            'active_grids': len(self.active_grids),
            'symbols': list(self.active_grids.keys()),
            'total_profit': self.total_profit,
            'trade_count': self.trade_count
        }


# Singleton
_grid_engine = None

def get_grid_engine() -> GridTradingEngine:
    global _grid_engine
    if _grid_engine is None:
        _grid_engine = GridTradingEngine()
    return _grid_engine
