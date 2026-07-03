"""
Trade Lak - Accumulation Alert System v2
نظام تنبيهات التراكم الصامت — يعتمد على OKX API فقط (بدون Coinglass)

المنطق:
- كل 15 دقيقة يجلب أعلى 30 عملة بـ OI من OKX (قائمة ديناميكية)
- لكل عملة يفحص 5 شروط:
  1. OI ارتفع > +0.5% في ساعة
  2. Funding محايد أو سلبي (< 0.01%)
  3. Volume يرتفع > +2%
  4. Long/Short Ratio يتحسن (أغلبية Long تزيد)
  5. OI يرتفع على 4 ساعات أيضاً (تراكم مستمر)

تنبيه 1: 3+ شروط → تراكم أولي
تنبيه 2: 4+ شروط → تراكم متصاعد
"""
import requests
import logging
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pattern_filter import check_smart_money_pattern

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/root/trade_lak_bot/accumulation_alert.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

# ─── إعدادات ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
TELEGRAM_CHANNEL_ID = "-1003942444248"   # Trade Lak Liquidity
OKX_BASE            = "https://www.okx.com/api/v5"
STATE_FILE          = "/root/trade_lak_bot/accumulation_state.json"
SCAN_INTERVAL       = 15 * 60           # 15 دقيقة

# ─── حدود التنبيه ─────────────────────────────────────────────────────────────
ALERT1_OI_RISE_MIN       = 0.5    # OI ارتفع +0.5% في ساعة
ALERT1_FUNDING_MAX       = 0.0001 # Funding < 0.01%
ALERT1_VOL_RISE_MIN      = 2.0    # Volume ارتفع +2%
ALERT1_MIN_CONDITIONS    = 3

ALERT2_OI_RISE_MIN       = 1.0    # OI ارتفع +1% في ساعة
ALERT2_FUNDING_MAX       = 0.00005
ALERT2_VOL_RISE_MIN      = 8.0
ALERT2_MIN_CONDITIONS    = 4
ALERT2_COOLDOWN_MINUTES  = 30

# ─── فلتر العملات الغريبة (أسهم، معادن، stablecoins) ─────────────────────────
EXCLUDE_COINS = {
    # أسهم
    'MU','SPCX','SNDK','SLX','SOXL','SKHYNIX','INTC','MRVL','O','MSFT','RDDT',
    'HPE','WDC','MSTR','ASML','IREN','LPT','FLNC','NVDA','QQQ','CRCL',
    # معادن وسلع
    'XAU','XAG','XCU','XPT','XPD','CL','BZ',
    # stablecoins
    'USDC','USDT','BUSD','DAI','USDG','RLUSD','RESOLV',
    # عملات غير معروفة / سيولة مصطنعة
    'LAB','H','BEAT','NES','IP','ZBT','KITE','EWT','KGEN','LITE','ACU',
    'EDGE','ZKP','OL','SYRUP','WAL','VANA','PUMP','LAYER','GIGGLE',
    'NEIRO','MEME','PI','RIVER','COAI','ASTER','DRAM',
}


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

# ─── مساعد تنسيق السعر ────────────────────────────────────────────────────────
def _fmt_price(price: float) -> str:
    if not price or price <= 0: return "—"
    if price >= 1000:   return f"${price:,.2f}"
    elif price >= 1:    return f"${price:.4f}"
    elif price >= 0.01: return f"${price:.6f}"
    elif price >= 0.0001: return f"${price:.8f}"
    else: return f"${price:.10f}".rstrip('0').rstrip('.')

# ─── OKX API helpers ──────────────────────────────────────────────────────────
def _okx_get(path: str, params: dict = None) -> dict:
    try:
        r = requests.get(f"{OKX_BASE}{path}", params=params or {}, timeout=10)
        return r.json()
    except Exception as e:
        logger.warning(f"OKX GET {path} error: {e}")
        return {}

def get_top_coins_by_oi(min_oi_usd: float = 10_000_000, top_n: int = 35) -> List[str]:
    """جلب أعلى العملات بـ OI من OKX (قائمة ديناميكية)"""
    try:
        # جلب OI
        oi_data = _okx_get('/public/open-interest', {'instType': 'SWAP'})
        # جلب الأسعار
        tickers_data = _okx_get('/market/tickers', {'instType': 'SWAP'})
        prices = {t['instId']: float(t.get('last', 0) or 0)
                  for t in tickers_data.get('data', [])}

        results = []
        for item in oi_data.get('data', []):
            inst_id = item.get('instId', '')
            if not inst_id.endswith('-USDT-SWAP'):
                continue
            coin = inst_id.replace('-USDT-SWAP', '')
            if coin in EXCLUDE_COINS:
                continue
            price = prices.get(inst_id, 0)
            oi_contracts = float(item.get('oi', 0) or 0)
            oi_usd = oi_contracts * price
            if oi_usd >= min_oi_usd:
                results.append((coin, oi_usd))

        results.sort(key=lambda x: x[1], reverse=True)
        coins = [c[0] for c in results[:top_n]]
        logger.info(f"📋 قائمة ديناميكية: {len(coins)} عملة (OI > ${min_oi_usd/1e6:.0f}M)")
        return coins
    except Exception as e:
        logger.error(f"get_top_coins_by_oi error: {e}")
        # fallback ثابت
        return ['BTC','ETH','SOL','BNB','XRP','DOGE','AVAX','LINK','UNI',
                'AAVE','INJ','SUI','NEAR','APT','ARB','OP','BCH','LTC',
                'TRX','DOT','ATOM','HYPE','TAO','WLD','ORDI','FIL','ICP']

def get_oi_history(coin: str, period: str = '1H', limit: int = 5) -> List[float]:
    """جلب تاريخ OI لعملة (بالدولار)"""
    d = _okx_get('/rubik/stat/contracts/open-interest-volume',
                 {'ccy': coin, 'period': period})
    rows = d.get('data', [])[:limit]
    # كل صف: [timestamp, oi_usd, vol_usd]
    return [float(r[1]) for r in rows]

def get_funding_rate(coin: str) -> float:
    """جلب Funding Rate الحالي"""
    d = _okx_get('/public/funding-rate', {'instId': f"{coin}-USDT-SWAP"})
    items = d.get('data', [])
    if items:
        val = items[0].get('fundingRate', '') or '0'
        try:
            return float(val)
        except:
            return 0.0
    return 0.0

def get_long_short_ratio(coin: str) -> float:
    """جلب نسبة Long/Short (> 1 = أغلبية Long)"""
    d = _okx_get('/rubik/stat/contracts/long-short-account-ratio',
                 {'ccy': coin, 'period': '1H'})
    rows = d.get('data', [])
    if rows and len(rows) >= 2:
        current = float(rows[0][1])
        prev    = float(rows[1][1])
        return current, prev
    elif rows:
        return float(rows[0][1]), 1.0
    return 1.0, 1.0

def get_price(coin: str) -> float:
    """جلب السعر الحالي"""
    d = _okx_get('/market/ticker', {'instId': f"{coin}-USDT-SWAP"})
    items = d.get('data', [])
    if items:
        return float(items[0].get('last', 0) or 0)
    return 0.0

# ─── تحليل عملة واحدة ────────────────────────────────────────────────────────
def get_last_candle(coin: str) -> dict:
    """جلب بيانات الشمعة الاخيرة (1H) للتحقق من اتجاه الحركة"""
    try:
        d = _okx_get('/market/candles', {'instId': f"{coin}-USDT", 'bar': '1H', 'limit': '2'})
        rows = d.get('data', [])
        if rows:
            row = rows[0]
            open_p  = float(row[1])
            close_p = float(row[4])
            return {
                'open':     open_p,
                'close':    close_p,
                'is_green': close_p > open_p,
                'body_pct': (close_p - open_p) / open_p * 100 if open_p > 0 else 0,
            }
    except Exception:
        pass
    return {'open': 0, 'close': 0, 'is_green': True, 'body_pct': 0}


def analyze_coin(coin: str) -> Optional[Dict]:
    """تحليل عملة وإرجاع نتيجة التراكم"""
    try:
        # جلب تاريخ OI (آخر 5 ساعات)
        oi_h1 = get_oi_history(coin, '1H', 5)
        oi_h4 = get_oi_history(coin, '4H', 3)

        if len(oi_h1) < 2:
            return None

        # حساب التغير
        oi_now_h1   = oi_h1[0]
        oi_prev_h1  = oi_h1[1]
        h1_oi_chg   = ((oi_now_h1 - oi_prev_h1) / oi_prev_h1 * 100) if oi_prev_h1 > 0 else 0

        h4_oi_chg = 0.0
        if len(oi_h4) >= 2 and oi_h4[1] > 0:
            h4_oi_chg = (oi_h4[0] - oi_h4[1]) / oi_h4[1] * 100

        # Volume من نفس البيانات (العمود الثالث)
        d_vol = _okx_get('/rubik/stat/contracts/open-interest-volume',
                         {'ccy': coin, 'period': '1H'})
        vol_rows = d_vol.get('data', [])
        h1_vol_chg = 0.0
        if len(vol_rows) >= 2:
            v_now  = float(vol_rows[0][2])
            v_prev = float(vol_rows[1][2])
            if v_prev > 0:
                h1_vol_chg = (v_now - v_prev) / v_prev * 100

        # Funding Rate
        funding = get_funding_rate(coin)

        # Long/Short Ratio
        ls_current, ls_prev = get_long_short_ratio(coin)
        ls_improving = ls_current > ls_prev  # نسبة Long تزيد

        # السعر
        price = get_price(coin)
        # فحص اتجاه الشمعة الاخيرة
        candle = get_last_candle(coin)
        is_green_candle = candle['is_green']
        candle_body_pct = candle['body_pct']

        # ─── تقييم الشروط ──────────────────────────────────────────────────
        conditions = {
            'oi_rising': {
                'met': h1_oi_chg >= ALERT1_OI_RISE_MIN,
                'value': h1_oi_chg,
                'label': f"OI {h1_oi_chg:+.2f}% (1h)"
            },
            'funding_neutral': {
                'met': funding <= ALERT1_FUNDING_MAX,
                'value': funding,
                'label': f"Funding {funding*100:+.4f}%"
            },
            'vol_rising': {
                'met': h1_vol_chg >= ALERT1_VOL_RISE_MIN,
                'value': h1_vol_chg,
                'label': f"Volume {h1_vol_chg:+.1f}% (1h)"
            },
            'ls_improving': {
                'met': ls_improving,
                'value': ls_current,
                'label': f"L/S Ratio {ls_current:.3f} ({'↑' if ls_improving else '↓'})"
            },
            'oi_sustained': {
                'met': h4_oi_chg >= 0.5,
                'value': h4_oi_chg,
                'label': f"OI {h4_oi_chg:+.2f}% (4h)"
            },
        }

        conditions['candle_green'] = {
            'met': is_green_candle,
            'value': candle_body_pct,
            'label': 'Candle Green' if is_green_candle else 'Candle Red',
        }
        met_count = sum(1 for c in conditions.values() if c['met'])

        return {
            'symbol':       coin,
            'price':        price,
            'conditions':   conditions,
            'met_count':    met_count,
            'h1_oi_chg':    h1_oi_chg,
            'h4_oi_chg':    h4_oi_chg,
            'h1_vol_chg':   h1_vol_chg,
            'avg_funding':  funding,
            'ls_current':   ls_current,
            'ls_improving':    ls_improving,
            'is_green_candle': is_green_candle,
            'candle_body_pct': candle_body_pct,
        }
    except Exception as e:
        logger.error(f"analyze_coin({coin}) error: {e}")
        return None

# ─── إدارة الحالة (منع التكرار) ──────────────────────────────────────────────
def _load_state() -> Dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def _save_state(state: Dict):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"State save error: {e}")

def _can_alert(state: Dict, coin: str, level: int) -> bool:
    key = f"{coin}_alert{level}"
    last = state.get(key, 0)
    cooldown = ALERT2_COOLDOWN_MINUTES * 60 if level == 2 else 60 * 60
    return (time.time() - last) > cooldown

def _mark_alert(state: Dict, coin: str, level: int):
    state[f"{coin}_alert{level}"] = time.time()

# ─── إرسال Telegram ───────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={'chat_id': TELEGRAM_CHANNEL_ID, 'text': msg,
                  'parse_mode': 'HTML', 'disable_web_page_preview': True},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

# ─── تنسيق الرسائل ────────────────────────────────────────────────────────────
def format_alert1(analysis: Dict) -> str:
    coin    = analysis['symbol']
    price   = _fmt_price(analysis['price'])
    h1_oi   = analysis['h1_oi_chg']
    h1_vol  = analysis['h1_vol_chg']
    funding = analysis['avg_funding'] * 100
    ls      = analysis['ls_current']
    now     = datetime.now()

    cond_lines = '\n'.join(
        f"  {'✅' if c['met'] else '⬜'} {c['label']}"
        for c in analysis['conditions'].values()
    )

    return (
        f"🔔 <b>تنبيه أول — تراكم صامت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>{coin}/USDT</b>\n"
        f"🏷 القطاع: <b>{get_sector(coin)}</b>\n"
        f"💰 السعر: <b>{price}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>المؤشرات:</b>\n"
        f"{cond_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 OI (1h): <b>{h1_oi:+.2f}%</b>\n"
        f"📦 Volume (1h): <b>{h1_vol:+.1f}%</b>\n"
        f"💸 Funding: <b>{funding:+.4f}%</b>\n"
        f"⚖️ L/S Ratio: <b>{ls:.3f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now.strftime('%H:%M')}  |  📅 {now.strftime('%Y-%m-%d')}"
    )

def format_alert2(analysis: Dict) -> str:
    coin    = analysis['symbol']
    price   = _fmt_price(analysis['price'])
    h1_oi   = analysis['h1_oi_chg']
    h4_oi   = analysis['h4_oi_chg']
    h1_vol  = analysis['h1_vol_chg']
    funding = analysis['avg_funding'] * 100
    ls      = analysis['ls_current']
    now     = datetime.now()

    cond_lines = '\n'.join(
        f"  {'✅' if c['met'] else '⬜'} {c['label']}"
        for c in analysis['conditions'].values()
    )

    return (
        f"🚨 <b>تنبيه ثانٍ — تراكم متصاعد</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>{coin}/USDT</b>\n"
        f"🏷 القطاع: <b>{get_sector(coin)}</b>\n"
        f"💰 السعر: <b>{price}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>المؤشرات:</b>\n"
        f"{cond_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 OI (1h): <b>{h1_oi:+.2f}%</b>  |  OI (4h): <b>{h4_oi:+.2f}%</b>\n"
        f"📦 Volume (1h): <b>{h1_vol:+.1f}%</b>\n"
        f"💸 Funding: <b>{funding:+.4f}%</b>\n"
        f"⚖️ L/S Ratio: <b>{ls:.3f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>التراكم يتصاعد — راقب الاختراق</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now.strftime('%H:%M')}  |  📅 {now.strftime('%Y-%m-%d')}"
    )

# ─── حلقة المسح الرئيسية ─────────────────────────────────────────────────────
def scan_all():
    """مسح جميع العملات وإرسال التنبيهات"""
    # جلب القائمة الديناميكية
    watch_coins = get_top_coins_by_oi(min_oi_usd=10_000_000, top_n=35)
    logger.info(f"🔍 Scanning {len(watch_coins)} coins for accumulation signals...")

    state = _load_state()
    alerts_sent = 0

    for i, coin in enumerate(watch_coins):
        try:
            analysis = analyze_coin(coin)
            if not analysis:
                continue

            met       = analysis['met_count']
            h1_oi     = analysis['h1_oi_chg']
            h1_vol    = analysis['h1_vol_chg']
            funding   = analysis['avg_funding']

            # تنبيه 2: تراكم متصاعد
            is_alert2 = (
                met >= ALERT2_MIN_CONDITIONS and
                h1_oi >= ALERT2_OI_RISE_MIN and
                h1_vol >= ALERT2_VOL_RISE_MIN and
                funding <= ALERT2_FUNDING_MAX
            )
            # فلتر الشمعة: لا نرسل اذا كانت الشمعة حمراء
            if not analysis.get('is_green_candle', True):
                logger.debug(f'skip {coin}: red candle - not bullish')
                continue
            # ─── فلتر بصمة الحركة (Smart Money Pattern) ───────────────────
            # يفحص: EMA50 + MACD+ + RSI(40-75) + OI صاعد (3 من 4 على الأقل)
            pattern = check_smart_money_pattern(coin)
            if not pattern['passed']:
                logger.debug(
                    f'skip {coin}: pattern failed (score {pattern["score"]}/4) '
                    f'EMA50={pattern["above_ema50"]} MACD={pattern["macd_positive"]} '
                    f'RSI={pattern["rsi_value"]} OI={pattern["oi_change"]}'
                )
                continue
            if is_alert2 and _can_alert(state, coin, 2):
                msg = format_alert2(analysis)
                if send_telegram(msg):
                    _mark_alert(state, coin, 2)
                    _mark_alert(state, coin, 1)
                    alerts_sent += 1
                    logger.info(f"🚨 Alert 2 sent for {coin} ({met}/5 conditions)")
                continue

            # تنبيه 1: تراكم أولي
            is_alert1 = (
                met >= ALERT1_MIN_CONDITIONS and
                h1_oi >= ALERT1_OI_RISE_MIN and
                funding <= ALERT1_FUNDING_MAX
            )
            if is_alert1 and _can_alert(state, coin, 1):
                msg = format_alert1(analysis)
                if send_telegram(msg):
                    _mark_alert(state, coin, 1)
                    alerts_sent += 1
                    logger.info(f"🔔 Alert 1 sent for {coin} ({met}/5 conditions)")

            # تأخير بسيط لتجنب rate limiting
            if i % 5 == 4:
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error scanning {coin}: {e}")
            continue

    _save_state(state)
    logger.info(f"✅ Scan complete. Alerts sent: {alerts_sent}")
    return alerts_sent

def main():
    logger.info("🚀 Accumulation Alert System v2 — OKX Only")
    logger.info(f"   Scan interval: {SCAN_INTERVAL//60} min | Alert1: {ALERT1_MIN_CONDITIONS}+ cond | Alert2: {ALERT2_MIN_CONDITIONS}+ cond")

    while True:
        try:
            scan_all()
        except Exception as e:
            logger.error(f"Scan loop error: {e}")
        logger.info(f"⏳ Next scan in {SCAN_INTERVAL//60} minutes...")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
