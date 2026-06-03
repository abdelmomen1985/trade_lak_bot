# Trade Lak Bot - CoinGlass Data Client
# وحدة جلب بيانات السيولة من CoinGlass API v4
# Updated: May 2026 - Migrated from v2 (coinglassSecret) to v4 (CG-API-KEY)

import requests
import logging
from config.config import COINGLASS_API_KEY, MIN_LIQUIDATION_VOLUME, FUNDING_RATE_THRESHOLD

logger = logging.getLogger(__name__)

# CoinGlass API v4 - Updated base URL and auth header
COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com"


class CoinGlassClient:
    """
    جلب بيانات السيولة والتصفيات ومعدلات التمويل من CoinGlass API v4
    Fetches liquidity, liquidation, and funding rate data from CoinGlass API v4

    Changes from v2:
    - Base URL: open-api.coinglass.com/public/v2 → open-api-v4.coinglass.com
    - Auth header: 'coinglassSecret' → 'CG-API-KEY'
    - Endpoint paths completely restructured under /api/futures/
    - Response code: 'success' boolean → 'code' integer (0 = success)
    """

    DEFAULT_EXCHANGE = "Binance"
    DEFAULT_INTERVAL = "h1"

    def __init__(self):
        self.headers = {
            "CG-API-KEY": COINGLASS_API_KEY,
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logger.info("✅ CoinGlass Client v4 initialized")

    def _get(self, path: str, params: dict = None):
        """Helper: make GET request and return parsed data field."""
        try:
            url = f"{COINGLASS_BASE_URL}{path}"
            r = self.session.get(url, params=params or {}, timeout=10)
            data = r.json()
            # code=0 means success in CoinGlass API v4
            # Note: code may be returned as string "0" or integer 0 depending on server
            code = data.get("code")
            if str(code) == "0" or code == 0:
                return data.get("data")
            else:
                logger.warning(f"CoinGlass API error [{path}]: {data.get('msg', 'Unknown error')}")
                return None
        except Exception as e:
            logger.error(f"CoinGlass request failed [{path}]: {e}")
            return None

    def test_connection(self) -> bool:
        """Test API connectivity."""
        result = self._get("/api/futures/liquidation/coin-list")
        if result is not None and isinstance(result, list) and len(result) > 0:
            logger.info("✅ CoinGlass API v4 connection OK")
            return True
        logger.warning("❌ CoinGlass API v4 connection failed")
        return False

    def get_liquidation_data(self, symbol: str = "BTC") -> dict:
        """
        جلب بيانات التصفيات للعملة
        Get liquidation data for a coin (24h, 12h, 4h, 1h)
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/liquidation/coin-list")
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if item:
                    liq_24h = item.get("liquidation_usd_24h", 0)
                    long_24h = item.get("long_liquidation_usd_24h", 0)
                    short_24h = item.get("short_liquidation_usd_24h", 0)
                    logger.info(
                        f"Liquidation {clean} 24h: ${liq_24h:,.0f} "
                        f"(Long: ${long_24h:,.0f} | Short: ${short_24h:,.0f})"
                    )
                    return {
                        "total_24h": liq_24h,
                        "long_24h": long_24h,
                        "short_24h": short_24h,
                        "total_12h": item.get("liquidation_usd_12h", 0),
                        "total_4h": item.get("liquidation_usd_4h", 0),
                        "total_1h": item.get("liquidation_usd_1h", 0),
                    }
            return {"total_24h": 0, "long_24h": 0, "short_24h": 0,
                    "total_12h": 0, "total_4h": 0, "total_1h": 0}
        except Exception as e:
            logger.error(f"Error fetching liquidation data: {e}")
            return {"total_24h": 0, "long_24h": 0, "short_24h": 0,
                    "total_12h": 0, "total_4h": 0, "total_1h": 0}

    # Backward-compatible alias
    def get_liquidations(self, symbol: str = "BTC", interval: str = "1h") -> list:
        """Backward-compatible wrapper for get_liquidation_data."""
        data = self.get_liquidation_data(symbol)
        return [data] if data.get("total_24h", 0) > 0 else []

    def get_funding_rate(self, symbol: str = "BTC") -> float:
        """
        جلب معدل التمويل الحالي (من Binance)
        Get current funding rate from Binance (OI-weighted)
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/funding-rate/exchange-list", {"symbol": clean})
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if not item and result:
                    item = result[0]
                if item:
                    sc_list = item.get("stablecoin_margin_list", [])
                    if sc_list:
                        binance = next((x for x in sc_list if x.get("exchange") == "Binance"), None)
                        entry = binance or sc_list[0]
                        rate = float(entry.get("funding_rate", 0))
                        logger.info(f"Funding rate {clean}: {rate:.4f}%")
                        return rate
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return 0.0

    def get_funding_rate_v2(self, symbol: str = "BTC") -> float:
        """
        جلب معدل التمويل من coins-markets (أسرع وأكثر دقة)
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/coins-markets", {"symbol": clean})
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if item:
                    rate = float(item.get("avg_funding_rate_by_oi", 0))
                    logger.info(f"Funding Rate {clean}: {rate:.4f}% (from coins-markets)")
                    return rate
        except Exception as e:
            logger.error(f"Error fetching funding rate v2: {e}")
        return 0.0

    def get_long_short_ratio(self, symbol: str = "BTC") -> dict:
        """
        جلب نسبة Long/Short من coins-markets (أكثر دقة وموثوقية)
        Uses long_short_ratio_1h from coins-markets endpoint
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/coins-markets", {"symbol": clean})
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if item:
                    # long_short_ratio_1h = long_vol / short_vol
                    ls_ratio_1h = float(item.get("long_short_ratio_1h", 1.0))
                    ls_ratio_4h = float(item.get("long_short_ratio_4h", 1.0))
                    # تحويل النسبة إلى نسب مئوية
                    # ratio = long/short, إذا ratio=0.8 → long=44.4%, short=55.6%
                    total = ls_ratio_1h + 1.0
                    long_pct = ls_ratio_1h / total if total > 0 else 0.5
                    short_pct = 1.0 / total if total > 0 else 0.5
                    # إضافة بيانات إضافية
                    long_vol_1h = float(item.get("long_volume_usd_1h", 0))
                    short_vol_1h = float(item.get("short_volume_usd_1h", 0))
                    logger.info(
                        f"Long/Short {clean}: Ratio_1h={ls_ratio_1h:.3f} | "
                        f"Long={long_pct:.1%} | Short={short_pct:.1%} | "
                        f"LongVol=${long_vol_1h:,.0f} | ShortVol=${short_vol_1h:,.0f}"
                    )
                    return {
                        "long": long_pct,
                        "short": short_pct,
                        "ratio_1h": ls_ratio_1h,
                        "ratio_4h": ls_ratio_4h,
                        "long_vol_1h": long_vol_1h,
                        "short_vol_1h": short_vol_1h,
                    }
            return {"long": 0.5, "short": 0.5, "ratio_1h": 1.0, "ratio_4h": 1.0}
        except Exception as e:
            logger.error(f"Error fetching long/short ratio: {e}")
            return {"long": 0.5, "short": 0.5, "ratio_1h": 1.0, "ratio_4h": 1.0}

    def get_open_interest(self, symbol: str = "BTC") -> dict:
        """
        جلب الفائدة المفتوحة (Open Interest) من coins-markets
        Includes real-time change percentages for 1h, 4h, 24h
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/coins-markets", {"symbol": clean})
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if item:
                    oi_usd = float(item.get("open_interest_usd", 0))
                    oi_change_1h = float(item.get("open_interest_change_percent_1h", 0)) / 100
                    oi_change_4h = float(item.get("open_interest_change_percent_4h", 0)) / 100
                    oi_change_24h = float(item.get("open_interest_change_percent_24h", 0)) / 100
                    logger.info(
                        f"Open Interest {clean}: ${oi_usd:,.0f} | "
                        f"1h={oi_change_1h:.2%} | 4h={oi_change_4h:.2%} | 24h={oi_change_24h:.2%}"
                    )
                    return {
                        "current": oi_usd,
                        "change_pct": oi_change_1h,  # للتوافق مع الكود القديم
                        "change_1h": oi_change_1h,
                        "change_4h": oi_change_4h,
                        "change_24h": oi_change_24h,
                    }
            return {"current": 0, "change_pct": 0, "change_1h": 0, "change_4h": 0, "change_24h": 0}
        except Exception as e:
            logger.error(f"Error fetching open interest: {e}")
            return {"current": 0, "change_pct": 0, "change_1h": 0, "change_4h": 0, "change_24h": 0}

    def get_coins_market_data(self, symbol: str = "BTC") -> dict:
        """
        جلب بيانات السوق الشاملة للعملة
        Get comprehensive market data for a coin
        """
        try:
            clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()
            result = self._get("/api/futures/coins-markets", {"symbol": clean})
            if result and isinstance(result, list):
                item = next((x for x in result if x.get("symbol") == clean), None)
                if item:
                    return {
                        "price": item.get("current_price", 0),
                        "avg_funding_rate": item.get("avg_funding_rate_by_oi", 0),
                        "oi_market_cap_ratio": item.get("open_interest_market_cap_ratio", 0),
                        "market_cap": item.get("market_cap_usd", 0),
                    }
            return {}
        except Exception as e:
            logger.error(f"Error fetching coins market data: {e}")
            return {}

    def analyze_signal(self, symbol: str) -> dict:
        """
        تحليل شامل لإشارة التداول بناءً على بيانات CoinGlass v4
        Comprehensive signal analysis based on CoinGlass v4 data
        Returns: 'BUY', 'SELL', or 'NEUTRAL'
        """
        clean = symbol.replace("/USDT", "").replace("/BTC", "").upper()

        funding_rate = self.get_funding_rate_v2(clean)
        if funding_rate == 0.0:
            funding_rate = self.get_funding_rate(clean)
        long_short = self.get_long_short_ratio(clean)
        oi_data = self.get_open_interest(clean)
        liq_data = self.get_liquidation_data(clean)

        score = 0
        reasons = []

        # تحليل معدل التمويل
        if funding_rate < -FUNDING_RATE_THRESHOLD:
            score += 2
            reasons.append(f"معدل تمويل سلبي ({funding_rate:.4f}%) = ضغط بيع زائد = فرصة شراء")
        elif funding_rate > FUNDING_RATE_THRESHOLD * 3:
            score -= 2
            reasons.append(f"معدل تمويل مرتفع ({funding_rate:.4f}%) = ضغط شراء زائد = خطر")

        # تحليل نسبة Long/Short
        if long_short["short"] > 0.65:
            score += 2
            reasons.append(f"نسبة Short مرتفعة ({long_short['short']:.1%}) = فرصة ارتداد صعودي")
        elif long_short["long"] > 0.70:
            score -= 1
            reasons.append(f"نسبة Long مرتفعة جداً ({long_short['long']:.1%}) = خطر تصحيح")

        # تحليل Open Interest
        if oi_data["change_pct"] > 0.05:
            score += 1
            reasons.append(f"ارتفاع Open Interest ({oi_data['change_pct']:.2%}) = دخول أموال جديدة")
        elif oi_data["change_pct"] < -0.05:
            score -= 1
            reasons.append(f"انخفاض Open Interest ({oi_data['change_pct']:.2%}) = خروج أموال")

        # تحليل التصفيات
        long_liq = liq_data.get("long_24h", 0)
        short_liq = liq_data.get("short_24h", 0)
        if long_liq > short_liq * 2 and long_liq > MIN_LIQUIDATION_VOLUME:
            score += 1
            reasons.append(f"تصفيات Long كبيرة (${long_liq:,.0f}) = ضغط بيع منتهٍ")
        elif short_liq > long_liq * 2 and short_liq > MIN_LIQUIDATION_VOLUME:
            score -= 1
            reasons.append(f"تصفيات Short كبيرة (${short_liq:,.0f}) = ضغط شراء منتهٍ")

        # تحديد الإشارة النهائية
        if score >= 3:
            signal = "BUY"
        elif score <= -2:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        logger.info(f"CoinGlass signal for {symbol}: {signal} (score: {score})")
        for reason in reasons:
            logger.info(f"  - {reason}")

        return {
            "signal": signal,
            "score": score,
            "reasons": reasons,
            "funding_rate": funding_rate,
            "long_short": long_short,
            "open_interest": oi_data,
            "liquidation": liq_data,
        }
