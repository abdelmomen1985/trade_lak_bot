"""
AI Chatbot Module for Trade Lak Bot
Provides intelligent conversation and analysis capabilities
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re


class AIChattbot:
    """Intelligent chatbot for trading bot interaction"""
    
    def __init__(self, bot_stats: Dict = None):
        """
        Initialize the chatbot
        
        Args:
            bot_stats: Dictionary containing bot statistics
        """
        self.bot_stats = bot_stats or {}
        self.conversation_history = []
        self.knowledge_base = self._init_knowledge_base()
        
    def _init_knowledge_base(self) -> Dict:
        """Initialize knowledge base with trading information"""
        return {
            "strategies": {
                "momentum": "استراتيجية الزخم - تتابع الأسعار الصاعدة",
                "mean_reversion": "استراتيجية العودة للمتوسط - تتوقع عودة الأسعار",
                "breakout": "استراتيجية الاختراق - تفتح صفقات عند كسر المستويات",
                "volume_profile": "استراتيجية ملف الحجم - تحلل توزيع الحجم",
                "ml_based": "استراتيجية الذكاء الاصطناعي - تتعلم من البيانات"
            },
            "risk_management": {
                "circuit_breaker": "قاطع الدائرة - يوقف التداول عند الخسائر الكبيرة",
                "stop_loss": "إيقاف الخسائر - يحد من الخسائر في كل صفقة",
                "position_sizing": "حجم المركز - يحسب الحجم الآمن للصفقة",
                "correlation_filter": "مرشح الارتباط - يتجنب الصفقات المترابطة"
            },
            "market_analysis": {
                "whale_tracking": "تتبع الحيتان - مراقبة تحركات المحافظ الكبيرة",
                "funding_rate": "معدل التمويل - يشير إلى اتجاه السوق",
                "liquidation": "التصفيات - مستويات قد تسبب انهيار السعر",
                "orderbook": "دفتر الأوامر - يكشف الضغط على السعر"
            }
        }
    
    def process_query(self, user_input: str) -> str:
        """
        Process user query and return intelligent response
        
        Args:
            user_input: User's question or command
            
        Returns:
            Response from the chatbot
        """
        # Add to conversation history
        self.conversation_history.append({
            "user": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # Normalize input
        query = user_input.lower().strip()
        
        # Detect query type
        response = self._detect_and_respond(query)
        
        # Add response to history
        self.conversation_history.append({
            "bot": response,
            "timestamp": datetime.now().isoformat()
        })
        
        return response
    
    def _detect_and_respond(self, query: str) -> str:
        """Detect query type and generate appropriate response"""
        
        # Statistics queries
        if any(word in query for word in ["كم", "اليوم", "الأرباح", "الخسائر", "الصفقات"]):
            return self._handle_statistics_query(query)
        
        # Strategy queries
        if any(word in query for word in ["استراتيجية", "strategy", "كيف", "كيفية"]):
            return self._handle_strategy_query(query)
        
        # Risk management queries
        if any(word in query for word in ["مخاطر", "خسارة", "حماية", "آمان"]):
            return self._handle_risk_query(query)
        
        # Market analysis queries
        if any(word in query for word in ["حيتان", "سوق", "تحليل", "فرصة"]):
            return self._handle_market_query(query)
        
        # Bot status queries
        if any(word in query for word in ["حالة", "status", "يعمل", "تشغيل"]):
            return self._handle_status_query(query)
        
        # Performance queries
        if any(word in query for word in ["أداء", "نتائج", "أرباح", "نسبة"]):
            return self._handle_performance_query(query)
        
        # Default response
        return self._handle_general_query(query)
    
    def _handle_statistics_query(self, query: str) -> str:
        """Handle statistics-related queries"""
        
        if "اليوم" in query or "today" in query:
            return f"""
📊 **إحصائيات اليوم:**

💰 إجمالي الأرباح: ${self.bot_stats.get('daily_profit', 0):.2f}
📈 عدد الصفقات: {self.bot_stats.get('total_trades', 0)}
✅ الصفقات الرابحة: {self.bot_stats.get('winning_trades', 0)}
❌ الصفقات الخاسرة: {self.bot_stats.get('losing_trades', 0)}
📊 نسبة النجاح: {self.bot_stats.get('win_rate', 0):.1f}%

🎯 أفضل صفقة: ${self.bot_stats.get('best_trade', 0):.2f}
📉 أسوأ صفقة: ${self.bot_stats.get('worst_trade', 0):.2f}
"""
        
        if "الأسبوع" in query or "week" in query:
            return f"""
📊 **إحصائيات الأسبوع:**

💰 إجمالي الأرباح: ${self.bot_stats.get('weekly_profit', 0):.2f}
📈 عدد الصفقات: {self.bot_stats.get('weekly_trades', 0)}
📊 متوسط الربح: ${self.bot_stats.get('avg_profit', 0):.2f}
📈 أعلى يوم: ${self.bot_stats.get('best_day', 0):.2f}
"""
        
        return """
📊 **الإحصائيات:**

اسأل عن:
- إحصائيات اليوم
- إحصائيات الأسبوع
- عدد الصفقات
- نسبة النجاح
"""
    
    def _handle_strategy_query(self, query: str) -> str:
        """Handle strategy-related queries"""
        
        strategies_info = """
🎯 **الاستراتيجيات المتاحة:**

1️⃣ **استراتيجية الزخم (Momentum)**
   - تتابع الأسعار الصاعدة
   - تفتح صفقات عند الارتفاع
   - مناسبة للأسواق القوية

2️⃣ **استراتيجية العودة للمتوسط (Mean Reversion)**
   - تتوقع عودة الأسعار للمتوسط
   - تفتح صفقات عند الانخفاض الشديد
   - مناسبة للأسواق المتذبذبة

3️⃣ **استراتيجية الاختراق (Breakout)**
   - تفتح صفقات عند كسر المستويات
   - تستفيد من التحركات الكبيرة
   - مناسبة للأسواق المتقلبة

4️⃣ **استراتيجية ملف الحجم (Volume Profile)**
   - تحلل توزيع الحجم
   - تجد مستويات الدعم والمقاومة
   - مناسبة للتحليل العميق

5️⃣ **استراتيجية الذكاء الاصطناعي (ML-Based)**
   - تتعلم من البيانات التاريخية
   - تتحسن مع الوقت
   - مناسبة لجميع الأسواق
"""
        return strategies_info
    
    def _handle_risk_query(self, query: str) -> str:
        """Handle risk management queries"""
        
        return """
🛡️ **إدارة المخاطر:**

1️⃣ **قاطع الدائرة (Circuit Breaker)**
   - يوقف التداول عند خسائر كبيرة
   - 4 مستويات حماية
   - يحمي رأس المال

2️⃣ **إيقاف الخسائر (Stop Loss)**
   - يحد من الخسائر في كل صفقة
   - متحرك ديناميكي
   - يتكيف مع السوق

3️⃣ **حجم المركز (Position Sizing)**
   - يحسب الحجم الآمن
   - بناءً على رأس المال
   - بناءً على المخاطرة المقبولة

4️⃣ **مرشح الارتباط (Correlation Filter)**
   - يتجنب الصفقات المترابطة
   - يقلل المخاطر المنهجية
   - يحسن التنويع

✅ كل هذه الحماية مفعلة الآن!
"""
    
    def _handle_market_query(self, query: str) -> str:
        """Handle market analysis queries"""
        
        return """
📊 **تحليل السوق:**

🐋 **تتبع الحيتان:**
   - مراقبة تحركات المحافظ الكبيرة
   - اكتشاف الضغط على السوق
   - فرص قبل الحركات الكبيرة

💰 **معدل التمويل (Funding Rate):**
   - يشير إلى اتجاه السوق
   - معدل إيجابي = ضغط شراء
   - معدل سالب = ضغط بيع

📉 **التصفيات (Liquidations):**
   - مستويات قد تسبب انهيار السعر
   - فرص دخول جيدة
   - مؤشر قوة السوق

📋 **دفتر الأوامر (Orderbook):**
   - يكشف الضغط على السعر
   - يحدد مستويات المقاومة
   - يساعد في التنبؤ بالحركات
"""
    
    def _handle_status_query(self, query: str) -> str:
        """Handle bot status queries"""
        
        status = self.bot_stats.get('status', 'running')
        uptime = self.bot_stats.get('uptime', 0)
        
        return f"""
🤖 **حالة البوت:**

✅ الحالة: {status.upper()}
⏱️ وقت التشغيل: {uptime} ساعة
💰 رأس المال الحالي: ${self.bot_stats.get('current_capital', 0):.2f}
📊 عدد الصفقات المفتوحة: {self.bot_stats.get('open_trades', 0)}
🔔 التنبيهات: مفعلة على تليجرام

✅ كل الأنظمة تعمل بشكل طبيعي!
"""
    
    def _handle_performance_query(self, query: str) -> str:
        """Handle performance-related queries"""
        
        roi = self.bot_stats.get('roi', 0)
        monthly_profit = self.bot_stats.get('monthly_profit', 0)
        
        return f"""
📈 **الأداء:**

💹 العائد على الاستثمار (ROI): {roi:.2f}%
💰 الأرباح الشهرية: ${monthly_profit:.2f}
📊 متوسط الربح لكل صفقة: ${self.bot_stats.get('avg_profit_per_trade', 0):.2f}
⏱️ متوسط مدة الصفقة: {self.bot_stats.get('avg_trade_duration', 0)} دقيقة

🎯 الأداء ممتاز! استمر في المراقبة.
"""
    
    def _handle_general_query(self, query: str) -> str:
        """Handle general queries"""
        
        return """
👋 **مرحباً! أنا بوت التداول الذكي**

يمكنك أن تسأل عن:
- 📊 الإحصائيات (اليوم، الأسبوع، الشهر)
- 🎯 الاستراتيجيات وكيفية عملها
- 🛡️ إدارة المخاطر والحماية
- 📈 تحليل السوق والحيتان
- 🤖 حالة البوت والأداء
- 💡 النصائح والتوصيات

اسأل أي سؤال! 💙
"""
    
    def get_recommendation(self) -> str:
        """Get AI recommendation based on current data"""
        
        current_profit = self.bot_stats.get('daily_profit', 0)
        win_rate = self.bot_stats.get('win_rate', 0)
        open_trades = self.bot_stats.get('open_trades', 0)
        
        recommendations = []
        
        if current_profit > 0:
            recommendations.append("✅ الأداء جيد اليوم! استمر في المراقبة.")
        
        if win_rate > 60:
            recommendations.append("🎯 نسبة النجاح عالية جداً! البوت يعمل بكفاءة.")
        
        if open_trades > 5:
            recommendations.append("⚠️ عدد الصفقات المفتوحة كثير. قد تحتاج للانتظار.")
        
        if not recommendations:
            recommendations.append("📊 الأداء طبيعي. استمر في المراقبة.")
        
        return "\n".join(recommendations)
    
    def get_conversation_summary(self) -> str:
        """Get summary of conversation history"""
        
        if not self.conversation_history:
            return "لا توجد محادثات سابقة."
        
        summary = f"📝 **ملخص المحادثة:**\n\n"
        summary += f"عدد الأسئلة: {len([h for h in self.conversation_history if 'user' in h])}\n"
        summary += f"عدد الإجابات: {len([h for h in self.conversation_history if 'bot' in h])}\n"
        
        return summary


# Example usage
if __name__ == "__main__":
    # Initialize chatbot with sample stats
    sample_stats = {
        "daily_profit": 45.50,
        "total_trades": 12,
        "winning_trades": 8,
        "losing_trades": 4,
        "win_rate": 66.7,
        "best_trade": 25.00,
        "worst_trade": -5.00,
        "current_capital": 2450.00,
        "open_trades": 2,
        "status": "running",
        "uptime": 24,
        "roi": 8.5,
        "monthly_profit": 450.00,
        "avg_profit_per_trade": 3.79,
        "avg_trade_duration": 45
    }
    
    chatbot = AIChattbot(sample_stats)
    
    # Test queries
    test_queries = [
        "كم ربحنا اليوم؟",
        "اشرح لي الاستراتيجيات",
        "كيف يتم حماية الأموال؟",
        "ما حالة البوت؟"
    ]
    
    for query in test_queries:
        print(f"\n👤 المستخدم: {query}")
        response = chatbot.process_query(query)
        print(f"🤖 البوت: {response}")
