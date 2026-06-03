"""
Cryptopanic Intelligence Module
Integrates Cryptopanic news data with the main intelligence engine
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from core.cryptopanic_integration import CryptoPanicIntegration

logger = logging.getLogger(__name__)


class CryptoPanicIntelligence:
    """Cryptopanic Intelligence Analysis"""
    
    def __init__(self, api_key: str):
        """Initialize Cryptopanic Intelligence"""
        self.cp = CryptoPanicIntegration(api_key)
        self.analysis_cache = {}
        logger.info("✅ Cryptopanic Intelligence initialized")
    
    # ========================================================================
    # News Sentiment Analysis
    # ========================================================================
    
    def analyze_news_sentiment_trend(self, currency: str,
                                     limit: int = 50) -> Dict:
        """
        Analyze news sentiment trend for a currency
        
        Returns:
            Dict with sentiment trend analysis
        """
        try:
            sentiment = self.cp.get_currency_sentiment(currency, limit=limit)
            
            trend = {
                'currency': currency,
                'overall_sentiment': sentiment.get('sentiment', 'UNKNOWN'),
                'sentiment_score': sentiment.get('score', 50),
                'bullish_news': sentiment.get('bullish_news', 0),
                'bearish_news': sentiment.get('bearish_news', 0),
                'total_news': sentiment.get('news_count', 0),
                'recommendation': self._get_sentiment_recommendation(sentiment),
                'timestamp': datetime.now().isoformat()
            }
            
            return trend
        except Exception as e:
            logger.error(f"Error analyzing sentiment trend: {e}")
            return {}
    
    def _get_sentiment_recommendation(self, sentiment: Dict) -> str:
        """Get recommendation based on sentiment"""
        overall = sentiment.get('sentiment', 'NEUTRAL')
        score = sentiment.get('score', 50)
        
        if overall == 'BULLISH':
            if score >= 70:
                return "🚀 STRONG BULLISH - Positive news dominates"
            else:
                return "📈 BULLISH - More positive news"
        elif overall == 'BEARISH':
            if score <= 30:
                return "🔴 STRONG BEARISH - Negative news dominates"
            else:
                return "📉 BEARISH - More negative news"
        else:
            return "🟡 NEUTRAL - Mixed news sentiment"
    
    # ========================================================================
    # Critical News Detection
    # ========================================================================
    
    def detect_critical_events(self, limit: int = 50) -> Dict:
        """
        Detect critical news events
        
        Returns:
            Dict with critical events
        """
        try:
            critical_news = self.cp.get_critical_news(limit=limit)
            
            events = {
                'critical_count': len(critical_news),
                'extreme_events': len([n for n in critical_news if n.get('impact') == 'EXTREME']),
                'high_events': len([n for n in critical_news if n.get('impact') == 'HIGH']),
                'top_events': critical_news[:10],  # Top 10
                'has_critical': len(critical_news) > 0,
                'recommendation': self._get_critical_recommendation(critical_news),
                'timestamp': datetime.now().isoformat()
            }
            
            return events
        except Exception as e:
            logger.error(f"Error detecting critical events: {e}")
            return {}
    
    def _get_critical_recommendation(self, critical_news: List[Dict]) -> str:
        """Get recommendation based on critical news"""
        if not critical_news:
            return "✅ NO CRITICAL NEWS - Safe to trade"
        
        extreme_count = len([n for n in critical_news if n.get('impact') == 'EXTREME'])
        
        if extreme_count > 0:
            return f"🚨 EXTREME NEWS ALERT - {extreme_count} critical event(s)"
        else:
            return f"⚠️ IMPORTANT NEWS - {len(critical_news)} significant event(s)"
    
    # ========================================================================
    # Multi-Currency Analysis
    # ========================================================================
    
    def analyze_market_sentiment(self, currencies: List[str] = None) -> Dict:
        """
        Analyze market sentiment across multiple currencies
        
        Returns:
            Dict with market sentiment analysis
        """
        try:
            if not currencies:
                currencies = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA']
            
            sentiments = {}
            for currency in currencies:
                sentiment = self.cp.get_currency_sentiment(currency, limit=30)
                sentiments[currency] = sentiment
            
            # Calculate overall market sentiment
            avg_score = sum(s.get('score', 50) for s in sentiments.values()) / len(sentiments)
            
            if avg_score >= 60:
                market_sentiment = 'BULLISH'
            elif avg_score <= 40:
                market_sentiment = 'BEARISH'
            else:
                market_sentiment = 'NEUTRAL'
            
            analysis = {
                'market_sentiment': market_sentiment,
                'average_score': int(avg_score),
                'currency_sentiments': sentiments,
                'bullish_currencies': len([s for s in sentiments.values() if s.get('sentiment') == 'BULLISH']),
                'bearish_currencies': len([s for s in sentiments.values() if s.get('sentiment') == 'BEARISH']),
                'recommendation': self._get_market_recommendation(market_sentiment, avg_score),
                'timestamp': datetime.now().isoformat()
            }
            
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing market sentiment: {e}")
            return {}
    
    def _get_market_recommendation(self, sentiment: str, score: int) -> str:
        """Get market recommendation"""
        if sentiment == 'BULLISH':
            if score >= 70:
                return "🚀 STRONG BULL MARKET - Positive sentiment across market"
            else:
                return "📈 BULL MARKET - Generally positive news"
        elif sentiment == 'BEARISH':
            if score <= 30:
                return "🔴 STRONG BEAR MARKET - Negative sentiment across market"
            else:
                return "📉 BEAR MARKET - Generally negative news"
        else:
            return "🟡 MIXED MARKET - Conflicting signals"
    
    # ========================================================================
    # News-Based Trading Signals
    # ========================================================================
    
    def generate_news_trading_signal(self, currency: str) -> Dict:
        """
        Generate trading signal based on news
        
        Returns:
            Dict with trading signal
        """
        try:
            # Get sentiment trend
            sentiment_trend = self.analyze_news_sentiment_trend(currency, limit=50)
            
            # Get critical news
            critical_news = self.cp.get_critical_news(limit=30)
            currency_critical = [n for n in critical_news if currency in n.get('title', '')]
            
            # Calculate signal strength
            sentiment_score = sentiment_trend.get('sentiment_score', 50)
            critical_impact = len(currency_critical) * 20  # Each critical news = 20 points
            
            signal_strength = min(100, sentiment_score + critical_impact)
            
            # Determine signal
            if signal_strength >= 70:
                signal = 'STRONG_BUY'
            elif signal_strength >= 55:
                signal = 'BUY'
            elif signal_strength <= 30:
                signal = 'STRONG_SELL'
            elif signal_strength <= 45:
                signal = 'SELL'
            else:
                signal = 'NEUTRAL'
            
            return {
                'currency': currency,
                'signal': signal,
                'signal_strength': signal_strength,
                'sentiment': sentiment_trend.get('overall_sentiment', 'UNKNOWN'),
                'critical_news_count': len(currency_critical),
                'recommendation': self._get_signal_recommendation(signal, signal_strength),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error generating news trading signal: {e}")
            return {}
    
    def _get_signal_recommendation(self, signal: str, strength: int) -> str:
        """Get signal recommendation"""
        if signal == 'STRONG_BUY':
            return f"🚀 STRONG BUY - News sentiment very positive ({strength}%)"
        elif signal == 'BUY':
            return f"📈 BUY - News sentiment positive ({strength}%)"
        elif signal == 'STRONG_SELL':
            return f"🔴 STRONG SELL - News sentiment very negative ({strength}%)"
        elif signal == 'SELL':
            return f"📉 SELL - News sentiment negative ({strength}%)"
        else:
            return f"🟡 NEUTRAL - Mixed news signals ({strength}%)"
    
    # ========================================================================
    # Real-time Monitoring
    # ========================================================================
    
    def monitor_news_events(self, currencies: List[str] = None) -> Dict:
        """
        Monitor news events in real-time
        
        Returns:
            Dict with monitoring results
        """
        try:
            if not currencies:
                currencies = ['BTC', 'ETH']
            
            monitoring = {
                'currencies': {},
                'critical_alerts': [],
                'timestamp': datetime.now().isoformat()
            }
            
            for currency in currencies:
                monitor_result = self.cp.monitor_currency_news(currency)
                monitoring['currencies'][currency] = monitor_result
                
                # Add critical alerts
                if monitor_result.get('important_news', 0) > 0:
                    for news in monitor_result.get('news_items', []):
                        monitoring['critical_alerts'].append({
                            'currency': currency,
                            'news': news
                        })
            
            return monitoring
        except Exception as e:
            logger.error(f"Error monitoring news events: {e}")
            return {}
    
    # ========================================================================
    # Integration with Main Intelligence
    # ========================================================================
    
    def get_cryptopanic_decision(self, currency: str) -> Dict:
        """
        Get comprehensive Cryptopanic decision for trading
        
        Returns:
            Dict with trading decision based on news
        """
        try:
            sentiment_trend = self.analyze_news_sentiment_trend(currency)
            critical_events = self.detect_critical_events(limit=50)
            trading_signal = self.generate_news_trading_signal(currency)
            
            decision = {
                'currency': currency,
                'sentiment_trend': sentiment_trend,
                'critical_events': critical_events,
                'trading_signal': trading_signal,
                'overall_recommendation': self._get_overall_news_recommendation(
                    sentiment_trend, critical_events, trading_signal
                ),
                'timestamp': datetime.now().isoformat()
            }
            
            return decision
        except Exception as e:
            logger.error(f"Error getting Cryptopanic decision: {e}")
            return {}
    
    def _get_overall_news_recommendation(self, sentiment_trend: Dict,
                                        critical_events: Dict,
                                        trading_signal: Dict) -> Dict:
        """Get overall news-based recommendation"""
        
        reasons = []
        confidence = 50
        
        # Sentiment impact
        sentiment = sentiment_trend.get('overall_sentiment', 'NEUTRAL')
        if sentiment == 'BULLISH':
            confidence += 20
            reasons.append(f"📈 Bullish sentiment ({sentiment_trend.get('sentiment_score', 50)}%)")
        elif sentiment == 'BEARISH':
            confidence -= 20
            reasons.append(f"📉 Bearish sentiment ({sentiment_trend.get('sentiment_score', 50)}%)")
        
        # Critical events impact
        if critical_events.get('extreme_events', 0) > 0:
            confidence -= 30
            reasons.append(f"🚨 {critical_events.get('extreme_events')} extreme event(s)")
        elif critical_events.get('high_events', 0) > 0:
            confidence -= 15
            reasons.append(f"⚠️ {critical_events.get('high_events')} high impact event(s)")
        
        # Trading signal impact
        signal = trading_signal.get('signal', 'NEUTRAL')
        if signal == 'STRONG_BUY':
            confidence += 25
            reasons.append("🚀 Strong buy signal from news")
        elif signal == 'BUY':
            confidence += 15
            reasons.append("📈 Buy signal from news")
        elif signal == 'STRONG_SELL':
            confidence -= 25
            reasons.append("🔴 Strong sell signal from news")
        elif signal == 'SELL':
            confidence -= 15
            reasons.append("📉 Sell signal from news")
        
        # Determine action
        if confidence >= 60:
            action = "🚀 STRONG BUY"
        elif confidence >= 30:
            action = "📈 BUY"
        elif confidence >= -30:
            action = "🟡 NEUTRAL"
        elif confidence >= -60:
            action = "📉 SELL"
        else:
            action = "🔴 STRONG SELL"
        
        return {
            'action': action,
            'confidence': confidence,
            'reasons': reasons
        }


# Example usage
if __name__ == "__main__":
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    
    # Your Cryptopanic API Key
    API_KEY = "afed90b669cebc6535f88540ecb1679ee551facc"
    
    # Create Cryptopanic Intelligence
    cp_intel = CryptoPanicIntelligence(API_KEY)
    
    # Get comprehensive decision
    decision = cp_intel.get_cryptopanic_decision("BTC")
    print(f"Decision: {decision}")
