# ============================================================
# Trade Lak Bot v4 — Advanced AI Trading Bot (Spot + Futures)
# بوت Trade لك v4 — بوت تداول ذكي متقدم (سبوت + فيوتشر)
# ============================================================
# ✨ ميزات متقدمة:
#   🤖 Machine Learning - يتعلم من كل صفقة
#   📊 5 استراتيجيات متوازية
#   🛡️ نظام إدارة مخاطر فائق (Circuit Breaker)
#   🐋 تتبع الحيتان والمحافظ الكبيرة
#   📖 تحليل دفتر الأوامر
#   💎 بيانات CoinGlass
#   📢 تنبيهات تليجرام فورية
# ============================================================

import sys
import time
import logging
import os
from datetime import datetime
from pathlib import Path

# Create directories
os.makedirs('logs', exist_ok=True)
os.makedirs('models', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import configuration
from config.config import (
    CHECK_INTERVAL, TOTAL_CAPITAL, DRY_RUN,
    TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    MAX_SPOT_TRADES, MAX_FUTURES_TRADES,
    BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_PRIVATE_KEY_PATH
)

# Import core modules
from core.okx_client import OKXClient
from core.bybit_client import create_bybit_client
from core.exchange_router import ExchangeRouter
from core.coinglass_client import CoinGlassClient
from core.strategy import StrategyEngine
from core.market_scanner import MarketScanner
from core.intelligence_engine import AdvancedIntelligenceEngine
from core.ml_model import MLModel, MLTrainer
from core.multi_strategy import MultiStrategyEngine
from core.advanced_risk_manager import AdvancedRiskManager

# Import utilities
from utils.notifier import Notifier, TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.telegram_chat_handler import TelegramChatHandler
from utils.advanced_chat_handler import AdvancedChatHandler
from utils.recommendation_engine import RecommendationEngine
from utils.trade_reporter import TradeReporter
import utils.dual_channel_signals as dcs


class TradeLakBotV4:
    """
    Trade Lak Bot v4 — Advanced AI Trading Bot with ML
    بوت Trade لك v4 — بوت تداول ذكي متقدم مع التعلم الآلي
    """

    def __init__(self):
        """Initialize the bot with all advanced components"""
        
        logger.info("=" * 80)
        logger.info("  🚀 Trade Lak Bot v4 — Advanced AI Trading Bot")
        logger.info("  🤖 Machine Learning | 📊 Multi-Strategy | 🛡️ Advanced Risk Management")
        logger.info("  🐋 Whale Tracking | 📖 Order Book Intel | 💎 CoinGlass")
        logger.info("=" * 80)
        
        # Initialize API clients
        self.okx = OKXClient()
        self.coinglass = CoinGlassClient()
        # Initialize Bybit client (RSA)
        try:
            self.bybit = create_bybit_client(
                api_key=BYBIT_API_KEY,
                api_secret=BYBIT_API_SECRET,
                private_key_path=BYBIT_API_PRIVATE_KEY_PATH
            )
            if self.bybit.is_available():
                logger.info("[Bybit] Bybit Client initialized - RSA")
            else:
                logger.warning("[Bybit] Bybit Client: connection unavailable")
        except Exception as _bybit_err:
            logger.warning(f"[Bybit] Bybit Client init error: {_bybit_err}")
            self.bybit = None
        
        # Initialize ExchangeRouter (OKX primary + Bybit secondary)
        try:
            self.router = ExchangeRouter(self.okx, self.bybit)
            logger.info("[Router] Exchange Router initialized — OKX (primary) + Bybit (secondary)")
        except Exception as _router_err:
            logger.warning(f"[Router] init error: {_router_err}")
            self.router = None
        # Initialize strategy engines
        self.strategy = StrategyEngine(self.okx, self.coinglass)
        self.scanner = MarketScanner(self.okx, exchange_router=self.router)
        
        # Initialize Advanced Intelligence Engine (with ML, Multi-Strategy, Risk Manager)
        self.intel = AdvancedIntelligenceEngine(
            okx_client=self.okx,
            coinglass_client=self.coinglass,
            strategy_engine=self.strategy,
            total_capital=TOTAL_CAPITAL
        )
        
        # Initialize notifiers
        self.notifier = Notifier()
        self.trade_log = TradeLogger()
        
        # Initialize Telegram notifier
        self.telegram = None
        self.chat_handler = None
        self.advanced_chat = None
        self.recommendation_engine = None
        self.trade_reporter = None
        
        if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN:
            self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            logger.info("✅ Telegram Notifier initialized")
            
            # Initialize Chat Handler
            try:
                self.chat_handler = TelegramChatHandler(self.okx, self.intel)
                logger.info("✅ Telegram Chat Handler initialized")
            except Exception as e:
                logger.error(f"Error initializing chat handler: {e}")
                self.chat_handler = None
            
            # Initialize Advanced Chat Handler
            try:
                self.advanced_chat = AdvancedChatHandler(self.okx, self.intel)
                logger.info("✅ Advanced Chat Handler initialized")
            except Exception as e:
                logger.error(f"Error initializing advanced chat handler: {e}")
                self.advanced_chat = None
            
            # Initialize Recommendation Engine
            try:
                self.recommendation_engine = RecommendationEngine(self.okx, self.intel)
                logger.info("✅ Recommendation Engine initialized")
            except Exception as e:
                logger.error(f"Error initializing recommendation engine: {e}")
                self.recommendation_engine = None
            
            # Initialize Trade Reporter
            try:
                self.trade_reporter = TradeReporter(self.telegram)
                logger.info("✅ Trade Reporter initialized")
            except Exception as e:
                logger.error(f"Error initializing trade reporter: {e}")
                self.trade_reporter = None
            
            # Start message handler
            try:
                self.telegram.set_message_handler(self.handle_telegram_message)
            except Exception as e:
                logger.warning(f"Warning: set_message_handler not available: {e}")
        
        # Bot state
        self.running = True
        self.last_daily_report = datetime.now().date()
        self.last_ml_training = datetime.now()
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        mode = "🧪 اختبار (Dry Run)" if DRY_RUN else "💰 تداول حقيقي (LIVE)"
        logger.info(f"{mode} | رأس المال: ${TOTAL_CAPITAL}")
        logger.info(f"Max Spot Trades: {MAX_SPOT_TRADES} | Max Futures Trades: {MAX_FUTURES_TRADES}")
    
    # ================================================================
    # Main Loop / الحلقة الرئيسية
    # ================================================================
    
    def run(self):
        """Main bot loop"""
        logger.info("🤖 البوت يعمل الآن... اضغط Ctrl+C للإيقاف")
        
        # Send startup notification
        if self.telegram:
            self.telegram.detect_chat_id()
            self.telegram.notify_bot_started()
        
        while self.running:
            try:
                self._scan_and_trade()
                self._monitor_open_trades()
                self._check_daily_report()
                self._check_ml_training()
                
                logger.info(f"⏳ انتظار {CHECK_INTERVAL} ثانية...\n")
                time.sleep(CHECK_INTERVAL)
            
            except KeyboardInterrupt:
                logger.info("🛑 إيقاف البوت...")
                self.running = False
                if self.telegram:
                    self.telegram.notify_bot_stopped("Manual stop")
            
            except Exception as e:
                logger.error(f"❌ خطأ غير متوقع: {e}")
                if self.telegram:
                    self.telegram.notify_error("Bot Error", str(e))
                time.sleep(30)
    
    # ================================================================
    # Market Scanning & Trading / فحص السوق والتداول
    # ================================================================
    
    def _scan_and_trade(self):
        """
        Scan market and execute trades using Advanced Intelligence Engine
        فحص السوق وتنفيذ الصفقات باستخدام محرك الذكاء المتقدم
        """
        logger.info("━━━ 🔍 فحص السوق الكامل (ذكاء متقدم + ML) ━━━")
        
        # Check if trading is allowed (Circuit Breaker)
        can_trade, reason = self.intel.can_trade()
        if not can_trade:
            logger.warning(f"⚠️ Trading blocked: {reason}")
            if self.telegram:
                self.telegram.notify_warning("Trading Blocked", reason)
            return
        
        # Check balance
        balance = self.okx.get_balance()
        if balance['free'] < 10:
            logger.warning(f"⚠️ رصيد منخفض: ${balance['free']:.2f}")
            return
        
        # Find best trading opportunities
        opportunities = self.scanner.find_best_trades(
            intelligence_engine=self.intel,
            max_results=5
        )
        
        if not opportunities:
            logger.info("ℹ️ لا توجد فرص مناسبة حالياً")
            return
        
        # Process each opportunity
        for opp in opportunities:
            symbol = opp.get('symbol')
            
            # Check if we can open new position (correlation filter)
            open_positions = list(self.strategy.open_spot_trades.keys()) + \
                           list(self.strategy.open_futures_trades.keys())
            
            can_open, reason = self.intel.can_open_position(symbol, open_positions)
            if not can_open:
                logger.warning(f"⚠️ {symbol}: {reason}")
                continue
            
            # Decide trade action
            actions = self.strategy.decide_trade(opp)
            if not actions:
                continue
            
            for action in actions:
                # إرسال إشارة الصفقة إلى قناة Trade Lak Signal
                try:
                    entry_price = opp.get('price', 0)
                    if entry_price > 0:
                        sl_price = entry_price * 0.97   # SL افتراضي 3%
                        tp1 = entry_price * 1.04         # TP1 4%
                        tp2 = entry_price * 1.07         # TP2 7%
                        tp3 = entry_price * 1.12         # TP3 12%
                        dcs.send_trade_signal(
                            symbol=opp.get('symbol', ''),
                            sector=opp.get('sector', 'Other'),
                            current_price=entry_price,
                            entry_low=entry_price * 0.999,
                            entry_high=entry_price * 1.001,
                            tp1=tp1, tp2=tp2, tp3=tp3,
                            sl=sl_price,
                            confidence=opp.get('confidence', 0) * 100,
                            reasons=opp.get('reasons', []),
                        )
                except Exception as _dcs_err:
                    logger.debug(f"[DCS] خطأ في إرسال الإشارة: {_dcs_err}")
                self._execute_entry(opp, action)
    
    # ================================================================
    # Trade Execution / تنفيذ الصفقات
    # ================================================================
    
    def _execute_entry(self, opportunity, action):
        """Execute a trade entry"""
        try:
            symbol = opportunity['symbol']
            market = action['market']
            direction = action['direction']
            ohlcv = opportunity.get('ohlcv', [])
            confidence = opportunity.get('confidence', 0)
            reasons = opportunity.get('reasons', [])
            
            # Get current price
            ticker = (self.router.get_ticker if self.router else self.okx.get_ticker)(symbol, market)
            if not ticker:
                logger.warning(f"❌ Could not get ticker for {symbol}")
                return
            
            entry_price = ticker['price']
            
            # Calculate Stop Loss and Take Profit
            sl, tp = self.strategy.calculate_smart_sl_tp(entry_price, ohlcv, direction)
            
            # Calculate position size using Risk Manager
            balance = self.okx.get_balance()
            if market == 'spot':
                available_capital = balance['spot_allocated']
                max_trades = MAX_SPOT_TRADES
                current_trades = len(self.strategy.open_spot_trades)
            else:
                available_capital = balance['futures_allocated']
                max_trades = MAX_FUTURES_TRADES
                current_trades = len(self.strategy.open_futures_trades)
            
            # Check max trades limit
            if current_trades >= max_trades:
                logger.warning(f"⚠️ Max {market} trades ({max_trades}) reached")
                return
            
            # Calculate position size
            position_size = self.intel.calculate_position_size(entry_price, sl, available_capital)
            amount_usdt = position_size
            
            logger.info(
                f"▶️ 执行 {direction} | {symbol} | {market.upper()} | "
                f"Entry: ${entry_price:.6f} | SL: ${sl:.6f} | TP: ${tp:.6f} | "
                f"Amount: ${amount_usdt:.2f} | Confidence: {confidence:.0%}"
            )
            
            # Execute order
            order = None
            if direction == 'SPOT_BUY':
                if self.router:
                    order = self.router.spot_buy(symbol, amount_usdt)
                else:
                    order = self.okx.spot_buy(symbol, amount_usdt)
            elif direction == 'LONG':
                if self.router:
                    order = self.router.futures_open_long(symbol, amount_usdt)
                else:
                    order = self.okx.futures_open_long(symbol, amount_usdt)
            elif direction == 'SHORT':
                if self.router:
                    order = self.router.futures_open_short(symbol, amount_usdt)
                else:
                    order = self.okx.futures_open_short(symbol, amount_usdt)
            
            if not order:
                logger.error(f"❌ Order failed for {symbol}")
                return
            
            # Record trade
            trade_record = {
                'entry_price': entry_price,
                'stop_loss': sl,
                'take_profit': tp,
                'amount_usdt': amount_usdt,
                'amount_coin': amount_usdt / entry_price,
                'direction': direction,
                'open_time': datetime.now(),
                'best_price': entry_price,
                'confidence': confidence,
                'reasons': reasons,
            }
            
            if market == 'spot':
                self.strategy.open_spot_trades[symbol] = trade_record
            else:
                self.strategy.open_futures_trades[symbol] = trade_record
            # حفظ الصفقات فوراً
            self.strategy._save_trades()
            
            # Send notifications using Trade Reporter
            if self.trade_reporter:
                trade_data = {
                    'symbol': symbol,
                    'current_price': entry_price,
                    'entry_price': entry_price,
                    'entry_price_2': entry_price * 0.995,  # 0.5% lower
                    'stop_loss': sl,
                    'take_profit_1': tp,
                    'take_profit_2': tp * 1.02,  # 2% higher
                    'take_profit_3': tp * 1.04,  # 4% higher
                    'position_size': amount_usdt,
                    'trade_type': market.upper(),
                    'direction': 'BUY' if 'BUY' in direction else 'SHORT',
                    'confidence': confidence,
                    'reason': ', '.join(reasons) if reasons else 'Strong signal detected',
                    'analysis': f"Confidence: {confidence:.0%}",
                    'success_rate': 75,  # Default
                }
                self.trade_reporter.report_trade_opened(trade_data)
            else:
                # Fallback to old notification
                self.notifier.send_telegram(
                    f"🟢 صفقة جديدة: {symbol}\n"
                    f"النوع: {direction} ({market.upper()})\n"
                    f"الدخول: ${entry_price:.6f}\n"
                    f"SL: ${sl:.6f} | TP: ${tp:.6f}\n"
                    f"المبلغ: ${amount_usdt:.2f} | الثقة: {confidence:.0%}"
                )
            
            if self.telegram and not self.trade_reporter:
                # Check for wick trap warnings
                wick_data = opp.get('analysis', {}).get('all_data', {}).get('wick_detection', {})
                if wick_data and wick_data.get('danger_level') in ('HIGH', 'CRITICAL'):
                    self.telegram.notify_wick_trap(
                        symbol=symbol,
                        wick_type=wick_data.get('wick_type', 'Unknown'),
                        danger_level=wick_data.get('danger_level', 'UNKNOWN'),
                        recommendation=wick_data.get('recommendation', 'Be careful'),
                        score=wick_data.get('score', 0)
                    )
                
                self.telegram.notify_trade_opened({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'stop_loss': sl,
                    'take_profit': tp,
                    'trade_type': market.upper(),
                    'direction': direction,
                    'position_size': amount_usdt,
                    'confidence': confidence
                })
        
        except Exception as e:
            logger.error(f"❌ Error executing entry: {e}")
            if self.telegram:
                self.telegram.send_message(f"❌ خطأ في تنفيذ الصفقة: {str(e)}")
    
    # ================================================================
    # Trade Monitoring / مراقبة الصفقات
    # ================================================================
    
    def _monitor_open_trades(self):
        """Monitor all open trades"""
        total = len(self.strategy.open_spot_trades) + len(self.strategy.open_futures_trades)
        if total == 0:
            return
        
        logger.info(f"━━━ 👁️ مراقبة {total} صفقة مفتوحة ━━━")
        
        # Monitor Spot trades
        for symbol in list(self.strategy.open_spot_trades.keys()):
            self._check_and_close(symbol, 'spot')
        
        # Monitor Futures trades
        for symbol in list(self.strategy.open_futures_trades.keys()):
            self._check_and_close(symbol, 'futures')
        # مراقبة أهداف إشارات dual_channel_signals
        try:
            dcs.check_targets_and_liquidity()
        except Exception as _dcs_err:
            logger.debug(f"[DCS] خطأ في check_targets_and_liquidity: {_dcs_err}")
    
    def _check_and_close(self, symbol, market):
        """Check and close a trade if needed"""
        try:
            ticker = (self.router.get_ticker if self.router else self.okx.get_ticker)(symbol, market)
            if not ticker:
                return
            
            current_price = ticker['price']
            current_volume = ticker.get('volume', None)
            
            # Add price for correlation tracking
            self.intel.add_price(symbol, current_price)
            
            # Check exit conditions
            should_exit, reason = self.strategy.check_exit_conditions(
                symbol, current_price, market
            )
            
            # Additional smart exit check from Intelligence Engine
            if not should_exit:
                should_exit, reason = self.intel.quick_check(
                    symbol, current_price, current_volume
                )
                if should_exit:
                    reason = f"🧠 Smart Exit: {reason}"
            
            if should_exit:
                self._execute_exit(symbol, current_price, reason, market)
        
        except Exception as e:
            logger.error(f"❌ Error checking {symbol} ({market}): {e}")
    
    # ================================================================
    # Trade Exit / إغلاق الصفقات
    # ================================================================
    
    def _execute_exit(self, symbol, exit_price, reason, market, current_price=None):
        """Close a trade"""
        try:
            trades = self.strategy.open_spot_trades if market == 'spot' \
                     else self.strategy.open_futures_trades
            trade = trades.get(symbol)
            if not trade:
                return
            
            entry_price = trade['entry_price']
            amount_coin = trade['amount_coin']
            amount_usdt = trade['amount_usdt']
            direction = trade['direction']
            duration_min = int((datetime.now() - trade['open_time']).seconds / 60)
            
            # Execute close order
            if direction == 'SPOT_BUY':
                (self.router.spot_sell if self.router else self.okx.spot_sell)(symbol, amount_coin)
            elif direction == 'LONG':
                (self.router.futures_close_long if self.router else self.okx.futures_close_long)(symbol, amount_coin)
            elif direction == 'SHORT':
                (self.router.futures_close_short if self.router else self.okx.futures_close_short)(symbol, amount_coin)
            
            # Calculate P&L
            if direction in ('SPOT_BUY', 'LONG'):
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                pnl_usdt = (exit_price - entry_price) * amount_coin
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                pnl_usdt = (entry_price - exit_price) * amount_coin
            
            # Update statistics
            self.total_trades += 1
            if pnl_usdt > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            # Send notifications
            emoji = "✅" if pnl_usdt >= 0 else "❌"
            self.notifier.send_telegram(
                f"{emoji} إغلاق صفقة: {symbol}\n"
                f"السبب: {reason}\n"
                f"الدخول: ${entry_price:.6f} | الخروج: ${exit_price:.6f}\n"
                f"الربح/الخسارة: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)\n"
                f"المدة: {duration_min} دقيقة"
            )
            
            if self.telegram:
                self.telegram.notify_trade_closed({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit_loss': pnl_usdt,
                    'profit_loss_pct': pnl_pct,
                    'duration': f"{duration_min} min",
                    'close_reason': reason
                })
            
            # Log trade
            self.trade_log.log_trade({
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'market': market,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'stop_loss': trade['stop_loss'],
                'take_profit': trade['take_profit'],
                'amount_usdt': amount_usdt,
                'pnl_usdt': pnl_usdt,
                'pnl_pct': pnl_pct,
                'reason': reason,
                'duration_min': duration_min,
                'confidence': trade.get('confidence', 0),
            })
            
            # Send comprehensive trade closed report
            if self.trade_reporter:
                duration_str = f"{duration_min // 60}h {duration_min % 60}m" if duration_min >= 60 else f"{duration_min}m"
                trade_close_data = {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit_loss': pnl_usdt,
                    'profit_loss_pct': pnl_pct,
                    'position_size': amount_usdt,
                    'duration': duration_str,
                    'reason': reason,
                    'trade_type': market.upper(),
                    'direction': direction,
                    'stop_loss': trade['stop_loss'],
                    'take_profit_1': trade['take_profit'],
                    'take_profit_2': trade['take_profit'] * 1.02,
                    'take_profit_3': trade['take_profit'] * 1.04,
                    'confidence': trade.get('confidence', 0),
                    'analysis': f"Trade closed with {pnl_pct:+.2f}% return",
                }
                self.trade_reporter.report_trade_closed(trade_close_data)
            
            # Record for ML training
            self.intel.record_trade({
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit_loss': pnl_usdt,
                'profit_loss_pct': pnl_pct,
                'timestamp': datetime.now()
            })
            
            # Remove from open trades
            if symbol in trades:
                del trades[symbol]
            # حفظ الصفقات بعد الإغلاق
            self.strategy._save_trades()
        
        except Exception as e:
            logger.error(f"❌ Error executing exit: {e}")
            if self.telegram:
                self.telegram.send_message(f"❌ خطأ في إغلاق الصفقة {symbol}: {str(e)}")
    
    # ================================================================
    # Daily Report / التقرير اليومي
    # ================================================================
    
    def _check_daily_report(self):
        """Send daily report"""
        today = datetime.now().date()
        if today > self.last_daily_report:
            try:
                stats = self.trade_log.get_stats()
                balance = self.okx.get_balance()
                
                report = (
                    f"📊 التقرير اليومي\n"
                    f"الصفقات: {stats.get('total_trades', 0)}\n"
                    f"الناجحة: {stats.get('winning_trades', 0)} ✅\n"
                    f"الخاسرة: {stats.get('losing_trades', 0)} ❌\n"
                    f"نسبة النجاح: {stats.get('win_rate', 0):.1%}\n"
                    f"إجمالي الربح: ${stats.get('total_pnl', 0):+.2f}\n"
                    f"رأس المال الحالي: ${balance.get('total', 0):.2f}"
                )
                
                self.notifier.send_telegram(report)
                
                if self.telegram:
                    self.telegram.notify_daily_stats({
                        'total_trades': stats.get('total_trades', 0),
                        'winning_trades': stats.get('winning_trades', 0),
                        'losing_trades': stats.get('losing_trades', 0),
                        'win_rate': stats.get('win_rate', 0),
                        'daily_pnl': stats.get('total_pnl', 0),
                        'daily_pnl_pct': stats.get('total_pnl', 0) / TOTAL_CAPITAL * 100
                    })
                
                self.last_daily_report = today
            
            except Exception as e:
                logger.error(f"❌ Error sending daily report: {e}")
    
    # ================================================================
    # ML Training / تدريب نموذج التعلم الآلي
    # ================================================================
    
    def _check_ml_training(self):
        """Check if ML model should be trained"""
        try:
            # Train ML model every hour or every 50 trades
            now = datetime.now()
            if (now - self.last_ml_training).seconds > 3600 or \
               len(self.intel.ml_trainer.trade_history) % 50 == 0:
                
                logger.info("🤖 تدريب نموذج التعلم الآلي...")
                success = self.intel.train_ml_model()
                
                if success:
                    logger.info("✅ تم تدريب النموذج بنجاح")
                    stats = self.intel.get_status()
                    logger.info(f"📊 ML Stats: {stats['ml_stats']}")
                    self.last_ml_training = now
                else:
                    logger.warning("⚠️ فشل تدريب النموذج")
        
        except Exception as e:
            logger.error(f"❌ Error in ML training: {e}")
    
    # ================================================================
    # Telegram Chat Handler / معالج الحوار عبر Telegram
    # ================================================================
    
    def handle_telegram_message(self, message):
        """
        Handle incoming Telegram messages
        معالجة الرسائل الواردة من Telegram
        """
        try:
            if not self.advanced_chat:
                logger.warning("Advanced chat handler not initialized")
                return
            
            user_message = message.get('text', '').strip()
            if not user_message:
                return
            
            logger.info(f"💬 Telegram Message: {user_message}")
            
            # Handle advanced conversation
            response = self.advanced_chat.handle_advanced_conversation(user_message)
            
            if self.telegram:
                self.telegram.send_message(response)
        
        except Exception as e:
            logger.error(f"❌ Error handling telegram message: {e}")
            if self.telegram:
                self.telegram.send_message(f"❌ حدث خطأ: {str(e)}")
    
    # ================================================================
    # Recommendation System / نظام التوصيات
    # ================================================================
    
    def generate_and_send_recommendations(self):
        """
        Generate and send trading recommendations
        إنشاء وإرسال توصيات التداول
        """
        try:
            if not self.recommendation_engine:
                logger.warning("Recommendation engine not initialized")
                return
            
            logger.info("━━━ 📊 إنشاء التوصيات ━━━")
            
            # Get top trading opportunities
            opportunities = self.scanner.find_best_trades(
                intelligence_engine=self.intel,
                max_results=5
            )
            
            if not opportunities:
                logger.info("ℹ️ لا توجد فرص توصية حالياً")
                return
            
            # Generate recommendations for each opportunity
            for opp in opportunities:
                try:
                    symbol = opp.get('symbol')
                    current_price = opp.get('current_price', 0)
                    analysis_data = opp.get('analysis', {}).get('all_data', {})
                    
                    # Generate recommendation
                    rec = self.recommendation_engine.generate_recommendation(
                        symbol=symbol,
                        current_price=current_price,
                        analysis_data=analysis_data
                    )
                    
                    if rec and rec['success_rate'] >= 60:  # Only send high confidence recommendations
                        # Format and send
                        message = self.recommendation_engine.format_recommendation_for_telegram(rec)
                        
                        if self.telegram:
                            self.telegram.send_message(message)
                        
                        logger.info(f"✅ Recommendation sent for {symbol} (Success Rate: {rec['success_rate']}%)")
                
                except Exception as e:
                    logger.error(f"Error generating recommendation for {opp.get('symbol')}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error in recommendation generation: {e}")


# ================================================================
# Main Entry Point
# ================================================================

if __name__ == "__main__":
    try:
        bot = TradeLakBotV4()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
