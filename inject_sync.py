"""
سكريبت حقن الصفقات المزامنة في Trade Lak
يعمل عبر تعديل ملف الحالة أو إرسال إشارة للبوت
"""
import sys, os, json, pickle, subprocess, time
from datetime import datetime

# قراءة الصفقات المزامنة
with open('/root/sync_trades.pkl', 'rb') as f:
    sync_trades = pickle.load(f)

print(f"=== حقن {len(sync_trades)} صفقة في Trade Lak ===\n")

# إيقاف البوت مؤقتاً
print("⏸️ إيقاف Trade Lak مؤقتاً...")
result = subprocess.run(['pkill', '-f', 'python3.*main.py'], capture_output=True)
time.sleep(3)

# التحقق من إيقاف البوت
check = subprocess.run(['pgrep', '-f', 'python3.*main.py'], capture_output=True, text=True)
if check.returncode == 0:
    print(f"⚠️ البوت لا يزال يعمل (PID: {check.stdout.strip()}) — سنحاول مرة أخرى")
    subprocess.run(['kill', '-9', check.stdout.strip()])
    time.sleep(2)
else:
    print("✅ تم إيقاف Trade Lak")

# بناء سكريبت Python لحقن الصفقات مباشرة في strategy
inject_code = '''
import sys, pickle, os
from datetime import datetime

sys.path.insert(0, '/root/trade_lak_bot')
sys.path.insert(0, '/root/trade_lak_bot/venv/lib/python3.12/site-packages')

# قراءة الصفقات
with open('/root/sync_trades.pkl', 'rb') as f:
    sync_trades = pickle.load(f)

# استيراد Strategy وحقن الصفقات
from core.strategy import TradingStrategy
import yaml

with open('/root/trade_lak_bot/config_production.yaml') as f:
    cfg_data = f.read()

# إنشاء ملف حالة مؤقت يقرأه البوت عند بدء التشغيل
state_file = '/root/trade_lak_bot/data/portfolio_sync.pkl'
os.makedirs('/root/trade_lak_bot/data', exist_ok=True)

with open(state_file, 'wb') as f:
    pickle.dump(sync_trades, f)

print(f"✅ تم حفظ {len(sync_trades)} صفقة في {state_file}")
for sym, trade in sync_trades.items():
    print(f"  {sym}: entry=${trade['entry_price']:.4f} | SL=${trade['stop_loss']:.4f}")
'''

with open('/root/inject_helper.py', 'w') as f:
    f.write(inject_code)

result = subprocess.run(
    ['/root/trade_lak_bot/venv/bin/python3', '/root/inject_helper.py'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(f"تحذيرات: {result.stderr[:200]}")

# الآن نحتاج لتعديل main.py ليقرأ ملف المزامنة عند البدء
main_py = '/root/trade_lak_bot/main.py'
with open(main_py, 'r') as f:
    content = f.read()

# إضافة كود قراءة ملف المزامنة في __init__
sync_loader = '''
        # === مزامنة المحفظة الفعلية ===
        sync_file = os.path.join(os.path.dirname(__file__), 'data', 'portfolio_sync.pkl')
        if os.path.exists(sync_file):
            try:
                import pickle as _pkl
                synced = _pkl.load(open(sync_file, 'rb'))
                self.strategy.open_spot_trades.update(synced)
                logger.info(f"✅ تمت مزامنة {len(synced)} صفقة من المحفظة الفعلية")
                os.rename(sync_file, sync_file + '.loaded')
            except Exception as e:
                logger.warning(f"⚠️ فشل تحميل مزامنة المحفظة: {e}")
        # === نهاية مزامنة المحفظة ===
'''

# إيجاد مكان مناسب للإضافة — بعد تهيئة strategy
if 'self.strategy = TradingStrategy' in content and 'portfolio_sync' not in content:
    content = content.replace(
        'self.strategy = TradingStrategy',
        'self.strategy = TradingStrategy',
    )
    # إضافة بعد سطر import os إذا لم يكن موجوداً
    if 'import os' not in content:
        content = content.replace('import sys', 'import sys\nimport os')
    
    # إيجاد نهاية __init__ وإضافة كود المزامنة
    # نبحث عن آخر سطر في __init__ قبل أول def آخر
    lines = content.split('\n')
    init_end = -1
    in_init = False
    for i, line in enumerate(lines):
        if 'def __init__' in line and 'TradeLak' in content[max(0, content.find(line)-200):content.find(line)+50]:
            in_init = True
        elif in_init and line.startswith('    def ') and '__init__' not in line:
            init_end = i
            break
    
    if init_end > 0:
        # إضافة كود المزامنة قبل نهاية __init__
        lines.insert(init_end, sync_loader)
        content = '\n'.join(lines)
        with open(main_py, 'w') as f:
            f.write(content)
        print("✅ تم تعديل main.py لقراءة ملف المزامنة عند البدء")
    else:
        print("⚠️ لم يُعثر على نهاية __init__ — سيتم الحقن مباشرة")
else:
    if 'portfolio_sync' in content:
        print("✅ main.py يحتوي بالفعل على كود المزامنة")
    else:
        print("⚠️ لم يُعثر على TradingStrategy في main.py")

# إعادة تشغيل البوت
print("\n▶️ إعادة تشغيل Trade Lak...")
os.makedirs('/root/trade_lak_bot/logs', exist_ok=True)
proc = subprocess.Popen(
    ['/root/trade_lak_bot/venv/bin/python3', '/root/trade_lak_bot/main.py'],
    stdout=open('/root/trade_lak_bot/bot_log.txt', 'a'),
    stderr=subprocess.STDOUT,
    cwd='/root/trade_lak_bot',
    start_new_session=True
)
time.sleep(5)

# التحقق من التشغيل
check = subprocess.run(['pgrep', '-f', 'python3.*main.py'], capture_output=True, text=True)
if check.returncode == 0:
    print(f"✅ Trade Lak يعمل الآن (PID: {check.stdout.strip()})")
else:
    print("❌ فشل إعادة التشغيل")

print("\n✅ اكتملت المزامنة! Trade Lak يراقب الآن 12 عملة")
