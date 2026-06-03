#!/usr/bin/env python3
"""
إصلاح المزامنة: بدلاً من الاعتماد على ملف مؤقت يُحذف،
نجعل البوت يجلب المحفظة مباشرة من OKX عند كل إعادة تشغيل
"""

import re

MAIN_FILE = '/root/trade_lak_bot/main.py'

with open(MAIN_FILE, 'r') as f:
    content = f.read()

# الكود القديم للمزامنة (يعتمد على ملف pkl مؤقت)
OLD_SYNC = '''        # === مزامنة المحفظة الفعلية عند البدء ===
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
        # === نهاية مزامنة المحفظة ==='''

# الكود الجديد: يجلب المحفظة مباشرة من OKX عند كل بدء تشغيل
NEW_SYNC = '''        # === مزامنة المحفظة الفعلية عند كل بدء تشغيل ===
        try:
            self._auto_sync_portfolio()
        except Exception as _sync_err:
            logger.warning(f"⚠️ فشل المزامنة التلقائية: {_sync_err}")
        # === نهاية مزامنة المحفظة ==='''

if OLD_SYNC in content:
    content = content.replace(OLD_SYNC, NEW_SYNC)
    print("✅ تم استبدال كود المزامنة القديم")
else:
    print("❌ لم يُعثر على الكود القديم — تحقق يدوياً")
    # محاولة بديلة
    if '# === مزامنة المحفظة الفعلية عند البدء ===' in content:
        # استبدال المنطقة بأكملها
        content = re.sub(
            r'# === مزامنة المحفظة الفعلية عند البدء ===.*?# === نهاية مزامنة المحفظة ===',
            NEW_SYNC.strip(),
            content,
            flags=re.DOTALL
        )
        print("✅ تم الاستبدال بالـ regex")

# إضافة دالة _auto_sync_portfolio قبل دالة run
AUTO_SYNC_METHOD = '''
    def _auto_sync_portfolio(self):
        """مزامنة تلقائية مع المحفظة الفعلية من OKX عند كل بدء تشغيل"""
        import time as _time
        try:
            bal = self.okx.spot.fetch_balance()
            assets = {k: v for k, v in bal['total'].items() 
                      if v and v > 0 and k not in ('USDT', 'USDC', 'BUSD', 'DAI')}
            
            if not assets:
                logger.info("📭 لا توجد عملات في المحفظة للمزامنة")
                return
            
            synced_count = 0
            for coin, qty in assets.items():
                symbol = f"{coin}/USDT"
                
                # تخطي إذا كانت الصفقة موجودة بالفعل
                if symbol in self.strategy.open_spot_trades:
                    continue
                
                # جلب السعر الحالي
                ticker = self.okx.get_ticker(symbol, 'spot')
                if not ticker or not ticker.get('price'):
                    continue
                
                current_price = ticker['price']
                value_usdt = qty * current_price
                
                # تجاهل القيم الصغيرة جداً (أقل من $5)
                if value_usdt < 5:
                    continue
                
                # محاولة جلب سعر الدخول من سجل الصفقات
                try:
                    trades_hist = self.okx.spot.fetch_my_trades(symbol, limit=10)
                    buy_trades = [t for t in trades_hist if t.get('side') == 'buy']
                    if buy_trades:
                        total_cost = sum(t['cost'] for t in buy_trades)
                        total_qty  = sum(t['amount'] for t in buy_trades)
                        entry_price = total_cost / total_qty if total_qty > 0 else current_price
                    else:
                        entry_price = current_price
                except:
                    entry_price = current_price
                
                # حساب SL/TP بناءً على سعر الدخول
                sl_pct = 0.04  # 4% stop loss
                tp_pct = 0.08  # 8% take profit
                
                # إذا كان السعر الحالي أعلى من الدخول → نضع SL عند نقطة التعادل أو أعلى
                if current_price > entry_price * 1.02:
                    # في ربح → SL عند نقطة التعادل + 0.5%
                    stop_loss = entry_price * 1.005
                elif current_price > entry_price:
                    stop_loss = entry_price * 0.98
                else:
                    stop_loss = entry_price * (1 - sl_pct)
                
                take_profit = entry_price * (1 + tp_pct)
                
                trade_record = {
                    'symbol': symbol,
                    'direction': 'BUY',
                    'market': 'spot',
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'quantity': qty,
                    'amount_usdt': value_usdt,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'take_profit_2': entry_price * (1 + tp_pct * 1.5),
                    'take_profit_3': entry_price * (1 + tp_pct * 2.5),
                    'confidence': 60.0,
                    'sector': 'synced',
                    'entry_time': _time.time(),
                    'synced_from_portfolio': True,
                }
                
                self.strategy.open_spot_trades[symbol] = trade_record
                pnl_pct = (current_price - entry_price) / entry_price * 100
                pnl_sign = "🟢" if pnl_pct >= 0 else "🔴"
                logger.info(
                    f"   📌 {symbol}: دخول=${entry_price:.4f} | "
                    f"الآن=${current_price:.4f} | "
                    f"{pnl_sign} {pnl_pct:+.2f}% | "
                    f"SL=${stop_loss:.4f} | القيمة=${value_usdt:.2f}"
                )
                synced_count += 1
            
            if synced_count > 0:
                logger.info(f"✅ مزامنة تلقائية: تم تحميل {synced_count} عملة من المحفظة الفعلية")
            else:
                logger.info("✅ المزامنة: جميع العملات محملة مسبقاً")
                
        except Exception as e:
            logger.error(f"خطأ في المزامنة التلقائية: {e}")

'''

# إضافة الدالة قبل دالة run
if 'def _auto_sync_portfolio' not in content:
    # إيجاد دالة run وإضافة الدالة قبلها
    run_idx = content.find('\n    def run(self)')
    if run_idx == -1:
        run_idx = content.find('\n    def run(')
    
    if run_idx != -1:
        content = content[:run_idx] + AUTO_SYNC_METHOD + content[run_idx:]
        print("✅ تم إضافة دالة _auto_sync_portfolio")
    else:
        print("❌ لم يُعثر على دالة run")
else:
    print("ℹ️ دالة _auto_sync_portfolio موجودة مسبقاً")

# حفظ الملف
with open(MAIN_FILE, 'w') as f:
    f.write(content)

print("✅ تم حفظ main.py بالمزامنة التلقائية")

# التحقق من الصحة
import subprocess
result = subprocess.run(['python3', '-m', 'py_compile', MAIN_FILE], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Syntax صحيح")
else:
    print(f"❌ خطأ syntax: {result.stderr}")
