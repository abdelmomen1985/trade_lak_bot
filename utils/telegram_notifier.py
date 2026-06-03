# ============================================================
# Trade Lak Bot - Advanced Telegram Notifier
# تطبيق Trade لك - وحدة إخطارات تليجرام المتقدمة
# ============================================================

import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Advanced Telegram Notifier - sends real-time trading alerts
    وحدة إخطارات تليجرام المتقدمة - ترسل تنبيهات التداول الفورية
    """
    
    def __init__(self, bot_token: str, chat_id: str = None):
        """
        Initialize Telegram Notifier
        
        Args:
            bot_token: Telegram Bot Token
            chat_id: Chat ID (can be auto-detected from first message)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.message_history = []
        self.auto_detect_chat_id = chat_id is None
        
        logger.info("✅ Telegram Notifier initialized")
    
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message to Telegram (public method)
        إرسال رسالة إلى تليجرام
        """
        return self._send_message(text, parse_mode)
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send raw message to Telegram
        إرسال رسالة خام إلى تليجرام
        """
        try:
            if not self.chat_id:
                logger.warning("⚠️ Chat ID not set. Waiting for first message...")
                return False
            
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Message sent to Telegram")
                self.message_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'text': text[:100]
                })
                return True
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False
    
    def detect_chat_id(self) -> Optional[str]:
        """
        Auto-detect chat ID from updates
        الكشف التلقائي عن Chat ID من التحديثات
        """
        try:
            response = requests.get(
                f"{self.api_url}/getUpdates",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result') and len(data['result']) > 0:
                    chat_id = data['result'][0]['message']['chat']['id']
                    self.chat_id = str(chat_id)
                    logger.info(f"✅ Chat ID detected: {self.chat_id}")
                    return self.chat_id
        
        except Exception as e:
            logger.error(f"❌ Error detecting chat ID: {e}")
        
        return None
    
    # ================================================================
    # Trade Notifications / إخطارات التداول
    # ================================================================
    
    def notify_trade_opened(self, trade_data: Dict) -> bool:
        """
        Notify when a new trade is opened
        إخطار عند فتح صفقة جديدة
        """
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            entry_price = trade_data.get('entry_price', 0)
            stop_loss = trade_data.get('stop_loss', 0)
            take_profit = trade_data.get('take_profit', 0)
            trade_type = trade_data.get('trade_type', 'SPOT')  # SPOT or FUTURES
            direction = trade_data.get('direction', 'LONG')
            position_size = trade_data.get('position_size', 0)
            confidence = trade_data.get('confidence', 0)
            
            # Determine emoji
            if direction == 'LONG':
                emoji = "📈" if trade_type == 'SPOT' else "🚀"
            else:
                emoji = "📉"
            
            message = f"""
{emoji} <b>صفقة جديدة!</b>

<b>العملة:</b> {symbol}
<b>النوع:</b> {trade_type} {direction}
<b>نقطة الدخول:</b> ${entry_price:.2f}
<b>Stop Loss:</b> ${stop_loss:.2f}
<b>Take Profit:</b> ${take_profit:.2f}
<b>حجم المركز:</b> {position_size:.4f}
<b>الثقة:</b> {confidence:.0%}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying trade opened: {e}")
            return False
    
    def notify_trade_closed(self, trade_data: Dict) -> bool:
        """
        Notify when a trade is closed
        إخطار عند إغلاق صفقة
        """
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            entry_price = trade_data.get('entry_price', 0)
            exit_price = trade_data.get('exit_price', 0)
            profit_loss = trade_data.get('profit_loss', 0)
            profit_loss_pct = trade_data.get('profit_loss_pct', 0)
            duration = trade_data.get('duration', 'Unknown')
            close_reason = trade_data.get('close_reason', 'TP/SL')
            
            # Determine emoji
            if profit_loss > 0:
                emoji = "✅"
                status = "رابح"
            elif profit_loss < 0:
                emoji = "❌"
                status = "خاسر"
            else:
                emoji = "⚪"
                status = "متعادل"
            
            message = f"""
{emoji} <b>صفقة مغلقة - {status}</b>

<b>العملة:</b> {symbol}
<b>نقطة الدخول:</b> ${entry_price:.2f}
<b>نقطة الخروج:</b> ${exit_price:.2f}
<b>الربح/الخسارة:</b> ${profit_loss:+.2f} ({profit_loss_pct:+.2f}%)
<b>السبب:</b> {close_reason}
<b>المدة:</b> {duration}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying trade closed: {e}")
            return False
    
    def notify_circuit_breaker(self, reason: str, stats: Dict) -> bool:
        """
        Notify when circuit breaker is triggered
        إخطار عند تفعيل قاطع الدائرة
        """
        try:
            daily_pnl = stats.get('daily_pnl', 0)
            total_trades = stats.get('total_trades', 0)
            
            message = f"""
⚠️ <b>تنبيه: قاطع الدائرة مفعّل!</b>

<b>السبب:</b> {reason}
<b>خسائر اليوم:</b> {daily_pnl:.2f}%
<b>عدد الصفقات:</b> {total_trades}

🛑 <b>البوت توقف عن التداول للحماية</b>

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying circuit breaker: {e}")
            return False
    
    def notify_wick_trap(self, symbol: str, wick_type: str, danger_level: str, recommendation: str, score: float) -> bool:
        """
        Notify when a wick trap is detected
        """
        try:
            emoji_map = {
                'CRITICAL': '🚫',
                'HIGH': '🔴',
                'MEDIUM': '🟠',
                'LOW': '🟡',
                'SAFE': '🟢'
            }
            emoji = emoji_map.get(danger_level, '⚠️')
            
            message = f"""
{emoji} <b>تنبيه فخ ذيول!</b>

<b>العملة:</b> {symbol}
<b>نوع الذيل:</b> {wick_type}
<b>درجة الخطورة:</b> {danger_level}
<b>النقاط:</b> {score:.0f}/100

<b>التوصية:</b>
{recommendation}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"Error notifying wick trap: {e}")
            return False
    
    def notify_strong_signal(self, signal_data: Dict) -> bool:
        """
        Notify about strong trading signals
        إخطار عن إشارات قوية
        """
        try:
            symbol = signal_data.get('symbol', 'UNKNOWN')
            signal = signal_data.get('signal', 'NEUTRAL')
            confidence = signal_data.get('confidence', 0)
            reasons = signal_data.get('reasons', [])
            
            # Determine emoji
            if signal == 'STRONG_BUY':
                emoji = "🚀"
            elif signal == 'BUY':
                emoji = "📈"
            elif signal == 'STRONG_SELL':
                emoji = "💥"
            elif signal == 'SELL':
                emoji = "📉"
            else:
                emoji = "⚪"
            
            reasons_text = "\n".join([f"• {r}" for r in reasons[:3]])
            
            message = f"""
{emoji} <b>إشارة قوية!</b>

<b>العملة:</b> {symbol}
<b>الإشارة:</b> {signal}
<b>الثقة:</b> {confidence:.0%}

<b>الأسباب:</b>
{reasons_text}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying signal: {e}")
            return False
    
    # ================================================================
    # Daily Statistics / الإحصائيات اليومية
    # ================================================================
    
    def notify_daily_stats(self, stats: Dict) -> bool:
        """
        Send daily trading statistics
        إرسال إحصائيات التداول اليومية
        """
        try:
            total_trades = stats.get('total_trades', 0)
            winning_trades = stats.get('winning_trades', 0)
            losing_trades = stats.get('losing_trades', 0)
            win_rate = stats.get('win_rate', 0)
            daily_pnl = stats.get('daily_pnl', 0)
            daily_pnl_pct = stats.get('daily_pnl_pct', 0)
            
            # Determine emoji
            if daily_pnl > 0:
                emoji = "📈"
            elif daily_pnl < 0:
                emoji = "📉"
            else:
                emoji = "⚪"
            
            message = f"""
{emoji} <b>إحصائيات اليوم</b>

<b>إجمالي الصفقات:</b> {total_trades}
<b>صفقات رابحة:</b> {winning_trades} ✅
<b>صفقات خاسرة:</b> {losing_trades} ❌
<b>نسبة النجاح:</b> {win_rate:.1%}

<b>الأرباح/الخسائر:</b> ${daily_pnl:+.2f} ({daily_pnl_pct:+.2f}%)

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error sending daily stats: {e}")
            return False
    
    def notify_weekly_stats(self, stats: Dict) -> bool:
        """
        Send weekly trading statistics
        إرسال إحصائيات التداول الأسبوعية
        """
        try:
            total_trades = stats.get('total_trades', 0)
            win_rate = stats.get('win_rate', 0)
            weekly_pnl = stats.get('weekly_pnl', 0)
            weekly_pnl_pct = stats.get('weekly_pnl_pct', 0)
            profit_factor = stats.get('profit_factor', 0)
            
            # Determine emoji
            if weekly_pnl > 0:
                emoji = "📊"
            else:
                emoji = "📉"
            
            message = f"""
{emoji} <b>إحصائيات الأسبوع</b>

<b>إجمالي الصفقات:</b> {total_trades}
<b>نسبة النجاح:</b> {win_rate:.1%}
<b>Profit Factor:</b> {profit_factor:.2f}

<b>الأرباح/الخسائر:</b> ${weekly_pnl:+.2f} ({weekly_pnl_pct:+.2f}%)

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error sending weekly stats: {e}")
            return False
    
    # ================================================================
    # Warnings and Errors / التحذيرات والأخطاء
    # ================================================================
    
    def notify_warning(self, title: str, message: str) -> bool:
        """
        Send warning notification
        إرسال تنبيه تحذيري
        """
        try:
            full_message = f"""
⚠️ <b>{title}</b>

{message}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(full_message)
        
        except Exception as e:
            logger.error(f"❌ Error sending warning: {e}")
            return False
    
    def notify_error(self, error_title: str, error_message: str) -> bool:
        """
        Send error notification
        إرسال إخطار خطأ
        """
        try:
            full_message = f"""
❌ <b>خطأ: {error_title}</b>

{error_message}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(full_message)
        
        except Exception as e:
            logger.error(f"❌ Error sending error notification: {e}")
            return False
    
    # ================================================================
    # Status and Info / الحالة والمعلومات
    # ================================================================
    
    def notify_bot_started(self) -> bool:
        """
        Notify when bot starts
        إخطار عند بدء البوت
        """
        try:
            message = """
✅ <b>البوت بدأ التشغيل!</b>

🤖 Trade Lak Bot
🚀 نسخة متقدمة مع ذكاء اصطناعي
📊 جاهز للتداول الآن

⏰ الوقت: """ + datetime.now().strftime('%H:%M:%S')
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying bot started: {e}")
            return False
    
    def notify_bot_stopped(self, reason: str = "") -> bool:
        """
        Notify when bot stops
        إخطار عند إيقاف البوت
        """
        try:
            message = f"""
🛑 <b>البوت توقف!</b>

السبب: {reason if reason else "إيقاف يدوي"}

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error notifying bot stopped: {e}")
            return False
    
    def notify_status(self, status_data: Dict) -> bool:
        """
        Send current bot status
        إرسال حالة البوت الحالية
        """
        try:
            open_trades = status_data.get('open_trades', 0)
            total_capital = status_data.get('total_capital', 0)
            available_capital = status_data.get('available_capital', 0)
            total_pnl = status_data.get('total_pnl', 0)
            total_pnl_pct = status_data.get('total_pnl_pct', 0)
            
            message = f"""
📊 <b>حالة البوت</b>

<b>الصفقات المفتوحة:</b> {open_trades}
<b>رأس المال الكلي:</b> ${total_capital:.2f}
<b>رأس المال المتاح:</b> ${available_capital:.2f}
<b>إجمالي الأرباح/الخسائر:</b> ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)

⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return self._send_message(message)
        
        except Exception as e:
            logger.error(f"❌ Error sending status: {e}")
            return False
    
    # ================================================================
    # Utilities / الأدوات المساعدة
    # ================================================================
    
    def get_message_history(self, limit: int = 10) -> List[Dict]:
        """Get recent message history"""
        return self.message_history[-limit:]
    
    def clear_history(self):
        """Clear message history"""
        self.message_history = []
        logger.info("✅ Message history cleared")

    def notify_psychology_alert(self, sentiment_level: str, sentiment_score: float,
                               liquidity_risk: str = None, risky_period: str = None):
        """Send market psychology alert"""
        try:
            emoji_map = {
                'Extreme Fear': '🔴',
                'Fear': '🟠',
                'Neutral': '⚪',
                'Greed': '🟡',
                'Extreme Greed': '🟢'
            }
            emoji = emoji_map.get(sentiment_level, '⚪')
            
            message = f"🧠 تنبيه نفسية السوق!\n\n"
            message += f"{emoji} المشاعر: {sentiment_level}\n"
            message += f"📊 النقاط: {sentiment_score:.0f}/100\n"
            
            if liquidity_risk == 'CRITICAL':
                message += f"\n💧 ⚠️ تحذير: السيولة منخفضة جداً!\n"
                message += f"❌ تجنب التداول الآن"
            
            if risky_period:
                message += f"\n⏰ ⚠️ فترة خطرة: {risky_period}\n"
                message += f"❌ معدل خسارة عالي في هذه الفترة"
            
            message += f"\n\n⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending psychology alert: {e}")
    
    def notify_contrarian_opportunity(self, sentiment_level: str, confidence: float):
        """Send contrarian trading opportunity alert"""
        try:
            if 'Fear' in sentiment_level:
                emoji = '🟢'
                action = 'شراء'
            else:
                emoji = '🔴'
                action = 'بيع'
            
            message = (
                f"{emoji} فرصة تداول عكسية!\n\n"
                f"المشاعر: {sentiment_level}\n"
                f"الثقة: {confidence:.0%}\n\n"
                f"التوصية: {action} قوي!\n"
                f"الناس في {sentiment_level.lower()} → أسعار جيدة\n\n"
                f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            )
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending contrarian opportunity alert: {e}")

    def notify_economic_event(self, event_name: str, impact: str, time_until: str,
                             volatility_expected: float, recommendation: str):
        """Send economic event alert"""
        try:
            impact_emoji = {
                'Critical': '🚫',
                'Very High': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Low': '🟢'
            }
            emoji = impact_emoji.get(impact, '📅')
            
            message = f"{emoji} تنبيه حدث اقتصادي!\n\n"
            message += f"الحدث: {event_name}\n"
            message += f"التأثير: {impact}\n"
            message += f"الوقت: {time_until}\n"
            message += f"التذبذب المتوقع: {volatility_expected:.1f}%\n\n"
            message += f"التوصية:\n{recommendation}\n\n"
            message += f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending economic event alert: {e}")
    
    def notify_economic_calendar_summary(self, upcoming_count: int, critical_count: int,
                                        high_count: int, next_event: str = None):
        """Send economic calendar summary"""
        try:
            message = f"📅 ملخص التقويم الاقتصادي\n\n"
            message += f"الأحداث القادمة (24 ساعة): {upcoming_count}\n"
            message += f"🚫 أحداث حرجة: {critical_count}\n"
            message += f"🔴 أحداث عالية: {high_count}\n"
            
            if next_event:
                message += f"\nالحدث التالي: {next_event}"
            
            if critical_count > 0 or high_count > 0:
                message += f"\n\n⚠️ توصية: كن حذراً! أحداث اقتصادية مهمة قادمة"
            else:
                message += f"\n\n✅ اليوم هادئ نسبياً"
            
            message += f"\n\n⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending calendar summary: {e}")

    def notify_market_condition(self, condition: str, crash_prob: float = 0, pump_prob: float = 0,
                               recession_prob: float = 0, altseason_prob: float = 0):
        """Send market condition alert"""
        try:
            if condition == 'Crash':
                message = f"🚫 تنبيه انهيار!\n\n"
                message += f"احتمال الانهيار: {crash_prob:.0%}\n"
                message += f"⚠️ توصية: تجنب التداول فوراً!\n"
            elif condition == 'Pump':
                message = f"🚀 تنبيه ضخ سيولة!\n\n"
                message += f"احتمال الضخ: {pump_prob:.0%}\n"
                message += f"⚠️ توصية: كن حذراً من الذروة!\n"
            elif condition == 'Recession':
                message = f"📉 تنبيه ركود!\n\n"
                message += f"احتمال الركود: {recession_prob:.0%}\n"
                message += f"⚠️ توصية: تجنب التداول!\n"
            elif condition == 'Altseason':
                message = f"🟢 موسم العملات البديلة!\n\n"
                message += f"احتمال الموسم: {altseason_prob:.0%}\n"
                message += f"✅ توصية: ركز على العملات البديلة الجيدة!\n"
            else:
                message = f"📊 السوق عادي\n\n"
                message += f"✅ توصية: تداول عادي\n"
            
            message += f"\n⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending market condition alert: {e}")
    
    def notify_crash_warning(self, indicators_count: int, probability: float, affected_pairs: list):
        """Send crash warning"""
        try:
            message = f"🚫 تحذير انهيار!\n\n"
            message += f"عدد المؤشرات: {indicators_count}\n"
            message += f"احتمال الانهيار: {probability:.0%}\n"
            message += f"العملات المتأثرة: {', '.join(affected_pairs[:3])}\n\n"
            message += f"⚠️ توصية: تجنب التداول الآن!\n"
            message += f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending crash warning: {e}")
    
    def notify_altseason_opportunity(self, strength: float, top_alts: list):
        """Send altseason opportunity alert"""
        try:
            message = f"🚀 فرصة موسم العملات البديلة!\n\n"
            message += f"قوة الموسم: {strength:.0f}/100\n"
            message += f"أفضل العملات:\n"
            for alt in top_alts[:5]:
                message += f"   • {alt}\n"
            message += f"\n✅ توصية: ركز على هذه العملات!\n"
            message += f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
            
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending altseason alert: {e}")

    def notify_sector_report(self, report_text: str) -> bool:
        """
        إرسال تقرير القطاعات وتدفق السيولة
        Send sector liquidity flow report
        """
        try:
            return self._send_message(report_text)
        except Exception as e:
            logger.error(f"Error sending sector report: {e}")
            return False

    def notify_explosion_candidate(self, symbol: str, sector: str, score: float,
                                    vol_spike: float, price_change: float,
                                    signals: list, entry_price: float) -> bool:
        """
        إشعار عملة مهيأة للانفجار
        Notify about a coin ready to explode
        """
        try:
            sym = symbol.replace('/USDT', '')
            signals_text = "\n".join([f"  ✅ {s}" for s in signals[:4]])
            vol_bar = "🔥" * min(int(vol_spike), 5)
            message = f"""
🚀 <b>عملة مهيأة للانفجار!</b>

💎 <b>{sym}</b> — قطاع: <b>{sector}</b>
━━━━━━━━━━━━━━━━━━━━━
📊 نقاط الزخم: <b>{score:.0f}/100</b>
📈 تغير السعر: <b>{price_change:+.1f}%</b>
💧 انفجار الحجم: <b>{vol_spike:.1f}x</b> {vol_bar}
💰 السعر الحالي: <b>${entry_price:.4f}</b>

🎯 <b>إشارات الانفجار:</b>
{signals_text}

⚡ <b>البوت يراقب ويدخل تلقائياً عند التأكيد</b>
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(message)
        except Exception as e:
            logger.error(f"Error sending explosion candidate: {e}")
            return False

    def notify_trade_opened_v2(self, trade_data: Dict) -> bool:
        """
        إشعار فتح صفقة محسّن مع معلومات القطاع والانفجار
        Enhanced trade opened notification with sector info
        """
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            sym = symbol.replace('/USDT', '')
            entry_price = trade_data.get('entry_price', 0)
            stop_loss = trade_data.get('stop_loss', 0)
            take_profit = trade_data.get('take_profit', 0)
            trade_type = trade_data.get('trade_type', 'SPOT')
            direction = trade_data.get('direction', 'LONG')
            position_size = trade_data.get('position_size', 0)
            confidence = trade_data.get('confidence', 0)
            sector = trade_data.get('sector', 'Other')
            sector_boost = trade_data.get('sector_boost', 0)
            is_explosion = trade_data.get('is_explosion_candidate', False)
            reasons = trade_data.get('reasons', [])
            leverage = trade_data.get('leverage', 1)

            # رموز الاتجاه
            if direction in ('LONG', 'SPOT_BUY'):
                dir_emoji = "📈"
                dir_text = "شراء"
            else:
                dir_emoji = "📉"
                dir_text = "بيع"

            # حساب نسبة الربح المتوقعة
            if entry_price > 0:
                tp_pct = abs(take_profit - entry_price) / entry_price * 100 * leverage
                sl_pct = abs(stop_loss - entry_price) / entry_price * 100 * leverage
            else:
                tp_pct = sl_pct = 0

            explosion_line = "🚀 <b>عملة مهيأة للانفجار!</b>\n" if is_explosion else ""
            sector_line = f"🏦 القطاع: <b>{sector}</b>" + (f" (+{sector_boost:.0%} مكافأة)" if sector_boost > 0 else "")
            reasons_text = "\n".join([f"  • {r}" for r in reasons[:3]]) if reasons else "  • تحليل شامل"

            message = f"""
{dir_emoji} <b>صفقة جديدة مفتوحة!</b>
{explosion_line}━━━━━━━━━━━━━━━━━━━━━
💎 <b>{sym}/USDT</b> — {trade_type} {dir_text}
{sector_line}
━━━━━━━━━━━━━━━━━━━━━
💰 الدخول: <b>${entry_price:.4f}</b>
🛑 Stop Loss: <b>${stop_loss:.4f}</b> (-{sl_pct:.1f}%)
🎯 Take Profit: <b>${take_profit:.4f}</b> (+{tp_pct:.1f}%)
📦 الحجم: <b>{position_size:.4f}</b>
🧠 الثقة: <b>{confidence:.0f}%</b>
━━━━━━━━━━━━━━━━━━━━━
📊 <b>أسباب الدخول:</b>
{reasons_text}
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(message)
        except Exception as e:
            logger.error(f"Error in notify_trade_opened_v2: {e}")
            return False

    def notify_trade_closed_v2(self, trade_data: Dict) -> bool:
        """
        إشعار إغلاق صفقة محسّن
        Enhanced trade closed notification
        """
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            sym = symbol.replace('/USDT', '')
            entry_price = trade_data.get('entry_price', 0)
            exit_price = trade_data.get('exit_price', 0)
            profit_loss = trade_data.get('profit_loss', 0)
            profit_loss_pct = trade_data.get('profit_loss_pct', 0)
            duration = trade_data.get('duration', 'Unknown')
            close_reason = trade_data.get('close_reason', 'TP/SL')
            sector = trade_data.get('sector', 'Other')
            trade_type = trade_data.get('trade_type', 'SPOT')

            if profit_loss > 0:
                emoji = "✅"
                status = "رابح 🎉"
                profit_bar = "💚" * min(int(abs(profit_loss_pct) / 2), 5)
            elif profit_loss < 0:
                emoji = "❌"
                status = "خاسر"
                profit_bar = "🔴" * min(int(abs(profit_loss_pct) / 2), 5)
            else:
                emoji = "⚪"
                status = "متعادل"
                profit_bar = ""

            message = f"""
{emoji} <b>صفقة مغلقة — {status}</b>
━━━━━━━━━━━━━━━━━━━━━
💎 <b>{sym}/USDT</b> — {trade_type}
🏦 القطاع: <b>{sector}</b>
━━━━━━━━━━━━━━━━━━━━━
💰 الدخول: <b>${entry_price:.4f}</b>
🏁 الخروج: <b>${exit_price:.4f}</b>
📊 الربح/الخسارة: <b>${profit_loss:+.2f} ({profit_loss_pct:+.1f}%)</b> {profit_bar}
📋 السبب: <b>{close_reason}</b>
⏱ المدة: <b>{duration}</b>
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(message)
        except Exception as e:
            logger.error(f"Error in notify_trade_closed_v2: {e}")
            return False


    def notify_liquidity_alert(self, symbol: str, decision: str, reason: str,
                               summary: str, pnl_pct: float = 0.0) -> bool:
        """
        إشعار تدهور السيولة بعد الدخول
        Post-Entry Liquidity Deterioration Alert
        """
        try:
            if decision == 'EARLY_EXIT':
                icon = "🚨"
                title = "خروج مبكر بسبب تدهور السيولة"
                color_line = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            else:
                icon = "⚠️"
                title = "تشديد Stop Loss — تراجع السيولة"
                color_line = "─────────────────────────────────"

            pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct != 0 else "—"

            message = f"""{color_line}
{icon} <b>{title}</b>
{color_line}
💱 <b>العملة:</b> {symbol}
📊 <b>القرار:</b> {decision}
💧 <b>السبب:</b> {reason}
📈 <b>P&amp;L الحالي:</b> {pnl_str}
{color_line}
🔍 <b>ملخص المؤشرات:</b>
{summary}
{color_line}
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            return self._send_message(message)
        except Exception as e:
            logger.error(f"Error in notify_liquidity_alert: {e}")
            return False
