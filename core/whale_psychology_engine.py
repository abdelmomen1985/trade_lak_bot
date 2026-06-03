"""
Whale Psychology Engine
محرك نفسية الحيتان المتقدم
Detects whale manipulation patterns, stop loss hunts, and pump/dump schemes
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from collections import deque


class WhalePattern(Enum):
    """Types of whale manipulation patterns"""
    STOP_LOSS_HUNT = "Stop Loss Hunt"           # صيد Stop Loss
    PUMP_AND_DUMP = "Pump and Dump"             # الضخ والتفريغ
    ACCUMULATION = "Accumulation"               # التجميع
    DISTRIBUTION = "Distribution"               # التوزيع
    FAKE_BREAKOUT = "Fake Breakout"             # كسر وهمي
    SPOOFING = "Spoofing"                       # الخداع
    WASH_TRADING = "Wash Trading"               # التداول الوهمي
    NONE = "No Pattern"                         # لا يوجد نمط


@dataclass
class WhaleAlert:
    """Alert for detected whale activity"""
    pattern: WhalePattern
    confidence: float           # 0-1
    severity: str               # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    recommendation: str
    affected_price_level: float
    expected_direction: str     # UP, DOWN, NEUTRAL
    time_frame: str             # الإطار الزمني المتوقع


class WhaleDetector:
    """Detects whale manipulation patterns"""
    
    def __init__(self, lookback_periods: int = 100):
        """
        Initialize whale detector
        
        Args:
            lookback_periods: Number of candles to analyze
        """
        self.lookback_periods = lookback_periods
        self.price_history = deque(maxlen=lookback_periods)
        self.volume_history = deque(maxlen=lookback_periods)
        self.high_history = deque(maxlen=lookback_periods)
        self.low_history = deque(maxlen=lookback_periods)
        self.close_history = deque(maxlen=lookback_periods)
        self.alerts = []
        
        # Thresholds
        self.VOLUME_SPIKE_THRESHOLD = 2.5      # 250% of average
        self.PRICE_SPIKE_THRESHOLD = 0.05      # 5% price move
        self.ACCUMULATION_THRESHOLD = 0.03     # 3% consolidation
        self.DISTRIBUTION_THRESHOLD = 0.02     # 2% distribution
        
    def add_candle(self, open_price: float, high: float, low: float, 
                   close: float, volume: float):
        """Add a new candle to the history"""
        self.price_history.append(close)
        self.volume_history.append(volume)
        self.high_history.append(high)
        self.low_history.append(low)
        self.close_history.append(close)
    
    def detect_stop_loss_hunt(self) -> Optional[WhaleAlert]:
        """
        Detect stop loss hunting pattern
        صيد Stop Loss: حيتان تضغط السعر لأسفل لضرب Stop Loss ثم ترفعه
        """
        if len(self.price_history) < 5:
            return None
        
        recent_prices = list(self.price_history)[-5:]
        recent_volumes = list(self.volume_history)[-5:]
        recent_lows = list(self.low_history)[-5:]
        
        # Pattern: High volume down move followed by recovery
        avg_volume = np.mean(list(self.volume_history)[-20:])
        
        # Check for sharp down move with high volume
        down_move = (recent_prices[-2] - recent_prices[-1]) / recent_prices[-2]
        volume_spike = recent_volumes[-1] / avg_volume if avg_volume > 0 else 0
        
        if down_move > 0.02 and volume_spike > 2.0:
            # Check if price recovered
            if recent_prices[-1] > recent_prices[-2]:
                confidence = min(volume_spike / 3.0, 1.0)
                
                return WhaleAlert(
                    pattern=WhalePattern.STOP_LOSS_HUNT,
                    confidence=confidence,
                    severity="HIGH" if confidence > 0.7 else "MEDIUM",
                    description=f"🐋 كشف صيد Stop Loss! انخفاض حاد بـ {down_move*100:.2f}% مع حجم {volume_spike:.1f}x",
                    recommendation="⚠️ لا تضع Stop Loss قريب جداً من السعر الحالي",
                    affected_price_level=min(recent_lows),
                    expected_direction="UP",
                    time_frame="1-4 ساعات"
                )
        
        return None
    
    def detect_pump_and_dump(self) -> Optional[WhaleAlert]:
        """
        Detect pump and dump scheme
        الضخ والتفريغ: ارتفاع سريع متبوع بانخفاض حاد
        """
        if len(self.price_history) < 10:
            return None
        
        recent_prices = list(self.price_history)[-10:]
        recent_volumes = list(self.volume_history)[-10:]
        
        # Calculate price momentum
        price_changes = [
            (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
            for i in range(1, len(recent_prices))
        ]
        
        # Check for rapid pump (3+ consecutive up candles with increasing volume)
        pump_count = 0
        pump_volume = 0
        for i in range(len(price_changes) - 3):
            if (price_changes[i] > 0.01 and price_changes[i+1] > 0.01 and 
                price_changes[i+2] > 0.01):
                pump_count += 1
                pump_volume = np.mean(recent_volumes[i:i+3])
        
        if pump_count > 0:
            # Check for dump (sharp down move)
            recent_change = price_changes[-1]
            if recent_change < -0.02:
                avg_volume = np.mean(recent_volumes[:-1])
                volume_ratio = pump_volume / avg_volume if avg_volume > 0 else 0
                
                total_pump = sum([c for c in price_changes if c > 0])
                
                confidence = min(abs(recent_change) * 10, 1.0)
                
                return WhaleAlert(
                    pattern=WhalePattern.PUMP_AND_DUMP,
                    confidence=confidence,
                    severity="CRITICAL" if confidence > 0.8 else "HIGH",
                    description=f"🚨 كشف ضخ وتفريغ! ارتفاع {total_pump*100:.2f}% متبوع بانخفاض {recent_change*100:.2f}%",
                    recommendation="🚫 تجنب الدخول! هذا فخ حيتان واضح جداً",
                    affected_price_level=max(recent_prices[-5:]),
                    expected_direction="DOWN",
                    time_frame="دقائق إلى ساعات"
                )
        
        return None
    
    def detect_accumulation(self) -> Optional[WhaleAlert]:
        """
        Detect accumulation pattern
        التجميع: حيتان تجمع العملات بأسعار منخفضة
        """
        if len(self.price_history) < 20:
            return None
        
        recent_prices = list(self.price_history)[-20:]
        recent_volumes = list(self.volume_history)[-20:]
        
        # Check for consolidation (low volatility)
        price_range = max(recent_prices) - min(recent_prices)
        avg_price = np.mean(recent_prices)
        volatility = price_range / avg_price if avg_price > 0 else 0
        
        # Accumulation: low volatility + high volume
        avg_volume = np.mean(recent_volumes)
        volume_above_avg = sum([1 for v in recent_volumes if v > avg_volume * 1.2])
        
        if volatility < self.ACCUMULATION_THRESHOLD and volume_above_avg > 8:
            confidence = min((1 - volatility / 0.05) * 0.8, 1.0)
            
            return WhaleAlert(
                pattern=WhalePattern.ACCUMULATION,
                confidence=confidence,
                severity="MEDIUM",
                description=f"🐋 كشف تجميع! تذبذب منخفض {volatility*100:.2f}% مع حجم عالي",
                recommendation="💡 حيتان تجمع العملات. توقع ارتفاع قريب",
                affected_price_level=np.mean(recent_prices),
                expected_direction="UP",
                time_frame="أيام إلى أسابيع"
            )
        
        return None
    
    def detect_distribution(self) -> Optional[WhaleAlert]:
        """
        Detect distribution pattern
        التوزيع: حيتان تفرغ العملات بأسعار عالية
        """
        if len(self.price_history) < 20:
            return None
        
        recent_prices = list(self.price_history)[-20:]
        recent_volumes = list(self.volume_history)[-20:]
        
        # Check for high volatility with declining trend
        price_range = max(recent_prices) - min(recent_prices)
        avg_price = np.mean(recent_prices)
        volatility = price_range / avg_price if avg_price > 0 else 0
        
        # Declining trend
        trend = recent_prices[-1] - recent_prices[0]
        trend_pct = trend / recent_prices[0] if recent_prices[0] > 0 else 0
        
        # Distribution: high volatility + declining + high volume
        avg_volume = np.mean(recent_volumes)
        volume_above_avg = sum([1 for v in recent_volumes if v > avg_volume * 1.2])
        
        if volatility > 0.02 and trend_pct < -0.01 and volume_above_avg > 8:
            confidence = min(abs(trend_pct) * 50, 1.0)
            
            return WhaleAlert(
                pattern=WhalePattern.DISTRIBUTION,
                confidence=confidence,
                severity="HIGH" if confidence > 0.7 else "MEDIUM",
                description=f"🐋 كشف توزيع! اتجاه هابط {trend_pct*100:.2f}% مع حجم عالي",
                recommendation="⚠️ حيتان تفرغ العملات. توقع انخفاض إضافي",
                affected_price_level=max(recent_prices),
                expected_direction="DOWN",
                time_frame="أيام إلى أسابيع"
            )
        
        return None
    
    def detect_fake_breakout(self) -> Optional[WhaleAlert]:
        """
        Detect fake breakout pattern
        الكسر الوهمي: حيتان تكسر مستوى مقاومة ثم تسحب السعر للخلف
        """
        if len(self.price_history) < 15:
            return None
        
        recent_prices = list(self.price_history)[-15:]
        recent_volumes = list(self.volume_history)[-15:]
        recent_highs = list(self.high_history)[-15:]
        
        # Find resistance level (highest high in last 15 candles)
        resistance = max(recent_highs[:-1])
        current_price = recent_prices[-1]
        
        # Check if price broke above resistance
        if current_price > resistance * 1.005:  # 0.5% above
            # Check if it's pulling back quickly
            if recent_prices[-1] < recent_prices[-2]:
                volume_spike = recent_volumes[-1] / np.mean(recent_volumes[:-1])
                
                if volume_spike > 1.5:
                    confidence = min(volume_spike / 3.0, 1.0)
                    
                    return WhaleAlert(
                        pattern=WhalePattern.FAKE_BREAKOUT,
                        confidence=confidence,
                        severity="HIGH",
                        description=f"🚨 كشف كسر وهمي! كسر المقاومة ثم سحب بـ {(recent_prices[-2]-current_price)/current_price*100:.2f}%",
                        recommendation="⚠️ لا تدخل على الكسر! قد يكون فخ حيتان",
                        affected_price_level=resistance,
                        expected_direction="DOWN",
                        time_frame="دقائق إلى ساعات"
                    )
        
        return None
    
    def detect_spoofing(self) -> Optional[WhaleAlert]:
        """
        Detect spoofing pattern
        الخداع: أوامر وهمية كبيرة لتحريك السعر
        """
        if len(self.price_history) < 10:
            return None
        
        recent_volumes = list(self.volume_history)[-10:]
        recent_prices = list(self.price_history)[-10:]
        
        # Spoofing: huge volume spike without significant price move
        avg_volume = np.mean(recent_volumes[:-1])
        current_volume = recent_volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        price_change = abs(recent_prices[-1] - recent_prices[-2]) / recent_prices[-2]
        
        if volume_ratio > 3.0 and price_change < 0.01:
            confidence = min((volume_ratio - 3.0) / 2.0, 1.0)
            
            return WhaleAlert(
                pattern=WhalePattern.SPOOFING,
                confidence=confidence,
                severity="MEDIUM",
                description=f"🎭 كشف خداع! حجم {volume_ratio:.1f}x لكن حركة سعر {price_change*100:.2f}% فقط",
                recommendation="💡 أوامر وهمية. انتظر حتى تتضح الحركة الحقيقية",
                affected_price_level=recent_prices[-1],
                expected_direction="NEUTRAL",
                time_frame="دقائق"
            )
        
        return None
    
    def analyze_all_patterns(self) -> List[WhaleAlert]:
        """
        Analyze all whale patterns
        تحليل جميع أنماط الحيتان
        """
        alerts = []
        
        # Check each pattern
        patterns = [
            self.detect_stop_loss_hunt(),
            self.detect_pump_and_dump(),
            self.detect_accumulation(),
            self.detect_distribution(),
            self.detect_fake_breakout(),
            self.detect_spoofing(),
        ]
        
        for pattern in patterns:
            if pattern is not None:
                alerts.append(pattern)
        
        # Sort by severity and confidence
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        alerts.sort(
            key=lambda x: (severity_order.get(x.severity, 4), -x.confidence)
        )
        
        return alerts
    
    def get_whale_score(self) -> float:
        """
        Calculate overall whale activity score (0-100)
        حساب درجة نشاط الحيتان الكلية
        """
        alerts = self.analyze_all_patterns()
        
        if not alerts:
            return 0.0
        
        # Weight by severity
        severity_weights = {
            'CRITICAL': 100,
            'HIGH': 75,
            'MEDIUM': 50,
            'LOW': 25
        }
        
        total_score = 0
        for alert in alerts:
            weight = severity_weights.get(alert.severity, 0)
            total_score += weight * alert.confidence
        
        # Average and normalize
        avg_score = total_score / len(alerts) if alerts else 0
        return min(avg_score, 100.0)
    
    def get_recommendation(self) -> str:
        """
        Get overall recommendation based on whale activity
        """
        alerts = self.analyze_all_patterns()
        
        if not alerts:
            return "✅ لا يوجد نشاط حيتان مريب - آمن للتداول"
        
        # Get highest severity alert
        top_alert = alerts[0]
        
        if top_alert.severity == 'CRITICAL':
            return f"🚫 {top_alert.recommendation}"
        elif top_alert.severity == 'HIGH':
            return f"⚠️ {top_alert.recommendation}"
        elif top_alert.severity == 'MEDIUM':
            return f"💡 {top_alert.recommendation}"
        else:
            return f"ℹ️ {top_alert.recommendation}"


class WhaleProtectionSystem:
    """System to protect against whale manipulation"""
    
    def __init__(self):
        """Initialize protection system"""
        self.detector = WhaleDetector()
        self.protected_trades = {}
        
    def add_candle(self, open_price: float, high: float, low: float,
                   close: float, volume: float):
        """Add a new candle for analysis"""
        self.detector.add_candle(open_price, high, low, close, volume)
    
    def should_enter_trade(self, symbol: str, direction: str) -> Tuple[bool, str]:
        """
        Determine if it's safe to enter a trade
        
        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            
        Returns:
            (should_enter, reason)
        """
        alerts = self.detector.analyze_all_patterns()
        whale_score = self.detector.get_whale_score()
        
        # Don't enter if whale score is too high
        if whale_score > 70:
            return False, f"🚫 نشاط حيتان مريب جداً (النقاط: {whale_score:.0f}/100)"
        
        # Check specific patterns
        for alert in alerts:
            if alert.severity == 'CRITICAL':
                return False, f"🚫 {alert.description}"
            
            # For LONG trades, avoid accumulation/distribution patterns
            if direction == 'LONG' and alert.pattern == WhalePattern.DISTRIBUTION:
                return False, f"⚠️ توزيع حيتان - تجنب الشراء"
            
            # For SHORT trades, avoid accumulation patterns
            if direction == 'SHORT' and alert.pattern == WhalePattern.ACCUMULATION:
                return False, f"⚠️ تجميع حيتان - تجنب البيع"
        
        return True, "✅ آمن للدخول"
    
    def adjust_stop_loss(self, entry_price: float, direction: str) -> float:
        """
        Adjust stop loss based on whale activity
        
        Args:
            entry_price: Entry price
            direction: LONG or SHORT
            
        Returns:
            Recommended stop loss price
        """
        alerts = self.detector.analyze_all_patterns()
        
        # Base stop loss (2% from entry)
        if direction == 'LONG':
            base_sl = entry_price * 0.98
        else:
            base_sl = entry_price * 1.02
        
        # Adjust based on stop loss hunt detection
        for alert in alerts:
            if alert.pattern == WhalePattern.STOP_LOSS_HUNT:
                # Move stop loss further away
                if direction == 'LONG':
                    base_sl = min(base_sl, alert.affected_price_level * 0.95)
                else:
                    base_sl = max(base_sl, alert.affected_price_level * 1.05)
        
        return base_sl
    
    def get_status(self) -> Dict:
        """Get protection system status"""
        alerts = self.detector.analyze_all_patterns()
        whale_score = self.detector.get_whale_score()
        
        return {
            'whale_score': whale_score,
            'alerts_count': len(alerts),
            'alerts': [
                {
                    'pattern': a.pattern.value,
                    'confidence': a.confidence,
                    'severity': a.severity,
                    'description': a.description
                }
                for a in alerts[:3]  # Top 3 alerts
            ],
            'recommendation': self.detector.get_recommendation()
        }


# Example usage
if __name__ == "__main__":
    system = WhaleProtectionSystem()
    
    # Simulate some candles
    test_candles = [
        (100, 102, 99, 101, 1000),
        (101, 103, 100, 102, 1100),
        (102, 105, 101, 103, 1200),
        (103, 110, 102, 104, 3000),  # Volume spike
        (104, 108, 103, 103.5, 2500),  # Pullback
        (103.5, 104, 102, 102.5, 1300),
    ]
    
    for candle in test_candles:
        system.add_candle(*candle)
    
    # Get analysis
    status = system.get_status()
    print(f"\n🐋 Whale Activity Score: {status['whale_score']:.0f}/100")
    print(f"⚠️ Alerts: {status['alerts_count']}")
    print(f"\n{status['recommendation']}")
    
    # Check entry
    can_enter, reason = system.should_enter_trade('BTC/USDT', 'LONG')
    print(f"\n📊 Can enter LONG: {can_enter}")
    print(f"   Reason: {reason}")
    
    # Adjust stop loss
    sl = system.adjust_stop_loss(104, 'LONG')
    print(f"\n🛡️ Recommended SL: {sl:.2f}")
