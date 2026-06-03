"""
Bybit Client — RSA Authentication Version
يدعم توقيع RSA-SHA256 كما يتطلب Bybit AI Skill
"""

import time
import hashlib
import logging
import requests
import json
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

BYBIT_MAKER_FEE = 0.001
BYBIT_TAKER_FEE = 0.001
OKX_TAKER_FEE   = 0.001
MIN_PROFIT_PCT   = 0.05  # 0.05% صافي بعد الرسوم


def _rsa_sign(param_str: str, private_key_path: str) -> str:
    """توقيع RSA-SHA256 PKCS#1 v1.5"""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        with open(private_key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        signature = private_key.sign(param_str.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())
        import base64
        return base64.b64encode(signature).decode('utf-8')
    except ImportError:
        # fallback: استخدام subprocess + openssl
        import subprocess, base64
        result = subprocess.run(
            ['openssl', 'dgst', '-sha256', '-sign', private_key_path, '-binary'],
            input=param_str.encode('utf-8'),
            capture_output=True
        )
        return base64.b64encode(result.stdout).decode('utf-8')


class BybitClient:
    """
    Bybit Client مع RSA Authentication
    """
    BASE_URL = 'https://api.bybit.com'

    def __init__(self, api_key: str = '', api_secret: str = '',
                 private_key_path: str = ''):
        self.api_key          = api_key
        self.api_secret       = api_secret
        self.private_key_path = private_key_path
        self._available       = False
        self._session         = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'bybit-skill/1.4.1',
            'X-Referer': 'bybit-skill',
        })

        # تحديد نوع التوقيع
        if private_key_path and Path(private_key_path).exists():
            self._sign_type = 'RSA'
            self._sign_type_header = '2'
        elif api_secret:
            self._sign_type = 'HMAC'
            self._sign_type_header = '1'
        else:
            self._sign_type = 'NONE'
            self._sign_type_header = ''

        self.has_keys = bool(api_key and self._sign_type != 'NONE')
        self._test_connection()

    def _make_signature(self, param_str: str) -> str:
        if self._sign_type == 'RSA':
            return _rsa_sign(param_str, self.private_key_path)
        elif self._sign_type == 'HMAC':
            import hmac
            return hmac.new(
                self.api_secret.encode('utf-8'),
                param_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        return ''

    def _auth_headers(self, param_str: str, timestamp: str) -> Dict:
        sign = self._make_signature(param_str)
        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': sign,
            'X-BAPI-RECV-WINDOW': '5000',
        }
        if self._sign_type_header:
            headers['X-BAPI-SIGN-TYPE'] = self._sign_type_header
        return headers

    def _test_connection(self):
        try:
            r = self._session.get(f'{self.BASE_URL}/v5/market/time', timeout=5)
            if r.status_code == 200 and r.json().get('retCode') == 0:
                self._available = True
                mode = f'RSA ({Path(self.private_key_path).name})' if self._sign_type == 'RSA' else \
                       'HMAC' if self._sign_type == 'HMAC' else 'مراقبة فقط'
                logger.info(f'[Bybit] ✅ متصل — {mode}')
            else:
                logger.warning(f'[Bybit] ⚠️ استجابة غير متوقعة')
        except Exception as e:
            logger.warning(f'[Bybit] ⚠️ فشل الاتصال: {e}')
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def get_price(self, symbol: str) -> Optional[float]:
        if not self._available:
            return None
        try:
            sym = symbol.replace('/', '').replace('-', '')
            r = self._session.get(
                f'{self.BASE_URL}/v5/market/tickers',
                params={'category': 'spot', 'symbol': sym},
                timeout=5
            )
            data = r.json()
            if data.get('retCode') == 0:
                items = data.get('result', {}).get('list', [])
                if items:
                    return float(items[0]['lastPrice'])
        except Exception as e:
            logger.debug(f'[Bybit] خطأ في جلب سعر {symbol}: {e}')
        return None

    def compare_price_with_okx(self, symbol: str, okx_price: float) -> Dict:
        result = {
            'opportunity': False,
            'bybit_price': 0.0,
            'okx_price': okx_price,
            'spread_pct': 0.0,
            'direction': '',
            'profit_after_fees': 0.0
        }
        bybit_price = self.get_price(symbol)
        if not bybit_price or bybit_price <= 0:
            return result
        result['bybit_price'] = bybit_price
        spread = abs(bybit_price - okx_price) / okx_price * 100
        result['spread_pct'] = spread
        total_fees = (OKX_TAKER_FEE + BYBIT_TAKER_FEE) * 100
        profit_after_fees = spread - total_fees
        result['profit_after_fees'] = profit_after_fees
        result['direction'] = 'okx_cheaper' if bybit_price > okx_price else 'bybit_cheaper'
        if profit_after_fees >= MIN_PROFIT_PCT:
            result['opportunity'] = True
        return result

    def get_account_balance(self) -> Optional[Dict]:
        if not self.has_keys or not self._available:
            return None
        try:
            timestamp = str(int(time.time() * 1000))
            recv_window = '5000'
            query = 'accountType=UNIFIED'
            param_str = f'{timestamp}{self.api_key}{recv_window}{query}'
            headers = self._auth_headers(param_str, timestamp)
            r = self._session.get(
                f'{self.BASE_URL}/v5/account/wallet-balance',
                params={'accountType': 'UNIFIED'},
                headers=headers,
                timeout=10
            )
            data = r.json()
            if data.get('retCode') == 0:
                coins = data.get('result', {}).get('list', [{}])[0].get('coin', [])
                return {c['coin']: float(c['walletBalance']) for c in coins
                        if float(c.get('walletBalance', 0)) > 0}
        except Exception as e:
            logger.error(f'[Bybit] خطأ في جلب الرصيد: {e}')
        return None

    def place_spot_order(self, symbol: str, side: str, qty: float,
                         order_type: str = 'Market',
                         market_unit: str = 'baseCoin') -> Optional[Dict]:
        """
        تنفيذ أمر Spot على Bybit
        side: 'Buy' | 'Sell'
        market_unit: 'baseCoin' (qty بالعملة) | 'quoteCoin' (qty بـ USDT)
        """
        if not self.has_keys or not self._available:
            logger.warning('[Bybit] لا يمكن التداول — مفاتيح API غير مُعدَّة')
            return None
        try:
            timestamp = str(int(time.time() * 1000))
            recv_window = '5000'
            sym = symbol.replace('/', '').replace('-', '')
            body = {
                'category': 'spot',
                'symbol': sym,
                'side': side,
                'orderType': order_type,
                'qty': str(qty),
                'marketUnit': market_unit,
            }
            body_str = json.dumps(body, separators=(',', ':'))
            param_str = f'{timestamp}{self.api_key}{recv_window}{body_str}'
            headers = self._auth_headers(param_str, timestamp)
            r = self._session.post(
                f'{self.BASE_URL}/v5/order/create',
                data=body_str,
                headers=headers,
                timeout=10
            )
            data = r.json()
            if data.get('retCode') == 0:
                order_id = data.get('result', {}).get('orderId', '')
                logger.info(f'[Bybit] ✅ {side} {qty} {sym} — OrderID: {order_id}')
                return data.get('result', {})
            else:
                logger.error(f'[Bybit] ❌ فشل الأمر: {data.get("retMsg")}')
        except Exception as e:
            logger.error(f'[Bybit] ❌ خطأ: {e}')
        return None


def create_bybit_client(api_key: str = '', api_secret: str = '',
                        private_key_path: str = '') -> BybitClient:
    return BybitClient(api_key=api_key, api_secret=api_secret,
                       private_key_path=private_key_path)
