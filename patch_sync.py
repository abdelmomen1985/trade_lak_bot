"""
Patch لإضافة كود مزامنة المحفظة في main.py
يُضاف بعد سطر "Bot state"
"""
import sys

main_file = '/root/trade_lak_bot/main.py'

with open(main_file, 'r') as f:
    content = f.read()

# التحقق من عدم وجود الكود مسبقاً
if 'portfolio_sync' in content:
    print("✅ كود المزامنة موجود بالفعل في main.py")
    sys.exit(0)

# الكود الذي سنضيفه — بعد "# Bot state"
sync_code = '''
        # === مزامنة المحفظة الفعلية عند البدء ===
        import os as _os, pickle as _pkl
        _sync_file = _os.path.join(_os.path.dirname(__file__), 'data', 'portfolio_sync.pkl')
        if _os.path.exists(_sync_file):
            try:
                _synced = _pkl.load(open(_sync_file, 'rb'))
                self.strategy.open_spot_trades.update(_synced)
                logger.info(f"✅ مزامنة المحفظة: تم تحميل {len(_synced)} صفقة من المحفظة الفعلية")
                for _sym in _synced:
                    logger.info(f"   📌 {_sym}: دخول=${_synced[_sym]['entry_price']:.4f} | SL=${_synced[_sym]['stop_loss']:.4f}")
                _os.rename(_sync_file, _sync_file + '.loaded')
            except Exception as _e:
                logger.warning(f"⚠️ فشل تحميل مزامنة المحفظة: {_e}")
        # === نهاية مزامنة المحفظة ===
'''

# إضافة الكود بعد "# Bot state"
if '        # Bot state' in content:
    content = content.replace(
        '        # Bot state',
        sync_code + '        # Bot state'
    )
    with open(main_file, 'w') as f:
        f.write(content)
    print("✅ تم إضافة كود مزامنة المحفظة في main.py (بعد # Bot state)")
else:
    # بديل: إضافة قبل "self.running = True"
    content = content.replace(
        '        self.running = True',
        sync_code + '        self.running = True'
    )
    with open(main_file, 'w') as f:
        f.write(content)
    print("✅ تم إضافة كود مزامنة المحفظة في main.py (قبل self.running)")

# التحقق
import subprocess
result = subprocess.run(
    ['/root/trade_lak_bot/venv/bin/python3', '-m', 'py_compile', main_file],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("✅ main.py صحيح نحوياً")
else:
    print(f"❌ خطأ نحوي: {result.stderr}")
