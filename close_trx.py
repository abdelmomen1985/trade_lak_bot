import sys
sys.path.insert(0, '/root/trade_lak_bot')
import ccxt
import json
import time
from datetime import datetime
from config.config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE

exchange = ccxt.okx({
    'apiKey': OKX_API_KEY,
    'secret': OKX_SECRET_KEY,
    'password': OKX_PASSPHRASE,
})

print("=" * 50)
print("  إغلاق صفقة TRX/USDT")
print("=" * 50)

try:
    # جلب الرصيد الحالي من TRX
    balance = exchange.fetch_balance()
    trx_amount = balance['free'].get('TRX', 0)
    trx_total  = balance['total'].get('TRX', 0)

    print(f"TRX حر: {trx_amount:.4f}")
    print(f"TRX كلي: {trx_total:.4f}")

    if trx_amount < 1:
        print("⚠️ لا يوجد TRX كافٍ للبيع")
        sys.exit(0)

    # جلب السعر الحالي
    ticker = exchange.fetch_ticker('TRX/USDT')
    current_price = ticker['last']
    value = trx_amount * current_price

    print(f"السعر الحالي: ${current_price:.6f}")
    print(f"القيمة الإجمالية: ${value:.2f}")
    print()

    # تنفيذ أمر البيع بالسوق
    print(f"جاري بيع {trx_amount:.4f} TRX بسعر السوق...")
    order = exchange.create_market_sell_order('TRX/USDT', trx_amount)

    print(f"✅ تم تنفيذ أمر البيع!")
    print(f"   معرف الأمر: {order.get('id', 'N/A')}")
    print(f"   الكمية: {order.get('amount', trx_amount):.4f} TRX")
    print(f"   الحالة: {order.get('status', 'N/A')}")

    # انتظار لحظة ثم التحقق من الرصيد
    time.sleep(3)
    balance_after = exchange.fetch_balance()
    usdt_after = balance_after['free'].get('USDT', 0)
    trx_after  = balance_after['free'].get('TRX', 0)

    print()
    print("=== الرصيد بعد الإغلاق ===")
    print(f"  USDT الحر: ${usdt_after:.2f}")
    print(f"  TRX المتبقي: {trx_after:.4f}")

    # تحديث active_trades.json — مسح TRX
    try:
        with open('/root/trade_lak_bot/data/active_trades.json') as f:
            trades = json.load(f)

        # حذف صفقة TRX
        to_remove = [tid for tid, t in trades.items() if 'TRX' in t.get('symbol', '')]
        for tid in to_remove:
            del trades[tid]
            print(f"  ✅ حُذفت صفقة TRX من السجل: {tid}")

        with open('/root/trade_lak_bot/data/active_trades.json', 'w') as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)

        print(f"  الصفقات المتبقية في السجل: {len(trades)}")
    except Exception as e:
        print(f"  ⚠️ خطأ في تحديث السجل: {e}")

    print()
    print("=" * 50)
    print(f"✅ صفقة TRX مُغلقة بنجاح!")
    print(f"   الرصيد الجاهز للتداول: ${usdt_after:.2f}")
    print("=" * 50)

except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()
