# 🚀 Trade Lak Bot v4 - Advanced AI Trading Bot

**بوت Trade لك v4 - بوت تداول ذكي متقدم مع التعلم الآلي**

---

## ✨ الميزات الرئيسية

### 🤖 Machine Learning
- نماذج Random Forest و Gradient Boosting
- تعلم مستمر من كل صفقة
- استخراج ميزات متقدم من بيانات السوق
- دقة تنبؤ عالية

### 📊 5 استراتيجيات متوازية
1. **Momentum Strategy** - متابعة الزخم والاتجاهات
2. **Mean Reversion Strategy** - الشراء عند الانخفاض الزائد
3. **Breakout Strategy** - الاختراقات والمستويات الرئيسية
4. **Volume Profile Strategy** - التداول عند مستويات الحجم العالي
5. **ML-Based Strategy** - إشارات مبنية على الذكاء الاصطناعي

### 🛡️ نظام إدارة مخاطر فائق
- **Circuit Breaker** - 4 مستويات حماية
- **Correlation Filter** - منع المراكز المترابطة
- **Position Sizer** - حساب حجم المركز الأمثل
- **Kelly Criterion** - إدارة رأس المال الذكية

### 🐋 تتبع الحيتان والمحافظ الكبيرة
- مراقبة تحركات المحافظ الكبيرة On-Chain
- كشف عمليات التحويل الكبيرة

### 📖 تحليل دفتر الأوامر
- كشف تحركات البوتات الكبيرة
- تحليل عمق دفتر الأوامر

### 💎 بيانات CoinGlass
- معدلات التمويل
- نسب Long/Short
- ضغط التصفيات

### 📢 تنبيهات تليجرام الفورية
- إخطارات عند فتح/إغلاق صفقة
- إحصائيات يومية وأسبوعية
- تنبيهات الأخطاء والتحذيرات

### 🎯 Spot + Futures
- تداول في سوق Spot
- تداول في سوق Futures
- Long و Short positions

---

## 📋 المتطلبات

- Python 3.8+
- pip (مدير الحزم)

---

## 🔧 التثبيت والإعداد

### 1. تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 2. إعداد الإعدادات
عدّل `config/config.py`:

```python
# OKX API Credentials
OKX_API_KEY      = "your_api_key"
OKX_SECRET_KEY   = "your_secret_key"
OKX_PASSPHRASE   = "your_passphrase"

# Telegram
TELEGRAM_ENABLED    = True
TELEGRAM_BOT_TOKEN  = "your_bot_token"
TELEGRAM_CHAT_ID    = "your_chat_id"

# رأس المال
TOTAL_CAPITAL        = 300
SPOT_CAPITAL_PCT     = 0.65
FUTURES_CAPITAL_PCT  = 0.35

# الوضع
DRY_RUN = True   # True = اختبار | False = تداول حقيقي
```

### 3. تشغيل البوت
```bash
python main.py
```

---

## 📊 البنية المعمارية

```
trade_lak_bot/
├── config/config.py              # الإعدادات
├── core/
│   ├── okx_client.py             # عميل OKX
│   ├── coinglass_client.py       # عميل CoinGlass
│   ├── intelligence_engine.py    # محرك الذكاء
│   ├── ml_model.py               # نموذج ML
│   ├── multi_strategy.py         # الاستراتيجيات
│   ├── advanced_risk_manager.py  # إدارة المخاطر
│   └── ...
├── utils/
│   ├── notifier.py               # إخطارات
│   └── telegram_notifier.py      # تليجرام
├── models/                       # نماذج ML
├── logs/                         # السجلات
├── main.py                       # الملف الرئيسي
└── requirements.txt              # المكتبات
```

---

## 🚀 كيفية العمل

```
1. فحص السوق الكامل (كل 60 ثانية)
2. تطبيق 5 استراتيجيات متوازية
3. دمج النتائج مع ML
4. اتخاذ القرار النهائي
5. فتح صفقة (إن وجدت إشارة قوية)
6. مراقبة الصفقات المفتوحة
7. إغلاق الصفقات عند الشروط
8. تسجيل الصفقة وتدريب ML
9. إرسال تنبيهات تليجرام
```

---

## 🔒 الأمان

1. **لا تشارك API Keys مع أحد**
2. **استخدم اختبار (Dry Run) أولاً**
3. **ابدأ برأس مال صغير**
4. **راقب البوت بانتظام**

---

## ⚠️ تحذير مهم

**التداول بالعملات الرقمية ينطوي على مخاطر عالية!**

- قد تفقد كل رأس مالك
- استخدم البوت على مسؤوليتك الخاصة
- ابدأ برأس مال صغير

---

**الإصدار:** v4.0.0
