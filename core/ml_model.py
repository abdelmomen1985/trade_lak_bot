# ============================================================
# Trade Lak Bot - Advanced Machine Learning Module
# تطبيق Trade لك - وحدة التعلم الآلي المتقدمة
# ============================================================

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import os
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MLModel:
    """
    Advanced Machine Learning Model for Trading Signals
    نموذج التعلم الآلي المتقدم للإشارات التجارية
    
    Features:
    - Multiple model types (Random Forest, Gradient Boosting)
    - Continuous learning from each trade
    - Feature engineering from market data
    - Model persistence and versioning
    - Performance tracking
    """
    
    def __init__(self, model_dir="models"):
        """
        Initialize ML Model
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Models
        self.rf_model = None
        self.gb_model = None
        self.lstm_model = None
        self.lstm_meta = {}
        self.scaler = StandardScaler()
        
        # Training data
        self.training_data = []
        self.training_labels = []
        
        # Model metadata
        self.model_version = 1
        self.last_trained = None
        self.model_performance = {}
        
        # Load existing models if available
        self._load_models()
        
        logger.info("✅ ML Model initialized")
    
    def _load_models(self):
        """Load existing models from disk"""
        try:
            # أولاً: النماذج المحسَّنة (27 features)
            okx_rf_path = self.model_dir / "okx_rf_model.pkl"
            okx_gb_path = self.model_dir / "okx_gb_model.pkl"
            okx_scaler_path = self.model_dir / "okx_scaler.pkl"
            rf_path = self.model_dir / "rf_model.pkl"
            gb_path = self.model_dir / "gb_model.pkl"
            scaler_path = self.model_dir / "scaler.pkl"

            if okx_rf_path.exists():
                self.rf_model = joblib.load(okx_rf_path)
                logger.info(f"✅ OKX RF model loaded (n={self.rf_model.n_features_in_})")
            elif rf_path.exists():
                self.rf_model = joblib.load(rf_path)
                logger.info("✅ Random Forest model loaded")

            if okx_gb_path.exists():
                self.gb_model = joblib.load(okx_gb_path)
                logger.info(f"✅ OKX GB model loaded (n={self.gb_model.n_features_in_})")
            elif gb_path.exists():
                self.gb_model = joblib.load(gb_path)
                logger.info("✅ Gradient Boosting model loaded")

            if okx_scaler_path.exists():
                self.scaler = joblib.load(okx_scaler_path)
                logger.info(f"✅ OKX Scaler loaded (n={self.scaler.n_features_in_})")
            elif scaler_path.exists():
                self.scaler = joblib.load(scaler_path)
                logger.info("✅ Scaler loaded")
        except Exception as e:
            # تحميل LSTM إذا كان متاحاً
            lstm_path = self.model_dir / "okx_lstm_model.keras"
            if lstm_path.exists():
                try:
                    import tensorflow as tf
                    self.lstm_model = tf.keras.models.load_model(str(lstm_path))
                    import json as _json
                    lstm_meta_p = self.model_dir / "okx_lstm_meta.json"
                    if lstm_meta_p.exists():
                        self.lstm_meta = _json.load(open(str(lstm_meta_p)))
                    logger.info("[LSTM] LSTM model loaded")
                except Exception as _le:
                    logger.debug("[LSTM] load skipped")
                    self.lstm_model = None
            logger.warning(f"Could not load models: {e}")
    
    def _save_models(self):
        """Save models to disk"""
        try:
            joblib.dump(self.rf_model, self.model_dir / "rf_model.pkl")
            joblib.dump(self.gb_model, self.model_dir / "gb_model.pkl")
            joblib.dump(self.scaler, self.model_dir / "scaler.pkl")
            logger.info("✅ Models saved successfully")
        except Exception as e:
            logger.error(f"❌ Error saving models: {e}")
    
    def extract_features(self, ohlcv_data, coinglass_data=None):
        """
        Extract features from market data
        استخراج الميزات من بيانات السوق
        
        Args:
            ohlcv_data: OHLCV candlestick data (list of dicts with o, h, l, c, v)
            coinglass_data: Optional CoinGlass data (liquidations, funding rate, etc.)
        
        Returns:
            np.array: Feature vector
        """
        features = []
        
        try:
            df = pd.DataFrame(ohlcv_data)
            
            # === Price Action Features ===
            # Returns
            returns = df['close'].pct_change().fillna(0)
            features.append(returns.mean())  # Mean return
            features.append(returns.std())   # Volatility
            features.append(returns.iloc[-1])  # Latest return
            
            # Price levels
            features.append((df['close'].iloc[-1] - df['close'].min()) / (df['close'].max() - df['close'].min()))  # Normalized price
            features.append((df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1])  # Today's change
            
            # === Volume Analysis ===
            volume_ma = df['volume'].rolling(window=5).mean()
            features.append(df['volume'].iloc[-1] / volume_ma.iloc[-1])  # Volume ratio
            
            # === Momentum Indicators ===
            # RSI
            rsi = self._calculate_rsi(df['close'], period=14)
            features.append(rsi.iloc[-1] if len(rsi) > 0 else 50)
            
            # MACD
            macd, signal, hist = self._calculate_macd(df['close'])
            features.append(hist.iloc[-1] if len(hist) > 0 else 0)
            
            # === Volatility ===
            features.append(df['high'].rolling(window=14).mean().iloc[-1] - df['low'].rolling(window=14).mean().iloc[-1])
            
            # === Trend ===
            sma_20 = df['close'].rolling(window=20).mean()
            sma_50 = df['close'].rolling(window=50).mean()
            features.append((sma_20.iloc[-1] - sma_50.iloc[-1]) / sma_50.iloc[-1] if sma_50.iloc[-1] != 0 else 0)
            
            # === CoinGlass Features (if available) ===
            if coinglass_data:
                features.append(coinglass_data.get('funding_rate', 0))
                features.append(coinglass_data.get('long_short_ratio', 0.5))
                features.append(coinglass_data.get('liquidation_pressure', 0))
                features.append(coinglass_data.get('open_interest_change', 0))
            else:
                features.extend([0, 0.5, 0, 0])
            
            # === Whale Activity ===
            # (Will be added from whale_tracker)
            features.append(0)  # Placeholder
            
            # === Order Book Intelligence ===
            # (Will be added from orderbook_intel)
            features.append(0)  # Placeholder
            

            # ── ميزات جديدة (المستوى 2) ──
            try:
                # EMA Cross: EMA9 vs EMA21
                ema9 = df['close'].ewm(span=9).mean()
                ema21 = df['close'].ewm(span=21).mean()
                ema_cross = (ema9.iloc[-1] - ema21.iloc[-1]) / ema21.iloc[-1]
                features.append(float(ema_cross))
                # Bollinger Bands Width
                bb_mid = df['close'].rolling(20).mean()
                bb_std = df['close'].rolling(20).std()
                bb_width = (2 * bb_std.iloc[-1]) / bb_mid.iloc[-1] if bb_mid.iloc[-1] > 0 else 0
                features.append(float(bb_width))
                # Price position in BB
                bb_upper = bb_mid.iloc[-1] + 2 * bb_std.iloc[-1]
                bb_lower = bb_mid.iloc[-1] - 2 * bb_std.iloc[-1]
                bb_range = bb_upper - bb_lower
                price_in_bb = (df['close'].iloc[-1] - bb_lower) / bb_range if bb_range > 0 else 0.5
                features.append(float(price_in_bb))
                # Volume-Price Correlation
                import math
                vpc = df['close'].pct_change().tail(10).corr(df['volume'].pct_change().tail(10))
                features.append(float(vpc) if not math.isnan(float(vpc)) else 0.0)
                # Momentum 3 periods
                mom3 = (df['close'].iloc[-1] - df['close'].iloc[-4]) / df['close'].iloc[-4] if len(df) >= 4 else 0
                features.append(float(mom3))
                # Candle Body Ratio
                body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
                total_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                body_ratio = body / total_range if total_range > 0 else 0.5
                features.append(float(body_ratio))
            except Exception:
                features.extend([0.0, 0.0, 0.5, 0.0, 0.0, 0.5])

            return np.array(features, dtype=np.float32)
        
        except Exception as e:
            logger.error(f"❌ Error extracting features: {e}")
            return np.zeros(24, dtype=np.float32)
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
        except:
            return [50] * len(prices)
    
    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD indicator"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            return macd, signal_line, histogram
        except:
            return [0] * len(prices), [0] * len(prices), [0] * len(prices)
    
    def add_training_data(self, features, label):
        """
        Add training data point
        إضافة نقطة بيانات تدريب (من كل صفقة منتهية)
        
        Args:
            features: Feature vector
            label: 1 (profitable trade), 0 (loss/breakeven)
        """
        self.training_data.append(features)
        self.training_labels.append(label)
        logger.info(f"📊 Training data added: {len(self.training_data)} samples")
    
    def train(self, min_samples=50):
        """
        Train models on collected data
        تدريب النماذج على البيانات المجمعة
        
        Args:
            min_samples: Minimum samples required to train
        """
        if len(self.training_data) < min_samples:
            logger.warning(f"⚠️ Not enough training data: {len(self.training_data)}/{min_samples}")
            return False
        
        try:
            X = np.array(self.training_data, dtype=np.float32)
            y = np.array(self.training_labels)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            # Train Random Forest
            self.rf_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            self.rf_model.fit(X_train, y_train)
            rf_pred = self.rf_model.predict(X_test)
            rf_acc = accuracy_score(y_test, rf_pred)
            
            # Train Gradient Boosting
            self.gb_model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            self.gb_model.fit(X_train, y_train)
            gb_pred = self.gb_model.predict(X_test)
            gb_acc = accuracy_score(y_test, gb_pred)
            
            # Store performance metrics
            self.model_performance = {
                'rf_accuracy': float(rf_acc),
                'rf_precision': float(precision_score(y_test, rf_pred, zero_division=0)),
                'rf_recall': float(recall_score(y_test, rf_pred, zero_division=0)),
                'rf_f1': float(f1_score(y_test, rf_pred, zero_division=0)),
                'gb_accuracy': float(gb_acc),
                'gb_precision': float(precision_score(y_test, gb_pred, zero_division=0)),
                'gb_recall': float(recall_score(y_test, gb_pred, zero_division=0)),
                'gb_f1': float(f1_score(y_test, gb_pred, zero_division=0)),
                'training_samples': len(self.training_data),
                'last_trained': datetime.now().isoformat()
            }
            
            self.last_trained = datetime.now()
            self.model_version += 1
            
            # Save models
            self._save_models()
            
            logger.info(f"""
            ✅ Models trained successfully!
            📊 Random Forest Accuracy: {rf_acc:.2%}
            📊 Gradient Boosting Accuracy: {gb_acc:.2%}
            📊 Training samples: {len(self.training_data)}
            """)
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Error training models: {e}")
            return False
    
    def predict(self, features, use_ensemble=True):
        """
        Predict trading signal
        التنبؤ بإشارة التداول
        
        Args:
            features: Feature vector
            use_ensemble: Use ensemble of both models
        
        Returns:
            dict: {
                'signal': 1 (buy) or 0 (no signal),
                'confidence': 0-1,
                'rf_prob': Random Forest probability,
                'gb_prob': Gradient Boosting probability
            }
        """
        try:
            if self.rf_model is None or self.gb_model is None:
                logger.warning("⚠️ Models not trained yet")
                return {'signal': 0, 'confidence': 0, 'rf_prob': 0, 'gb_prob': 0}
            
            # Scale features
            # تصحيح عدد features إذا كان مختلفاً عن المتوقع
            import numpy as _np_fix
            _expected_n = getattr(self.scaler, "n_features_in_", len(features))
            if len(features) != _expected_n:
                if len(features) < _expected_n:
                    features = _np_fix.concatenate([features, _np_fix.zeros(_expected_n - len(features))])
                else:
                    features = features[:_expected_n]
            features_scaled = self.scaler.transform([features])[0]
            
            # Get predictions
            rf_prob = self.rf_model.predict_proba([features_scaled])[0][1]
            gb_prob = self.gb_model.predict_proba([features_scaled])[0][1]
            
            if use_ensemble:
                # Ensemble prediction (average)
                ensemble_prob = (rf_prob + gb_prob) / 2
                signal = 1 if ensemble_prob > 0.55 else 0
                confidence = ensemble_prob
            else:
                # Use Random Forest only
                signal = self.rf_model.predict([features_scaled])[0]
                confidence = rf_prob
            
            # إضافة LSTM prediction إذا كان متاحاً
            lstm_prob = 0.0
            lstm_direction = "NEUTRAL"
            if hasattr(self, 'lstm_model') and self.lstm_model is not None:
                try:
                    import numpy as np
                    # بناء sequence من آخر lookback نقطة
                    lookback = self.lstm_meta.get("lookback", 24)
                    n_feat = self.lstm_meta.get("n_features", 27)
                    # نُكيّف features_scaled لتناسب LSTM features
                    feat_len = len(features_scaled)
                    if feat_len >= n_feat:
                        lstm_feat = features_scaled[:n_feat]
                    else:
                        # نُكمّل بأصفار إذا كانت features أقل
                        lstm_feat = np.concatenate([features_scaled, np.zeros(n_feat - feat_len)])
                    seq = np.array([lstm_feat] * lookback).reshape(1, lookback, n_feat)
                    lstm_raw = float(self.lstm_model.predict(seq, verbose=0)[0][0])
                    lstm_prob = lstm_raw
                    # تحديد الاتجاه
                    if lstm_raw > 0.6:
                        lstm_direction = "UP"
                    elif lstm_raw < 0.4:
                        lstm_direction = "DOWN"
                    else:
                        lstm_direction = "NEUTRAL"
                    # دمج LSTM مع Ensemble (وزن 30% LSTM + 70% RF+GB)
                    if lstm_direction != "NEUTRAL":
                        ensemble_prob = (ensemble_prob * 0.70 + lstm_prob * 0.30)
                        signal = 1 if ensemble_prob > 0.55 else 0
                        confidence = ensemble_prob
                    logger.debug(f"[LSTM] prob={lstm_prob:.3f} dir={lstm_direction} → ensemble={ensemble_prob:.3f}")
                except Exception as le:
                    logger.debug(f"[LSTM] prediction skipped: {le}")
            return {
                'signal': int(signal),
                'confidence': float(confidence),
                'rf_prob': float(rf_prob),
                'gb_prob': float(gb_prob),
                'lstm_prob': float(lstm_prob),
                'lstm_direction': lstm_direction,
                'lstm_active': self.lstm_model is not None,
                'model_version': self.model_version
            }
        
        except Exception as e:
            logger.error(f"❌ Error making prediction: {e}")
            return {'signal': 0, 'confidence': 0, 'rf_prob': 0, 'gb_prob': 0}
    
    def predict_sequence(self, ohlcv_list, coinglass_data=None):
        """
        تنبؤ LSTM بالتسلسل الزمني الكامل (lookback نقطة)
        أكثر دقة من predict() لأنه يستخدم بيانات حقيقية متسلسلة
        Args:
            ohlcv_list: قائمة من آخر 24+ شمعة
            coinglass_data: بيانات CoinGlass الاختيارية
        Returns:
            dict: نتيجة LSTM مع الاتجاه والثقة
        """
        if not hasattr(self, 'lstm_model') or self.lstm_model is None:
            return {"direction": "NEUTRAL", "confidence": 0.5, "lstm_prob": 0.5, "active": False}
        try:
            import numpy as np
            lookback = self.lstm_meta.get("lookback", 24)
            n_feat = self.lstm_meta.get("n_features", 27)
            feat_names = self.lstm_meta.get("feature_names", [])
            # نحتاج على الأقل lookback شمعة
            if len(ohlcv_list) < lookback:
                return {"direction": "NEUTRAL", "confidence": 0.5, "lstm_prob": 0.5, "active": True}
            # بناء sequence من آخر lookback شمعة
            sequence = []
            for i in range(len(ohlcv_list) - lookback, len(ohlcv_list)):
                feat = self.extract_features(ohlcv_list[max(0, i-50):i+1], coinglass_data)
                feat_len = len(feat)
                if feat_len >= n_feat:
                    sequence.append(feat[:n_feat])
                else:
                    padded = np.concatenate([feat, np.zeros(n_feat - feat_len)])
                    sequence.append(padded)
            seq_array = np.array(sequence).reshape(1, lookback, n_feat)
            lstm_raw = float(self.lstm_model.predict(seq_array, verbose=0)[0][0])
            if lstm_raw > 0.65:
                direction = "UP"
                confidence = lstm_raw
            elif lstm_raw < 0.35:
                direction = "DOWN"
                confidence = 1 - lstm_raw
            else:
                direction = "NEUTRAL"
                confidence = 0.5
            return {
                "direction": direction,
                "confidence": float(confidence),
                "lstm_prob": float(lstm_raw),
                "active": True
            }
        except Exception as e:
            logger.debug(f"[LSTM] predict_sequence error: {e}")
            return {"direction": "NEUTRAL", "confidence": 0.5, "lstm_prob": 0.5, "active": True}

    def get_feature_importance(self):
        """
        Get feature importance from Random Forest
        الحصول على أهمية الميزات
        """
        try:
            if self.rf_model is None:
                return {}
            
            feature_names = [
                'mean_return', 'volatility', 'latest_return', 'normalized_price',
                'daily_change', 'volume_ratio', 'rsi', 'macd_histogram',
                'volatility_range', 'trend', 'funding_rate', 'long_short_ratio',
                'liquidation_pressure', 'oi_change', 'whale_activity', 'orderbook_intel',
                'placeholder1', 'placeholder2'
            ]
            
            importance = self.rf_model.feature_importances_
            importance_dict = dict(zip(feature_names, importance))
            
            # Sort by importance
            return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
        
        except Exception as e:
            logger.error(f"❌ Error getting feature importance: {e}")
            return {}
    
    def get_model_stats(self):
        """Get model statistics"""
        return {
            'model_version': self.model_version,
            'last_trained': self.last_trained.isoformat() if self.last_trained else None,
            'training_samples': len(self.training_data),
            'performance': self.model_performance,
            'models_available': {
                'random_forest': self.rf_model is not None,
                'gradient_boosting': self.gb_model is not None
            }
        }


class MLTrainer:
    """
    ML Model Trainer - handles continuous learning
    مدرب نموذج التعلم الآلي - يتعامل مع التعلم المستمر
    """
    
    def __init__(self, ml_model):
        self.ml_model = ml_model
        self.trade_history = []
        logger.info("✅ ML Trainer initialized")
    
    def record_trade(self, trade_data):
        """
        Record a completed trade for training
        تسجيل صفقة منتهية للتدريب
        
        Args:
            trade_data: {
                'symbol': 'BTC/USDT',
                'entry_price': 45000,
                'exit_price': 46000,
                'profit_loss': 1000,
                'profit_loss_pct': 2.2,
                'ohlcv_data': [...],
                'coinglass_data': {...}
            }
        """
        try:
            # Extract features
            features = self.ml_model.extract_features(
                trade_data.get('ohlcv_data', []),
                trade_data.get('coinglass_data', {})
            )
            
            # Label: 1 if profitable, 0 if loss
            label = 1 if trade_data.get('profit_loss', 0) > 0 else 0
            
            # Add to training data
            self.ml_model.add_training_data(features, label)
            
            # Record in history
            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': trade_data.get('symbol'),
                'profit_loss': trade_data.get('profit_loss'),
                'profit_loss_pct': trade_data.get('profit_loss_pct'),
                'label': label
            })
            
            logger.info(f"📈 Trade recorded: {trade_data.get('symbol')} | PnL: {trade_data.get('profit_loss_pct', 0):.2f}%")
            
            # Auto-train if we have enough data
            if len(self.ml_model.training_data) % 50 == 0:
                logger.info("🔄 Auto-training models...")
                self.ml_model.train()
        
        except Exception as e:
            logger.error(f"❌ Error recording trade: {e}")
    
    def get_training_stats(self):
        """Get training statistics"""
        if not self.trade_history:
            return {'total_trades': 0, 'win_rate': 0, 'avg_pnl': 0}
        
        df = pd.DataFrame(self.trade_history)
        total_trades = len(df)
        winning_trades = (df['label'] == 1).sum()
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_pnl = df['profit_loss_pct'].mean()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': float(win_rate),
            'avg_pnl_pct': float(avg_pnl),
            'total_pnl_pct': float(df['profit_loss_pct'].sum())
        }
