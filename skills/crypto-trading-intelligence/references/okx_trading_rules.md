# قواعد التداول على OKX

## الحدود الدنيا للصفقات

| نوع الصفقة | الحد الأدنى | ملاحظة |
|-----------|-----------|--------|
| Spot USDT | $10 | minimum order amount |
| Futures USDT | $5 | حسب العقد |
| الحد الموصى به | $10.50 | لتجنب رسالة الخطأ |

## رسوم التداول

| المستوى | Maker | Taker |
|---------|-------|-------|
| VIP 0 (افتراضي) | 0.08% | 0.10% |
| VIP 1 | 0.07% | 0.09% |
| VIP 2 | 0.06% | 0.08% |

**ملاحظة**: احسب الرسوم في TP/SL:
```python
# تكلفة الدخول + الخروج
total_fees = position_size * (0.001 + 0.001)  # 0.2% إجمالي
# يجب أن يكون TP1 > entry * (1 + 0.002 + profit_target)
```

## رموز الأزواج

```python
# Spot
symbol_spot = "BTC-USDT"   # تنسيق OKX للـ Spot

# Futures Perpetual
symbol_futures = "BTC-USDT-SWAP"  # تنسيق OKX للـ Futures

# تحويل من تنسيق عام
def to_okx_spot(symbol):
    return symbol.replace('/', '-')  # BTC/USDT → BTC-USDT

def to_okx_futures(symbol):
    base = symbol.replace('/USDT', '').replace('USDT', '')
    return f"{base}-USDT-SWAP"
```

## حدود الرافعة المالية

| القطاع | الرافعة الموصى بها | الحد الأقصى |
|--------|------------------|------------|
| BTC/ETH | 5x-10x | 100x |
| Altcoins كبيرة | 3x-5x | 50x |
| Altcoins صغيرة | 2x-3x | 20x |
| Meme | لا Futures | — |

## API Endpoints المهمة

```python
BASE_URL = "https://www.okx.com"

# الأسعار والبيانات
GET /api/v5/market/ticker?instId=BTC-USDT
GET /api/v5/market/books?instId=BTC-USDT&sz=400
GET /api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=200

# الرصيد والمراكز
GET /api/v5/account/balance
GET /api/v5/account/positions

# الأوامر
POST /api/v5/trade/order
POST /api/v5/trade/cancel-order
```

## أخطاء شائعة وحلولها

| الخطأ | السبب | الحل |
|-------|-------|------|
| `minimum order amount` | الصفقة < $10 | رفع الحد الأدنى إلى $10.50 |
| `Insufficient balance` | رصيد غير كافٍ | فحص الرصيد المتاح فعلياً |
| `Order size too small` | حجم العملة صغير جداً | حساب الحجم بدقة أكبر |
| `Rate limit exceeded` | طلبات كثيرة | إضافة sleep(0.1) بين الطلبات |

## إعدادات البوت الموصى بها

```python
# config.py
TOTAL_CAPITAL = 300          # رأس المال الكلي بـ USDT
MAX_SPOT_TRADES = 5          # أقصى صفقات Spot متزامنة
MAX_FUTURES_TRADES = 3       # أقصى صفقات Futures متزامنة
RISK_PER_TRADE = 0.03        # 3% مخاطرة لكل صفقة
MIN_CONFIDENCE = 60          # حد الثقة الأدنى للدخول
CHECK_INTERVAL = 60          # فحص كل 60 ثانية
MIN_ORDER_AMOUNT = 10.5      # الحد الأدنى للصفقة
MAX_DAILY_DRAWDOWN = 0.08    # 8% خسارة يومية → إيقاف
```
