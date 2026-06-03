"""
Wick Detection & Avoidance Engine
محرك كشف وتجنب ذيول الشموع المريبة
Detects whale traps and fake breakouts through wick analysis
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class WickDangerLevel(Enum):
    """Danger levels for wick patterns"""
    SAFE = 0           # آمن - يمكن الدخول
    LOW = 1            # منخفض - انتظر تأكيد
    MEDIUM = 2         # متوسط - كن حذراً
    HIGH = 3           # عالي - تجنب
    CRITICAL = 4       # حرج - تجنب تماماً


@dataclass
class WickAnalysis:
    """Wick analysis result"""
    danger_level: WickDangerLevel
    wick_ratio: float           # نسبة الذيل للجسم
    wick_type: str              # نوع الذيل
    confidence: float           # درجة الثقة (0-1)
    is_trap: bool               # هل هذا فخ؟
    recommendation: str         # التوصية
    score: float                # نقاط الخطورة (0-100)


class WickDetectionEngine:
    """Engine for detecting and avoiding wick traps"""
    
    def __init__(self):
        """Initialize the wick detection engine"""
        self.wick_history = []
        self.trap_patterns = []
        self.safe_entry_points = []
        
        # Thresholds
        self.EXTREME_WICK_RATIO = 2.5      # نسبة الذيل الشديدة
        self.HIGH_WICK_RATIO = 2.0         # نسبة الذيل العالية
        self.MEDIUM_WICK_RATIO = 1.5       # نسبة الذيل المتوسطة
        self.NORMAL_WICK_RATIO = 0.8       # نسبة الذيل الطبيعية
        
    def analyze_candle(self, 
                      open_price: float,
                      high_price: float,
                      low_price: float,
                      close_price: float,
                      volume: float,
                      avg_volume: float = None) -> WickAnalysis:
        """
        Analyze a single candle for wick traps
        
        Args:
            open_price: سعر الفتح
            high_price: أعلى سعر
            low_price: أقل سعر
            close_price: سعر الإغلاق
            volume: حجم التداول
            avg_volume: متوسط الحجم
            
        Returns:
            WickAnalysis object with detailed analysis
        """
        
        # Calculate wick lengths
        upper_wick = high_price - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low_price
        body = abs(close_price - open_price)
        
        # Determine candle color
        is_bullish = close_price > open_price
        
        # Calculate wick ratios
        upper_wick_ratio = upper_wick / body if body > 0 else 0
        lower_wick_ratio = lower_wick / body if body > 0 else 0
        total_wick_ratio = (upper_wick + lower_wick) / body if body > 0 else 0
        
        # Analyze wick type
        wick_type = self._identify_wick_type(
            upper_wick, lower_wick, body, is_bullish
        )
        
        # Calculate danger level
        danger_level, danger_score = self._calculate_danger_level(
            upper_wick_ratio, lower_wick_ratio, total_wick_ratio,
            wick_type, volume, avg_volume
        )
        
        # Detect if it's a trap
        is_trap = self._is_trap_pattern(
            upper_wick_ratio, lower_wick_ratio, wick_type, danger_level
        )
        
        # Generate recommendation
        recommendation = self._get_recommendation(
            danger_level, wick_type, is_trap
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            upper_wick_ratio, lower_wick_ratio, volume, avg_volume
        )
        
        analysis = WickAnalysis(
            danger_level=danger_level,
            wick_ratio=total_wick_ratio,
            wick_type=wick_type,
            confidence=confidence,
            is_trap=is_trap,
            recommendation=recommendation,
            score=danger_score
        )
        
        # Store in history
        self.wick_history.append({
            'analysis': analysis,
            'candle': {
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            }
        })
        
        return analysis
    
    def _identify_wick_type(self, upper_wick: float, lower_wick: float, 
                           body: float, is_bullish: bool) -> str:
        """
        Identify the wick pattern type
        
        نوع الذيل:
        - Hammer: ذيل سفلي طويل (فخ بيع)
        - Hanging Man: ذيل سفلي طويل (فخ شراء)
        - Shooting Star: ذيل علوي طويل (فخ شراء)
        - Inverted Hammer: ذيل علوي طويل (فخ بيع)
        - Doji: ذيول متساوية (عدم تأكد)
        - Normal: ذيول طبيعية
        """
        
        if body < 0.0001:  # Doji
            if upper_wick > lower_wick * 1.5:
                return "Doji_Upper"
            elif lower_wick > upper_wick * 1.5:
                return "Doji_Lower"
            else:
                return "Doji_Balanced"
        
        # Check for extreme wicks
        if upper_wick > body * 2:
            return "Shooting_Star" if is_bullish else "Inverted_Hammer"
        
        if lower_wick > body * 2:
            return "Hammer" if is_bullish else "Hanging_Man"
        
        # Check for double wicks
        if upper_wick > body * 1.2 and lower_wick > body * 1.2:
            return "Double_Wick_Trap"
        
        # Normal candles
        if upper_wick > lower_wick * 1.5:
            return "Upper_Wick_Bias"
        elif lower_wick > upper_wick * 1.5:
            return "Lower_Wick_Bias"
        else:
            return "Normal"
    
    def _calculate_danger_level(self, upper_ratio: float, lower_ratio: float,
                               total_ratio: float, wick_type: str,
                               volume: float, avg_volume: float = None) -> Tuple[WickDangerLevel, float]:
        """Calculate danger level based on wick characteristics"""
        
        danger_score = 0
        
        # Wick ratio scoring
        if total_ratio > self.EXTREME_WICK_RATIO:
            danger_score += 40
        elif total_ratio > self.HIGH_WICK_RATIO:
            danger_score += 30
        elif total_ratio > self.MEDIUM_WICK_RATIO:
            danger_score += 20
        elif total_ratio > self.NORMAL_WICK_RATIO:
            danger_score += 10
        
        # Wick type scoring
        trap_types = {
            "Shooting_Star": 25,
            "Inverted_Hammer": 25,
            "Hammer": 20,
            "Hanging_Man": 20,
            "Double_Wick_Trap": 35,
            "Doji_Upper": 15,
            "Doji_Lower": 15,
            "Upper_Wick_Bias": 10,
            "Lower_Wick_Bias": 10,
        }
        
        danger_score += trap_types.get(wick_type, 0)
        
        # Volume scoring
        if avg_volume and volume > avg_volume * 1.5:
            danger_score += 15  # High volume increases danger
        
        # Determine danger level
        if danger_score >= 80:
            return WickDangerLevel.CRITICAL, danger_score
        elif danger_score >= 60:
            return WickDangerLevel.HIGH, danger_score
        elif danger_score >= 40:
            return WickDangerLevel.MEDIUM, danger_score
        elif danger_score >= 20:
            return WickDangerLevel.LOW, danger_score
        else:
            return WickDangerLevel.SAFE, danger_score
    
    def _is_trap_pattern(self, upper_ratio: float, lower_ratio: float,
                        wick_type: str, danger_level: WickDangerLevel) -> bool:
        """Determine if this is a trap pattern"""
        
        # Extreme wick ratios are traps
        if upper_ratio > self.EXTREME_WICK_RATIO or lower_ratio > self.EXTREME_WICK_RATIO:
            return True
        
        # Known trap patterns
        trap_patterns = [
            "Shooting_Star",
            "Inverted_Hammer",
            "Hammer",
            "Hanging_Man",
            "Double_Wick_Trap"
        ]
        
        if wick_type in trap_patterns and danger_level.value >= WickDangerLevel.MEDIUM.value:
            return True
        
        return False
    
    def _get_recommendation(self, danger_level: WickDangerLevel,
                           wick_type: str, is_trap: bool) -> str:
        """Generate trading recommendation"""
        
        if danger_level == WickDangerLevel.CRITICAL:
            return f"🚫 تجنب تماماً! ({wick_type}) - فخ حقيقي جداً"
        
        elif danger_level == WickDangerLevel.HIGH:
            return f"⚠️ كن حذراً! ({wick_type}) - احتمال فخ عالي"
        
        elif danger_level == WickDangerLevel.MEDIUM:
            return f"⏳ انتظر تأكيد! ({wick_type}) - قد يكون فخ"
        
        elif danger_level == WickDangerLevel.LOW:
            return f"✅ آمن نسبياً ({wick_type}) - انتظر تأكيد إضافي"
        
        else:  # SAFE
            return f"✅ آمن جداً ({wick_type}) - يمكن الدخول"
    
    def _calculate_confidence(self, upper_ratio: float, lower_ratio: float,
                             volume: float, avg_volume: float = None) -> float:
        """Calculate confidence level of the analysis (0-1)"""
        
        confidence = 0.5  # Base confidence
        
        # Extreme ratios increase confidence
        if upper_ratio > self.EXTREME_WICK_RATIO or lower_ratio > self.EXTREME_WICK_RATIO:
            confidence += 0.3
        elif upper_ratio > self.HIGH_WICK_RATIO or lower_ratio > self.HIGH_WICK_RATIO:
            confidence += 0.2
        
        # High volume increases confidence
        if avg_volume and volume > avg_volume * 2:
            confidence += 0.1
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def analyze_multi_candle(self, candles: List[Dict]) -> Dict:
        """
        Analyze multiple candles for trap patterns
        
        Args:
            candles: List of candle data dicts
            
        Returns:
            Analysis of the pattern
        """
        
        if len(candles) < 2:
            return {"error": "Need at least 2 candles"}
        
        analyses = []
        for candle in candles:
            analysis = self.analyze_candle(
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume'],
                candle.get('avg_volume')
            )
            analyses.append(analysis)
        
        # Detect trap sequences
        trap_sequence = self._detect_trap_sequence(analyses)
        
        # Calculate overall danger
        avg_danger = sum([a.score for a in analyses]) / len(analyses)
        
        return {
            "analyses": analyses,
            "trap_sequence": trap_sequence,
            "average_danger": avg_danger,
            "recommendation": self._get_multi_candle_recommendation(analyses, trap_sequence)
        }
    
    def _detect_trap_sequence(self, analyses: List[WickAnalysis]) -> str:
        """Detect common trap sequences"""
        
        trap_count = sum([1 for a in analyses if a.is_trap])
        
        if trap_count == len(analyses):
            return "Multiple_Traps_in_a_Row"
        elif trap_count >= len(analyses) * 0.5:
            return "Trap_Sequence"
        else:
            return "No_Sequence"
    
    def _get_multi_candle_recommendation(self, analyses: List[WickAnalysis],
                                        trap_sequence: str) -> str:
        """Get recommendation for multi-candle analysis"""
        
        if trap_sequence == "Multiple_Traps_in_a_Row":
            return "🚫 تسلسل فخاخ متعددة! تجنب الدخول الآن"
        elif trap_sequence == "Trap_Sequence":
            return "⚠️ تسلسل فخاخ! انتظر تأكيد قوي"
        else:
            latest = analyses[-1]
            if latest.danger_level.value >= WickDangerLevel.MEDIUM.value:
                return "⏳ انتظر تأكيد إضافي قبل الدخول"
            else:
                return "✅ يمكن الدخول بحذر"
    
    def should_enter_trade(self, analysis: WickAnalysis, 
                          confirmation_candle: Optional[WickAnalysis] = None) -> bool:
        """
        Determine if it's safe to enter a trade
        
        Args:
            analysis: Current candle analysis
            confirmation_candle: Optional confirmation candle
            
        Returns:
            True if safe to enter, False otherwise
        """
        
        # Never enter on critical danger
        if analysis.danger_level == WickDangerLevel.CRITICAL:
            return False
        
        # High danger needs confirmation
        if analysis.danger_level == WickDangerLevel.HIGH:
            if confirmation_candle is None:
                return False
            # Confirmation must be safe
            return confirmation_candle.danger_level.value <= WickDangerLevel.LOW.value
        
        # Medium danger needs confirmation
        if analysis.danger_level == WickDangerLevel.MEDIUM:
            if confirmation_candle is None:
                return False
            # Confirmation must be safe
            return confirmation_candle.danger_level.value <= WickDangerLevel.LOW.value
        
        # Low danger is okay
        if analysis.danger_level == WickDangerLevel.LOW:
            return True
        
        # Safe is always okay
        return True
    
    def get_safe_entry_points(self, candles: List[Dict], 
                             lookback: int = 10) -> List[Dict]:
        """
        Get safe entry points by avoiding wick traps
        
        Args:
            candles: List of recent candles
            lookback: Number of candles to analyze
            
        Returns:
            List of safe entry points
        """
        
        safe_points = []
        
        for i in range(len(candles) - 1):
            current = candles[i]
            next_candle = candles[i + 1] if i + 1 < len(candles) else None
            
            analysis = self.analyze_candle(
                current['open'],
                current['high'],
                current['low'],
                current['close'],
                current['volume'],
                current.get('avg_volume')
            )
            
            confirmation = None
            if next_candle:
                confirmation = self.analyze_candle(
                    next_candle['open'],
                    next_candle['high'],
                    next_candle['low'],
                    next_candle['close'],
                    next_candle['volume'],
                    next_candle.get('avg_volume')
                )
            
            if self.should_enter_trade(analysis, confirmation):
                safe_points.append({
                    'candle_index': i,
                    'price': current['close'],
                    'analysis': analysis,
                    'confirmation': confirmation,
                    'safety_score': 100 - analysis.score
                })
        
        # Sort by safety score
        safe_points.sort(key=lambda x: x['safety_score'], reverse=True)
        
        return safe_points[:lookback]


# Example usage
if __name__ == "__main__":
    engine = WickDetectionEngine()
    
    # Test candles
    test_candles = [
        {
            'open': 100,
            'high': 102,
            'low': 98,
            'close': 99,
            'volume': 1000,
            'avg_volume': 800
        },
        {
            'open': 99,
            'high': 105,
            'low': 98,
            'close': 100,
            'volume': 1200,
            'avg_volume': 800
        },
        {
            'open': 100,
            'high': 101,
            'low': 95,
            'close': 96,
            'volume': 1500,
            'avg_volume': 800
        }
    ]
    
    # Analyze
    for i, candle in enumerate(test_candles):
        analysis = engine.analyze_candle(
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['volume'],
            candle['avg_volume']
        )
        
        print(f"\nCandle {i+1}:")
        print(f"  Wick Type: {analysis.wick_type}")
        print(f"  Danger Level: {analysis.danger_level.name}")
        print(f"  Danger Score: {analysis.score}")
        print(f"  Is Trap: {analysis.is_trap}")
        print(f"  Recommendation: {analysis.recommendation}")
        print(f"  Confidence: {analysis.confidence:.2f}")
    
    # Multi-candle analysis
    print("\n\nMulti-Candle Analysis:")
    result = engine.analyze_multi_candle(test_candles)
    print(f"Average Danger: {result['average_danger']:.2f}")
    print(f"Trap Sequence: {result['trap_sequence']}")
    print(f"Recommendation: {result['recommendation']}")
