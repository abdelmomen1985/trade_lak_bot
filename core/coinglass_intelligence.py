"""
CoinGlass Intelligence Module
Integrates CoinGlass data with the main intelligence engine
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from core.coinglass_integration import CoinGlassIntegration

logger = logging.getLogger(__name__)


class CoinGlassIntelligence:
    """CoinGlass Intelligence Analysis"""
    
    def __init__(self, api_key: str):
        """Initialize CoinGlass Intelligence"""
        self.cg = CoinGlassIntegration(api_key)
        self.analysis_cache = {}
        logger.info("✅ CoinGlass Intelligence initialized")
    
    # ========================================================================
    # Liquidation Analysis
    # ========================================================================
    
    def analyze_liquidation_pressure(self, symbol: str) -> Dict:
        """
        Analyze liquidation pressure
        
        Returns:
            Dict with pressure analysis
        """
        try:
            liq_risk = self.cg.analyze_liquidation_risk(symbol)
            
            pressure = {
                'symbol': symbol,
                'risk_level': liq_risk['risk_level'],
                'pressure_score': liq_risk['score'],
                'total_liquidations': liq_risk['total_liquidations'],
                'long_liquidations': liq_risk['long_liquidations'],
                'short_liquidations': liq_risk['short_liquidations'],
                'recommendation': self._get_liquidation_recommendation(liq_risk),
                'timestamp': datetime.now().isoformat()
            }
            
            return pressure
        except Exception as e:
            logger.error(f"Error analyzing liquidation pressure: {e}")
            return {}
    
    def _get_liquidation_recommendation(self, liq_risk: Dict) -> str:
        """Get recommendation based on liquidation risk"""
        risk_level = liq_risk['risk_level']
        
        if risk_level == 'CRITICAL':
            return "🚫 AVOID - Extreme liquidation risk"
        elif risk_level == 'HIGH':
            return "⚠️ CAUTION - High liquidation pressure"
        elif risk_level == 'MEDIUM':
            return "🟡 MODERATE - Be cautious with position size"
        else:
            return "✅ SAFE - Low liquidation risk"
    
    # ========================================================================
    # Whale Activity Analysis
    # ========================================================================
    
    def analyze_whale_behavior(self, symbol: str) -> Dict:
        """
        Analyze whale behavior
        
        Returns:
            Dict with whale behavior analysis
        """
        try:
            whale_activity = self.cg.analyze_whale_activity(symbol)
            
            behavior = {
                'symbol': symbol,
                'activity_level': whale_activity['activity_level'],
                'direction': whale_activity['direction'],
                'confidence': whale_activity['confidence'],
                'net_flow': whale_activity['net_flow'],
                'whale_buys': whale_activity['whale_buys'],
                'whale_sells': whale_activity['whale_sells'],
                'recommendation': self._get_whale_recommendation(whale_activity),
                'timestamp': datetime.now().isoformat()
            }
            
            return behavior
        except Exception as e:
            logger.error(f"Error analyzing whale behavior: {e}")
            return {}
    
    def _get_whale_recommendation(self, whale_activity: Dict) -> str:
        """Get recommendation based on whale activity"""
        direction = whale_activity['direction']
        activity_level = whale_activity['activity_level']
        
        if direction == 'BULLISH':
            if activity_level == 'EXTREME':
                return "🚀 STRONG BUY - Whales accumulating heavily"
            elif activity_level == 'HIGH':
                return "📈 BUY SIGNAL - Whale accumulation detected"
            else:
                return "✅ POSITIVE - Moderate whale buying"
        else:  # BEARISH
            if activity_level == 'EXTREME':
                return "🔴 STRONG SELL - Whales dumping heavily"
            elif activity_level == 'HIGH':
                return "📉 SELL SIGNAL - Whale distribution detected"
            else:
                return "⚠️ NEGATIVE - Moderate whale selling"
    
    # ========================================================================
    # Market Condition Analysis
    # ========================================================================
    
    def analyze_market_health(self, symbol: str) -> Dict:
        """
        Analyze overall market health
        
        Returns:
            Dict with market health metrics
        """
        try:
            market_analysis = self.cg.analyze_market_conditions(symbol)
            
            # Extract key metrics
            liq_risk = market_analysis.get('liquidation_risk', {})
            whale_activity = market_analysis.get('whale_activity', {})
            long_short = market_analysis.get('long_short_ratio', {})
            funding = market_analysis.get('funding_rate', {})
            
            # Calculate health score
            health_score = self._calculate_market_health_score(
                liq_risk, whale_activity, long_short, funding
            )
            
            health = {
                'symbol': symbol,
                'health_score': health_score,
                'health_status': self._get_health_status(health_score),
                'liquidation_risk': liq_risk.get('risk_level', 'UNKNOWN'),
                'whale_direction': whale_activity.get('direction', 'NEUTRAL'),
                'long_ratio': long_short.get('long_ratio', 0),
                'funding_rate': funding.get('funding_rate', 0),
                'details': market_analysis,
                'timestamp': datetime.now().isoformat()
            }
            
            return health
        except Exception as e:
            logger.error(f"Error analyzing market health: {e}")
            return {}
    
    def _calculate_market_health_score(self, liq_risk: Dict, whale_activity: Dict,
                                       long_short: Dict, funding: Dict) -> int:
        """Calculate overall market health score (0-100)"""
        score = 50  # Start at neutral
        
        # Liquidation risk impact (-30 to +10)
        risk_level = liq_risk.get('risk_level', 'MEDIUM')
        if risk_level == 'CRITICAL':
            score -= 30
        elif risk_level == 'HIGH':
            score -= 20
        elif risk_level == 'MEDIUM':
            score -= 10
        else:
            score += 10
        
        # Whale activity impact (-20 to +20)
        direction = whale_activity.get('direction', 'NEUTRAL')
        activity_level = whale_activity.get('activity_level', 'MODERATE')
        
        if direction == 'BULLISH':
            if activity_level == 'EXTREME':
                score += 20
            elif activity_level == 'HIGH':
                score += 15
            else:
                score += 5
        elif direction == 'BEARISH':
            if activity_level == 'EXTREME':
                score -= 20
            elif activity_level == 'HIGH':
                score -= 15
            else:
                score -= 5
        
        # Long/Short ratio impact (-15 to +15)
        long_ratio = long_short.get('long_ratio', 0.5)
        if long_ratio > 0.65:
            score -= 15  # Too many longs, squeeze risk
        elif long_ratio < 0.35:
            score += 15  # More shorts, potential bounce
        else:
            score += 5  # Balanced
        
        # Funding rate impact (-10 to +10)
        funding_rate = funding.get('funding_rate', 0)
        if funding_rate > 0.01:
            score -= 10  # High positive funding, overheated
        elif funding_rate < -0.01:
            score += 10  # Negative funding, potential bounce
        
        # Clamp score between 0 and 100
        return max(0, min(100, score))
    
    def _get_health_status(self, score: int) -> str:
        """Get health status based on score"""
        if score >= 80:
            return "🟢 EXCELLENT"
        elif score >= 60:
            return "🟡 GOOD"
        elif score >= 40:
            return "🟠 FAIR"
        elif score >= 20:
            return "🔴 POOR"
        else:
            return "🚫 CRITICAL"
    
    # ========================================================================
    # Trap Detection
    # ========================================================================
    
    def detect_market_traps(self, symbol: str) -> Dict:
        """
        Detect potential market traps
        
        Returns:
            Dict with trap detection results
        """
        try:
            trap_signals = self.cg.detect_trap_signals(symbol)
            
            traps = {
                'symbol': symbol,
                'is_trap': trap_signals['is_trap'],
                'trap_signals': trap_signals['trap_signals'],
                'confidence': trap_signals['confidence'],
                'recommendation': self._get_trap_recommendation(trap_signals),
                'timestamp': datetime.now().isoformat()
            }
            
            return traps
        except Exception as e:
            logger.error(f"Error detecting traps: {e}")
            return {}
    
    def _get_trap_recommendation(self, trap_signals: Dict) -> str:
        """Get recommendation based on trap signals"""
        if not trap_signals['is_trap']:
            return "✅ NO TRAP DETECTED - Safe to trade"
        
        confidence = trap_signals['confidence']
        signals = trap_signals['trap_signals']
        
        if confidence >= 80:
            return f"🚫 HIGH PROBABILITY TRAP - {', '.join(signals)}"
        elif confidence >= 60:
            return f"⚠️ POSSIBLE TRAP - {', '.join(signals)}"
        else:
            return f"🟡 WATCH OUT - {', '.join(signals)}"
    
    # ========================================================================
    # Integration with Main Intelligence
    # ========================================================================
    
    def get_coinglass_decision(self, symbol: str) -> Dict:
        """
        Get comprehensive CoinGlass decision for trading
        
        Returns:
            Dict with trading decision based on CoinGlass data
        """
        try:
            liq_pressure = self.analyze_liquidation_pressure(symbol)
            whale_behavior = self.analyze_whale_behavior(symbol)
            market_health = self.analyze_market_health(symbol)
            trap_detection = self.detect_market_traps(symbol)
            
            # Combine all analysis
            decision = {
                'symbol': symbol,
                'liquidation_pressure': liq_pressure,
                'whale_behavior': whale_behavior,
                'market_health': market_health,
                'trap_detection': trap_detection,
                'overall_recommendation': self._get_overall_recommendation(
                    liq_pressure, whale_behavior, market_health, trap_detection
                ),
                'timestamp': datetime.now().isoformat()
            }
            
            return decision
        except Exception as e:
            logger.error(f"Error getting CoinGlass decision: {e}")
            return {}
    
    def _get_overall_recommendation(self, liq_pressure: Dict, whale_behavior: Dict,
                                   market_health: Dict, trap_detection: Dict) -> Dict:
        """Get overall trading recommendation"""
        
        # Calculate confidence score
        confidence = 0
        reasons = []
        
        # Check liquidation pressure
        if liq_pressure.get('risk_level') == 'CRITICAL':
            confidence -= 40
            reasons.append("🚫 Critical liquidation risk")
        elif liq_pressure.get('risk_level') == 'HIGH':
            confidence -= 20
            reasons.append("⚠️ High liquidation pressure")
        
        # Check whale behavior
        whale_direction = whale_behavior.get('direction', 'NEUTRAL')
        whale_activity = whale_behavior.get('activity_level', 'MODERATE')
        
        if whale_direction == 'BULLISH' and whale_activity in ['HIGH', 'EXTREME']:
            confidence += 30
            reasons.append("🐋 Whales accumulating")
        elif whale_direction == 'BEARISH' and whale_activity in ['HIGH', 'EXTREME']:
            confidence -= 30
            reasons.append("🐋 Whales dumping")
        
        # Check market health
        health_score = market_health.get('health_score', 50)
        if health_score >= 70:
            confidence += 20
            reasons.append("📈 Market health excellent")
        elif health_score <= 30:
            confidence -= 20
            reasons.append("📉 Market health poor")
        
        # Check trap detection
        if trap_detection.get('is_trap'):
            confidence -= (trap_detection.get('confidence', 50) / 2)
            reasons.append(f"🚫 Trap detected: {trap_detection.get('trap_signals', [])}")
        
        # Clamp confidence
        confidence = max(-100, min(100, confidence))
        
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
    
    # Your CoinGlass API Key
    API_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
    
    # Create CoinGlass Intelligence
    cg_intel = CoinGlassIntelligence(API_KEY)
    
    # Get comprehensive decision
    decision = cg_intel.get_coinglass_decision("BTC")
    print(f"Decision: {decision}")
