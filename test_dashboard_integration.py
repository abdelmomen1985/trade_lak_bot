"""
Test Dashboard Integration - Trade Lak Bot
يختبر الربط الكامل بين البوت ولوحة التحكم
"""
import sys
sys.path.insert(0, '/root/trade_lak_bot')

from utils.dashboard_notifier import DashboardNotifier
import time

print("=" * 60)
print("🧪 Testing Dashboard Integration")
print("=" * 60)

d = DashboardNotifier()

# ─── Test 1: Trade Opened ────────────────────────────────────
print("\n📊 Test 1: Sending trade opened...")
ok = d.notify_trade_opened({
    "symbol": "BTC-USDT",
    "tradeType": "SPOT",
    "direction": "BUY",
    "entryPrice": 104500.0,
    "stopLoss": 102000.0,
    "takeProfit1": 107000.0,
    "takeProfit2": 109000.0,
    "takeProfit3": 112000.0,
    "positionSize": 50.0,
    "confidence": 0.82,
    "successRate": 78.5,
    "reason": "AI Boost: Fear&Greed=28 (Extreme Fear) + LSTM Prediction UP + Whale Accumulation",
    "analysis": "Confidence: 82% | Market: SPOT | BTC oversold zone",
})
print(f"   Result: {'✅ SUCCESS' if ok else '❌ FAILED'}")
time.sleep(1)

# ─── Test 2: Recommendation ──────────────────────────────────
print("\n📊 Test 2: Sending recommendation...")
ok2 = d.notify_recommendation({
    "symbol": "ETH-USDT",
    "tradeType": "SPOT",
    "direction": "BUY",
    "entryPrice": 2650.0,
    "entryPrice2": 2620.0,
    "stopLoss": 2550.0,
    "takeProfit1": 2750.0,
    "takeProfit2": 2850.0,
    "takeProfit3": 2950.0,
    "successRate": 72.0,
    "confidence": 0.75,
    "reason": "ETH/BTC ratio improving + EIP-4844 momentum + Institutional buying",
    "analysis": "Strong support at $2620 | RSI: 42 (oversold) | Volume increasing",
})
print(f"   Result: {'✅ SUCCESS' if ok2 else '❌ FAILED'}")
time.sleep(1)

# ─── Test 3: Alert ────────────────────────────────────────────
print("\n📊 Test 3: Sending alert...")
ok3 = d.notify_alert(
    alert_type="SYSTEM",
    title="🤖 Bot Connected to Dashboard",
    message="Trade Lak Bot v4 is now connected and sending real-time data to the dashboard. All trades, recommendations, and alerts will be synced automatically.",
    severity="SUCCESS"
)
print(f"   Result: {'✅ SUCCESS' if ok3 else '❌ FAILED'}")
time.sleep(1)

# ─── Test 4: Trade Closed ─────────────────────────────────────
print("\n📊 Test 4: Sending trade closed...")
ok4 = d.notify_trade_closed(trade_data={
    "symbol": "BTC-USDT",
    "exitPrice": 107200.0,
    "profitLoss": 135.0,
    "profitLossPct": 2.59,
    "closeReason": "TP1_HIT",
})
print(f"   Result: {'✅ SUCCESS' if ok4 else '❌ FAILED'}")
time.sleep(1)

# ─── Test 5: Backtest Result ──────────────────────────────────
print("\n📊 Test 5: Sending backtest result...")
ok5 = d.notify_backtest_result({
    "name": "BTC-USDT AI Strategy - 1 Year",
    "symbol": "BTC-USDT",
    "strategy": "AI_ENHANCED",
    "timeframe": "1h",
    "startDate": "2025-05-01",
    "endDate": "2026-05-01",
    "initialCapital": 1000.0,
    "finalCapital": 1847.3,
    "totalTrades": 142,
    "winningTrades": 98,
    "losingTrades": 44,
    "winRate": 69.0,
    "totalProfit": 847.3,
    "maxDrawdown": 12.4,
    "sharpeRatio": 2.31,
})
print(f"   Result: {'✅ SUCCESS' if ok5 else '❌ FAILED'}")

# ─── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 60)
results = [ok, ok2, ok3, ok4, ok5]
passed = sum(1 for r in results if r)
print(f"📊 Results: {passed}/5 tests passed")
if passed == 5:
    print("✅ Dashboard integration is FULLY WORKING!")
    print("   → Open the dashboard to see live data")
    print("   → https://tradelakdash-cmxz8kc9.manus.space")
elif passed >= 3:
    print("⚠️ Partial integration - some endpoints working")
else:
    print("❌ Integration failed - check dashboard URL and API key")
print("=" * 60)
