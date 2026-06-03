# ============================================================
# Trade Lak Bot - Multi-Strategy Module
# تطبيق Trade لك - وحدة الاستراتيجيات المتعددة
# ============================================================

import numpy as np
import pandas as pd
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """Strategy types"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    VOLUME_PROFILE = "volume_profile"
    ML_BASED = "ml_based"


@dataclass
class StrategySignal:
    """Strategy signal output"""
    strategy_type: StrategyType
    signal: int  # 1 = BUY, -1 = SELL, 0 = HOLD
    confidence: float  # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    reasoning: str
    score: float  # 0-10


class MomentumStrategy:
    """
    Momentum Strategy - Trend Following
    استراتيجية الزخم - متابعة الاتجاه
    
    Looks for strong uptrends and downtrends based on:
    - Price momentum (rate of change)
    - Volume confirmation
    - Moving average alignment
    """
    
    def __init__(self):
        self.name = "Momentum Strategy"
        self.lookback_period = 20
    
    def analyze(self, ohlcv_data: List[Dict]) -> StrategySignal:
        """
        Analyze market for momentum signals
        """
        try:
            df = pd.DataFrame(ohlcv_data)
            if len(df) < self.lookback_period:
                return StrategySignal(
                    strategy_type=StrategyType.MOMENTUM,
                    signal=0, confidence=0, entry_price=0, stop_loss=0,
                    take_profit=0, reasoning="Not enough data", score=0
                )
            
            # Calculate momentum
            close = df['close'].values
            momentum = close[-1] - close[-self.lookback_period]
            momentum_pct = (momentum / close[-self.lookback_period]) * 100
            
            # Calculate volume trend
            volume = df['volume'].values
            avg_volume = volume[-self.lookback_period:].mean()
            current_volume = volume[-1]
            volume_ratio = current_volume / avg_volume
            
            # Moving averages
            sma_10 = df['close'].rolling(window=10).mean().iloc[-1]
            sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
            sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
            
            current_price = close[-1]
            
            # Signal logic
            signal = 0
            confidence = 0
            score = 0
            reasoning = ""
            
            # Strong uptrend
            if (momentum_pct > 5 and volume_ratio > 1.2 and 
                sma_10 > sma_20 > sma_50):
                signal = 1
                confidence = min(0.9, 0.5 + (momentum_pct / 100))
                score = min(10, 5 + (momentum_pct / 10))
                reasoning = f"Strong uptrend: {momentum_pct:.2f}% momentum, {volume_ratio:.2f}x volume"
            
            # Strong downtrend
            elif (momentum_pct < -5 and volume_ratio > 1.2 and 
                  sma_10 < sma_20 < sma_50):
                signal = -1
                confidence = min(0.9, 0.5 + (abs(momentum_pct) / 100))
                score = min(10, 5 + (abs(momentum_pct) / 10))
                reasoning = f"Strong downtrend: {momentum_pct:.2f}% momentum, {volume_ratio:.2f}x volume"
            
            # Calculate SL and TP
            atr = self._calculate_atr(df)
            if signal == 1:
                stop_loss = current_price - (atr * 2)
                take_profit = current_price + (atr * 3)
            elif signal == -1:
                stop_loss = current_price + (atr * 2)
                take_profit = current_price - (atr * 3)
            else:
                stop_loss = current_price - atr
                take_profit = current_price + atr
            
            return StrategySignal(
                strategy_type=StrategyType.MOMENTUM,
                signal=signal,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                score=score
            )
        
        except Exception as e:
            logger.error(f"❌ Momentum strategy error: {e}")
            return StrategySignal(
                strategy_type=StrategyType.MOMENTUM,
                signal=0, confidence=0, entry_price=0, stop_loss=0,
                take_profit=0, reasoning=f"Error: {e}", score=0
            )
    
    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )
            atr = np.mean(tr[-period:])
            return atr
        except:
            return 0


class MeanReversionStrategy:
    """
    Mean Reversion Strategy - Overbought/Oversold
    استراتيجية العودة للمتوسط - الشراء عند الانخفاض الزائد
    
    Looks for extremes in RSI and Bollinger Bands
    """
    
    def __init__(self):
        self.name = "Mean Reversion Strategy"
    
    def analyze(self, ohlcv_data: List[Dict]) -> StrategySignal:
        """
        Analyze market for mean reversion signals
        """
        try:
            df = pd.DataFrame(ohlcv_data)
            if len(df) < 20:
                return StrategySignal(
                    strategy_type=StrategyType.MEAN_REVERSION,
                    signal=0, confidence=0, entry_price=0, stop_loss=0,
                    take_profit=0, reasoning="Not enough data", score=0
                )
            
            # Calculate RSI
            rsi = self._calculate_rsi(df['close'], period=14)
            current_rsi = rsi.iloc[-1]
            
            # Calculate Bollinger Bands
            sma = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            bb_upper = sma + (std * 2)
            bb_lower = sma - (std * 2)
            
            current_price = df['close'].iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            
            signal = 0
            confidence = 0
            score = 0
            reasoning = ""
            
            # Oversold (buy signal)
            if current_rsi < 30 and current_price < current_bb_lower:
                signal = 1
                confidence = min(0.85, (30 - current_rsi) / 30)
                score = min(10, 7 - (current_rsi / 10))
                reasoning = f"Oversold: RSI={current_rsi:.1f}, Price below lower BB"
            
            # Overbought (sell signal)
            elif current_rsi > 70 and current_price > current_bb_upper:
                signal = -1
                confidence = min(0.85, (current_rsi - 70) / 30)
                score = min(10, 7 - ((100 - current_rsi) / 10))
                reasoning = f"Overbought: RSI={current_rsi:.1f}, Price above upper BB"
            
            # Calculate SL and TP
            atr = self._calculate_atr(df)
            if signal == 1:
                stop_loss = current_bb_lower - atr
                take_profit = sma.iloc[-1]
            elif signal == -1:
                stop_loss = current_bb_upper + atr
                take_profit = sma.iloc[-1]
            else:
                stop_loss = current_price - atr
                take_profit = current_price + atr
            
            return StrategySignal(
                strategy_type=StrategyType.MEAN_REVERSION,
                signal=signal,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                score=score
            )
        
        except Exception as e:
            logger.error(f"❌ Mean reversion strategy error: {e}")
            return StrategySignal(
                strategy_type=StrategyType.MEAN_REVERSION,
                signal=0, confidence=0, entry_price=0, stop_loss=0,
                take_profit=0, reasoning=f"Error: {e}", score=0
            )
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
        except:
            return [50] * len(prices)
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )
            atr = np.mean(tr[-period:])
            return atr
        except:
            return 0


class BreakoutStrategy:
    """
    Breakout Strategy - Price breaks key levels
    استراتيجية الاختراق - السعر يخترق المستويات الرئيسية
    """
    
    def __init__(self):
        self.name = "Breakout Strategy"
        self.lookback_period = 20
    
    def analyze(self, ohlcv_data: List[Dict]) -> StrategySignal:
        """
        Analyze market for breakout signals
        """
        try:
            df = pd.DataFrame(ohlcv_data)
            if len(df) < self.lookback_period:
                return StrategySignal(
                    strategy_type=StrategyType.BREAKOUT,
                    signal=0, confidence=0, entry_price=0, stop_loss=0,
                    take_profit=0, reasoning="Not enough data", score=0
                )
            
            # Find resistance and support
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            resistance = high[-self.lookback_period:].max()
            support = low[-self.lookback_period:].min()
            current_price = close[-1]
            
            # Volume confirmation
            volume = df['volume'].values
            avg_volume = volume[-self.lookback_period:].mean()
            current_volume = volume[-1]
            volume_ratio = current_volume / avg_volume
            
            signal = 0
            confidence = 0
            score = 0
            reasoning = ""
            
            # Breakout above resistance
            if current_price > resistance and volume_ratio > 1.5:
                signal = 1
                confidence = min(0.9, 0.5 + (volume_ratio - 1) / 2)
                score = min(10, 6 + (volume_ratio - 1))
                reasoning = f"Breakout above resistance: {resistance:.2f}, Volume: {volume_ratio:.2f}x"
            
            # Breakdown below support
            elif current_price < support and volume_ratio > 1.5:
                signal = -1
                confidence = min(0.9, 0.5 + (volume_ratio - 1) / 2)
                score = min(10, 6 + (volume_ratio - 1))
                reasoning = f"Breakdown below support: {support:.2f}, Volume: {volume_ratio:.2f}x"
            
            # Calculate SL and TP
            atr = self._calculate_atr(df)
            if signal == 1:
                stop_loss = support
                take_profit = current_price + (resistance - support)
            elif signal == -1:
                stop_loss = resistance
                take_profit = current_price - (resistance - support)
            else:
                stop_loss = support
                take_profit = resistance
            
            return StrategySignal(
                strategy_type=StrategyType.BREAKOUT,
                signal=signal,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                score=score
            )
        
        except Exception as e:
            logger.error(f"❌ Breakout strategy error: {e}")
            return StrategySignal(
                strategy_type=StrategyType.BREAKOUT,
                signal=0, confidence=0, entry_price=0, stop_loss=0,
                take_profit=0, reasoning=f"Error: {e}", score=0
            )
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )
            atr = np.mean(tr[-period:])
            return atr
        except:
            return 0


class VolumeProfileStrategy:
    """
    Volume Profile Strategy - Trading at high volume levels
    استراتيجية ملف الحجم - التداول عند مستويات الحجم العالي
    """
    
    def __init__(self):
        self.name = "Volume Profile Strategy"
    
    def analyze(self, ohlcv_data: List[Dict]) -> StrategySignal:
        """
        Analyze market for volume profile signals
        """
        try:
            df = pd.DataFrame(ohlcv_data)
            if len(df) < 10:
                return StrategySignal(
                    strategy_type=StrategyType.VOLUME_PROFILE,
                    signal=0, confidence=0, entry_price=0, stop_loss=0,
                    take_profit=0, reasoning="Not enough data", score=0
                )
            
            # Volume analysis
            volume = df['volume'].values
            price = df['close'].values
            
            # Find volume-weighted average price (VWAP)
            vwap = (df['close'] * df['volume']).sum() / df['volume'].sum()
            current_price = price[-1]
            current_volume = volume[-1]
            
            # Volume trend
            avg_volume = volume[-10:].mean()
            volume_trend = (current_volume - avg_volume) / avg_volume
            
            # Price position relative to VWAP
            price_diff_pct = (current_price - vwap) / vwap * 100
            
            signal = 0
            confidence = 0
            score = 0
            reasoning = ""
            
            # High volume at support (buy signal)
            if current_volume > avg_volume * 1.5 and current_price < vwap:
                signal = 1
                confidence = min(0.85, 0.5 + (volume_trend / 2))
                score = min(10, 6 + volume_trend)
                reasoning = f"High volume at support: {current_volume:.0f} vs avg {avg_volume:.0f}"
            
            # High volume at resistance (sell signal)
            elif current_volume > avg_volume * 1.5 and current_price > vwap:
                signal = -1
                confidence = min(0.85, 0.5 + (volume_trend / 2))
                score = min(10, 6 + volume_trend)
                reasoning = f"High volume at resistance: {current_volume:.0f} vs avg {avg_volume:.0f}"
            
            # Calculate SL and TP
            atr = self._calculate_atr(df)
            if signal == 1:
                stop_loss = current_price - atr
                take_profit = vwap + (vwap - current_price)
            elif signal == -1:
                stop_loss = current_price + atr
                take_profit = vwap - (current_price - vwap)
            else:
                stop_loss = current_price - atr
                take_profit = current_price + atr
            
            return StrategySignal(
                strategy_type=StrategyType.VOLUME_PROFILE,
                signal=signal,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                score=score
            )
        
        except Exception as e:
            logger.error(f"❌ Volume profile strategy error: {e}")
            return StrategySignal(
                strategy_type=StrategyType.VOLUME_PROFILE,
                signal=0, confidence=0, entry_price=0, stop_loss=0,
                take_profit=0, reasoning=f"Error: {e}", score=0
            )
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )
            atr = np.mean(tr[-period:])
            return atr
        except:
            return 0


class MultiStrategyEngine:
    """
    Multi-Strategy Engine - Combines all 5 strategies
    محرك الاستراتيجيات المتعددة - يدمج كل 5 استراتيجيات
    """
    
    def __init__(self, ml_model=None):
        self.strategies = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            BreakoutStrategy(),
            VolumeProfileStrategy()
        ]
        self.ml_model = ml_model
        self.strategy_weights = {
            StrategyType.MOMENTUM: 0.25,
            StrategyType.MEAN_REVERSION: 0.20,
            StrategyType.BREAKOUT: 0.25,
            StrategyType.VOLUME_PROFILE: 0.20,
            StrategyType.ML_BASED: 0.10
        }
        logger.info("✅ Multi-Strategy Engine initialized")
    
    def analyze(self, ohlcv_data: List[Dict], coinglass_data: Dict = None) -> Dict:
        """
        Analyze market with all strategies
        تحليل السوق بكل الاستراتيجيات
        
        Returns:
            {
                'final_signal': 1 (buy), -1 (sell), 0 (hold),
                'confidence': 0-1,
                'strategy_signals': [...],
                'weighted_score': 0-10,
                'recommendation': 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL'
            }
        """
        try:
            signals = []
            total_score = 0
            
            # Run all traditional strategies
            for strategy in self.strategies:
                signal = strategy.analyze(ohlcv_data)
                signals.append(signal)
                total_score += signal.score * self.strategy_weights[signal.strategy_type]
            
            # Add ML signal if available
            ml_signal = None
            if self.ml_model:
                try:
                    features = self.ml_model.extract_features(ohlcv_data, coinglass_data)
                    ml_pred = self.ml_model.predict(features)
                    
                    if ml_pred['confidence'] > 0.6:
                        ml_signal_val = 1 if ml_pred['signal'] == 1 else -1
                        ml_score = ml_pred['confidence'] * 10
                    else:
                        ml_signal_val = 0
                        ml_score = 0
                    
                    ml_signal = StrategySignal(
                        strategy_type=StrategyType.ML_BASED,
                        signal=ml_signal_val,
                        confidence=ml_pred['confidence'],
                        entry_price=ohlcv_data[-1]['close'],
                        stop_loss=0,
                        take_profit=0,
                        reasoning=f"ML confidence: {ml_pred['confidence']:.2%}",
                        score=ml_score
                    )
                    signals.append(ml_signal)
                    total_score += ml_score * self.strategy_weights[StrategyType.ML_BASED]
                except Exception as e:
                    logger.warning(f"⚠️ ML signal error: {e}")
            
            # Aggregate signals
            buy_signals = sum(1 for s in signals if s.signal == 1)
            sell_signals = sum(1 for s in signals if s.signal == -1)
            total_signals = len(signals)
            
            # Final decision
            if buy_signals > total_signals * 0.6:
                final_signal = 1
                confidence = buy_signals / total_signals
            elif sell_signals > total_signals * 0.6:
                final_signal = -1
                confidence = sell_signals / total_signals
            else:
                final_signal = 0
                confidence = 0
            
            # Recommendation
            if final_signal == 1:
                recommendation = "STRONG_BUY" if confidence > 0.75 else "BUY"
            elif final_signal == -1:
                recommendation = "STRONG_SELL" if confidence > 0.75 else "SELL"
            else:
                recommendation = "HOLD"
            
            return {
                'final_signal': final_signal,
                'confidence': float(confidence),
                'strategy_signals': [
                    {
                        'strategy': s.strategy_type.value,
                        'signal': s.signal,
                        'confidence': s.confidence,
                        'score': s.score,
                        'reasoning': s.reasoning
                    }
                    for s in signals
                ],
                'weighted_score': float(total_score),
                'recommendation': recommendation,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'total_signals': total_signals,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Multi-strategy analysis error: {e}")
            return {
                'final_signal': 0,
                'confidence': 0,
                'strategy_signals': [],
                'weighted_score': 0,
                'recommendation': 'HOLD',
                'error': str(e)
            }
