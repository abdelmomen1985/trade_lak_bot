"""
Inject DashboardNotifier into main.py
يضيف DashboardNotifier في النقاط الصحيحة داخل main.py
"""
import re

main_file = "/root/trade_lak_bot/main.py"

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. إضافة import ─────────────────────────────────────────────────────────
old_import = "from utils.trade_reporter import TradeReporter"
new_import = """from utils.trade_reporter import TradeReporter
from utils.dashboard_notifier import DashboardNotifier"""

if "from utils.dashboard_notifier import DashboardNotifier" not in content:
    content = content.replace(old_import, new_import)
    print("✅ Added DashboardNotifier import")
else:
    print("⚠️ DashboardNotifier import already exists")

# ─── 2. تهيئة DashboardNotifier في __init__ ──────────────────────────────────
old_init_end = """            # Initialize Trade Reporter
            try:
                self.trade_reporter = TradeReporter(self.telegram)
                logger.info("✅ Trade Reporter initialized")
            except Exception as e:
                logger.error(f"Error initializing trade reporter: {e}")
                self.trade_reporter = None"""

new_init_end = """            # Initialize Trade Reporter
            try:
                self.trade_reporter = TradeReporter(self.telegram)
                logger.info("✅ Trade Reporter initialized")
            except Exception as e:
                logger.error(f"Error initializing trade reporter: {e}")
                self.trade_reporter = None
        # Initialize Dashboard Notifier (always active, independent of Telegram)
        try:
            self.dashboard = DashboardNotifier()
            logger.info("✅ Dashboard Notifier initialized → https://tradelakdash-cmxz8kc9.manus.space")
        except Exception as e:
            logger.error(f"Error initializing dashboard notifier: {e}")
            self.dashboard = None"""

if "self.dashboard = DashboardNotifier()" not in content:
    content = content.replace(old_init_end, new_init_end)
    print("✅ Added DashboardNotifier initialization in __init__")
else:
    print("⚠️ DashboardNotifier init already exists")

# ─── 3. إرسال بيانات فتح الصفقة ──────────────────────────────────────────────
old_trade_open_end = """            if self.telegram and not self.trade_reporter:
                # Check for wick trap warnings"""

new_trade_open_end = """            # ─── Dashboard Notification: Trade Opened ───────────────────
            if self.dashboard:
                try:
                    self.dashboard.notify_trade_opened({
                        "symbol": symbol,
                        "tradeType": market.upper(),
                        "direction": "BUY" if direction in ("SPOT_BUY", "LONG") else ("SELL" if direction == "SPOT_SELL" else direction),
                        "entryPrice": entry_price,
                        "stopLoss": sl,
                        "takeProfit1": tp,
                        "takeProfit2": tp * 1.02,
                        "takeProfit3": tp * 1.04,
                        "positionSize": amount_usdt,
                        "confidence": confidence,
                        "successRate": 75,
                        "reason": ", ".join(reasons) if reasons else "Strong signal detected",
                        "analysis": f"Confidence: {confidence:.0%} | Market: {market.upper()}",
                    })
                except Exception as _de:
                    logger.warning(f"Dashboard notify_trade_opened error: {_de}")
            # ─────────────────────────────────────────────────────────────────
            if self.telegram and not self.trade_reporter:
                # Check for wick trap warnings"""

if "Dashboard Notification: Trade Opened" not in content:
    content = content.replace(old_trade_open_end, new_trade_open_end)
    print("✅ Added Dashboard notification for trade opened")
else:
    print("⚠️ Trade opened dashboard notification already exists")

# ─── 4. إرسال بيانات إغلاق الصفقة ───────────────────────────────────────────
old_trade_close = """            # Send comprehensive trade closed report
            if self.trade_reporter:"""

new_trade_close = """            # ─── Dashboard Notification: Trade Closed ────────────────────
            if self.dashboard:
                try:
                    self.dashboard.notify_trade_closed(trade_data={
                        "symbol": symbol,
                        "exitPrice": exit_price,
                        "profitLoss": pnl_usdt,
                        "profitLossPct": pnl_pct,
                        "closeReason": reason,
                    })
                except Exception as _de:
                    logger.warning(f"Dashboard notify_trade_closed error: {_de}")
            # ─────────────────────────────────────────────────────────────────
            # Send comprehensive trade closed report
            if self.trade_reporter:"""

if "Dashboard Notification: Trade Closed" not in content:
    content = content.replace(old_trade_close, new_trade_close)
    print("✅ Added Dashboard notification for trade closed")
else:
    print("⚠️ Trade closed dashboard notification already exists")

# ─── 5. إرسال التوصيات للوحة التحكم ─────────────────────────────────────────
old_rec_send = """                    if rec and rec['success_rate'] >= 60:  # Only send high confidence recommendations
                        # Format and send
                        message = self.recommendation_engine.format_recommendation_for_telegram(rec)
                        if self.telegram:
                            self.telegram.send_message(message)
                        logger.info(f"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)")"""

new_rec_send = """                    if rec and rec['success_rate'] >= 60:  # Only send high confidence recommendations
                        # Format and send
                        message = self.recommendation_engine.format_recommendation_for_telegram(rec)
                        if self.telegram:
                            self.telegram.send_message(message)
                        logger.info(f"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)")
                        # ─── Dashboard Notification: Recommendation ──────────
                        if self.dashboard:
                            try:
                                self.dashboard.notify_recommendation({
                                    "symbol": symbol,
                                    "direction": rec.get("direction", "BUY"),
                                    "tradeType": rec.get("trade_type", "SPOT"),
                                    "entryPrice": rec.get("entry_price", current_price),
                                    "entryPrice2": rec.get("entry_price_2"),
                                    "stopLoss": rec.get("stop_loss"),
                                    "takeProfit1": rec.get("take_profit_1"),
                                    "takeProfit2": rec.get("take_profit_2"),
                                    "takeProfit3": rec.get("take_profit_3"),
                                    "successRate": rec.get("success_rate", 0),
                                    "confidence": rec.get("confidence", 0),
                                    "reason": rec.get("reason", ""),
                                    "analysis": rec.get("analysis", ""),
                                })
                            except Exception as _de:
                                logger.warning(f"Dashboard notify_recommendation error: {_de}")
                        # ─────────────────────────────────────────────────────"""

if "Dashboard Notification: Recommendation" not in content:
    content = content.replace(old_rec_send, new_rec_send)
    print("✅ Added Dashboard notification for recommendations")
else:
    print("⚠️ Recommendation dashboard notification already exists")

# ─── حفظ الملف المعدّل ───────────────────────────────────────────────────────
with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ main.py updated successfully with Dashboard Notifier integration!")
print(f"   Dashboard URL: https://tradelakdash-cmxz8kc9.manus.space")
