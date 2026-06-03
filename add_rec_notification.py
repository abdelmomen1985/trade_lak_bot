"""
Add dashboard notification for recommendations in main.py
"""
main_file = "/root/trade_lak_bot/main.py"

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the recommendation section and add dashboard notification after it
old_snippet = "                        logger.info(f\"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)\")"

new_snippet = """                        logger.info(f\"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)\")
                        # Dashboard Notification: Recommendation
                        if self.dashboard:
                            try:
                                self.dashboard.notify_recommendation({
                                    'symbol': symbol,
                                    'direction': rec.get('direction', 'BUY'),
                                    'tradeType': rec.get('trade_type', 'SPOT'),
                                    'entryPrice': rec.get('entry_price', current_price),
                                    'entryPrice2': rec.get('entry_price_2'),
                                    'stopLoss': rec.get('stop_loss'),
                                    'takeProfit1': rec.get('take_profit_1'),
                                    'takeProfit2': rec.get('take_profit_2'),
                                    'takeProfit3': rec.get('take_profit_3'),
                                    'successRate': rec.get('success_rate', 0),
                                    'confidence': rec.get('confidence', 0),
                                    'reason': rec.get('reason', ''),
                                    'analysis': rec.get('analysis', ''),
                                })
                            except Exception as _de:
                                logger.warning(f'Dashboard notify_recommendation error: {_de}')"""

if "Dashboard Notification: Recommendation" in content:
    print("⚠️ Recommendation notification already exists")
elif old_snippet in content:
    content = content.replace(old_snippet, new_snippet)
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Recommendation dashboard notification added successfully!")
else:
    print("❌ Pattern not found. Checking content around line 902...")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'Recommendation sent for' in line:
            print(f"Line {i+1}: {repr(line)}")
