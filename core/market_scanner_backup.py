# ============================================================
# Trade Lak Bot - Autonomous Market Scanner v2
# وحدة فحص السوق المستقلة — تستخدم Intelligence Engine الكامل
# ============================================================

import logging
from config.config import (
    SCAN_TOP_N_COINS, MIN_VOLUME_24H_USD,
    MIN_SCORE_FOR_SPOT, MIN_SCORE_FOR_FUTURES, MIN_SCORE_FOR_SHORT
)

logger = logging.getLogger(__name__)

# الحد الأدنى للثقة لقبول الإشارة
MIN_CONFIDENCE_SPOT    = 40   # 40% ثقة للـ Spot
MIN_CONFIDENCE_FUTURES = 55   # 55% ثقة للـ Futures (أعلى لأنه أخطر)


class MarketScanner:
    """
    يفحص كامل سوق العملات الرقمية باستخدام Intelligence Engine الكامل
    Scans the entire crypto market using the full Intelligence Engine
    """

    def __init__(self, okx_client):
        self.okx = okx_client

    def get_top_opportunities(self):
        """
        جلب أفضل العملات من حيث حجم التداول وتصفيتها
        Fetch top coins by volume and filter for opportunities
        """
        try:
            logger.info(f"فحص السوق الكامل — أفضل {SCAN_TOP_N_COINS} عملة...")
            all_tickers = self.okx.exchange.fetch_tickers()

            usdt_pairs = {
                symbol: data for symbol, data in all_tickers.items()
                if symbol.endswith('/USDT') and data.get('quoteVolume', 0) > 0
            }

            sorted_pairs = sorted(
                usdt_pairs.items(),
                key=lambda x: x[1].get('quoteVolume', 0),
                reverse=True
            )

            stable_coins = {'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FRAX', 'USDD', 'FDUSD'}
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
                })

            logger.info(f"تم العثور على {len(candidates)} عملة مؤهلة للتحليل")
            return candidates

        except Exception as e:
            logger.error(f"خطأ في فحص السوق: {e}")
            return []

    def find_best_trades(self, intelligence_engine, max_results=5):
        """
        البحث الكامل عن أفضل فرص التداول باستخدام Intelligence Engine
        Full market search using the complete Intelligence Engine

        intelligence_engine: IntelligenceEngine instance (يدمج كل المصادر)
        Returns: sorted list of best opportunities
        """
        candidates = self.get_top_opportunities()
        if not candidates:
            return []

        scored_opportunities = []

        for coin_data in candidates:
            symbol = coin_data['symbol']
            try:
                # جلب بيانات الشموع
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

                # تصفية الإشارات الضعيفة
                if market_type == 'none' or direction is None:
                    continue

                if direction == 'LONG' and confidence < MIN_CONFIDENCE_SPOT:
                    continue
                if direction == 'SHORT' and confidence < MIN_CONFIDENCE_FUTURES:
                    continue

                # تحويل النقاط الموزونة إلى نقاط 0-10 للتوافق مع بقية النظام
                normalized_score = abs(score) * 10

                opportunity = {
                    'symbol':      symbol,
                    'score':       normalized_score,
                    'direction':   direction,
                    'market_type': market_type,
                    'confidence':  confidence,
                    'reasons':     analysis.get('reasons', []),
                    'price':       coin_data['price'],
                    'volume_24h':  volume_24h,
                    'ohlcv':       ohlcv,
                    'analysis':    analysis,   # التحليل الكامل للمرجع
                }

                scored_opportunities.append(opportunity)
                logger.info(
                    f"فرصة مكتشفة: {symbol} | {final_signal} | "
                    f"الثقة: {confidence:.0f}% | السوق: {market_type}"
                )

            except Exception as e:
                logger.debug(f"تخطي {symbol}: {e}")
                continue

        # ترتيب حسب الثقة أولاً ثم النقاط
        scored_opportunities.sort(
            key=lambda x: (x['confidence'], x['score']),
            reverse=True
        )

        top = scored_opportunities[:max_results]

        logger.info(f"\n{'='*50}")
        logger.info(f"أفضل {len(top)} فرصة تم اكتشافها:")
        for i, opp in enumerate(top, 1):
            logger.info(
                f"  {i}. {opp['symbol']} | {opp['direction']} | "
                f"السوق: {opp['market_type']} | "
                f"الثقة: {opp['confidence']:.0f}% | "
                f"النقاط: {opp['score']:.1f}"
            )
        logger.info(f"{'='*50}\n")

        return top
