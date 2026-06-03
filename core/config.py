# ============================================================
# Trade Lak Bot - Configuration File (Spot + Futures)
# تطبيق Trade لك - ملف الإعدادات (سبوت + فيوتشر)
# ============================================================
# ⚠️  أدخل بياناتك هنا بعد إنشاء API Keys من OKX
# ============================================================

# --- OKX API Credentials ---
OKX_API_KEY      = "35c12b6c-deda-4d0e-8f4c-d0e4ca8a608d"
OKX_SECRET_KEY   = "4495EDF88675CEE07291C4E4E5583F43"
OKX_PASSPHRASE   = "Lrtm@01102200"

# --- CoinGlass API ---
COINGLASS_API_KEY = "eaf8efd7876142b0bac70affb6f65f2a"

# --- Capital Allocation / تقسيم رأس المال ---
TOTAL_CAPITAL        = 300      # رأس المال الكلي بالدولار
SPOT_CAPITAL_PCT     = 0.65     # 65% للـ Spot  = $195
FUTURES_CAPITAL_PCT  = 0.35     # 35% للـ Futures = $105

# --- Risk Management / إدارة المخاطر ---
SPOT_RISK_PER_TRADE     = 0.03  # 3% مخاطرة لكل صفقة Spot
FUTURES_RISK_PER_TRADE  = 0.02  # 2% مخاطرة لكل صفقة Futures (أقل لأن الرافعة تضاعف)
FUTURES_LEVERAGE        = 3     # رافعة مالية 3x فقط (آمنة)
MIN_TRADE_AMOUNT        = 10    # الحد الأدنى لأي صفقة بالدولار

# --- Stop Loss / Take Profit ---
# البوت يحسبها تلقائياً بناءً على التحليل الفني
# لكن هذه هي الحدود القصوى المسموح بها
MAX_STOP_LOSS_PCT   = 0.05      # الحد الأقصى لوقف الخسارة 5%
MIN_TAKE_PROFIT_RR  = 1.5       # الحد الأدنى لنسبة المخاطرة/المكافأة (1:1.5)
TRAILING_STOP       = True      # تفعيل Stop Loss متحرك
TRAILING_STOP_PCT   = 0.015     # نسبة الـ Trailing Stop

# --- Open Trades Limits / حدود الصفقات المفتوحة ---
MAX_SPOT_TRADES     = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح
MAX_FUTURES_TRADES  = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح

# --- Market Scanner Settings / إعدادات فحص السوق ---
# البوت يفحص كامل السوق تلقائياً ولا يحتاج قائمة يدوية
SCAN_TOP_N_COINS        = 100   # فحص أفضل 100 عملة من حيث حجم التداول
MIN_VOLUME_24H_USD      = 5_000_000   # الحد الأدنى لحجم التداول اليومي ($5M)
MIN_PRICE_CHANGE_SIGNAL = 2.0   # الحد الأدنى لتغير السعر % لاعتباره إشارة

# --- Signal Scoring Thresholds / عتبات نقاط الإشارة ---
MIN_SCORE_FOR_SPOT      = 3     # الحد الأدنى للنقاط للدخول في Spot
MIN_SCORE_FOR_FUTURES   = 5     # الحد الأدنى للنقاط للدخول في Futures (أعلى لأنه أخطر)
MIN_SCORE_FOR_SHORT     = 4     # الحد الأدنى للنقاط للدخول في Futures Short

# --- CoinGlass Thresholds ---
FUNDING_RATE_LONG_THRESHOLD  = -0.001   # معدل تمويل سلبي = فرصة Long
FUNDING_RATE_SHORT_THRESHOLD =  0.003   # معدل تمويل مرتفع جداً = فرصة Short
LONG_SHORT_SHORT_DOMINANCE   =  0.65    # 65% يبيعون = فرصة صعود
LONG_SHORT_LONG_DOMINANCE    =  0.70    # 70% يشترون = فرصة هبوط
MIN_LIQUIDATION_VOLUME       = 100_000  # الحد الأدنى لحجم التصفيات بالدولار
FUNDING_RATE_THRESHOLD       = 0.001    # عتبة معدل التمويل

# --- Technical Analysis ---
RSI_OVERSOLD    = 35    # RSI أقل من 35 = مبالغة في البيع = فرصة شراء
RSI_OVERBOUGHT  = 70    # RSI أعلى من 70 = مبالغة في الشراء = فرصة بيع

# --- Telegram Notifications (Optional) ---
TELEGRAM_ENABLED    = True
TELEGRAM_BOT_TOKEN  = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
TELEGRAM_CHAT_ID    = "-1003942444248"  # سيتم الحصول عليه تلقائياً عند أول رسالة

# --- AI Chatbot Configuration ---
CHATBOT_ENABLED      = True
CHATBOT_LANGUAGE     = 'ar'  # Arabic / العربية
CHATBOT_RESPONSE_TIME = 1    # seconds
CHATBOT_MEMORY_SIZE  = 100   # conversation history size

# --- General Settings ---
LOG_LEVEL        = "INFO"
CHECK_INTERVAL   = 60       # فحص السوق كل 60 ثانية
DRY_RUN          = True     # True = اختبار | False = تداول حقيقي (سنغيره لـ False بعد الاختبار)
