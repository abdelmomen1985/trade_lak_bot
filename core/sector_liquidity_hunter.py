# ============================================================
# Sector Liquidity Hunter v1.0
# محرك صيد السيولة القطاعية — يكتشف القطاع الأقوى والعملة المهيأة للانفجار
# ============================================================
import logging
import time
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# ─── تصنيف القطاعات ───────────────────────────────────────────────────────────
SECTOR_MAP = {
    # Layer 1 - الطبقة الأولى (البلوكشين الأساسية)
    "Layer1": [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "AVAX/USDT",
        "DOT/USDT", "ATOM/USDT", "NEAR/USDT", "APT/USDT", "SUI/USDT",
        "TIA/USDT", "SEI/USDT", "INJ/USDT", "TON/USDT", "ALGO/USDT",
        "ICP/USDT", "S/USDT", "ONE/USDT", "EGLD/USDT", "HBAR/USDT",
    ],
    # Layer 2 - الطبقة الثانية (حلول التوسع)
    "Layer2": [
        "POL/USDT", "ARB/USDT", "OP/USDT", "LRC/USDT", "IMX/USDT",
        "STRK/USDT", "METIS/USDT", "ZKJ/USDT",
    ],
    # DeFi - التمويل اللامركزي
    "DeFi": [
        "UNI/USDT", "AAVE/USDT", "CRV/USDT", "COMP/USDT",
        "SNX/USDT", "SUSHI/USDT", "YFI/USDT", "1INCH/USDT",
        "DYDX/USDT", "GMX/USDT", "PENDLE/USDT", "JUP/USDT",
    ],
    # Meme - عملات الميم
    "Meme": [
        "DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "FLOKI/USDT", "BONK/USDT",
        "WIF/USDT", "MEME/USDT", "NEIRO/USDT", "BOME/USDT",
        "TURBO/USDT",
    ],
    # AI & Data - الذكاء الاصطناعي والبيانات
    "AI_Data": [
        "FET/USDT", "RENDER/USDT", "ARKM/USDT", "RENDER/USDT", "GRT/USDT",
        "WLD/USDT", "ARKM/USDT", "NMR/USDT",
    ],
    # Gaming & Metaverse - الألعاب والميتافيرس
    "Gaming": [
        "AXS/USDT", "SAND/USDT", "MANA/USDT", "ENJ/USDT", "GALA/USDT",
        "ILV/USDT", "MAGIC/USDT", "RON/USDT", "PIXEL/USDT",
        "YGG/USDT", "GALA/USDT",
    ],
    # Infrastructure - البنية التحتية
    "Infrastructure": [
        "LINK/USDT", "FIL/USDT", "AR/USDT", "LPT/USDT", "API3/USDT",
        "BAND/USDT", "STORJ/USDT", "GLM/USDT",
        "THETA/USDT", "IOTA/USDT",
    ],
    # Exchange Tokens - عملات البورصات
    "Exchange": [
        "BNB/USDT", "OKB/USDT", "CRO/USDT",
        "WOO/USDT",
    ],
    # Privacy - الخصوصية
    "Privacy": [
        "ZEC/USDT", "DASH/USDT",
    ],
    # RWA & Staking - الأصول الحقيقية والستيكينج
    "RWA_Staking": [
        "ONDO/USDT", "CFG/USDT", "LDO/USDT", "RPL/USDT",
        "STETH/USDT",
    ],
    # Payments & Remittance - المدفوعات والتحويلات
    "Payments": [
        "XRP/USDT", "LTC/USDT", "XLM/USDT", "TRX/USDT", "BCH/USDT",
        "CELO/USDT",
    ],
    # NFT & Creator - NFT والمبدعون
    "NFT": [
        "APE/USDT", "BLUR/USDT",
        "CHZ/USDT", "FLOW/USDT",
    ],
}

# ─── عكس الخريطة: عملة → قطاع ────────────────────────────────────────────────
COIN_TO_SECTOR = {}
for sector, coins in SECTOR_MAP.items():
    for coin in coins:
        COIN_TO_SECTOR[coin] = sector


class SectorLiquidityHunter:
    """
    محرك صيد السيولة القطاعية
    - يتتبع تدفق السيولة بين القطاعات
    - يكتشف القطاع الأقوى (الذي تتجمع فيه السيولة)
    - يحدد العملة الأقوى في كل قطاع (المهيأة للانفجار)
    """

    def __init__(self, okx_client):
        self.okx = okx_client
        self._sector_cache = {}
        self._cache_time = 0
        self._cache_ttl = 180  # 3 دقائق

    def get_sector(self, symbol: str) -> str:
        """إرجاع القطاع لعملة معينة"""
        return COIN_TO_SECTOR.get(symbol, "Other")

    def _calc_rsi(self, closes: List[float], period: int = 14) -> float:
        """حساب RSI"""
        if len(closes) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)

    def _calc_ema(self, closes: List[float], period: int) -> float:
        """حساب EMA"""
        if len(closes) < period:
            return closes[-1] if closes else 0
        k = 2 / (period + 1)
        ema = sum(closes[:period]) / period
        for p in closes[period:]:
            ema = p * k + ema * (1 - k)
        return ema

    def _calc_volume_spike(self, ohlcv: List[Dict]) -> float:
        """حساب انفجار الحجم: نسبة آخر 3 شموع إلى متوسط 20 شمعة"""
        if len(ohlcv) < 23:
            return 1.0
        vols = [c['volume'] for c in ohlcv]
        recent_avg = sum(vols[-3:]) / 3
        base_avg = sum(vols[-23:-3]) / 20
        return recent_avg / base_avg if base_avg > 0 else 1.0

    def _calc_momentum_score(self, ohlcv: List[Dict]) -> Dict:
        """
        حساب نقاط الزخم الشامل لعملة واحدة
        Returns: dict with score, rsi, ema_trend, vol_spike, price_change
        """
        if not ohlcv or len(ohlcv) < 50:
            return {"score": 0, "rsi": 50, "ema_trend": 0, "vol_spike": 1.0, "price_change": 0}

        closes = [c['close'] for c in ohlcv]
        highs  = [c['high']  for c in ohlcv]
        lows   = [c['low']   for c in ohlcv]
        vols   = [c['volume'] for c in ohlcv]

        current = closes[-1]
        rsi = self._calc_rsi(closes)
        ema20 = self._calc_ema(closes, 20)
        ema50 = self._calc_ema(closes, 50)
        vol_spike = self._calc_volume_spike(ohlcv)

        # تغير السعر في آخر 4 ساعات
        price_4h_ago = closes[-4] if len(closes) >= 4 else closes[0]
        price_change = (current - price_4h_ago) / price_4h_ago * 100

        # ATR كنسبة مئوية
        trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
               for i in range(1, len(closes))]
        atr = sum(trs[-14:]) / 14 if len(trs) >= 14 else current * 0.02
        atr_pct = atr / current * 100

        # ─── حساب النقاط ───────────────────────────────────────────
        score = 0
        signals = []

        # 1. RSI: أفضل نطاق للانفجار هو 40-60 (ليس مشبعاً بعد)
        if 35 <= rsi <= 55:
            score += 25
            signals.append(f"RSI={rsi:.0f} في النطاق الذهبي")
        elif rsi < 35:
            score += 15
            signals.append(f"RSI={rsi:.0f} مبالغة بيع")
        elif rsi > 70:
            score -= 10
            signals.append(f"RSI={rsi:.0f} مبالغة شراء")

        # 2. EMA Trend: السعر فوق EMA20 وEMA20 فوق EMA50
        ema_trend = 0
        if current > ema20 > ema50:
            score += 30
            ema_trend = 1
            signals.append("EMA20 > EMA50 اتجاه صاعد")
        elif current > ema20 and ema20 < ema50:
            score += 10
            ema_trend = 0.5
            signals.append("فوق EMA20 لكن اتجاه ضعيف")
        elif current < ema20:
            score -= 5
            ema_trend = -1

        # 3. Volume Spike: انفجار الحجم
        if vol_spike >= 4.0:
            score += 40
            signals.append(f"حجم {vol_spike:.1f}x انفجار ضخم!")
        elif vol_spike >= 2.5:
            score += 25
            signals.append(f"حجم {vol_spike:.1f}x ارتفاع قوي")
        elif vol_spike >= 1.5:
            score += 12
            signals.append(f"حجم {vol_spike:.1f}x ارتفاع معتدل")

        # 4. Price Momentum: زخم السعر
        if price_change > 3.0:
            score += 20
            signals.append(f"زخم +{price_change:.1f}% قوي")
        elif price_change > 1.0:
            score += 10
            signals.append(f"زخم +{price_change:.1f}%")
        elif price_change < -3.0:
            score -= 15
            signals.append(f"ضغط -{abs(price_change):.1f}%")

        # 5. ATR: تقلب عالٍ = فرصة انفجار
        if atr_pct > 3.0:
            score += 10
            signals.append(f"ATR={atr_pct:.1f}% تقلب عالٍ")

        # 6. Breakout Pattern: كسر أعلى نقطة في 20 شمعة
        recent_high = max(highs[-20:])
        if current >= recent_high * 0.99:
            score += 20
            signals.append("اختراق أعلى 20 شمعة!")

        # 7. Accumulation: حجم مرتفع مع سعر ثابت (تراكم الحيتان)
        avg_vol_20 = sum(vols[-20:]) / 20
        last_vol = vols[-1]
        price_stability = abs(current - closes[-2]) / closes[-2] * 100
        if last_vol > avg_vol_20 * 2 and price_stability < 0.5:
            score += 20
            signals.append("تراكم حيتان (حجم مرتفع + سعر ثابت)")

        return {
            "score": max(0, score),
            "rsi": rsi,
            "ema_trend": ema_trend,
            "vol_spike": vol_spike,
            "price_change": price_change,
            "atr_pct": atr_pct,
            "signals": signals,
            "current_price": current,
            "ema20": ema20,
            "ema50": ema50,
        }

    def _fetch_coin_data(self, symbol: str) -> Optional[Dict]:
        """جلب بيانات عملة واحدة"""
        try:
            raw_ohlcv = self.okx.get_ohlcv(symbol, timeframe='1h', limit=100)
            if not raw_ohlcv or len(raw_ohlcv) < 50:
                return None
            ohlcv = [
                {
                    'timestamp': c[0],
                    'open':   float(c[1]),
                    'high':   float(c[2]),
                    'low':    float(c[3]),
                    'close':  float(c[4]),
                    'volume': float(c[5]) if len(c) > 5 else 0.0,
                }
                for c in raw_ohlcv
            ]
            return ohlcv
        except Exception as e:
            logger.debug(f"خطأ في جلب {symbol}: {e}")
            return None

    def analyze_all_sectors(self) -> Dict:
        """
        تحليل كل القطاعات وإيجاد:
        1. القطاع الأقوى (أعلى تدفق سيولة)
        2. أفضل عملة في كل قطاع (المهيأة للانفجار)
        Returns: dict with sector analysis
        """
        # فحص الكاش
        if time.time() - self._cache_time < self._cache_ttl and self._sector_cache:
            logger.info("✅ استخدام كاش القطاعات (حديث)")
            return self._sector_cache

        logger.info("🔍 بدء تحليل القطاعات الكامل...")
        sector_results = {}

        for sector_name, coins in SECTOR_MAP.items():
            sector_scores = []
            best_coin = None
            best_score = -1

            for symbol in coins:
                try:
                    ohlcv = self._fetch_coin_data(symbol)
                    if not ohlcv:
                        continue

                    momentum = self._calc_momentum_score(ohlcv)
                    score = momentum["score"]

                    sector_scores.append(score)

                    if score > best_score:
                        best_score = score
                        best_coin = {
                            "symbol": symbol,
                            "score": score,
                            "rsi": momentum["rsi"],
                            "vol_spike": momentum["vol_spike"],
                            "price_change": momentum["price_change"],
                            "signals": momentum["signals"],
                            "current_price": momentum["current_price"],
                            "ema_trend": momentum["ema_trend"],
                        }
                except Exception as e:
                    logger.debug(f"خطأ في {symbol}: {e}")
                    continue

            if sector_scores:
                avg_score = sum(sector_scores) / len(sector_scores)
                max_score = max(sector_scores)
                # نقاط القطاع = متوسط + 30% من الأعلى (لمكافأة القطاعات ذات العملات القوية)
                sector_total = avg_score * 0.7 + max_score * 0.3

                sector_results[sector_name] = {
                    "sector": sector_name,
                    "total_score": round(sector_total, 1),
                    "avg_score": round(avg_score, 1),
                    "max_score": round(max_score, 1),
                    "coins_analyzed": len(sector_scores),
                    "best_coin": best_coin,
                }
                logger.info(
                    f"  📊 {sector_name}: نقاط={sector_total:.0f} | "
                    f"أفضل عملة={best_coin['symbol'] if best_coin else 'N/A'} "
                    f"(نقاط={best_score:.0f})"
                )

        # ترتيب القطاعات حسب القوة
        sorted_sectors = sorted(
            sector_results.values(),
            key=lambda x: x["total_score"],
            reverse=True
        )

        result = {
            "sectors": sorted_sectors,
            "top_sector": sorted_sectors[0] if sorted_sectors else None,
            "top_coins_per_sector": [
                s["best_coin"] for s in sorted_sectors if s.get("best_coin")
            ],
            "timestamp": time.time(),
        }

        # حفظ في الكاش
        self._sector_cache = result
        self._cache_time = time.time()

        logger.info(f"✅ تحليل القطاعات اكتمل: {len(sorted_sectors)} قطاع")
        if sorted_sectors:
            top = sorted_sectors[0]
            logger.info(
                f"🏆 القطاع الأقوى: {top['sector']} "
                f"(نقاط={top['total_score']:.0f}) | "
                f"أفضل عملة: {top['best_coin']['symbol'] if top.get('best_coin') else 'N/A'}"
            )

        return result

    def get_explosion_candidates(self, min_score: int = 60) -> List[Dict]:
        """
        إرجاع قائمة العملات المهيأة للانفجار من كل قطاع
        min_score: الحد الأدنى للنقاط للاعتبار العملة مهيأة للانفجار
        """
        analysis = self.analyze_all_sectors()
        candidates = []

        for sector_data in analysis.get("sectors", []):
            best_coin = sector_data.get("best_coin")
            if best_coin and best_coin["score"] >= min_score:
                candidates.append({
                    **best_coin,
                    "sector": sector_data["sector"],
                    "sector_score": sector_data["total_score"],
                    "sector_rank": analysis["sectors"].index(sector_data) + 1,
                })

        # ترتيب حسب نقاط العملة
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def get_sector_for_symbol(self, symbol: str) -> Tuple[str, float]:
        """
        إرجاع القطاع ونقاطه لعملة معينة
        Returns: (sector_name, sector_score)
        """
        sector_name = self.get_sector(symbol)
        analysis = self._sector_cache
        if analysis:
            for s in analysis.get("sectors", []):
                if s["sector"] == sector_name:
                    return sector_name, s["total_score"]
        return sector_name, 0.0

    def format_sector_report(self) -> str:
        """تنسيق تقرير القطاعات لإرساله عبر Telegram"""
        analysis = self.analyze_all_sectors()
        sectors = analysis.get("sectors", [])
        if not sectors:
            return "⚠️ لا توجد بيانات قطاعات"

        lines = [
            "🏦 <b>تقرير تدفق السيولة القطاعية</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
        ]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, sector in enumerate(sectors[:5]):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            best = sector.get("best_coin", {})
            best_sym = best.get("symbol", "N/A").replace("/USDT", "") if best else "N/A"
            best_score = best.get("score", 0) if best else 0
            vol_spike = best.get("vol_spike", 1.0) if best else 1.0
            price_chg = best.get("price_change", 0) if best else 0

            lines.append(
                f"{medal} <b>{sector['sector']}</b> — نقاط: {sector['total_score']:.0f}\n"
                f"   💎 أفضل عملة: <b>{best_sym}</b> | نقاط: {best_score:.0f} | "
                f"حجم: {vol_spike:.1f}x | تغير: {price_chg:+.1f}%"
            )

        lines.append("━━━━━━━━━━━━━━━━━━━━━")

        # العملات المهيأة للانفجار
        candidates = self.get_explosion_candidates(min_score=60)
        if candidates:
            lines.append("🚀 <b>عملات مهيأة للانفجار:</b>")
            for c in candidates[:5]:
                sym = c["symbol"].replace("/USDT", "")
                sigs = ", ".join(c.get("signals", [])[:2])
                lines.append(
                    f"  🎯 <b>{sym}</b> ({c['sector']}) — "
                    f"نقاط: {c['score']:.0f} | {sigs}"
                )

        return "\n".join(lines)
