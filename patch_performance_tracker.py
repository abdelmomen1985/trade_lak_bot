"""
دمج PerformanceTracker في main.py
"""

with open('/root/trade_lak_bot/main.py', 'r') as f:
    content = f.read()

# ── 1. إضافة import ──────────────────────────────────────────
old_import = 'from startup_health_check import StartupHealthCheck'
new_import = '''from startup_health_check import StartupHealthCheck
from performance_tracker import PerformanceTracker'''

if old_import in content and 'from performance_tracker' not in content:
    content = content.replace(old_import, new_import, 1)
    print('SUCCESS: تمت إضافة import PerformanceTracker')
else:
    print('WARNING: import موجود بالفعل أو لم يُعثر على نقطة الإدراج')

# ── 2. تهيئة PerformanceTracker في __init__ ──────────────────
old_init = 'self.health_checker = StartupHealthCheck(self)'
new_init = '''self.health_checker = StartupHealthCheck(self)
        self.perf_tracker = PerformanceTracker(
            notifier=self.notifier,
            total_capital=1104.98
        )'''

if old_init in content and 'self.perf_tracker' not in content:
    content = content.replace(old_init, new_init, 1)
    print('SUCCESS: تمت تهيئة PerformanceTracker في __init__')
else:
    print('WARNING: التهيئة موجودة بالفعل أو لم يُعثر على نقطة الإدراج')

# ── 3. تسجيل فتح الصفقة ──────────────────────────────────────
# البحث عن مكان تسجيل الصفقة في open_spot_trades
old_open = "self.strategy.open_spot_trades[symbol] = trade_record\n                logger.info("
new_open = """self.strategy.open_spot_trades[symbol] = trade_record
                # تسجيل في Performance Tracker
                try:
                    self.perf_tracker.record_trade_open(
                        symbol=symbol,
                        direction='SPOT_BUY',
                        entry_price=trade_record.get('entry_price', 0),
                        amount_usdt=trade_record.get('amount_usdt', 0),
                        confidence=trade_record.get('confidence', 0),
                    )
                except Exception as _pt_err:
                    logger.debug(f"Tracker open error: {_pt_err}")
                logger.info("""

if old_open in content:
    content = content.replace(old_open, new_open, 1)
    print('SUCCESS: تمت إضافة تسجيل فتح الصفقة في Tracker')
else:
    print('WARNING: لم يُعثر على نقطة تسجيل فتح الصفقة')

# ── 4. تسجيل إغلاق الصفقة ────────────────────────────────────
# البحث عن مكان حذف الصفقة من open_spot_trades
old_close = "del trades[symbol]"
new_close = """# تسجيل الإغلاق في Performance Tracker
                    try:
                        _exit_price = trades[symbol].get('current_price', 0)
                        self.perf_tracker.record_trade_close(
                            symbol=symbol,
                            exit_price=_exit_price,
                            exit_reason=exit_reason if 'exit_reason' in dir() else 'monitor',
                        )
                    except Exception as _pt_err:
                        logger.debug(f"Tracker close error: {_pt_err}")
                    del trades[symbol]"""

if old_close in content and 'record_trade_close' not in content:
    content = content.replace(old_close, new_close, 1)
    print('SUCCESS: تمت إضافة تسجيل إغلاق الصفقة في Tracker')
else:
    print('WARNING: تسجيل الإغلاق موجود بالفعل أو لم يُعثر على نقطة الإدراج')

# ── 5. استدعاء check_periodic_reports في الحلقة الرئيسية ─────
# البحث عن periodic_review في الحلقة
old_periodic = 'self.periodic_review.check_and_run()'
new_periodic = '''self.periodic_review.check_and_run()
                # فحص تقارير الأداء
                try:
                    bal = self.okx.spot.fetch_balance()
                    _portfolio_val = float(bal['total'].get('USDT', 0))
                    self.perf_tracker.check_periodic_reports(_portfolio_val)
                except Exception as _pr_err:
                    logger.debug(f"Perf report error: {_pr_err}")'''

if old_periodic in content and 'check_periodic_reports' not in content:
    content = content.replace(old_periodic, new_periodic, 1)
    print('SUCCESS: تمت إضافة check_periodic_reports في الحلقة الرئيسية')
else:
    print('WARNING: check_periodic_reports موجود بالفعل أو لم يُعثر على نقطة الإدراج')

# حفظ الملف
with open('/root/trade_lak_bot/main.py', 'w') as f:
    f.write(content)

# التحقق من صحة الملف
import ast
try:
    ast.parse(content)
    print('SUCCESS: main.py صحيح نحوياً ✅')
except SyntaxError as e:
    print(f'ERROR: خطأ نحوي في main.py: {e}')
