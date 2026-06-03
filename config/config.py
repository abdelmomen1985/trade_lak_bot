# ============================================================
# Trade Lak Bot - Configuration File (Spot + Futures)
# تطبيق Trade لك - ملف الإعدادات (سبوت + فيوتشر)
# ============================================================
# ⚠️  أدخل بياناتك هنا بعد إنشاء API Keys من OKX
# ============================================================

# --- OKX API Credentials ---
OKX_API_KEY      = "f81a3505-1ed6-4cf6-84b8-4f5de25487a8"
OKX_SECRET_KEY   = "03899CE28C92CC62C03826E2C8B4D72B"
OKX_PASSPHRASE   = "Ll@12%553"

# --- CoinGlass API ---
COINGLASS_API_KEY = "eaf8efd7876142b0bac70affb6f65f2a"
# --- CryptoPanic News API ---
CRYPTOPANIC_API_KEY = "afed90b669cebc6535f88540ecb1679ee551facc"
CRYPTOPANIC_PLAN    = "growth"
# --- BscScan / EtherScan On-Chain (optional) ---
BSCSCAN_API_KEY  = "W994R5JJQQVGX1ZI8KD8ZIFAFZ52RSUMMC"
ETHERSCAN_API_KEY = "W994R5JJQQVGX1ZI8KD8ZIFAFZ52RSUMMC"

# --- Capital Allocation / تقسيم رأس المال ---
TOTAL_CAPITAL        = 1312.69  # يُحدَّث تلقائياً — القيمة الفعلية من OKX
DAILY_CAPITAL_LIMIT  = 170.0   # الحد الأقصى للرأس المال المستخدم خلال 24 ساعة
SPOT_CAPITAL_PCT     = 0.85     # 85% للـ Spot
FUTURES_CAPITAL_PCT  = 0.15     # 15% للـ Futures — مخصص للـ Hedge فقط

# --- Risk Management / إدارة المخاطر ---
SPOT_RISK_PER_TRADE     = 0.04  # 4% مخاطرة لكل صفقة Spot (رفع للوصول لهدف 10% يومياً)
FUTURES_RISK_PER_TRADE  = 0.02  # 2% مخاطرة لكل صفقة Futures
FUTURES_LEVERAGE        = 3     # رافعة مالية 3x فقط (آمنة)
MIN_TRADE_AMOUNT        = 50    # الحد الأدنى لأي صفقة (مُعدَّل لحد 170 دولار يومياً)

# --- Stop Loss / Take Profit ---
# البوت يحسبها تلقائياً بناءً على التحليل الفني
# لكن هذه هي الحدود القصوى المسموح بها
MAX_STOP_LOSS_PCT   = 0.05      # الحد الأقصى لوقف الخسارة 5%
MIN_TAKE_PROFIT_RR  = 1.5       # الحد الأدنى لنسبة المخاطرة/المكافأة (1:1.5)
TRAILING_STOP       = True      # تفعيل Stop Loss متحرك
TRAILING_STOP_PCT   = 0.015     # نسبة الـ Trailing Stop

# --- Open Trades Limits / حدود الصفقات المفتوحة ---
MAX_SPOT_TRADES     = 999       # لا حد — طالما الرصيد يسمح
MAX_FUTURES_TRADES  = 999       # لا حد — الـ Hedge يفتح تلقائياً عند ثقة 90%+
MIN_ORDER_USDT      = 100       # الحد الأدنى لأي صفقة $100

# --- New Trade Entry Control / التحكم في فتح صفقات جديدة ---
PAUSE_NEW_TRADES    = False      # True = إيقاف مؤقت حتى تغلق الصفقات القائمة

# --- Banned Assets / الأصول المحظورة ---
BANNED_GOLD_TOKENS  = {'XAUT', 'PAXG', 'XAUM', 'XGOLD', 'PMGT', 'DGLD', 'TGOLD'}
# الذهب الرقمي محظور نهائياً — لا قيمة مضاربية كافية

# --- Market Scanner Settings / إعدادات فحص السوق ---
# البوت يفحص كامل السوق تلقائياً ولا يحتاج قائمة يدوية
SCAN_TOP_N_COINS        = 100   # فحص أفضل 100 عملة من حيث حجم التداول
MIN_VOLUME_24H_USD      = 5_000_000   # الحد الأدنى لحجم التداول اليومي ($5M)
MIN_PRICE_CHANGE_SIGNAL = 2.0   # الحد الأدنى لتغير السعر % لاعتباره إشارة

# --- Signal Scoring Thresholds / عتبات نقاط الإشارة ---
# ⚠️ الاستراتيجية الجديدة: شروط صارمة — النمط الرابح المُثبَت:
# Breakout+Retest مع Score≥5 + OI متصاعد + قطاع رائد + EMA50 فوق + TP1≥2.5%
MIN_SCORE_FOR_SPOT      = 5     # رُفع من 2.5 إلى 5 — فقط الإشارات عالية الجودة
MIN_SCORE_FOR_FUTURES   = 6     # رُفع من 4 إلى 6
MIN_SCORE_FOR_SHORT     = 5     # رُفع من 4 إلى 5
MIN_CONFIDENCE_FOR_SPOT = 0.65  # الحد الأدنى للثقة 65%
MIN_TP1_PERCENT         = 0.025 # الحد الأدنى لـ TP1: 2.5% (يضمن ربح يتجاوز الرسوم بـ 10x)
DAILY_PROFIT_TARGET_PCT = 0.10  # هدف الربح اليومي 10% من رأس المال

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
TELEGRAM_CHAT_ID          = "-1003907481197"  # Trade Lak Trade — القناة الرئيسية للصفقات
TELEGRAM_PRIVATE_CHAT    = "6633826689"   # المحادثة الخاصة بالمالك — للتقارير الداخلية فقط
TELEGRAM_LIQUIDITY_CHAT   = "-1003942444248"  # Trade Lak Liquidity — إشارات السيولة
TELEGRAM_SIGNAL_CHAT      = "-1003834970832"  # Trade Lak Signal — إشارات الصفقات

# --- AI Chatbot Configuration ---
CHATBOT_ENABLED      = True
CHATBOT_LANGUAGE     = 'ar'  # Arabic / العربية
CHATBOT_RESPONSE_TIME = 1    # seconds
CHATBOT_MEMORY_SIZE  = 100   # conversation history size

# --- General Settings ---
LOG_LEVEL        = "INFO"
CHECK_INTERVAL   = 30       # فحص السوق كل 30 ثانية
DRY_RUN          = False    # True = اختبار | False = تداول حقيقي

# ── Bybit API (RSA Authentication) ───────────────────────────────
BYBIT_API_KEY = 'PuPbKUWM3TRGYFvIHb'
BYBIT_API_SECRET = ''  # HMAC Secret
BYBIT_API_PRIVATE_KEY_PATH = '/root/trade_lak_bot/keys/bybit_private_v2.pem'
BYBIT_ENV              = 'mainnet'  # mainnet أو testnet

BYBIT_RSA_PRIVATE_KEY_PATH = '/root/trade_lak_bot/keys/bybit_private_v2.pem'
