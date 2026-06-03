import sys
sys.path.insert(0, '/root/trade_lak_bot/venv/lib/python3.12/site-packages')
import ccxt
from datetime import datetime, timedelta

exchange = ccxt.okx({
    'apiKey': '35c12b6c-deda-4d0e-8f4c-d0e4ca8a608d',
    'secret': '4495EDF88675CEE07291C4E4E5583F43',
    'password': 'Lrtm@01102200',
    'enableRateLimit': True,
})

# العملات الموجودة في المحفظة مع كمياتها وقيمها الحالية
portfolio = {
    'XRP':  {'amount': 140.004889, 'current_price': 1.3566, 'current_value': 189.93},
    'UNI':  {'amount': 29.435686,  'current_price': 3.4390, 'current_value': 101.23},
    'ADA':  {'amount': 406.033860, 'current_price': 0.2455, 'current_value': 99.68},
    'TRX':  {'amount': 270.724833, 'current_price': 0.3633, 'current_value': 98.35},
    'ICP':  {'amount': 15.694311,  'current_price': 2.5920, 'current_value': 40.68},
    'SUI':  {'amount': 19.368398,  'current_price': 1.0573, 'current_value': 20.48},
    'SOL':  {'amount': 0.237366,   'current_price': 85.71,  'current_value': 20.34},
    'LINK': {'amount': 2.121319,   'current_price': 9.5430, 'current_value': 20.24},
    'BNB':  {'amount': 0.026375,   'current_price': 654.60, 'current_value': 17.26},
    'XAUT': {'amount': 0.002220,   'current_price': 4518.10,'current_value': 10.03},
    'BTC':  {'amount': 0.000130,   'current_price': 76718.0,'current_value': 9.99},
    'LTC':  {'amount': 0.107971,   'current_price': 53.27,  'current_value': 5.75},
}

print('=== سجل صفقات الشراء لكل عملة (آخر 60 يوم) ===\n')
since = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)

results = {}
for coin, info in portfolio.items():
    symbol = coin + '/USDT'
    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=50)
        buy_trades = [t for t in trades if t['side'] == 'buy']
        if buy_trades:
            total_cost = sum(t['price'] * t['amount'] for t in buy_trades)
            total_amount = sum(t['amount'] for t in buy_trades)
            avg_entry = total_cost / total_amount
            last_buy = buy_trades[-1]
            pnl_pct = ((info['current_price'] - avg_entry) / avg_entry) * 100
            results[coin] = {
                'avg_entry': avg_entry,
                'last_entry': last_buy['price'],
                'pnl_pct': pnl_pct,
                'num_trades': len(buy_trades)
            }
            status = '🟢' if pnl_pct > 0 else '🔴'
            print(f"{status} {coin:6}: متوسط دخول ${avg_entry:.4f} | حالي ${info['current_price']:.4f} | P&L: {pnl_pct:+.2f}% | صفقات: {len(buy_trades)}")
        else:
            # استخدام السعر الحالي كتقدير
            results[coin] = {
                'avg_entry': info['current_price'],
                'last_entry': info['current_price'],
                'pnl_pct': 0,
                'num_trades': 0
            }
            print(f"⚪ {coin:6}: لا سجل — سيُستخدم السعر الحالي ${info['current_price']:.4f} كسعر دخول")
    except Exception as e:
        results[coin] = {
            'avg_entry': info['current_price'],
            'last_entry': info['current_price'],
            'pnl_pct': 0,
            'num_trades': 0
        }
        print(f"⚠️ {coin:6}: خطأ ({e}) — سيُستخدم السعر الحالي")

print('\n=== ملخص الأرباح والخسائر ===')
total_pnl = 0
for coin, r in results.items():
    info = portfolio[coin]
    pnl_usd = info['current_value'] - (r['avg_entry'] * info['amount'])
    total_pnl += pnl_usd
    print(f"{coin:6}: P&L = ${pnl_usd:+.2f} ({r['pnl_pct']:+.2f}%)")

print(f"\nإجمالي الأرباح/الخسائر غير المحققة: ${total_pnl:+.2f}")

# حفظ النتائج لاستخدامها في سكريبت المزامنة
import json
with open('/root/entry_prices.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\n✅ تم حفظ أسعار الدخول في /root/entry_prices.json')
