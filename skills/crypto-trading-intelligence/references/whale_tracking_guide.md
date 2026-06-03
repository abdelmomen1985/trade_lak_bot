# دليل تتبع الحيتان الشامل

## تعريف الحوت
- محفظة تمتلك > 1% من العرض المتداول
- أو تُنفّذ صفقات > $500K في جلسة واحدة
- أو تُحرّك السعر > 0.5% بصفقة واحدة

---

## مصادر بيانات الحيتان

| المصدر | ما يوفره | الاستخدام |
|--------|---------|----------|
| **CoinGlass** | Exchange Inflow/Outflow, Liquidations | تتبع تدفق البورصات |
| **Whale Alert** | تحويلات كبيرة on-chain | تنبيهات فورية |
| **Nansen** | تصنيف المحافظ (Smart Money) | تحديد المحافظ الذكية |
| **Glassnode** | SOPR, NUPL, Exchange Balance | تحليل on-chain |
| **CryptoQuant** | Exchange Reserve, Miner Flow | تحليل عمق |

---

## أنماط الحيتان وتفسيرها

### نمط 1: التراكم الهادئ (Stealth Accumulation)
```
العلامات:
- OI يرتفع ببطء + السعر ثابت أو يتراجع قليلاً
- Funding Rate سلبي أو محايد
- Exchange Outflow مرتفع (سحب من البورصات)
- حجم تداول Spot أعلى من المتوسط

التفسير: الحيتان تشتري Spot بينما تُشجّع المضاربين على البيع
الإجراء: دخول Spot مع SL محكم
```

### نمط 2: جدار الشراء الوهمي (Spoofing)
```
العلامات:
- جدار شراء ضخم في Order Book يختفي عند الاقتراب
- السعر لا يرتفع رغم الجدار
- حجم منخفض

التفسير: تلاعب لجذب الشراء قبل البيع
الإجراء: تجاهل الإشارة، انتظار تأكيد حجم حقيقي
```

### نمط 3: الضخ والتفريغ (Pump & Dump)
```
العلامات:
- ارتفاع مفاجئ > 10% بحجم مرتفع جداً
- Funding Rate يرتفع بسرعة > 0.05%
- Social Volume ينفجر فجأة
- OI يرتفع بسرعة (مضاربون يدخلون)

التفسير: الحيتان تبيع للمضاربين المتأخرين
الإجراء: لا دخول، أو Short Futures بحذر
```

### نمط 4: التصفية المنظمة (Cascade Liquidation)
```
العلامات:
- انخفاض سريع > 5% خلال ساعة
- ارتفاع Liquidations على CoinGlass
- Long/Short Ratio ينخفض بسرعة

التفسير: تصفية مراكز Long، قد يكون قاع مؤقت
الإجراء: انتظار استقرار + Funding سلبي = فرصة شراء
```

---

## نظام نقاط الحوت (يُضاف لنقاط الإشارة)

```python
whale_score = 0

# Exchange Flow
if exchange_outflow_24h > exchange_outflow_avg * 1.5:
    whale_score += 15  # سحب كبير = احتفاظ
if exchange_inflow_24h > exchange_inflow_avg * 2.0:
    whale_score -= 20  # إيداع كبير = نية بيع

# Funding Rate
if funding_rate < -0.005:
    whale_score += 10  # حيتان تشتري Spot
elif funding_rate > 0.015:
    whale_score -= 15  # سوق محموم

# Order Book
if large_buy_wall_detected:
    whale_score += 10
if large_sell_wall_detected:
    whale_score -= 10

# OI vs Price
if oi_change_1h > 0.02 and price_change_1h > 0:
    whale_score += 8  # تراكم مع ارتفاع = إيجابي
elif oi_change_1h > 0.02 and price_change_1h < 0:
    whale_score -= 8  # تراكم مع هبوط = Short Squeeze محتمل
```

---

## أدوات التتبع العملية

### CoinGlass API
```python
# Exchange Inflow/Outflow
GET https://open-api.coinglass.com/public/v2/indicator/exchange_flows
params: {'symbol': 'BTC', 'interval': '1h'}

# Liquidations
GET https://open-api.coinglass.com/public/v2/indicator/liquidation_chart
params: {'symbol': 'BTC', 'interval': '1h'}
```

### OKX Order Book Analysis
```python
# الحصول على Order Book
GET https://www.okx.com/api/v5/market/books
params: {'instId': 'BTC-USDT', 'sz': '400'}

# تحليل الجدران
def detect_large_walls(bids, asks, threshold_multiplier=5):
    avg_bid_size = sum(b[1] for b in bids[:20]) / 20
    large_bids = [b for b in bids if b[1] > avg_bid_size * threshold_multiplier]
    return large_bids
```

---

## قواعد التداول مع الحيتان

1. **تابع الحوت، لا تحاربه**: إذا كانت الحيتان تشتري Spot، اشترِ معها
2. **الـ Funding سلبي = فرصة**: يعني الحيتان تشتري Spot بينما المضاربون يبيعون Futures
3. **جدار الشراء الحقيقي**: يبقى في Order Book لساعات، الوهمي يختفي خلال دقائق
4. **Exchange Outflow مستمر**: تراكم على مدى أيام = صعود قادم
5. **لا تدخل بعد الضخ**: إذا ارتفعت العملة > 15% خلال ساعة، انتظر التصحيح
