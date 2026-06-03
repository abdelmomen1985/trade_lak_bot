"""
Fear & Greed Index Engine
يجلب مؤشر الخوف والجشع ويدمجه في تحليل السوق
"""
import requests
import json
from datetime import datetime


class FearGreedEngine:
    """محرك مؤشر الخوف والجشع للعملات الرقمية"""
    
    API_URL = "https://api.alternative.me/fng/"
    
    def __init__(self):
        self.cache = None
        self.cache_time = None
        self.cache_duration = 3600  # ساعة واحدة
    
    def get_current_index(self):
        """جلب مؤشر الخوف والجشع الحالي"""
        try:
            # فحص الكاش
            if self.cache and self.cache_time:
                elapsed = (datetime.now() - self.cache_time).seconds
                if elapsed < self.cache_duration:
                    return self.cache
            
            response = requests.get(
                self.API_URL,
                params={"limit": 1, "format": "json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    item = data["data"][0]
                    result = {
                        "value": int(item["value"]),
                        "classification": item["value_classification"],
                        "timestamp": item["timestamp"],
                        "signal": self._get_trading_signal(int(item["value"])),
                        "description": self._get_description(int(item["value"]))
                    }
                    self.cache = result
                    self.cache_time = datetime.now()
                    return result
        except Exception as e:
            print(f"[FearGreed] Error: {e}")
        
        # قيمة افتراضية عند الفشل
        return {
            "value": 50,
            "classification": "Neutral",
            "signal": "NEUTRAL",
            "description": "لا يمكن جلب المؤشر حالياً"
        }
    
    def get_historical(self, days=30):
        """جلب بيانات تاريخية للمؤشر"""
        try:
            response = requests.get(
                self.API_URL,
                params={"limit": days, "format": "json"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            print(f"[FearGreed] Historical Error: {e}")
        return []
    
    def _get_trading_signal(self, value):
        """تحويل القيمة إلى إشارة تداول"""
        if value <= 20:
            return "EXTREME_FEAR_BUY"  # خوف شديد = فرصة شراء ممتازة
        elif value <= 35:
            return "FEAR_BUY"          # خوف = فرصة شراء
        elif value <= 55:
            return "NEUTRAL"           # محايد = انتظار
        elif value <= 75:
            return "GREED_CAUTION"     # جشع = حذر من الشراء
        else:
            return "EXTREME_GREED_SELL"  # جشع شديد = وقت البيع
    
    def _get_description(self, value):
        """وصف تفصيلي للمؤشر بالعربية"""
        if value <= 20:
            return f"⚠️ خوف شديد جداً ({value}) - السوق في ذعر! هذه فرصة شراء تاريخية. الحيتان تتراكم."
        elif value <= 35:
            return f"😨 خوف ({value}) - السوق خائف. فرصة شراء جيدة مع إدارة مخاطر."
        elif value <= 55:
            return f"😐 محايد ({value}) - السوق متوازن. انتظر إشارات أقوى."
        elif value <= 75:
            return f"😏 جشع ({value}) - السوق متفائل. كن حذراً من الدخول الجديد."
        else:
            return f"🚨 جشع شديد ({value}) - السوق في فقاعة! خطر انهيار قريب."
    
    def get_market_bias(self):
        """الحصول على التحيز العام للسوق"""
        data = self.get_current_index()
        value = data["value"]
        
        if value <= 25:
            return {"bias": "STRONGLY_BULLISH", "weight": 0.9, "reason": "خوف شديد = فرصة شراء"}
        elif value <= 40:
            return {"bias": "BULLISH", "weight": 0.7, "reason": "خوف = ميل للشراء"}
        elif value <= 60:
            return {"bias": "NEUTRAL", "weight": 0.5, "reason": "محايد"}
        elif value <= 75:
            return {"bias": "BEARISH", "weight": 0.3, "reason": "جشع = تجنب الشراء"}
        else:
            return {"bias": "STRONGLY_BEARISH", "weight": 0.1, "reason": "جشع شديد = خطر انهيار"}
    
    def calculate_success_boost(self, trade_direction):
        """حساب تأثير المؤشر على نسبة النجاح"""
        data = self.get_current_index()
        value = data["value"]
        
        boost = 0
        
        if trade_direction == "LONG":
            if value <= 20:
                boost = +15  # خوف شديد = دعم قوي للشراء
            elif value <= 35:
                boost = +8
            elif value <= 55:
                boost = 0
            elif value <= 75:
                boost = -5
            else:
                boost = -15  # جشع شديد = خطر للشراء
        
        elif trade_direction == "SHORT":
            if value >= 80:
                boost = +15  # جشع شديد = دعم قوي للبيع
            elif value >= 65:
                boost = +8
            elif value >= 45:
                boost = 0
            elif value >= 30:
                boost = -5
            else:
                boost = -15  # خوف شديد = خطر للبيع
        
        return boost
    
    def format_for_telegram(self):
        """تنسيق المؤشر لرسالة Telegram"""
        data = self.get_current_index()
        value = data["value"]
        
        # اختيار الإيموجي المناسب
        if value <= 20:
            emoji = "🔴🔴"
        elif value <= 35:
            emoji = "🔴"
        elif value <= 55:
            emoji = "🟡"
        elif value <= 75:
            emoji = "🟢"
        else:
            emoji = "🟢🟢"
        
        return (
            f"{emoji} **مؤشر الخوف والجشع:** {value}/100\n"
            f"   📊 التصنيف: {data['classification']}\n"
            f"   💡 {data['description']}"
        )


# اختبار سريع
if __name__ == "__main__":
    engine = FearGreedEngine()
    data = engine.get_current_index()
    print(f"Fear & Greed Index: {data['value']} - {data['classification']}")
    print(f"Signal: {data['signal']}")
    print(f"Description: {data['description']}")
    print(f"\nTelegram format:\n{engine.format_for_telegram()}")
