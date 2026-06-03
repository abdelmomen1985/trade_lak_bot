"""
Coinglass Pro Engine v2 - Advanced Market Intelligence
Uses CG-API-KEY header (correct for v4 API)
Provides: Whale Liquidations, OI, Funding Rate, Long/Short, Taker Volume
"""
import requests
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

COINGLASS_API_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
BASE_URL = "https://open-api-v4.coinglass.com"
HEADERS = {"CG-API-KEY": COINGLASS_API_KEY}

# Thresholds
WHALE_LIQUIDATION_USD = 500_000       # تصفية whale = أكثر من $500K
HIGH_FUNDING_RATE = 0.01              # معدل تمويل مرتفع
EXTREME_FUNDING_RATE = 0.05           # معدل تمويل متطرف
NEGATIVE_FUNDING_RATE = -0.005        # معدل تمويل سلبي
OI_SURGE_1H = 2.0                    # ارتفاع OI بنسبة 2% في ساعة
OI_SURGE_4H = 5.0                    # ارتفاع OI بنسبة 5% في 4 ساعات
LONG_SHORT_RATIO_HIGH = 1.2          # نسبة Long/Short مرتفعة (أكثر Long من Short)
LONG_SHORT_RATIO_LOW = 0.7           # نسبة Long/Short منخفضة (أكثر Short من Long)


def _get(path: str, params: dict = None) -> Optional[list | dict]:
    """Make a GET request to Coinglass API v4."""
    try:
        r = requests.get(
            BASE_URL + path,
            headers=HEADERS,
            params=params or {},
            timeout=12,
        )
        data = r.json()
        if data.get("code") == "0":
            return data.get("data")
        else:
            logger.debug(f"[CG Pro] {path} → code={data.get('code')}, msg={data.get('msg','')[:80]}")
            return None
    except Exception as e:
        logger.error(f"[CG Pro] Request error {path}: {e}")
        return None


# ─── Whale Liquidation Orders ──────────────────────────────────────────────────
def get_whale_liquidations(symbol: str, limit: int = 100) -> dict:
    """
    جلب أوامر التصفية الكبيرة (Whale Liquidations) في الوقت الفعلي
    """
    clean = symbol.replace("-USDT", "").replace("/USDT", "").upper()
    data = _get("/api/futures/liquidation/order", {"symbol": clean, "limit": limit})

    result = {
        "whale_long_vol": 0,
        "whale_short_vol": 0,
        "total_whale_volume": 0,
        "biggest_liq": 0,
        "biggest_liq_side": "",
        "whale_count": 0,
        "signal": "NEUTRAL",
        "score": 0,
    }

    if not data or not isinstance(data, list):
        return result

    whale_long_vol = 0
    whale_short_vol = 0
    whale_count = 0

    for order in data:
        usd_val = float(order.get("usd_value", 0))
        side = order.get("side", 0)  # 1 = Long liquidated, 0 = Short liquidated

        if usd_val >= WHALE_LIQUIDATION_USD:
            whale_count += 1
            if side == 1:  # Long liquidated (bearish pressure)
                whale_long_vol += usd_val
            else:  # Short liquidated (bullish pressure)
                whale_short_vol += usd_val

            if usd_val > result["biggest_liq"]:
                result["biggest_liq"] = usd_val
                result["biggest_liq_side"] = "LONG" if side == 1 else "SHORT"

    result["whale_long_vol"] = whale_long_vol
    result["whale_short_vol"] = whale_short_vol
    result["whale_count"] = whale_count
    result["total_whale_volume"] = whale_long_vol + whale_short_vol

    # تحديد الإشارة
    score = 0
    if whale_short_vol > whale_long_vol * 2 and whale_short_vol > 1_000_000:
        result["signal"] = "BULLISH"
        score = 2
    elif whale_long_vol > whale_short_vol * 2 and whale_long_vol > 1_000_000:
        result["signal"] = "BEARISH"
        score = -2
    elif whale_short_vol > whale_long_vol * 1.5:
        result["signal"] = "SLIGHTLY_BULLISH"
        score = 1
    elif whale_long_vol > whale_short_vol * 1.5:
        result["signal"] = "SLIGHTLY_BEARISH"
        score = -1

    result["score"] = score

    logger.info(
        f"[CG Pro] Whale Liq {clean}: "
        f"Long=${whale_long_vol:,.0f}, Short=${whale_short_vol:,.0f}, "
        f"Signal={result['signal']}"
    )
    return result


# ─── Rich Market Intelligence from coins-markets ──────────────────────────────
def get_market_intelligence(symbol: str) -> dict:
    """
    جلب بيانات السوق الشاملة من coins-markets:
    - Funding Rate (avg by OI)
    - Open Interest + تغيراته (1h, 4h, 24h)
    - Long/Short Ratio (1h, 4h, 24h)
    - Long/Short Volume (1h, 4h)
    - Price Change (1h, 4h, 24h)
    """
    clean = symbol.replace("-USDT", "").replace("/USDT", "").upper()

    result = {
        # Funding Rate
        "funding_rate": 0.0,
        "funding_signal": "NEUTRAL",
        # Open Interest
        "oi_usd": 0,
        "oi_change_1h": 0,
        "oi_change_4h": 0,
        "oi_change_24h": 0,
        "oi_signal": "NEUTRAL",
        # Long/Short Ratio
        "ls_ratio_1h": 1.0,
        "ls_ratio_4h": 1.0,
        "ls_ratio_24h": 1.0,
        "long_vol_1h": 0,
        "short_vol_1h": 0,
        "long_vol_4h": 0,
        "short_vol_4h": 0,
        "ls_signal": "NEUTRAL",
        # Price
        "price": 0,
        "price_change_1h": 0,
        "price_change_4h": 0,
        "price_change_24h": 0,
        # Market Cap
        "market_cap": 0,
        # Composite
        "composite_score": 0,
        "composite_signal": "NEUTRAL",
        "reasons": [],
    }

    market_data = _get("/api/futures/coins-markets", {"symbol": clean})
    if not market_data or not isinstance(market_data, list):
        return result

    item = next((x for x in market_data if x.get("symbol") == clean), None)
    if not item:
        return result

    # استخراج البيانات
    result["price"] = float(item.get("current_price", 0))
    result["funding_rate"] = float(item.get("avg_funding_rate_by_oi", 0))
    result["market_cap"] = float(item.get("market_cap_usd", 0))
    result["oi_usd"] = float(item.get("open_interest_usd", 0))

    # OI Changes
    result["oi_change_1h"] = float(item.get("open_interest_change_percent_1h", 0))
    result["oi_change_4h"] = float(item.get("open_interest_change_percent_4h", 0))
    result["oi_change_24h"] = float(item.get("open_interest_change_percent_24h", 0))

    # Long/Short Ratios (ratio = long_vol / short_vol)
    result["ls_ratio_1h"] = float(item.get("long_short_ratio_1h", 1.0))
    result["ls_ratio_4h"] = float(item.get("long_short_ratio_4h", 1.0))
    result["ls_ratio_24h"] = float(item.get("long_short_ratio_24h", 1.0))

    # Long/Short Volumes
    result["long_vol_1h"] = float(item.get("long_volume_usd_1h", 0))
    result["short_vol_1h"] = float(item.get("short_volume_usd_1h", 0))
    result["long_vol_4h"] = float(item.get("long_volume_usd_4h", 0))
    result["short_vol_4h"] = float(item.get("short_volume_usd_4h", 0))

    # Price Changes
    result["price_change_1h"] = float(item.get("price_change_percent_1h", 0))
    result["price_change_4h"] = float(item.get("price_change_percent_4h", 0))
    result["price_change_24h"] = float(item.get("price_change_percent_24h", 0))

    # ─── تحليل الإشارات ───
    score = 0
    reasons = []

    # 1. Funding Rate
    fr = result["funding_rate"]
    if fr < NEGATIVE_FUNDING_RATE:
        score += 3
        result["funding_signal"] = "STRONG_BULLISH"
        reasons.append(f"📉 Funding Rate سلبي ({fr:.4f}%) = تكلفة على Short = فرصة Long")
    elif fr < 0:
        score += 1
        result["funding_signal"] = "BULLISH"
        reasons.append(f"📉 Funding Rate سلبي قليلاً ({fr:.4f}%)")
    elif fr > EXTREME_FUNDING_RATE:
        score -= 3
        result["funding_signal"] = "STRONG_BEARISH"
        reasons.append(f"📈 Funding Rate مرتفع جداً ({fr:.4f}%) = خطر تصفية Long")
    elif fr > HIGH_FUNDING_RATE:
        score -= 1
        result["funding_signal"] = "BEARISH"
        reasons.append(f"📈 Funding Rate مرتفع ({fr:.4f}%)")

    # 2. Long/Short Ratio (1h هو الأهم)
    ls_1h = result["ls_ratio_1h"]
    ls_4h = result["ls_ratio_4h"]

    if ls_1h < LONG_SHORT_RATIO_LOW:
        score += 2
        result["ls_signal"] = "BULLISH"
        reasons.append(f"🐻 نسبة L/S منخفضة ({ls_1h:.2f}) = Short يهيمن = Short Squeeze محتمل")
    elif ls_1h > LONG_SHORT_RATIO_HIGH:
        score -= 2
        result["ls_signal"] = "BEARISH"
        reasons.append(f"🐂 نسبة L/S مرتفعة ({ls_1h:.2f}) = Long يهيمن = Long Squeeze محتمل")

    # تأكيد الإشارة من 4h
    if ls_4h < LONG_SHORT_RATIO_LOW and ls_1h < LONG_SHORT_RATIO_LOW:
        score += 1
        reasons.append(f"✅ تأكيد Short Squeeze: L/S 4h={ls_4h:.2f} أيضاً منخفض")
    elif ls_4h > LONG_SHORT_RATIO_HIGH and ls_1h > LONG_SHORT_RATIO_HIGH:
        score -= 1
        reasons.append(f"⚠️ تأكيد Long Squeeze: L/S 4h={ls_4h:.2f} أيضاً مرتفع")

    # 3. Open Interest Changes
    oi_1h = result["oi_change_1h"]
    oi_4h = result["oi_change_4h"]

    if oi_1h > OI_SURGE_1H:
        score += 1
        result["oi_signal"] = "BULLISH"
        reasons.append(f"📊 OI ارتفع {oi_1h:.1f}% في ساعة = دخول أموال جديدة")
    elif oi_1h < -OI_SURGE_1H:
        score -= 1
        result["oi_signal"] = "BEARISH"
        reasons.append(f"📊 OI انخفض {oi_1h:.1f}% في ساعة = خروج أموال")

    if oi_4h > OI_SURGE_4H:
        score += 1
        reasons.append(f"📊 OI ارتفع {oi_4h:.1f}% في 4 ساعات = اهتمام متزايد")
    elif oi_4h < -OI_SURGE_4H:
        score -= 1
        reasons.append(f"📊 OI انخفض {oi_4h:.1f}% في 4 ساعات = تراجع الاهتمام")

    # 4. Price vs OI Divergence (مهم جداً)
    price_1h = result["price_change_1h"]
    if price_1h < -1.0 and oi_1h > 1.0:
        score -= 1
        reasons.append(f"⚠️ السعر ينخفض ({price_1h:.1f}%) مع ارتفاع OI = ضغط هبوطي")
    elif price_1h > 1.0 and oi_1h > 1.0:
        score += 1
        reasons.append(f"✅ السعر يرتفع ({price_1h:.1f}%) مع ارتفاع OI = زخم صعودي")

    result["composite_score"] = score
    result["reasons"] = reasons

    if score >= 4:
        result["composite_signal"] = "STRONG_BUY"
    elif score >= 2:
        result["composite_signal"] = "BUY"
    elif score <= -4:
        result["composite_signal"] = "STRONG_SELL"
    elif score <= -2:
        result["composite_signal"] = "SELL"
    else:
        result["composite_signal"] = "NEUTRAL"

    logger.info(
        f"[CG Pro] Market Intel {clean}: "
        f"FR={fr:.4f}%, L/S_1h={ls_1h:.2f}, OI_1h={oi_1h:.1f}%, "
        f"Signal={result['composite_signal']} (score={score})"
    )
    return result


# ─── Full Pro Analysis ─────────────────────────────────────────────────────────
def analyze_pro(symbol: str) -> dict:
    """
    التحليل الكامل باستخدام Coinglass Pro
    يدمج: Whale Liquidations + Market Intelligence
    """
    clean = symbol.replace("-USDT", "").replace("/USDT", "").upper()

    whale = get_whale_liquidations(clean)
    market = get_market_intelligence(clean)

    # دمج النتائج
    total_score = market["composite_score"] + whale["score"]
    all_reasons = list(market["reasons"])

    # إضافة تأثير Whale Liquidations
    if whale["signal"] in ("BULLISH", "SLIGHTLY_BULLISH"):
        all_reasons.append(
            f"🐋 تصفيات Whale Short: ${whale['whale_short_vol']:,.0f} = ضغط صعودي"
        )
    elif whale["signal"] in ("BEARISH", "SLIGHTLY_BEARISH"):
        all_reasons.append(
            f"🐋 تصفيات Whale Long: ${whale['whale_long_vol']:,.0f} = ضغط هبوطي"
        )

    if whale["biggest_liq"] > 2_000_000:
        all_reasons.append(
            f"⚡ أكبر تصفية: ${whale['biggest_liq']:,.0f} ({whale['biggest_liq_side']})"
        )

    # الإشارة النهائية
    if total_score >= 5:
        final_signal = "STRONG_BUY"
        confidence_boost = 25
    elif total_score >= 3:
        final_signal = "BUY"
        confidence_boost = 15
    elif total_score >= 1:
        final_signal = "WEAK_BUY"
        confidence_boost = 5
    elif total_score <= -5:
        final_signal = "STRONG_SELL"
        confidence_boost = 25
    elif total_score <= -3:
        final_signal = "SELL"
        confidence_boost = 15
    elif total_score <= -1:
        final_signal = "WEAK_SELL"
        confidence_boost = 5
    else:
        final_signal = "NEUTRAL"
        confidence_boost = 0

    result = {
        "symbol": clean,
        "signal": final_signal,
        "score": total_score,
        "confidence_boost": confidence_boost,
        "reasons": all_reasons,
        "whale": whale,
        "market": market,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        f"[CG Pro] FULL ANALYSIS {clean}: "
        f"Signal={final_signal}, Score={total_score}, "
        f"Confidence Boost=+{confidence_boost}%"
    )
    return result


# ─── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    symbols = ["BTC", "ETH", "BNB", "SOL"]
    for sym in symbols:
        print(f"\n{'='*55}")
        print(f"  COINGLASS PRO ANALYSIS: {sym}")
        print('='*55)
        result = analyze_pro(sym)

        print(f"Signal:       {result['signal']}")
        print(f"Score:        {result['score']}")
        print(f"Conf Boost:   +{result['confidence_boost']}%")
        print(f"Price:        ${result['market']['price']:,.2f}")
        print(f"Funding Rate: {result['market']['funding_rate']:.4f}%")
        print(f"L/S Ratio 1h: {result['market']['ls_ratio_1h']:.3f}")
        print(f"L/S Ratio 4h: {result['market']['ls_ratio_4h']:.3f}")
        print(f"OI Change 1h: {result['market']['oi_change_1h']:.2f}%")
        print(f"OI Change 4h: {result['market']['oi_change_4h']:.2f}%")
        print(f"OI (USD):     ${result['market']['oi_usd']:,.0f}")
        print(f"Whale Liq:    ${result['whale']['total_whale_volume']:,.0f} ({result['whale']['signal']})")
        print(f"Reasons:")
        for r in result["reasons"]:
            print(f"  • {r}")
