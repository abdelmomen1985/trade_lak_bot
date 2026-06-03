---
name: crypto-trading-intelligence
description: |
  منهجية متكاملة لدراسة سوق العملات الرقمية، تتبع محافظ الحيتان، واتخاذ قرارات التداول الذكي.
  استخدم هذه المهارة عند: تحليل فرص التداول في Spot/Futures، تتبع تدفق السيولة بين القطاعات،
  اكتشاف تحركات الحيتان وتأثيرها على السوق، بناء أو تحسين بوتات التداول الآلي،
  تقييم صفقة مفتوحة وقرار الخروج المبكر، أو تدريب نماذج ML على بيانات التداول.
  مبنية على خبرة فعلية من بوت Trade Lak v4 على منصة OKX.
---

# Crypto Trading Intelligence Skill

منهجية شاملة مستخلصة من تجربة فعلية في بناء وتشغيل بوت تداول ذكي على OKX.

---

## الاستراتيجية الأساسية: دعم + كسر كاذب + تأكيد (Fake Break)

> **هذه هي استراتيجية Trade Lak الجوهرية — تحتل 30% من وزن القرار**

السوق يتحرك بالسيولة. الحيتان يصطادون وقف خسارة الصغار قبل الحركة الحقيقية. الاستراتيجية تنتظر هذا الاصطياد (Liquidity Grab) ثم تدخل بعده مباشرة.

### الخطوات السبع

| الخطوة | الوصف | المعيار |
|--------|-------|--------|
| **1. تحديد الاتجاه** | 4H/1H: قمم وقيعان صاعدة = شراء فقط | EMA20 + Swing Analysis |
| **2. رسم منطقة S/R** | منطقة (0.8% عرض) وليس خط | آخر 50 شمعة |
| **3. انتظار Liquidity Grab** | اختراق 0.1%-2.5% ثم عودة سريعة | FAKE_BREAK_MIN/MAX_PCT |
| **4. تأكيد الشمعة** | Pin Bar أو Engulfing أو إغلاق قوي 60%+ | TAIL_RATIO ≥ 1.5 |
| **5. الدخول** | بعد إغلاق شمعة التأكيد فقط | entry = close[-1] |
| **6. وقف الخسارة** | خلف الذيل + 0.3% مسافة أمان | stop = grab_low × 0.997 |
| **7. الأهداف الثلاثة** | TP1=30%, TP2=60%, TP3=قمة سابقة | أخذ أرباح تدريجي |

### القواعد الذهبية للاستراتيجية

> **لا تدخل أول ما يصل السعر للمنطقة — انتظر حتى يفضح نفسه**

> **الكسر الكاذب المثالي: 0.3% إلى 1.5% تحت الدعم ثم عودة سريعة**

> **قوة المنطقة = عدد مرات الارتداد (3 مرات = قوية جداً)**

### الكود المُطبَّق في البوت
```python
# core/fake_break_detector.py
from core.fake_break_detector import FakeBreakDetector
detector = FakeBreakDetector()
result = detector.analyze(ohlcv_data)
# result['signal']: 1=شراء, -1=بيع, 0=انتظار
# result['fake_break_detected']: True/False
# result['confidence']: 0-100%
# result['entry_price'], result['stop_loss'], result['tp1/tp2/tp3']
```

### توزيع الأوزان بعد دمج الاستراتيجية
```
fake_break:      30%  ← استراتيجيتك الأساسية (الأعلى وزناً)
ml_model:        18%
multi_strategy:  18%
onchain:         14%
orderbook:       10%
coinglass:        5%
wick_detection:   3%
news_sentiment:   2%
```

---

## المنهجية الأساسية: هرم القرار

```
المستوى 1 — حالة السوق الكلية (BTC Dominance + Fear&Greed)
    ↓
المستوى 2 — تدفق السيولة بين القطاعات (Sector Rotation)
    ↓
المستوى 3 — اختيار العملة الأقوى في القطاع الأقوى
    ↓
المستوى 4 — تأكيد الإشارة (Order Book + Volume + OI + Funding)
    ↓
المستوى 5 — إدارة المخاطر (حجم المركز + SL/TP ديناميكي)
    ↓
المستوى 6 — مراقبة ما بعد الدخول (Post-Entry Liquidity Monitor)
```

---

## 1. دراسة حالة السوق الكلية

### مؤشرات إلزامية قبل أي صفقة

| المؤشر | المصدر | الدلالة |
|--------|--------|----------|
| BTC Dominance | CoinGecko/CoinGlass | >55% = موسم BTC، <45% = موسم Altcoins |
| Fear & Greed Index | alternative.me | <25 = خوف شديد (فرصة شراء)، >75 = جشع (خطر) |
| BTC Funding Rate | CoinGlass | >0.01% = سوق محموم، <-0.01% = ضغط بيع |
| Global Open Interest | CoinGlass | ارتفاع OI + ارتفاع سعر = تأكيد اتجاه |
| Long/Short Ratio | CoinGlass | >70% Long = احتمال تصفية صعودية |

### قواعد حالة السوق
- **Bull Market**: BTC فوق MA200 + Fear&Greed > 50 → زيادة حجم المراكز
- **Bear Market**: BTC تحت MA200 → Spot فقط، لا Futures Long
- **Sideways**: تداول نطاق، TP أقرب، SL أضيق

---

## 2. تحليل تدفق السيولة بين القطاعات (Sector Rotation)

### القطاعات الـ 12 وأهم عملاتها

| القطاع | العملات الرئيسية | علامات الانفجار |
|--------|-----------------|----------------|
| **Layer1** | ETH, SOL, ADA, AVAX, ICP | ارتفاع TVL + نشاط DApps |
| **Layer2** | ARB, OP, MATIC, ZKJ, STRK | ارتفاع المعاملات + Bridge Volume |
| **DeFi** | AAVE, UNI, CRV, COMP | ارتفاع TVL + Yield Farming |
| **Infrastructure** | LINK, LPT, GRT, API3 | طلب Data Feeds + Oracle |
| **Payments** | XRP, XLM, LTC, TRX | حجم تحويلات + شراكات |
| **Exchange** | BNB, OKB, CRO | حجم تداول + Buyback |
| **AI/Data** | FET, OCEAN, RNDR, TAO | نشاط GPU + AI Projects |
| **Gaming/NFT** | AXS, SAND, MANA, IMX | حجم NFT + DAU |
| **Privacy** | XMR, ZEC, DASH | طلب الخصوصية |
| **RWA/Staking** | CFG, ONDO, POLYX | ربط الأصول الحقيقية |
| **Meme** | DOGE, SHIB, PEPE | Sentiment + Social Volume |
| **BTC Ecosystem** | WBTC, STX, ORDI | BTC L2 Activity |

### كيفية تحديد القطاع الأقوى
```python
# نقاط القطاع = متوسط (تغير السعر 24h + تغير الحجم 24h + OI change)
sector_score = (price_change_24h * 0.4) + (volume_change_24h * 0.35) + (oi_change * 0.25)
# القطاع الفائز: أعلى نقاط مع حجم تداول > المتوسط بـ 1.5x
```

### مكافأة القطاع الأقوى (تُضاف لنقاط الثقة)
- القطاع الأول: +20% | القطاع الثاني: +12% | القطاع الثالث: +7%

---

## 3. تتبع محافظ الحيتان

### مؤشرات نشاط الحيتان

| المؤشر | الدلالة الإيجابية | الدلالة السلبية |
|--------|-----------------|----------------|
| **Whale Accumulation** | تراكم تدريجي على مدى أيام | بيع مفاجئ بعد ارتفاع |
| **Large Order Walls** | جدار شراء كبير في Order Book | جدار بيع يمنع الاختراق |
| **Exchange Inflow** | — | تحويل للبورصة = نية بيع |
| **Exchange Outflow** | تحويل للمحفظة الباردة = احتفاظ | — |
| **Funding Rate Divergence** | Funding سلبي + سعر يرتفع = حيتان تشتري Spot | Funding إيجابي جداً = حيتان تبيع للمضاربين |
| **OI Spike + Price Flat** | تراكم مراكز بهدوء | — |

### إشارة الحوت القوية (تستحق الدخول)
- تراكم Spot + Funding Rate سلبي (الحيتان تشتري بينما المضاربون يبيعون)
- جدار شراء كبير في Order Book (دعم قوي)
- Exchange Outflow مرتفع (سحب من البورصات = احتفاظ)

---

## 4. نظام نقاط الإشارة (يجب ≥ 60 للدخول)

```
Order Book Analysis     → 0-25 نقطة
  Bid/Ask Ratio > 1.5   → +15 | جدار شراء كبير → +10

Volume Analysis         → 0-20 نقطة
  Volume > MA(20)*1.5   → +15 | Volume Trend صاعد → +5

Technical Analysis      → 0-20 نقطة
  RSI 40-60 (مثالي)     → +10 | فوق MA50 + MA200 → +10

CoinGlass Signals       → 0-20 نقطة
  OI ارتفع مع السعر     → +10 | Long/Short > 55% → +5 | Funding طبيعي → +5

Sector Score            → 0-15 نقطة
  قطاع أول → +15 | قطاع ثانٍ → +10 | قطاع ثالث → +7

ML Model Confidence     → 0-20 نقطة
  RF + GB > 65%         → +20 | RF + GB > 55% → +10
```

**حدود الثقة**: ≥75% → حجم 5% | 65-74% → حجم 3% | 60-64% → حجم 2%

---

## 5. إدارة المخاطر

```python
# حجم المركز
risk_amount = total_capital * 0.03  # 3% مخاطرة قصوى
position_size = max(risk_amount / (entry_price * stop_loss_pct), 10.5)  # حد OKX الأدنى

# Stop Loss ديناميكي
SL_spot = entry * 0.97      # -3% للـ Spot
SL_futures = entry * 0.98   # -2% للـ Futures
# Break Even عند +0.15% → نقل SL للدخول
# Trailing Stop: يتبع السعر بفارق 2%

# Take Profit متعدد
TP1 = entry * 1.015   # +1.5% → إغلاق 30%
TP2 = entry * 1.03    # +3%   → إغلاق 40%
TP3 = entry * 1.06    # +6%   → إغلاق 30%
```

**قواعد المخاطر الكلية**: Max 5 Spot + 3 Futures | Max Drawdown يومي 8% → إيقاف

---

## 6. مراقبة ما بعد الدخول (Post-Entry Monitor)

| المؤشر | حد التحذير | حد الخروج المبكر |
|--------|-----------|------------------|
| Order Book Depth | انخفاض 20% | انخفاض 35% |
| Bid/Ask Ratio | < 0.55 | < 0.40 |
| Volume Momentum | انخفاض 25% | انخفاض 40% |
| Open Interest (1h) | انخفاض 1.5% | انخفاض 2.5% |
| Funding Rate | > 0.010% | > 0.015% |
| Price Momentum | شمعتان هابطتان | 3 شمعات هابطة |

```
نقاط ≤ -3 → EARLY_EXIT | نقاط ≤ -1 → TIGHTEN_SL (40%) | نقاط ≥ +2 → HOLD
```

---

## 7. أنماط الفشل الشائعة (تجنّبها)

| النمط | الوصف | الحل |
|-------|-------|------|
| **Wick Trap** | شمعة بفتيل طويل تجذب الدخول ثم تنعكس | Wick/Body Ratio > 2 = تجاهل |
| **Low Liquidity Pump** | ارتفاع سريع بحجم منخفض | Volume < MA(20) = لا دخول |
| **Correlation Trap** | دخول عملتين مترابطتين | Correlation > 0.7 = رفض الثانية |
| **Funding Squeeze** | Funding مرتفع يُنهك Long | Funding > 0.02% = لا Long Futures |
| **News Spike** | ارتفاع مفاجئ بسبب خبر | انتظار تأكيد 15 دقيقة |

---

## 8. تدريب نموذج ML

```python
features = [
    'rsi_14', 'macd_signal', 'bb_position', 'ema_cross', 'volume_ratio',
    'price_momentum_1h', 'price_momentum_4h',
    'bid_ask_ratio', 'ob_depth_change', 'large_order_presence',
    'oi_change_1h', 'funding_rate', 'long_short_ratio', 'liquidation_risk',
    'sector_rank', 'sector_score',
    'btc_dominance', 'fear_greed_index', 'market_regime'
]
# Target: 1 إذا وصلت TP1 قبل SL، وإلا 0
# نموذج: Random Forest + Gradient Boosting | Threshold: P(success) > 0.60
# تحديث أسبوعي على آخر 500 صفقة
```

---

## 9. ملفات السيرفر (164.68.112.131)

```
/root/trade_lak_bot/core/
├── sector_liquidity_hunter.py  ← محرك القطاعات
├── post_entry_monitor.py       ← مراقبة ما بعد الدخول
├── intelligence_engine.py      ← محرك القرار الرئيسي
├── market_scanner.py           ← فحص الفرص
└── advanced_risk_manager.py    ← إدارة المخاطر
```

```bash
# فحص حالة البوت
ssh root@164.68.112.131 "tail -50 /root/bot_log.txt"
# إعادة التشغيل
ssh root@164.68.112.131 "bash /root/start_bot.sh"
```

---

## 10. القواعد الذهبية

1. **السيولة أولاً**: حجم تداول يومي < $5M = تجاهل
2. **القطاع يقود العملة**: الأقوى في الأقوى دائماً يتفوق
3. **الحيتان لا تكذب**: Spot accumulation + Funding سلبي = فرصة ذهبية
4. **الخروج المبكر ربح**: تدهور السيولة بعد الدخول = اخرج قبل SL
5. **لا تحارب الاتجاه الكلي**: BTC تحت MA200 = لا Long Futures
6. **التنويع القطاعي**: لا أكثر من صفقتين في نفس القطاع
7. **ML + Order Book معاً**: ML وحده غير كافٍ، يجب تأكيد Order Book
8. **الحد الأدنى OKX**: $10.50 لكل صفقة

---

## الملفات المرجعية

- `references/sector_definitions.md` — تعريف كامل للقطاعات وعملاتها
- `references/okx_trading_rules.md` — قواعد OKX: الحدود الدنيا، الرسوم، الرافعة
- `references/whale_tracking_guide.md` — دليل تتبع الحيتان بالتفصيل
- `scripts/analyze_trade_history.py` — تحليل سجل الصفقات واستخراج الأنماط
- `scripts/sector_scanner.py` — فحص القطاعات وترتيبها
- `scripts/whale_alert_checker.py` — فحص نشاط الحيتان
