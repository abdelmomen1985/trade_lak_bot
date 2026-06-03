#!/usr/bin/env python3
"""
إصلاحات شاملة:
1. تخفيض حد التجاهل من $5 إلى $1 لمراقبة جميع العملات
2. إضافة منطق جني الأرباح التدريجي (TP1/TP2/TP3) للعملات المزامَنة
3. تحسين check_exit_conditions لدعم TP متعدد المراحل
"""

import re

# ─── 1. إصلاح _auto_sync_portfolio: تخفيض الحد إلى $1 ───
MAIN_FILE = '/root/trade_lak_bot/main.py'
with open(MAIN_FILE, 'r') as f:
    main_content = f.read()

# تخفيض حد التجاهل من $5 إلى $1
main_content = main_content.replace(
    '# تجاهل القيم الصغيرة جداً (أقل من $5)\n                if value_usdt < 5:',
    '# تجاهل القيم الصغيرة جداً (أقل من $1)\n                if value_usdt < 1:'
)
print("✅ تم تخفيض حد التجاهل إلى $1")

# تحسين حساب TP في _auto_sync_portfolio ليكون متعدد المراحل
OLD_TP_CALC = '''                # حساب SL/TP بناءً على سعر الدخول
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
                
                take_profit = entry_price * (1 + tp_pct)'''

NEW_TP_CALC = '''                # حساب SL/TP بناءً على سعر الدخول
                sl_pct = 0.04  # 4% stop loss
                tp_pct = 0.08  # 8% take profit
                
                # إذا كان السعر الحالي أعلى من الدخول → نضع SL عند نقطة التعادل أو أعلى
                if current_price > entry_price * 1.05:
                    # في ربح كبير → SL عند نقطة التعادل + 1%
                    stop_loss = entry_price * 1.01
                elif current_price > entry_price * 1.02:
                    # في ربح متوسط → SL عند نقطة التعادل + 0.5%
                    stop_loss = entry_price * 1.005
                elif current_price > entry_price:
                    stop_loss = entry_price * 0.98
                else:
                    stop_loss = entry_price * (1 - sl_pct)
                
                take_profit = entry_price * (1 + tp_pct)'''

if OLD_TP_CALC in main_content:
    main_content = main_content.replace(OLD_TP_CALC, NEW_TP_CALC)
    print("✅ تم تحسين حساب SL للعملات في ربح كبير")
else:
    print("⚠️ لم يُعثر على كود TP القديم — قد يكون محدّثاً مسبقاً")

# تحسين trade_record في _auto_sync_portfolio لإضافة amount_coin
OLD_RECORD = '''                trade_record = {
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
                }'''

NEW_RECORD = '''                trade_record = {
                    'symbol': symbol,
                    'direction': 'SPOT_BUY',
                    'market': 'spot',
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'quantity': qty,
                    'amount_coin': qty,
                    'amount_usdt': value_usdt,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'take_profit_1': take_profit,
                    'take_profit_2': entry_price * (1 + tp_pct * 1.5),
                    'take_profit_3': entry_price * (1 + tp_pct * 2.5),
                    'best_price': current_price,
                    'break_even_activated': current_price > entry_price * 1.015,
                    'confidence': 60.0,
                    'sector': 'synced',
                    'entry_time': _time.time(),
                    'open_time': __import__('datetime').datetime.now(),
                    'synced_from_portfolio': True,
                }'''

if OLD_RECORD in main_content:
    main_content = main_content.replace(OLD_RECORD, NEW_RECORD)
    print("✅ تم تحسين trade_record بإضافة amount_coin وopen_time")
else:
    print("⚠️ لم يُعثر على trade_record القديم")

with open(MAIN_FILE, 'w') as f:
    f.write(main_content)

# ─── 2. تحسين check_exit_conditions في strategy.py لدعم TP متعدد ───
STRATEGY_FILE = '/root/trade_lak_bot/core/strategy.py'
with open(STRATEGY_FILE, 'r') as f:
    strat_content = f.read()

OLD_TP_CHECK = '''        # ── فحص Take Profit ──
        if direc in ('SPOT_BUY', 'LONG') and current_price >= tp:
            return True, 'TAKE_PROFIT'
        if direc == 'SHORT' and current_price <= tp:
            return True, 'TAKE_PROFIT'
        return False, None'''

NEW_TP_CHECK = '''        # ── فحص Take Profit متعدد المراحل ──
        tp1 = trade.get('take_profit_1', tp)
        tp2 = trade.get('take_profit_2', tp * 1.5)
        tp3 = trade.get('take_profit_3', tp * 2.0)
        
        if direc in ('SPOT_BUY', 'LONG'):
            # TP3 — الهدف الكامل
            if current_price >= tp3 and not trade.get('tp3_hit'):
                trade['tp3_hit'] = True
                return True, 'TAKE_PROFIT_3 🎯🎯🎯'
            # TP2 — الهدف المتوسط
            if current_price >= tp2 and not trade.get('tp2_hit'):
                trade['tp2_hit'] = True
                # رفع SL إلى TP1 لحماية الربح
                if tp1 > trade.get('stop_loss', 0):
                    trade['stop_loss'] = tp1
                    logger.info(f"🎯 TP2 لـ {symbol}: SL رُفع إلى TP1={tp1:.6f}")
                # لا نخرج عند TP2 — نستمر نحو TP3
            # TP1 — الهدف الأول
            if current_price >= tp1 and not trade.get('tp1_hit'):
                trade['tp1_hit'] = True
                # رفع SL إلى نقطة التعادل
                be_sl = trade['entry_price'] * 1.002
                if be_sl > trade.get('stop_loss', 0):
                    trade['stop_loss'] = be_sl
                    logger.info(f"🎯 TP1 لـ {symbol}: SL رُفع إلى Break Even={be_sl:.6f}")
                # لا نخرج عند TP1 — نستمر نحو TP2/TP3
            # الخروج عند TP الأصلي إذا لم يكن هناك TP متعدد
            if current_price >= tp and not trade.get('tp1_hit') and not trade.get('tp2_hit'):
                return True, 'TAKE_PROFIT'
        elif direc == 'SHORT':
            if current_price <= tp:
                return True, 'TAKE_PROFIT'
        return False, None'''

if OLD_TP_CHECK in strat_content:
    strat_content = strat_content.replace(OLD_TP_CHECK, NEW_TP_CHECK)
    print("✅ تم تحسين check_exit_conditions بـ TP متعدد المراحل")
else:
    print("⚠️ لم يُعثر على كود TP القديم في strategy.py")

with open(STRATEGY_FILE, 'w') as f:
    f.write(strat_content)

# ─── التحقق من الصحة ───
import subprocess
for f_path in [MAIN_FILE, STRATEGY_FILE]:
    result = subprocess.run(['python3', '-m', 'py_compile', f_path],
                           capture_output=True, text=True)
    fname = f_path.split('/')[-1]
    if result.returncode == 0:
        print(f"✅ {fname}: Syntax صحيح")
    else:
        print(f"❌ {fname}: {result.stderr}")
