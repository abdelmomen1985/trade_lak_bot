import sys
sys.path.insert(0, '/root/trade_lak_bot/venv/lib/python3.12/site-packages')
import ccxt

exchange = ccxt.okx({
    'apiKey': '35c12b6c-deda-4d0e-8f4c-d0e4ca8a608d',
    'secret': '4495EDF88675CEE07291C4E4E5583F43',
    'password': 'Lrtm@01102200',
    'enableRateLimit': True,
})

try:
    result = exchange.fetch_balance({'type': 'trading'})
    print('=== كل العملات في محفظة Trading ===')
    total_usdt = 0
    assets = []
    
    for coin, amount in result['total'].items():
        if amount and float(amount) > 0 and coin != 'USDT':
            try:
                ticker = exchange.fetch_ticker(coin + '/USDT')
                price = float(ticker['last'])
                value_usdt = float(amount) * price
                assets.append((coin, float(amount), price, value_usdt))
                total_usdt += value_usdt
            except:
                assets.append((coin, float(amount), 0, 0))
    
    assets.sort(key=lambda x: x[3], reverse=True)
    
    print(f"{'العملة':8} | {'الكمية':15} | {'السعر':14} | {'القيمة USDT':12}")
    print("-" * 60)
    for coin, amount, price, value in assets:
        print(f"{coin:8} | {amount:15.6f} | ${price:13.4f} | ${value:11.2f}")
    
    usdt_free = float(result['free'].get('USDT', 0) or 0)
    usdt_total = float(result['total'].get('USDT', 0) or 0)
    print("-" * 60)
    print(f"{'USDT':8} | {'':15} | {'':14} | ${usdt_free:11.2f}")
    print(f"\nعدد العملات (غير USDT): {len(assets)}")
    print(f"إجمالي قيمة العملات:   ${total_usdt:.2f}")
    print(f"USDT حر:               ${usdt_free:.2f}")
    print(f"الإجمالي الكلي:        ${total_usdt + usdt_free:.2f}")

except Exception as e:
    import traceback
    print(f'خطأ: {e}')
    traceback.print_exc()
