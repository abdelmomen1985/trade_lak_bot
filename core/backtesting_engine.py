"""
Advanced Backtesting Engine
اختبار الاستراتيجيات على بيانات تاريخية من Binance
يدعم 5 سنوات من البيانات
"""
import requests
import json
import time
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class BacktestingEngine:
    """محرك Backtesting متقدم لاختبار استراتيجيات التداول"""
    
    BINANCE_API = "https://api.binance.com/api/v3"
    DATA_CACHE_DIR = "/root/trade_lak_bot/data/historical"
    
    def __init__(self):
        os.makedirs(self.DATA_CACHE_DIR, exist_ok=True)
        self.results = {}
    
    # ============================================================
    # جلب البيانات التاريخية
    # ============================================================
    
    def fetch_historical_data(self, symbol, interval="1h", days=365):
        """
        جلب بيانات تاريخية من Binance
        symbol: مثل BTCUSDT
        interval: 1m, 5m, 15m, 1h, 4h, 1d
        days: عدد الأيام (حتى 1825 = 5 سنوات)
        """
        cache_file = f"{self.DATA_CACHE_DIR}/{symbol}_{interval}_{days}d.json"
        
        # فحص الكاش (صالح لـ 6 ساعات)
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 21600:  # 6 ساعات
                print(f"[Backtest] Loading {symbol} from cache...")
                with open(cache_file, 'r') as f:
                    return json.load(f)
        
        print(f"[Backtest] Fetching {symbol} {interval} data for {days} days...")
        
        all_candles = []
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        # Binance يرجع 1000 شمعة كحد أقصى في كل طلب
        current_start = start_time
        
        while current_start < end_time:
            try:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": current_start,
                    "endTime": end_time,
                    "limit": 1000
                }
                
                response = requests.get(
                    f"{self.BINANCE_API}/klines",
                    params=params,
                    timeout=15
                )
                
                if response.status_code == 200:
                    candles = response.json()
                    if not candles:
                        break
                    
                    all_candles.extend(candles)
                    current_start = candles[-1][0] + 1  # الشمعة التالية
                    
                    if len(candles) < 1000:
                        break
                    
                    time.sleep(0.1)  # تجنب rate limiting
                else:
                    print(f"[Backtest] API Error: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"[Backtest] Fetch Error: {e}")
                break
        
        if all_candles:
            # حفظ في الكاش
            with open(cache_file, 'w') as f:
                json.dump(all_candles, f)
            print(f"[Backtest] ✅ Fetched {len(all_candles)} candles for {symbol}")
        
        return all_candles
    
    def candles_to_dataframe(self, candles):
        """تحويل البيانات الخام إلى DataFrame"""
        if not candles:
            return pd.DataFrame()
        
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    # ============================================================
    # حساب المؤشرات التقنية
    # ============================================================
    
    def calculate_indicators(self, df):
        """حساب جميع المؤشرات التقنية"""
        if df.empty:
            return df
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # RSI
        df['rsi'] = self._calculate_rsi(close, 14)
        
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df['bb_upper'] = sma20 + (2 * std20)
        df['bb_lower'] = sma20 - (2 * std20)
        df['bb_mid'] = sma20
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        
        # Moving Averages
        df['ema9'] = close.ewm(span=9).mean()
        df['ema21'] = close.ewm(span=21).mean()
        df['ema50'] = close.ewm(span=50).mean()
        df['ema200'] = close.ewm(span=200).mean()
        df['sma50'] = close.rolling(50).mean()
        df['sma200'] = close.rolling(200).mean()
        
        # Volume indicators
        df['volume_sma20'] = volume.rolling(20).mean()
        df['volume_ratio'] = volume / df['volume_sma20']
        
        # ATR (Average True Range)
        df['atr'] = self._calculate_atr(high, low, close, 14)
        
        # Stochastic RSI
        df['stoch_rsi'] = self._calculate_stoch_rsi(close, 14)
        
        # Price change
        df['price_change_1h'] = close.pct_change(1)
        df['price_change_4h'] = close.pct_change(4)
        df['price_change_24h'] = close.pct_change(24)
        
        # Support/Resistance levels
        df['pivot'] = (high + low + close) / 3
        df['resistance1'] = 2 * df['pivot'] - low
        df['support1'] = 2 * df['pivot'] - high
        
        return df
    
    def _calculate_rsi(self, prices, period=14):
        """حساب RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_atr(self, high, low, close, period=14):
        """حساب ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calculate_stoch_rsi(self, prices, period=14):
        """حساب Stochastic RSI"""
        rsi = self._calculate_rsi(prices, period)
        rsi_min = rsi.rolling(period).min()
        rsi_max = rsi.rolling(period).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min)
        return stoch_rsi * 100
    
    # ============================================================
    # استراتيجيات التداول
    # ============================================================
    
    def strategy_rsi_macd(self, df):
        """استراتيجية RSI + MACD"""
        signals = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            rsi = df['rsi'].iloc[i]
            macd = df['macd'].iloc[i]
            macd_prev = df['macd'].iloc[i-1]
            signal = df['macd_signal'].iloc[i]
            signal_prev = df['macd_signal'].iloc[i-1]
            
            # إشارة شراء: RSI < 40 + MACD يتقاطع للأعلى
            if rsi < 40 and macd > signal and macd_prev <= signal_prev:
                signals.iloc[i] = 1
            
            # إشارة بيع: RSI > 70 + MACD يتقاطع للأسفل
            elif rsi > 70 and macd < signal and macd_prev >= signal_prev:
                signals.iloc[i] = -1
        
        return signals
    
    def strategy_ema_crossover(self, df):
        """استراتيجية EMA Crossover"""
        signals = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            ema9 = df['ema9'].iloc[i]
            ema21 = df['ema21'].iloc[i]
            ema9_prev = df['ema9'].iloc[i-1]
            ema21_prev = df['ema21'].iloc[i-1]
            ema200 = df['ema200'].iloc[i]
            close = df['close'].iloc[i]
            
            # إشارة شراء: EMA9 يتقاطع فوق EMA21 والسعر فوق EMA200
            if ema9 > ema21 and ema9_prev <= ema21_prev and close > ema200:
                signals.iloc[i] = 1
            
            # إشارة بيع: EMA9 يتقاطع تحت EMA21
            elif ema9 < ema21 and ema9_prev >= ema21_prev:
                signals.iloc[i] = -1
        
        return signals
    
    def strategy_bollinger_rsi(self, df):
        """استراتيجية Bollinger Bands + RSI"""
        signals = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            bb_lower = df['bb_lower'].iloc[i]
            bb_upper = df['bb_upper'].iloc[i]
            rsi = df['rsi'].iloc[i]
            
            # إشارة شراء: السعر تحت الباند السفلي + RSI < 35
            if close < bb_lower and rsi < 35:
                signals.iloc[i] = 1
            
            # إشارة بيع: السعر فوق الباند العلوي + RSI > 65
            elif close > bb_upper and rsi > 65:
                signals.iloc[i] = -1
        
        return signals
    
    def strategy_combined(self, df):
        """الاستراتيجية المدمجة - أقوى استراتيجية"""
        signals = pd.Series(0, index=df.index)
        
        for i in range(50, len(df)):
            close = df['close'].iloc[i]
            rsi = df['rsi'].iloc[i]
            macd = df['macd'].iloc[i]
            macd_signal = df['macd_signal'].iloc[i]
            macd_prev = df['macd'].iloc[i-1]
            macd_signal_prev = df['macd_signal'].iloc[i-1]
            ema9 = df['ema9'].iloc[i]
            ema21 = df['ema21'].iloc[i]
            ema200 = df['ema200'].iloc[i]
            bb_lower = df['bb_lower'].iloc[i]
            bb_upper = df['bb_upper'].iloc[i]
            volume_ratio = df['volume_ratio'].iloc[i]
            
            buy_score = 0
            sell_score = 0
            
            # RSI
            if rsi < 30: buy_score += 3
            elif rsi < 45: buy_score += 1
            elif rsi > 70: sell_score += 3
            elif rsi > 55: sell_score += 1
            
            # MACD
            if macd > macd_signal and macd_prev <= macd_signal_prev:
                buy_score += 2
            elif macd < macd_signal and macd_prev >= macd_signal_prev:
                sell_score += 2
            
            # EMA Trend
            if close > ema200: buy_score += 1
            else: sell_score += 1
            
            if ema9 > ema21: buy_score += 1
            else: sell_score += 1
            
            # Bollinger
            if close < bb_lower: buy_score += 2
            elif close > bb_upper: sell_score += 2
            
            # Volume
            if volume_ratio > 1.5: 
                buy_score += 1 if buy_score > sell_score else 0
                sell_score += 1 if sell_score > buy_score else 0
            
            # إشارة نهائية (تحتاج 5+ نقاط)
            if buy_score >= 5 and buy_score > sell_score:
                signals.iloc[i] = 1
            elif sell_score >= 5 and sell_score > buy_score:
                signals.iloc[i] = -1
        
        return signals
    
    # ============================================================
    # تنفيذ Backtest
    # ============================================================
    
    def run_backtest(self, df, signals, initial_capital=10000, 
                     take_profit=0.03, stop_loss=0.015, fee=0.001):
        """
        تنفيذ Backtest كامل
        initial_capital: رأس المال الابتدائي بالدولار
        take_profit: نسبة الربح المستهدف (3%)
        stop_loss: نسبة وقف الخسارة (1.5%)
        fee: رسوم التداول (0.1%)
        """
        capital = initial_capital
        position = None
        entry_price = 0
        trades = []
        equity_curve = [capital]
        
        for i in range(len(df)):
            close = df['close'].iloc[i]
            signal = signals.iloc[i]
            timestamp = df.index[i]
            
            # إدارة المركز المفتوح
            if position == "LONG":
                pnl_pct = (close - entry_price) / entry_price
                
                # وقف الخسارة
                if pnl_pct <= -stop_loss:
                    pnl = capital * pnl_pct - capital * fee
                    capital += pnl
                    trades.append({
                        "type": "LONG",
                        "entry": entry_price,
                        "exit": close,
                        "pnl_pct": pnl_pct,
                        "pnl_usd": pnl,
                        "result": "LOSS",
                        "exit_reason": "STOP_LOSS",
                        "timestamp": str(timestamp)
                    })
                    position = None
                
                # هدف الربح
                elif pnl_pct >= take_profit:
                    pnl = capital * pnl_pct - capital * fee
                    capital += pnl
                    trades.append({
                        "type": "LONG",
                        "entry": entry_price,
                        "exit": close,
                        "pnl_pct": pnl_pct,
                        "pnl_usd": pnl,
                        "result": "WIN",
                        "exit_reason": "TAKE_PROFIT",
                        "timestamp": str(timestamp)
                    })
                    position = None
                
                # إشارة بيع
                elif signal == -1:
                    pnl = capital * pnl_pct - capital * fee
                    capital += pnl
                    trades.append({
                        "type": "LONG",
                        "entry": entry_price,
                        "exit": close,
                        "pnl_pct": pnl_pct,
                        "pnl_usd": pnl,
                        "result": "WIN" if pnl > 0 else "LOSS",
                        "exit_reason": "SIGNAL",
                        "timestamp": str(timestamp)
                    })
                    position = None
            
            # فتح مركز جديد
            if position is None and signal == 1:
                position = "LONG"
                entry_price = close * (1 + fee)  # مع الرسوم
            
            equity_curve.append(capital)
        
        # إغلاق أي مركز مفتوح في النهاية
        if position == "LONG" and len(df) > 0:
            close = df['close'].iloc[-1]
            pnl_pct = (close - entry_price) / entry_price
            pnl = capital * pnl_pct
            capital += pnl
            trades.append({
                "type": "LONG",
                "entry": entry_price,
                "exit": close,
                "pnl_pct": pnl_pct,
                "pnl_usd": pnl,
                "result": "WIN" if pnl > 0 else "LOSS",
                "exit_reason": "END_OF_DATA",
                "timestamp": "END"
            })
        
        return self._calculate_metrics(trades, equity_curve, initial_capital, capital)
    
    def _calculate_metrics(self, trades, equity_curve, initial_capital, final_capital):
        """حساب مقاييس الأداء"""
        if not trades:
            return {"error": "No trades executed"}
        
        wins = [t for t in trades if t["result"] == "WIN"]
        losses = [t for t in trades if t["result"] == "LOSS"]
        
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        
        avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
        
        profit_factor = abs(avg_win * len(wins)) / abs(avg_loss * len(losses)) if losses and avg_loss != 0 else float('inf')
        
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # Maximum Drawdown
        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak * 100
        max_drawdown = abs(drawdown.min())
        
        # Sharpe Ratio (تقريبي)
        returns = np.diff(equity) / equity[:-1]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(365 * 24)) if np.std(returns) > 0 else 0
        
        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 2),
            "avg_win_pct": round(avg_win * 100, 2),
            "avg_loss_pct": round(avg_loss * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "total_return_pct": round(total_return, 2),
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trades": trades[-20:]  # آخر 20 صفقة
        }
    
    # ============================================================
    # تشغيل Backtest كامل
    # ============================================================
    
    def run_full_backtest(self, symbols=None, days=365):
        """تشغيل Backtest شامل على عدة عملات"""
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        
        all_results = {}
        
        for symbol in symbols:
            print(f"\n[Backtest] Testing {symbol}...")
            
            candles = self.fetch_historical_data(symbol, "1h", days)
            if not candles:
                print(f"[Backtest] No data for {symbol}")
                continue
            
            df = self.candles_to_dataframe(candles)
            df = self.calculate_indicators(df)
            df.dropna(inplace=True)
            
            symbol_results = {}
            
            # اختبار الاستراتيجيات المختلفة
            strategies = {
                "RSI_MACD": self.strategy_rsi_macd,
                "EMA_Crossover": self.strategy_ema_crossover,
                "Bollinger_RSI": self.strategy_bollinger_rsi,
                "Combined": self.strategy_combined
            }
            
            for strategy_name, strategy_func in strategies.items():
                signals = strategy_func(df)
                results = self.run_backtest(df, signals)
                symbol_results[strategy_name] = results
                
                print(f"  {strategy_name}: Win Rate={results.get('win_rate', 0)}% | "
                      f"Return={results.get('total_return_pct', 0)}% | "
                      f"Trades={results.get('total_trades', 0)}")
            
            all_results[symbol] = symbol_results
        
        # حفظ النتائج
        results_file = "/root/trade_lak_bot/data/backtest_results.json"
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n[Backtest] ✅ Results saved to {results_file}")
        return all_results
    
    def get_best_strategy(self, symbol="BTCUSDT"):
        """الحصول على أفضل استراتيجية بناءً على نتائج Backtest"""
        results_file = "/root/trade_lak_bot/data/backtest_results.json"
        
        if not os.path.exists(results_file):
            return "Combined"  # الافتراضي
        
        try:
            with open(results_file, 'r') as f:
                all_results = json.load(f)
            
            if symbol not in all_results:
                return "Combined"
            
            symbol_results = all_results[symbol]
            best_strategy = max(
                symbol_results.items(),
                key=lambda x: x[1].get("win_rate", 0) * x[1].get("profit_factor", 0)
            )
            
            return best_strategy[0]
        except:
            return "Combined"


# اختبار سريع
if __name__ == "__main__":
    engine = BacktestingEngine()
    print("Running quick backtest on BTC (30 days)...")
    results = engine.run_full_backtest(["BTCUSDT"], days=30)
    
    for symbol, strategies in results.items():
        print(f"\n=== {symbol} ===")
        for strategy, metrics in strategies.items():
            print(f"{strategy}: Win Rate={metrics.get('win_rate')}% | "
                  f"Return={metrics.get('total_return_pct')}%")
