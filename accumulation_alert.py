"""
Trade Lak - Accumulation Alert System
نظام تنبيهات التراكم الصامت

يراقب:
- OI يرتفع تدريجياً
- Funding محايد أو سلبي خفيف
- Volume يزيد
- CVD يتحسن (نستنتجه من نسبة Long/Short)

تنبيه 1: عند بداية ظهور الإشارات (3+ شروط)
تنبيه 2: عند تصاعد التراكم (4+ شروط + تأكيد)
"""

import requests
import logging
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _fmt_price(price: float) -> str:
    """تنسيق السعر بشكل ذكي يدعم العملات الصغيرة جداً مثل PEPE"""
    if not price or price <= 0:
        return "—"
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    elif price >= 0.01:
        return f"${price:.6f}"
    elif price >= 0.0001:
        return f"${price:.8f}"
    else:
        # عملات صغيرة جداً مثل PEPE — نعرض الأرقام المعنوية
        return f"${price:.10f}".rstrip('0').rstrip('.')


# ─── إعدادات ──────────────────────────────────────────────────────────────────
COINGLASS_API_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
TELEGRAM_BOT_TOKEN = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
TELEGRAM_CHANNEL_ID = "-1003942444248"
COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"

# ─── حدود التنبيه ─────────────────────────────────────────────────────────────
# تنبيه 1: تراكم أولي
ALERT1_OI_RISE_MIN = 0.3        # OI ارتفع +0.3% في ساعة
ALERT1_FUNDING_MAX = 0.01       # Funding أقل من 0.01% (محايد أو سلبي)
ALERT1_VOL_RISE_MIN = 2.0       # Volume ارتفع +2% في ساعة
ALERT1_MIN_CONDITIONS = 3       # يكفي 3 شروط من 5

# تنبيه 2: تراكم متصاعد (أقوى)
ALERT2_OI_RISE_MIN = 1.0        # OI ارتفع +1% في ساعة
ALERT2_FUNDING_MAX = 0.005      # Funding محايد جداً أو سلبي
ALERT2_VOL_RISE_MIN = 8.0       # Volume ارتفع +8%
ALERT2_MIN_CONDITIONS = 4       # يحتاج 4 شروط من 5
ALERT2_COOLDOWN_MINUTES = 30    # لا تكرر تنبيه 2 قبل 30 دقيقة

# ─── حالة التنبيهات (لمنع التكرار) ───────────────────────────────────────────
STATE_FILE = "/root/trade_lak_bot/accumulation_state.json"

# ─── قائمة العملات والقطاعات ──────────────────────────────────────────────────
SECTORS = {
    "Layer1": ["BTC", "ETH", "SOL", "ADA", "AVAX", "DOT", "ATOM", "NEAR", "APT", "SUI", "ICP", "HBAR", "TON"],
    "Layer2": ["POL", "ARB", "OP", "LRC", "IMX", "STRK"],
    "DeFi":   ["UNI", "AAVE", "CRV", "COMP", "DYDX", "GMX", "PENDLE", "JUP"],
    "Meme":   ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "BOME"],
    "AI_Data":["FET", "RENDER", "GRT", "WLD", "ARKM"],
    "Gaming": ["AXS", "SAND", "MANA", "ENJ", "GALA", "RON"],
    "Infrastructure": ["LINK", "FIL", "AR", "THETA", "IOTA"],
    "Exchange": ["BNB", "OKB", "CRO"],
    "Other":  ["XRP", "LTC", "TRX", "XLM", "VET", "ALGO", "FTM", "MATIC"],
}

# خريطة عكسية: عملة -> قطاع
COIN_SECTOR = {}
for sector, coins in SECTORS.items():
    for coin in coins:
        COIN_SECTOR[coin] = sector

# قائمة العملات المراقبة (الأكثر سيولة)
WATCH_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT",
    "LINK", "UNI", "ATOM", "NEAR", "APT", "SUI", "ARB", "OP", "PEPE",
    "FIL", "LTC", "TRX", "ICP", "AAVE", "HBAR", "TON", "WIF", "INJ",
]


class AccumulationAlertSystem:
    """نظام تنبيهات التراكم الصامت"""

    def __init__(self):
        self.cg_headers = {
            'accept': 'application/json',
            'coinglassSecret': COINGLASS_API_KEY
        }
        self.state = self._load_state()
        logger.info("✅ Accumulation Alert System initialized")

    def _load_state(self) -> Dict:
        """تحميل حالة التنبيهات المحفوظة"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_state(self):
        """حفظ حالة التنبيهات"""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def _get_oi_data(self, symbol: str) -> Optional[Dict]:
        """جلب بيانات OI من CoinGlass"""
        try:
            r = requests.get(
                f"{COINGLASS_BASE}/open_interest",
                headers=self.cg_headers,
                params={'symbol': symbol},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                items = data['data']
                # نأخذ السطر الأول (All exchanges)
                item = items[0] if isinstance(items, list) else items
                return item
        except Exception as e:
            logger.error(f"OI fetch error for {symbol}: {e}")
        return None

    def _get_funding_data(self, symbol: str) -> Optional[float]:
        """جلب متوسط Funding Rate"""
        try:
            r = requests.get(
                f"{COINGLASS_BASE}/funding",
                headers=self.cg_headers,
                params={'symbol': symbol},
                timeout=10
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                items = data['data']
                item = items[0] if isinstance(items, list) else items
                # نأخذ متوسط الـ funding من OKX أو Binance
                u_margin = item.get('uMarginList', [])
                rates = []
                for ex in u_margin:
                    if ex.get('exchangeName') in ('OKX', 'Binance', 'Bybit'):
                        rates.append(ex.get('rate', 0))
                if rates:
                    return sum(rates) / len(rates)
                return item.get('avgFundingRate', 0)
        except Exception as e:
            logger.error(f"Funding fetch error for {symbol}: {e}")
        return None

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """جلب السعر الحالي من OKX"""
        try:
            r = requests.get(
                f"https://www.okx.com/api/v5/market/ticker",
                params={'instId': f"{symbol}-USDT"},
                timeout=8
            )
            data = r.json()
            if data.get('code') == '0' and data.get('data'):
                return float(data['data'][0]['last'])
        except Exception:
            pass
        return None

    def _analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """تحليل عملة واحدة وإرجاع نتيجة التراكم"""
        oi_data = self._get_oi_data(symbol)
        if not oi_data:
            return None

        funding = self._get_funding_data(symbol)
        price = self._get_current_price(symbol)

        # ─── استخراج المؤشرات ─────────────────────────────────────────────────
        h1_oi_chg = oi_data.get('h1OIChangePercent', 0) or 0
        h4_oi_chg = oi_data.get('h4OIChangePercent', 0) or 0
        m15_oi_chg = oi_data.get('m15OIChangePercent', 0) or 0
        h1_vol_chg = oi_data.get('h1VolChangePercent', 0) or 0
        h4_vol_chg = oi_data.get('h4VolChangePercent', 0) or 0
        avg_funding = funding if funding is not None else (oi_data.get('avgFundingRateBySymbol', 0) or 0)
        oi_total = oi_data.get('openInterest', 0) or 0

        # ─── تقييم الشروط ─────────────────────────────────────────────────────
        conditions = {}

        # 1. OI يرتفع تدريجياً
        oi_rising = h1_oi_chg >= ALERT1_OI_RISE_MIN and m15_oi_chg >= 0
        conditions['oi_rising'] = {
            'met': oi_rising,
            'value': h1_oi_chg,
            'label': f"OI +{h1_oi_chg:.2f}% (1h)"
        }

        # 2. Funding محايد أو سلبي خفيف
        funding_neutral = avg_funding <= ALERT1_FUNDING_MAX
        conditions['funding_neutral'] = {
            'met': funding_neutral,
            'value': avg_funding,
            'label': f"Funding {avg_funding*100:.4f}%"
        }

        # 3. Volume يزيد
        vol_rising = h1_vol_chg >= ALERT1_VOL_RISE_MIN
        conditions['vol_rising'] = {
            'met': vol_rising,
            'value': h1_vol_chg,
            'label': f"Volume +{h1_vol_chg:.1f}% (1h)"
        }

        # 4. OI/Volume ratio يتحسن (OI يرتفع أسرع من Volume = تراكم)
        oi_vol_ratio_chg = oi_data.get('oiVolRadioH1ChangePercent', 0) or 0
        cvd_improving = oi_vol_ratio_chg > 0 and h1_oi_chg > 0
        conditions['cvd_improving'] = {
            'met': cvd_improving,
            'value': oi_vol_ratio_chg,
            'label': f"OI/Vol ratio +{oi_vol_ratio_chg:.2f}%"
        }

        # 5. OI يرتفع على مدى 4 ساعات أيضاً (تراكم مستمر)
        oi_sustained = h4_oi_chg >= 0.5
        conditions['oi_sustained'] = {
            'met': oi_sustained,
            'value': h4_oi_chg,
            'label': f"OI +{h4_oi_chg:.2f}% (4h)"
        }

        met_count = sum(1 for c in conditions.values() if c['met'])
        sector = COIN_SECTOR.get(symbol, 'Other')

        return {
            'symbol': symbol,
            'sector': sector,
            'price': price,
            'conditions': conditions,
            'met_count': met_count,
            'h1_oi_chg': h1_oi_chg,
            'h4_oi_chg': h4_oi_chg,
            'h1_vol_chg': h1_vol_chg,
            'avg_funding': avg_funding,
            'oi_vol_ratio_chg': oi_vol_ratio_chg,
            'oi_total': oi_total,
        }

    def _should_send_alert(self, symbol: str, alert_level: int) -> bool:
        """فحص إذا كان يجب إرسال التنبيه (منع التكرار)"""
        key = f"{symbol}_alert{alert_level}"
        last_sent = self.state.get(key, 0)
        now = time.time()

        # تنبيه 1: لا تكرر قبل 60 دقيقة
        cooldown = 60 * 60 if alert_level == 1 else ALERT2_COOLDOWN_MINUTES * 60

        return (now - last_sent) > cooldown

    def _mark_alert_sent(self, symbol: str, alert_level: int):
        """تسجيل وقت إرسال التنبيه"""
        key = f"{symbol}_alert{alert_level}"
        self.state[key] = time.time()
        self._save_state()

    def _send_telegram(self, message: str) -> bool:
        """إرسال رسالة لقناة التليجرام"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            r = requests.post(url, json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def _format_alert1(self, analysis: Dict) -> str:
        """صيغة تنبيه 1 — تراكم أولي"""
        symbol = analysis['symbol']
        sector = analysis['sector']
        price = analysis['price']
        h1_oi = analysis['h1_oi_chg']
        h1_vol = analysis['h1_vol_chg']
        funding = analysis['avg_funding'] * 100
        now = datetime.now()

        price_str = _fmt_price(price)

        # بناء قائمة الشروط المتحققة
        cond_lines = []
        for k, c in analysis['conditions'].items():
            icon = "✅" if c['met'] else "⬜"
            cond_lines.append(f"  {icon} {c['label']}")

        msg = f"""🔔 <b>تنبيه أول — تراكم صامت</b>
━━━━━━━━━━━━━━━━━━━━━
💎 <b>{symbol}/USDT</b> — {sector}
💰 السعر الحالي: <b>{price_str}</b>
━━━━━━━━━━━━━━━━━━━━━
📊 <b>المؤشرات:</b>
{chr(10).join(cond_lines)}
━━━━━━━━━━━━━━━━━━━━━
📈 OI (1h): <b>{h1_oi:+.2f}%</b>
📦 Volume (1h): <b>{h1_vol:+.1f}%</b>
💸 Funding: <b>{funding:+.4f}%</b>
━━━━━━━━━━━━━━━━━━━━━
🕐 {now.strftime('%H:%M:%S')}  |  📅 {now.strftime('%Y-%m-%d')}"""
        return msg

    def _format_alert2(self, analysis: Dict) -> str:
        """صيغة تنبيه 2 — تراكم متصاعد"""
        symbol = analysis['symbol']
        sector = analysis['sector']
        price = analysis['price']
        h1_oi = analysis['h1_oi_chg']
        h4_oi = analysis['h4_oi_chg']
        h1_vol = analysis['h1_vol_chg']
        funding = analysis['avg_funding'] * 100
        oi_vol = analysis['oi_vol_ratio_chg']
        now = datetime.now()

        price_str = _fmt_price(price)

        # بناء قائمة الشروط
        cond_lines = []
        for k, c in analysis['conditions'].items():
            icon = "✅" if c['met'] else "⬜"
            cond_lines.append(f"  {icon} {c['label']}")

        msg = f"""🚨 <b>تنبيه ثانٍ — تراكم متصاعد</b>
━━━━━━━━━━━━━━━━━━━━━
💎 <b>{symbol}/USDT</b> — {sector}
💰 السعر الحالي: <b>{price_str}</b>
━━━━━━━━━━━━━━━━━━━━━
📊 <b>المؤشرات:</b>
{chr(10).join(cond_lines)}
━━━━━━━━━━━━━━━━━━━━━
📈 OI (1h): <b>{h1_oi:+.2f}%</b>  |  OI (4h): <b>{h4_oi:+.2f}%</b>
📦 Volume (1h): <b>{h1_vol:+.1f}%</b>
💸 Funding: <b>{funding:+.4f}%</b>
📉 OI/Vol Ratio: <b>{oi_vol:+.2f}%</b>
━━━━━━━━━━━━━━━━━━━━━
⚡ <b>التراكم يتصاعد — راقب الاختراق</b>
━━━━━━━━━━━━━━━━━━━━━
🕐 {now.strftime('%H:%M:%S')}  |  📅 {now.strftime('%Y-%m-%d')}"""
        return msg

    def scan_all(self):
        """مسح جميع العملات وإرسال التنبيهات المناسبة"""
        logger.info(f"🔍 Scanning {len(WATCH_COINS)} coins for accumulation signals...")
        alerts_sent = 0

        for i, symbol in enumerate(WATCH_COINS):
            try:
                analysis = self._analyze_symbol(symbol)
                if not analysis:
                    continue

                met = analysis['met_count']
                h1_oi = analysis['h1_oi_chg']
                h1_vol = analysis['h1_vol_chg']
                avg_funding = analysis['avg_funding']

                # ─── تنبيه 2: تراكم متصاعد (شروط أقوى) ──────────────────────
                is_alert2 = (
                    met >= ALERT2_MIN_CONDITIONS and
                    h1_oi >= ALERT2_OI_RISE_MIN and
                    h1_vol >= ALERT2_VOL_RISE_MIN and
                    avg_funding <= ALERT2_FUNDING_MAX
                )

                if is_alert2 and self._should_send_alert(symbol, 2):
                    msg = self._format_alert2(analysis)
                    if self._send_telegram(msg):
                        self._mark_alert_sent(symbol, 2)
                        # إعادة ضبط تنبيه 1 أيضاً
                        self._mark_alert_sent(symbol, 1)
                        alerts_sent += 1
                        logger.info(f"🚨 Alert 2 sent for {symbol} (conditions: {met}/5)")
                    continue

                # ─── تنبيه 1: تراكم أولي ──────────────────────────────────────
                is_alert1 = (
                    met >= ALERT1_MIN_CONDITIONS and
                    h1_oi >= ALERT1_OI_RISE_MIN and
                    avg_funding <= ALERT1_FUNDING_MAX
                )

                if is_alert1 and self._should_send_alert(symbol, 1):
                    msg = self._format_alert1(analysis)
                    if self._send_telegram(msg):
                        self._mark_alert_sent(symbol, 1)
                        alerts_sent += 1
                        logger.info(f"🔔 Alert 1 sent for {symbol} (conditions: {met}/5)")

                # تأخير بسيط لتجنب rate limiting
                if i % 5 == 4:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue

        logger.info(f"✅ Scan complete. Alerts sent: {alerts_sent}")
        return alerts_sent


def main():
    """تشغيل المسح الدوري"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler('/root/trade_lak_bot/accumulation_alert.log'),
            logging.StreamHandler()
        ]
    )

    system = AccumulationAlertSystem()

    # مسح كل 15 دقيقة
    SCAN_INTERVAL = 15 * 60

    logger.info("🚀 Accumulation Alert System started")
    logger.info(f"📡 Monitoring {len(WATCH_COINS)} coins every {SCAN_INTERVAL//60} minutes")

    while True:
        try:
            system.scan_all()
        except Exception as e:
            logger.error(f"Scan error: {e}")

        logger.info(f"⏳ Next scan in {SCAN_INTERVAL//60} minutes...")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
