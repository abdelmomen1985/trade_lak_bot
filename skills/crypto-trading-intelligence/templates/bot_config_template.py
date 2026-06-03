"""
bot_config_template.py
قالب إعدادات بوت التداول الذكي
انسخ هذا الملف إلى config/config.py وعدّل القيم حسب رأس مالك
"""

# ==================== رأس المال وإدارة المخاطر ====================
TOTAL_CAPITAL = 300          # رأس المال الكلي بـ USDT
RISK_PER_TRADE = 0.03        # 3% مخاطرة لكل صفقة
MAX_DAILY_DRAWDOWN = 0.08    # 8% خسارة يومية → إيقاف تلقائي

# ==================== حدود الصفقات ====================
MAX_SPOT_TRADES = 5          # أقصى صفقات Spot متزامنة
MAX_FUTURES_TRADES = 3       # أقصى صفقات Futures متزامنة
MIN_ORDER_AMOUNT = 10.5      # الحد الأدنى للصفقة على OKX (دولار)

# ==================== حدود الثقة ====================
MIN_CONFIDENCE = 60          # حد الثقة الأدنى للدخول (%)
HIGH_CONFIDENCE = 75         # ثقة عالية → حجم مركز أكبر
MIN_SCORE_POINTS = 60        # الحد الأدنى من نقاط الإشارة

# ==================== Stop Loss / Take Profit ====================
SPOT_SL_PCT = 0.03           # 3% Stop Loss للـ Spot
FUTURES_SL_PCT = 0.02        # 2% Stop Loss للـ Futures
TRAILING_STOP_PCT = 0.02     # 2% Trailing Stop
BREAK_EVEN_TRIGGER = 0.0015  # تفعيل Break Even عند +0.15%

TP1_PCT = 0.015              # +1.5% → إغلاق 30%
TP2_PCT = 0.030              # +3%   → إغلاق 40%
TP3_PCT = 0.060              # +6%   → إغلاق 30%

# ==================== مكافآت القطاعات ====================
SECTOR_BONUS_1ST = 0.20      # +20% للقطاع الأول
SECTOR_BONUS_2ND = 0.12      # +12% للقطاع الثاني
SECTOR_BONUS_3RD = 0.07      # +7% للقطاع الثالث

# ==================== مراقبة ما بعد الدخول ====================
POST_ENTRY_CHECK_INTERVAL = 300   # فحص كل 5 دقائق
OB_DEPTH_EXIT_THRESHOLD = -0.35   # خروج عند انخفاض 35% في عمق OB
BID_ASK_EXIT_THRESHOLD = 0.40     # خروج عند bid/ask < 0.40
VOLUME_EXIT_THRESHOLD = -0.40     # خروج عند انخفاض 40% في الحجم
OI_EXIT_THRESHOLD = -0.025        # خروج عند انخفاض 2.5% في OI
FUNDING_EXIT_THRESHOLD = 0.015    # خروج عند funding > 0.015%

# ==================== فلاتر السيولة ====================
MIN_VOLUME_24H = 5_000_000   # حجم تداول يومي أدنى ($5M)
MIN_PRICE_CHANGE_FILTER = -0.15  # تجاهل العملات التي هبطت > 15%

# ==================== إعدادات التشغيل ====================
CHECK_INTERVAL = 60          # فحص كل 60 ثانية
DRY_RUN = False              # True = وضع اختبار بدون صفقات حقيقية
LOG_LEVEL = "INFO"           # DEBUG / INFO / WARNING

# ==================== مثال حساب حجم المركز ====================
# position_size = (TOTAL_CAPITAL * RISK_PER_TRADE) / (entry_price * SPOT_SL_PCT)
# position_size = max(position_size, MIN_ORDER_AMOUNT / entry_price)
# if confidence >= HIGH_CONFIDENCE: position_size *= 1.5
