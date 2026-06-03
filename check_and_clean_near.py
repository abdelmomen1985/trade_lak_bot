#!/usr/bin/env python3
"""
التحقق من رصيد NEAR الفعلي في OKX وتنظيف active_trades.json
"""
import sys, json, os
sys.path.insert(0, '/root/trade_lak_bot')
os.chdir('/root/trade_lak_bot')

from core.okx_client import OKXClient

okx = OKXClient()

# فحص رصيد NEAR الفعلي
try:
    bal = okx.get_balance()
    print(f"الرصيد الكلي: {json.dumps(bal, indent=2, default=str)}")
except Exception as e:
    print(f"خطأ في get_balance: {e}")

# فحص NEAR تحديداً
try:
    import ccxt
    exchange = okx.exchange
    balance = exchange.fetch_balance()
    near_free = balance.get('NEAR', {}).get('free', 0)
    near_total = balance.get('NEAR', {}).get('total', 0)
    usdt_free = balance.get('USDT', {}).get('free', 0)
    print(f"\nNEAR free: {near_free}")
    print(f"NEAR total: {near_total}")
    print(f"USDT free: {usdt_free:.2f}")
except Exception as e:
    print(f"خطأ في fetch_balance: {e}")

# تنظيف active_trades.json
trades_path = '/root/trade_lak_bot/data/active_trades.json'
with open(trades_path, 'r') as f:
    trades = json.load(f)

print(f"\nالصفقات الحالية في active_trades.json: {list(trades.keys())}")

# حفظ نسخة احتياطية
import shutil, time
backup_path = f'/root/trade_lak_bot/data/active_trades_backup_{int(time.time())}.json'
shutil.copy(trades_path, backup_path)
print(f"نسخة احتياطية: {backup_path}")

# تفريغ الملف
with open(trades_path, 'w') as f:
    json.dump({}, f, indent=2)

print("✅ تم تفريغ active_trades.json")
