"""
Exchange Router — نظام توجيه الصفقات الثنائي
OKX: المنصة الرئيسية لجميع العملات المتاحة (Spot + Futures)
Bybit: للعملات الحصرية غير الموجودة على OKX + Futures
"""
import logging
import time
import json
import requests
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)

# ─── Cache لقوائم العملات ───────────────────────────────────────────
_okx_symbols_cache: Set[str] = set()
_bybit_symbols_cache: Set[str] = set()
_bybit_futures_cache: Set[str] = set()
_cache_time: float = 0
CACHE_TTL = 3600  # تحديث كل ساعة


def _refresh_symbol_caches():
    """تحديث قوائم العملات من OKX وBybit"""
    global _okx_symbols_cache, _bybit_symbols_cache, _bybit_futures_cache, _cache_time
    try:
        # OKX Spot
        r = requests.get(
            'https://www.okx.com/api/v5/market/tickers?instType=SPOT',
            timeout=10
        )
        data = r.json()
        _okx_symbols_cache = {
            item['instId'].replace('-USDT', '')
            for item in data.get('data', [])
            if item['instId'].endswith('-USDT')
        }

        # Bybit Spot
        r2 = requests.get(
            'https://api.bybit.com/v5/market/tickers?category=spot',
            timeout=10
        )
        data2 = r2.json()
        _bybit_symbols_cache = {
            item['symbol'].replace('USDT', '')
            for item in data2.get('result', {}).get('list', [])
            if item['symbol'].endswith('USDT')
        }

        # Bybit Linear Futures
        r3 = requests.get(
            'https://api.bybit.com/v5/market/tickers?category=linear',
            timeout=10
        )
        data3 = r3.json()
        _bybit_futures_cache = {
            item['symbol'].replace('USDT', '')
            for item in data3.get('result', {}).get('list', [])
            if item['symbol'].endswith('USDT')
        }

        _cache_time = time.time()
        logger.info(
            f"[Router] قوائم العملات: OKX={len(_okx_symbols_cache)} | "
            f"Bybit Spot={len(_bybit_symbols_cache)} | "
            f"Bybit Futures={len(_bybit_futures_cache)}"
        )
    except Exception as e:
        logger.warning(f"[Router] خطأ في تحديث قوائم العملات: {e}")


def _ensure_cache():
    """التأكد من أن الـ cache محدّث"""
    if time.time() - _cache_time > CACHE_TTL or not _okx_symbols_cache:
        _refresh_symbol_caches()


def _normalize(symbol: str) -> str:
    """تحويل BTC/USDT أو BTCUSDT إلى BTC"""
    return symbol.replace('/USDT', '').replace('USDT', '').replace('-USDT', '').upper()


class ExchangeRouter:
    """
    يوجّه الصفقات إلى المنصة الصحيحة:
    - OKX: المنصة الرئيسية لجميع العملات المتاحة (Spot + Futures)
    - Bybit: للعملات الحصرية (غير موجودة على OKX) + Futures
    """

    def __init__(self, okx_client, bybit_client=None):
        self.okx = okx_client
        self.bybit = bybit_client
        _ensure_cache()
        logger.info("[Router] ✅ Exchange Router initialized — OKX (primary) + Bybit (secondary)")

    def get_exchange_for_symbol(self, symbol: str, market: str = 'spot') -> str:
        """
        تحديد المنصة المناسبة للعملة والنوع
        Returns: 'okx' | 'bybit'
        """
        _ensure_cache()
        coin = _normalize(symbol)

        if market == 'futures':
            # Futures: OKX أولاً، إذا لم تكن متاحة → Bybit
            if coin in _okx_symbols_cache:
                return 'okx'
            elif self.bybit and self.bybit.is_available() and coin in _bybit_futures_cache:
                return 'bybit'
            return 'okx'  # fallback

        # Spot: OKX أولاً
        if coin in _okx_symbols_cache:
            return 'okx'
        # إذا غير موجودة على OKX → Bybit
        if self.bybit and self.bybit.is_available() and coin in _bybit_symbols_cache:
            return 'bybit'
        return 'okx'  # fallback

    def is_bybit_exclusive(self, symbol: str) -> bool:
        """هل العملة حصرية على Bybit (غير موجودة على OKX)؟"""
        _ensure_cache()
        coin = _normalize(symbol)
        return coin not in _okx_symbols_cache and coin in _bybit_symbols_cache

    def get_bybit_exclusive_symbols(self) -> Set[str]:
        """قائمة العملات الحصرية على Bybit"""
        _ensure_cache()
        return _bybit_symbols_cache - _okx_symbols_cache

    # ─── Spot Operations ────────────────────────────────────────────

    def spot_buy(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
        """شراء Spot على المنصة الصحيحة"""
        exchange = self.get_exchange_for_symbol(symbol, 'spot')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            logger.info(f"[Router] {symbol} → Bybit Spot (حصرية)")
            # Bybit يحتاج qty بـ USDT مع marketUnit=quoteCoin
            return self.bybit.place_spot_order(
                symbol=f"{coin}USDT",
                side='Buy',
                qty=amount_usdt,
                market_unit='quoteCoin'
            )
        else:
            logger.info(f"[Router] {symbol} → OKX Spot (رئيسية)")
            return self.okx.spot_buy(symbol, amount_usdt)

    def spot_sell(self, symbol: str, amount_coin: float, full_exit: bool = False) -> Optional[Dict]:
        """بيع Spot على المنصة الصحيحة"""
        exchange = self.get_exchange_for_symbol(symbol, 'spot')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            logger.info(f"[Router] {symbol} → Bybit Spot Sell (حصرية)")
            return self.bybit.place_spot_order(
                symbol=f"{coin}USDT",
                side='Sell',
                qty=amount_coin,
                market_unit='baseCoin'
            )
        else:
            logger.info(f"[Router] {symbol} → OKX Spot Sell (رئيسية)")
            return self.okx.spot_sell(symbol, amount_coin, full_exit)

    # ─── Futures Operations ─────────────────────────────────────────

    def futures_open_long(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
        """فتح Long Futures على المنصة الصحيحة"""
        exchange = self.get_exchange_for_symbol(symbol, 'futures')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            logger.info(f"[Router] {symbol} → Bybit Futures Long")
            return self.bybit.futures_open_long(f"{coin}USDT", amount_usdt)
        else:
            logger.info(f"[Router] {symbol} → OKX Futures Long (رئيسية)")
            return self.okx.futures_open_long(symbol, amount_usdt)

    def futures_open_short(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
        """فتح Short Futures على المنصة الصحيحة"""
        exchange = self.get_exchange_for_symbol(symbol, 'futures')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            logger.info(f"[Router] {symbol} → Bybit Futures Short")
            return self.bybit.futures_open_short(f"{coin}USDT", amount_usdt)
        else:
            logger.info(f"[Router] {symbol} → OKX Futures Short (رئيسية)")
            return self.okx.futures_open_short(symbol, amount_usdt)

    def futures_close_long(self, symbol: str, amount_coin: float) -> Optional[Dict]:
        """إغلاق Long Futures"""
        exchange = self.get_exchange_for_symbol(symbol, 'futures')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            return self.bybit.futures_close_long(f"{coin}USDT", amount_coin)
        return self.okx.futures_close_long(symbol, amount_coin)

    def futures_close_short(self, symbol: str, amount_coin: float) -> Optional[Dict]:
        """إغلاق Short Futures"""
        exchange = self.get_exchange_for_symbol(symbol, 'futures')
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            return self.bybit.futures_close_short(f"{coin}USDT", amount_coin)
        return self.okx.futures_close_short(symbol, amount_coin)

    # ─── Market Data ────────────────────────────────────────────────

    def get_ticker(self, symbol: str, market: str = 'spot') -> Optional[Dict]:
        """جلب السعر الحالي من المنصة الصحيحة"""
        exchange = self.get_exchange_for_symbol(symbol, market)
        coin = _normalize(symbol)

        if exchange == 'bybit' and self.bybit and self.bybit.is_available():
            price = self.bybit.get_price(f"{coin}USDT")
            if price:
                return {'price': price, 'symbol': symbol, 'exchange': 'bybit'}
        return self.okx.get_ticker(symbol, market)

    def get_balance(self) -> Dict:
        """
        جلب الرصيد من كلا المنصتين ودمجهما
        OKX هو المصدر الرئيسي، Bybit يُضاف إليه
        """
        balance = self.okx.get_balance()

        if self.bybit and self.bybit.is_available():
            bybit_bal = self.bybit.get_account_balance()
            if bybit_bal:
                bybit_usdt = bybit_bal.get('USDT', 0.0)
                # إضافة رصيد Bybit إلى الرصيد الإجمالي
                balance['bybit_usdt'] = bybit_usdt
                logger.debug(f"[Router] Bybit balance: {bybit_usdt} USDT")

        return balance

    def get_exchange_label(self, symbol: str, market: str = 'spot') -> str:
        """الحصول على اسم المنصة للعرض"""
        ex = self.get_exchange_for_symbol(symbol, market)
        return "Bybit" if ex == 'bybit' else "OKX"
