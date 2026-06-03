import sys
sys.path.insert(0, '/root/trade_lak_bot')
import ccxt
import json
from datetime import datetime

try:
    from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE
    exchange = ccxt.okx({
        'apiKey': OKX_API_KEY,
        'secret': OKX_SECRET_KEY,
        'password': OKX_PASSPHRASE,
    })

    # جلب الرصيد الفعلي
    balance = exchange.fetch_balance()
    free_usdt = balance['free'].get('USDT', 0)
    total_usdt = balance['total'].get('USDT', 0)

    print(f"USDT حر: ${free_usdt:.2f}")
    print(f"USDT كلي: ${total_usdt:.2f}")
    print()

    # جلب المراكز المفتوحة
    positions = []
    spot_bal = balance.get('total', {})
    for coin, amt in spot_bal.items():
        if coin not in ('USDT', 'USDC') and amt and float(amt) > 0.0001:
            try:
                ticker = exchange.fetch_ticker(coin + '/USDT')
                current_price = ticker['last']
                value = float(amt) * current_price
                if value > 1.0:  # تجاهل القيم الصغيرة جداً
                    positions.append({
                        'symbol': coin + '/USDT',
                        'amount': float(amt),
                        'current_price': current_price,
                        'value_usdt': value
                    })
            except Exception as e:
                pass

    print("=== المراكز المفتوحة الفعلية على OKX ===")
    if positions:
        for p in positions:
            print(f"  {p['symbol']}: {p['amount']:.6g} وحدة @ ${p['current_price']:.6g} = ${p['value_usdt']:.2f}")
    else:
        print("  لا توجد مراكز مفتوحة على OKX")

    print()

    # قراءة ملف الصفقات النشطة
    try:
        with open('/root/trade_lak_bot/data/active_trades.json') as f:
            trades = json.load(f)

        print(f"=== صفقات البوت النشطة: {len(trades)} صفقة ===")
        for tid, t in trades.items():
            sym = t.get('symbol', '')
            entry = t.get('entry_price', 0)
            sl = t.get('stop_loss', 0)
            targets = t.get('targets', [])
            open_ts = t.get('open_time', 0)
            open_dt = datetime.fromtimestamp(open_ts).strftime('%Y-%m-%d %H:%M') if open_ts else 'N/A'

            # جلب السعر الحالي
            try:
                ticker = exchange.fetch_ticker(sym)
                current = ticker['last']
                pnl_pct = ((current - entry) / entry) * 100
                # حساب المسافة للهدف الأول
                tp1 = targets[0] if targets else 0
                dist_to_tp1 = ((tp1 - current) / current) * 100 if tp1 else 0
            except:
                current = 0
                pnl_pct = 0
                dist_to_tp1 = 0

            status = "ربح" if pnl_pct > 0 else "خسارة"
            print(f"\n  [{tid[:8]}] {sym}")
            print(f"    دخول: {entry:.6g} | الآن: {current:.6g} | PnL: {pnl_pct:+.2f}% ({status})")
            print(f"    SL: {sl:.6g} | TP1: {targets[0]:.6g} | TP2: {targets[1]:.6g} | TP3: {targets[2]:.6g}" if len(targets) >= 3 else f"    SL: {sl:.6g}")
            print(f"    مسافة للهدف الأول: {dist_to_tp1:+.2f}%")
            print(f"    فُتحت: {open_dt}")
    except Exception as e:
        print(f"خطأ في قراءة الصفقات: {e}")

except Exception as e:
    print(f"خطأ: {e}")
    import traceback
    traceback.print_exc()
