#!/usr/bin/env python3
"""
Market Opportunity Scanner
يحلل الأخبار الحالية + بيانات السوق + ويرسل التوصيات على Telegram
"""
import sys
import os
import time
import logging
import requests
try:
    from coinglass_pro_engine import analyze_pro as cg_analyze_pro
    CG_PRO_AVAILABLE = True
except ImportError:
    CG_PRO_AVAILABLE = False
import json

# Global tracker for no-opportunity alerts
_no_opp_tracker = {}
from datetime import datetime

sys.path.insert(0, '/root/trade_lak_bot')

logging.basicConfig(level=logging.WARNING)
# ─── AI Enhancement (FinBERT + Fear&Greed + LSTM + Crash Detection) ───────────
try:
    sys.path.insert(0, '/root/trade_lak_bot/core')
    from ai_enhancement_patch import get_ai_boost, get_fear_greed_text, get_market_warning
    AI_ENHANCEMENT_AVAILABLE = True
    print("[Scanner] ✅ AI Enhancement loaded!")
except Exception as _ai_e:
    AI_ENHANCEMENT_AVAILABLE = False
    print(f"[Scanner] ⚠️ AI Enhancement unavailable: {_ai_e}")
    def get_ai_boost(*args, **kwargs): return 0, {}
    def get_fear_greed_text(): return ""
    def get_market_warning(*args): return ""
# ──────────────────────────────────────────────────────────────────────────────


# ─── Config ───────────────────────────────────────────────────────────────────
# Direct config values
TELEGRAM_TOKEN = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
CHAT_ID        = "6633826689"
CRYPTOPANIC_API_KEY = "afed90b669cebc6535f88540ecb1679ee551facc"
COINGLASS_API_KEY   = "eaf8efd7876142b0bac70affb6f65f2a"

# ─── Helpers ──────────────────────────────────────────────────────────────────
def send_telegram(text: str):
    """Disabled — log only. Liquidity channel reserved for accumulation alerts."""
    import logging as _lg
    _lg.getLogger(__name__).info(f"[scanner log-only] {str(text)[:150]}")

def normalize_ohlcv(raw):
    if not raw:
        return []
    if isinstance(raw[0], dict):
        return raw
    return [{'timestamp': c[0], 'open': float(c[1]), 'high': float(c[2]),
             'low': float(c[3]), 'close': float(c[4]),
             'volume': float(c[5]) if len(c) > 5 else 0.0} for c in raw]

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def calc_ema(closes, period):
    if len(closes) < period:
        return closes[-1] if closes else 0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for p in closes[period:]:
        ema = p * k + ema * (1 - k)
    return ema

def detect_strategy(ohlcv, rsi, funding_rate, long_liq, short_liq, news_sentiment):
    """يحدد الاستراتيجية المناسبة بناءً على المؤشرات"""
    closes = [c['close'] for c in ohlcv]
    highs  = [c['high']  for c in ohlcv]
    lows   = [c['low']   for c in ohlcv]
    vols   = [c['volume'] for c in ohlcv]

    current = closes[-1]
    ema20   = calc_ema(closes, 20)
    ema50   = calc_ema(closes, 50)
    avg_vol = sum(vols[-20:]) / 20 if len(vols) >= 20 else vols[-1]
    vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 1

    # ATR
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
           for i in range(1, len(closes))]
    atr = sum(trs[-14:]) / 14 if len(trs) >= 14 else current * 0.02

    strategies = []
    score = 0
    reasons = []

    # ── 1. Oversold Bounce (RSI < 35 + EMA صاعد) ──────────────────────────
    if rsi < 35 and ema20 > ema50 * 0.995:
        strategies.append("📈 Oversold Bounce")
        score += 25
        reasons.append(f"RSI={rsi} منخفض جداً مع اتجاه صاعد")

    # ── 2. Momentum Breakout (سعر فوق EMA20 + حجم مرتفع) ─────────────────
    if current > ema20 * 1.005 and vol_ratio > 1.5 and ema20 > ema50:
        strategies.append("🚀 Momentum Breakout")
        score += 30
        reasons.append(f"اختراق مع حجم {vol_ratio:.1f}x فوق المتوسط")

    # ── 3. Funding Rate Reversal (تمويل سلبي = فرصة Long) ─────────────────
    if funding_rate < -0.003:
        strategies.append("💰 Funding Rate Reversal")
        score += 20
        reasons.append(f"معدل تمويل سلبي {funding_rate:.4f}% = ضغط بيع زائد")

    # ── 4. Liquidation Cascade Recovery (تصفيات Long كبيرة) ───────────────
    if long_liq > 1_000_000:
        strategies.append("🔄 Liquidation Recovery")
        score += 20
        reasons.append(f"تصفيات Long ${long_liq/1e6:.1f}M = ضغط بيع منتهٍ")

    # ── 5. News Catalyst (أخبار إيجابية) ──────────────────────────────────
    if news_sentiment > 0.6:
        strategies.append("📰 News Catalyst")
        score += 15
        reasons.append("أخبار إيجابية قوية في السوق")
    elif news_sentiment < 0.3:
        score -= 10
        reasons.append("أخبار سلبية تضغط على السعر")

    # ── 6. Whale Accumulation (حجم ضخم + سعر ثابت) ────────────────────────
    if vol_ratio > 2.0 and abs(current - closes[-2]) / closes[-2] < 0.005:
        strategies.append("🐋 Whale Accumulation")
        score += 25
        reasons.append(f"حجم {vol_ratio:.1f}x مع سعر ثابت = تراكم الحيتان")

    # ── 7. Trend Following (EMA20 > EMA50 + RSI 45-65) ────────────────────
    if ema20 > ema50 and 45 <= rsi <= 65 and current > ema20:
        strategies.append("📊 Trend Following")
        score += 20
        reasons.append("اتجاه صاعد واضح مع RSI صحي")

    return strategies, score, reasons, atr, ema20, ema50

# ─── Main Scanner ─────────────────────────────────────────────────────────────
def main():
    print("🔍 جاري تحليل السوق...")

    # 1. جلب أخبار CryptoPanic
    print("📰 جلب الأخبار...")
    news_scores = {}
    try:
        r = requests.get(
            f"https://cryptopanic.com/api/growth/v2/posts/",
            params={"auth_token": CRYPTOPANIC_API_KEY, "public": "true", "kind": "news"},
            timeout=15
        )
        if r.status_code == 200:
            posts = r.json().get("results", [])
            for post in posts[:30]:
                currencies = post.get("currencies", []) or []
                votes = post.get("votes", {}) or {}
                positive = votes.get("positive", 0) or 0
                negative = votes.get("negative", 0) or 0
                total = positive + negative
                sentiment = positive / total if total > 0 else 0.5
                for cur in currencies:
                    code = cur.get("code", "").upper()
                    if code:
                        if code not in news_scores:
                            news_scores[code] = []
                        news_scores[code].append(sentiment)
    except Exception as e:
        print(f"⚠️ CryptoPanic: {e}")

    # 2. جلب بيانات OKX
    print("📊 جلب بيانات السوق من OKX...")
    from core.okx_client import OKXClient
    okx = OKXClient()

    # قائمة العملات للتحليل
    symbols = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT",
        "BNB/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT",
        "LINK/USDT", "DOT/USDT", "MATIC/USDT", "ATOM/USDT",
        "LTC/USDT", "UNI/USDT", "NEAR/USDT", "FIL/USDT",
        "INJ/USDT", "SUI/USDT", "TIA/USDT", "ARB/USDT"
    ]

    # 3. جلب بيانات CoinGlass Pro (محرك محسّن)
    print("💎 جلب بيانات CoinGlass Pro...")
    coinglass_data = {}
    cg_pro_cache = {}  # cache للتحليل الكامل
    if CG_PRO_AVAILABLE:
        for sym in ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "DOT"]:
            try:
                pro_result = cg_analyze_pro(sym)
                cg_pro_cache[sym] = pro_result
                # استخراج البيانات للتوافق مع الكود القديم
                market = pro_result.get("market", {})
                whale = pro_result.get("whale", {})
                coinglass_data[sym] = {
                    "funding_rate": market.get("funding_rate", 0.0),
                    "long_liq": whale.get("whale_long_vol", 0.0),
                    "short_liq": whale.get("whale_short_vol", 0.0),
                    "ls_ratio_1h": market.get("ls_ratio_1h", 1.0),
                    "oi_change_1h": market.get("oi_change_1h", 0.0),
                    "oi_change_4h": market.get("oi_change_4h", 0.0),
                    "cg_signal": pro_result.get("signal", "NEUTRAL"),
                    "cg_score": pro_result.get("score", 0),
                    "confidence_boost": pro_result.get("confidence_boost", 0),
                    "cg_reasons": pro_result.get("reasons", []),
                }
            except Exception as e:
                print(f"⚠️ CG Pro error for {sym}: {e}")
    else:
        # Fallback للكود القديم
        cg_headers = {"CG-API-KEY": COINGLASS_API_KEY}
        cg_base = "https://open-api-v4.coinglass.com"
        for sym in ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"]:
            try:
                r = requests.get(f"{cg_base}/api/futures/liquidation/order",
                               params={"symbol": sym, "limit": 50}, headers=cg_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if str(data.get("code")) == "0":
                        orders = data.get("data", [])
                        long_liq = sum(float(o.get("usd_value", 0)) for o in orders if o.get("side") == 1)
                        short_liq = sum(float(o.get("usd_value", 0)) for o in orders if o.get("side") == 0)
                        coinglass_data.setdefault(sym, {})["long_liq"] = long_liq
                        coinglass_data.setdefault(sym, {})["short_liq"] = short_liq
            except:
                pass
    # 4. تحليل كل عملة
    print("🧠 تحليل الفرص...")
    opportunities = []

    for symbol in symbols:
        try:
            base = symbol.split("/")[0]

            # جلب OHLCV
            raw_ohlcv = okx.get_ohlcv(symbol, "1h", 100)
            if not raw_ohlcv or len(raw_ohlcv) < 50:
                continue
            ohlcv = normalize_ohlcv(raw_ohlcv)

            closes = [c['close'] for c in ohlcv]
            current_price = closes[-1]

            # RSI
            rsi = calc_rsi(closes)

            # CoinGlass data
            cg = coinglass_data.get(base, {})
            funding_rate = cg.get("funding_rate", 0.0)
            long_liq     = cg.get("long_liq", 0.0)
            short_liq    = cg.get("short_liq", 0.0)
            cg_confidence_boost = cg.get("confidence_boost", 0)
            cg_signal    = cg.get("cg_signal", "NEUTRAL")
            cg_reasons   = cg.get("cg_reasons", [])

            # News sentiment
            news_list = news_scores.get(base, [])
            news_sentiment = sum(news_list) / len(news_list) if news_list else 0.5

            # تحديد الاستراتيجية
            strategies, score, reasons, atr, ema20, ema50 = detect_strategy(
                ohlcv, rsi, funding_rate, long_liq, short_liq, news_sentiment
            )

            # إضافة CoinGlass Pro boost
            if cg_confidence_boost > 0 and cg_signal in ("BUY", "STRONG_BUY", "WEAK_BUY"):
                score += cg_confidence_boost
            elif cg_confidence_boost > 0 and cg_signal in ("SELL", "STRONG_SELL", "WEAK_SELL"):
                score -= cg_confidence_boost // 2  # تخفيض أقل لأننا نبحث عن Long فقط

            if score >= 25 and strategies:
                # حساب مستويات التداول
                entry1 = round(current_price * 0.999, 6)
                entry2 = round(current_price * 0.995, 6)
                # ===== حساب ذكي للأهداف بناءً على قوة الزخم والسيولة =====
                vols_5   = [c['volume'] for c in ohlcv[-5:]]
                vols_20  = [c['volume'] for c in ohlcv[-20:-5]]
                avg_vol_5  = sum(vols_5)  / len(vols_5)  if vols_5  else 1
                avg_vol_20 = sum(vols_20) / len(vols_20) if vols_20 else 1
                vol_spike  = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0
                atr_pct = (atr / current_price) * 100 if current_price > 0 else 1.0
                # مضاعف الحجم
                if vol_spike >= 5.0:   vol_mult = 4.0
                elif vol_spike >= 3.0: vol_mult = 3.0
                elif vol_spike >= 2.0: vol_mult = 2.0
                elif vol_spike >= 1.5: vol_mult = 1.5
                else:                  vol_mult = 1.0
                # مضاعف الاستراتيجيات الانفجارية
                explosive_strats = [s for s in strategies if any(
                    k in s.lower() for k in ['breakout','pump','whale','explosion']
                )]
                strat_mult   = 1.0 + (len(explosive_strats) * 0.5)
                funding_mult = 1.3 if funding_rate < -0.005 else 1.0
                liq_mult     = 1.4 if short_liq > 2_000_000 else (1.2 if short_liq > 500_000 else 1.0)
                rsi_mult     = 1.2 if 30 <= rsi <= 50 else 1.0
                total_mult   = min(vol_mult * strat_mult * funding_mult * liq_mult * rsi_mult, 6.0)
                # حساب نسب الأهداف الذكية
                base_tp1_pct = max(2.0,  atr_pct * 1.2 * total_mult)
                base_tp2_pct = max(5.0,  atr_pct * 2.5 * total_mult)
                base_tp3_pct = max(10.0, atr_pct * 5.0 * total_mult)
                max_tp3 = 40.0 if ('BTC' in symbol or 'ETH' in symbol) else 120.0
                base_tp1_pct = min(base_tp1_pct, max_tp3 * 0.25)
                base_tp2_pct = min(base_tp2_pct, max_tp3 * 0.55)
                base_tp3_pct = min(base_tp3_pct, max_tp3)
                tp1 = round(current_price * (1 + base_tp1_pct / 100), 6)
                tp2 = round(current_price * (1 + base_tp2_pct / 100), 6)
                tp3 = round(current_price * (1 + base_tp3_pct / 100), 6)
                # ===== وقف خسارة ذكي يتفادى ذيول الشموع وتلاعب صناع السوق =====
                # 1. حساب أطول ذيل سفلي في آخر 20 شمعة
                lower_wicks = []
                for candle in ohlcv[-20:]:
                    body_low  = min(candle['open'], candle['close'])
                    wick_size = (body_low - candle['low']) / current_price * 100
                    lower_wicks.append(wick_size)
                max_wick_pct = max(lower_wicks) if lower_wicks else 0.5
                avg_wick_pct = sum(lower_wicks) / len(lower_wicks) if lower_wicks else 0.3
                # 2. حساب أدنى نقطة في آخر 10 شموع (دعم حقيقي)
                recent_lows  = [c['low'] for c in ohlcv[-10:]]
                support_low  = min(recent_lows)
                support_dist = (current_price - support_low) / current_price * 100
                # 3. ATR الحقيقي كنسبة مئوية (موسّع لتفادي الضوضاء)
                atr_sl_pct = atr_pct * 2.2
                # 4. هامش إضافي لتفادي تلاعب صناع السوق
                # يضاف 0.3% + نصف أطول ذيل كهامش أمان
                manipulation_buffer = 0.3 + (max_wick_pct * 0.5)
                # 5. اختيار أكبر قيمة بين: ATR / دعم حقيقي / ذيول الشموع
                sl_from_atr      = atr_sl_pct
                sl_from_support  = support_dist + manipulation_buffer
                sl_from_wicks    = max_wick_pct + avg_wick_pct + manipulation_buffer
                sl_pct_val = max(sl_from_atr, sl_from_support, sl_from_wicks)
                # 6. حدود: لا يقل عن 2% ولا يزيد عن 8%
                # (إذا كان TP1 أكبر من 15% نسمح بـ SL أكبر)
                sl_max = 8.0 if base_tp1_pct < 15.0 else 12.0
                sl_pct_val = max(2.0, min(sl_pct_val, sl_max))
                # 7. التأكد أن نسبة المخاطرة/الربح مقبولة (RR >= 1.5)
                rr_ratio = base_tp1_pct / sl_pct_val if sl_pct_val > 0 else 1.0
                if rr_ratio < 1.5:
                    sl_pct_val = base_tp1_pct / 1.5  # تعديل SL للحفاظ على RR
                    sl_pct_val = max(2.0, sl_pct_val)
                sl = round(current_price * (1 - sl_pct_val / 100), 6)
                sl_pct  = round(sl_pct_val, 2)
                tp1_pct = round(base_tp1_pct, 2)
                tp2_pct = round(base_tp2_pct, 2)
                tp3_pct = round(base_tp3_pct, 2)

                # نوع التداول
                trade_type = "FUTURES" if score >= 50 else "SPOT"
                if funding_rate < -0.005:
                    trade_type = "FUTURES"

                # نسبة النجاح - حساب متقدم بناءً على عوامل متعددة
                base_rate = 55
                # إضافة نقاط بناءً على عدد الاستراتيجيات المتوافقة
                base_rate += len(strategies) * 8
                # إضافة نقاط بناءً على RSI
                if 30 <= rsi <= 45:
                    base_rate += 12  # منطقة شراء مثالية
                elif 45 <= rsi <= 60:
                    base_rate += 8   # منطقة صحية
                # إضافة نقاط بناءً على حجم التداول
                vols_last = [c['volume'] for c in ohlcv[-5:]]
                vols_prev = [c['volume'] for c in ohlcv[-20:-5]]
                avg_prev = sum(vols_prev) / len(vols_prev) if vols_prev else 1
                avg_last = sum(vols_last) / len(vols_last) if vols_last else 1
                if avg_last > avg_prev * 1.5:
                    base_rate += 10  # حجم متزايد
                # إضافة نقاط بناءً على الأخبار
                if news_sentiment > 0.65:
                    base_rate += 8
                elif news_sentiment > 0.55:
                    base_rate += 4
                # إضافة نقاط بناءً على معدل التمويل
                if -0.01 < funding_rate < -0.002:
                    base_rate += 7  # تمويل سلبي = فرصة
                # إضافة نقاط بناءً على التصفيات
                if long_liq > 500_000:
                    base_rate += 5
                # ─── AI Enhancement Boost ───────────────────────────────
                if AI_ENHANCEMENT_AVAILABLE:
                    try:
                        # تحضير قائمة الأخبار للـ FinBERT
                        _news_for_ai = [{"title": t} for t in list(news_scores.get(base, []))]
                        # الحصول على تعزيز AI
                        _ai_boost, _ai_components = get_ai_boost(
                            symbol=symbol,
                            trade_direction="LONG",
                            news_list=_news_for_ai if _news_for_ai else None
                        )
                        base_rate += _ai_boost
                    except Exception as _e:
                        pass
                # ────────────────────────────────────────────────────────────
                success_rate = min(97, max(50, base_rate))

                opportunities.append({
                    "symbol": symbol,
                    "base": base,
                    "price": current_price,
                    "entry1": entry1,
                    "entry2": entry2,
                    "sl": sl,
                    "sl_pct": sl_pct,
                    "tp1": tp1, "tp1_pct": tp1_pct,
                    "tp2": tp2, "tp2_pct": tp2_pct,
                    "tp3": tp3, "tp3_pct": tp3_pct,
                    "rsi": rsi,
                    "strategies": strategies,
                    "score": score,
                    "reasons": reasons,
                    "trade_type": trade_type,
                    "success_rate": success_rate,
                    "rsi_label": (
                        "🔴 ذروة بيع" if rsi < 30 else
                        "🟢 منطقة شراء" if rsi < 40 else
                        "🟡 منطقة صحية" if rsi < 55 else
                        "🟠 اقتراب تشبع" if rsi < 70 else
                        "🔴 ذروة شراء — تحذير"
                    ),
                    "news_sentiment": news_sentiment,
                    "funding_rate": funding_rate,
                })

        except Exception as e:
            print(f"⚠️ {symbol}: {e}")
            continue

    # 5. ترتيب حسب الأفضل
    opportunities.sort(key=lambda x: x["success_rate"], reverse=True)
    top = [o for o in opportunities if o["success_rate"] >= 70][:5]

    if not top:
        # لا توجد فرص 70%+ - صمت ولا نرسل شيئاً
        # فقط نتتبع الوقت لإرسال تنبيه بعد ساعة كاملة
        _no_opp_tracker['count'] = _no_opp_tracker.get('count', 0) + 1
        _no_opp_tracker['last_alert'] = _no_opp_tracker.get('last_alert', 0)
        now_ts = time.time()
        # إذا مرت ساعة (3600 ثانية) بدون فرص، أرسل تنبيهاً واحداً
        if now_ts - _no_opp_tracker['last_alert'] >= 3600:
            send_telegram("\u23f3 \u0645\u0631\u0627\u0642\u0628\u0629 \u0627\u0644\u0633\u0648\u0642 \u062c\u0627\u0631\u064a\u0629...\n\u0644\u0645 \u062a\u064f\u0643\u062a\u0634\u0641 \u0641\u0631\u0635 70%+ \u062e\u0644\u0627\u0644 \u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u0645\u0627\u0636\u064a\u0629.\n\u0633\u064a\u0633\u062a\u0645\u0631 \u0627\u0644\u0628\u0648\u062a \u0628\u0627\u0644\u0645\u0631\u0627\u0642\u0628\u0629.")
            _no_opp_tracker['last_alert'] = now_ts
            _no_opp_tracker['count'] = 0
        print('لا توجد فرص 70%+ حالياً - صامت')
        return

    # 6. إرسال ملخص عام
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # إضافة Fear & Greed للملخص
    _fg_text = get_fear_greed_text() if AI_ENHANCEMENT_AVAILABLE else ""
    summary = f"""🔍 <b>تقرير الفرص الحالية — {now}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🧠 تم تحليل {len(symbols)} عملة
✅ فرص مكتشفة: {len(opportunities)}
🏆 أفضل {len(top)} فرص (نسبة نجاح ≥85%):

"""
    for i, opp in enumerate(top, 1):
        summary += f"{i}. <b>{opp['base']}</b> — نسبة نجاح: {opp['success_rate']}% | {' + '.join(opp['strategies'][:2])}\n"

    summary += "\n📊 التفاصيل الكاملة في الرسائل التالية..."
    # إضافة Fear & Greed للملخص إذا كان متاحاً
    if _fg_text:
        summary += f"\n\n{_fg_text}"
    disclaimer_s = chr(10) + chr(10) + '─' * 30 + chr(10)
    disclaimer_s += '⚠️ تنبيه: هذا تحليل فني آلي فقط، وليس نصيحة أو توصية بالمضاربة.'
    send_telegram(summary + disclaimer_s)
    time.sleep(1)

    # 7. إرسال تفاصيل كل فرصة
    for i, opp in enumerate(top, 1):
        sentiment_emoji = "🟢" if opp["news_sentiment"] > 0.6 else ("🔴" if opp["news_sentiment"] < 0.4 else "🟡")
        type_emoji = "⚡" if opp["trade_type"] == "FUTURES" else "💰"

        msg = f"""{'━'*30}
🎯 <b>فرصة #{i}: {opp['symbol']}</b>
{'━'*30}

💵 <b>السعر الحالي:</b> {opp['price']:,.6g}
📊 <b>RSI:</b> {opp['rsi']} {opp['rsi_label']} | {type_emoji} <b>نوع التداول:</b> {opp['trade_type']}

🎯 <b>نقاط الدخول:</b>
   • الدخول الأول:  {opp['entry1']:,.6g}
   • الدخول الثاني: {opp['entry2']:,.6g}

📈 <b>أهداف جني الأرباح:</b>
   • TP1: {opp['tp1']:,.6g} (+{opp['tp1_pct']}%)
   • TP2: {opp['tp2']:,.6g} (+{opp['tp2_pct']}%)
   • TP3: {opp['tp3']:,.6g} (+{opp['tp3_pct']}%)

🛑 <b>وقف الخسارة:</b> {opp['sl']:,.6g} (-{opp['sl_pct']}%)

🧠 <b>الاستراتيجيات:</b>
"""
        for s in opp['strategies']:
            msg += f"   • {s}\n"

        msg += f"""
📋 <b>الأسباب:</b>
"""
        # إضافة RSI كأول سبب دائماً
        rsi_val = opp['rsi']
        if rsi_val < 30:
            rsi_reason = f"RSI = {rsi_val:.1f} ← ذروة بيع قوية، فرصة انعكاس صعودي"
        elif rsi_val < 40:
            rsi_reason = f"RSI = {rsi_val:.1f} ← منطقة شراء مثالية، الزخم يتحول"
        elif rsi_val < 55:
            rsi_reason = f"RSI = {rsi_val:.1f} ← منطقة صحية، اتجاه صاعد مستمر"
        elif rsi_val < 70:
            rsi_reason = f"RSI = {rsi_val:.1f} ← يقترب من التشبع، راقب الأهداف"
        else:
            rsi_reason = f"RSI = {rsi_val:.1f} ← ذروة شراء، احتمال تصحيح قريب"
        msg += f"   📈 {rsi_reason}\n"
        for r in opp['reasons'][:3]:
            msg += f"   • {r}\n"

        if opp['funding_rate'] != 0:
            msg += f"\n💰 <b>معدل التمويل:</b> {opp['funding_rate']:.4f}%"

        msg += f"""
{sentiment_emoji} <b>معنويات الأخبار:</b> {'إيجابية' if opp['news_sentiment'] > 0.6 else ('سلبية' if opp['news_sentiment'] < 0.4 else 'محايدة')}

✅ <b>نسبة نجاح الصفقة:</b> {opp['success_rate']}%
⚠️ <i>هذا تحليل آلي — استخدم إدارة المخاطر دائماً</i>"""

        disclaimer = chr(10) + chr(10) + '─' * 30 + chr(10)
        disclaimer += '⚠️ تنبيه مهم: هذا تحليل فني آلي فقط، وليس نصيحة أو توصية بالمضاربة. التداول ينطوي على مخاطر عالية. تحمّل مسؤوليتك الكاملة قبل اتخاذ أي قرار.'
        send_telegram(msg + disclaimer)
        time.sleep(1.5)

    print(f"✅ تم إرسال {len(top)} فرصة على Telegram!")

if __name__ == "__main__":
    main()
