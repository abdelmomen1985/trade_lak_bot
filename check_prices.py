import ccxt, sys
sys.path.insert(0, '/root/trade_lak_bot')
from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE

ex = ccxt.okx({'apiKey': OKX_API_KEY, 'secret': OKX_SECRET_KEY, 'password': OKX_PASSPHRASE})

# العملات التي دخلنا فيها مع أسعار الدخول والخروج
trades = {
    'LINK/USDT': {'entry': 9.2293,   'exit': None,    'exit_pct': +0.74,  'exit_reason': 'BREAK_EVEN_STOP', 'exit_price': 9.2986},
    'PEPE/USDT': {'entry': 0.000014, 'exit': None,    'exit_pct': -2.52,  'exit_reason': 'STOP_LOSS',       'exit_price': 0.000013647},
    'BNB/USDT':  {'entry': 649.6753, 'exit': None,    'exit_pct': +0.25,  'exit_reason': 'BREAK_EVEN_STOP', 'exit_price': 651.3},
    'ICP/USDT':  {'entry': 2.5600,   'exit': None,    'exit_pct': +1.21,  'exit_reason': 'BREAK_EVEN_STOP', 'exit_price': 2.591},
    'LTC/USDT':  {'entry': 52.0700,  'exit': None,    'exit_pct': +0.12,  'exit_reason': 'BREAK_EVEN_STOP', 'exit_price': 52.133},
    'ADA/USDT':  {'entry': 0.2408,   'exit': None,    'exit_pct': +0.13,  'exit_reason': 'BREAK_EVEN_STOP', 'exit_price': 0.24111},
    'PEPE/USDT2':{'entry': 0.000014, 'exit': None,    'exit_pct': -0.78,  'exit_reason': 'STOP_LOSS',       'exit_price': 0.000013891},
    'TRX/USDT':  {'entry': 0.3595,   'exit': None,    'exit_pct': None,   'exit_reason': 'OPEN',            'exit_price': None},
    'XAUT/USDT': {'entry': 4500.0,   'exit': None,    'exit_pct': None,   'exit_reason': 'OPEN',            'exit_price': None},
    'BTC/USDT':  {'entry': 76718.2,  'exit': None,    'exit_pct': None,   'exit_reason': 'OPEN',            'exit_price': None},
}

coins = ['LINK/USDT','PEPE/USDT','BNB/USDT','ICP/USDT','LTC/USDT','ADA/USDT','TRX/USDT','XAUT/USDT','BTC/USDT']

print("\n{'='*70}")
print("تحليل العملات: سعر الدخول vs السعر الحالي")
print("="*70)

for c in coins:
    try:
        t = ex.fetch_ticker(c)
        current = t['last']
        change_24h = t.get('percentage', 0) or 0
        
        entry = trades.get(c, {}).get('entry', 0)
        exit_price = trades.get(c, {}).get('exit_price')
        exit_reason = trades.get(c, {}).get('exit_reason', '')
        
        if entry > 0:
            pct_from_entry = ((current - entry) / entry) * 100
        else:
            pct_from_entry = 0
            
        if exit_price and exit_price > 0:
            pct_after_exit = ((current - exit_price) / exit_price) * 100
        else:
            pct_after_exit = None
        
        status = "🟢 OPEN" if exit_reason == 'OPEN' else f"❌ CLOSED ({exit_reason})"
        
        print(f"\n{c}:")
        print(f"  دخول: ${entry:.6f}")
        if exit_price:
            print(f"  خروج: ${exit_price:.6f} ({exit_reason})")
        print(f"  الآن:  ${current:.6f} | 24h: {change_24h:+.2f}%")
        print(f"  من الدخول: {pct_from_entry:+.2f}%", end="")
        if pct_after_exit is not None:
            print(f" | بعد الخروج: {pct_after_exit:+.2f}%", end="")
        print()
        
        # تقييم
        if exit_reason == 'STOP_LOSS' and pct_from_entry > 0:
            print(f"  ⚠️  ضرب SL ثم ارتد! خسرنا وهي الآن {pct_from_entry:+.2f}% من دخولنا")
        elif exit_reason == 'BREAK_EVEN_STOP' and pct_from_entry > 2:
            print(f"  💡 خرجنا مبكراً! لو بقينا كان ربحنا {pct_from_entry:+.2f}% بدلاً من الربح الصغير")
        elif exit_reason == 'OPEN':
            print(f"  📊 صفقة مفتوحة حالياً")
            
    except Exception as e:
        print(f"{c}: خطأ - {e}")
