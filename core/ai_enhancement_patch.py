"""
AI Enhancement Patch for market_opportunity_scanner.py
يضيف:
1. Fear & Greed Index
2. FinBERT Sentiment (Fallback Mode)
3. LSTM Price Prediction
4. Crash/Recovery/Pump Detection
"""
import sys
import os
sys.path.insert(0, '/root/trade_lak_bot/core')

# استيراد المحركات الجديدة
try:
    from fear_greed_engine import FearGreedEngine
    _fear_greed = FearGreedEngine()
    FEAR_GREED_AVAILABLE = True
except Exception as e:
    print(f"[AI Patch] FearGreed unavailable: {e}")
    FEAR_GREED_AVAILABLE = False

try:
    from finbert_analyzer import FinBERTAnalyzer
    _finbert = FinBERTAnalyzer(use_local=False)
    FINBERT_AVAILABLE = True
except Exception as e:
    print(f"[AI Patch] FinBERT unavailable: {e}")
    FINBERT_AVAILABLE = False

try:
    from lstm_model import MultiSymbolPredictor
    from backtesting_engine import BacktestingEngine
    _lstm = MultiSymbolPredictor()
    _backtester = BacktestingEngine()
    LSTM_AVAILABLE = True
except Exception as e:
    print(f"[AI Patch] LSTM unavailable: {e}")
    LSTM_AVAILABLE = False

try:
    from crash_recovery_engine import CrashRecoveryEngine
    _crash_engine = CrashRecoveryEngine()
    CRASH_ENGINE_AVAILABLE = True
except Exception as e:
    print(f"[AI Patch] CrashEngine unavailable: {e}")
    CRASH_ENGINE_AVAILABLE = False


def get_ai_boost(symbol, trade_direction="LONG", news_list=None, ohlcv_data=None):
    """
    الحصول على تعزيز نسبة النجاح من جميع محركات AI
    يُضاف إلى base_rate الموجودة في scanner
    """
    total_boost = 0
    ai_components = {}
    
    # 1. Fear & Greed Index
    if FEAR_GREED_AVAILABLE:
        try:
            fg_boost = _fear_greed.calculate_success_boost(trade_direction)
            fg_data = _fear_greed.get_current_index()
            total_boost += fg_boost
            ai_components["fear_greed"] = {
                "value": fg_data["value"],
                "classification": fg_data["classification"],
                "boost": fg_boost
            }
        except Exception as e:
            pass
    
    # 2. FinBERT Sentiment
    if FINBERT_AVAILABLE and news_list:
        try:
            sentiment = _finbert.analyze_news_batch(news_list)
            sentiment_boost = _finbert.get_sentiment_boost(sentiment, trade_direction)
            total_boost += sentiment_boost
            ai_components["finbert"] = {
                "sentiment": sentiment["overall_sentiment"],
                "score": sentiment["score"],
                "boost": sentiment_boost
            }
        except Exception as e:
            pass
    
    # 3. LSTM Prediction
    if LSTM_AVAILABLE and ohlcv_data:
        try:
            import pandas as pd
            # تحويل OHLCV إلى DataFrame
            df = pd.DataFrame(ohlcv_data)
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'] if len(df.columns) == 6 else df.columns
            df = _backtester.calculate_indicators(df)
            df.dropna(inplace=True)
            
            if len(df) > 50:
                prediction = _lstm.predict(symbol, df)
                predictor = _lstm.get_predictor(symbol)
                lstm_boost = predictor.get_success_boost(prediction, trade_direction)
                total_boost += lstm_boost
                ai_components["lstm"] = {
                    "direction": prediction["direction"],
                    "confidence": prediction["confidence"],
                    "boost": lstm_boost
                }
        except Exception as e:
            pass
    
    # 4. Crash/Recovery/Pump Detection
    if CRASH_ENGINE_AVAILABLE and ohlcv_data:
        try:
            import pandas as pd
            df = pd.DataFrame(ohlcv_data)
            if len(df.columns) >= 5:
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                df = _backtester.calculate_indicators(df)
                df.dropna(inplace=True)
                
                if len(df) > 20:
                    analysis = _crash_engine.analyze_market_condition(df, symbol)
                    condition = analysis["condition"]
                    
                    condition_boost = {
                        "CRASH_WARNING": -30 if trade_direction == "LONG" else +20,
                        "RECOVERY": +20 if trade_direction == "LONG" else -15,
                        "PUMP_EARLY": +15 if trade_direction == "LONG" else -10,
                        "PUMP_LATE": -20 if trade_direction == "LONG" else +15,
                        "NORMAL": 0
                    }.get(condition, 0)
                    
                    total_boost += condition_boost
                    ai_components["market_condition"] = {
                        "condition": condition,
                        "boost": condition_boost
                    }
        except Exception as e:
            pass
    
    return total_boost, ai_components


def get_fear_greed_text():
    """الحصول على نص مؤشر الخوف والجشع للرسالة"""
    if FEAR_GREED_AVAILABLE:
        try:
            return _fear_greed.format_for_telegram()
        except:
            pass
    return ""


def get_market_warning(symbol, ohlcv_data):
    """الحصول على تحذير حالة السوق"""
    if not CRASH_ENGINE_AVAILABLE or not ohlcv_data:
        return ""
    
    try:
        import pandas as pd
        df = pd.DataFrame(ohlcv_data)
        if len(df.columns) >= 5:
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
            df = _backtester.calculate_indicators(df)
            df.dropna(inplace=True)
            
            if len(df) > 20:
                analysis = _crash_engine.analyze_market_condition(df, symbol)
                condition = analysis["condition"]
                
                if condition == "CRASH_WARNING":
                    return "⚠️ تحذير: إشارات انهيار محتملة - كن حذراً"
                elif condition == "RECOVERY":
                    return "🚀 السوق في مرحلة تعافٍ - فرصة جيدة"
                elif condition == "PUMP_EARLY":
                    return "⚡ بداية ضخ محتمل - دخول سريع مع وقف ضيق"
                elif condition == "PUMP_LATE":
                    return "⚠️ ضخ متأخر - خطر انهيار قريب"
    except:
        pass
    
    return ""


# اختبار
if __name__ == "__main__":
    print("=== AI Enhancement Patch Test ===")
    boost, components = get_ai_boost("BTCUSDT", "LONG")
    print(f"Total AI Boost: {boost:+d}%")
    print(f"Components: {components}")
    print(f"\nFear & Greed: {get_fear_greed_text()}")
