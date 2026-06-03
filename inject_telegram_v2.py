"""
inject_telegram_v2.py
يدمج TelegramNotifierV2 في main.py:
1. يضيف import في أعلى الملف
2. يضيف تهيئة TelegramNotifierV2 في __init__
3. يستبدل استدعاء generate_and_send_recommendations لاستخدام notifier_v2
4. يضيف PriceTracker و LanguageBot
"""

import re

MAIN_PATH = "/root/trade_lak_bot/main.py"

with open(MAIN_PATH, "r") as f:
    content = f.read()

# ─── 1. إضافة imports ───────────────────────────────────────────────────────
old_import = "from utils.telegram_notifier import TelegramNotifier"
new_import = (
    "from utils.telegram_notifier import TelegramNotifier\n"
    "try:\n"
    "    from telegram_notifier import TelegramNotifierV2\n"
    "    from price_tracker import PriceTracker\n"
    "    from language_bot import LanguageBot\n"
    "    TELEGRAM_V2_AVAILABLE = True\n"
    "except ImportError as _e:\n"
    "    TELEGRAM_V2_AVAILABLE = False\n"
    "    print(f'TelegramV2 not available: {_e}')"
)

if "TelegramNotifierV2" not in content:
    content = content.replace(old_import, new_import, 1)
    print("✅ Added TelegramNotifierV2 import")
else:
    print("⚠️ TelegramNotifierV2 import already exists")

# ─── 2. تهيئة notifier_v2 في __init__ ───────────────────────────────────────
old_init = "        self.telegram = None"
new_init = (
    "        self.telegram = None\n"
    "        self.notifier_v2 = None\n"
    "        self.price_tracker = None\n"
    "        self.language_bot = None"
)

if "self.notifier_v2 = None" not in content:
    content = content.replace(old_init, new_init, 1)
    print("✅ Added notifier_v2/price_tracker/language_bot to __init__")
else:
    print("⚠️ notifier_v2 already in __init__")

# ─── 3. تهيئة notifier_v2 بعد تهيئة self.telegram ──────────────────────────
old_telegram_init = "            self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)"
new_telegram_init = (
    "            self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)\n"
    "            # ─── TelegramNotifierV2 (Signal + Trades channels) ───\n"
    "            if TELEGRAM_V2_AVAILABLE:\n"
    "                try:\n"
    "                    self.notifier_v2 = TelegramNotifierV2()\n"
    "                    self.price_tracker = PriceTracker(self.okx, self.notifier_v2)\n"
    "                    self.price_tracker.start()\n"
    "                    self.language_bot = LanguageBot()\n"
    "                    self.language_bot.start()\n"
    "                    logger.info('✅ TelegramNotifierV2 initialized (Signal + Trades channels)')\n"
    "                except Exception as _tge:\n"
    "                    logger.warning(f'TelegramNotifierV2 init failed: {_tge}')"
)

if "TelegramNotifierV2()" not in content:
    content = content.replace(old_telegram_init, new_telegram_init, 1)
    print("✅ Added TelegramNotifierV2 initialization")
else:
    print("⚠️ TelegramNotifierV2 init already exists")

# ─── 4. استبدال إرسال التوصية في generate_and_send_recommendations ──────────
old_send_rec = (
    "                        # Format and send\n"
    "                        message = self.recommendation_engine.format_recommendation_for_telegram(rec)\n"
    "                        if self.telegram:\n"
    "                            self.telegram.send_message(message)\n"
    "                        logger.info(f\"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)\")"
)
new_send_rec = (
    "                        # Format and send\n"
    "                        message = self.recommendation_engine.format_recommendation_for_telegram(rec)\n"
    "                        if self.telegram:\n"
    "                            self.telegram.send_message(message)\n"
    "                        # ─── TelegramV2: إرسال للقناة Signal ───\n"
    "                        if self.notifier_v2:\n"
    "                            try:\n"
    "                                self.notifier_v2.send_signal(\n"
    "                                    symbol=symbol,\n"
    "                                    direction=rec.get('direction', 'BUY'),\n"
    "                                    entry_price=rec.get('entry_price', current_price),\n"
    "                                    current_price=current_price,\n"
    "                                    stop_loss=rec.get('stop_loss', 0),\n"
    "                                    take_profit_1=rec.get('take_profit_1', 0),\n"
    "                                    take_profit_2=rec.get('take_profit_2', 0),\n"
    "                                    take_profit_3=rec.get('take_profit_3', 0),\n"
    "                                    confidence=rec.get('confidence', rec.get('success_rate', 0) / 100),\n"
    "                                    factors=rec.get('reason', ''),\n"
    "                                    trade_type=rec.get('trade_type', 'SPOT'),\n"
    "                                )\n"
    "                            except Exception as _v2e:\n"
    "                                logger.warning(f'TelegramV2 signal error: {_v2e}')\n"
    "                        logger.info(f\"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)\")"
)

if "notifier_v2.send_signal" not in content:
    content = content.replace(old_send_rec, new_send_rec, 1)
    print("✅ Added TelegramV2 send_signal in generate_and_send_recommendations")
else:
    print("⚠️ TelegramV2 send_signal already in recommendations")

# ─── 5. إضافة إشعار V2 عند فتح الصفقة الحقيقية ─────────────────────────────
old_trade_open_notify = (
    "                self.telegram.notify_trade_opened({\n"
    "                    'symbol': symbol,\n"
    "                    'entry_price': entry_price,\n"
    "                    'stop_loss': sl,\n"
    "                    'take_profit': tp,\n"
    "                    'trade_type': market.upper(),\n"
    "                    'direction': direction,\n"
    "                    'position_size': amount_usdt,\n"
    "                    'confidence': confidence\n"
    "                })"
)
new_trade_open_notify = (
    "                self.telegram.notify_trade_opened({\n"
    "                    'symbol': symbol,\n"
    "                    'entry_price': entry_price,\n"
    "                    'stop_loss': sl,\n"
    "                    'take_profit': tp,\n"
    "                    'trade_type': market.upper(),\n"
    "                    'direction': direction,\n"
    "                    'position_size': amount_usdt,\n"
    "                    'confidence': confidence\n"
    "                })\n"
    "                # ─── TelegramV2: إشعار قناة Trades بالصفقة الحقيقية ───\n"
    "                if self.notifier_v2:\n"
    "                    try:\n"
    "                        self.notifier_v2.send_real_trade_opened(\n"
    "                            symbol=symbol,\n"
    "                            direction=direction,\n"
    "                            entry_price=entry_price,\n"
    "                            stop_loss=sl,\n"
    "                            take_profit_1=tp,\n"
    "                            take_profit_2=tp * 1.02,\n"
    "                            take_profit_3=tp * 1.04,\n"
    "                            position_size=amount_usdt,\n"
    "                            confidence=confidence,\n"
    "                            trade_type=market.upper(),\n"
    "                        )\n"
    "                    except Exception as _v2e:\n"
    "                        logger.warning(f'TelegramV2 trade open error: {_v2e}')"
)

if "notifier_v2.send_real_trade_opened" not in content:
    content = content.replace(old_trade_open_notify, new_trade_open_notify, 1)
    print("✅ Added TelegramV2 send_real_trade_opened")
else:
    print("⚠️ TelegramV2 trade open already exists")

# ─── 6. إضافة إشعار V2 عند إغلاق الصفقة الحقيقية ───────────────────────────
old_trade_close_notify = (
    "            if self.telegram:\n"
    "                self.telegram.notify_trade_closed({\n"
    "                    'symbol': symbol,\n"
    "                    'entry_price': entry_price,\n"
    "                    'exit_price': exit_price,\n"
    "                    'profit_loss': pnl_usdt,\n"
    "                    'profit_loss_pct': pnl_pct,\n"
    "                    'duration': f\"{duration_min} min\",\n"
    "                    'close_reason': reason\n"
    "                })"
)
new_trade_close_notify = (
    "            if self.telegram:\n"
    "                self.telegram.notify_trade_closed({\n"
    "                    'symbol': symbol,\n"
    "                    'entry_price': entry_price,\n"
    "                    'exit_price': exit_price,\n"
    "                    'profit_loss': pnl_usdt,\n"
    "                    'profit_loss_pct': pnl_pct,\n"
    "                    'duration': f\"{duration_min} min\",\n"
    "                    'close_reason': reason\n"
    "                })\n"
    "            # ─── TelegramV2: إشعار قناة Trades بإغلاق الصفقة ───\n"
    "            if self.notifier_v2:\n"
    "                try:\n"
    "                    duration_str = f\"{duration_min // 60}h {duration_min % 60}m\" if duration_min >= 60 else f\"{duration_min}m\"\n"
    "                    self.notifier_v2.send_real_trade_closed(\n"
    "                        symbol=symbol,\n"
    "                        entry_price=entry_price,\n"
    "                        exit_price=exit_price,\n"
    "                        pnl_usdt=pnl_usdt,\n"
    "                        pnl_pct=pnl_pct,\n"
    "                        duration=duration_str,\n"
    "                        reason=reason,\n"
    "                        trade_type=market.upper(),\n"
    "                        direction=direction,\n"
    "                    )\n"
    "                    # إضافة للتقرير اليومي\n"
    "                    if self.price_tracker:\n"
    "                        self.price_tracker.add_trade_to_daily({\n"
    "                            'symbol': symbol,\n"
    "                            'direction': direction,\n"
    "                            'entry_price': entry_price,\n"
    "                            'exit_price': exit_price,\n"
    "                            'pnl_usdt': pnl_usdt,\n"
    "                            'pnl_pct': pnl_pct,\n"
    "                            'duration': duration_str,\n"
    "                            'reason': reason,\n"
    "                        })\n"
    "                except Exception as _v2e:\n"
    "                    logger.warning(f'TelegramV2 trade close error: {_v2e}')"
)

if "notifier_v2.send_real_trade_closed" not in content:
    content = content.replace(old_trade_close_notify, new_trade_close_notify, 1)
    print("✅ Added TelegramV2 send_real_trade_closed")
else:
    print("⚠️ TelegramV2 trade close already exists")

# ─── حفظ الملف ───────────────────────────────────────────────────────────────
with open(MAIN_PATH, "w") as f:
    f.write(content)

print("\n✅ inject_telegram_v2.py completed successfully!")
print("Verifying changes...")

# التحقق
checks = [
    "TelegramNotifierV2",
    "self.notifier_v2",
    "self.price_tracker",
    "self.language_bot",
    "notifier_v2.send_signal",
    "notifier_v2.send_real_trade_opened",
    "notifier_v2.send_real_trade_closed",
]
with open(MAIN_PATH, "r") as f:
    final = f.read()

for check in checks:
    status = "✅" if check in final else "❌"
    print(f"  {status} {check}")
