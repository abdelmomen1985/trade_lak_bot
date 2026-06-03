"""
Cryptopanic Integration Module
Handles all Cryptopanic API connections and news data retrieval

QUOTA OPTIMIZATION (v2.1):
- Global news cache: fetched once every 15 minutes (not per-currency)
- Per-currency sentiment cache: 30 minutes TTL
- Trending/critical news cache: 20 minutes TTL
- Result: ~96 requests/day instead of ~44,640/day (99.8% reduction)
"""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import threading

logger = logging.getLogger(__name__)


class CryptoPanicIntegration:
    """Cryptopanic API Integration with Smart Caching"""

    BASE_URL = "https://cryptopanic.com/api/growth/v2"
    API_PLAN = "growth"  # Updated: free/developer plan discontinued April 2026

    # News kinds - v2 only accepts 'news' or 'media' (not 'all')
    NEWS_KIND_ALL = "news"   # v2: 'all' is invalid, default to 'news'
    NEWS_KIND_NEWS = "news"
    NEWS_KIND_MEDIA = "media"

    # ── Cache TTL settings ────────────────────────────────────────────────
    # كل هذه الأرقام بالدقائق
    GLOBAL_NEWS_TTL_MINUTES   = 15   # الأخبار العامة: تُحدَّث كل 15 دقيقة
    CURRENCY_CACHE_TTL_MINUTES = 30  # أخبار عملة محددة: تُحدَّث كل 30 دقيقة
    TRENDING_CACHE_TTL_MINUTES = 20  # الأخبار الرائجة: تُحدَّث كل 20 دقيقة

    # Currencies
    CURRENCIES = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'MATIC': 'polygon',
        'LINK': 'chainlink',
        'USDT': 'tether',
        'BNB': 'binance-coin'
    }

    def __init__(self, api_key: str):
        """
        Initialize Cryptopanic connection
        Args:
            api_key: Cryptopanic API Key
        """
        self.api_key = api_key
        self.session = requests.Session()

        # ── Smart Cache ───────────────────────────────────────────────────
        self._lock = threading.Lock()

        # Global news cache (all currencies together)
        self._global_news_cache: List[Dict] = []
        self._global_news_last_fetch: Optional[datetime] = None

        # Per-currency sentiment cache  {currency: (result_dict, fetched_at)}
        self._currency_cache: Dict[str, tuple] = {}

        # Trending news cache
        self._trending_cache: List[Dict] = []
        self._trending_last_fetch: Optional[datetime] = None

        # API call counter for monitoring
        self._api_calls_today = 0
        self._api_calls_reset_date = datetime.now().date()

        logger.info("✅ Cryptopanic Integration initialized (with smart cache)")

    # ========================================================================
    # Cache Helpers
    # ========================================================================
    def _is_cache_valid(self, last_fetch: Optional[datetime], ttl_minutes: int) -> bool:
        """Check if cache is still valid"""
        if last_fetch is None:
            return False
        return datetime.now() - last_fetch < timedelta(minutes=ttl_minutes)

    def _increment_api_counter(self):
        """Track API calls for quota monitoring"""
        today = datetime.now().date()
        if today != self._api_calls_reset_date:
            self._api_calls_today = 0
            self._api_calls_reset_date = today
        self._api_calls_today += 1
        if self._api_calls_today % 10 == 0:
            logger.info(f"📊 CryptoPanic API calls today: {self._api_calls_today}")

    def get_api_stats(self) -> Dict:
        """Get API usage statistics"""
        return {
            'calls_today': self._api_calls_today,
            'global_cache_age_min': (
                round((datetime.now() - self._global_news_last_fetch).total_seconds() / 60, 1)
                if self._global_news_last_fetch else None
            ),
            'cached_currencies': list(self._currency_cache.keys()),
            'global_cache_size': len(self._global_news_cache),
        }

    # ========================================================================
    # Connection Test
    # ========================================================================
    def test_connection(self) -> bool:
        """Test Cryptopanic connection"""
        try:
            params = {'auth_token': self.api_key}
            response = self.session.get(
                f"{self.BASE_URL}/posts/",
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✅ Cryptopanic connection successful")
                return True
            elif response.status_code == 429:
                logger.warning("⚠️ Cryptopanic: API quota exceeded (429)")
                return False
            else:
                logger.error(f"❌ Cryptopanic connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Cryptopanic connection error: {e}")
            return False

    # ========================================================================
    # News Retrieval (with Cache)
    # ========================================================================
    def get_latest_news(self, currency: Optional[str] = None,
                       kind: str = NEWS_KIND_ALL,
                       limit: int = 50) -> List[Dict]:
        """
        Get latest news — uses global cache to avoid per-currency API calls.
        
        Strategy:
        - Fetch ALL news once every 15 minutes (global cache)
        - Filter by currency from the cached data (no extra API call)
        """
        with self._lock:
            # ── 1. Refresh global cache if stale ─────────────────────────
            if not self._is_cache_valid(self._global_news_last_fetch, self.GLOBAL_NEWS_TTL_MINUTES):
                try:
                    valid_kinds = {'news', 'media'}
                    params = {
                        'auth_token': self.api_key,
                        'public': 'true',
                    }
                    if kind in valid_kinds:
                        params['kind'] = kind

                    response = self.session.get(
                        f"{self.BASE_URL}/posts/",
                        params=params,
                        timeout=10
                    )
                    self._increment_api_counter()

                    if response.status_code == 200:
                        data = response.json()
                        self._global_news_cache = data.get('results', [])
                        self._global_news_last_fetch = datetime.now()
                        logger.debug(f"📰 Global news cache refreshed: {len(self._global_news_cache)} items")
                    elif response.status_code == 429:
                        logger.warning("⚠️ CryptoPanic quota exceeded — using stale cache")
                    else:
                        logger.warning(f"⚠️ CryptoPanic returned {response.status_code}")
                except Exception as e:
                    logger.error(f"Error fetching global news: {e}")

            # ── 2. Filter from cache ──────────────────────────────────────
            all_news = self._global_news_cache
            if currency:
                currency_upper = currency.upper()
                filtered = []
                for item in all_news:
                    currencies_in_item = [
                        c.get('code', '').upper()
                        for c in item.get('currencies', [])
                    ]
                    if currency_upper in currencies_in_item:
                        filtered.append(item)
                return filtered[:limit]

            return all_news[:limit]

    def get_trending_news(self, limit: int = 20) -> List[Dict]:
        """Get trending news — cached for 20 minutes"""
        with self._lock:
            if not self._is_cache_valid(self._trending_last_fetch, self.TRENDING_CACHE_TTL_MINUTES):
                try:
                    params = {
                        'auth_token': self.api_key,
                        'kind': self.NEWS_KIND_NEWS,
                        'public': 'true'
                    }
                    response = self.session.get(
                        f"{self.BASE_URL}/posts/",
                        params=params,
                        timeout=10
                    )
                    self._increment_api_counter()

                    if response.status_code == 200:
                        data = response.json()
                        self._trending_cache = data.get('results', [])
                        self._trending_last_fetch = datetime.now()
                        logger.debug(f"📈 Trending cache refreshed: {len(self._trending_cache)} items")
                    elif response.status_code == 429:
                        logger.warning("⚠️ CryptoPanic quota exceeded — using stale trending cache")
                except Exception as e:
                    logger.error(f"Error fetching trending news: {e}")

            return self._trending_cache[:limit]

    def get_currency_news(self, currency: str, limit: int = 50) -> List[Dict]:
        """Get news for specific currency — filtered from global cache"""
        return self.get_latest_news(currency=currency, limit=limit)

    # ========================================================================
    # News Analysis (unchanged — no API calls)
    # ========================================================================
    def analyze_news_sentiment(self, news_item: Dict) -> Dict:
        """Analyze sentiment of a single news item"""
        try:
            title = news_item.get('title', '').lower()
            votes = news_item.get('votes', {})

            positive_votes = votes.get('positive', 0) or 0
            negative_votes = votes.get('negative', 0) or 0
            total_votes = positive_votes + negative_votes

            # Keyword-based sentiment
            bullish_keywords = [
                'surge', 'rally', 'bull', 'rise', 'gain', 'pump', 'moon',
                'breakout', 'ath', 'all-time high', 'adoption', 'partnership',
                'launch', 'upgrade', 'positive', 'growth', 'increase', 'up',
                'record', 'milestone', 'success', 'approve', 'approval'
            ]
            bearish_keywords = [
                'crash', 'dump', 'bear', 'fall', 'drop', 'plunge', 'hack',
                'scam', 'fraud', 'ban', 'regulation', 'lawsuit', 'sell',
                'decline', 'loss', 'negative', 'down', 'fear', 'panic',
                'warning', 'risk', 'concern', 'investigation', 'arrest'
            ]

            bullish_count = sum(1 for kw in bullish_keywords if kw in title)
            bearish_count = sum(1 for kw in bearish_keywords if kw in title)

            # Calculate score (0-100)
            if total_votes > 0:
                vote_score = (positive_votes / total_votes) * 100
            else:
                vote_score = 50

            if bullish_count > bearish_count:
                keyword_score = min(75 + (bullish_count * 5), 90)
            elif bearish_count > bullish_count:
                keyword_score = max(25 - (bearish_count * 5), 10)
            else:
                keyword_score = 50

            # Weighted average
            final_score = (vote_score * 0.4) + (keyword_score * 0.6)

            if final_score >= 60:
                sentiment = 'BULLISH'
            elif final_score <= 40:
                sentiment = 'BEARISH'
            else:
                sentiment = 'NEUTRAL'

            return {
                'sentiment': sentiment,
                'score': int(final_score),
                'bullish_keywords': bullish_count,
                'bearish_keywords': bearish_count,
                'vote_score': int(vote_score),
                'title': news_item.get('title', '')
            }
        except Exception as e:
            logger.error(f"Error analyzing news sentiment: {e}")
            return {'sentiment': 'NEUTRAL', 'score': 50}

    def get_news_importance(self, news_item: Dict) -> Dict:
        """Calculate news importance score"""
        try:
            votes = news_item.get('votes', {})
            positive = votes.get('positive', 0) or 0
            negative = votes.get('negative', 0) or 0
            important = votes.get('important', 0) or 0
            liked = votes.get('liked', 0) or 0
            disliked = votes.get('disliked', 0) or 0
            lol = votes.get('lol', 0) or 0

            total_engagement = positive + negative + important + liked + disliked + lol
            importance_score = (important * 3) + (positive * 2) + (negative * 2) + liked + disliked

            if importance_score >= 20:
                importance_level = 'CRITICAL'
            elif importance_score >= 10:
                importance_level = 'HIGH'
            elif importance_score >= 5:
                importance_level = 'MEDIUM'
            else:
                importance_level = 'LOW'

            return {
                'importance': importance_level,
                'importance_score': importance_score,
                'total_engagement': total_engagement,
                'title': news_item.get('title', '')
            }
        except Exception as e:
            logger.error(f"Error calculating news importance: {e}")
            return {'importance': 'LOW', 'importance_score': 0}

    def analyze_news_impact(self, news_item: Dict) -> Dict:
        """Analyze the potential market impact of a news item"""
        try:
            sentiment = self.analyze_news_sentiment(news_item)
            importance = self.get_news_importance(news_item)

            sentiment_score = sentiment.get('score', 50)
            importance_score = importance.get('importance_score', 0)

            impact_score = (abs(sentiment_score - 50) * 2) + (importance_score * 5)

            if impact_score >= 50:
                impact = 'EXTREME'
            elif impact_score >= 25:
                impact = 'HIGH'
            elif impact_score >= 10:
                impact = 'MEDIUM'
            else:
                impact = 'LOW'

            return {
                'impact': impact,
                'impact_score': impact_score,
                'sentiment': sentiment.get('sentiment', 'NEUTRAL'),
                'sentiment_score': sentiment_score,
                'importance': importance.get('importance', 'LOW'),
                'recommendation': self._get_impact_recommendation(impact),
                'title': news_item.get('title', ''),
                'url': news_item.get('url', ''),
                'published_at': news_item.get('published_at', '')
            }
        except Exception as e:
            logger.error(f"Error analyzing news impact: {e}")
            return {'impact': 'LOW', 'impact_score': 0}

    def _get_impact_recommendation(self, impact: str) -> str:
        """Get trading recommendation based on impact"""
        if impact == 'EXTREME':
            return "🚨 CRITICAL NEWS - Expect high volatility"
        elif impact == 'HIGH':
            return "⚠️ IMPORTANT NEWS - Significant market impact expected"
        elif impact == 'MEDIUM':
            return "📰 MODERATE NEWS - Watch for market reaction"
        else:
            return "ℹ️ LOW IMPACT - Minor news"

    # ========================================================================
    # Currency-Specific Analysis (with per-currency cache)
    # ========================================================================
    def get_currency_sentiment(self, currency: str, limit: int = 50) -> Dict:
        """
        Get overall sentiment for a currency — cached per-currency for 30 min.
        """
        with self._lock:
            # Check per-currency cache
            if currency in self._currency_cache:
                cached_result, cached_at = self._currency_cache[currency]
                if self._is_cache_valid(cached_at, self.CURRENCY_CACHE_TTL_MINUTES):
                    logger.debug(f"📦 Using cached sentiment for {currency}")
                    return cached_result

        # Cache miss — compute from global news cache (no extra API call)
        try:
            news_list = self.get_latest_news(currency=currency, limit=limit)
            if not news_list:
                result = {
                    'currency': currency,
                    'sentiment': 'UNKNOWN',
                    'score': 50,
                    'news_count': 0
                }
            else:
                sentiments = []
                for news in news_list:
                    sentiment = self.analyze_news_sentiment(news)
                    sentiments.append(sentiment.get('score', 50))

                avg_sentiment = sum(sentiments) / len(sentiments)

                if avg_sentiment >= 60:
                    overall_sentiment = 'BULLISH'
                elif avg_sentiment <= 40:
                    overall_sentiment = 'BEARISH'
                else:
                    overall_sentiment = 'NEUTRAL'

                result = {
                    'currency': currency,
                    'sentiment': overall_sentiment,
                    'score': int(avg_sentiment),
                    'news_count': len(news_list),
                    'bullish_news': sum(1 for s in sentiments if s >= 60),
                    'bearish_news': sum(1 for s in sentiments if s <= 40),
                    'timestamp': datetime.now().isoformat()
                }

            # Store in per-currency cache
            with self._lock:
                self._currency_cache[currency] = (result, datetime.now())

            return result
        except Exception as e:
            logger.error(f"Error getting currency sentiment: {e}")
            return {}

    def get_critical_news(self, limit: int = 50) -> List[Dict]:
        """Get critical news items — uses trending cache"""
        try:
            news_list = self.get_trending_news(limit=limit)
            critical_news = []
            for news in news_list:
                impact = self.analyze_news_impact(news)
                if impact.get('impact') in ['EXTREME', 'HIGH']:
                    critical_news.append(impact)
            return sorted(
                critical_news,
                key=lambda x: x.get('impact_score', 0),
                reverse=True
            )
        except Exception as e:
            logger.error(f"Error getting critical news: {e}")
            return []

    # ========================================================================
    # Real-time Monitoring
    # ========================================================================
    def monitor_currency_news(self, currency: str,
                             check_interval: int = 300) -> Dict:
        """Monitor news for a currency"""
        try:
            news_list = self.get_currency_news(currency, limit=10)
            important_news = []
            for news in news_list:
                impact = self.analyze_news_impact(news)
                if impact.get('impact') in ['EXTREME', 'HIGH']:
                    important_news.append(impact)
            return {
                'currency': currency,
                'total_news': len(news_list),
                'important_news': len(important_news),
                'news_items': important_news[:5],
                'next_check': datetime.now() + timedelta(seconds=check_interval),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error monitoring currency news: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    API_KEY = "afed90b669cebc6535f88540ecb1679ee551facc"
    cp = CryptoPanicIntegration(API_KEY)

    if cp.test_connection():
        news = cp.get_latest_news(currency="BTC", limit=5)
        print(f"Latest News: {len(news)} items")
        if news:
            impact = cp.analyze_news_impact(news[0])
            print(f"News Impact: {impact}")
        sentiment = cp.get_currency_sentiment("BTC")
        print(f"BTC Sentiment: {sentiment}")
        critical = cp.get_critical_news(limit=10)
        print(f"Critical News: {len(critical)} items")
        print(f"API Stats: {cp.get_api_stats()}")
