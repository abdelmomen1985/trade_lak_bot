#!/usr/bin/env python3
"""Trade Lak - Full Data Sources Diagnostic v3 (All APIs Fixed)"""
import sys, requests
sys.path.insert(0, '/root/trade_lak_bot')

from config.config import (
    OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE,
    COINGLASS_API_KEY, CRYPTOPANIC_API_KEY,
    BSCSCAN_API_KEY, ETHERSCAN_API_KEY
)
try:
    from config.config import CRYPTOPANIC_PLAN
except:
    CRYPTOPANIC_PLAN = "growth"

results = {}
print("\n" + "="*60)
print("   Trade Lak - Full Data Sources Diagnostic v3")
print("="*60)

# ── 1. OKX ────────────────────────────────────────────────────
print("\n[1] OKX - Price Data...")
btc_price = 0; eth_price = 0
try:
    import ccxt
    okx = ccxt.okx({'apiKey': OKX_API_KEY, 'secret': OKX_SECRET_KEY,
                    'password': OKX_PASSPHRASE, 'enableRateLimit': True})
    btc_ticker = okx.fetch_ticker('BTC/USDT')
    eth_ticker = okx.fetch_ticker('ETH/USDT')
    btc_price = btc_ticker['last']
    eth_price = eth_ticker['last']
    results['OKX'] = f"OK BTC=${btc_price:,.2f} | ETH=${eth_price:,.2f}"
    print(f"   ✅ BTC/USDT = ${btc_price:,.2f}")
    print(f"   ✅ ETH/USDT = ${eth_price:,.2f}")
except Exception as e:
    results['OKX'] = f"ERR {str(e)[:60]}"
    print(f"   ❌ {e}")

# ── 2. Coinglass ──────────────────────────────────────────────
print("\n[2] Coinglass Pro - Liquidity Data...")
funding_rate = 0; long_ratio = 50; short_ratio = 50
try:
    from core.coinglass_client import CoinGlassClient
    cg = CoinGlassClient()
    funding_rate = cg.get_funding_rate_v2('BTC') or 0
    ls = cg.get_long_short_ratio('BTC') or {}
    long_ratio  = ls.get('long', 0.5) * 100
    short_ratio = ls.get('short', 0.5) * 100
    results['Coinglass'] = f"OK Funding={funding_rate:.4f}% L/S={long_ratio:.1f}%/{short_ratio:.1f}%"
    print(f"   ✅ Funding Rate = {funding_rate:.4f}%")
    print(f"   ✅ Long/Short = {long_ratio:.1f}% / {short_ratio:.1f}%")
except Exception as e:
    results['Coinglass'] = f"ERR {str(e)[:60]}"
    print(f"   ❌ {e}")

# ── 3. Fear & Greed ───────────────────────────────────────────
print("\n[3] Fear & Greed Index...")
fg_value = 50; fg_label = "Neutral"
try:
    from core.fear_greed_engine import FearGreedEngine
    fg = FearGreedEngine()
    val = fg.get_current_index()
    fg_value = val.get("value", 50)
    fg_label = val.get("classification", "Neutral")
    results['Fear & Greed'] = f"OK {fg_value} - {fg_label}"
    print(f"   ✅ {fg_value} ({fg_label})")
except Exception as e:
    results['Fear & Greed'] = f"ERR {str(e)[:60]}"
    print(f"   ❌ {e}")

# ── 4. CryptoPanic (Growth Plan) ──────────────────────────────
print(f"\n[4] CryptoPanic ({CRYPTOPANIC_PLAN} plan) - News Sentiment...")
news_sentiment = 50; news_count = 0; latest_news = []
try:
    url = f"https://cryptopanic.com/api/{CRYPTOPANIC_PLAN}/v2/posts/"
    r = requests.get(url, params={
        "auth_token": CRYPTOPANIC_API_KEY,
        "public": "true",
        "currencies": "BTC,ETH,BNB",
        "filter": "hot"
        # Note: 'size' param is enterprise-only, removed
    }, timeout=12)
    if r.status_code == 200:
        posts = r.json().get("results", [])
        news_count = len(posts)
        bullish = sum(1 for p in posts
                      if p.get('votes', {}).get('positive', 0) > p.get('votes', {}).get('negative', 0))
        bearish = news_count - bullish
        news_sentiment = int((bullish / news_count * 100)) if news_count > 0 else 50
        sentiment_label = "BULLISH" if news_sentiment >= 60 else ("BEARISH" if news_sentiment <= 40 else "NEUTRAL")
        results['CryptoPanic'] = f"OK {news_count} news | {sentiment_label} {news_sentiment}%"
        print(f"   ✅ {news_count} news articles fetched")
        print(f"   ✅ Bullish={bullish} | Bearish={bearish} | Sentiment={news_sentiment}% ({sentiment_label})")
        for p in posts[:3]:
            title = p.get('title', '')[:65]
            votes = p.get('votes', {})
            pos = votes.get('positive', 0)
            neg = votes.get('negative', 0)
            icon = "📈" if pos > neg else ("📉" if neg > pos else "➡️")
            print(f"   {icon} {title}")
            latest_news.append(title)
    else:
        results['CryptoPanic'] = f"ERR HTTP {r.status_code}: {r.text[:60]}"
        print(f"   ❌ HTTP {r.status_code}: {r.text[:80]}")
except Exception as e:
    results['CryptoPanic'] = f"ERR {e}"
    print(f"   ❌ {e}")

# ── 5. EtherScan V2 - ETH On-Chain ───────────────────────────
print("\n[5] EtherScan V2 - ETH On-Chain Data...")
eth_supply = 0
try:
    r5 = requests.get("https://api.etherscan.io/v2/api", params={
        "chainid": "1",
        "module": "stats",
        "action": "ethsupply",
        "apikey": ETHERSCAN_API_KEY
    }, timeout=10)
    data5 = r5.json()
    if r5.status_code == 200 and data5.get("status") == "1":
        eth_supply = int(data5.get("result", 0)) / 1e18
        results['EtherScan (ETH)'] = f"OK ETH Supply={eth_supply:,.0f}"
        print(f"   ✅ ETH Supply = {eth_supply:,.0f} ETH")
    else:
        results['EtherScan (ETH)'] = f"WARN {data5.get('message','')}"
        print(f"   ⚠️ {data5.get('message','')}: {str(data5.get('result',''))[:60]}")
except Exception as e:
    results['EtherScan (ETH)'] = f"ERR {e}"
    print(f"   ❌ {e}")

# ── 6. EtherScan V2 - ETH Price ──────────────────────────────
print("\n[6] EtherScan V2 - ETH Price...")
try:
    r6 = requests.get("https://api.etherscan.io/v2/api", params={
        "chainid": "1",
        "module": "stats",
        "action": "ethprice",
        "apikey": ETHERSCAN_API_KEY
    }, timeout=10)
    data6 = r6.json()
    if r6.status_code == 200 and data6.get("status") == "1":
        eth_usd = data6.get("result", {}).get("ethusd", "?")
        btc_eth = data6.get("result", {}).get("ethbtc", "?")
        results['EtherScan (Price)'] = f"OK ETH=${eth_usd} | ETH/BTC={btc_eth}"
        print(f"   ✅ ETH/USD = ${eth_usd} | ETH/BTC = {btc_eth}")
    else:
        results['EtherScan (Price)'] = f"WARN {data6.get('message','')}"
        print(f"   ⚠️ {data6.get('message','')}")
except Exception as e:
    results['EtherScan (Price)'] = f"ERR {e}"
    print(f"   ❌ {e}")

# ── 7. BscScan - Note ─────────────────────────────────────────
print("\n[7] BscScan - Status...")
# BscScan V1 deprecated, V2 requires paid plan for BSC chain
# Using Etherscan V2 API for BSC data instead
results['BscScan'] = "INFO Using EtherScan V2 for BSC (BscScan V1 deprecated)"
print("   ℹ️  BscScan V1 deprecated. BSC data available via EtherScan V2 (paid plan needed for BSC chain)")
print("   ℹ️  Whale Tracker handles on-chain BSC/ETH monitoring independently")

# ── 8. Whale Tracker ──────────────────────────────────────────
print("\n[8] Whale Tracker...")
try:
    from core.whale_tracker import WhaleTracker
    wt = WhaleTracker()
    results['Whale Tracker'] = "OK loaded"
    print("   ✅ Whale Tracker loaded")
except Exception as e:
    results['Whale Tracker'] = f"ERR {e}"
    print(f"   ❌ {e}")

# ── SUMMARY ───────────────────────────────────────────────────
print("\n" + "="*60)
print("   FINAL SUMMARY:")
print("="*60)
ok_count = 0
for k, v in results.items():
    if v.startswith("OK"):
        icon = "✅"; ok_count += 1
    elif v.startswith("WARN"):
        icon = "⚠️"
    elif v.startswith("INFO"):
        icon = "ℹ️"
    else:
        icon = "❌"
    print(f"  {icon} {k:25s} → {v}")

print(f"\n  {ok_count}/{len([v for v in results.values() if not v.startswith('INFO')])} active sources")

# ── LIVE ANALYSIS ─────────────────────────────────────────────
print("\n" + "="*60)
print("   BTC/USDT LIVE ANALYSIS:")
print("="*60)
factors = []
signal = "NEUTRAL"
confidence = 0.5

# Funding Rate
if funding_rate < -0.01:
    factors.append(f"Funding Rate سلبي {funding_rate:.4f}% ← فرصة Long قوية")
    confidence += 0.1; signal = "BUY"
elif funding_rate > 0.05:
    factors.append(f"Funding Rate مرتفع {funding_rate:.4f}% ← ضغط على Long")
    confidence -= 0.05
else:
    factors.append(f"Funding Rate معتدل {funding_rate:.4f}% (محايد)")

# Long/Short Ratio
if short_ratio > 55:
    factors.append(f"أكثرية تراهن على الهبوط ({short_ratio:.1f}% Short) ← فرصة عكسية")
    confidence += 0.08
elif long_ratio > 60:
    factors.append(f"ازدحام في Long ({long_ratio:.1f}%) ← خطر تصفية")
    confidence -= 0.05
else:
    factors.append(f"Long/Short متوازن: {long_ratio:.1f}% / {short_ratio:.1f}%")

# Fear & Greed
if fg_value < 25:
    factors.append(f"خوف شديد ({fg_value}) ← أفضل وقت للشراء تاريخياً")
    confidence += 0.1; signal = "BUY"
elif fg_value < 40:
    factors.append(f"خوف في السوق ({fg_value}) ← فرصة محتملة")
    confidence += 0.05
elif fg_value > 75:
    factors.append(f"جشع مفرط ({fg_value}) ← خطر انعكاس")
    confidence -= 0.1
else:
    factors.append(f"السوق محايد ({fg_value})")

# News Sentiment
if news_count > 0:
    if news_sentiment >= 60:
        factors.append(f"الأخبار إيجابية ({news_sentiment}% bullish من {news_count} خبر)")
        confidence += 0.05
    elif news_sentiment <= 40:
        factors.append(f"الأخبار سلبية ({news_sentiment}% bullish من {news_count} خبر)")
        confidence -= 0.05
    else:
        factors.append(f"الأخبار محايدة ({news_sentiment}% من {news_count} خبر)")

conf_pct = min(95, max(30, int(confidence * 100)))

print(f"\n  💰 BTC: ${btc_price:,.2f}  |  ETH: ${eth_price:,.2f}")
print(f"  📊 الإشارة: {signal}")
print(f"  📈 الثقة: {conf_pct}%")
print(f"\n  🔍 العوامل:")
for f in factors:
    print(f"     ▪ {f}")

if latest_news:
    print(f"\n  📰 أحدث الأخبار:")
    for n in latest_news[:3]:
        print(f"     • {n}")

print("\n" + "="*60)
print("✅ التحليل اكتمل — البوت يعمل ويحلل البيانات")
print("="*60)
print("\n⚠️  تنبيه: هذا تحليل فني فقط وليس توصية استثمارية.")
print()
