"""
سكريبت إضافة Trade Lak Signal notification في قسم recommendations في main.py
"""
import re

path = '/root/trade_lak_bot/main.py'
content = open(path, encoding='utf-8').read()

# نجد السطر الذي يرسل الرسالة القديمة ونضيف بعده مباشرة
# نبحث عن النمط الدقيق
search = 'self.telegram.send_message(message)\n'

# نجد الموقع
idx = content.find(search)
if idx < 0:
    print("❌ Pattern 'self.telegram.send_message(message)' not found")
    exit(1)

# نتحقق أن هذا في قسم recommendations وليس مكان آخر
context = content[idx-200:idx+300]
if 'Recommendation' not in context and 'recommendation' not in context:
    print("⚠️ Found send_message but not in recommendations context, searching further...")
    idx2 = content.find(search, idx+1)
    if idx2 >= 0:
        idx = idx2
        context = content[idx-200:idx+300]

print(f"Found at position {idx}")
print("Context:", repr(context[:200]))

# الكود الجديد الذي نضيفه بعد send_message
new_code = '''self.telegram.send_message(message)
                        # ─── Trade Lak Signal Channel ───
                        if self.notifier_v2:
                            try:
                                import time as _tl_time
                                _tps = [
                                    rec.get('take_profit_1', 0),
                                    rec.get('take_profit_2', 0),
                                    rec.get('take_profit_3', 0),
                                ]
                                _factors = [f.strip() for f in rec.get('reason', '').split(',') if f.strip()]
                                if not _factors:
                                    _factors = [rec.get('reason', 'تحليل فني')]
                                self.notifier_v2.send_signal_both_languages(
                                    symbol=symbol,
                                    direction=rec.get('direction', 'BUY'),
                                    entry_price=rec.get('entry_price', current_price),
                                    stop_loss=rec.get('stop_loss', 0),
                                    targets=_tps,
                                    confidence=rec.get('confidence', rec.get('success_rate', 60) / 100),
                                    factors=_factors,
                                    signal_id=f"{symbol}_{int(_tl_time.time())}",
                                )
                            except Exception as _v2e:
                                logger.warning(f'Trade Lak Signal notify error: {_v2e}')
'''

# نستبدل
new_content = content[:idx] + new_code + content[idx + len(search):]

# نتحقق من صحة Python
import ast
try:
    ast.parse(new_content)
    print("✅ Syntax check passed")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    exit(1)

open(path, 'w', encoding='utf-8').write(new_content)
print("✅ Trade Lak Signal notification added to recommendations successfully!")

# تحقق نهائي
if 'notifier_v2.send_signal_both_languages' in new_content:
    print("✅ Verification: send_signal_both_languages found in main.py")
else:
    print("❌ Verification failed")
