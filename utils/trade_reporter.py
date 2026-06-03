"""
Trade Reporter
Comprehensive trade reporting system with detailed notifications
نظام التقارير الشامل للصفقات مع إخطارات مفصلة
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class TradeReporter:
    """Comprehensive trade reporting system"""
    
    def __init__(self, telegram_notifier=None):
        """Initialize trade reporter"""
        self.telegram = telegram_notifier
        self.open_trades = {}
        self.closed_trades = []
        self.trade_statistics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
        }
        logger.info("✅ Trade Reporter initialized")
    
    # ========================================================================
    # Trade Opening Report
    # ========================================================================
    
    def report_trade_opened(self, trade_data: Dict) -> str:
        """
        Generate and send trade opening report
        إنشاء وإرسال تقرير فتح الصفقة
        """
        try:
            symbol = trade_data.get('symbol', 'Unknown')
            current_price = trade_data.get('current_price', 0)
            entry_price = trade_data.get('entry_price', 0)
            entry_price_2 = trade_data.get('entry_price_2', entry_price)
            stop_loss = trade_data.get('stop_loss', 0)
            take_profit_1 = trade_data.get('take_profit_1', 0)
            take_profit_2 = trade_data.get('take_profit_2', 0)
            take_profit_3 = trade_data.get('take_profit_3', 0)
            position_size = trade_data.get('position_size', 0)
            trade_type = trade_data.get('trade_type', 'SPOT')
            direction = trade_data.get('direction', 'BUY')
            confidence = trade_data.get('confidence', 0)
            reason = trade_data.get('reason', 'Strong signal detected')
            analysis = trade_data.get('analysis', '')
            success_rate = trade_data.get('success_rate', 0)
            
            # Calculate potential profit/loss
            potential_profit_tp1 = ((take_profit_1 - entry_price) / entry_price) * 100
            potential_profit_tp2 = ((take_profit_2 - entry_price) / entry_price) * 100
            potential_profit_tp3 = ((take_profit_3 - entry_price) / entry_price) * 100
            potential_loss = ((entry_price - stop_loss) / entry_price) * 100
            
            # Direction emoji
            direction_emoji = "🟢" if direction == "BUY" else "🔴"
            
            message = f"""
{direction_emoji} **صفقة جديدة مفتوحة**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **معلومات الصفقة**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💱 **العملة:** {symbol}
💰 **السعر الحالي:** ${current_price:,.2f}
📈 **الاتجاه:** {direction} ({direction_emoji})
⚙️ **النوع:** {trade_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **نقاط الدخول**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 الدخول الأول: ${entry_price:,.2f}
🔹 الدخول الثاني: ${entry_price_2:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 **أهداف جني الأرباح**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 الهدف الأول (TP1): ${take_profit_1:,.2f} (+{potential_profit_tp1:.2f}%)
🎯 الهدف الثاني (TP2): ${take_profit_2:,.2f} (+{potential_profit_tp2:.2f}%)
🎯 الهدف الثالث (TP3): ${take_profit_3:,.2f} (+{potential_profit_tp3:.2f}%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 **الحماية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛑 وقف الخسارة: ${stop_loss:,.2f} (-{potential_loss:.2f}%)
💵 حجم الصفقة: ${position_size:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **التقييم**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💪 نسبة الثقة: {confidence:.0f}%
✨ نسبة النجاح المتوقعة: {success_rate:.0f}%
📝 السبب: {reason}

{analysis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # Store trade
            self.open_trades[symbol] = {
                'open_time': datetime.now(),
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'take_profit_3': take_profit_3,
                'position_size': position_size,
                'trade_type': trade_type,
                'direction': direction,
                'current_price': current_price,
                'confidence': confidence,
            }
            
            # Send notification
            if self.telegram:
                self.telegram.send_message(message)
            
            logger.info(f"✅ Trade opened report sent for {symbol}")
            return message
        
        except Exception as e:
            logger.error(f"Error generating trade opened report: {e}")
            return f"❌ خطأ: {str(e)}"
    
    # ========================================================================
    # Trade Update Report
    # ========================================================================
    
    def report_trade_update(self, symbol: str, current_price: float, 
                           profit_loss: float, profit_loss_pct: float) -> Optional[str]:
        """
        Generate trade update report
        إنشاء تقرير تحديث الصفقة
        """
        try:
            if symbol not in self.open_trades:
                return None
            
            trade = self.open_trades[symbol]
            entry_price = trade['entry_price']
            stop_loss = trade['stop_loss']
            tp1 = trade['take_profit_1']
            tp2 = trade['take_profit_2']
            tp3 = trade['take_profit_3']
            position_size = trade['position_size']
            direction = trade['direction']
            
            # Calculate distances
            distance_to_tp1 = ((tp1 - current_price) / current_price) * 100
            distance_to_sl = ((current_price - stop_loss) / current_price) * 100
            
            # Determine next target
            if current_price >= tp3:
                next_target = "TP3 ✅"
                next_target_price = tp3
            elif current_price >= tp2:
                next_target = "TP3"
                next_target_price = tp3
            elif current_price >= tp1:
                next_target = "TP2"
                next_target_price = tp2
            else:
                next_target = "TP1"
                next_target_price = tp1
            
            # Duration
            duration = datetime.now() - trade['open_time']
            duration_str = f"{duration.seconds // 3600}h {(duration.seconds % 3600) // 60}m"
            
            # Profit/Loss emoji
            emoji = "📈" if profit_loss >= 0 else "📉"
            
            message = f"""
{emoji} **تحديث الصفقة: {symbol}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **السعر والربح**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💱 السعر الحالي: ${current_price:,.2f}
📊 الربح/الخسارة: {emoji} ${profit_loss:+.2f} ({profit_loss_pct:+.2f}%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **الأهداف**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 TP1: ${tp1:,.2f} ({distance_to_tp1:+.2f}%)
🔹 TP2: ${tp2:,.2f}
🔹 TP3: ${tp3:,.2f}
🔹 الهدف التالي: {next_target} (${next_target_price:,.2f})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 **الحماية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛑 وقف الخسارة: ${stop_loss:,.2f} ({distance_to_sl:+.2f}%)
💵 حجم الصفقة: ${position_size:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ **المدة:** {duration_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # Update current price
            trade['current_price'] = current_price
            
            if self.telegram:
                self.telegram.send_message(message)
            
            return message
        
        except Exception as e:
            logger.error(f"Error generating trade update report: {e}")
            return None
    
    # ========================================================================
    # Trade Closing Report
    # ========================================================================
    
    def report_trade_closed(self, trade_data: Dict) -> str:
        """
        Generate comprehensive trade closing report
        إنشاء تقرير شامل لإغلاق الصفقة
        """
        try:
            symbol = trade_data.get('symbol', 'Unknown')
            entry_price = trade_data.get('entry_price', 0)
            exit_price = trade_data.get('exit_price', 0)
            profit_loss = trade_data.get('profit_loss', 0)
            profit_loss_pct = trade_data.get('profit_loss_pct', 0)
            position_size = trade_data.get('position_size', 0)
            duration = trade_data.get('duration', 'Unknown')
            reason = trade_data.get('reason', 'Unknown')
            trade_type = trade_data.get('trade_type', 'SPOT')
            direction = trade_data.get('direction', 'BUY')
            stop_loss = trade_data.get('stop_loss', 0)
            take_profit_1 = trade_data.get('take_profit_1', 0)
            take_profit_2 = trade_data.get('take_profit_2', 0)
            take_profit_3 = trade_data.get('take_profit_3', 0)
            confidence = trade_data.get('confidence', 0)
            analysis = trade_data.get('analysis', '')
            
            # Determine which target was hit
            if exit_price >= take_profit_3:
                target_hit = "TP3 ✅✅✅"
            elif exit_price >= take_profit_2:
                target_hit = "TP2 ✅✅"
            elif exit_price >= take_profit_1:
                target_hit = "TP1 ✅"
            elif exit_price <= stop_loss:
                target_hit = "Stop Loss 🛑"
            else:
                target_hit = "Manual Exit"
            
            # Result emoji
            if profit_loss >= 0:
                result_emoji = "✅"
                result_text = "ناجحة"
            else:
                result_emoji = "❌"
                result_text = "خاسرة"
            
            # Update statistics
            self.trade_statistics['total_trades'] += 1
            if profit_loss >= 0:
                self.trade_statistics['winning_trades'] += 1
                self.trade_statistics['total_profit'] += profit_loss
            else:
                self.trade_statistics['losing_trades'] += 1
                self.trade_statistics['total_loss'] += abs(profit_loss)
            
            # Calculate averages
            if self.trade_statistics['winning_trades'] > 0:
                self.trade_statistics['avg_profit'] = \
                    self.trade_statistics['total_profit'] / self.trade_statistics['winning_trades']
            if self.trade_statistics['losing_trades'] > 0:
                self.trade_statistics['avg_loss'] = \
                    self.trade_statistics['total_loss'] / self.trade_statistics['losing_trades']
            
            # Calculate win rate
            if self.trade_statistics['total_trades'] > 0:
                self.trade_statistics['win_rate'] = \
                    (self.trade_statistics['winning_trades'] / self.trade_statistics['total_trades']) * 100
            
            message = f"""
{result_emoji} **صفقة {result_text} - مغلقة**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **معلومات الصفقة**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💱 **العملة:** {symbol}
📈 **الاتجاه:** {direction}
⚙️ **النوع:** {trade_type}
⏱️ **المدة:** {duration}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **الأسعار**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 نقطة الدخول: ${entry_price:,.2f}
📊 نقطة الخروج: ${exit_price:,.2f}
🛑 وقف الخسارة: ${stop_loss:,.2f}
📈 الهدف المحقق: {target_hit}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 **النتيجة المالية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 الربح/الخسارة: {result_emoji} ${profit_loss:+.2f}
📊 النسبة المئوية: {profit_loss_pct:+.2f}%
💵 حجم الصفقة: ${position_size:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **التفاصيل**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 سبب الإغلاق: {reason}
💪 نسبة الثقة: {confidence:.0f}%

{analysis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **الإحصائيات الكلية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 إجمالي الصفقات: {self.trade_statistics['total_trades']}
✅ الناجحة: {self.trade_statistics['winning_trades']}
❌ الخاسرة: {self.trade_statistics['losing_trades']}
📊 معدل النجاح: {self.trade_statistics['win_rate']:.1f}%

💰 إجمالي الأرباح: ${self.trade_statistics['total_profit']:+.2f}
💸 إجمالي الخسائر: ${-self.trade_statistics['total_loss']:+.2f}
💎 الربح الصافي: ${self.trade_statistics['total_profit'] - self.trade_statistics['total_loss']:+.2f}

📈 متوسط الربح: ${self.trade_statistics['avg_profit']:+.2f}
📉 متوسط الخسارة: ${-self.trade_statistics['avg_loss']:+.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # Store closed trade
            self.closed_trades.append({
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'duration': duration,
                'close_time': datetime.now(),
            })
            
            # Remove from open trades
            if symbol in self.open_trades:
                del self.open_trades[symbol]
            
            # Send notification
            if self.telegram:
                self.telegram.send_message(message)
            
            logger.info(f"✅ Trade closed report sent for {symbol}")
            return message
        
        except Exception as e:
            logger.error(f"Error generating trade closed report: {e}")
            return f"❌ خطأ: {str(e)}"
    
    # ========================================================================
    # Daily Statistics Report
    # ========================================================================
    
    def report_daily_statistics(self) -> str:
        """
        Generate daily statistics report
        إنشاء تقرير الإحصائيات اليومية
        """
        try:
            # Get today's trades
            today_trades = [t for t in self.closed_trades 
                           if t['close_time'].date() == datetime.now().date()]
            
            if not today_trades:
                return "📊 لا توجد صفقات اليوم"
            
            # Calculate today's stats
            today_profit = sum(t['profit_loss'] for t in today_trades)
            today_winning = sum(1 for t in today_trades if t['profit_loss'] >= 0)
            today_losing = len(today_trades) - today_winning
            today_win_rate = (today_winning / len(today_trades)) * 100 if today_trades else 0
            
            message = f"""
📊 **التقرير اليومي**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 **الصفقات**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 إجمالي الصفقات: {len(today_trades)}
✅ الناجحة: {today_winning}
❌ الخاسرة: {today_losing}
📊 معدل النجاح: {today_win_rate:.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **النتائج المالية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 الربح الصافي: ${today_profit:+.2f}
📈 أفضل صفقة: ${max(t['profit_loss'] for t in today_trades):+.2f}
📉 أسوأ صفقة: ${min(t['profit_loss'] for t in today_trades):+.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **الإحصائيات الكلية**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 إجمالي الصفقات: {self.trade_statistics['total_trades']}
✅ الناجحة: {self.trade_statistics['winning_trades']}
❌ الخاسرة: {self.trade_statistics['losing_trades']}
📊 معدل النجاح: {self.trade_statistics['win_rate']:.1f}%

💎 الربح الصافي الكلي: ${self.trade_statistics['total_profit'] - self.trade_statistics['total_loss']:+.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            if self.telegram:
                self.telegram.send_message(message)
            
            return message
        
        except Exception as e:
            logger.error(f"Error generating daily statistics report: {e}")
            return f"❌ خطأ: {str(e)}"
    
    # ========================================================================
    # Get Statistics
    # ========================================================================
    
    def get_statistics(self) -> Dict:
        """Get current statistics"""
        return self.trade_statistics.copy()
    
    def get_open_trades(self) -> Dict:
        """Get all open trades"""
        return self.open_trades.copy()
    
    def get_closed_trades(self) -> List:
        """Get all closed trades"""
        return self.closed_trades.copy()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize
    reporter = TradeReporter()
    
    # Test trade opening
    trade_data = {
        'symbol': 'BTC',
        'current_price': 45000,
        'entry_price': 44800,
        'entry_price_2': 44500,
        'stop_loss': 44000,
        'take_profit_1': 45500,
        'take_profit_2': 46200,
        'take_profit_3': 47000,
        'position_size': 400,
        'trade_type': 'SPOT',
        'direction': 'BUY',
        'confidence': 85,
        'reason': 'Strong bullish signal',
        'success_rate': 82,
    }
    
    report = reporter.report_trade_opened(trade_data)
    print(report)
