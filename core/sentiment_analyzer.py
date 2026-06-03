# ============================================================
# Trade Lak Bot - Sentiment Analysis Engine
# محرك تحليل المشاعر — يحلل الأخبار ويتنبأ بحركات السوق
# ============================================================
# يستخدم:
#   - NewsAPI: أخبار العملات الرقمية
#   - NLP: معالجة اللغة الطبيعية
#   - Sentiment Scoring: تقييم إيجابي/سلبي
# ============================================================

import logging
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import re

logger = logging.getLogger(__name__)

# عتبات تحليل المشاعر
SENTIMENT_THRESHOLD_POSITIVE = 0.6
SENTIMENT_THRESHOLD_NEGATIVE = -0.6
NEWS_IMPACT_MULTIPLIER = 1.5  # تأثير الأخبار على القرار


class SentimentAnalyzer:
    """
    محرك تحليل المشاعر — يحلل أخبار العملات ويتنبأ بالحركات
    Sentiment Analysis Engine — analyzes crypto news and predicts movements
    """

    def __init__(self, newsapi_key):
        self.newsapi_key = newsapi_key
        self.sentiment_cache = {}  # تخزين مؤقت للمشاعر
        self.news_history = defaultdict(list)  # سجل الأخبار لكل عملة

    # ----------------------------------------------------------------
    # جلب الأخبار / Fetch News
    # ----------------------------------------------------------------

    def fetch_news(self, symbol, hours=24):
        """
        جلب أخبار العملة من NewsAPI
        Fetch news for a symbol from NewsAPI
        """
        try:
            coin_name = self._get_coin_name(symbol)
            if not coin_name:
                return []

            url = "https://newsapi.org/v2/everything"
            params = {
                "q": coin_name,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": self.newsapi_key,
                "pageSize": 50,
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                logger.warning(f"NewsAPI error: {response.status_code}")
                return []

            articles = response.json().get("articles", [])

            # تصفية الأخبار الحديثة فقط
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_articles = [
                a for a in articles
                if datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00")) > cutoff_time
            ]

            logger.info(f"جلب {len(recent_articles)} خبر حديث لـ {symbol}")
            return recent_articles

        except Exception as e:
            logger.error(f"خطأ في جلب الأخبار لـ {symbol}: {e}")
            return []

    # ----------------------------------------------------------------
    # تحليل المشاعر / Sentiment Analysis
    # ----------------------------------------------------------------

    def analyze_sentiment(self, text):
        """
        تحليل مشاعر النص (إيجابي/سلبي/محايد)
        Analyze sentiment of text (-1 to +1)
        """
        if not text:
            return 0.0

        text = text.lower()

        # كلمات إيجابية
        positive_words = {
            'surge', 'rally', 'bull', 'bullish', 'pump', 'moon', 'rocket',
            'gain', 'profit', 'soar', 'jump', 'breakthrough', 'record',
            'success', 'growth', 'adoption', 'partnership', 'integration',
            'upgrade', 'launch', 'innovation', 'boom', 'explosion',
            'positive', 'strong', 'excellent', 'amazing', 'fantastic',
        }

        # كلمات سلبية
        negative_words = {
            'crash', 'dump', 'bear', 'bearish', 'collapse', 'plunge',
            'loss', 'decline', 'fall', 'drop', 'hack', 'scam', 'fraud',
            'risk', 'warning', 'danger', 'concern', 'issue', 'problem',
            'negative', 'weak', 'poor', 'terrible', 'disaster',
            'bankruptcy', 'liquidation', 'exploit', 'vulnerability',
        }

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        sentiment = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, sentiment))

    # ----------------------------------------------------------------
    # تحليل الأخبار الكاملة / Full News Analysis
    # ----------------------------------------------------------------

    def analyze_news_for_symbol(self, symbol, hours=24):
        """
        تحليل شامل لجميع أخبار العملة
        Comprehensive analysis of all news for a symbol
        """
        articles = self.fetch_news(symbol, hours=hours)
        if not articles:
            return {
                "symbol": symbol,
                "sentiment": 0.0,
                "signal": "NEUTRAL",
                "article_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "articles": [],
            }

        sentiments = []
        positive_count = 0
        negative_count = 0
        analyzed_articles = []

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "")
            content = f"{title} {description}"

            sentiment = self.analyze_sentiment(content)
            sentiments.append(sentiment)

            if sentiment > SENTIMENT_THRESHOLD_POSITIVE:
                positive_count += 1
            elif sentiment < SENTIMENT_THRESHOLD_NEGATIVE:
                negative_count += 1

            analyzed_articles.append({
                "title": title,
                "sentiment": sentiment,
                "url": article.get("url"),
                "published_at": article.get("publishedAt"),
                "source": article.get("source", {}).get("name", "Unknown"),
            })

        # حساب المشاعر الإجمالية
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # تحديد الإشارة
        if avg_sentiment > SENTIMENT_THRESHOLD_POSITIVE:
            signal = "STRONG_POSITIVE"
        elif avg_sentiment > 0.3:
            signal = "POSITIVE"
        elif avg_sentiment < SENTIMENT_THRESHOLD_NEGATIVE:
            signal = "STRONG_NEGATIVE"
        elif avg_sentiment < -0.3:
            signal = "NEGATIVE"
        else:
            signal = "NEUTRAL"

        result = {
            "symbol": symbol,
            "sentiment": avg_sentiment,
            "signal": signal,
            "article_count": len(articles),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "articles": analyzed_articles[:10],  # أفضل 10 أخبار
        }

        # حفظ في السجل
        self.news_history[symbol].append(result)
        self.sentiment_cache[symbol] = result

        logger.info(
            f"تحليل الأخبار لـ {symbol}: {signal} | "
            f"المشاعر: {avg_sentiment:.2f} | "
            f"إيجابي: {positive_count} | سلبي: {negative_count}"
        )

        return result

    # ----------------------------------------------------------------
    # الإشارة التجارية من الأخبار / Trading Signal
    # ----------------------------------------------------------------

    def get_trading_signal(self, symbol, hours=24):
        """
        الحصول على إشارة تجارية بناءً على الأخبار
        Get trading signal based on news sentiment
        """
        result = self.analyze_news_for_symbol(symbol, hours=hours)
        sentiment = result["sentiment"]
        signal = result["signal"]

        # تحويل إلى إشارة تجارية
        if signal == "STRONG_POSITIVE":
            trade_signal = "STRONG_BUY"
            confidence = min(abs(sentiment) * 100, 90)
        elif signal == "POSITIVE":
            trade_signal = "BUY"
            confidence = abs(sentiment) * 100
        elif signal == "STRONG_NEGATIVE":
            trade_signal = "STRONG_SELL"
            confidence = min(abs(sentiment) * 100, 90)
        elif signal == "NEGATIVE":
            trade_signal = "SELL"
            confidence = abs(sentiment) * 100
        else:
            trade_signal = "NEUTRAL"
            confidence = 0

        return {
            "signal": trade_signal,
            "confidence": confidence,
            "sentiment": sentiment,
            "article_count": result["article_count"],
            "positive_count": result["positive_count"],
            "negative_count": result["negative_count"],
        }

    # ----------------------------------------------------------------
    # المراقبة المستمرة / Continuous Monitoring
    # ----------------------------------------------------------------

    def monitor_sentiment_changes(self, symbol, check_interval_minutes=60):
        """
        مراقبة تغيرات المشاعر — اكتشاف التحولات المفاجئة
        Monitor sentiment changes — detect sudden shifts
        """
        current = self.analyze_news_for_symbol(symbol, hours=24)
        previous = self.sentiment_cache.get(symbol)

        if not previous:
            return {"change": 0, "trend": "STABLE"}

        sentiment_change = current["sentiment"] - previous["sentiment"]
        article_change = current["article_count"] - previous["article_count"]

        if abs(sentiment_change) > 0.3:
            if sentiment_change > 0:
                trend = "IMPROVING"
            else:
                trend = "DETERIORATING"
        else:
            trend = "STABLE"

        # إذا كان هناك ارتفاع مفاجئ في عدد الأخبار السلبية
        if article_change > 5 and current["negative_count"] > current["positive_count"]:
            alert = "⚠️ تحذير: ارتفاع مفاجئ في الأخبار السلبية!"
        else:
            alert = None

        return {
            "change": sentiment_change,
            "trend": trend,
            "article_change": article_change,
            "alert": alert,
        }

    # ----------------------------------------------------------------
    # مساعد / Helper
    # ----------------------------------------------------------------

    def _get_coin_name(self, symbol):
        """تحويل الرمز إلى اسم العملة"""
        mapping = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'BNB': 'Binance Coin',
            'SOL': 'Solana',
            'XRP': 'Ripple',
            'ADA': 'Cardano',
            'DOGE': 'Dogecoin',
            'PEPE': 'Pepe',
            'SHIB': 'Shiba Inu',
            'LINK': 'Chainlink',
            'AVAX': 'Avalanche',
            'MATIC': 'Polygon',
            'OP': 'Optimism',
            'ARB': 'Arbitrum',
        }
        return mapping.get(symbol.replace('/USDT', ''), symbol)
