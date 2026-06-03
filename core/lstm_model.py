"""
Advanced LSTM + Transformer Price Prediction Model
نموذج AI متقدم للتنبؤ بحركة الأسعار
"""
import numpy as np
import json
import os
import pickle
from datetime import datetime


class LSTMPredictor:
    """
    نموذج LSTM للتنبؤ بحركة الأسعار
    يدعم وضعين:
    1. Full LSTM: يحتاج torch (للسيرفر)
    2. Simple ML: يستخدم sklearn فقط (بديل خفيف)
    """
    
    MODEL_DIR = "/root/trade_lak_bot/models"
    
    def __init__(self, symbol="BTCUSDT", use_torch=False):
        self.symbol = symbol
        self.use_torch = use_torch
        self.model = None
        self.scaler = None
        self.sequence_length = 60  # 60 شمعة للتنبؤ
        self.features = ['close', 'volume', 'rsi', 'macd', 'bb_width', 'atr']
        
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        
        if use_torch:
            self._init_torch_model()
        else:
            self._init_sklearn_model()
    
    def _init_sklearn_model(self):
        """تهيئة نموذج sklearn (أخف وأسرع)"""
        try:
            from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import Pipeline
            
            self.scaler = StandardScaler()
            self.model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                random_state=42
            )
            print(f"[LSTM] ✅ GradientBoosting model initialized for {self.symbol}")
        except ImportError:
            print("[LSTM] sklearn not available")
    
    def _init_torch_model(self):
        """تهيئة نموذج LSTM الكامل"""
        try:
            import torch
            import torch.nn as nn
            
            class LSTMNet(nn.Module):
                def __init__(self, input_size, hidden_size=128, num_layers=3, dropout=0.2):
                    super(LSTMNet, self).__init__()
                    self.hidden_size = hidden_size
                    self.num_layers = num_layers
                    
                    self.lstm = nn.LSTM(
                        input_size=input_size,
                        hidden_size=hidden_size,
                        num_layers=num_layers,
                        batch_first=True,
                        dropout=dropout
                    )
                    
                    self.attention = nn.MultiheadAttention(hidden_size, num_heads=8, batch_first=True)
                    
                    self.fc = nn.Sequential(
                        nn.Linear(hidden_size, 64),
                        nn.ReLU(),
                        nn.Dropout(0.2),
                        nn.Linear(64, 3)  # UP, DOWN, NEUTRAL
                    )
                
                def forward(self, x):
                    lstm_out, _ = self.lstm(x)
                    attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
                    out = self.fc(attn_out[:, -1, :])
                    return out
            
            self.model = LSTMNet(input_size=len(self.features))
            print(f"[LSTM] ✅ LSTM+Attention model initialized for {self.symbol}")
            
        except ImportError:
            print("[LSTM] torch not available, falling back to sklearn")
            self.use_torch = False
            self._init_sklearn_model()
    
    def prepare_features(self, df):
        """تحضير الميزات للتدريب"""
        available_features = [f for f in self.features if f in df.columns]
        
        if not available_features:
            return None, None
        
        X = df[available_features].values
        
        # حساب الهدف: هل سيرتفع السعر في الساعة القادمة؟
        future_return = df['close'].shift(-1) / df['close'] - 1
        
        # تصنيف: 0=هبوط، 1=محايد، 2=صعود
        y = np.where(future_return > 0.005, 2,  # صعود > 0.5%
              np.where(future_return < -0.005, 0,  # هبوط > 0.5%
              1))  # محايد
        
        # إزالة القيم الناقصة
        valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X = X[valid_mask]
        y = y[valid_mask]
        
        return X, y
    
    def train(self, df):
        """تدريب النموذج"""
        print(f"[LSTM] Training model for {self.symbol}...")
        
        X, y = self.prepare_features(df)
        if X is None or len(X) < 100:
            print("[LSTM] Insufficient data for training")
            return False
        
        try:
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import train_test_split
            
            # تقسيم البيانات
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, shuffle=False
            )
            
            # تطبيع البيانات
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # تدريب النموذج
            self.model.fit(X_train_scaled, y_train)
            
            # تقييم الأداء
            accuracy = self.model.score(X_test_scaled, y_test)
            print(f"[LSTM] ✅ Training complete! Accuracy: {accuracy:.2%}")
            
            # حفظ النموذج
            self._save_model()
            
            return accuracy
            
        except Exception as e:
            print(f"[LSTM] Training error: {e}")
            return False
    
    def predict(self, df_recent):
        """التنبؤ بالحركة القادمة"""
        if self.model is None:
            return {"direction": "NEUTRAL", "confidence": 0.5, "signal": 0}
        
        try:
            X, _ = self.prepare_features(df_recent)
            if X is None or len(X) == 0:
                return {"direction": "NEUTRAL", "confidence": 0.5, "signal": 0}
            
            # استخدام آخر صف فقط للتنبؤ
            X_last = X[-1:].reshape(1, -1)
            
            if self.scaler:
                X_last = self.scaler.transform(X_last)
            
            prediction = self.model.predict(X_last)[0]
            probabilities = self.model.predict_proba(X_last)[0]
            
            direction_map = {0: "DOWN", 1: "NEUTRAL", 2: "UP"}
            direction = direction_map[prediction]
            confidence = probabilities[prediction]
            
            return {
                "direction": direction,
                "confidence": float(confidence),
                "signal": 1 if direction == "UP" else (-1 if direction == "DOWN" else 0),
                "probabilities": {
                    "up": float(probabilities[2]),
                    "neutral": float(probabilities[1]),
                    "down": float(probabilities[0])
                }
            }
            
        except Exception as e:
            print(f"[LSTM] Prediction error: {e}")
            return {"direction": "NEUTRAL", "confidence": 0.5, "signal": 0}
    
    def get_success_boost(self, prediction, trade_direction):
        """حساب تأثير النموذج على نسبة النجاح"""
        direction = prediction.get("direction", "NEUTRAL")
        confidence = prediction.get("confidence", 0.5)
        
        boost = 0
        
        if trade_direction == "LONG":
            if direction == "UP":
                boost = int(confidence * 15)  # حتى +15%
            elif direction == "DOWN":
                boost = -int(confidence * 20)  # حتى -20%
        
        elif trade_direction == "SHORT":
            if direction == "DOWN":
                boost = int(confidence * 15)
            elif direction == "UP":
                boost = -int(confidence * 20)
        
        return boost
    
    def _save_model(self):
        """حفظ النموذج على القرص"""
        try:
            model_file = f"{self.MODEL_DIR}/{self.symbol}_model.pkl"
            scaler_file = f"{self.MODEL_DIR}/{self.symbol}_scaler.pkl"
            
            with open(model_file, 'wb') as f:
                pickle.dump(self.model, f)
            
            if self.scaler:
                with open(scaler_file, 'wb') as f:
                    pickle.dump(self.scaler, f)
            
            print(f"[LSTM] Model saved to {model_file}")
        except Exception as e:
            print(f"[LSTM] Save error: {e}")
    
    def load_model(self):
        """تحميل النموذج المحفوظ"""
        try:
            model_file = f"{self.MODEL_DIR}/{self.symbol}_model.pkl"
            scaler_file = f"{self.MODEL_DIR}/{self.symbol}_scaler.pkl"
            
            if os.path.exists(model_file):
                with open(model_file, 'rb') as f:
                    self.model = pickle.load(f)
                
                if os.path.exists(scaler_file):
                    with open(scaler_file, 'rb') as f:
                        self.scaler = pickle.load(f)
                
                print(f"[LSTM] ✅ Model loaded for {self.symbol}")
                return True
        except Exception as e:
            print(f"[LSTM] Load error: {e}")
        return False


class MultiSymbolPredictor:
    """مدير نماذج متعددة لعدة عملات"""
    
    def __init__(self):
        self.predictors = {}
    
    def get_predictor(self, symbol):
        """الحصول على نموذج لعملة معينة"""
        if symbol not in self.predictors:
            predictor = LSTMPredictor(symbol)
            predictor.load_model()  # محاولة تحميل نموذج محفوظ
            self.predictors[symbol] = predictor
        return self.predictors[symbol]
    
    def predict(self, symbol, df):
        """التنبؤ لعملة معينة"""
        predictor = self.get_predictor(symbol)
        return predictor.predict(df)
    
    def train_all(self, symbol_data_dict):
        """تدريب نماذج لجميع العملات"""
        for symbol, df in symbol_data_dict.items():
            predictor = self.get_predictor(symbol)
            predictor.train(df)


# اختبار سريع
if __name__ == "__main__":
    print("Testing LSTM Predictor...")
    predictor = LSTMPredictor("BTCUSDT", use_torch=False)
    print("✅ Predictor initialized successfully")
