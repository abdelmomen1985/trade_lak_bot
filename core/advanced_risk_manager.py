# ============================================================
# Trade Lak Bot - Advanced Risk Management Module
# تطبيق Trade لك - وحدة إدارة المخاطر المتقدمة
# ============================================================

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit Breaker - Stops trading on excessive losses
    قاطع الدائرة - يوقف التداول عند الخسائر الكبيرة
    
    Implements multiple levels of protection:
    1. Daily loss limit
    2. Weekly loss limit
    3. Monthly loss limit
    4. Consecutive loss limit
    """
    
    def __init__(self, 
                 daily_loss_limit_pct=5,
                 weekly_loss_limit_pct=10,
                 monthly_loss_limit_pct=15,
                 consecutive_loss_limit=5):
        """
        Initialize Circuit Breaker
        
        Args:
            daily_loss_limit_pct: Max daily loss % before stopping
            weekly_loss_limit_pct: Max weekly loss % before stopping
            monthly_loss_limit_pct: Max monthly loss % before stopping
            consecutive_loss_limit: Max consecutive losses before stopping
        """
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.weekly_loss_limit_pct = weekly_loss_limit_pct
        self.monthly_loss_limit_pct = monthly_loss_limit_pct
        self.consecutive_loss_limit = consecutive_loss_limit
        
        # Trade history
        self.trade_history = []
        
        # Circuit states
        self.daily_breaker_triggered = False
        self.weekly_breaker_triggered = False
        self.monthly_breaker_triggered = False
        self.consecutive_breaker_triggered = False
        
        logger.info("✅ Circuit Breaker initialized")
    
    def record_trade(self, trade_data: Dict):
        """
        Record a completed trade
        تسجيل صفقة منتهية
        
        Args:
            trade_data: {
                'timestamp': datetime,
                'symbol': 'BTC/USDT',
                'profit_loss': 100,
                'profit_loss_pct': 2.5
            }
        """
        self.trade_history.append({
            'timestamp': trade_data.get('timestamp', datetime.now()),
            'symbol': trade_data.get('symbol'),
            'profit_loss': trade_data.get('profit_loss', 0),
            'profit_loss_pct': trade_data.get('profit_loss_pct', 0)
        })
        
        # Check circuit breakers
        self._check_daily_limit()
        self._check_weekly_limit()
        self._check_monthly_limit()
        self._check_consecutive_losses()
    
    def _check_daily_limit(self):
        """Check daily loss limit"""
        today = datetime.now().date()
        today_trades = [
            t for t in self.trade_history
            if t['timestamp'].date() == today
        ]
        
        daily_pnl = sum(t['profit_loss_pct'] for t in today_trades)
        
        if daily_pnl < -self.daily_loss_limit_pct:
            self.daily_breaker_triggered = True
            logger.warning(f"⚠️ DAILY CIRCUIT BREAKER TRIGGERED: {daily_pnl:.2f}% loss")
        else:
            self.daily_breaker_triggered = False
    
    def _check_weekly_limit(self):
        """Check weekly loss limit"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        week_trades = [
            t for t in self.trade_history
            if t['timestamp'] >= week_start
        ]
        
        weekly_pnl = sum(t['profit_loss_pct'] for t in week_trades)
        
        if weekly_pnl < -self.weekly_loss_limit_pct:
            self.weekly_breaker_triggered = True
            logger.warning(f"⚠️ WEEKLY CIRCUIT BREAKER TRIGGERED: {weekly_pnl:.2f}% loss")
        else:
            self.weekly_breaker_triggered = False
    
    def _check_monthly_limit(self):
        """Check monthly loss limit"""
        today = datetime.now()
        month_start = today.replace(day=1)
        
        month_trades = [
            t for t in self.trade_history
            if t['timestamp'] >= month_start
        ]
        
        monthly_pnl = sum(t['profit_loss_pct'] for t in month_trades)
        
        if monthly_pnl < -self.monthly_loss_limit_pct:
            self.monthly_breaker_triggered = True
            logger.warning(f"⚠️ MONTHLY CIRCUIT BREAKER TRIGGERED: {monthly_pnl:.2f}% loss")
        else:
            self.monthly_breaker_triggered = False
    
    def _check_consecutive_losses(self):
        """Check consecutive losses"""
        if len(self.trade_history) < self.consecutive_loss_limit:
            self.consecutive_breaker_triggered = False
            return
        
        recent_trades = self.trade_history[-self.consecutive_loss_limit:]
        consecutive_losses = sum(
            1 for t in recent_trades if t['profit_loss'] < 0
        )
        
        if consecutive_losses >= self.consecutive_loss_limit:
            self.consecutive_breaker_triggered = True
            logger.warning(f"⚠️ CONSECUTIVE LOSSES CIRCUIT BREAKER TRIGGERED: {consecutive_losses} losses")
        else:
            self.consecutive_breaker_triggered = False
    
    def is_trading_allowed(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed
        التحقق من السماح بالتداول
        
        Returns:
            (is_allowed, reason)
        """
        if self.daily_breaker_triggered:
            return False, "Daily loss limit exceeded"
        
        if self.weekly_breaker_triggered:
            return False, "Weekly loss limit exceeded"
        
        if self.monthly_breaker_triggered:
            return False, "Monthly loss limit exceeded"
        
        if self.consecutive_breaker_triggered:
            return False, "Too many consecutive losses"
        
        return True, "Trading allowed"
    
    def get_status(self) -> Dict:
        """Get circuit breaker status"""
        today = datetime.now().date()
        today_trades = [
            t for t in self.trade_history
            if t['timestamp'].date() == today
        ]
        daily_pnl = sum(t['profit_loss_pct'] for t in today_trades)
        
        return {
            'daily_breaker': self.daily_breaker_triggered,
            'weekly_breaker': self.weekly_breaker_triggered,
            'monthly_breaker': self.monthly_breaker_triggered,
            'consecutive_breaker': self.consecutive_breaker_triggered,
            'daily_pnl': float(daily_pnl),
            'daily_limit': -self.daily_loss_limit_pct,
            'total_trades': len(self.trade_history)
        }


class CorrelationFilter:
    """
    Correlation Filter - Prevents correlated positions
    مرشح الارتباط - يمنع المراكز المترابطة
    
    Prevents opening multiple positions in highly correlated assets
    """
    
    def __init__(self, correlation_threshold=0.7):
        """
        Initialize Correlation Filter
        
        Args:
            correlation_threshold: Max allowed correlation between positions
        """
        self.correlation_threshold = correlation_threshold
        self.price_history = {}  # {symbol: [prices]}
        self.max_history = 100
        logger.info("✅ Correlation Filter initialized")
    
    def add_price(self, symbol: str, price: float):
        """
        Add price data for correlation calculation
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(price)
        
        # Keep only recent prices
        if len(self.price_history[symbol]) > self.max_history:
            self.price_history[symbol] = self.price_history[symbol][-self.max_history:]
    
    def calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Calculate correlation between two symbols
        حساب الارتباط بين رمزين
        """
        try:
            prices1 = self.price_history.get(symbol1, [])
            prices2 = self.price_history.get(symbol2, [])
            
            if len(prices1) < 10 or len(prices2) < 10:
                return 0
            
            # Use recent prices
            min_len = min(len(prices1), len(prices2), 50)
            prices1 = prices1[-min_len:]
            prices2 = prices2[-min_len:]
            
            # Calculate returns
            returns1 = np.diff(prices1) / prices1[:-1]
            returns2 = np.diff(prices2) / prices2[:-1]
            
            # Calculate correlation
            min_ret = min(len(returns1), len(returns2))
            returns1 = returns1[-min_ret:]
            returns2 = returns2[-min_ret:]
            correlation = np.corrcoef(returns1, returns2)[0, 1]
            
            return float(correlation) if not np.isnan(correlation) else 0
        
        except Exception as e:
            logger.error(f"❌ Error calculating correlation: {e}")
            return 0
    
    def can_open_position(self, new_symbol: str, open_positions: List[str]) -> Tuple[bool, str]:
        """
        Check if new position can be opened
        التحقق من إمكانية فتح مركز جديد
        
        Args:
            new_symbol: Symbol to open position in
            open_positions: List of currently open positions
        
        Returns:
            (can_open, reason)
        """
        for open_symbol in open_positions:
            correlation = self.calculate_correlation(new_symbol, open_symbol)
            
            if correlation > self.correlation_threshold:
                return False, f"High correlation with {open_symbol}: {correlation:.2f}"
        
        return True, "No correlation issues"
    
    def get_correlation_matrix(self, symbols: List[str]) -> Dict:
        """
        Get correlation matrix for symbols
        الحصول على مصفوفة الارتباط للرموز
        """
        correlations = {}
        
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                key = f"{sym1}-{sym2}"
                correlations[key] = self.calculate_correlation(sym1, sym2)
        
        return correlations


class PositionSizer:
    """
    Position Sizer - Calculates optimal position size
    حجم المركز - يحسب حجم المركز الأمثل
    
    Uses Kelly Criterion and risk management rules
    """
    
    def __init__(self, 
                 total_capital: float,
                 risk_per_trade_pct: float = 0.02):
        """
        Initialize Position Sizer
        
        Args:
            total_capital: Total capital available
            risk_per_trade_pct: Risk per trade as % of capital
        """
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.trade_history = []
        logger.info("✅ Position Sizer initialized")
    
    def calculate_position_size(self,
                               entry_price: float,
                               stop_loss: float,
                               available_capital: float = None) -> float:
        """
        Calculate optimal position size
        حساب حجم المركز الأمثل
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            available_capital: Available capital (uses total if None)
        
        Returns:
            Position size in base currency
        """
        if available_capital is None:
            available_capital = self.total_capital
        
        try:
            # Risk amount
            risk_amount = available_capital * self.risk_per_trade_pct
            
            # Distance to stop loss
            risk_distance = abs(entry_price - stop_loss)
            
            if risk_distance == 0:
                logger.warning("⚠️ Stop loss too close to entry")
                return available_capital * 0.01  # Minimum position
            
            # Position size
            position_size = risk_amount / risk_distance
            
            # Cap position size
            max_position = available_capital * 0.1  # Max 10% of capital per trade
            position_size = min(position_size, max_position)
            
            return float(position_size)
        
        except Exception as e:
            logger.error(f"❌ Error calculating position size: {e}")
            return available_capital * 0.01
    
    def calculate_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly Criterion fraction
        حساب كسر كيلي
        
        Args:
            win_rate: Winning trades / total trades
            avg_win: Average winning trade %
            avg_loss: Average losing trade %
        
        Returns:
            Kelly fraction (0-1)
        """
        try:
            if avg_loss == 0:
                return 0.25
            
            kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
            
            # Use half Kelly for safety (Kelly/2)
            kelly_fraction = kelly / 2
            
            # Cap at 25% for safety
            kelly_fraction = max(0.01, min(kelly_fraction, 0.25))
            
            return float(kelly_fraction)
        
        except Exception as e:
            logger.error(f"❌ Error calculating Kelly fraction: {e}")
            return 0.02
    
    def record_trade(self, trade_data: Dict):
        """Record trade for statistics"""
        self.trade_history.append(trade_data)
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0
            }
        
        df = pd.DataFrame(self.trade_history)
        
        total_trades = len(df)
        winning_trades = (df['profit_loss'] > 0).sum()
        losing_trades = (df['profit_loss'] < 0).sum()
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = df[df['profit_loss'] > 0]['profit_loss'].mean() if winning_trades > 0 else 0
        avg_loss = abs(df[df['profit_loss'] < 0]['profit_loss'].mean()) if losing_trades > 0 else 0
        
        total_wins = df[df['profit_loss'] > 0]['profit_loss'].sum()
        total_losses = abs(df[df['profit_loss'] < 0]['profit_loss'].sum())
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'total_pnl': float(df['profit_loss'].sum())
        }


class AdvancedRiskManager:
    """
    Advanced Risk Manager - Combines all risk management tools
    مدير المخاطر المتقدم - يدمج كل أدوات إدارة المخاطر
    """
    
    def __init__(self,
                 total_capital: float,
                 risk_per_trade_pct: float = 0.02,
                 daily_loss_limit_pct: float = 5,
                 correlation_threshold: float = 0.7):
        """
        Initialize Advanced Risk Manager
        """
        self.circuit_breaker = CircuitBreaker(daily_loss_limit_pct=daily_loss_limit_pct)
        self.correlation_filter = CorrelationFilter(correlation_threshold=correlation_threshold)
        self.position_sizer = PositionSizer(total_capital, risk_per_trade_pct)
        
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        
        logger.info("✅ Advanced Risk Manager initialized")
    
    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed"""
        return self.circuit_breaker.is_trading_allowed()
    
    def can_open_position(self, symbol: str, open_positions: List[str]) -> Tuple[bool, str]:
        """Check if position can be opened"""
        return self.correlation_filter.can_open_position(symbol, open_positions)
    
    def calculate_position_size(self,
                               entry_price: float,
                               stop_loss: float,
                               available_capital: float = None) -> float:
        """Calculate position size"""
        return self.position_sizer.calculate_position_size(entry_price, stop_loss, available_capital)
    
    def record_trade(self, trade_data: Dict):
        """Record completed trade"""
        self.circuit_breaker.record_trade(trade_data)
        self.position_sizer.record_trade(trade_data)
    
    def add_price(self, symbol: str, price: float):
        """Add price for correlation calculation"""
        self.correlation_filter.add_price(symbol, price)
    
    def get_status(self) -> Dict:
        """Get full risk management status"""
        return {
            'circuit_breaker': self.circuit_breaker.get_status(),
            'position_sizer_stats': self.position_sizer.get_statistics(),
            'can_trade': self.can_trade()[0],
            'trade_reason': self.can_trade()[1]
        }
