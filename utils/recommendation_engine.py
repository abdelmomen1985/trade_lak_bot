"""
Recommendation Engine
Advanced recommendation system with success rate calculation
نظام التوصيات المتقدم مع حساب نسب النجاح
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Advanced recommendation engine with AI-powered success rate calculation"""
    
    def __init__(self, okx, intelligence_engine):
        """Initialize recommendation engine"""
        self.okx = okx
        self.intelligence = intelligence_engine
        self.recommendations_history = []
        logger.info("✅ Recommendation Engine initialized")
    
    # ========================================================================
    # Price Level Calculation
    # ========================================================================
    
    def calculate_entry_levels(self, current_price: float, signal_strength: float) -> Tuple[float, float]:
        """
        Calculate entry levels based on current price and signal strength
        حساب مستويات الدخول بناءً على السعر الحالي وقوة الإشارة
        """
        # Signal strength: 0.0 to 1.0
        # Strong signal: entry closer to current price
        # Weak signal: entry lower (more conservative)
        
        if signal_strength >= 0.8:  # Very strong signal
            entry1 = current_price * 0.997  # 0.3% below
            entry2 = current_price * 0.994  # 0.6% below
        elif signal_strength >= 0.7:  # Strong signal
            entry1 = current_price * 0.995  # 0.5% below
            entry2 = current_price * 0.990  # 1.0% below
        elif signal_strength >= 0.6:  # Moderate signal
            entry1 = current_price * 0.992  # 0.8% below
            entry2 = current_price * 0.985  # 1.5% below
        else:  # Weak signal
            entry1 = current_price * 0.990  # 1.0% below
            entry2 = current_price * 0.980  # 2.0% below
        
        return round(entry1, 2), round(entry2, 2)
    
    def calculate_take_profit_levels(self, entry_price: float, signal_strength: float, 
                                    volatility: float) -> Tuple[float, float, float]:
        """
        Calculate take profit levels (TP1, TP2, TP3)
        حساب مستويات جني الأرباح
        """
        # Adjust TP levels based on volatility and signal strength
        # Higher volatility = wider TP levels
        # Stronger signal = higher TP levels
        
        volatility_factor = 1.0 + (volatility * 0.5)  # 0% to 50% adjustment
        signal_factor = 0.8 + (signal_strength * 0.4)  # 0.8 to 1.2 multiplier
        
        # Base TP levels (conservative)
        tp1_pct = 1.5 * volatility_factor * signal_factor  # ~1.5% to 3%
        tp2_pct = 3.0 * volatility_factor * signal_factor  # ~3% to 6%
        tp3_pct = 5.0 * volatility_factor * signal_factor  # ~5% to 10%
        
        tp1 = entry_price * (1 + tp1_pct / 100)
        tp2 = entry_price * (1 + tp2_pct / 100)
        tp3 = entry_price * (1 + tp3_pct / 100)
        
        return round(tp1, 2), round(tp2, 2), round(tp3, 2)
    
    def calculate_stop_loss(self, entry_price: float, signal_strength: float, 
                           volatility: float) -> float:
        """
        Calculate stop loss level
        حساب مستوى وقف الخسارة
        """
        # Wider SL for higher volatility and weaker signals
        volatility_factor = 1.0 + (volatility * 0.3)
        signal_factor = 1.2 - (signal_strength * 0.3)  # 0.9 to 1.2
        
        # Base SL: 2% below entry
        sl_pct = 2.0 * volatility_factor * signal_factor
        
        sl = entry_price * (1 - sl_pct / 100)
        return round(sl, 2)
    
    # ========================================================================
    # Success Rate Calculation
    # ========================================================================
    
    def calculate_success_rate(self, symbol: str, analysis_data: Dict) -> float:
        """
        Calculate success rate based on multiple factors
        حساب نسبة النجاح بناءً على عوامل متعددة
        """
        scores = []
        weights = []
        
        # 1. Technical Analysis Score (25%)
        technical_score = self._calculate_technical_score(analysis_data)
        scores.append(technical_score)
        weights.append(0.25)
        
        # 2. Market Sentiment Score (20%)
        sentiment_score = self._calculate_sentiment_score(analysis_data)
        scores.append(sentiment_score)
        weights.append(0.20)
        
        # 3. Whale Activity Score (20%)
        whale_score = self._calculate_whale_score(analysis_data)
        scores.append(whale_score)
        weights.append(0.20)
        
        # 4. Volume & Liquidity Score (15%)
        volume_score = self._calculate_volume_score(analysis_data)
        scores.append(volume_score)
        weights.append(0.15)
        
        # 5. Risk/Reward Ratio Score (10%)
        rr_score = self._calculate_rr_score(analysis_data)
        scores.append(rr_score)
        weights.append(0.10)
        
        # 6. Economic Events Score (10%)
        events_score = self._calculate_events_score(analysis_data)
        scores.append(events_score)
        weights.append(0.10)
        
        # Calculate weighted average
        weighted_score = sum(s * w for s, w in zip(scores, weights))
        
        # Convert to percentage (0-100)
        success_rate = min(95, max(30, weighted_score * 100))  # Cap at 95%, floor at 30%
        
        return round(success_rate, 1)
    
    def _calculate_technical_score(self, data: Dict) -> float:
        """Calculate technical analysis score (0.0 to 1.0)"""
        score = 0.0
        count = 0
        
        # RSI analysis
        if 'rsi' in data:
            rsi = data['rsi']
            if 30 <= rsi <= 70:
                score += 0.3
            elif 40 <= rsi <= 60:
                score += 0.5
            count += 1
        
        # MACD analysis
        if 'macd_signal' in data:
            if data['macd_signal'] == 'bullish':
                score += 0.4
            elif data['macd_signal'] == 'neutral':
                score += 0.2
            count += 1
        
        # Trend analysis
        if 'trend' in data:
            if data['trend'] == 'uptrend':
                score += 0.5
            elif data['trend'] == 'neutral':
                score += 0.3
            count += 1
        
        # Moving averages
        if 'price_above_ma' in data:
            if data['price_above_ma']:
                score += 0.4
            count += 1
        
        return score / count if count > 0 else 0.5
    
    def _calculate_sentiment_score(self, data: Dict) -> float:
        """Calculate market sentiment score"""
        score = 0.0
        count = 0
        
        # Fear & Greed Index
        if 'fear_greed' in data:
            fg = data['fear_greed']
            if fg < 30:  # Extreme Fear - Good buying opportunity
                score += 0.8
            elif fg < 50:  # Fear
                score += 0.6
            elif fg < 70:  # Greed
                score += 0.3
            else:  # Extreme Greed
                score += 0.1
            count += 1
        
        # News sentiment
        if 'news_sentiment' in data:
            sentiment = data['news_sentiment']
            if sentiment == 'very_positive':
                score += 0.7
            elif sentiment == 'positive':
                score += 0.5
            elif sentiment == 'neutral':
                score += 0.3
            else:
                score += 0.1
            count += 1
        
        # Social sentiment
        if 'social_sentiment' in data:
            if data['social_sentiment'] == 'bullish':
                score += 0.6
            elif data['social_sentiment'] == 'neutral':
                score += 0.3
            count += 1
        
        return score / count if count > 0 else 0.5
    
    def _calculate_whale_score(self, data: Dict) -> float:
        """Calculate whale activity score"""
        score = 0.0
        count = 0
        
        # Whale accumulation
        if 'whale_accumulation' in data:
            if data['whale_accumulation']:
                score += 0.8
            count += 1
        
        # Whale distribution
        if 'whale_distribution' in data:
            if data['whale_distribution']:
                score += 0.1
            else:
                score += 0.7
            count += 1
        
        # Whale trap detection
        if 'whale_trap_detected' in data:
            if not data['whale_trap_detected']:
                score += 0.8
            else:
                score += 0.2
            count += 1
        
        # Liquidation pressure
        if 'liquidation_pressure' in data:
            pressure = data['liquidation_pressure']
            if pressure == 'low':
                score += 0.8
            elif pressure == 'medium':
                score += 0.5
            else:
                score += 0.2
            count += 1
        
        return score / count if count > 0 else 0.5
    
    def _calculate_volume_score(self, data: Dict) -> float:
        """Calculate volume and liquidity score"""
        score = 0.0
        count = 0
        
        # Volume trend
        if 'volume_trend' in data:
            if data['volume_trend'] == 'increasing':
                score += 0.8
            elif data['volume_trend'] == 'stable':
                score += 0.5
            else:
                score += 0.2
            count += 1
        
        # Volume level
        if 'volume_level' in data:
            if data['volume_level'] == 'high':
                score += 0.8
            elif data['volume_level'] == 'medium':
                score += 0.5
            else:
                score += 0.3
            count += 1
        
        # Liquidity
        if 'liquidity' in data:
            if data['liquidity'] == 'high':
                score += 0.9
            elif data['liquidity'] == 'medium':
                score += 0.6
            else:
                score += 0.3
            count += 1
        
        return score / count if count > 0 else 0.5
    
    def _calculate_rr_score(self, data: Dict) -> float:
        """Calculate risk/reward ratio score"""
        score = 0.5  # Default neutral
        
        if 'risk_reward_ratio' in data:
            rr = data['risk_reward_ratio']
            if rr >= 3.0:  # Excellent
                score = 1.0
            elif rr >= 2.0:  # Very good
                score = 0.9
            elif rr >= 1.5:  # Good
                score = 0.8
            elif rr >= 1.0:  # Acceptable
                score = 0.6
            else:  # Poor
                score = 0.3
        
        return score
    
    def _calculate_events_score(self, data: Dict) -> float:
        """Calculate economic events score"""
        score = 0.8  # Default good (no bad events)
        
        # Check for high impact events
        if 'high_impact_events' in data:
            if data['high_impact_events']:
                score = 0.3  # Reduce score if high impact events
        
        # Check for medium impact events
        if 'medium_impact_events' in data:
            if data['medium_impact_events']:
                score = min(score, 0.6)
        
        return score
    
    # ========================================================================
    # Recommendation Generation
    # ========================================================================
    
    def generate_recommendation(self, symbol: str, current_price: float, 
                               analysis_data: Dict, trade_type: str = 'auto') -> Dict:
        """
        Generate complete recommendation
        إنشاء توصية كاملة
        """
        try:
            # Calculate signal strength (0.0 to 1.0)
            signal_strength = self._calculate_signal_strength(analysis_data)
            
            # Calculate volatility
            volatility = self._calculate_volatility(analysis_data)
            
            # Calculate entry levels
            entry1, entry2 = self.calculate_entry_levels(current_price, signal_strength)
            
            # Calculate take profit levels
            tp1, tp2, tp3 = self.calculate_take_profit_levels(entry1, signal_strength, volatility)
            
            # Calculate stop loss
            sl = self.calculate_stop_loss(entry1, signal_strength, volatility)
            
            # Determine trade type
            if trade_type == 'auto':
                trade_type = self._determine_trade_type(analysis_data)
            
            # Calculate success rate
            success_rate = self.calculate_success_rate(symbol, analysis_data)
            
            # Create recommendation
            recommendation = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'current_price': current_price,
                'entry_level_1': entry1,
                'entry_level_2': entry2,
                'take_profit_1': tp1,
                'take_profit_2': tp2,
                'take_profit_3': tp3,
                'stop_loss': sl,
                'trade_type': trade_type,
                'success_rate': success_rate,
                'signal_strength': round(signal_strength * 100, 1),
                'volatility': round(volatility * 100, 1),
                'risk_reward_ratio': round((tp3 - entry1) / (entry1 - sl), 2),
                'analysis_summary': self._create_analysis_summary(analysis_data),
            }
            
            # Add to history
            self.recommendations_history.append(recommendation)
            if len(self.recommendations_history) > 100:
                self.recommendations_history = self.recommendations_history[-100:]
            
            return recommendation
        
        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return None
    
    def _calculate_signal_strength(self, data: Dict) -> float:
        """Calculate overall signal strength (0.0 to 1.0)"""
        strengths = []
        
        if 'technical_signal' in data:
            strengths.append(data['technical_signal'])
        if 'sentiment_signal' in data:
            strengths.append(data['sentiment_signal'])
        if 'whale_signal' in data:
            strengths.append(data['whale_signal'])
        if 'volume_signal' in data:
            strengths.append(data['volume_signal'])
        
        return np.mean(strengths) if strengths else 0.5
    
    def _calculate_volatility(self, data: Dict) -> float:
        """Calculate market volatility (0.0 to 1.0)"""
        if 'volatility' in data:
            vol = data['volatility']
            # Normalize to 0.0-1.0
            return min(1.0, max(0.0, vol / 10.0))
        return 0.3  # Default moderate volatility
    
    def _determine_trade_type(self, data: Dict) -> str:
        """Determine best trade type (SPOT or FUTURES)"""
        # Use SPOT for conservative signals, FUTURES for strong signals
        if 'signal_strength' in data:
            strength = data['signal_strength']
            if strength >= 0.8:
                return 'FUTURES'
            elif strength >= 0.6:
                return 'SPOT'
            else:
                return 'SPOT'
        return 'SPOT'
    
    def _create_analysis_summary(self, data: Dict) -> str:
        """Create analysis summary"""
        summary = "📊 **تحليل التوصية:**\n"
        
        if 'technical_analysis' in data:
            summary += f"• التحليل الفني: {data['technical_analysis']}\n"
        
        if 'sentiment' in data:
            summary += f"• معنويات السوق: {data['sentiment']}\n"
        
        if 'whale_activity' in data:
            summary += f"• نشاط الحيتان: {data['whale_activity']}\n"
        
        if 'volume_analysis' in data:
            summary += f"• تحليل الحجم: {data['volume_analysis']}\n"
        
        return summary
    
    # ========================================================================
    # Recommendation Formatting
    # ========================================================================
    
    def format_recommendation_for_telegram(self, rec: Dict) -> str:
        """Format recommendation for Telegram message"""
        if not rec:
            return "❌ لم يتمكن من إنشاء توصية"
        
        # Emoji based on success rate
        if rec['success_rate'] >= 80:
            emoji = "🟢"
        elif rec['success_rate'] >= 60:
            emoji = "🟡"
        else:
            emoji = "🔴"
        
        message = f"""
{emoji} **توصية تداول جديدة**

📊 **العملة:** {rec['symbol']}
💰 **السعر الحالي:** ${rec['current_price']:,.2f}

🎯 **نقاط الدخول:**
• الدخول الأول: ${rec['entry_level_1']:,.2f}
• الدخول الثاني: ${rec['entry_level_2']:,.2f}

📈 **أهداف جني الأرباح:**
• الهدف الأول (TP1): ${rec['take_profit_1']:,.2f}
• الهدف الثاني (TP2): ${rec['take_profit_2']:,.2f}
• الهدف الثالث (TP3): ${rec['take_profit_3']:,.2f}

🛑 **وقف الخسارة:** ${rec['stop_loss']:,.2f}

⚙️ **نوع التداول:** {rec['trade_type']}

📊 **نسبة النجاح:** {rec['success_rate']}%
💪 **قوة الإشارة:** {rec['signal_strength']}%
📉 **التقلبات:** {rec['volatility']}%
💎 **نسبة المخاطرة/الربح:** 1:{rec['risk_reward_ratio']}

{rec['analysis_summary']}

⏰ **الوقت:** {datetime.now().strftime('%H:%M:%S')}
"""
        return message
    
    def format_recommendation_detailed(self, rec: Dict) -> str:
        """Format detailed recommendation"""
        if not rec:
            return "❌ لم يتمكن من إنشاء توصية"
        
        message = f"""
{'🟢' if rec['success_rate'] >= 80 else '🟡' if rec['success_rate'] >= 60 else '🔴'} **توصية تفصيلية: {rec['symbol']}**

---

**📊 بيانات العملة:**
• السعر الحالي: ${rec['current_price']:,.2f}
• التقلبات: {rec['volatility']}%
• قوة الإشارة: {rec['signal_strength']}%

**🎯 مستويات الدخول:**
• الدخول الأول: ${rec['entry_level_1']:,.2f}
• الدخول الثاني: ${rec['entry_level_2']:,.2f}
• الفرق: {((rec['entry_level_1'] - rec['entry_level_2']) / rec['entry_level_1'] * 100):.2f}%

**📈 أهداف جني الأرباح:**
• TP1: ${rec['take_profit_1']:,.2f} (+{((rec['take_profit_1'] - rec['entry_level_1']) / rec['entry_level_1'] * 100):.2f}%)
• TP2: ${rec['take_profit_2']:,.2f} (+{((rec['take_profit_2'] - rec['entry_level_1']) / rec['entry_level_1'] * 100):.2f}%)
• TP3: ${rec['take_profit_3']:,.2f} (+{((rec['take_profit_3'] - rec['entry_level_1']) / rec['entry_level_1'] * 100):.2f}%)

**🛑 وقف الخسارة:**
• المستوى: ${rec['stop_loss']:,.2f}
• الخسارة المحتملة: {((rec['entry_level_1'] - rec['stop_loss']) / rec['entry_level_1'] * 100):.2f}%

**⚙️ تفاصيل التداول:**
• نوع التداول: {rec['trade_type']}
• نسبة النجاح: {rec['success_rate']}%
• نسبة المخاطرة/الربح: 1:{rec['risk_reward_ratio']}

**📊 التحليل:**
{rec['analysis_summary']}

**⏰ الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize
    engine = RecommendationEngine(None, None)
    
    # Test data
    test_data = {
        'rsi': 45,
        'macd_signal': 'bullish',
        'trend': 'uptrend',
        'price_above_ma': True,
        'fear_greed': 35,
        'news_sentiment': 'positive',
        'social_sentiment': 'bullish',
        'whale_accumulation': True,
        'whale_distribution': False,
        'whale_trap_detected': False,
        'liquidation_pressure': 'low',
        'volume_trend': 'increasing',
        'volume_level': 'high',
        'liquidity': 'high',
        'risk_reward_ratio': 2.5,
        'high_impact_events': False,
        'technical_signal': 0.8,
        'sentiment_signal': 0.7,
        'whale_signal': 0.85,
        'volume_signal': 0.8,
        'volatility': 2.5,
    }
    
    # Generate recommendation
    rec = engine.generate_recommendation('BTC', 45000, test_data)
    
    if rec:
        print(engine.format_recommendation_for_telegram(rec))
