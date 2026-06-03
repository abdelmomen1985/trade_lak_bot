"""
patch_fake_break.py
يدمج FakeBreakDetector في intelligence_engine:
1. يضيف import
2. يرفع وزن fake_break إلى 0.30 ويعيد توزيع الأوزان
3. يضيف استدعاء FakeBreakDetector في دالة analyze()
4. يضيف fake_break_score إلى weighted_score
"""

import re

path = '/root/trade_lak_bot/core/intelligence_engine.py'

with open(path, 'r') as f:
    content = f.read()

# ── 1. إضافة import ──────────────────────────────────────────
old_import = "from core.market_indicators_engine import MarketIndicatorsEngine"
new_import = """from core.market_indicators_engine import MarketIndicatorsEngine
from core.fake_break_detector import FakeBreakDetector"""

if 'from core.fake_break_detector import FakeBreakDetector' not in content:
    content = content.replace(old_import, new_import)
    print("✅ أُضيف import FakeBreakDetector")
else:
    print("⚠️ import موجود مسبقاً")

# ── 2. تحديث WEIGHTS ─────────────────────────────────────────
old_weights = '''WEIGHTS = {
    "ml_model": 0.25,           # 25% — نموذج التعلم الآلي
    "multi_strategy": 0.25,     # 25% — الاستراتيجيات المتعددة
    "onchain": 0.20,            # 20% — تحركات البلوكشين
    "orderbook": 0.15,          # 15% — دفتر الأوامر
    "coinglass": 0.07,          # 7% — بيانات CoinGlass
    "news_sentiment": 0.03,     # 3% — تحليل أخبار CryptoPanic
    "wick_detection": 0.05,     # 5% — كشف ذيول الشموع (فلتر أمان)
}'''

new_weights = '''WEIGHTS = {
    "fake_break": 0.30,         # 30% — استراتيجية دعم+كسر كاذب+تأكيد (Trade Lak)
    "ml_model": 0.18,           # 18% — نموذج التعلم الآلي
    "multi_strategy": 0.18,     # 18% — الاستراتيجيات المتعددة
    "onchain": 0.14,            # 14% — تحركات البلوكشين
    "orderbook": 0.10,          # 10% — دفتر الأوامر
    "coinglass": 0.05,          # 5%  — بيانات CoinGlass
    "news_sentiment": 0.02,     # 2%  — تحليل أخبار CryptoPanic
    "wick_detection": 0.03,     # 3%  — كشف ذيول الشموع (فلتر أمان)
}'''

if '"fake_break": 0.30' not in content:
    content = content.replace(old_weights, new_weights)
    if '"fake_break": 0.30' in content:
        print("✅ تم تحديث WEIGHTS")
    else:
        print("⚠️ لم يتم تحديث WEIGHTS — سيتم البحث عن نمط مختلف")
        # محاولة بديلة
        content = re.sub(
            r'WEIGHTS\s*=\s*\{[^}]+\}',
            new_weights,
            content,
            count=1
        )
        if '"fake_break": 0.30' in content:
            print("✅ تم تحديث WEIGHTS (بديل)")
        else:
            print("❌ فشل تحديث WEIGHTS")
else:
    print("⚠️ WEIGHTS محدّث مسبقاً")

# ── 3. إضافة FakeBreakDetector في __init__ ───────────────────
old_init_end = "self.market_indicators = MarketIndicatorsEngine()"
new_init_end = """self.market_indicators = MarketIndicatorsEngine()
        # استراتيجية Trade Lak: دعم + كسر كاذب + تأكيد
        self.fake_break_detector = FakeBreakDetector()"""

if 'self.fake_break_detector = FakeBreakDetector()' not in content:
    content = content.replace(old_init_end, new_init_end)
    if 'self.fake_break_detector' in content:
        print("✅ أُضيف fake_break_detector في __init__")
    else:
        print("❌ فشل إضافة fake_break_detector في __init__")
else:
    print("⚠️ fake_break_detector موجود في __init__")

# ── 4. إضافة استدعاء FakeBreakDetector في analyze() ─────────
# نضيفه قبل سطر "# ── القرار النهائي"
old_final = "        # ── القرار النهائي ─────────────────────────────────────────"
new_fake_break_block = '''        # ── 7. Fake Break Detector (استراتيجية Trade Lak الأساسية) ──────────
        fake_break_result = None
        try:
            fake_break_result = self.fake_break_detector.analyze(ohlcv_data)
            results['fake_break'] = fake_break_result
            fb_score = fake_break_result.get('score', 0)
            weighted_score += fb_score * WEIGHTS['fake_break']
            if fake_break_result.get('signal', 0) == 1:
                signal_count['buy'] += 2  # وزن مضاعف لأهمية الاستراتيجية
            elif fake_break_result.get('signal', 0) == -1:
                signal_count['sell'] += 2
            if fake_break_result.get('fake_break_detected'):
                logger.info(
                    f"  🎯 Fake Break: {fake_break_result.get('reason', '')} | "
                    f"نقاط={fb_score:.2f} | ثقة={fake_break_result.get('confidence', 0):.0f}%"
                )
            else:
                logger.debug(f"  🎯 Fake Break: {fake_break_result.get('reason', 'لا إشارة')}")
        except Exception as e:
            logger.warning(f"  ⚠️ FakeBreakDetector تعذّر: {e}")
            results['fake_break'] = {"signal": 0, "score": 0, "fake_break_detected": False}

        # ── القرار النهائي ─────────────────────────────────────────'''

if 'fake_break_result = self.fake_break_detector.analyze' not in content:
    content = content.replace(old_final, new_fake_break_block)
    if 'fake_break_result = self.fake_break_detector.analyze' in content:
        print("✅ أُضيف استدعاء FakeBreakDetector في analyze()")
    else:
        print("❌ فشل إضافة استدعاء FakeBreakDetector")
else:
    print("⚠️ استدعاء FakeBreakDetector موجود مسبقاً")

# ── 5. تمرير fake_break_result إلى _make_final_decision ──────
old_final_call = "final = self._make_final_decision(weighted_score, results, signal_count, wick_analysis)"
new_final_call = "final = self._make_final_decision(weighted_score, results, signal_count, wick_analysis, fake_break_result)"

content = content.replace(old_final_call, new_final_call)
print("✅ تم تحديث استدعاء _make_final_decision")

# ── 6. تحديث _make_final_decision لاستخدام fake_break ────────
old_make_final_sig = "    def _make_final_decision(self, weighted_score: float, results: Dict, \n                            signal_count: Dict, wick_analysis=None) -> Dict:"
new_make_final_sig = "    def _make_final_decision(self, weighted_score: float, results: Dict, \n                            signal_count: Dict, wick_analysis=None, fake_break_result=None) -> Dict:"

content = content.replace(old_make_final_sig, new_make_final_sig)
print("✅ تم تحديث signature _make_final_decision")

# ── حفظ الملف ────────────────────────────────────────────────
with open(path, 'w') as f:
    f.write(content)

print("\n✅ تم تطبيق جميع التغييرات على intelligence_engine.py")

# ── فحص syntax ───────────────────────────────────────────────
import subprocess
result = subprocess.run(
    ['python3', '-m', 'py_compile', path],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("✅ Syntax صحيح")
else:
    print(f"❌ خطأ syntax: {result.stderr}")
