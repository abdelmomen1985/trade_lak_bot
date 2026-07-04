# ─── فلتر بصمة الحركة (Smart Money Pattern) ─────────────────────────────────
# النمط المستخلص من تحليل 12 عملة ارتفعت +3% بعد تنبيه الحجم الاستثنائي:
#   ✅ السعر فوق EMA50 على 4H  (92% من الحالات)
#   ✅ MACD إيجابي على 4H      (92% من الحالات)
#   ✅ RSI 4H في نطاق 40-75    (100% من الحالات)
#   ✅ OI صاعد >2% (آخر 8 ساعات) (75% من الحالات)
# القطاع لا يهم — النمط التقني هو المحدد

import requests

OKX_BASE = "https://www.okx.com/api/v5"


def _okx(path, params={}):
    try:
        r = requests.get(f"{OKX_BASE}{path}", params=params, timeout=10)
        return r.json().get('data', [])
    except Exception:
        return []


def _calc_ema(closes, p):
    if len(closes) < p:
        return None
    k = 2 / (p + 1)
    e = sum(closes[:p]) / p
    for c in closes[p:]:
        e = c * k + e * (1 - k)
    return e


def _calc_rsi(closes, p=14):
    if len(closes) < p + 1:
        return None
    g = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    l = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    ag = sum(g[-p:]) / p
    al = sum(l[-p:]) / p
    return 100 - (100 / (1 + ag / al)) if al > 0 else 100


def check_smart_money_pattern(coin: str) -> dict:
    """
    يفحص إذا كانت العملة تستوفي بصمة الحركة الكاملة.
    يُعيد dict مع: passed (bool), score (0-4), details (dict)
    الشروط:
      1. السعر فوق EMA50 على 4H
      2. MACD إيجابي على 4H
      3. RSI 4H في نطاق 40-75
      4. OI صاعد >2% (آخر 8 ساعات)
    يمر إذا تحققت 3 شروط من 4 على الأقل.
    """
    result = {
        'passed': False,
        'score': 0,
        'details': {},
        'above_ema50': False,
        'macd_positive': False,
        'rsi_in_range': False,
        'oi_rising': False,
        'rsi_value': None,
        'oi_change': None,
    }

    # جلب شموع 4H
    candles = _okx('/market/candles', {'instId': f'{coin}-USDT', 'bar': '4H', 'limit': '50'})
    if not candles or len(candles) < 26:
        return result

    # ترتيب من الأقدم للأحدث
    candles_r = candles[::-1]
    closes = [float(c[4]) for c in candles_r]
    price = closes[-1]

    # EMA50
    ema50 = _calc_ema(closes, 50)
    above_ema50 = price > ema50 if ema50 else False

    # MACD (EMA12 - EMA26)
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    macd_positive = (ema12 - ema26) > 0 if (ema12 and ema26) else False

    # RSI 4H
    rsi = _calc_rsi(closes, 14)
    rsi_in_range = (rsi is not None) and (40 <= rsi <= 75)

    # OI (آخر 8 ساعات)
    oi_hist = _okx('/rubik/stat/contracts/open-interest-volume', {'ccy': coin, 'period': '1H'})
    oi_change = None
    oi_rising = False
    if oi_hist and len(oi_hist) >= 8:
        try:
            oi_vals = [float(h[1]) for h in oi_hist[:8] if len(h) > 1]
            if len(oi_vals) >= 8 and oi_vals[-1] > 0:
                oi_change = (oi_vals[0] - oi_vals[-1]) / oi_vals[-1] * 100
                oi_rising = oi_change >= 2.0
        except Exception:
            pass

    score = sum([above_ema50, macd_positive, rsi_in_range, oi_rising])
    passed = score >= 3

    rsi_str = f"{rsi:.0f}" if rsi is not None else "N/A"
    oi_str = f"{oi_change:+.1f}%" if oi_change is not None else "N/A"

    result.update({
        'passed': passed,
        'score': score,
        'above_ema50': above_ema50,
        'macd_positive': macd_positive,
        'rsi_in_range': rsi_in_range,
        'oi_rising': oi_rising,
        'rsi_value': round(rsi, 1) if rsi is not None else None,
        'oi_change': round(oi_change, 2) if oi_change is not None else None,
        'details': {
            'EMA50':       'pass' if above_ema50 else 'fail',
            'MACD+':       'pass' if macd_positive else 'fail',
            'RSI(40-75)':  f"pass:{rsi_str}" if rsi_in_range else f"fail:{rsi_str}",
            'OI_rising':   f"pass:{oi_str}" if oi_rising else f"fail:{oi_str}",
        }
    })
    return result


# ─── قاموس القطاعات ───────────────────────────────────────────────────────────
COIN_SECTORS = {
    # Layer 1
    'BTC': 'Layer 1', 'ETH': 'Layer 1', 'SOL': 'Layer 1', 'BNB': 'Layer 1',
    'ADA': 'Layer 1', 'AVAX': 'Layer 1', 'ATOM': 'Layer 1', 'NEAR': 'Layer 1',
    'APT': 'Layer 1', 'SUI': 'Layer 1', 'SEI': 'Layer 1', 'TON': 'Layer 1',
    'TRX': 'Layer 1', 'XLM': 'Layer 1', 'ALGO': 'Layer 1', 'HBAR': 'Layer 1',
    'ICP': 'Layer 1', 'FTM': 'Layer 1', 'BERA': 'Layer 1', 'S': 'Layer 1',
    # Layer 2
    'ARB': 'Layer 2', 'OP': 'Layer 2', 'MATIC': 'Layer 2', 'IMX': 'Layer 2',
    'STRK': 'Layer 2', 'ZK': 'Layer 2', 'MANTA': 'Layer 2',
    # DeFi
    'UNI': 'DeFi', 'AAVE': 'DeFi', 'CRV': 'DeFi', 'MKR': 'DeFi',
    'COMP': 'DeFi', 'SNX': 'DeFi', 'SUSHI': 'DeFi', 'GMX': 'DeFi',
    'DYDX': 'DeFi', 'HYPE': 'DeFi', 'JUP': 'DeFi', 'PENDLE': 'DeFi',
    'ENA': 'DeFi', 'ETHFI': 'DeFi',
    # Oracle / Infrastructure
    'LINK': 'Oracle', 'BAND': 'Oracle', 'API3': 'Oracle',
    'GRT': 'Infrastructure', 'LPT': 'Infrastructure',
    # Privacy
    'XMR': 'Privacy', 'ZEC': 'Privacy', 'DASH': 'Privacy',
    'LIT': 'Privacy', 'SCRT': 'Privacy', 'ROSE': 'Privacy',
    # AI / Data
    'WLD': 'AI', 'FET': 'AI', 'AGIX': 'AI', 'OCEAN': 'AI',
    'TAO': 'AI', 'RENDER': 'AI', 'AKT': 'AI', 'IO': 'AI',
    # Storage / Web3
    'FIL': 'Storage', 'AR': 'Storage', 'STORJ': 'Storage', 'HNT': 'Storage',
    # Gaming / Metaverse
    'AXS': 'Gaming', 'SAND': 'Gaming', 'MANA': 'Gaming',
    'GALA': 'Gaming', 'BEAM': 'Gaming',
    # Meme
    'DOGE': 'Meme', 'SHIB': 'Meme', 'PEPE': 'Meme',
    'FLOKI': 'Meme', 'WIF': 'Meme', 'BONK': 'Meme',
    # Payments
    'XRP': 'Payments', 'LTC': 'Payments', 'BCH': 'Payments',
    # Staking / LST
    'LDO': 'Staking', 'RPL': 'Staking', 'ANKR': 'Staking', 'SSV': 'Staking',
    # Real World Assets
    'ONDO': 'RWA', 'PAXG': 'RWA', 'XAUT': 'RWA',
    # Derivatives
    'INJ': 'Derivatives',
    # Interop
    'DOT': 'Interop', 'RUNE': 'Interop', 'AXL': 'Interop', 'ZRO': 'Interop',
    # Exchange Tokens
    'OKB': 'Exchange Token', 'CRO': 'Exchange Token',
}


def get_sector(coin: str) -> str:
    """يُعيد اسم القطاع للعملة، أو 'Crypto' إذا لم تُعرف"""
    return COIN_SECTORS.get(coin.upper(), 'Crypto')
