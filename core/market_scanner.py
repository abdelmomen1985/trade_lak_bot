# ============================================================
# Trade Lak Bot - Autonomous Market Scanner v3 (Sector Liquidity Hunter)
# وحدة فحص السوق المستقلة — مع محرك صيد السيولة القطاعية
# ============================================================
import logging
import requests as _requests
from config.config import (
    SCAN_TOP_N_COINS, MIN_VOLUME_24H_USD,
    MIN_SCORE_FOR_SPOT, MIN_SCORE_FOR_FUTURES, MIN_SCORE_FOR_SHORT
)
logger = logging.getLogger(__name__)

# ─── AI Enhancement Integration ──────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, '/root/trade_lak_bot/core')
try:
    from ai_enhancement_patch import get_ai_boost, get_fear_greed_text, get_market_warning
    _AI_AVAILABLE = True
    logger.info("✅ AI Enhancement (Fear&Greed + LSTM + Crash) loaded in MarketScanner!")
except Exception as _e:
    _AI_AVAILABLE = False
    logger.warning(f"⚠️ AI Enhancement unavailable: {_e}")
    def get_ai_boost(*a, **kw): return 0, {}
    def get_fear_greed_text(): return ""
    def get_market_warning(*a): return ""

# ─── Sector Liquidity Hunter ─────────────────────────────────────────────────
try:
    from core.sector_liquidity_hunter import SectorLiquidityHunter, COIN_TO_SECTOR
    _SECTOR_AVAILABLE = True
    logger.info("✅ Sector Liquidity Hunter loaded!")
except Exception as _se:
    _SECTOR_AVAILABLE = False
    logger.warning(f"⚠️ Sector Hunter unavailable: {_se}")
    COIN_TO_SECTOR = {}
# ──────────────────────────────────────────────────────────────────────────────

# الحد الأدنى للثقة لقبول الإشارة
MIN_CONFIDENCE_SPOT    = 25   # 25% ثقة للـ Spot (مُخفَّض لتفعيل التداول)
MIN_CONFIDENCE_FUTURES = 55   # 55% ثقة للـ Futures (أعلى لأنه أخطر)

class MarketScanner:
    """
    يفحص كامل سوق العملات الرقمية باستخدام Intelligence Engine الكامل
    مع محرك صيد السيولة القطاعية لتحديد العملات المهيأة للانفجار
    """
    def __init__(self, okx_client, exchange_router=None):
        self.okx = okx_client
        self.router = exchange_router  # ExchangeRouter
        # تهيئة محرك القطاعات
        if _SECTOR_AVAILABLE:
            self.sector_hunter = SectorLiquidityHunter(okx_client)
            logger.info("✅ Sector Liquidity Hunter initialized in MarketScanner")
        else:
            self.sector_hunter = None

    def get_top_opportunities(self):
        """
        جلب أفضل العملات من حيث حجم التداول وتصفيتها
        مع إعطاء أولوية للعملات في القطاعات ذات السيولة العالية
        """
        try:
            logger.info(f"فحص السوق الكامل — أفضل {SCAN_TOP_N_COINS} عملة...")
            # استخدام OKX REST API مباشرة لتجنب خطأ BCH-USD في ccxt
            _okx_resp = _requests.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SPOT"},
                timeout=15
            ).json()
            _raw_tickers = _okx_resp.get("data", [])
            usdt_pairs = {}
            for _t in _raw_tickers:
                _inst = _t.get("instId", "")
                if not _inst.endswith("-USDT"):
                    continue
                _vol = float(_t.get("volCcy24h", 0) or 0)
                if _vol <= 0:
                    continue
                _sym = _inst.replace("-USDT", "/USDT")
                usdt_pairs[_sym] = {
                    "quoteVolume": _vol,
                    "last": float(_t.get("last", 0) or 0),
                    "high": float(_t.get("high24h", 0) or 0),
                    "low": float(_t.get("low24h", 0) or 0),
                    "percentage": float(_t.get("chgUtc0", 0) or 0),
                }
            sorted_pairs = sorted(
                usdt_pairs.items(),
                key=lambda x: x[1].get('quoteVolume', 0),
                reverse=True
            )
            stable_coins = {
                'USDT','USDC','BUSD','DAI','TUSD','USDP','FRAX','USDD','FDUSD','BTC',
                'USDG','RLUSD','PYUSD','GUSD','SUSD','LUSD','CRVUSD','USDE','USDB',
                'USDX','CUSD','HUSD','EURS','USDK','USDJ','XUSD','USDQ',
                'USDN','USDH','USDR','USDV','USDY','USDZ','EURC','EUROC'
            }
            candidates = []
            for symbol, ticker in sorted_pairs[:SCAN_TOP_N_COINS]:
                volume_24h = ticker.get('quoteVolume', 0)
                if volume_24h < MIN_VOLUME_24H_USD:
                    continue
                base = symbol.replace('/USDT', '')
                if base in stable_coins:
                    continue
                candidates.append({
                    'symbol':          symbol,
                    'price':           ticker.get('last', 0),
                    'volume_24h':      volume_24h,
                    'price_change_pct': ticker.get('percentage', 0) or 0,
                    'high_24h':        ticker.get('high', 0),
                    'low_24h':         ticker.get('low', 0),
                    'sector':          COIN_TO_SECTOR.get(symbol, 'Other'),
                })
            # Bybit exclusive symbols
            if self.router is not None:
                try:
                    bybit_exclusive = self.router.get_bybit_exclusive_symbols()
                    bybit_resp = _requests.get(
                        "https://api.bybit.com/v5/market/tickers?category=spot",
                        timeout=10
                    ).json()
                    bybit_tickers = {
                        item["symbol"].replace("USDT", ""): item
                        for item in bybit_resp.get("result", {}).get("list", [])
                        if item["symbol"].endswith("USDT")
                    }
                    added = 0
                    for coin in bybit_exclusive:
                        if coin in stable_coins:
                            continue
                        ticker = bybit_tickers.get(coin)
                        if not ticker:
                            continue
                        vol = float(ticker.get("turnover24h", 0) or 0)
                        if vol < MIN_VOLUME_24H_USD:
                            continue
                        sym = coin + "/USDT"
                        candidates.append({
                            "symbol": sym,
                            "price": float(ticker.get("lastPrice", 0) or 0),
                            "volume_24h": vol,
                            "price_change_pct": float(ticker.get("price24hPcnt", 0) or 0) * 100,
                            "high_24h": float(ticker.get("highPrice24h", 0) or 0),
                            "low_24h": float(ticker.get("lowPrice24h", 0) or 0),
                            "sector": COIN_TO_SECTOR.get(sym, "Other"),
                            "exchange": "bybit",
                        })
                        added += 1
                    if added > 0:
                        logger.info(f"[Router] added {added} Bybit-exclusive coins")
                except Exception as _bybit_err:
                    logger.warning(f"[Router] Bybit fetch error: {_bybit_err}")
            logger.info(f"Found {len(candidates)} coins (OKX + Bybit)")
            return candidates
        except Exception as e:
            logger.error(f"خطأ في فحص السوق: {e}")
            return []

    def get_sector_boost(self, symbol: str) -> float:
        """
        حساب مكافأة القطاع للعملة
        إذا كانت العملة في القطاع الأقوى → مكافأة +0.15 على weighted_score
        """
        if not self.sector_hunter:
            return 0.0
        try:
            cache = self.sector_hunter._sector_cache
            if not cache:
                return 0.0
            sectors = cache.get("sectors", [])
            if not sectors:
                return 0.0
            # أفضل 3 قطاعات تحصل على مكافأة
            top3_sectors = {s["sector"] for s in sectors[:3]}
            coin_sector = COIN_TO_SECTOR.get(symbol, "Other")
            if coin_sector in top3_sectors:
                # مكافأة أكبر للقطاع الأول
                rank = next((i for i, s in enumerate(sectors) if s["sector"] == coin_sector), 10)
                if rank == 0:
                    return 0.20   # القطاع الأول: +20%
                elif rank == 1:
                    return 0.12   # القطاع الثاني: +12%
                else:
                    return 0.07   # القطاع الثالث: +7%
            return 0.0
        except Exception:
            return 0.0

    def find_best_trades(self, intelligence_engine, max_results=5):
        """
        البحث الكامل عن أفضل فرص التداول باستخدام Intelligence Engine
        مع دمج تحليل القطاعات لتحديد العملات المهيأة للانفجار
        """
        candidates = self.get_top_opportunities()
        if not candidates:
            return []

        # ── تشغيل تحليل القطاعات في الخلفية ──────────────────────
        sector_analysis = {}
        if self.sector_hunter:
            try:
                logger.info("🔍 تحليل القطاعات لتحديد تدفق السيولة...")
                sector_analysis = self.sector_hunter.analyze_all_sectors()
                top_sector = sector_analysis.get("top_sector", {})
                if top_sector:
                    logger.info(
                        f"🏆 القطاع الأقوى: {top_sector.get('sector')} "
                        f"(نقاط={top_sector.get('total_score', 0):.0f})"
                    )
                # قائمة العملات المهيأة للانفجار
                explosion_candidates = self.sector_hunter.get_explosion_candidates(min_score=60)
                if explosion_candidates:
                    logger.info(f"🚀 عملات مهيأة للانفجار: {[c['symbol'] for c in explosion_candidates[:5]]}")
            except Exception as e:
                logger.warning(f"⚠️ خطأ في تحليل القطاعات: {e}")

        scored_opportunities = []
        for coin_data in candidates:
            symbol = coin_data['symbol']
            try:
                # OHLCV from correct exchange
                _exchange_src = coin_data.get("exchange", "okx")
                if _exchange_src == "bybit" and self.router and self.router.bybit:
                    _coin = symbol.replace("/USDT", "")
                    _bybit_kline = _requests.get(
                        "https://api.bybit.com/v5/market/kline",
                        params={"category": "spot", "symbol": _coin + "USDT",
                                "interval": "60", "limit": 100},
                        timeout=10
                    ).json()
                    _klines = _bybit_kline.get("result", {}).get("list", [])
                    raw_ohlcv = [
                        [int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                         float(k[4]), float(k[5])]
                        for k in reversed(_klines)
                    ] if _klines else []
                else:
                    raw_ohlcv = self.okx.get_ohlcv(symbol, timeframe='1h', limit=100)
                if not raw_ohlcv or len(raw_ohlcv) < 50:
                    continue
                # تحويل OHLCV من list إلى dict
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
                if not ohlcv or len(ohlcv) < 50:
                    continue

                volume_24h = coin_data.get('volume_24h', 0)

                # ── التحليل الشامل عبر Intelligence Engine ──
                analysis = intelligence_engine.analyze(
                    symbol, ohlcv, current_volume=volume_24h
                )
                final_signal = analysis.get('final_signal', 'NEUTRAL')
                direction    = analysis.get('direction')
                market_type  = analysis.get('market_type', 'none')
                confidence   = analysis.get('confidence', 0)
                score        = analysis.get('weighted_score', 0)

                # ── مكافأة القطاع ─────────────────────────────────
                sector_boost = self.get_sector_boost(symbol)
                if sector_boost > 0:
                    score += sector_boost * abs(score) if score != 0 else sector_boost * 0.3
                    confidence = min(confidence + sector_boost * 20, 95)
                    analysis['sector_boost'] = sector_boost

                # تصفية الإشارات الضعيفة
                if market_type == 'none' or direction is None:
                    continue
                if direction == 'LONG' and confidence < MIN_CONFIDENCE_SPOT:
                    continue
                if direction == 'SHORT' and confidence < MIN_CONFIDENCE_FUTURES:
                    continue

                # تحويل النقاط الموزونة إلى نقاط 0-10 للتوافق مع بقية النظام
                normalized_score = abs(score) * 10

                # ── معلومات القطاع ────────────────────────────────
                coin_sector = COIN_TO_SECTOR.get(symbol, 'Other')
                sector_score = 0
                if sector_analysis:
                    for s in sector_analysis.get("sectors", []):
                        if s["sector"] == coin_sector:
                            sector_score = s.get("total_score", 0)
                            break

                # ── فحص هل هي من العملات المهيأة للانفجار ────────
                is_explosion_candidate = False
                if self.sector_hunter:
                    explosion_list = self.sector_hunter.get_explosion_candidates(min_score=55)
                    is_explosion_candidate = any(c['symbol'] == symbol for c in explosion_list)

                opportunity = {
                    'symbol':                symbol,
                    'score':                 normalized_score,
                    'direction':             direction,
                    'market_type':           market_type,
                    'confidence':            confidence,
                    'reasons':               analysis.get('reasons', []),
                    'price':                 coin_data['price'],
                    'volume_24h':            volume_24h,
                    'ohlcv':                 ohlcv,
                    'analysis':              analysis,
                    'sector':                coin_sector,
                    'sector_score':          sector_score,
                    'sector_boost':          sector_boost,
                    'is_explosion_candidate': is_explosion_candidate,
                }
                scored_opportunities.append(opportunity)
                explosion_tag = "🚀 EXPLOSION!" if is_explosion_candidate else ""
                logger.info(
                    f"فرصة مكتشفة: {symbol} [{coin_sector}] | {final_signal} | "
                    f"الثقة: {confidence:.0f}% | السوق: {market_type} "
                    f"| مكافأة قطاع: +{sector_boost:.0%} {explosion_tag}"
                )
            except Exception as e:
                logger.debug(f"تخطي {symbol}: {e}")
                continue

        # ترتيب: العملات المهيأة للانفجار أولاً، ثم حسب الثقة والنقاط
        scored_opportunities.sort(
            key=lambda x: (
                x.get('is_explosion_candidate', False),
                x['confidence'],
                x['score']
            ),
            reverse=True
        )
        top = scored_opportunities[:max_results]
        logger.info(f"\n{'='*50}")
        logger.info(f"أفضل {len(top)} فرصة تم اكتشافها:")
        for i, opp in enumerate(top, 1):
            explosion_tag = "🚀" if opp.get('is_explosion_candidate') else ""
            logger.info(
                f"  {i}. {opp['symbol']} [{opp.get('sector','?')}] {explosion_tag} | "
                f"{opp['direction']} | السوق: {opp['market_type']} | "
                f"الثقة: {opp['confidence']:.0f}% | النقاط: {opp['score']:.1f}"
            )
        logger.info(f"{'='*50}\n")
        return top

    def get_sector_report(self) -> str:
        """إرجاع تقرير القطاعات لإرساله عبر Telegram"""
        if self.sector_hunter:
            return self.sector_hunter.format_sector_report()
        return "⚠️ محرك القطاعات غير متاح"
