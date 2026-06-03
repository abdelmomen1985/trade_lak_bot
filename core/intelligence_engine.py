# ============================================================
# Trade Lak Bot - Advanced Intelligence Engine (Master Brain)
# تطبيق Trade لك - محرك الذكاء الرئيسي المتقدم
# ============================================================
# يدمج:
#   1. Machine Learning Models (ML)
#   2. Multi-Strategy Engine (5 strategies)
#   3. On-Chain Intelligence (Whale Tracker)
#   4. Order Book Intelligence
#   5. CoinGlass Data
#   6. Advanced Risk Management
#
# نظام النقاط النهائي:
#   -10 إلى +10 → يحدد القرار النهائي وقوته
# ============================================================

import logging
from typing import Dict, List, Tuple
from datetime import datetime
import numpy as np

from core.whale_tracker import WhaleTracker
from core.orderbook_intel import OrderBookIntel
from core.ml_model import MLModel, MLTrainer
from core.multi_strategy import MultiStrategyEngine
from core.advanced_risk_manager import AdvancedRiskManager
from core.wick_detection_engine import WickDetectionEngine
from core.whale_psychology_engine import WhaleProtectionSystem
from core.psychology_strategy_engine import PsychologyStrategyEngine
from core.economic_calendar_engine import EconomicCalendarEngine
try:
    from core.early_warning_system import EarlyWarningSystem
    _EWS_AVAILABLE = True
except ImportError as _ews_e:
    _EWS_AVAILABLE = False
    print(f'early_warning_system not available: {_ews_e}')
from core.market_indicators_engine import MarketIndicatorsEngine
from core.fake_break_detector import FakeBreakDetector
try:
    from core.cryptopanic_intelligence import CryptoPanicIntelligence
    from config.config import CRYPTOPANIC_API_KEY as _CP_KEY
    _CRYPTOPANIC_AVAILABLE = bool(_CP_KEY)
except Exception:
    _CRYPTOPANIC_AVAILABLE = False
    _CP_KEY = ""

logger = logging.getLogger(__name__)

# أوزان كل مصدر في القرار النهائي
WEIGHTS = {
    "fake_break": 0.32,         # 32% — استراتيجية دعم+كسر كاذب+تأكيد (الأقوى أداءً)
    "ml_model": 0.22,           # 22% — نموذج التعلم الآلي (رُفع: ميزات جديدة)
    "multi_strategy": 0.20,     # 20% — الاستراتيجيات المتعددة
    "onchain": 0.14,            # 14% — تحركات البلوكشين
    "orderbook": 0.07,          # 7%  — دفتر الأوامر
    "coinglass": 0.01,          # 1%  — بيانات CoinGlass
    "news_sentiment": 0.03,     # 3%  — تحليل أخبار CryptoPanic (رُفع)
    "wick_detection": 0.01,     # 1%  — كشف ذيول الشموع (فلتر أمان)
}


# قائمة العملات المستقرة — لا تُتداول
STABLECOINS = {
    'USDT','USDC','BUSD','DAI','TUSD','USDP','FRAX','USDD','FDUSD',
    'USDG','RLUSD','PYUSD','GUSD','SUSD','LUSD','CRVUSD','USDE','USDB',
    'USDX','CUSD','HUSD','EURS','USDK','USDJ','XUSD','USDQ',
    'USDN','USDH','USDR','USDV','USDY','USDZ','EURC','EUROC'
}

class AdvancedIntelligenceEngine:
    _adaptive_learning = None

    @classmethod
    def set_adaptive_learning(cls, engine):
        cls._adaptive_learning = engine

    """
    محرك الذكاء الرئيسي المتقدم — يجمع كل مصادر البيانات والذكاء الاصطناعي
    Advanced Master Brain — combines all data sources and AI for the smartest decision
    """

    def __init__(self, okx_client, coinglass_client, strategy_engine, total_capital=300):
        """
        Initialize Advanced Intelligence Engine
        
        Args:
            okx_client: OKX API client
            coinglass_client: CoinGlass API client
            strategy_engine: Technical strategy engine
            total_capital: Total trading capital
        """
        self.okx = okx_client
        self.coinglass = coinglass_client
        self.strategy = strategy_engine
        
        # AI Components
        self.ml_model = MLModel(model_dir="models")
        self.ml_trainer = MLTrainer(self.ml_model)
        self.multi_strategy_engine = MultiStrategyEngine(ml_model=self.ml_model)
        
        # Intelligence Components
        self.whale = WhaleTracker()
        self.ob_intel = OrderBookIntel(okx_client)
        
        # Risk Management
        self.risk_manager = AdvancedRiskManager(
            total_capital=total_capital,
            risk_per_trade_pct=0.02,
            daily_loss_limit_pct=5.0,
            correlation_threshold=0.7
        )
        
        # Wick Detection Engine
        self.wick_detector = WickDetectionEngine()
        
        # Whale Protection System
        self.whale_protector = WhaleProtectionSystem()
        
        # Psychology Strategy Engine
        self.psychology_engine = PsychologyStrategyEngine()
        
        # Economic Calendar Engine
        self.economic_calendar = EconomicCalendarEngine()
        
        # Market Indicators Engine
        self.market_indicators = MarketIndicatorsEngine()
        # استراتيجية Trade Lak: دعم + كسر كاذب + تأكيد
        self.fake_break_detector = FakeBreakDetector()
        # CryptoPanic News Intelligence
        self.cryptopanic = None
        if _CRYPTOPANIC_AVAILABLE:
            try:
                self.cryptopanic = CryptoPanicIntelligence(_CP_KEY)
                logger.info("✅ CryptoPanic News Intelligence initialized")
            except Exception as _e:
                logger.warning(f"⚠️ CryptoPanic init failed: {_e}")
        
        # Analysis history
        self.analysis_history = []
        # Early Warning System — نظام الإنذار المبكر للانهيارات
        self.early_warning = None
        if _EWS_AVAILABLE:
            try:
                self.early_warning = EarlyWarningSystem(
                    coinglass_client=coinglass_client,
                    okx_client=okx_client
                )
                logger.info("✅ Early Warning System initialized — 3 pre-crash indicators active")
            except Exception as _ews_init_e:
                logger.warning(f"⚠️ Early Warning System init failed: {_ews_init_e}")
        logger.info("✅ Advanced Intelligence Engine initialized")
    
    # ================================================================
    # التحليل الشامل / Full Analysis
    # ================================================================
    

    def _get_okx_market_type(self, symbol: str) -> str:
        """
        استعلام من OKX عن نوع السوق المتاح للعملة
        يستخدم cache لتجنب الطلبات المتكررة
        """
        try:
            if hasattr(self, 'okx') and self.okx and hasattr(self.okx, 'get_market_type'):
                return self.okx.get_market_type(symbol)
        except Exception:
            pass
        # fallback: افتراض أن كل العملات الرئيسية متاحة في كلا السوقين
        return 'both'

    def analyze(self, symbol: str, ohlcv_data: List[Dict], 
                coinglass_data: Dict = None, current_volume: float = None) -> Dict:
        """
        التحليل الكامل لعملة واحدة من جميع المصادر والذكاء الاصطناعي
        Full multi-source analysis for a single symbol
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            ohlcv_data: OHLCV candlestick data
            coinglass_data: CoinGlass market data
            current_volume: Current trading volume
        
        Returns:
            Comprehensive analysis with final signal and confidence
        """
        logger.info(f"🔍 تحليل شامل لـ {symbol}...")
        
        results = {}
        # ── تطبيق Adaptive Learning على الأوزان ──
        active_weights = dict(WEIGHTS)
        try:
            if hasattr(self, '_adaptive_learning') and self._adaptive_learning:
                regime = market_data_input.get('regime', 'unknown')
                adjustments = self._adaptive_learning.get_outperformance_adjustments(
                    {'signal': 0, 'confidence': 0}, regime
                )
                for key, factor in adjustments.items():
                    if key in active_weights:
                        active_weights[key] = min(0.45, max(0.01, active_weights[key] * factor))
                # إعادة التطبيع لتجمع إلى 1.0
                total = sum(active_weights.values())
                if total > 0:
                    active_weights = {k: v/total for k, v in active_weights.items()}
        except Exception as _al_e:
            pass  # fallback للأوزان الافتراضية
        weighted_score = 0
        signal_count = {'buy': 0, 'sell': 0, 'neutral': 0}
        
        # ── 0. Economic Calendar (Events & Volatility) ───────────────────────
        # فحص الأحداث الاقتصادية والتقارير
        economic_analysis = None
        try:
            # Check for upcoming events
            upcoming_events = self.economic_calendar.get_upcoming_events(hours_ahead=24)
            
            if upcoming_events:
                # Get the most critical event
                critical_events = [e for e in upcoming_events if e.risk_level == 'CRITICAL']
                high_events = [e for e in upcoming_events if e.risk_level == 'HIGH']
                
                economic_analysis = {
                    'upcoming_count': len(upcoming_events),
                    'critical_count': len(critical_events),
                    'high_count': len(high_events),
                    'events': []
                }
                
                # Analyze each event
                for alert in upcoming_events[:3]:
                    analysis = self.economic_calendar.analyze_event_impact(alert.event)
                    economic_analysis['events'].append({
                        'name': alert.event.name,
                        'time': alert.event.scheduled_time,
                        'impact': alert.event.impact.value,
                        'volatility': analysis.expected_volatility,
                        'recommendation': analysis.recommendation,
                        'confidence': analysis.confidence
                    })
                
                results['economic_calendar'] = economic_analysis
                logger.debug(f"  📅 Economic Events: {len(upcoming_events)} upcoming | Critical: {len(critical_events)}")
        except Exception as e:
            logger.warning(f"  ⚠️ Economic calendar check تعذّر: {e}")
            results['economic_calendar'] = {'upcoming_count': 0, 'critical_count': 0}
        
        # ── 1. Market Indicators (Crash, Pump, Recession, Altseason) ─────────────
        # فحص مؤشرات الأسواق - الانهيار والضخ والركود وموسم العملات البديلة
        market_indicators_analysis = None
        try:
            # Build market_data_input from ohlcv_data if not provided
            if not isinstance(ohlcv_data, list) or len(ohlcv_data) == 0:
                ohlcv_data = []
            # Normalize OHLCV to dict format
            def _to_dict(c):
                if isinstance(c, dict):
                    return c
                return {'timestamp': c[0], 'open': float(c[1]), 'high': float(c[2]),
                        'low': float(c[3]), 'close': float(c[4]),
                        'volume': float(c[5]) if len(c) > 5 else 0.0}
            ohlcv_data = [_to_dict(c) for c in ohlcv_data]
            # Derive market_data_input from OHLCV
            if len(ohlcv_data) >= 2:
                closes = [c['close'] for c in ohlcv_data[-20:]]
                volumes = [c.get('volume', 0) for c in ohlcv_data[-20:]]
                avg_vol = sum(volumes[:-1]) / max(len(volumes)-1, 1) if len(volumes) > 1 else 1
                price_change_1h = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else 0
                market_data_input = {
                    'volatility': max(closes) / min(closes) - 1 if min(closes) > 0 else 0.05,
                    'price_decline_1h': abs(price_change_1h) if price_change_1h < 0 else 0,
                    'price_increase_1h': price_change_1h if price_change_1h > 0 else 0,
                    'volume_ratio': volumes[-1] / avg_vol if avg_vol > 0 else 1,
                    'rsi': 50, 'macd_bearish': False, 'macd_bullish': False,
                    'support_broken': False, 'resistance_broken': False,
                    'funding_rate': 0, 'long_liquidations': 0, 'short_liquidations': 0,
                    'fear_index': 50, 'greed_index': 50, 'correlation': 0.5,
                    'momentum': price_change_1h, 'retail_fomo': 0,
                    'btc_dominance': 50, 'altcoin_performance': 0, 'altcoin_volume_ratio': 1,
                }
            else:
                market_data_input = {}
            # Simulate market data (in production, this would come from real data)
            market_data = {
                'volatility': market_data_input.get('volatility', 0.08),
                'price_decline_1h': market_data_input.get('price_decline_1h', 0),
                'price_increase_1h': market_data_input.get('price_increase_1h', 0),
                'volume_ratio': market_data_input.get('volume_ratio', 1),
                'rsi': market_data_input.get('rsi', 50),
                'macd_bearish': market_data_input.get('macd_bearish', False),
                'macd_bullish': market_data_input.get('macd_bullish', False),
                'support_broken': market_data_input.get('support_broken', False),
                'resistance_broken': market_data_input.get('resistance_broken', False),
                'funding_rate': market_data_input.get('funding_rate', 0),
                'long_liquidations': market_data_input.get('long_liquidations', 0),
                'short_liquidations': market_data_input.get('short_liquidations', 0),
                'fear_index': market_data_input.get('fear_index', 50),
                'greed_index': market_data_input.get('greed_index', 50),
                'correlation': market_data_input.get('correlation', 0.5),
                'momentum': market_data_input.get('momentum', 0),
                'retail_fomo': market_data_input.get('retail_fomo', 0),
                'btc_dominance': market_data_input.get('btc_dominance', 50),
                'altcoin_performance': market_data_input.get('altcoin_performance', 0),
                'altcoin_volume_ratio': market_data_input.get('altcoin_volume_ratio', 1),
                'altcoin_cap_growth': market_data_input.get('altcoin_cap_growth', 0),
                'gdp_growth': market_data_input.get('gdp_growth', 2),
                'unemployment_change': market_data_input.get('unemployment_change', 0),
                'yield_inversion': market_data_input.get('yield_inversion', False),
                'confidence_decline': market_data_input.get('confidence_decline', 0),
                'pmi': market_data_input.get('pmi', 50),
                'credit_spread': market_data_input.get('credit_spread', 1),
                'earnings_decline': market_data_input.get('earnings_decline', 0),
                'new_listings': market_data_input.get('new_listings', 0),
                'defi_tvl_growth': market_data_input.get('defi_tvl_growth', 0),
                'nft_volume': market_data_input.get('nft_volume', 0),
                'l2_adoption': market_data_input.get('l2_adoption', 0),
                'stablecoin_growth': market_data_input.get('stablecoin_growth', 0),
                'retail_participation': market_data_input.get('retail_participation', 0),
                'top_alts': ['ETH', 'SOL', 'AVAX', 'MATIC', 'ARB']
            }
            
            indicators_analysis = self.market_indicators.analyze_all_indicators(market_data)
            market_indicators_analysis = indicators_analysis
            results['market_indicators'] = indicators_analysis
            
            logger.debug(f"  📊 Market Condition: {indicators_analysis['market_condition']}")
        except Exception as e:
            logger.warning(f"  ⚠️ Market indicators check تعذّر: {e}")
            results['market_indicators'] = {'market_condition': 'Normal'}
        
        # ── 2. Psychology Strategy (Market Sentiment) ───────────────────────
        # تحليل نفسية السوق - الخوف والطمع
        psychology_analysis = None
        try:
            if len(ohlcv_data) >= 20:
                # Prepare market data for psychology analysis
                recent_prices = [c['close'] for c in ohlcv_data[-20:]]
                price_change_24h = ((recent_prices[-1] - recent_prices[0]) / recent_prices[0]) * 100
                volume_data = [c.get('volume', 0) for c in ohlcv_data[-20:]]
                volume_change = volume_data[-1] / np.mean(volume_data) if np.mean(volume_data) > 0 else 1
                
                # Calculate RSI
                deltas = np.diff(recent_prices)
                gains = np.where(deltas > 0, deltas, 0)
                losses = np.where(deltas < 0, -deltas, 0)
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                rs = avg_gain / avg_loss if avg_loss > 0 else 0
                rsi = 100 - (100 / (1 + rs))
                
                # Calculate volatility
                returns = np.diff(recent_prices) / recent_prices[:-1]
                volatility = np.std(returns)
                
                market_data = {
                    'price_change_24h': price_change_24h,
                    'volume_change': volume_change,
                    'volatility': volatility,
                    'rsi': rsi,
                    'higher_highs': recent_prices[-1] > recent_prices[-2] > recent_prices[-3],
                    'higher_lows': True,  # Simplified
                    'volume_24h': np.sum(volume_data),
                    'avg_volume_24h': np.mean(volume_data),
                    'bid_ask_spread_pct': 0.05,  # Default
                    'orderbook_depth': 50000,  # Default
                    'affected_pairs': []
                }
                
                psychology_analysis = self.psychology_engine.analyze_market_psychology(market_data)
                results['psychology'] = psychology_analysis
                
                logger.debug(f"  🧠 Psychology: {psychology_analysis['sentiment']['level']} | Score: {psychology_analysis['sentiment']['score']:.0f}")
        except Exception as e:
            logger.warning(f"  ⚠️ Psychology analysis تعذّر: {e}")
            results['psychology'] = {'sentiment': {'score': 0, 'level': 'NEUTRAL'}}
        
        # ── 1. Whale Protection (Safety Filter) ───────────────────────
        # فحص نشاط الحيتان - حماية من التلاعب
        whale_status = None
        try:
            if len(ohlcv_data) >= 10:
                # Add recent candles to whale detector
                for candle in ohlcv_data[-10:]:
                    self.whale_protector.add_candle(
                        open_price=candle['open'],
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        volume=candle.get('volume', 0)
                    )
                
                whale_status = self.whale_protector.get_status()
                results['whale_protection'] = whale_status
                
                logger.debug(f"  🐋 Whale Score: {whale_status['whale_score']:.0f} | Alerts: {whale_status['alerts_count']}")
        except Exception as e:
            logger.warning(f"  ⚠️ Whale protection تعذّر: {e}")
            results['whale_protection'] = {'whale_score': 0, 'alerts_count': 0}
        
        # ── 1. Wick Detection (Safety Filter) ───────────────────────
        # كشف ذيول الشموع - فلتر أمان
        wick_analysis = None
        try:
            if len(ohlcv_data) >= 1:
                latest_candle = ohlcv_data[-1]
                avg_volume = np.mean([c.get('volume', 0) for c in ohlcv_data[-10:]])
                
                wick_analysis = self.wick_detector.analyze_candle(
                    open_price=latest_candle['open'],
                    high_price=latest_candle['high'],
                    low_price=latest_candle['low'],
                    close_price=latest_candle['close'],
                    volume=latest_candle.get('volume', 0),
                    avg_volume=avg_volume
                )
                
                results['wick_detection'] = {
                    'danger_level': wick_analysis.danger_level.name,
                    'wick_type': wick_analysis.wick_type,
                    'is_trap': wick_analysis.is_trap,
                    'recommendation': wick_analysis.recommendation,
                    'score': wick_analysis.score,
                    'confidence': wick_analysis.confidence
                }
                
                logger.debug(f"  🕯️ Wick: {wick_analysis.wick_type} | Danger: {wick_analysis.danger_level.name}")
        except Exception as e:
            logger.warning(f"  ⚠️ Wick detection تعذّر: {e}")
            results['wick_detection'] = {'danger_level': 'SAFE', 'is_trap': False, 'score': 0}
        
        # ── 2. Machine Learning Analysis ────────────────────────────
        try:
            ml_analysis = self._ml_analysis(ohlcv_data, coinglass_data)
            results['ml'] = ml_analysis
            weighted_score += ml_analysis['score'] * active_weights.get('ml_model', WEIGHTS['ml_model'])
            if ml_analysis['signal'] == 1:
                signal_count['buy'] += 1
            elif ml_analysis['signal'] == -1:
                signal_count['sell'] += 1
            logger.debug(f"  🤖 ML: {ml_analysis['confidence']:.0%} confidence")
        except Exception as e:
            logger.warning(f"  ⚠️ ML تعذّر: {e}")
            results['ml'] = {"signal": 0, "score": 0, "confidence": 0}
        
        # ── 2. Multi-Strategy Analysis ──────────────────────────────
        try:
            multi_analysis = self._multi_strategy_analysis(ohlcv_data, coinglass_data)
            results['multi_strategy'] = multi_analysis
            weighted_score += multi_analysis['score'] * active_weights.get('multi_strategy', WEIGHTS['multi_strategy'])
            if multi_analysis['signal'] == 1:
                signal_count['buy'] += 1
            elif multi_analysis['signal'] == -1:
                signal_count['sell'] += 1
            logger.debug(f"  📊 Multi-Strategy: {multi_analysis['recommendation']}")
        except Exception as e:
            logger.warning(f"  ⚠️ Multi-Strategy تعذّر: {e}")
            results['multi_strategy'] = {"signal": 0, "score": 0, "recommendation": "HOLD"}
        
        # ── 3. On-Chain Analysis (Whale Tracker) ────────────────────
        try:
            onchain = self.whale.full_onchain_analysis(symbol)
            results['onchain'] = onchain
            raw_score = self._normalize_onchain_score(onchain['score'])
            weighted_score += raw_score * active_weights.get('onchain', WEIGHTS['onchain'])
            if 'BUY' in onchain['signal']:
                signal_count['buy'] += 1
            elif 'SELL' in onchain['signal']:
                signal_count['sell'] += 1
            logger.debug(f"  🐋 On-Chain: {onchain['signal']}")
        except Exception as e:
            logger.warning(f"  ⚠️ On-Chain تعذّر: {e}")
            results['onchain'] = {"signal": "NEUTRAL", "score": 0}
        
        # ── 4. Order Book Intelligence ──────────────────────────────
        try:
            ob = self.ob_intel.full_analysis(symbol, current_volume)
            results['orderbook'] = ob
            raw_score = ob['score'] / 5  # Normalize -5 to +5
            weighted_score += raw_score * active_weights.get('orderbook', WEIGHTS['orderbook'])
            if 'BUY' in ob['signal']:
                signal_count['buy'] += 1
            elif 'SELL' in ob['signal']:
                signal_count['sell'] += 1
            logger.debug(f"  📖 Order Book: {ob['signal']}")
        except Exception as e:
            logger.warning(f"  ⚠️ Order Book تعذّر: {e}")
            results['orderbook'] = {"signal": "NEUTRAL", "score": 0}
        
        # ── 5. CoinGlass Analysis ──────────────────────────────────
        try:
            cg = self.coinglass.analyze_signal(symbol)
            results['coinglass'] = cg
            raw_score = self._normalize_cg_score(cg)
            weighted_score += raw_score * active_weights.get('coinglass', WEIGHTS['coinglass'])
            if 'BUY' in cg.get('signal', ''):
                signal_count['buy'] += 1
            elif 'SELL' in cg.get('signal', ''):
                signal_count['sell'] += 1
            logger.debug(f"  💎 CoinGlass: {cg.get('signal', 'NEUTRAL')}")
        except Exception as e:
            logger.warning(f"  ⚠️ CoinGlass تعذّر: {e}")
            results['coinglass'] = {"signal": "NEUTRAL"}
        
        # ── 6. CryptoPanic News Sentiment ─────────────────────────────
        try:
            if self.cryptopanic:
                base_sym = symbol.split("/")[0].replace("-USDT","").replace("-SWAP","")
                news_data = self.cryptopanic.analyze_news_sentiment_trend(base_sym, limit=20)
                results["news_sentiment"] = news_data
                ns_score = news_data.get("sentiment_score", 50)
                # Convert 0-100 score to -1 to +1
                ns_normalized = (ns_score - 50) / 50
                weighted_score += ns_normalized * WEIGHTS.get("news_sentiment", 0.03)
                if ns_score >= 65:
                    signal_count["buy"] += 1
                elif ns_score <= 35:
                    signal_count["sell"] += 1
                logger.debug(f"  📰 News Sentiment: {news_data.get('overall_sentiment','NEUTRAL')} ({ns_score:.0f})")
            else:
                results["news_sentiment"] = {"overall_sentiment": "NEUTRAL", "sentiment_score": 50}
        except Exception as e:
            logger.warning(f"  ⚠️ CryptoPanic تعذّر: {e}")
            results["news_sentiment"] = {"overall_sentiment": "NEUTRAL", "sentiment_score": 50}
        # ── 7. Fake Break Detector (استراتيجية Trade Lak الأساسية) ──────────
        fake_break_result = None
        try:
            fake_break_result = self.fake_break_detector.analyze(ohlcv_data)
            results['fake_break'] = fake_break_result
            fb_score = fake_break_result.get('score', 0)
            weighted_score += fb_score * active_weights.get('fake_break', WEIGHTS['fake_break'])
            if fake_break_result.get('signal', 0) == 1:
                signal_count['buy'] += 2  # وزن مضاعف لأهمية الاستراتيجية
            elif fake_break_result.get('signal', 0) == -1:
                signal_count['sell'] += 2
            if fake_break_result.get('fake_break_detected'):
                logger.info(
                    f"  🎯 Fake Break: {fake_break_result.get('reason', '')} | "
                    f"نقاط={fb_score:.2f} | ثقة={fake_break_result.get('confidence', 0):.0f}%"
                )
            else:
                logger.debug(f"  🎯 Fake Break: {fake_break_result.get('reason', 'لا إشارة')}")
        except Exception as e:
            logger.warning(f"  ⚠️ FakeBreakDetector تعذّر: {e}")
            results['fake_break'] = {"signal": 0, "score": 0, "fake_break_detected": False}

        # ── نظام الإنذار المبكر للانهيار (Early Warning System) ──────
        try:
            if self.early_warning and ohlcv_data:
                last_candle = ohlcv_data[-1] if ohlcv_data else {}
                current_price = last_candle.get('close', 0)
                current_volume = last_candle.get('volume', 0)
                # جمع بيانات OI و Long/Short من coinglass إذا متاحة
                cg_result = results.get('coinglass', {})
                oi_val = cg_result.get('oi_change_1h', 0) * 1e9 if 'oi_change_1h' in cg_result else 0
                ls_ratio = cg_result.get('long_short_ratio', 0)
                fr_val = cg_result.get('funding_rate', 0)
                ew_data = {
                    'price': current_price,
                    'oi': oi_val,
                    'long_ratio': ls_ratio,
                    'volume': current_volume,
                    'funding_rate': fr_val,
                }
                ew_warning = self.early_warning.evaluate(symbol, ew_data)
                results['early_warning'] = ew_warning.to_dict()
                # إذا كان التحذير عالياً، اخفض النقاط
                if ew_warning.level.value == 'CRITICAL':
                    weighted_score = min(weighted_score, -0.3)
                    logger.warning(f"[EWS CRITICAL] {symbol}: score overridden to {weighted_score:.2f}")
                    # إرسال تحذير Telegram فوري
                    try:
                        from telegram_notifier import get_telegram_notifier
                        _tg = get_telegram_notifier()
                        _tg.send_crash_warning(
                            level='CRITICAL',
                            score=ew_warning.score,
                            indicators=ew_warning.indicators_triggered,
                            recommendation=ew_warning.recommendation,
                            symbol=symbol
                        )
                    except Exception as _tg_e:
                        logger.debug(f"EWS Telegram send failed: {_tg_e}")
                elif ew_warning.level.value == 'HIGH':
                    weighted_score = min(weighted_score, 0.1)
                    logger.warning(f"[EWS HIGH] {symbol}: score capped at {weighted_score:.2f}")
                    # إرسال تحذير Telegram
                    try:
                        from telegram_notifier import get_telegram_notifier
                        _tg = get_telegram_notifier()
                        _tg.send_crash_warning(
                            level='HIGH',
                            score=ew_warning.score,
                            indicators=ew_warning.indicators_triggered,
                            recommendation=ew_warning.recommendation,
                            symbol=symbol
                        )
                    except Exception as _tg_e:
                        logger.debug(f"EWS Telegram send failed: {_tg_e}")
                elif ew_warning.level.value == 'MEDIUM':
                    weighted_score *= 0.7  # تخفيض 30%
        except Exception as _ew_e:
            logger.debug(f"Early warning check failed: {_ew_e}")
            results['early_warning'] = {'level': 'NONE', 'score': 0}
        # ── القرار النهائي ─────────────────────────────────────────
        final = self._make_final_decision(weighted_score, results, signal_count, wick_analysis, fake_break_result, symbol)
        final['symbol'] = symbol
        final['all_data'] = results
        final['timestamp'] = datetime.now().isoformat()
        
        # Store in history
        self.analysis_history.append(final)
        
        logger.info(
            f"✅ القرار النهائي لـ {symbol}: {final['final_signal']} | "
            f"النقاط: {weighted_score:.2f} | الثقة: {final['confidence']:.0f}%"
        )
        
        return final
    
    # ================================================================
    # تحليلات فردية / Individual Analyses
    # ================================================================
    
    def _ml_analysis(self, ohlcv_data: List[Dict], coinglass_data: Dict = None) -> Dict:
        """
        Machine Learning analysis
        """
        try:
            features = self.ml_model.extract_features(ohlcv_data, coinglass_data)
            prediction = self.ml_model.predict(features)
            
            signal = prediction['signal']
            confidence = prediction['confidence']
            
            # Convert to -1 to +1 scale
            score = (confidence * 2 - 1) if signal == 1 else -(confidence * 2 - 1)
            
            return {
                'signal': signal,
                'confidence': confidence,
                'score': score,
                'rf_prob': prediction['rf_prob'],
                'gb_prob': prediction['gb_prob'],
                'model_version': prediction['model_version']
            }
        except Exception as e:
            logger.error(f"❌ ML analysis error: {e}")
            return {'signal': 0, 'confidence': 0, 'score': 0}
    
    def _multi_strategy_analysis(self, ohlcv_data: List[Dict], 
                                 coinglass_data: Dict = None) -> Dict:
        """
        Multi-Strategy analysis
        """
        try:
            result = self.multi_strategy_engine.analyze(ohlcv_data, coinglass_data)
            
            # Convert recommendation to score
            recommendation_scores = {
                'STRONG_BUY': 1.0,
                'BUY': 0.6,
                'HOLD': 0.0,
                'SELL': -0.6,
                'STRONG_SELL': -1.0
            }
            
            score = recommendation_scores.get(result['recommendation'], 0)
            signal = 1 if result['final_signal'] == 1 else (-1 if result['final_signal'] == -1 else 0)
            
            return {
                'signal': signal,
                'confidence': result['confidence'],
                'score': score,
                'recommendation': result['recommendation'],
                'weighted_score': result['weighted_score'],
                'strategy_signals': result['strategy_signals']
            }
        except Exception as e:
            logger.error(f"❌ Multi-strategy analysis error: {e}")
            return {'signal': 0, 'confidence': 0, 'score': 0, 'recommendation': 'HOLD'}
    
    # ================================================================
    # تطبيع النقاط / Score Normalization
    # ================================================================
    
    def _normalize_onchain_score(self, score: float) -> float:
        """تحويل نقاط On-Chain (-10 إلى +10) إلى (-1 إلى +1)"""
        return max(-1, min(1, score / 10))
    
    def _normalize_cg_score(self, cg_signal: Dict) -> float:
        """تحويل إشارة CoinGlass إلى نقاط"""
        signal = cg_signal.get('signal', 'NEUTRAL')
        mapping = {
            "STRONG_BUY": 1.0, "BUY": 0.6,
            "NEUTRAL": 0.0,
            "SELL": -0.6, "STRONG_SELL": -1.0,
        }
        return mapping.get(signal, 0.0)
    
    # ================================================================
    # القرار النهائي / Final Decision
    # ================================================================
    
    def _check_ema50_4h(self, symbol: str, direction: str = 'buy') -> bool:
        """
        شرط إلزامي: السعر فوق EMA50 على 4H للشراء — يمنع الدخول في تريند هابط
        درس مستفاد من PEPE: البوت دخل في تريند هابط واضح على 4H
        """
        try:
            ohlcv_4h = self.okx.get_ohlcv(symbol, '4h', limit=60)
            if not ohlcv_4h or len(ohlcv_4h) < 50:
                return True  # إذا لم تتوفر البيانات، لا نمنع الدخول
            # CCXT format: [timestamp, open, high, low, close, volume]
            closes = [c[4] if isinstance(c, (list, tuple)) else c['close'] for c in ohlcv_4h]
            k = 2 / (50 + 1)
            ema50 = closes[0]
            for c in closes[1:]:
                ema50 = c * k + ema50 * (1 - k)
            current_price = closes[-1]
            if direction == 'buy':
                result = current_price > ema50
                if not result:
                    logger.info(f"  🚫 EMA50 4H فلتر: {symbol} السعر ({current_price:.6f}) تحت EMA50 ({ema50:.6f}) — لا دخول شراء")
                return result
            else:  # sell/short
                result = current_price < ema50
                if not result:
                    logger.info(f"  🚫 EMA50 4H فلتر: {symbol} السعر ({current_price:.6f}) فوق EMA50 ({ema50:.6f}) — لا دخول بيع")
                return result
        except Exception as e:
            logger.debug(f"  ⚠️ EMA50 4H check error for {symbol}: {e}")
            return True  # عند الخطأ، لا نمنع الدخول

    def _make_final_decision(self, weighted_score: float, results: Dict,
                            signal_count: Dict, wick_analysis=None, fake_break_result=None, symbol: str = None) -> Dict:
        """
        اتخاذ القرار النهائي بناءً على كل المصادر
        Make the final decision based on all sources
        """
        # حساب الثقة (0-100%)
        confidence = min(abs(weighted_score) * 100, 95)
        
        # فلاتر أمان خماسية: الحيتان + الذيول + النفسية + الأحداث الاقتصادية + مؤشرات الأسواق
        whale_safety_filter = True
        wick_safety_filter = True
        psychology_safety_filter = True
        economic_safety_filter = True
        market_indicators_filter = True
        
        # فحص نشاط الحيتان
        whale_data = results.get('whale_protection', {})
        if whale_data.get('whale_score', 0) > 70:
            whale_safety_filter = False
            confidence = max(confidence * 0.6, 15)
        
        # فحص ذيول الشموع
        if wick_analysis:
            from core.wick_detection_engine import WickDangerLevel
            if wick_analysis.danger_level in (WickDangerLevel.CRITICAL, WickDangerLevel.HIGH):
                wick_safety_filter = False
                confidence = max(confidence * 0.5, 20)
        
        # فحص مؤشرات الأسواق
        market_indicators_data = results.get('market_indicators', {})
        if market_indicators_data:
            market_condition = market_indicators_data.get('market_condition', 'Normal')
            
            # Check crash signal
            crash_prob = market_indicators_data.get('crash', {}).get('probability', 0)
            if crash_prob > 0.80:
                market_indicators_filter = False
                confidence = max(confidence * 0.2, 5)
            elif crash_prob > 0.60:
                market_indicators_filter = False
                confidence = max(confidence * 0.4, 10)
            
            # Check recession signal
            recession_prob = market_indicators_data.get('recession', {}).get('probability', 0)
            if recession_prob > 0.80:
                market_indicators_filter = False
                confidence = max(confidence * 0.2, 5)
            
            # Altseason is good for trading
            altseason_prob = market_indicators_data.get('altseason', {}).get('probability', 0)
            if altseason_prob > 0.80 and market_condition == 'Altseason':
                confidence = min(confidence * 1.2, 95)
        
        # فحص الأحداث الاقتصادية
        economic_data = results.get('economic_calendar', {})
        if economic_data:
            critical_count = economic_data.get('critical_count', 0)
            high_count = economic_data.get('high_count', 0)
            
            if critical_count > 0:
                economic_safety_filter = False
                confidence = max(confidence * 0.3, 5)
            elif high_count > 0:
                economic_safety_filter = False
                confidence = max(confidence * 0.5, 15)
        
        # فحص نفسية السوق والسيولة
        psychology_data = results.get('psychology', {})
        if psychology_data:
            liquidity_risk = psychology_data.get('liquidity', {}).get('risk_level', 'LOW')
            if liquidity_risk == 'CRITICAL':
                psychology_safety_filter = False
                confidence = max(confidence * 0.4, 10)
            
            # تجنب التداول في فترات الخطر المعروفة
            risky_periods = psychology_data.get('risky_periods', [])
            if risky_periods and risky_periods[0].get('confidence', 0) > 0.7:
                psychology_safety_filter = False
                confidence = max(confidence * 0.5, 15)
        
        # عدد المصادر المتوافقة
        buy_count = signal_count['buy']
        sell_count = signal_count['sell']
        total_sources = buy_count + sell_count + signal_count['neutral']
        
        # تعزيز الثقة عند توافق المصادر
        if buy_count >= 3:
            confidence = min(confidence + 25, 98)
        elif sell_count >= 3:
            confidence = min(confidence + 25, 98)
        
        # ── شرط EMA50 على 4H (فلتر التريند الإلزامي) ──────────────────────────
        # درس مستفاد: لا دخول شراء إذا كان السعر تحت EMA50 على 4H (تريند هابط)
        ema50_4h_buy_ok = True
        ema50_4h_sell_ok = True
        if symbol and hasattr(self, 'okx') and self.okx:
            if weighted_score > 0:  # إشارة شراء محتملة
                ema50_4h_buy_ok = self._check_ema50_4h(symbol, 'buy')
            elif weighted_score < 0:  # إشارة بيع محتملة
                ema50_4h_sell_ok = self._check_ema50_4h(symbol, 'sell')

        # القرار النهائي (مع فلاتر أمان ستة: الحيتان + الذيول + النفسية + الأحداث + مؤشرات + EMA50)
        if not whale_safety_filter or not wick_safety_filter or not psychology_safety_filter or not economic_safety_filter or not market_indicators_filter:
            # إذا كان هناك نشاط حيتان أو فخ ذيول أو خطر نفسي أو حدث اقتصادي أو مؤشرات سوق خطرة، تجنب الدخول
            final_signal = "NEUTRAL"
            direction = None
            market_type = "none"
            action_level = "HOLD"
        elif weighted_score >= 0.5 and buy_count >= 2 and ema50_4h_buy_ok:
            final_signal = "STRONG_BUY"
            direction = "LONG"
            # تحديد السوق بناءً على توفر العملة الفعلي على OKX
            _okx_market = self._get_okx_market_type(symbol)
            if _okx_market == 'both':
                market_type = "both"   # Spot + Futures Long
            elif _okx_market == 'spot':
                market_type = "spot"   # Spot فقط
            elif _okx_market == 'futures':
                market_type = "futures"  # Futures فقط (لا Spot)
            else:
                market_type = "none"
            action_level = "AGGRESSIVE"
        elif weighted_score >= 0.25 and buy_count >= 1 and ema50_4h_buy_ok:
            final_signal = "BUY"
            direction = "LONG"
            _okx_market = self._get_okx_market_type(symbol)
            if _okx_market in ('both', 'spot'):
                market_type = "spot"   # Spot فقط للإشارات المعتدلة
            elif _okx_market == 'futures':
                market_type = "futures"  # Futures إذا لا Spot
            else:
                market_type = "none"
            action_level = "MODERATE"
        elif weighted_score <= -0.5 and sell_count >= 2 and ema50_4h_sell_ok:
            final_signal = "STRONG_SELL"
            direction = "SHORT"
            _okx_market = self._get_okx_market_type(symbol)
            if _okx_market in ('both', 'futures'):
                market_type = "futures"  # Futures Short
            else:
                market_type = "none"  # لا يمكن Short بدون Futures
            action_level = "AGGRESSIVE"
        elif weighted_score <= -0.25 and sell_count >= 1 and ema50_4h_sell_ok:
            final_signal = "SELL"
            direction = "SHORT"
            _okx_market = self._get_okx_market_type(symbol)
            if _okx_market in ('both', 'futures'):
                market_type = "futures"
            else:
                market_type = "none"
            action_level = "MODERATE"
        else:
            final_signal = "NEUTRAL"
            direction = None
            market_type = "none"
            action_level = "HOLD"
        
        # جمع أسباب القرار
        reasons = []
        
        # Whale protection reason
        if whale_data.get('whale_score', 0) > 70:
            score = whale_data.get('whale_score', 0)
            reasons.append(f"🐋 ⚠️ نشاط حيتان ({score:.0f}/100)")
        elif whale_data.get('alerts_count', 0) > 0:
            alerts = whale_data.get('alerts', [])
            if alerts and len(alerts) > 0:
                desc = alerts[0].get('description', '')
                if desc:
                    reasons.append(f"🐋 {desc}")
        
        # Wick detection reason (safety filter)
        if wick_analysis:
            if wick_analysis.danger_level.name in ('CRITICAL', 'HIGH'):
                reasons.append(f"🕯️ ⚠️ {wick_analysis.wick_type} - {wick_analysis.recommendation}")
            elif wick_analysis.danger_level.name == 'MEDIUM':
                reasons.append(f"🕯️ {wick_analysis.wick_type} (انتظر تأكيد)")
        
        # ML reason
        if results.get('ml', {}).get('confidence', 0) > 0.6:
            reasons.append(f"🤖 ML: {results['ml']['confidence']:.0%}")
        
        # Multi-strategy reason
        if results.get('multi_strategy', {}).get('recommendation') != 'HOLD':
            reasons.append(f"📊 {results['multi_strategy']['recommendation']}")
        
        # On-chain reason
        onchain_sigs = results.get('onchain', {}).get('signals', [])
        if onchain_sigs:
            reasons.extend([f"🐋 {sig}" for sig in onchain_sigs[:1]])
        
        # Order book reason
        ob_sig = results.get('orderbook', {}).get('signal', '')
        if ob_sig not in ('NEUTRAL', ''):
            reasons.append(f"📖 {ob_sig}")
        
        # Market Indicators reason
        if market_indicators_data and market_indicators_data.get('market_condition') != 'Normal':
            market_condition = market_indicators_data.get('market_condition')
            
            if market_condition == 'Crash':
                crash_prob = market_indicators_data.get('crash', {}).get('probability', 0)
                reasons.append(f"📊 ⚠️ احتمال انهيار: {crash_prob:.0%}")
            elif market_condition == 'Recession':
                recession_prob = market_indicators_data.get('recession', {}).get('probability', 0)
                reasons.append(f"📊 ⚠️ احتمال ركود: {recession_prob:.0%}")
            elif market_condition == 'Altseason':
                altseason_prob = market_indicators_data.get('altseason', {}).get('probability', 0)
                reasons.append(f"📊 🟢 موسم العملات البديلة: {altseason_prob:.0%}")
        
        # Economic Calendar reason
        if economic_data and economic_data.get('critical_count', 0) > 0:
            events = economic_data.get('events', [])
            if events:
                event = events[0]
                reasons.append(f"📅 ⚠️ حدث اقتصادي: {event['name']}")
        
        # Psychology reason
        if psychology_data:
            sentiment_level = psychology_data.get('sentiment', {}).get('level', 'NEUTRAL')
            sentiment_score = psychology_data.get('sentiment', {}).get('score', 0)
            reasons.append(f"🧠 {sentiment_level} ({sentiment_score:.0f})")
            
            if not psychology_safety_filter:
                liquidity_risk = psychology_data.get('liquidity', {}).get('risk_level', 'LOW')
                if liquidity_risk == 'CRITICAL':
                    reasons.append(f"💧 ⚠️ سيولة منخفضة جداً")
                
                risky_periods = psychology_data.get('risky_periods', [])
                if risky_periods:
                    period = risky_periods[0].get('period', '')
                    reasons.append(f"⏰ ⚠️ فترة خطرة: {period}")
        
        # CoinGlass reason
        cg_sig = results.get('coinglass', {}).get('signal', '')
        if cg_sig not in ('NEUTRAL', ''):
            reasons.append(f"💎 {cg_sig}")
        
        return {
            "final_signal": final_signal,
            "direction": direction,
            "market_type": market_type,
            "action_level": action_level,
            "weighted_score": float(weighted_score),
            "confidence": float(confidence),
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "total_sources": total_sources,
            "reasons": reasons[:3],  # Top 3 reasons
        }
    
    # ================================================================
    # المراقبة المستمرة / Continuous Monitoring
    # ================================================================
    
    def quick_check(self, symbol: str, current_price: float, 
                   current_volume: float = None) -> Tuple[bool, str]:
        """
        فحص سريع لعملة مفتوحة (للمراقبة المستمرة)
        Quick check for an open position
        
        Returns:
            (should_exit, reason)
        """
        try:
            # فحص دفتر الأوامر فقط (سريع)
            ob = self.ob_intel.full_analysis(symbol, current_volume)
            
            # إذا تحول دفتر الأوامر إلى بيع قوي = خروج مبكر
            if ob['signal'] in ('STRONG_SELL', 'VERY_STRONG_SELL'):
                return True, f"📖 Order book turned {ob['signal']}"
            
            # فحص ارتفاع الحجم في اتجاه عكسي
            vol = ob.get('volume', {})
            if vol.get('spike') and ob['signal'] in ('SELL', 'STRONG_SELL'):
                return True, "📖 High volume with sell pressure"
            
            return False, None
        
        except Exception as e:
            logger.debug(f"Quick check error for {symbol}: {e}")
            return False, None
    
    # ================================================================
    # إدارة المخاطر / Risk Management
    # ================================================================
    
    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed"""
        return self.risk_manager.can_trade()
    
    def can_open_position(self, symbol: str, open_positions: List[str]) -> Tuple[bool, str]:
        """Check if position can be opened"""
        return self.risk_manager.can_open_position(symbol, open_positions)
    
    def calculate_position_size(self, entry_price: float, stop_loss: float,
                               available_capital: float = None) -> float:
        """Calculate optimal position size"""
        return self.risk_manager.calculate_position_size(entry_price, stop_loss, available_capital)
    
    def record_trade(self, trade_data: Dict):
        """Record completed trade for ML training and risk management"""
        self.risk_manager.record_trade(trade_data)
        self.ml_trainer.record_trade(trade_data)
    
    def add_price(self, symbol: str, price: float):
        """Add price for correlation calculation"""
        self.risk_manager.add_price(symbol, price)
    
    # ================================================================
    # الإحصائيات والحالة / Statistics and Status
    # ================================================================
    
    def get_status(self) -> Dict:
        """Get comprehensive engine status"""
        return {
            'risk_management': self.risk_manager.get_status(),
            'ml_stats': self.ml_model.get_model_stats(),
            'ml_training_stats': self.ml_trainer.get_training_stats(),
            'analysis_count': len(self.analysis_history),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_ml_feature_importance(self) -> Dict:
        """Get ML model feature importance"""
        return self.ml_model.get_feature_importance()
    
    def train_ml_model(self) -> bool:
        """Train ML model on collected data"""
        return self.ml_model.train()
