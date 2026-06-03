"""
سكريبت مزامنة المحفظة الفعلية مع Trade Lak
يحقن الـ 12 عملة في open_spot_trades مع SL/TP مناسب
"""
import sys, os, json, pickle
from datetime import datetime

sys.path.insert(0, '/root/trade_lak_bot')
sys.path.insert(0, '/root/trade_lak_bot/venv/lib/python3.12/site-packages')

# قراءة أسعار الدخول المحسوبة
with open('/root/entry_prices.json') as f:
    entry_prices = json.load(f)

# بيانات المحفظة الفعلية
portfolio = {
    'XRP/USDT':  {'amount': 140.004889, 'current_price': 1.3566,  'value': 189.93},
    'UNI/USDT':  {'amount': 29.435686,  'current_price': 3.4390,  'value': 101.23},
    'ADA/USDT':  {'amount': 406.033860, 'current_price': 0.2455,  'value': 99.68},
    'TRX/USDT':  {'amount': 270.724833, 'current_price': 0.3633,  'value': 98.35},
    'ICP/USDT':  {'amount': 15.694311,  'current_price': 2.5920,  'value': 40.68},
    'SUI/USDT':  {'amount': 19.368398,  'current_price': 1.0573,  'value': 20.48},
    'SOL/USDT':  {'amount': 0.237366,   'current_price': 85.71,   'value': 20.34},
    'LINK/USDT': {'amount': 2.121319,   'current_price': 9.5430,  'value': 20.24},
    'BNB/USDT':  {'amount': 0.026375,   'current_price': 654.60,  'value': 17.26},
    'XAUT/USDT': {'amount': 0.002220,   'current_price': 4518.10, 'value': 10.03},
    'BTC/USDT':  {'amount': 0.000130,   'current_price': 76718.0, 'value': 9.99},
    'LTC/USDT':  {'amount': 0.107971,   'current_price': 53.27,   'value': 5.75},
}

# بناء قاموس open_spot_trades
open_spot_trades = {}

for symbol, info in portfolio.items():
    coin = symbol.replace('/USDT', '')
    entry_data = entry_prices.get(coin, {})
    entry_price = entry_data.get('avg_entry', info['current_price'])
    current_price = info['current_price']
    amount_coin = info['amount']
    amount_usdt = info['value']
    
    # حساب SL: 3% تحت سعر الدخول (أو 1.5% تحت الحالي إذا كان في ربح)
    pnl_pct = entry_data.get('pnl_pct', 0)
    if pnl_pct > 2:
        # في ربح — SL عند نقطة التعادل + 0.5%
        sl = entry_price * 1.005  # حماية الربح
    else:
        # قريب من الدخول — SL عند 3% تحت الدخول
        sl = entry_price * 0.97
    
    # حساب TP: 3 مستويات
    risk = abs(entry_price - sl)
    tp1 = entry_price + risk * 1.5   # TP1: 1.5× المخاطرة
    tp2 = entry_price + risk * 3.0   # TP2: 3× المخاطرة
    tp3 = entry_price + risk * 5.0   # TP3: 5× المخاطرة
    
    trade_record = {
        'entry_price': entry_price,
        'stop_loss': sl,
        'take_profit': tp1,
        'take_profit_2': tp2,
        'take_profit_3': tp3,
        'amount_usdt': amount_usdt,
        'amount_coin': amount_coin,
        'direction': 'SPOT_BUY',
        'open_time': datetime.now(),
        'best_price': current_price,
        'confidence': 60.0,
        'reasons': ['Portfolio sync - existing position'],
        'sector': 'Synced',
        'sector_boost': 0,
        'is_explosion_candidate': False,
        'synced_from_portfolio': True,
        'pnl_pct_at_sync': pnl_pct,
    }
    
    open_spot_trades[symbol] = trade_record
    status = '🟢' if pnl_pct > 0 else '🔴'
    print(f"{status} {symbol:12}: دخول=${entry_price:.4f} | SL=${sl:.4f} | TP1=${tp1:.4f} | P&L={pnl_pct:+.2f}%")

print(f"\n✅ تم بناء {len(open_spot_trades)} صفقة للمزامنة")

# حفظ القاموس كـ pickle لاستخدامه في سكريبت الحقن
with open('/root/sync_trades.pkl', 'wb') as f:
    pickle.dump(open_spot_trades, f)

# أيضاً حفظ كـ JSON للمراجعة
def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

with open('/root/sync_trades.json', 'w') as f:
    json.dump(open_spot_trades, f, indent=2, default=serialize)

print("✅ تم حفظ البيانات في /root/sync_trades.pkl و /root/sync_trades.json")
print("\n=== الخطوة التالية: تشغيل inject_sync.py لحقن الصفقات في Trade Lak ===")
