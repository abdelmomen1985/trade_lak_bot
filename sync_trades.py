"""
sync_trades.py — مزامنة active_trades.json مع الواقع الفعلي على OKX
يحذف جميع الصفقات القديمة ويُنشئ سجلاً جديداً بناءً على الأرصدة الفعلية
"""
import sys
sys.path.insert(0, '/root/trade_lak_bot')

import ccxt
import json
import time
from datetime import datetime

try:
    from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE

    exchange = ccxt.okx({
        'apiKey': OKX_API_KEY,
        'secret': OKX_SECRET_KEY,
        'password': OKX_PASSPHRASE,
    })

    print("=" * 60)
    print("  مزامنة active_trades.json مع OKX الفعلي")
    print("=" * 60)

    # جلب الرصيد الفعلي
    balance = exchange.fetch_balance()
    free_usdt = balance['free'].get('USDT', 0)
    total_usdt = balance['total'].get('USDT', 0)

    print(f"\nRصيد USDT الحر: ${free_usdt:.2f}")
    print(f"رصيد USDT الكلي: ${total_usdt:.2f}")

    # إيجاد العملات الفعلية المحتفظ بها (غير USDT)
    real_positions = {}
    spot_bal = balance.get('total', {})

    print("\nفحص الأرصدة الفعلية على OKX...")
    for coin, amt in spot_bal.items():
        if coin in ('USDT', 'USDC', 'BUSD', 'DAI') or not amt or float(amt) < 0.0001:
            continue
        try:
            ticker = exchange.fetch_ticker(coin + '/USDT')
            current_price = ticker['last']
            value = float(amt) * current_price
            if value > 0.5:  # تجاهل القيم الصغيرة جداً (غبار)
                real_positions[coin] = {
                    'amount': float(amt),
                    'current_price': current_price,
                    'value_usdt': value
                }
                print(f"  ✅ {coin}: {float(amt):.6g} وحدة @ ${current_price:.6g} = ${value:.2f}")
        except Exception as e:
            print(f"  ⚠️ {coin}: خطأ في جلب السعر — {e}")

    if not real_positions:
        print("  لا توجد مراكز مفتوحة على OKX")

    # قراءة الملف القديم للاحتفاظ بمعلومات الدخول
    old_trades = {}
    try:
        with open('/root/trade_lak_bot/data/active_trades.json') as f:
            old_trades = json.load(f)
        print(f"\nالملف القديم: {len(old_trades)} صفقة مسجلة")
    except:
        print("\nلا يوجد ملف قديم")

    # بناء الملف الجديد بناءً على الواقع الفعلي
    new_trades = {}
    now_ts = time.time()

    for coin, pos_data in real_positions.items():
        symbol = coin + '/USDT'
        current_price = pos_data['current_price']
        amount = pos_data['amount']
        value = pos_data['value_usdt']

        # البحث عن بيانات الدخول في الملف القديم
        entry_price = current_price  # افتراضي: السعر الحالي
        sl = current_price * 0.95    # SL افتراضي 5%
        targets = [
            current_price * 1.03,
            current_price * 1.06,
            current_price * 1.09
        ]
        open_time = now_ts
        trade_id = None

        # البحث في الصفقات القديمة عن نفس العملة
        for tid, t in old_trades.items():
            if t.get('symbol', '') == symbol and t.get('status', 'open') == 'open':
                entry_price = t.get('entry_price', current_price)
                sl = t.get('stop_loss', current_price * 0.95)
                targets = t.get('targets', targets)
                open_time = t.get('open_time', now_ts)
                trade_id = tid
                break

        # إنشاء سجل الصفقة
        tid_new = trade_id if trade_id else f"sync_{coin.lower()}_{int(now_ts)}"
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        new_trades[tid_new] = {
            "symbol": symbol,
            "direction": "SPOT_BUY",
            "entry_price": entry_price,
            "stop_loss": sl,
            "targets": targets,
            "size": amount,
            "capital_used": value,
            "status": "open",
            "open_time": open_time,
            "synced_at": now_ts,
            "current_price_at_sync": current_price,
            "pnl_pct_at_sync": round(pnl_pct, 2)
        }

        status = "ربح" if pnl_pct > 0 else "خسارة"
        print(f"\n  ✅ {symbol}: دخول=${entry_price:.6g} | الآن=${current_price:.6g} | PnL={pnl_pct:+.2f}% ({status})")
        print(f"     SL=${sl:.6g} | TP1=${targets[0]:.6g} | TP2=${targets[1]:.6g} | TP3=${targets[2]:.6g}")

    # حفظ النسخة الاحتياطية من الملف القديم
    backup_path = f'/root/trade_lak_bot/data/active_trades_backup_{int(now_ts)}.json'
    with open(backup_path, 'w') as f:
        json.dump(old_trades, f, indent=2, ensure_ascii=False)
    print(f"\n💾 نسخة احتياطية محفوظة: {backup_path}")

    # كتابة الملف الجديد
    with open('/root/trade_lak_bot/data/active_trades.json', 'w') as f:
        json.dump(new_trades, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"✅ تمت المزامنة بنجاح!")
    print(f"   الصفقات القديمة: {len(old_trades)}")
    print(f"   الصفقات الفعلية الجديدة: {len(new_trades)}")
    print(f"   رصيد USDT الحر للتداول: ${free_usdt:.2f}")
    print(f"{'=' * 60}")

    if len(new_trades) == 0:
        print("\n🟢 لا توجد صفقات مفتوحة — البوت جاهز للتداول الجديد!")
        print("   عند تغيير PAUSE_NEW_TRADES=False سيبدأ البوت فوراً")

except Exception as e:
    print(f"خطأ: {e}")
    import traceback
    traceback.print_exc()
