"""
Market Indicators Engine
محرك مؤشرات الأسواق المتقدم
Detects crashes, pumps, recessions, and altseason patterns
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MarketCondition(Enum):
    """Market conditions"""
    CRASH = "Crash"              # انهيار
    PUMP = "Pump"                # ضخ سيولة
    RECESSION = "Recession"      # ركود
    ALTSEASON = "Altseason"      # موسم العملات البديلة
    NORMAL = "Normal"            # عادي
    RECOVERY = "Recovery"        # تعافي


class IndicatorSeverity(Enum):
    """Indicator severity levels"""
    CRITICAL = "Critical"        # حرج
    HIGH = "High"                # عالي
    MEDIUM = "Medium"            # متوسط
    LOW = "Low"                  # منخفض
    NONE = "None"                # لا يوجد


@dataclass
class MarketIndicator:
    """Market indicator data"""
    name: str
    value: float                 # Current value
    threshold: float             # Threshold for alert
    severity: IndicatorSeverity
    description: str
    recommendation: str
    confidence: float            # 0-1


@dataclass
class CrashSignal:
    """Crash detection signal"""
    severity: IndicatorSeverity
    indicators: List[MarketIndicator]
    probability: float           # 0-1
    recommendation: str
    affected_pairs: List[str]
    time_to_crash: Optional[str] = None


@dataclass
class PumpSignal:
    """Pump detection signal"""
    severity: IndicatorSeverity
    indicators: List[MarketIndicator]
    probability: float           # 0-1
    pump_strength: float         # 0-100
    recommendation: str
    affected_pairs: List[str]


@dataclass
class RecessionSignal:
    """Recession detection signal"""
    severity: IndicatorSeverity
    indicators: List[MarketIndicator]
    probability: float           # 0-1
    duration_estimate: str       # Estimated duration
    recommendation: str
    affected_sectors: List[str]


@dataclass
class AltseasoSignal:
    """Altseason detection signal"""
    severity: IndicatorSeverity
    indicators: List[MarketIndicator]
    probability: float           # 0-1
    altseason_strength: float    # 0-100
    top_alts: List[str]          # Best performing alts
    recommendation: str


class CrashDetector:
    """Detects crash signals"""
    
    def __init__(self):
        """Initialize crash detector"""
        self.crash_indicators = []
    
    def detect_crash(self, market_data: Dict) -> CrashSignal:
        """
        Detect crash signals using multiple indicators
        
        Indicators:
        1. Extreme volatility spike (VIX > 30)
        2. Rapid price decline (> 10% in 1 hour)
        3. Volume spike (> 3x average)
        4. RSI extreme (< 20)
        5. MACD bearish crossover
        6. Support level break
        7. Funding rate extreme negative
        8. Long liquidation cascade
        9. Fear index spike
        10. Correlation increase (all assets falling together)
        """
        indicators = []
        severity_scores = []
        
        # 1. Volatility Spike
        volatility = market_data.get('volatility', 0)
        if volatility > 0.15:  # 15% volatility
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(1.0)
            indicators.append(MarketIndicator(
                name="Volatility Spike",
                value=volatility,
                threshold=0.15,
                severity=severity,
                description=f"تذبذب شديد جداً: {volatility*100:.1f}%",
                recommendation="🚫 تجنب التداول فوراً",
                confidence=0.95
            ))
        elif volatility > 0.10:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.7)
            indicators.append(MarketIndicator(
                name="Volatility Spike",
                value=volatility,
                threshold=0.10,
                severity=severity,
                description=f"تذبذب عالي: {volatility*100:.1f}%",
                recommendation="⚠️ كن حذراً جداً",
                confidence=0.85
            ))
        
        # 2. Rapid Price Decline
        price_decline = market_data.get('price_decline_1h', 0)
        if price_decline > 0.15:  # 15% decline in 1 hour
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(1.0)
            indicators.append(MarketIndicator(
                name="Rapid Price Decline",
                value=price_decline,
                threshold=0.15,
                severity=severity,
                description=f"انخفاض سريع: {price_decline*100:.1f}% في ساعة",
                recommendation="🚫 انهيار وشيك!",
                confidence=0.98
            ))
        elif price_decline > 0.08:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.8)
            indicators.append(MarketIndicator(
                name="Rapid Price Decline",
                value=price_decline,
                threshold=0.08,
                severity=severity,
                description=f"انخفاض سريع: {price_decline*100:.1f}%",
                recommendation="⚠️ احذر من الانهيار",
                confidence=0.90
            ))
        
        # 3. Volume Spike
        volume_ratio = market_data.get('volume_ratio', 1)
        if volume_ratio > 4:  # 4x average volume
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Volume Spike",
                value=volume_ratio,
                threshold=4,
                severity=severity,
                description=f"ارتفاع حجم: {volume_ratio:.1f}x المتوسط",
                recommendation="⚠️ بيع ضخم قادم",
                confidence=0.85
            ))
        
        # 4. RSI Extreme
        rsi = market_data.get('rsi', 50)
        if rsi < 20:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="RSI Extreme",
                value=rsi,
                threshold=20,
                severity=severity,
                description=f"RSI منخفض جداً: {rsi:.0f}",
                recommendation="⚠️ بيع مفرط",
                confidence=0.80
            ))
        
        # 5. MACD Bearish Crossover
        macd_bearish = market_data.get('macd_bearish', False)
        if macd_bearish:
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.60)
            indicators.append(MarketIndicator(
                name="MACD Bearish",
                value=1,
                threshold=0,
                severity=severity,
                description="MACD قطع هبوطي",
                recommendation="⚠️ إشارة هبوطية",
                confidence=0.75
            ))
        
        # 6. Support Level Break
        support_broken = market_data.get('support_broken', False)
        if support_broken:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Support Break",
                value=1,
                threshold=0,
                severity=severity,
                description="كسر مستوى الدعم الرئيسي",
                recommendation="🚫 خطر شديد!",
                confidence=0.90
            ))
        
        # 7. Funding Rate Extreme
        funding_rate = market_data.get('funding_rate', 0)
        if funding_rate < -0.02:  # -2% funding rate
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Funding Rate",
                value=funding_rate,
                threshold=-0.02,
                severity=severity,
                description=f"معدل تمويل سالب: {funding_rate*100:.2f}%",
                recommendation="⚠️ تصفية العقود الطويلة",
                confidence=0.85
            ))
        
        # 8. Long Liquidation
        liquidations = market_data.get('long_liquidations', 0)
        if liquidations > 500000000:  # $500M liquidations
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.95)
            indicators.append(MarketIndicator(
                name="Long Liquidations",
                value=liquidations,
                threshold=500000000,
                severity=severity,
                description=f"تصفيات طويلة: ${liquidations/1e6:.0f}M",
                recommendation="🚫 انهيار وشيك جداً!",
                confidence=0.98
            ))
        
        # 9. Fear Index Spike
        fear_index = market_data.get('fear_index', 50)
        if fear_index < 25:  # Extreme fear
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="Fear Index",
                value=fear_index,
                threshold=25,
                severity=severity,
                description=f"مؤشر الخوف: {fear_index:.0f} (خوف شديد)",
                recommendation="⚠️ خوف شديد في السوق",
                confidence=0.80
            ))
        
        # 10. Correlation Increase
        correlation = market_data.get('correlation', 0.5)
        if correlation > 0.85:  # High correlation
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.65)
            indicators.append(MarketIndicator(
                name="Correlation",
                value=correlation,
                threshold=0.85,
                severity=severity,
                description=f"ارتباط عالي: {correlation:.2f}",
                recommendation="⚠️ جميع الأصول تنخفض معاً",
                confidence=0.75
            ))
        
        # Calculate overall probability
        if severity_scores:
            probability = np.mean(severity_scores)
        else:
            probability = 0.0
        
        # Determine overall severity
        if probability > 0.85:
            overall_severity = IndicatorSeverity.CRITICAL
            recommendation = "🚫 احتمال انهيار عالي جداً! تجنب التداول فوراً"
        elif probability > 0.70:
            overall_severity = IndicatorSeverity.HIGH
            recommendation = "⚠️ احتمال انهيار عالي. كن حذراً جداً"
        elif probability > 0.50:
            overall_severity = IndicatorSeverity.MEDIUM
            recommendation = "⚠️ احتمال انهيار متوسط. انتظر تأكيد"
        else:
            overall_severity = IndicatorSeverity.LOW
            recommendation = "✅ احتمال انهيار منخفض"
        
        return CrashSignal(
            severity=overall_severity,
            indicators=indicators,
            probability=probability,
            recommendation=recommendation,
            affected_pairs=['BTC/USDT', 'ETH/USDT', 'EURUSD', 'GBPUSD'],
            time_to_crash="دقائق إلى ساعات" if probability > 0.80 else "ساعات إلى أيام"
        )


class PumpDetector:
    """Detects pump signals"""
    
    def __init__(self):
        """Initialize pump detector"""
        self.pump_indicators = []
    
    def detect_pump(self, market_data: Dict) -> PumpSignal:
        """
        Detect pump signals
        
        Indicators:
        1. Extreme positive momentum
        2. Rapid price increase (> 10% in 1 hour)
        3. Volume spike on upside
        4. RSI extreme (> 80)
        5. MACD bullish crossover
        6. Resistance level break
        7. Funding rate extreme positive
        8. Short liquidation cascade
        9. Greed index spike
        10. Retail FOMO signals
        """
        indicators = []
        severity_scores = []
        
        # 1. Positive Momentum
        momentum = market_data.get('momentum', 0)
        if momentum > 0.15:  # 15% positive momentum
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Positive Momentum",
                value=momentum,
                threshold=0.15,
                severity=severity,
                description=f"زخم إيجابي قوي: {momentum*100:.1f}%",
                recommendation="🟢 ضخ سيولة قادم",
                confidence=0.85
            ))
        
        # 2. Rapid Price Increase
        price_increase = market_data.get('price_increase_1h', 0)
        if price_increase > 0.15:  # 15% increase in 1 hour
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.95)
            indicators.append(MarketIndicator(
                name="Rapid Price Increase",
                value=price_increase,
                threshold=0.15,
                severity=severity,
                description=f"ارتفاع سريع: {price_increase*100:.1f}% في ساعة",
                recommendation="🚫 احذر من الذروة!",
                confidence=0.98
            ))
        elif price_increase > 0.08:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Rapid Price Increase",
                value=price_increase,
                threshold=0.08,
                severity=severity,
                description=f"ارتفاع سريع: {price_increase*100:.1f}%",
                recommendation="⚠️ احذر من الانعكاس",
                confidence=0.90
            ))
        
        # 3. Volume Spike on Upside
        volume_ratio = market_data.get('volume_ratio', 1)
        if volume_ratio > 3:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Volume Spike",
                value=volume_ratio,
                threshold=3,
                severity=severity,
                description=f"ارتفاع حجم: {volume_ratio:.1f}x المتوسط",
                recommendation="⚠️ شراء ضخم",
                confidence=0.85
            ))
        
        # 4. RSI Extreme
        rsi = market_data.get('rsi', 50)
        if rsi > 80:
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="RSI Extreme",
                value=rsi,
                threshold=80,
                severity=severity,
                description=f"RSI مرتفع جداً: {rsi:.0f}",
                recommendation="⚠️ شراء مفرط",
                confidence=0.80
            ))
        
        # 5. MACD Bullish Crossover
        macd_bullish = market_data.get('macd_bullish', False)
        if macd_bullish:
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.65)
            indicators.append(MarketIndicator(
                name="MACD Bullish",
                value=1,
                threshold=0,
                severity=severity,
                description="MACD قطع صعودي",
                recommendation="🟢 إشارة صعودية",
                confidence=0.75
            ))
        
        # 6. Resistance Break
        resistance_broken = market_data.get('resistance_broken', False)
        if resistance_broken:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Resistance Break",
                value=1,
                threshold=0,
                severity=severity,
                description="كسر مستوى المقاومة الرئيسي",
                recommendation="🟢 إشارة قوية",
                confidence=0.90
            ))
        
        # 7. Funding Rate Extreme Positive
        funding_rate = market_data.get('funding_rate', 0)
        if funding_rate > 0.02:  # +2% funding rate
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Funding Rate",
                value=funding_rate,
                threshold=0.02,
                severity=severity,
                description=f"معدل تمويل موجب: {funding_rate*100:.2f}%",
                recommendation="⚠️ تصفية العقود القصيرة",
                confidence=0.85
            ))
        
        # 8. Short Liquidation
        liquidations = market_data.get('short_liquidations', 0)
        if liquidations > 300000000:  # $300M liquidations
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.90)
            indicators.append(MarketIndicator(
                name="Short Liquidations",
                value=liquidations,
                threshold=300000000,
                severity=severity,
                description=f"تصفيات قصيرة: ${liquidations/1e6:.0f}M",
                recommendation="🚀 ضخ سيولة قوي!",
                confidence=0.95
            ))
        
        # 9. Greed Index Spike
        greed_index = market_data.get('greed_index', 50)
        if greed_index > 75:  # Extreme greed
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="Greed Index",
                value=greed_index,
                threshold=75,
                severity=severity,
                description=f"مؤشر الطمع: {greed_index:.0f} (طمع شديد)",
                recommendation="⚠️ احذر من الذروة",
                confidence=0.80
            ))
        
        # 10. Retail FOMO
        retail_fomo = market_data.get('retail_fomo', 0)
        if retail_fomo > 0.7:
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.65)
            indicators.append(MarketIndicator(
                name="Retail FOMO",
                value=retail_fomo,
                threshold=0.7,
                severity=severity,
                description=f"FOMO الأفراد: {retail_fomo*100:.0f}%",
                recommendation="⚠️ شراء من الأفراد",
                confidence=0.75
            ))
        
        # Calculate overall probability
        if severity_scores:
            probability = np.mean(severity_scores)
            pump_strength = probability * 100
        else:
            probability = 0.0
            pump_strength = 0.0
        
        # Determine overall severity
        if probability > 0.85:
            overall_severity = IndicatorSeverity.CRITICAL
            recommendation = "🚀 احتمال ضخ سيولة عالي جداً!"
        elif probability > 0.70:
            overall_severity = IndicatorSeverity.HIGH
            recommendation = "🟢 احتمال ضخ سيولة عالي"
        elif probability > 0.50:
            overall_severity = IndicatorSeverity.MEDIUM
            recommendation = "🟡 احتمال ضخ سيولة متوسط"
        else:
            overall_severity = IndicatorSeverity.LOW
            recommendation = "✅ احتمال ضخ سيولة منخفض"
        
        return PumpSignal(
            severity=overall_severity,
            indicators=indicators,
            probability=probability,
            pump_strength=pump_strength,
            recommendation=recommendation,
            affected_pairs=['BTC/USDT', 'ETH/USDT', 'Top Altcoins']
        )


class RecessionDetector:
    """Detects recession signals"""
    
    def __init__(self):
        """Initialize recession detector"""
        self.recession_indicators = []
    
    def detect_recession(self, market_data: Dict) -> RecessionSignal:
        """
        Detect recession signals
        
        Indicators:
        1. GDP decline
        2. Unemployment increase
        3. Yield curve inversion
        4. Consumer confidence decline
        5. Manufacturing PMI < 50
        6. Credit spreads widening
        7. Corporate earnings decline
        8. Real estate slowdown
        9. Inflation persistence
        10. Central bank hawkish signals
        """
        indicators = []
        severity_scores = []
        
        # 1. GDP Decline
        gdp_growth = market_data.get('gdp_growth', 0)
        if gdp_growth < 0:
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.90)
            indicators.append(MarketIndicator(
                name="GDP Decline",
                value=gdp_growth,
                threshold=0,
                severity=severity,
                description=f"انخفاض الناتج المحلي: {gdp_growth:.2f}%",
                recommendation="🚫 ركود اقتصادي!",
                confidence=0.95
            ))
        elif gdp_growth < 0.5:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="GDP Slowdown",
                value=gdp_growth,
                threshold=0.5,
                severity=severity,
                description=f"تباطؤ النمو: {gdp_growth:.2f}%",
                recommendation="⚠️ نمو ضعيف",
                confidence=0.85
            ))
        
        # 2. Unemployment Increase
        unemployment_change = market_data.get('unemployment_change', 0)
        if unemployment_change > 0.5:  # +0.5% unemployment
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Unemployment Rise",
                value=unemployment_change,
                threshold=0.5,
                severity=severity,
                description=f"ارتفاع البطالة: +{unemployment_change:.1f}%",
                recommendation="⚠️ تدهور سوق العمل",
                confidence=0.85
            ))
        
        # 3. Yield Curve Inversion
        yield_inversion = market_data.get('yield_inversion', False)
        if yield_inversion:
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.95)
            indicators.append(MarketIndicator(
                name="Yield Curve Inversion",
                value=1,
                threshold=0,
                severity=severity,
                description="انقلاب منحنى العائد",
                recommendation="🚫 مؤشر ركود قوي!",
                confidence=0.98
            ))
        
        # 4. Consumer Confidence Decline
        confidence_decline = market_data.get('confidence_decline', 0)
        if confidence_decline > 10:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Confidence Decline",
                value=confidence_decline,
                threshold=10,
                severity=severity,
                description=f"انخفاض ثقة المستهلك: -{confidence_decline:.1f}",
                recommendation="⚠️ تشاؤم المستهلكين",
                confidence=0.80
            ))
        
        # 5. Manufacturing PMI
        pmi = market_data.get('pmi', 50)
        if pmi < 45:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Manufacturing PMI",
                value=pmi,
                threshold=45,
                severity=severity,
                description=f"PMI التصنيع: {pmi:.0f}",
                recommendation="⚠️ تقلص التصنيع",
                confidence=0.85
            ))
        elif pmi < 50:
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.60)
            indicators.append(MarketIndicator(
                name="Manufacturing PMI",
                value=pmi,
                threshold=50,
                severity=severity,
                description=f"PMI التصنيع: {pmi:.0f}",
                recommendation="⚠️ تباطؤ التصنيع",
                confidence=0.75
            ))
        
        # 6. Credit Spreads Widening
        credit_spread = market_data.get('credit_spread', 1)
        if credit_spread > 2.5:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Credit Spreads",
                value=credit_spread,
                threshold=2.5,
                severity=severity,
                description=f"فروقات الائتمان: {credit_spread:.2f}%",
                recommendation="⚠️ خطر ائتماني",
                confidence=0.80
            ))
        
        # 7. Earnings Decline
        earnings_decline = market_data.get('earnings_decline', 0)
        if earnings_decline > 10:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Earnings Decline",
                value=earnings_decline,
                threshold=10,
                severity=severity,
                description=f"انخفاض الأرباح: -{earnings_decline:.1f}%",
                recommendation="⚠️ أرباح ضعيفة",
                confidence=0.80
            ))
        
        # Calculate overall probability
        if severity_scores:
            probability = np.mean(severity_scores)
        else:
            probability = 0.0
        
        # Determine overall severity and duration
        if probability > 0.85:
            overall_severity = IndicatorSeverity.CRITICAL
            duration = "6-12 شهر"
            recommendation = "🚫 احتمال ركود عالي جداً!"
        elif probability > 0.70:
            overall_severity = IndicatorSeverity.HIGH
            duration = "3-6 أشهر"
            recommendation = "⚠️ احتمال ركود عالي"
        elif probability > 0.50:
            overall_severity = IndicatorSeverity.MEDIUM
            duration = "1-3 أشهر"
            recommendation = "⚠️ احتمال ركود متوسط"
        else:
            overall_severity = IndicatorSeverity.LOW
            duration = "غير متوقع"
            recommendation = "✅ احتمال ركود منخفض"
        
        return RecessionSignal(
            severity=overall_severity,
            indicators=indicators,
            probability=probability,
            duration_estimate=duration,
            recommendation=recommendation,
            affected_sectors=['Finance', 'Technology', 'Consumer', 'Energy']
        )


class AltseasoDetector:
    """Detects altseason signals"""
    
    def __init__(self):
        """Initialize altseason detector"""
        self.altseason_indicators = []
    
    def detect_altseason(self, market_data: Dict) -> AltseasoSignal:
        """
        Detect altseason signals
        
        Indicators:
        1. BTC dominance decline
        2. Altcoin outperformance
        3. Altcoin volume increase
        4. Altcoin market cap growth
        5. New altcoin listings
        6. DeFi TVL increase
        7. NFT activity spike
        8. Layer 2 adoption
        9. Stablecoin supply increase
        10. Retail participation increase
        """
        indicators = []
        severity_scores = []
        
        # 1. BTC Dominance Decline
        btc_dominance = market_data.get('btc_dominance', 50)
        if btc_dominance < 40:
            severity = IndicatorSeverity.CRITICAL
            severity_scores.append(0.95)
            indicators.append(MarketIndicator(
                name="BTC Dominance",
                value=btc_dominance,
                threshold=40,
                severity=severity,
                description=f"هيمنة البيتكوين: {btc_dominance:.1f}%",
                recommendation="🚀 موسم العملات البديلة!",
                confidence=0.98
            ))
        elif btc_dominance < 45:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="BTC Dominance",
                value=btc_dominance,
                threshold=45,
                severity=severity,
                description=f"هيمنة البيتكوين: {btc_dominance:.1f}%",
                recommendation="🟢 موسم العملات البديلة قادم",
                confidence=0.85
            ))
        
        # 2. Altcoin Outperformance
        altcoin_performance = market_data.get('altcoin_performance', 0)
        if altcoin_performance > 0.20:  # 20% outperformance
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.85)
            indicators.append(MarketIndicator(
                name="Altcoin Performance",
                value=altcoin_performance,
                threshold=0.20,
                severity=severity,
                description=f"تفوق العملات البديلة: +{altcoin_performance*100:.1f}%",
                recommendation="🚀 العملات البديلة تتفوق",
                confidence=0.90
            ))
        
        # 3. Altcoin Volume Increase
        altcoin_volume_ratio = market_data.get('altcoin_volume_ratio', 1)
        if altcoin_volume_ratio > 1.5:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Altcoin Volume",
                value=altcoin_volume_ratio,
                threshold=1.5,
                severity=severity,
                description=f"حجم العملات البديلة: {altcoin_volume_ratio:.1f}x",
                recommendation="🟢 نشاط عالي في العملات البديلة",
                confidence=0.85
            ))
        
        # 4. Altcoin Market Cap Growth
        altcoin_cap_growth = market_data.get('altcoin_cap_growth', 0)
        if altcoin_cap_growth > 0.15:  # 15% growth
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Altcoin Market Cap",
                value=altcoin_cap_growth,
                threshold=0.15,
                severity=severity,
                description=f"نمو القيمة السوقية: +{altcoin_cap_growth*100:.1f}%",
                recommendation="🚀 نمو قوي في العملات البديلة",
                confidence=0.85
            ))
        
        # 5. New Altcoin Listings
        new_listings = market_data.get('new_listings', 0)
        if new_listings > 50:  # 50+ new listings
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="New Listings",
                value=new_listings,
                threshold=50,
                severity=severity,
                description=f"عملات جديدة: {new_listings:.0f}",
                recommendation="🟡 نشاط عالي في الإدراجات",
                confidence=0.75
            ))
        
        # 6. DeFi TVL Increase
        defi_tvl_growth = market_data.get('defi_tvl_growth', 0)
        if defi_tvl_growth > 0.20:  # 20% growth
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="DeFi TVL",
                value=defi_tvl_growth,
                threshold=0.20,
                severity=severity,
                description=f"نمو DeFi: +{defi_tvl_growth*100:.1f}%",
                recommendation="🚀 نشاط DeFi قوي",
                confidence=0.85
            ))
        
        # 7. NFT Activity Spike
        nft_volume = market_data.get('nft_volume', 0)
        if nft_volume > 500000000:  # $500M volume
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="NFT Volume",
                value=nft_volume,
                threshold=500000000,
                severity=severity,
                description=f"حجم NFT: ${nft_volume/1e6:.0f}M",
                recommendation="🟡 نشاط NFT مرتفع",
                confidence=0.75
            ))
        
        # 8. Layer 2 Adoption
        l2_adoption = market_data.get('l2_adoption', 0)
        if l2_adoption > 0.30:  # 30% adoption
            severity = IndicatorSeverity.MEDIUM
            severity_scores.append(0.70)
            indicators.append(MarketIndicator(
                name="Layer 2 Adoption",
                value=l2_adoption,
                threshold=0.30,
                severity=severity,
                description=f"تبني Layer 2: {l2_adoption*100:.0f}%",
                recommendation="🟢 نمو البنية التحتية",
                confidence=0.75
            ))
        
        # 9. Stablecoin Supply Increase
        stablecoin_growth = market_data.get('stablecoin_growth', 0)
        if stablecoin_growth > 0.15:  # 15% growth
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.75)
            indicators.append(MarketIndicator(
                name="Stablecoin Supply",
                value=stablecoin_growth,
                threshold=0.15,
                severity=severity,
                description=f"نمو العملات المستقرة: +{stablecoin_growth*100:.1f}%",
                recommendation="🚀 سيولة جديدة في السوق",
                confidence=0.85
            ))
        
        # 10. Retail Participation
        retail_participation = market_data.get('retail_participation', 0)
        if retail_participation > 0.70:
            severity = IndicatorSeverity.HIGH
            severity_scores.append(0.80)
            indicators.append(MarketIndicator(
                name="Retail Participation",
                value=retail_participation,
                threshold=0.70,
                severity=severity,
                description=f"مشاركة الأفراد: {retail_participation*100:.0f}%",
                recommendation="🟢 نشاط عالي من الأفراد",
                confidence=0.85
            ))
        
        # Calculate overall probability
        if severity_scores:
            probability = np.mean(severity_scores)
            altseason_strength = probability * 100
        else:
            probability = 0.0
            altseason_strength = 0.0
        
        # Top performing alts
        top_alts = market_data.get('top_alts', ['ETH', 'SOL', 'AVAX', 'MATIC', 'ARB'])
        
        # Determine overall severity
        if probability > 0.85:
            overall_severity = IndicatorSeverity.CRITICAL
            recommendation = "🚀 موسم العملات البديلة قوي جداً!"
        elif probability > 0.70:
            overall_severity = IndicatorSeverity.HIGH
            recommendation = "🟢 موسم العملات البديلة قوي"
        elif probability > 0.50:
            overall_severity = IndicatorSeverity.MEDIUM
            recommendation = "🟡 موسم العملات البديلة متوسط"
        else:
            overall_severity = IndicatorSeverity.LOW
            recommendation = "✅ موسم العملات البديلة ضعيف"
        
        return AltseasoSignal(
            severity=overall_severity,
            indicators=indicators,
            probability=probability,
            altseason_strength=altseason_strength,
            top_alts=top_alts,
            recommendation=recommendation
        )


class MarketIndicatorsEngine:
    """Main market indicators engine"""
    
    def __init__(self):
        """Initialize market indicators engine"""
        self.crash_detector = CrashDetector()
        self.pump_detector = PumpDetector()
        self.recession_detector = RecessionDetector()
        self.altseason_detector = AltseasoDetector()
        self.current_condition = MarketCondition.NORMAL
    
    def analyze_all_indicators(self, market_data: Dict) -> Dict:
        """Analyze all market indicators"""
        
        crash_signal = self.crash_detector.detect_crash(market_data)
        pump_signal = self.pump_detector.detect_pump(market_data)
        recession_signal = self.recession_detector.detect_recession(market_data)
        altseason_signal = self.altseason_detector.detect_altseason(market_data)
        
        # Determine market condition
        if crash_signal.probability > 0.80:
            self.current_condition = MarketCondition.CRASH
        elif pump_signal.probability > 0.80:
            self.current_condition = MarketCondition.PUMP
        elif recession_signal.probability > 0.80:
            self.current_condition = MarketCondition.RECESSION
        elif altseason_signal.probability > 0.80:
            self.current_condition = MarketCondition.ALTSEASON
        else:
            self.current_condition = MarketCondition.NORMAL
        
        return {
            'market_condition': self.current_condition.value,
            'crash': {
                'severity': crash_signal.severity.value,
                'probability': crash_signal.probability,
                'indicators_count': len(crash_signal.indicators),
                'recommendation': crash_signal.recommendation,
                'affected_pairs': crash_signal.affected_pairs
            },
            'pump': {
                'severity': pump_signal.severity.value,
                'probability': pump_signal.probability,
                'strength': pump_signal.pump_strength,
                'indicators_count': len(pump_signal.indicators),
                'recommendation': pump_signal.recommendation,
                'affected_pairs': pump_signal.affected_pairs
            },
            'recession': {
                'severity': recession_signal.severity.value,
                'probability': recession_signal.probability,
                'indicators_count': len(recession_signal.indicators),
                'duration': recession_signal.duration_estimate,
                'recommendation': recession_signal.recommendation,
                'affected_sectors': recession_signal.affected_sectors
            },
            'altseason': {
                'severity': altseason_signal.severity.value,
                'probability': altseason_signal.probability,
                'strength': altseason_signal.altseason_strength,
                'indicators_count': len(altseason_signal.indicators),
                'top_alts': altseason_signal.top_alts,
                'recommendation': altseason_signal.recommendation
            }
        }
    
    def get_trading_recommendation(self) -> Dict:
        """Get trading recommendation based on market condition"""
        
        if self.current_condition == MarketCondition.CRASH:
            return {
                'action': 'AVOID',
                'message': '🚫 تجنب التداول! احتمال انهيار عالي',
                'risk_level': 'CRITICAL'
            }
        elif self.current_condition == MarketCondition.PUMP:
            return {
                'action': 'CAUTIOUS',
                'message': '⚠️ كن حذراً! احتمال ضخ سيولة عالي',
                'risk_level': 'HIGH'
            }
        elif self.current_condition == MarketCondition.RECESSION:
            return {
                'action': 'AVOID',
                'message': '🚫 تجنب التداول! احتمال ركود عالي',
                'risk_level': 'CRITICAL'
            }
        elif self.current_condition == MarketCondition.ALTSEASON:
            return {
                'action': 'SELECTIVE',
                'message': '🟢 موسم العملات البديلة! اختر العملات الجيدة',
                'risk_level': 'MEDIUM'
            }
        else:
            return {
                'action': 'NORMAL',
                'message': '✅ السوق عادي. تداول عادي',
                'risk_level': 'LOW'
            }


# Example usage
if __name__ == "__main__":
    engine = MarketIndicatorsEngine()
    
    # Simulate market data
    market_data = {
        'volatility': 0.08,
        'price_decline_1h': 0.05,
        'price_increase_1h': 0.12,
        'volume_ratio': 2.5,
        'rsi': 75,
        'macd_bearish': False,
        'macd_bullish': True,
        'support_broken': False,
        'resistance_broken': True,
        'funding_rate': 0.015,
        'long_liquidations': 200000000,
        'short_liquidations': 400000000,
        'fear_index': 55,
        'greed_index': 72,
        'correlation': 0.65,
        'momentum': 0.12,
        'retail_fomo': 0.65,
        'gdp_growth': 2.5,
        'unemployment_change': -0.1,
        'yield_inversion': False,
        'confidence_decline': -5,
        'pmi': 52,
        'credit_spread': 1.2,
        'earnings_decline': -3,
        'btc_dominance': 42,
        'altcoin_performance': 0.18,
        'altcoin_volume_ratio': 1.4,
        'altcoin_cap_growth': 0.12,
        'new_listings': 45,
        'defi_tvl_growth': 0.18,
        'nft_volume': 400000000,
        'l2_adoption': 0.28,
        'stablecoin_growth': 0.12,
        'retail_participation': 0.68,
        'top_alts': ['ETH', 'SOL', 'AVAX', 'MATIC', 'ARB']
    }
    
    print("\n" + "="*80)
    print("📊 Market Indicators Engine - Test")
    print("="*80)
    
    # Analyze all indicators
    analysis = engine.analyze_all_indicators(market_data)
    
    print(f"\n🎯 Market Condition: {analysis['market_condition']}")
    
    print(f"\n🚫 Crash Signal:")
    print(f"   Severity: {analysis['crash']['severity']}")
    print(f"   Probability: {analysis['crash']['probability']:.0%}")
    print(f"   Indicators: {analysis['crash']['indicators_count']}")
    print(f"   Recommendation: {analysis['crash']['recommendation']}")
    
    print(f"\n🚀 Pump Signal:")
    print(f"   Severity: {analysis['pump']['severity']}")
    print(f"   Probability: {analysis['pump']['probability']:.0%}")
    print(f"   Strength: {analysis['pump']['strength']:.0f}/100")
    print(f"   Indicators: {analysis['pump']['indicators_count']}")
    print(f"   Recommendation: {analysis['pump']['recommendation']}")
    
    print(f"\n📉 Recession Signal:")
    print(f"   Severity: {analysis['recession']['severity']}")
    print(f"   Probability: {analysis['recession']['probability']:.0%}")
    print(f"   Duration: {analysis['recession']['duration']}")
    print(f"   Indicators: {analysis['recession']['indicators_count']}")
    print(f"   Recommendation: {analysis['recession']['recommendation']}")
    
    print(f"\n🟢 Altseason Signal:")
    print(f"   Severity: {analysis['altseason']['severity']}")
    print(f"   Probability: {analysis['altseason']['probability']:.0%}")
    print(f"   Strength: {analysis['altseason']['strength']:.0f}/100")
    print(f"   Indicators: {analysis['altseason']['indicators_count']}")
    print(f"   Top Alts: {', '.join(analysis['altseason']['top_alts'][:3])}")
    print(f"   Recommendation: {analysis['altseason']['recommendation']}")
    
    # Trading recommendation
    rec = engine.get_trading_recommendation()
    print(f"\n💡 Trading Recommendation:")
    print(f"   Action: {rec['action']}")
    print(f"   Message: {rec['message']}")
    print(f"   Risk Level: {rec['risk_level']}")
    
    print("\n" + "="*80)
