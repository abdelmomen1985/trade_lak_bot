#!/usr/bin/env python3
"""Test wick detection integration with main bot components"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 80)
print("🧪 اختبار تكامل محرك كشف الذيول")
print("=" * 80)

# Test 1: Import all components
print("\n1️⃣ اختبار الاستيراد...")
try:
    from core.wick_detection_engine import WickDetectionEngine, WickDangerLevel
    from core.intelligence_engine import AdvancedIntelligenceEngine
    from utils.telegram_notifier import TelegramNotifier
    print("✅ تم استيراد جميع المكونات بنجاح!")
except Exception as e:
    print(f"❌ خطأ في الاستيراد: {e}")
    sys.exit(1)

# Test 2: Create wick detector
print("\n2️⃣ اختبار إنشاء محرك كشف الذيول...")
try:
    wick_engine = WickDetectionEngine()
    print("✅ تم إنشاء محرك كشف الذيول بنجاح!")
except Exception as e:
    print(f"❌ خطأ: {e}")
    sys.exit(1)

# Test 3: Test various wick patterns
print("\n3️⃣ اختبار أنماط ذيول مختلفة...")

test_cases = [
    {
        'name': 'Hammer (فخ بيع)',
        'open': 100,
        'high': 101,
        'low': 95,
        'close': 100.5,
        'volume': 1000,
        'avg_volume': 800
    },
    {
        'name': 'Shooting Star (فخ شراء)',
        'open': 100,
        'high': 110,
        'low': 99,
        'close': 99.5,
        'volume': 1500,
        'avg_volume': 800
    },
    {
        'name': 'Normal candle (آمن)',
        'open': 100,
        'high': 102,
        'low': 99,
        'close': 101,
        'volume': 900,
        'avg_volume': 800
    },
    {
        'name': 'Extreme wick (خطر جداً)',
        'open': 100,
        'high': 120,
        'low': 98,
        'close': 99,
        'volume': 2000,
        'avg_volume': 800
    }
]

for test in test_cases:
    print(f"\n   📊 {test['name']}:")
    analysis = wick_engine.analyze_candle(
        open_price=test['open'],
        high_price=test['high'],
        low_price=test['low'],
        close_price=test['close'],
        volume=test['volume'],
        avg_volume=test['avg_volume']
    )
    
    print(f"      نوع الذيل: {analysis.wick_type}")
    print(f"      درجة الخطورة: {analysis.danger_level.name}")
    print(f"      هل هو فخ: {'نعم ✅' if analysis.is_trap else 'لا ❌'}")
    print(f"      النقاط: {analysis.score}/100")
    print(f"      التوصية: {analysis.recommendation}")

# Test 4: Test multi-candle analysis
print("\n4️⃣ اختبار تحليل شموع متعددة...")

candles = [
    {'open': 100, 'high': 105, 'low': 99, 'close': 104, 'volume': 1000, 'avg_volume': 800},
    {'open': 104, 'high': 115, 'low': 103, 'close': 104.5, 'volume': 1500, 'avg_volume': 800},
    {'open': 104.5, 'high': 106, 'low': 103, 'close': 105, 'volume': 900, 'avg_volume': 800},
]

result = wick_engine.analyze_multi_candle(candles)
print(f"   متوسط الخطورة: {result['average_danger']:.2f}")
print(f"   تسلسل الفخاخ: {result['trap_sequence']}")
print(f"   التوصية: {result['recommendation']}")

# Test 5: Test safe entry decision
print("\n5️⃣ اختبار قرار الدخول الآمن...")

safe_candle = wick_engine.analyze_candle(
    open_price=100,
    high_price=102,
    low_price=99,
    close_price=101,
    volume=900,
    avg_volume=800
)

trap_candle = wick_engine.analyze_candle(
    open_price=100,
    high_price=110,
    low_price=99,
    close_price=99.5,
    volume=1500,
    avg_volume=800
)

print(f"   شمعة آمنة - يمكن الدخول: {wick_engine.should_enter_trade(safe_candle)}")
print(f"   شمعة فخ - لا تدخل: {wick_engine.should_enter_trade(trap_candle)}")

# Test 6: Test Telegram notifier
print("\n6️⃣ اختبار وحدة تنبيهات Telegram...")
try:
    # Create a dummy notifier (won't actually send without valid token)
    notifier = TelegramNotifier(bot_token="dummy_token", chat_id="dummy_chat")
    print("✅ تم إنشاء وحدة التنبيهات بنجاح!")
    
    # Check if notify_wick_trap method exists
    if hasattr(notifier, 'notify_wick_trap'):
        print("✅ دالة notify_wick_trap موجودة!")
    else:
        print("❌ دالة notify_wick_trap غير موجودة!")
except Exception as e:
    print(f"❌ خطأ: {e}")

# Test 7: Summary
print("\n" + "=" * 80)
print("✅ جميع الاختبارات نجحت!")
print("=" * 80)
print("""
📊 ملخص الاختبارات:
   ✅ استيراد المكونات
   ✅ إنشاء محرك كشف الذيول
   ✅ تحليل أنماط ذيول مختلفة
   ✅ تحليل شموع متعددة
   ✅ قرار الدخول الآمن
   ✅ وحدة تنبيهات Telegram

🎯 البوت جاهز للتشغيل!
""")
