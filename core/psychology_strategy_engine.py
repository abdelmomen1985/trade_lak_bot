"""
Psychology Strategy Engine
محرك استراتيجيات نفسية متقدم
Implements Fear & Greed strategies with intelligent learning
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)


class MarketSentiment(Enum):
    """Market sentiment levels"""
    EXTREME_FEAR = "Extreme Fear"        # خوف شديد جداً
    FEAR = "Fear"                        # خوف
    NEUTRAL = "Neutral"                  # محايد
    GREED = "Greed"                      # طمع
    EXTREME_GREED = "Extreme Greed"      # طمع شديد جداً


class LiquidityLevel(Enum):
    """Liquidity levels"""
    VERY_HIGH = "Very High"              # عالية جداً
    HIGH = "High"                        # عالية
    NORMAL = "Normal"                    # عادية
    LOW = "Low"                          # منخفضة
    VERY_LOW = "Very Low"                # منخفضة جداً


@dataclass
class PsychologySignal:
    """Psychology-based trading signal"""
    sentiment: MarketSentiment
    sentiment_score: float              # -100 (extreme fear) to +100 (extreme greed)
    confidence: float                   # 0-1
    recommendation: str
    action: str                         # BUY, SELL, HOLD
    strength: str                       # WEAK, MEDIUM, STRONG
    reason: str


@dataclass
class LiquidityAlert:
    """Alert for liquidity issues"""
    level: LiquidityLevel
    score: float                        # 0-100
    risk_level: str                     # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    recommendation: str
    affected_pairs: List[str]
    time_period: str


@dataclass
class HistoricalLoss:
    """Historical loss pattern"""
    time_period: str                    # e.g., "Friday", "Weekend", "Holiday"
    average_loss_pct: float
    frequency: int                      # times occurred
    confidence: float                   # 0-1
    recommendation: str


class FearGreedAnalyzer:
    """Analyzes market fear and greed psychology"""
    
    def __init__(self):
        """Initialize Fear & Greed analyzer"""
        self.history = []
        self.sentiment_history = defaultdict(list)
        
        # Fear & Greed thresholds
        self.EXTREME_FEAR_THRESHOLD = -80
        self.FEAR_THRESHOLD = -40
        self.GREED_THRESHOLD = 40
        self.EXTREME_GREED_THRESHOLD = 80
    
    def calculate_sentiment_score(self, market_data: Dict) -> float:
        """
        Calculate market sentiment score (-100 to +100)
        
        Factors:
        - Price momentum
        - Volume analysis
        - Volatility
        - RSI levels
        - Market structure
        """
        score = 0
        weights = {}
        
        try:
            # 1. Price Momentum (30%)
            if 'price_change_24h' in market_data:
                momentum = market_data['price_change_24h']
                # -100% to +100% → -30 to +30
                momentum_score = np.clip(momentum / 3.33, -30, 30)
                score += momentum_score
                weights['momentum'] = 0.30
            
            # 2. Volume Analysis (25%)
            if 'volume_change' in market_data:
                vol_change = market_data['volume_change']
                # High volume in uptrend = greed, high volume in downtrend = fear
                if momentum > 0:
                    volume_score = np.clip(vol_change / 2, -25, 25)
                else:
                    volume_score = -np.clip(vol_change / 2, -25, 25)
                score += volume_score
                weights['volume'] = 0.25
            
            # 3. Volatility (20%)
            if 'volatility' in market_data:
                volatility = market_data['volatility']
                # High volatility = fear, low volatility = greed
                if volatility > 0.05:
                    volatility_score = -np.clip((volatility - 0.05) * 200, -20, 20)
                else:
                    volatility_score = np.clip((0.05 - volatility) * 200, -20, 20)
                score += volatility_score
                weights['volatility'] = 0.20
            
            # 4. RSI Levels (15%)
            if 'rsi' in market_data:
                rsi = market_data['rsi']
                # RSI > 70 = greed, RSI < 30 = fear
                if rsi > 70:
                    rsi_score = (rsi - 70) * 1.5  # Up to +15
                elif rsi < 30:
                    rsi_score = (rsi - 30) * 1.5  # Down to -15
                else:
                    rsi_score = 0
                score += rsi_score
                weights['rsi'] = 0.15
            
            # 5. Market Structure (10%)
            if 'higher_highs' in market_data and 'higher_lows' in market_data:
                if market_data['higher_highs'] and market_data['higher_lows']:
                    structure_score = 10  # Uptrend = greed
                elif not market_data['higher_highs'] and not market_data['higher_lows']:
                    structure_score = -10  # Downtrend = fear
                else:
                    structure_score = 0  # Sideways = neutral
                score += structure_score
                weights['structure'] = 0.10
            
            # Normalize to -100 to +100
            score = np.clip(score, -100, 100)
            
            logger.debug(f"Sentiment Score: {score:.1f} | Weights: {weights}")
            
            return score
        
        except Exception as e:
            logger.error(f"Error calculating sentiment: {e}")
            return 0.0
    
    def get_sentiment(self, sentiment_score: float) -> MarketSentiment:
        """Convert sentiment score to sentiment level"""
        if sentiment_score <= self.EXTREME_FEAR_THRESHOLD:
            return MarketSentiment.EXTREME_FEAR
        elif sentiment_score <= self.FEAR_THRESHOLD:
            return MarketSentiment.FEAR
        elif sentiment_score < self.GREED_THRESHOLD:
            return MarketSentiment.NEUTRAL
        elif sentiment_score < self.EXTREME_GREED_THRESHOLD:
            return MarketSentiment.GREED
        else:
            return MarketSentiment.EXTREME_GREED
    
    def analyze_sentiment(self, market_data: Dict) -> PsychologySignal:
        """
        Analyze market sentiment and generate signal
        """
        sentiment_score = self.calculate_sentiment_score(market_data)
        sentiment = self.get_sentiment(sentiment_score)
        
        # Determine action based on sentiment
        if sentiment == MarketSentiment.EXTREME_FEAR:
            # Buy when others are extremely afraid
            action = "BUY"
            strength = "STRONG"
            confidence = 0.85
            recommendation = "🟢 شراء قوي جداً! الخوف الشديد = فرصة ذهبية"
            reason = "الناس في خوف شديد → الأسعار منخفضة جداً → فرصة شراء عظيمة"
        
        elif sentiment == MarketSentiment.FEAR:
            # Buy when others are afraid
            action = "BUY"
            strength = "MEDIUM"
            confidence = 0.70
            recommendation = "🟢 شراء معتدل. الخوف = فرصة"
            reason = "الناس خائفة → الأسعار منخفضة → فرصة شراء جيدة"
        
        elif sentiment == MarketSentiment.NEUTRAL:
            # Hold in neutral market
            action = "HOLD"
            strength = "WEAK"
            confidence = 0.50
            recommendation = "⚪ محايد. انتظر إشارة أوضح"
            reason = "السوق محايد → لا توجد فرصة واضحة"
        
        elif sentiment == MarketSentiment.GREED:
            # Sell when others are greedy
            action = "SELL"
            strength = "MEDIUM"
            confidence = 0.70
            recommendation = "🔴 بيع معتدل. الطمع = تحذير"
            reason = "الناس طماعة → الأسعار مرتفعة جداً → وقت البيع"
        
        else:  # EXTREME_GREED
            # Strong sell when others are extremely greedy
            action = "SELL"
            strength = "STRONG"
            confidence = 0.85
            recommendation = "🔴 بيع قوي جداً! الطمع الشديد = تحذير خطير"
            reason = "الناس في طمع شديد → الأسعار في ذروة → وقت البيع الآن"
        
        signal = PsychologySignal(
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            confidence=confidence,
            recommendation=recommendation,
            action=action,
            strength=strength,
            reason=reason
        )
        
        self.history.append(signal)
        self.sentiment_history[sentiment.value].append(sentiment_score)
        
        return signal
    
    def get_contrarian_opportunity(self, sentiment_score: float) -> Tuple[bool, str, float]:
        """
        Detect contrarian trading opportunities
        (Buy when scared, Sell when greedy)
        """
        if sentiment_score <= self.EXTREME_FEAR_THRESHOLD:
            return True, "🟢 فرصة شراء عظيمة! الخوف الشديد", 0.90
        elif sentiment_score >= self.EXTREME_GREED_THRESHOLD:
            return True, "🔴 فرصة بيع عظيمة! الطمع الشديد", 0.90
        elif sentiment_score <= self.FEAR_THRESHOLD:
            return True, "🟢 فرصة شراء جيدة. الخوف", 0.75
        elif sentiment_score >= self.GREED_THRESHOLD:
            return True, "🔴 فرصة بيع جيدة. الطمع", 0.75
        else:
            return False, "لا توجد فرصة واضحة", 0.0


class LiquidityMonitor:
    """Monitors market liquidity and high-risk periods"""
    
    def __init__(self):
        """Initialize liquidity monitor"""
        self.history = []
        self.loss_patterns = {}
        self.risky_periods = {
            'Friday': {'risk': 'LOW', 'reason': 'سوق الكريبتو يعمل 24/7'},
            'Saturday': {'risk': 'LOW', 'reason': 'سوق الكريبتو يعمل 24/7'},
            'Sunday': {'risk': 'LOW', 'reason': 'سوق الكريبتو يعمل 24/7'},
            'Holiday': {'risk': 'CRITICAL', 'reason': 'عطلة رسمية'},
            '00:00-06:00': {'risk': 'HIGH', 'reason': 'ساعات منخفضة السيولة'},
        }
    
    def calculate_liquidity_score(self, market_data: Dict) -> float:
        """
        Calculate liquidity score (0-100)
        
        Factors:
        - Trading volume
        - Bid-ask spread
        - Order book depth
        - Price impact
        """
        score = 100  # Start with perfect liquidity
        
        try:
            # 1. Volume Analysis (40%)
            if 'volume_24h' in market_data and 'avg_volume_24h' in market_data:
                vol_ratio = market_data['volume_24h'] / market_data['avg_volume_24h']
                if vol_ratio < 0.5:
                    score -= 40  # Very low volume
                elif vol_ratio < 0.8:
                    score -= 20  # Low volume
                elif vol_ratio > 1.5:
                    score -= 5   # High volume is good
            
            # 2. Bid-Ask Spread (30%)
            if 'bid_ask_spread_pct' in market_data:
                spread = market_data['bid_ask_spread_pct']
                if spread > 0.5:
                    score -= 30
                elif spread > 0.2:
                    score -= 15
                elif spread > 0.1:
                    score -= 5
            
            # 3. Order Book Depth (20%)
            if 'orderbook_depth' in market_data:
                depth = market_data['orderbook_depth']
                if depth < 1000:
                    score -= 20
                elif depth < 5000:
                    score -= 10
            
            # 4. Price Volatility (10%)
            if 'volatility' in market_data:
                volatility = market_data['volatility']
                if volatility > 0.1:  # 10% volatility
                    score -= 10
                elif volatility > 0.05:  # 5% volatility
                    score -= 5
            
            score = np.clip(score, 0, 100)
            return score
        
        except Exception as e:
            logger.error(f"Error calculating liquidity: {e}")
            return 50.0
    
    def get_liquidity_level(self, liquidity_score: float) -> LiquidityLevel:
        """Convert liquidity score to level"""
        if liquidity_score >= 80:
            return LiquidityLevel.VERY_HIGH
        elif liquidity_score >= 60:
            return LiquidityLevel.HIGH
        elif liquidity_score >= 40:
            return LiquidityLevel.NORMAL
        elif liquidity_score >= 20:
            return LiquidityLevel.LOW
        else:
            return LiquidityLevel.VERY_LOW
    
    def check_risky_period(self) -> Tuple[bool, str, str]:
        """
        Check if current time is a risky period
        """
        now = datetime.now()
        day_name = now.strftime('%A')
        hour = now.hour
        
        # Check day
        if day_name in self.risky_periods:
            risk_info = self.risky_periods[day_name]
            return True, risk_info['reason'], risk_info['risk']
        
        # Check hour
        for period, info in self.risky_periods.items():
            if '-' in period:  # Time range
                start, end = period.split('-')
                start_hour = int(start.split(':')[0])
                end_hour = int(end.split(':')[0])
                if start_hour <= hour < end_hour:
                    return True, info['reason'], info['risk']
        
        return False, "وقت عادي", "LOW"
    
    def analyze_liquidity(self, market_data: Dict) -> LiquidityAlert:
        """
        Analyze liquidity and generate alert
        """
        liquidity_score = self.calculate_liquidity_score(market_data)
        liquidity_level = self.get_liquidity_level(liquidity_score)
        
        is_risky, reason, risk_level = self.check_risky_period()
        
        if liquidity_level == LiquidityLevel.VERY_LOW:
            risk_level = "CRITICAL"
            recommendation = "🚫 تجنب التداول! السيولة منخفضة جداً"
        elif is_risky and risk_level == "CRITICAL":
            # للكريبتو: نخفف CRITICAL إلى HIGH فقط (السوق يعمل 24/7)
            risk_level = "HIGH"
            recommendation = "⚠️ كن حذراً في هذا التوقيت"
        elif liquidity_level == LiquidityLevel.LOW:
            risk_level = "HIGH"
            recommendation = "⚠️ كن حذراً! السيولة منخفضة"
        elif liquidity_level == LiquidityLevel.NORMAL:
            risk_level = "MEDIUM"
            recommendation = "⚪ سيولة عادية"
        else:
            risk_level = "LOW"
            recommendation = "✅ سيولة جيدة"
        
        alert = LiquidityAlert(
            level=liquidity_level,
            score=liquidity_score,
            risk_level=risk_level,
            description=f"السيولة: {liquidity_level.value} | السبب: {reason}",
            recommendation=recommendation,
            affected_pairs=market_data.get('affected_pairs', []),
            time_period=reason
        )
        
        self.history.append(alert)
        return alert


class LossPatternLearner:
    """Learns from historical loss patterns"""
    
    def __init__(self, history_file: str = 'loss_patterns.json'):
        """Initialize loss pattern learner"""
        self.history_file = history_file
        self.patterns = defaultdict(lambda: {
            'losses': [],
            'wins': [],
            'total_trades': 0,
            'loss_rate': 0.0,
            'average_loss': 0.0
        })
        self.load_patterns()
    
    def load_patterns(self):
        """Load historical patterns from file"""
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                self.patterns = defaultdict(lambda: {
                    'losses': [],
                    'wins': [],
                    'total_trades': 0,
                    'loss_rate': 0.0,
                    'average_loss': 0.0
                }, data)
            logger.info(f"✅ تم تحميل {len(self.patterns)} أنماط خسارة")
        except FileNotFoundError:
            logger.info("📝 ملف الأنماط جديد")
    
    def save_patterns(self):
        """Save patterns to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(dict(self.patterns), f, indent=2, ensure_ascii=False)
            logger.info("✅ تم حفظ أنماط الخسارة")
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الأنماط: {e}")
    
    def record_trade(self, time_period: str, pnl: float, trade_data: Dict):
        """
        Record a trade result
        
        Args:
            time_period: e.g., "Friday", "Weekend", "Holiday", "Night"
            pnl: Profit/Loss in percentage
            trade_data: Additional trade data
        """
        if time_period not in self.patterns:
            self.patterns[time_period] = {
                'losses': [],
                'wins': [],
                'total_trades': 0,
                'loss_rate': 0.0,
                'average_loss': 0.0
            }
        
        pattern = self.patterns[time_period]
        pattern['total_trades'] += 1
        
        if pnl < 0:
            pattern['losses'].append(abs(pnl))
        else:
            pattern['wins'].append(pnl)
        
        # Calculate statistics
        if pattern['losses']:
            pattern['average_loss'] = np.mean(pattern['losses'])
            pattern['loss_rate'] = len(pattern['losses']) / pattern['total_trades']
        
        self.save_patterns()
    
    def get_risky_periods(self) -> List[HistoricalLoss]:
        """
        Get periods with high loss rates
        """
        risky = []
        
        for period, data in self.patterns.items():
            if data['total_trades'] >= 5:  # Minimum trades for reliability
                loss_rate = data['loss_rate']
                avg_loss = data['average_loss']
                confidence = min(data['total_trades'] / 20, 1.0)  # Confidence increases with more trades
                
                if loss_rate > 0.5:  # More than 50% loss rate
                    recommendation = f"🚫 تجنب التداول في {period}! معدل خسارة: {loss_rate*100:.0f}%"
                    risk_level = "CRITICAL"
                elif loss_rate > 0.4:  # More than 40% loss rate
                    recommendation = f"⚠️ كن حذراً في {period}. معدل خسارة: {loss_rate*100:.0f}%"
                    risk_level = "HIGH"
                else:
                    continue
                
                risky.append(HistoricalLoss(
                    time_period=period,
                    average_loss_pct=avg_loss,
                    frequency=data['total_trades'],
                    confidence=confidence,
                    recommendation=recommendation
                ))
        
        # Sort by confidence
        risky.sort(key=lambda x: x.confidence, reverse=True)
        return risky


class PsychologyStrategyEngine:
    """Main psychology strategy engine"""
    
    def __init__(self):
        """Initialize psychology strategy engine"""
        self.fear_greed = FearGreedAnalyzer()
        self.liquidity = LiquidityMonitor()
        self.loss_learner = LossPatternLearner()
        self.alerts = []
    
    def analyze_market_psychology(self, market_data: Dict) -> Dict:
        """
        Comprehensive market psychology analysis
        """
        results = {}
        
        # 1. Fear & Greed Analysis
        sentiment_signal = self.fear_greed.analyze_sentiment(market_data)
        results['sentiment'] = {
            'level': sentiment_signal.sentiment.value,
            'score': sentiment_signal.sentiment_score,
            'action': sentiment_signal.action,
            'strength': sentiment_signal.strength,
            'confidence': sentiment_signal.confidence,
            'recommendation': sentiment_signal.recommendation,
            'reason': sentiment_signal.reason
        }
        
        # 2. Contrarian Opportunity
        is_opportunity, opp_desc, opp_confidence = self.fear_greed.get_contrarian_opportunity(
            sentiment_signal.sentiment_score
        )
        results['contrarian_opportunity'] = {
            'detected': is_opportunity,
            'description': opp_desc,
            'confidence': opp_confidence
        }
        
        # 3. Liquidity Analysis
        liquidity_alert = self.liquidity.analyze_liquidity(market_data)
        results['liquidity'] = {
            'level': liquidity_alert.level.value,
            'score': liquidity_alert.score,
            'risk_level': liquidity_alert.risk_level,
            'description': liquidity_alert.description,
            'recommendation': liquidity_alert.recommendation
        }
        
        # 4. Risky Periods
        risky_periods = self.loss_learner.get_risky_periods()
        results['risky_periods'] = [
            {
                'period': p.time_period,
                'loss_rate': p.average_loss_pct,
                'frequency': p.frequency,
                'confidence': p.confidence,
                'recommendation': p.recommendation
            }
            for p in risky_periods[:3]
        ]
        
        return results
    
    def get_psychology_score(self, market_data: Dict) -> float:
        """
        Calculate overall psychology score (0-100)
        """
        analysis = self.analyze_market_psychology(market_data)
        
        # Base score from sentiment
        sentiment_score = analysis['sentiment']['score']
        base_score = (sentiment_score + 100) / 2  # Convert -100-100 to 0-100
        
        # Adjust for liquidity
        liquidity_score = analysis['liquidity']['score']
        adjusted_score = (base_score + liquidity_score) / 2
        
        # Reduce score if in risky period
        if analysis['risky_periods']:
            adjusted_score *= 0.7
        
        return np.clip(adjusted_score, 0, 100)
    
    def should_trade_now(self, market_data: Dict) -> Tuple[bool, str, float]:
        """
        Determine if it's safe to trade now
        """
        analysis = self.analyze_market_psychology(market_data)
        
        # Check liquidity
        if analysis['liquidity']['risk_level'] == 'CRITICAL':
            return False, f"🚫 {analysis['liquidity']['recommendation']}", 0.0
        
        # Check risky periods
        if analysis['risky_periods']:
            worst_period = analysis['risky_periods'][0]
            if worst_period['confidence'] > 0.7:
                return False, f"🚫 {worst_period['recommendation']}", 0.0
        
        # Check sentiment
        sentiment_action = analysis['sentiment']['action']
        sentiment_confidence = analysis['sentiment']['confidence']
        
        if sentiment_action in ['BUY', 'SELL']:
            return True, analysis['sentiment']['recommendation'], sentiment_confidence
        else:
            return False, "⚪ السوق محايد - انتظر إشارة أوضح", 0.0
    
    def record_trade_result(self, pnl: float, trade_data: Dict):
        """
        Record trade result for learning
        """
        now = datetime.now()
        
        # Determine time period
        day_name = now.strftime('%A')
        hour = now.hour
        
        if day_name in ['Saturday', 'Sunday']:
            period = 'Weekend'
        elif day_name == 'Friday':
            period = 'Friday'
        elif 0 <= hour < 6:
            period = 'Night'
        else:
            period = 'Normal'
        
        self.loss_learner.record_trade(period, pnl, trade_data)
    
    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            'fear_greed_history': len(self.fear_greed.history),
            'liquidity_alerts': len(self.liquidity.history),
            'learned_patterns': len(self.loss_learner.patterns),
            'risky_periods': [
                p.time_period for p in self.loss_learner.get_risky_periods()
            ]
        }


# Example usage
if __name__ == "__main__":
    engine = PsychologyStrategyEngine()
    
    # Simulate market data
    market_data = {
        'price_change_24h': 5.5,
        'volume_change': 1.2,
        'volatility': 0.03,
        'rsi': 72,
        'higher_highs': True,
        'higher_lows': True,
        'volume_24h': 2500000000,
        'avg_volume_24h': 2000000000,
        'bid_ask_spread_pct': 0.05,
        'orderbook_depth': 50000,
        'affected_pairs': ['BTC/USDT', 'ETH/USDT']
    }
    
    print("\n" + "="*80)
    print("🧠 Psychology Strategy Engine - Test")
    print("="*80)
    
    # Analyze
    analysis = engine.analyze_market_psychology(market_data)
    
    print(f"\n📊 Sentiment Analysis:")
    print(f"   Level: {analysis['sentiment']['level']}")
    print(f"   Score: {analysis['sentiment']['score']:.1f}")
    print(f"   Action: {analysis['sentiment']['action']}")
    print(f"   Confidence: {analysis['sentiment']['confidence']:.0%}")
    print(f"   Recommendation: {analysis['sentiment']['recommendation']}")
    
    print(f"\n💧 Liquidity Analysis:")
    print(f"   Level: {analysis['liquidity']['level']}")
    print(f"   Score: {analysis['liquidity']['score']:.1f}")
    print(f"   Risk: {analysis['liquidity']['risk_level']}")
    print(f"   Recommendation: {analysis['liquidity']['recommendation']}")
    
    print(f"\n⚠️ Risky Periods:")
    if analysis['risky_periods']:
        for period in analysis['risky_periods']:
            print(f"   • {period['period']}: {period['loss_rate']:.1%} loss rate")
    else:
        print("   ✅ لا توجد فترات خطرة معروفة")
    
    # Should trade?
    can_trade, reason, confidence = engine.should_trade_now(market_data)
    print(f"\n🎯 Should Trade Now?")
    print(f"   Can Trade: {can_trade}")
    print(f"   Reason: {reason}")
    print(f"   Confidence: {confidence:.0%}")
    
    # Psychology score
    psych_score = engine.get_psychology_score(market_data)
    print(f"\n📈 Overall Psychology Score: {psych_score:.1f}/100")
    
    print("\n" + "="*80)
