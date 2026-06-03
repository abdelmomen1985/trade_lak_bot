"""
FinBERT Sentiment Analyzer
نموذج AI متخصص في تحليل المشاعر المالية
يستخدم ProsusAI/finbert من HuggingFace
"""
import json
import re
import requests
from datetime import datetime


class FinBERTAnalyzer:
    """
    محلل المشاعر المالية باستخدام FinBERT
    يدعم وضعين:
    1. Local: تحميل النموذج محلياً (يحتاج torch + transformers)
    2. API: استخدام HuggingFace Inference API (مجاني)
    """
    
    # HuggingFace Inference API (مجاني بدون تحميل النموذج)
    HF_API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
    
    def __init__(self, use_local=False, hf_token=None):
        self.use_local = use_local
        self.hf_token = hf_token
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        
        if use_local:
            self._load_local_model()
    
    def _load_local_model(self):
        """تحميل النموذج محلياً"""
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            print("[FinBERT] Loading model locally...")
            model_name = "ProsusAI/finbert"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.pipeline = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                return_all_scores=True
            )
            print("[FinBERT] ✅ Model loaded successfully!")
            
        except ImportError:
            print("[FinBERT] ⚠️ torch/transformers not installed. Using API mode.")
            self.use_local = False
        except Exception as e:
            print(f"[FinBERT] Error loading model: {e}. Using API mode.")
            self.use_local = False
    
    def analyze_text(self, text):
        """تحليل نص واحد"""
        if not text or len(text.strip()) < 5:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "label": "neutral", "score": 0.34}
        
        # تنظيف النص
        text = self._clean_text(text)
        
        if self.use_local and self.pipeline:
            return self._analyze_local(text)
        else:
            return self._analyze_api(text)
    
    def _analyze_local(self, text):
        """تحليل باستخدام النموذج المحلي"""
        try:
            # تقليص النص إذا كان طويلاً
            if len(text) > 512:
                text = text[:512]
            
            results = self.pipeline(text)[0]
            scores = {r["label"].lower(): r["score"] for r in results}
            
            # تحديد التصنيف الأقوى
            label = max(scores, key=scores.get)
            
            return {
                "positive": scores.get("positive", 0),
                "negative": scores.get("negative", 0),
                "neutral": scores.get("neutral", 0),
                "label": label,
                "score": scores[label]
            }
        except Exception as e:
            print(f"[FinBERT Local] Error: {e}")
            return self._fallback_analysis(text)
    
    def _analyze_api(self, text):
        """تحليل عبر HuggingFace API"""
        try:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            # تقليص النص
            if len(text) > 400:
                text = text[:400]
            
            response = requests.post(
                self.HF_API_URL,
                headers=headers,
                json={"inputs": text},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    results = data[0] if isinstance(data[0], list) else data
                    scores = {}
                    for item in results:
                        if isinstance(item, dict):
                            label = item.get("label", "").lower()
                            score = item.get("score", 0)
                            scores[label] = score
                    
                    if scores:
                        label = max(scores, key=scores.get)
                        return {
                            "positive": scores.get("positive", 0),
                            "negative": scores.get("negative", 0),
                            "neutral": scores.get("neutral", 0),
                            "label": label,
                            "score": scores[label]
                        }
            
            # إذا فشل API، استخدم التحليل البديل
            return self._fallback_analysis(text)
            
        except Exception as e:
            print(f"[FinBERT API] Error: {e}")
            return self._fallback_analysis(text)
    
    def _fallback_analysis(self, text):
        """تحليل بديل باستخدام كلمات مفتاحية عند فشل النموذج"""
        text_lower = text.lower()
        
        # كلمات إيجابية مالية
        positive_words = [
            "bullish", "surge", "rally", "pump", "moon", "breakout", "support",
            "buy", "long", "profit", "gain", "rise", "up", "growth", "adoption",
            "partnership", "launch", "upgrade", "milestone", "record", "high",
            "institutional", "etf", "approval", "positive", "strong", "good",
            "صعود", "ارتفاع", "شراء", "ربح", "قوي", "إيجابي", "نمو"
        ]
        
        # كلمات سلبية مالية
        negative_words = [
            "bearish", "crash", "dump", "sell", "short", "loss", "fall", "down",
            "hack", "scam", "fraud", "ban", "regulation", "fear", "panic",
            "liquidation", "bankruptcy", "warning", "risk", "danger", "weak",
            "هبوط", "انخفاض", "بيع", "خسارة", "ضعيف", "سلبي", "خطر"
        ]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count
        
        if total == 0:
            return {"positive": 0.2, "negative": 0.2, "neutral": 0.6, "label": "neutral", "score": 0.6}
        
        pos_score = pos_count / total
        neg_score = neg_count / total
        neu_score = max(0, 1 - pos_score - neg_score)
        
        if pos_score > neg_score and pos_score > 0.5:
            label = "positive"
            score = pos_score
        elif neg_score > pos_score and neg_score > 0.5:
            label = "negative"
            score = neg_score
        else:
            label = "neutral"
            score = neu_score
        
        return {
            "positive": pos_score,
            "negative": neg_score,
            "neutral": neu_score,
            "label": label,
            "score": score
        }
    
    def analyze_news_batch(self, news_list):
        """تحليل مجموعة أخبار ودمج النتائج"""
        if not news_list:
            return {"overall_sentiment": "neutral", "score": 0.5, "details": []}
        
        results = []
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        
        for news in news_list[:10]:  # تحليل أول 10 أخبار فقط
            title = news.get("title", "") if isinstance(news, dict) else str(news)
            analysis = self.analyze_text(title)
            
            results.append({
                "title": title[:100],
                "sentiment": analysis["label"],
                "score": analysis["score"],
                "positive": analysis["positive"],
                "negative": analysis["negative"]
            })
            
            total_positive += analysis["positive"]
            total_negative += analysis["negative"]
            total_neutral += analysis["neutral"]
        
        count = len(results)
        avg_positive = total_positive / count
        avg_negative = total_negative / count
        avg_neutral = total_neutral / count
        
        # تحديد المشاعر الإجمالية
        if avg_positive > avg_negative and avg_positive > avg_neutral:
            overall = "positive"
            overall_score = avg_positive
        elif avg_negative > avg_positive and avg_negative > avg_neutral:
            overall = "negative"
            overall_score = avg_negative
        else:
            overall = "neutral"
            overall_score = avg_neutral
        
        return {
            "overall_sentiment": overall,
            "score": overall_score,
            "avg_positive": avg_positive,
            "avg_negative": avg_negative,
            "avg_neutral": avg_neutral,
            "news_count": count,
            "details": results
        }
    
    def get_sentiment_boost(self, sentiment_data, trade_direction):
        """حساب تأثير المشاعر على نسبة النجاح"""
        overall = sentiment_data.get("overall_sentiment", "neutral")
        score = sentiment_data.get("score", 0.5)
        
        boost = 0
        
        if trade_direction == "LONG":
            if overall == "positive":
                boost = int(score * 20)  # حتى +20%
            elif overall == "negative":
                boost = -int(score * 15)  # حتى -15%
        
        elif trade_direction == "SHORT":
            if overall == "negative":
                boost = int(score * 20)
            elif overall == "positive":
                boost = -int(score * 15)
        
        return boost
    
    def _clean_text(self, text):
        """تنظيف النص من الرموز غير الضرورية"""
        # إزالة URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        # إزالة رموز خاصة
        text = re.sub(r'[^\w\s\.\,\!\?\-]', ' ', text)
        # تقليص المسافات
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def format_for_telegram(self, sentiment_data):
        """تنسيق نتائج التحليل لرسالة Telegram"""
        overall = sentiment_data.get("overall_sentiment", "neutral")
        score = sentiment_data.get("score", 0.5)
        count = sentiment_data.get("news_count", 0)
        
        if overall == "positive":
            emoji = "🟢"
            label = "إيجابي"
        elif overall == "negative":
            emoji = "🔴"
            label = "سلبي"
        else:
            emoji = "🟡"
            label = "محايد"
        
        return (
            f"{emoji} **تحليل FinBERT للأخبار:** {label} ({score:.0%})\n"
            f"   📰 تحليل {count} خبر بالذكاء الاصطناعي\n"
            f"   📈 إيجابي: {sentiment_data.get('avg_positive', 0):.0%} | "
            f"📉 سلبي: {sentiment_data.get('avg_negative', 0):.0%}"
        )


# اختبار سريع
if __name__ == "__main__":
    analyzer = FinBERTAnalyzer(use_local=False)
    
    test_texts = [
        "Bitcoin surges to new all-time high as institutional adoption grows",
        "Crypto market crashes 30% amid regulatory crackdown",
        "Ethereum upgrade scheduled for next month"
    ]
    
    print("=== FinBERT Analysis Test ===\n")
    for text in test_texts:
        result = analyzer.analyze_text(text)
        print(f"Text: {text[:60]}...")
        print(f"Sentiment: {result['label']} ({result['score']:.2%})")
        print()
