"""
OKX Integration Module
Handles all OKX API connections and trading operations
"""

import ccxt
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class OKXIntegration:
    """OKX Exchange Integration"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        """
        Initialize OKX connection
        
        Args:
            api_key: OKX API Key
            api_secret: OKX API Secret
            passphrase: OKX Passphrase
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        
        # Initialize OKX exchange
        self.exchange = ccxt.okx({
            'apiKey': api_key,
            'secret': api_secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'fetchTradingFees': True,
            }
        })
        
        logger.info("✅ OKX Integration initialized")
    
    def test_connection(self) -> bool:
        """Test OKX connection"""
        try:
            balance = self.exchange.fetch_balance()
            logger.info("✅ OKX connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ OKX connection failed: {e}")
            return False
    
    def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            balance = self.exchange.fetch_balance()
            return {
                'total': balance.get('total', {}),
                'free': balance.get('free', {}),
                'used': balance.get('used', {}),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {}
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker data for a symbol"""
        try:
            # Convert symbol format (e.g., BTC/USDT)
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'high': ticker.get('high'),
                'low': ticker.get('low'),
                'volume': ticker.get('quoteVolume'),
                'timestamp': ticker.get('timestamp')
            }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List:
        """Get OHLCV data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return []
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Get order book"""
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
            return {
                'symbol': symbol,
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'timestamp': orderbook.get('timestamp')
            }
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            return None
    
    def get_markets(self) -> List[Dict]:
        """Get available markets"""
        try:
            markets = self.exchange.fetch_markets()
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def create_order(self, symbol: str, order_type: str, side: str, 
                    amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """
        Create an order
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT)
            order_type: 'limit' or 'market'
            side: 'buy' or 'sell'
            amount: Amount to trade
            price: Price for limit orders
        """
        try:
            if order_type == 'limit' and price is None:
                raise ValueError("Price required for limit orders")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price
            )
            
            logger.info(f"✅ Order created: {side.upper()} {amount} {symbol} at {price}")
            return order
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    def get_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Get order details"""
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"Error fetching order: {e}")
            return None
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders"""
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []
    
    def get_closed_orders(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get closed orders"""
        try:
            orders = self.exchange.fetch_closed_orders(symbol, limit=limit)
            return orders
        except Exception as e:
            logger.error(f"Error fetching closed orders: {e}")
            return []
    
    def get_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        try:
            trades = self.exchange.fetch_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    def get_trading_fees(self, symbol: Optional[str] = None) -> Dict:
        """Get trading fees"""
        try:
            fees = self.exchange.fetch_trading_fees(symbol)
            return fees
        except Exception as e:
            logger.error(f"Error fetching trading fees: {e}")
            return {}
    
    def get_deposit_address(self, currency: str) -> Optional[str]:
        """Get deposit address for a currency"""
        try:
            address = self.exchange.fetch_deposit_address(currency)
            return address.get('address')
        except Exception as e:
            logger.error(f"Error fetching deposit address: {e}")
            return None
    
    def calculate_position_size(self, capital: float, risk_percentage: float, 
                               entry_price: float, stop_loss_price: float) -> float:
        """
        Calculate position size based on risk management
        
        Args:
            capital: Total capital
            risk_percentage: Risk percentage (e.g., 2%)
            entry_price: Entry price
            stop_loss_price: Stop loss price
        
        Returns:
            Position size in base currency
        """
        try:
            risk_amount = capital * (risk_percentage / 100)
            price_difference = abs(entry_price - stop_loss_price)
            
            if price_difference == 0:
                return 0
            
            position_size = risk_amount / price_difference
            return position_size
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def get_symbol_precision(self, symbol: str) -> Tuple[int, int]:
        """Get amount and price precision for a symbol"""
        try:
            market = self.exchange.market(symbol)
            amount_precision = market['precision']['amount']
            price_precision = market['precision']['price']
            return amount_precision, price_precision
        except Exception as e:
            logger.error(f"Error getting symbol precision: {e}")
            return 8, 8
    
    def round_amount(self, amount: float, symbol: str) -> float:
        """Round amount to symbol precision"""
        try:
            precision, _ = self.get_symbol_precision(symbol)
            return round(amount, precision)
        except Exception as e:
            logger.error(f"Error rounding amount: {e}")
            return amount
    
    def round_price(self, price: float, symbol: str) -> float:
        """Round price to symbol precision"""
        try:
            _, precision = self.get_symbol_precision(symbol)
            return round(price, precision)
        except Exception as e:
            logger.error(f"Error rounding price: {e}")
            return price


class OKXStreamData:
    """Handle OKX streaming data"""
    
    def __init__(self, exchange: ccxt.okx):
        """Initialize streaming data handler"""
        self.exchange = exchange
        self.last_update = {}
    
    def get_ticker_stream(self, symbols: List[str]) -> Dict:
        """Get ticker stream data"""
        try:
            data = {}
            for symbol in symbols:
                ticker = self.exchange.fetch_ticker(symbol)
                data[symbol] = {
                    'last': ticker.get('last'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'volume': ticker.get('quoteVolume'),
                    'timestamp': datetime.now().isoformat()
                }
            return data
        except Exception as e:
            logger.error(f"Error in ticker stream: {e}")
            return {}
    
    def get_depth_stream(self, symbol: str) -> Optional[Dict]:
        """Get depth stream data"""
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit=50)
            return {
                'symbol': symbol,
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error in depth stream: {e}")
            return None


# Example usage
if __name__ == "__main__":
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    
    # Your OKX credentials
    API_KEY = "your_api_key"
    API_SECRET = "your_api_secret"
    PASSPHRASE = "your_passphrase"
    
    # Create OKX integration
    okx = OKXIntegration(API_KEY, API_SECRET, PASSPHRASE)
    
    # Test connection
    if okx.test_connection():
        # Get balance
        balance = okx.get_balance()
        print(f"Balance: {balance}")
        
        # Get ticker
        ticker = okx.get_ticker("BTC/USDT")
        print(f"BTC/USDT: {ticker}")
        
        # Get OHLCV
        ohlcv = okx.get_ohlcv("BTC/USDT", "1h", 10)
        print(f"OHLCV: {ohlcv}")
