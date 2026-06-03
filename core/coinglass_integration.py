"""
CoinGlass Integration Module
Handles all CoinGlass API connections and data retrieval
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class CoinGlassIntegration:
    """CoinGlass API Integration"""
    
    BASE_URL = "https://api.coinglass.com/api"
    
    def __init__(self, api_key: str):
        """
        Initialize CoinGlass connection
        
        Args:
            api_key: CoinGlass API Key
        """
        self.api_key = api_key
        self.headers = {
            'accept': 'application/json',
            'CG-PRO-API-KEY': api_key
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logger.info("✅ CoinGlass Integration initialized")
    
    def test_connection(self) -> bool:
        """Test CoinGlass connection"""
        try:
            response = self.session.get(f"{self.BASE_URL}/v1/liquidation/today")
            if response.status_code == 200:
                logger.info("✅ CoinGlass connection successful")
                return True
            else:
                logger.error(f"❌ CoinGlass connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ CoinGlass connection error: {e}")
            return False
    
    # ========================================================================
    # Liquidation Data
    # ========================================================================
    
    def get_liquidations_today(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get liquidation data for today"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/liquidation/today",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'long_liquidations': data.get('longLiquidation', 0),
                    'short_liquidations': data.get('shortLiquidation', 0),
                    'total_liquidations': data.get('totalLiquidation', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching liquidations for {symbol}: {e}")
            return None
    
    def get_liquidations_history(self, symbol: str = "BTC", 
                                 limit: int = 100) -> List[Dict]:
        """Get liquidation history"""
        try:
            params = {
                'symbol': symbol,
                'limit': limit
            }
            response = self.session.get(
                f"{self.BASE_URL}/v1/liquidation/history",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Error fetching liquidation history: {e}")
            return []
    
    def get_liquidation_heatmap(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get liquidation heatmap data"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/liquidation/heatmap",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error fetching liquidation heatmap: {e}")
            return None
    
    # ========================================================================
    # Long/Short Ratio
    # ========================================================================
    
    def get_long_short_ratio(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get Long/Short ratio"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/futures/longShortRatio",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'long_ratio': data.get('longRatio', 0),
                    'short_ratio': data.get('shortRatio', 0),
                    'long_short_ratio': data.get('longShortRatio', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching long/short ratio: {e}")
            return None
    
    # ========================================================================
    # Funding Rate
    # ========================================================================
    
    def get_funding_rate(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get funding rate"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/futures/fundingRate",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'funding_rate': data.get('fundingRate', 0),
                    'next_funding_time': data.get('nextFundingTime'),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return None
    
    # ========================================================================
    # Open Interest
    # ========================================================================
    
    def get_open_interest(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get open interest"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/futures/openInterest",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'open_interest': data.get('openInterest', 0),
                    'open_interest_usd': data.get('openInterestUsd', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching open interest: {e}")
            return None
    
    # ========================================================================
    # Support & Resistance
    # ========================================================================
    
    def get_support_resistance(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get support and resistance levels"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/support_resistance",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'support_levels': data.get('support', []),
                    'resistance_levels': data.get('resistance', []),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching support/resistance: {e}")
            return None
    
    # ========================================================================
    # Whale Tracking
    # ========================================================================
    
    def get_whale_transactions(self, symbol: str = "BTC", 
                              limit: int = 50) -> List[Dict]:
        """Get whale transactions"""
        try:
            params = {
                'symbol': symbol,
                'limit': limit
            }
            response = self.session.get(
                f"{self.BASE_URL}/v1/whale/transactions",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Error fetching whale transactions: {e}")
            return []
    
    def get_whale_activity(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get whale activity summary"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/whale/activity",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'whale_buys': data.get('whaleBuys', 0),
                    'whale_sells': data.get('whaleSells', 0),
                    'whale_net_flow': data.get('whaleNetFlow', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching whale activity: {e}")
            return None
    
    # ========================================================================
    # Market Analysis
    # ========================================================================
    
    def get_market_sentiment(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get market sentiment"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/market/sentiment",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'sentiment': data.get('sentiment'),
                    'confidence': data.get('confidence', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching market sentiment: {e}")
            return None
    
    def get_exchange_flow(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get exchange flow data"""
        try:
            params = {'symbol': symbol}
            response = self.session.get(
                f"{self.BASE_URL}/v1/exchange/flow",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'inflow': data.get('inflow', 0),
                    'outflow': data.get('outflow', 0),
                    'net_flow': data.get('netFlow', 0),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching exchange flow: {e}")
            return None
    
    # ========================================================================
    # Analysis Functions
    # ========================================================================
    
    def analyze_liquidation_risk(self, symbol: str = "BTC") -> Dict:
        """Analyze liquidation risk"""
        try:
            liq_data = self.get_liquidations_today(symbol)
            heatmap = self.get_liquidation_heatmap(symbol)
            
            if not liq_data:
                return {'risk_level': 'UNKNOWN', 'score': 0}
            
            total_liq = liq_data['total_liquidations']
            
            # Determine risk level
            if total_liq > 1000000000:  # > $1B
                risk_level = 'CRITICAL'
                score = 95
            elif total_liq > 500000000:  # > $500M
                risk_level = 'HIGH'
                score = 80
            elif total_liq > 100000000:  # > $100M
                risk_level = 'MEDIUM'
                score = 60
            else:
                risk_level = 'LOW'
                score = 30
            
            return {
                'symbol': symbol,
                'risk_level': risk_level,
                'score': score,
                'total_liquidations': total_liq,
                'long_liquidations': liq_data['long_liquidations'],
                'short_liquidations': liq_data['short_liquidations'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error analyzing liquidation risk: {e}")
            return {'risk_level': 'ERROR', 'score': 0}
    
    def analyze_whale_activity(self, symbol: str = "BTC") -> Dict:
        """Analyze whale activity"""
        try:
            whale_data = self.get_whale_activity(symbol)
            
            if not whale_data:
                return {'activity_level': 'UNKNOWN', 'direction': 'NEUTRAL'}
            
            net_flow = whale_data['whale_net_flow']
            
            # Determine activity level and direction
            if net_flow > 0:
                direction = 'BULLISH'  # More buys
                if net_flow > 1000000000:  # > $1B
                    activity_level = 'EXTREME'
                    confidence = 90
                elif net_flow > 500000000:  # > $500M
                    activity_level = 'HIGH'
                    confidence = 75
                else:
                    activity_level = 'MODERATE'
                    confidence = 60
            else:
                direction = 'BEARISH'  # More sells
                if net_flow < -1000000000:  # < -$1B
                    activity_level = 'EXTREME'
                    confidence = 90
                elif net_flow < -500000000:  # < -$500M
                    activity_level = 'HIGH'
                    confidence = 75
                else:
                    activity_level = 'MODERATE'
                    confidence = 60
            
            return {
                'symbol': symbol,
                'activity_level': activity_level,
                'direction': direction,
                'confidence': confidence,
                'net_flow': net_flow,
                'whale_buys': whale_data['whale_buys'],
                'whale_sells': whale_data['whale_sells'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error analyzing whale activity: {e}")
            return {'activity_level': 'ERROR', 'direction': 'NEUTRAL'}
    
    def analyze_market_conditions(self, symbol: str = "BTC") -> Dict:
        """Analyze overall market conditions"""
        try:
            liq_risk = self.analyze_liquidation_risk(symbol)
            whale_activity = self.analyze_whale_activity(symbol)
            long_short = self.get_long_short_ratio(symbol)
            funding = self.get_funding_rate(symbol)
            
            # Combine analysis
            analysis = {
                'symbol': symbol,
                'liquidation_risk': liq_risk,
                'whale_activity': whale_activity,
                'long_short_ratio': long_short,
                'funding_rate': funding,
                'timestamp': datetime.now().isoformat()
            }
            
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {}
    
    def detect_trap_signals(self, symbol: str = "BTC") -> Dict:
        """Detect potential trap signals"""
        try:
            liq_data = self.get_liquidations_today(symbol)
            whale_data = self.get_whale_activity(symbol)
            long_short = self.get_long_short_ratio(symbol)
            
            trap_signals = []
            confidence = 0
            
            # Check for stop loss hunt
            if liq_data and liq_data['total_liquidations'] > 500000000:
                trap_signals.append('STOP_LOSS_HUNT')
                confidence += 30
            
            # Check for whale dump
            if whale_data and whale_data['direction'] == 'BEARISH':
                if whale_data['activity_level'] in ['HIGH', 'EXTREME']:
                    trap_signals.append('WHALE_DUMP')
                    confidence += 40
            
            # Check for long squeeze
            if long_short and long_short['long_ratio'] > 0.65:
                if liq_data and liq_data['long_liquidations'] > liq_data['short_liquidations']:
                    trap_signals.append('LONG_SQUEEZE')
                    confidence += 35
            
            return {
                'symbol': symbol,
                'trap_signals': trap_signals,
                'confidence': min(confidence, 100),
                'is_trap': len(trap_signals) > 0,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error detecting trap signals: {e}")
            return {'trap_signals': [], 'confidence': 0, 'is_trap': False}


# Example usage
if __name__ == "__main__":
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    
    # Your CoinGlass API Key
    API_KEY = "your_api_key"
    
    # Create CoinGlass integration
    cg = CoinGlassIntegration(API_KEY)
    
    # Test connection
    if cg.test_connection():
        # Get liquidations
        liq = cg.get_liquidations_today("BTC")
        print(f"Liquidations: {liq}")
        
        # Get whale activity
        whale = cg.get_whale_activity("BTC")
        print(f"Whale Activity: {whale}")
        
        # Analyze market
        analysis = cg.analyze_market_conditions("BTC")
        print(f"Market Analysis: {analysis}")
        
        # Detect traps
        traps = cg.detect_trap_signals("BTC")
        print(f"Trap Signals: {traps}")
