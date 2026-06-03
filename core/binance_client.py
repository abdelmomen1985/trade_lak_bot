"""
Binance Client — Trade Lak Level 5
التداول على Binance كبورصة ثانية بجانب OKX
- مراقبة الأسعار على Binance لـ Statistical Arbitrage
- تنفيذ صفقات على Binance عند وجود فرصة أفضل
- مقارنة العمولات والسيولة بين البورصتين
"""

import logging
import time
from typing import Optional, Dict

logger = logging.getLogger(__name__)

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False


class BinanceClient:
    """
    عميل Binance — يعمل بمفاتيح API أو بدونها (للمراقبة فقط)
    بدون مفاتيح: يراقب الأسعار فقط لـ StatArb
    بمفاتيح: يمكنه تنفيذ صفقات حقيقية
    """

    # رسوم Binance
    MAKER_FEE = 0.001   # 0.1%
    TAKER_FEE = 0.001   # 0.1%

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.has_credentials = bool(api_key and api_secret)
        self._client = None
        self._price_cache: Dict[str, dict] = {}
        self._cache_ttl = 5  # 5 ثواني للكاش
        self._initialized = False
        self._init()

    def _init(self):
        """تهيئة الاتصال بـ Binance"""
        if not CCXT_AVAILABLE:
            logger.warning("[Binance] ccxt غير متاح")
            return

        try:
            params = {
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
            }
            if self.has_credentials:
                params['apiKey'] = self.api_key
                params['secret'] = self.api_secret

            self._client = ccxt.binance(params)
            # اختبار الاتصال
            self._client.load_markets()
            self._initialized = True
            mode = "مع مفاتيح API" if self.has_credentials else "مراقبة فقط (بدون مفاتيح)"
            logger.info(f"[Binance] ✅ متصل — {mode}")
        except Exception as e:
            logger.warning(f"[Binance] ⚠️ فشل الاتصال: {e}")
            self._initialized = False

    def get_price(self, symbol: str) -> Optional[float]:
        """
        جلب السعر من Binance مع كاش 5 ثواني
        symbol: مثل 'BTC/USDT'
        """
        if not self._initialized:
            return None

        # فحص الكاش
        cached = self._price_cache.get(symbol)
        if cached and time.time() - cached['time'] < self._cache_ttl:
            return cached['price']

        try:
            ticker = self._client.fetch_ticker(symbol)
            price = float(ticker['last'])
            self._price_cache[symbol] = {'price': price, 'time': time.time()}
            return price
        except Exception as e:
            logger.debug(f"[Binance] خطأ في جلب سعر {symbol}: {e}")
            return None

    def get_orderbook(self, symbol: str, limit: int = 5) -> Optional[dict]:
        """جلب Order Book من Binance"""
        if not self._initialized:
            return None
        try:
            ob = self._client.fetch_order_book(symbol, limit=limit)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            bid_vol = sum(q for _, q in bids)
            ask_vol = sum(q for _, q in asks)
            return {
                'bids': bids,
                'asks': asks,
                'best_bid': bids[0][0] if bids else 0,
                'best_ask': asks[0][0] if asks else 0,
                'bid_vol': bid_vol,
                'ask_vol': ask_vol,
                'imbalance': (bid_vol - ask_vol) / max(bid_vol + ask_vol, 1)
            }
        except Exception as e:
            logger.debug(f"[Binance] خطأ في Order Book {symbol}: {e}")
            return None

    def compare_price_with_okx(self, symbol: str, okx_price: float) -> dict:
        """
        مقارنة سعر Binance مع OKX لاكتشاف فرص StatArb
        يُعيد: {spread_pct, direction, opportunity}
        """
        binance_price = self.get_price(symbol)
        if not binance_price or not okx_price:
            return {'spread_pct': 0, 'direction': 'none', 'opportunity': False}

        spread_pct = (okx_price - binance_price) / binance_price * 100

        # فرصة إذا الفرق > 0.2% (بعد الرسوم 0.1% × 2)
        opportunity = abs(spread_pct) > 0.2

        direction = 'okx_cheaper' if spread_pct < 0 else 'binance_cheaper'

        return {
            'spread_pct': spread_pct,
            'direction': direction,
            'opportunity': opportunity,
            'binance_price': binance_price,
            'okx_price': okx_price,
            'profit_after_fees': abs(spread_pct) - 0.2  # الربح بعد الرسوم
        }

    def buy_market(self, symbol: str, usdt_amount: float) -> Optional[dict]:
        """
        تنفيذ أمر شراء بالسوق على Binance
        يتطلب مفاتيح API
        """
        if not self.has_credentials or not self._initialized:
            logger.warning("[Binance] لا يمكن التنفيذ — لا توجد مفاتيح API")
            return None

        try:
            price = self.get_price(symbol)
            if not price:
                return None
            qty = usdt_amount / price
            # تقريب الكمية حسب دقة Binance
            market = self._client.market(symbol)
            qty = self._client.amount_to_precision(symbol, qty)

            order = self._client.create_market_buy_order(symbol, float(qty))
            logger.info(f"[Binance] ✅ شراء {symbol}: {qty} @ ~${price:.4f}")
            return order
        except Exception as e:
            logger.error(f"[Binance] ❌ خطأ في الشراء: {e}")
            return None

    def sell_market(self, symbol: str, qty: float) -> Optional[dict]:
        """تنفيذ أمر بيع بالسوق على Binance"""
        if not self.has_credentials or not self._initialized:
            return None

        try:
            qty_str = self._client.amount_to_precision(symbol, qty)
            order = self._client.create_market_sell_order(symbol, float(qty_str))
            logger.info(f"[Binance] ✅ بيع {symbol}: {qty_str}")
            return order
        except Exception as e:
            logger.error(f"[Binance] ❌ خطأ في البيع: {e}")
            return None

    def get_balance(self) -> Optional[dict]:
        """جلب الرصيد من Binance"""
        if not self.has_credentials or not self._initialized:
            return None
        try:
            bal = self._client.fetch_balance()
            return {
                'free': bal['free'].get('USDT', 0),
                'total': bal['total'].get('USDT', 0),
            }
        except Exception as e:
            logger.error(f"[Binance] خطأ في جلب الرصيد: {e}")
            return None

    def is_available(self) -> bool:
        """هل Binance متاح للاستخدام؟"""
        return self._initialized

    def is_trading_enabled(self) -> bool:
        """هل التداول على Binance مفعّل؟"""
        return self._initialized and self.has_credentials
