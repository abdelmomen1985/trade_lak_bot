# ============================================================
# Trade Lak Bot - OKX Exchange Client (Spot + Futures)
# وحدة الاتصال بمنصة OKX — سبوت وفيوتشر
# ============================================================

import ccxt
import logging
from config.config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    FUTURES_LEVERAGE, DRY_RUN,
    SPOT_CAPITAL_PCT, FUTURES_CAPITAL_PCT, TOTAL_CAPITAL
)

logger = logging.getLogger(__name__)


class OKXClient:
    """
    يتعامل مع منصة OKX لتنفيذ صفقات Spot و Futures
    Handles OKX for both Spot and Futures trading
    """

    def __init__(self):
        # عميل Spot
        self.spot = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET_KEY,
            'password': OKX_PASSPHRASE,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        # عميل Futures (Swap)
        self.futures = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET_KEY,
            'password': OKX_PASSPHRASE,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        })

        if DRY_RUN:
            self.spot.set_sandbox_mode(True)
            self.futures.set_sandbox_mode(True)
            logger.info("وضع الاختبار مفعّل (Dry Run) — لا صفقات حقيقية")

        # استخدم spot كـ exchange افتراضي للـ Market Scanner
        self.exchange = self.spot
        logger.info("تم الاتصال بـ OKX (Spot + Futures)")
    # ----------------------------------------------------------------
    # تصنيف الأسواق / Market Classification
    # ----------------------------------------------------------------
    def get_available_markets(self):
        """
        جلب وتصنيف جميع العملات المتاحة على OKX
        Returns dict: spot, futures, both, spot_only, futures_only
        مع cache لتجنب الطلبات المتكررة
        """
        if hasattr(self, '_market_cache') and self._market_cache:
            return self._market_cache
        try:
            markets = self.spot.load_markets()
            spot_bases = set()
            swap_bases = set()
            for sym, mkt in markets.items():
                if not mkt.get('active'):
                    continue
                mtype = mkt.get('type', '')
                if mtype == 'spot' and '/USDT' in sym and ':' not in sym:
                    spot_bases.add(sym.split('/')[0])
                elif mtype == 'swap' and 'USDT' in sym:
                    swap_bases.add(sym.split('/')[0])
            both = spot_bases & swap_bases
            self._market_cache = {
                'spot': spot_bases,
                'futures': swap_bases,
                'both': both,
                'spot_only': spot_bases - swap_bases,
                'futures_only': swap_bases - spot_bases,
            }
            logger.info(
                f"أسواق OKX: {len(spot_bases)} Spot | "
                f"{len(swap_bases)} Futures | {len(both)} كلاهما"
            )
            return self._market_cache
        except Exception as e:
            logger.warning(f"خطأ في جلب الأسواق: {e}")
            return {'spot': set(), 'futures': set(), 'both': set(),
                    'spot_only': set(), 'futures_only': set()}

    def get_market_type(self, symbol: str) -> str:
        """
        تحديد نوع السوق المتاح لعملة معينة على OKX
        Returns: 'both' | 'spot' | 'futures' | 'none'
        """
        base = symbol.replace('/USDT', '')
        markets = self.get_available_markets()
        in_spot = base in markets.get('spot', set())
        in_futures = base in markets.get('futures', set())
        if in_spot and in_futures:
            return 'both'
        elif in_spot:
            return 'spot'
        elif in_futures:
            return 'futures'
        else:
            return 'none'



    # ----------------------------------------------------------------
    # بيانات السوق / Market Data
    # ----------------------------------------------------------------

    def get_balance(self):
        """جلب الرصيد الكامل — ديناميكي من OKX"""
        try:
            bal = self.spot.fetch_balance()
            usdt_free  = bal['free'].get('USDT', 0)
            usdt_total = bal['total'].get('USDT', 0)

            # ── رأس المال الديناميكي: يعتمد على الرصيد الحقيقي ──
            # نستخدم usdt_total (الكلي) كأساس للتخصيص
            # مع حد أدنى $100 لتجنب الأخطاء عند الرصيد الصفري
            dynamic_capital = max(usdt_total, 100.0)  # الرصيد الحقيقي فقط — لا قيم مُرمَّزة
            spot_alloc    = dynamic_capital * SPOT_CAPITAL_PCT
            futures_alloc = dynamic_capital * FUTURES_CAPITAL_PCT

            logger.info(
                f"الرصيد: ${usdt_free:.2f} متاح | الكلي: ${usdt_total:.2f} | "
                f"Spot مخصص: ${spot_alloc:.0f} | Futures مخصص: ${futures_alloc:.0f}"
            )
            return {
                'free': usdt_free, 'total': usdt_total,
                'spot_allocated': spot_alloc,
                'futures_allocated': futures_alloc,
                'dynamic_capital': dynamic_capital
            }
        except Exception as e:
            logger.error(f"خطأ في جلب الرصيد: {e}")
            return {'free': 0, 'total': 0, 'spot_allocated': 0, 'futures_allocated': 0, 'dynamic_capital': TOTAL_CAPITAL}

    def get_ticker(self, symbol, market='spot'):
        """جلب السعر الحالي"""
        try:
            client = self.spot if market == 'spot' else self.futures
            fsymbol = symbol if market == 'spot' else symbol.replace('/USDT', '/USDT:USDT')
            ticker = client.fetch_ticker(fsymbol)
            return {
                'symbol': symbol, 'price': ticker['last'],
                'bid': ticker['bid'], 'ask': ticker['ask'],
                'volume': ticker.get('baseVolume', 0),
                'change_pct': ticker.get('percentage', 0)
            }
        except Exception as e:
            logger.error(f"خطأ في جلب سعر {symbol}: {e}")
            return None

    def get_ohlcv(self, symbol, timeframe='1h', limit=100):
        """جلب بيانات الشموع من Spot"""
        try:
            return self.spot.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            logger.error(f"خطأ في جلب شموع {symbol}: {e}")
            return []

    # ----------------------------------------------------------------
    # تنفيذ صفقات Spot / Spot Orders
    # ----------------------------------------------------------------

    def spot_buy(self, symbol, amount_usdt):
        """شراء Spot — يُعيد الكمية الفعلية المُنفَّذة مع مراعاة الرسوم"""
        try:
            ticker = self.get_ticker(symbol, 'spot')
            if not ticker:
                return None
            price = ticker['price']
            amount_coin = amount_usdt / price
            order = self.spot.create_market_buy_order(symbol, amount_coin)
            # ── استخراج الكمية الفعلية من الأوردر مباشرة (بعد خصم رسوم المنصة) ──
            if order:
                # order['filled'] = الكمية الفعلية المُنفَّذة من OKX
                # لا نستخدم fetch_balance لأنه يعيد الرصيد الكلي وليس الكمية الجديدة فقط
                filled = order.get('filled', 0) or 0
                if not filled or filled <= 0:
                    # fallback: حساب نظري مع خصم 0.1% رسوم
                    filled = amount_coin * 0.999
                # تخزين الكمية الفعلية في الأوردر للاستخدام في main.py
                order['actual_filled_coin'] = filled
                logger.info(
                    f"Spot شراء: {symbol} | ${amount_usdt:.2f} | "
                    f"السعر: {price:.6f} | "
                    f"كمية مُنفَّذة: {filled:.6f} (طُلب: {amount_coin:.6f})"
                )
            return order
        except Exception as e:
            logger.error(f"خطأ Spot شراء {symbol}: {e}")
            return None

    def spot_sell(self, symbol, amount_coin, full_exit=False):
        """بيع Spot — يستخدم الرصيد الفعلي من OKX لتجنب خطأ insufficient balance
        full_exit=True: يبيع كامل الرصيد المتاح (لإغلاق الصفقة بالكامل)
        full_exit=False: يبيع الكمية المحددة فقط (للبيع الجزئي)
        """
        try:
            base_currency = symbol.split('/')[0]
            try:
                bal = self.spot.fetch_balance()
                actual_free = bal['free'].get(base_currency, 0)
                if actual_free > 0:
                    if full_exit:
                        # إغلاق كامل: بيع كل الرصيد المتاح بدون خصم
                        sell_qty = actual_free
                        logger.info(f"Spot بيع كامل: {symbol} | مُسجَّل={amount_coin:.6f} | فعلي={actual_free:.6f} | بيع={sell_qty:.6f} (100%)")
                    else:
                        # بيع جزئي: استخدام الكمية المحددة مع هامش 0.5%
                        sell_qty = min(amount_coin, actual_free * 0.999)
                        if sell_qty < amount_coin * 0.5:
                            sell_qty = actual_free
                        logger.info(f"Spot بيع جزئي: {symbol} | مُسجَّل={amount_coin:.6f} | فعلي={actual_free:.6f} | بيع={sell_qty:.6f}")
                    amount_coin = sell_qty
                else:
                    logger.warning(f"⚠️ رصيد {base_currency} = 0 على OKX، محاولة البيع بالكمية المُسجَّلة")
            except Exception as bal_err:
                logger.warning(f"⚠️ فشل جلب رصيد {base_currency}: {bal_err} — استخدام الكمية المُسجَّلة")
            order = self.spot.create_market_sell_order(symbol, amount_coin)
            logger.info(f"Spot بيع: {symbol} | الكمية: {amount_coin:.6f}")
            return order
        except Exception as e:
            logger.error(f"خطأ Spot بيع {symbol}: {e}")
            return None

    # ----------------------------------------------------------------
    # تنفيذ صفقات Futures / Futures Orders
    # ----------------------------------------------------------------

    def _futures_symbol(self, symbol):
        """تحويل رمز Spot إلى رمز Futures"""
        return symbol.replace('/USDT', '/USDT:USDT')

    def set_leverage(self, symbol, leverage=None):
        """ضبط الرافعة المالية"""
        lev = leverage or FUTURES_LEVERAGE
        try:
            fsymbol = self._futures_symbol(symbol)
            self.futures.set_leverage(lev, fsymbol)
            logger.info(f"الرافعة المالية لـ {symbol}: {lev}x")
        except Exception as e:
            logger.warning(f"تحذير ضبط الرافعة لـ {symbol}: {e}")

    def futures_open_long(self, symbol, amount_usdt):
        """فتح صفقة Futures Long (شراء)"""
        try:
            self.set_leverage(symbol)
            fsymbol = self._futures_symbol(symbol)
            ticker  = self.get_ticker(symbol, 'futures')
            if not ticker:
                return None
            amount_coin = (amount_usdt * FUTURES_LEVERAGE) / ticker['price']
            order = self.futures.create_market_buy_order(
                fsymbol, amount_coin,
                params={'tdMode': 'cross', 'posSide': 'long'}
            )
            logger.info(f"Futures LONG: {symbol} | ${amount_usdt:.2f} × {FUTURES_LEVERAGE}x | السعر: {ticker['price']:.6f}")
            return order
        except Exception as e:
            logger.error(f"خطأ Futures Long {symbol}: {e}")
            return None

    def futures_open_short(self, symbol, amount_usdt):
        """فتح صفقة Futures Short (بيع)"""
        try:
            self.set_leverage(symbol)
            fsymbol = self._futures_symbol(symbol)
            ticker  = self.get_ticker(symbol, 'futures')
            if not ticker:
                return None
            amount_coin = (amount_usdt * FUTURES_LEVERAGE) / ticker['price']
            order = self.futures.create_market_sell_order(
                fsymbol, amount_coin,
                params={'tdMode': 'cross', 'posSide': 'short'}
            )
            logger.info(f"Futures SHORT: {symbol} | ${amount_usdt:.2f} × {FUTURES_LEVERAGE}x | السعر: {ticker['price']:.6f}")
            return order
        except Exception as e:
            logger.error(f"خطأ Futures Short {symbol}: {e}")
            return None

    def futures_close_long(self, symbol, amount_coin):
        """إغلاق صفقة Futures Long"""
        try:
            fsymbol = self._futures_symbol(symbol)
            order = self.futures.create_market_sell_order(
                fsymbol, amount_coin,
                params={'tdMode': 'cross', 'posSide': 'long', 'reduceOnly': True}
            )
            logger.info(f"إغلاق Futures LONG: {symbol}")
            return order
        except Exception as e:
            logger.error(f"خطأ إغلاق Futures Long {symbol}: {e}")
            return None

    def futures_close_short(self, symbol, amount_coin):
        """إغلاق صفقة Futures Short"""
        try:
            fsymbol = self._futures_symbol(symbol)
            order = self.futures.create_market_buy_order(
                fsymbol, amount_coin,
                params={'tdMode': 'cross', 'posSide': 'short', 'reduceOnly': True}
            )
            logger.info(f"إغلاق Futures SHORT: {symbol}")
            return order
        except Exception as e:
            logger.error(f"خطأ إغلاق Futures Short {symbol}: {e}")
            return None
