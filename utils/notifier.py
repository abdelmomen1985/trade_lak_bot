# ============================================================
# Trade Lak Bot - Notifications & Trade Logger
# نظام التنبيهات وسجل الصفقات
# ============================================================

import requests
import logging
import json
import csv
import os
from datetime import datetime
from config.config import TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_PRIVATE_CHAT

logger = logging.getLogger(__name__)

TRADES_LOG_FILE = "logs/trades_history.csv"
STATS_FILE = "logs/stats.json"


class Notifier:
    """نظام التنبيهات عبر Telegram"""

    def send_telegram(self, message, parse_mode='HTML'):
        """إرسال رسالة إلى قناة Trade Lak Trade الرئيسية"""
        try:
            if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN:
                logger.info(f"[telegram-disabled] {str(message)[:150]}")
                return False
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": parse_mode
            }
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                logger.info(f"✅ [Telegram] رسالة أُرسلت إلى Trade channel")
                return True
            else:
                logger.error(f"❌ [Telegram] فشل الإرسال: {r.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"❌ [Telegram] خطأ: {e}")
            return False

    def send_private(self, message, parse_mode='HTML'):
        """إرسال رسالة خاصة للمالك فقط"""
        try:
            if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN:
                return False
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_PRIVATE_CHAT,
                "text": message,
                "parse_mode": parse_mode
            }
            r = requests.post(url, json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"❌ [Telegram-Private] خطأ: {e}")
            return False

    def notify_trade_open(self, symbol, direction, entry_price, stop_loss, take_profit, amount_usdt):
        msg = (
            f"<b>Trade Lak Bot - صفقة جديدة</b>\n"
            f"العملة: {symbol}\n"
            f"الاتجاه: {'شراء BUY' if direction == 'BUY' else 'بيع SELL'}\n"
            f"سعر الدخول: {entry_price:.6f}\n"
            f"Stop Loss: {stop_loss:.6f}\n"
            f"Take Profit: {take_profit:.6f}\n"
            f"المبلغ: ${amount_usdt:.2f}\n"
            f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"صفقة جديدة: {symbol} | {direction} | الدخول: {entry_price:.6f}")
        self.send_telegram(msg)

    def notify_trade_close(self, symbol, entry_price, exit_price, pnl_usdt, pnl_pct, reason):
        emoji = "✅" if pnl_usdt > 0 else "❌"
        msg = (
            f"<b>{emoji} Trade Lak Bot - إغلاق صفقة</b>\n"
            f"العملة: {symbol}\n"
            f"سعر الدخول: {entry_price:.6f}\n"
            f"سعر الخروج: {exit_price:.6f}\n"
            f"الربح/الخسارة: ${pnl_usdt:.2f} ({pnl_pct:.2f}%)\n"
            f"السبب: {reason}\n"
            f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"إغلاق صفقة: {symbol} | PnL: ${pnl_usdt:.2f} ({pnl_pct:.2f}%) | {reason}")
        self.send_telegram(msg)

    def notify_error(self, error_msg):
        msg = f"<b>⚠️ Trade Lak Bot - تنبيه خطأ</b>\n{error_msg}"
        logger.error(error_msg)
        self.send_telegram(msg)

    def notify_daily_summary(self, stats):
        msg = (
            f"<b>📊 Trade Lak Bot - ملخص يومي</b>\n"
            f"إجمالي الصفقات: {stats.get('total_trades', 0)}\n"
            f"الصفقات الرابحة: {stats.get('winning_trades', 0)}\n"
            f"الصفقات الخاسرة: {stats.get('losing_trades', 0)}\n"
            f"نسبة النجاح: {stats.get('win_rate', 0):.1f}%\n"
            f"إجمالي الأرباح: ${stats.get('total_pnl', 0):.2f}\n"
            f"رأس المال الحالي: ${stats.get('current_capital', 0):.2f}"
        )
        self.send_telegram(msg)


class TradeLogger:
    """سجل الصفقات في ملف CSV"""

    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(TRADES_LOG_FILE):
            with open(TRADES_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'date', 'symbol', 'direction', 'entry_price',
                    'exit_price', 'stop_loss', 'take_profit',
                    'amount_usdt', 'pnl_usdt', 'pnl_pct', 'reason', 'duration_min'
                ])

    def log_trade(self, trade_data):
        try:
            with open(TRADES_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    trade_data.get('symbol', ''),
                    trade_data.get('direction', ''),
                    trade_data.get('entry_price', 0),
                    trade_data.get('exit_price', 0),
                    trade_data.get('stop_loss', 0),
                    trade_data.get('take_profit', 0),
                    trade_data.get('amount_usdt', 0),
                    trade_data.get('pnl_usdt', 0),
                    trade_data.get('pnl_pct', 0),
                    trade_data.get('reason', ''),
                    trade_data.get('duration_min', 0),
                ])
            logger.info(f"تم تسجيل الصفقة في السجل: {trade_data.get('symbol')}")
        except Exception as e:
            logger.error(f"خطأ في تسجيل الصفقة: {e}")

    def get_stats(self):
        try:
            stats = {
                'total_trades': 0, 'winning_trades': 0,
                'losing_trades': 0, 'total_pnl': 0.0, 'win_rate': 0.0
            }
            if not os.path.exists(TRADES_LOG_FILE):
                return stats
            with open(TRADES_LOG_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total_trades'] += 1
                    pnl = float(row.get('pnl_usdt', 0))
                    stats['total_pnl'] += pnl
                    if pnl > 0:
                        stats['winning_trades'] += 1
                    else:
                        stats['losing_trades'] += 1
            if stats['total_trades'] > 0:
                stats['win_rate'] = (stats['winning_trades'] / stats['total_trades']) * 100
            return stats
        except Exception as e:
            logger.error(f"خطأ في جلب الإحصائيات: {e}")
            return {}
