#!/usr/bin/env python3
"""
lstm_predictor.py — وحدة LSTM مستقلة لـ Trade Lak
تعمل بـ 27 feature المُدرَّب عليها LSTM
وتُدمج مع نتائج RF+GB في قرارات التداول
"""

import numpy as np
import pandas as pd
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class LSTMPredictor:
    """
    وحدة تنبؤ LSTM مستقلة
    تستخدم 27 feature محددة مطابقة لبيانات التدريب
    """
    def __init__(self, model_dir="models"):
        self.model_dir = Path(model_dir)
        self.model = None
        self.meta = {}
        self.lookback = 24
        self.n_features = 27
        self.feature_names = []
        self._load()

    def _load(self):
        """تحميل نموذج LSTM والـ metadata"""
        try:
            model_path = self.model_dir / "okx_lstm_model.keras"
            meta_path = self.model_dir / "okx_lstm_meta.json"
            if not model_path.exists():
                logger.warning("[LSTM] Model file not found")
                return
            import tensorflow as tf
            self.model = tf.keras.models.load_model(str(model_path))
            if meta_path.exists():
                with open(meta_path) as f:
                    self.meta = json.load(f)
                self.lookback = self.meta.get("lookback", 24)
                self.n_features = self.meta.get("n_features", 27)
                self.feature_names = self.meta.get("feature_names", [])
            acc = self.meta.get("lstm_accuracy", 0)
            logger.info(f"✅ [LSTM] Loaded — features={self.n_features}, lookback={self.lookback}, accuracy={acc:.1%}")
        except Exception as e:
            logger.warning(f"[LSTM] Load failed: {e}")
            self.model = None

    def build_features(self, ohlcv_data: list, coinglass_data: dict = None) -> np.ndarray:
        """
        بناء 27 feature من بيانات OHLCV + CoinGlass
        مطابقة تماماً لبيانات التدريب
        """
        try:
            df = pd.DataFrame(ohlcv_data)
            if len(df) < 50:
                return None
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']

            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 1e-9)
            rsi = (100 - 100 / (1 + rs)).fillna(50)

            # EMA cross (9 vs 21)
            ema9 = close.ewm(span=9).mean()
            ema21 = close.ewm(span=21).mean()
            ema50 = close.ewm(span=50).mean()
            ema_cross = ((ema9 - ema21) / ema21.replace(0, 1e-9)).fillna(0)

            # MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            macd_signal = macd_line.ewm(span=9).mean()
            macd_hist = macd_line - macd_signal

            # Bollinger Bands
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std().replace(0, 1e-9)
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            bb_width = ((bb_upper - bb_lower) / bb_mid.replace(0, 1e-9)).fillna(0)
            bb_range = (bb_upper - bb_lower).replace(0, 1e-9)
            bb_position = ((close - bb_lower) / bb_range).fillna(0.5).clip(0, 1)

            # ATR
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().fillna(0)
            atr_pct = (atr / close.replace(0, 1e-9)).fillna(0)

            # Volume ratio
            vol_ma = volume.rolling(20).mean().replace(0, 1e-9)
            vol_ratio = (volume / vol_ma).fillna(1)

            # Price changes
            price_change_1h = close.pct_change(1).fillna(0)
            price_change_4h = close.pct_change(4).fillna(0)
            price_change_24h = close.pct_change(24).fillna(0)

            # Stochastic K
            low_14 = low.rolling(14).min()
            high_14 = high.rolling(14).max()
            stoch_range = (high_14 - low_14).replace(0, 1e-9)
            stoch_k = ((close - low_14) / stoch_range * 100).fillna(50)

            # CoinGlass features
            cg = coinglass_data or {}
            long_liq = float(cg.get('long_liquidations', 0))
            short_liq = float(cg.get('short_liquidations', 0))
            total_liq = long_liq + short_liq
            liq_normalized = min(total_liq / 1e8, 1.0) if total_liq > 0 else 0.0
            liq_ratio = (long_liq / total_liq) if total_liq > 0 else 0.5
            oi_change = float(cg.get('open_interest_change', 0))
            funding_rate = float(cg.get('funding_rate', 0))
            fear_greed = float(cg.get('fear_greed', 50)) / 100.0

            # بناء sequence
            n = len(df)
            sequence = []
            for i in range(max(0, n - self.lookback), n):
                feat = np.array([
                    float(rsi.iloc[i]),
                    float(ema_cross.iloc[i]),
                    float(macd_line.iloc[i]),
                    float(macd_hist.iloc[i]),
                    float(macd_signal.iloc[i]),
                    float(bb_width.iloc[i]),
                    float(bb_position.iloc[i]),
                    float(atr_pct.iloc[i]),
                    float(vol_ratio.iloc[i]),
                    float(price_change_1h.iloc[i]),
                    float(price_change_4h.iloc[i]),
                    float(price_change_24h.iloc[i]),
                    float(stoch_k.iloc[i]),
                    float(ema9.iloc[i] / close.iloc[i] if close.iloc[i] > 0 else 1),
                    float(ema21.iloc[i] / close.iloc[i] if close.iloc[i] > 0 else 1),
                    float(ema50.iloc[i] / close.iloc[i] if close.iloc[i] > 0 else 1),
                    float(bb_upper.iloc[i] / close.iloc[i] if close.iloc[i] > 0 else 1),
                    float(bb_lower.iloc[i] / close.iloc[i] if close.iloc[i] > 0 else 1),
                    long_liq,
                    short_liq,
                    liq_normalized,
                    liq_ratio,
                    oi_change,
                    funding_rate,
                    fear_greed,
                    float(vol_ma.iloc[i]),
                    float(atr.iloc[i]),
                ], dtype=np.float32)
                # تنظيف NaN و Inf
                feat = np.nan_to_num(feat, nan=0.0, posinf=1.0, neginf=-1.0)
                sequence.append(feat)

            if len(sequence) < self.lookback:
                # نُكمّل بأصفار في البداية
                pad = [np.zeros(self.n_features, dtype=np.float32)] * (self.lookback - len(sequence))
                sequence = pad + sequence

            return np.array(sequence[-self.lookback:], dtype=np.float32)

        except Exception as e:
            logger.debug(f"[LSTM] build_features error: {e}")
            return None

    def predict(self, ohlcv_data: list, coinglass_data: dict = None) -> dict:
        """
        تنبؤ LSTM بالاتجاه
        Returns:
            dict: {direction, confidence, lstm_prob, active}
        """
        default = {"direction": "NEUTRAL", "confidence": 0.5, "lstm_prob": 0.5, "active": False}
        if self.model is None:
            return default

        try:
            sequence = self.build_features(ohlcv_data, coinglass_data)
            if sequence is None:
                return {**default, "active": True}

            seq_input = sequence.reshape(1, self.lookback, self.n_features)
            lstm_raw = float(self.model.predict(seq_input, verbose=0)[0][0])

            if lstm_raw > 0.62:
                direction = "UP"
                confidence = lstm_raw
            elif lstm_raw < 0.38:
                direction = "DOWN"
                confidence = 1.0 - lstm_raw
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
            logger.debug(f"[LSTM] predict error: {e}")
            return {**default, "active": True}

    def boost_score(self, current_score: float, ohlcv_data: list, coinglass_data: dict = None) -> tuple:
        """
        تعديل Score بناءً على تنبؤ LSTM
        Returns:
            (new_score, lstm_result)
        """
        result = self.predict(ohlcv_data, coinglass_data)
        if not result["active"]:
            return current_score, result

        direction = result["direction"]
        confidence = result["confidence"]
        lstm_prob = result["lstm_prob"]

        if direction == "UP" and confidence > 0.65:
            boost = +1.5 * (confidence - 0.5)  # max +0.75
            new_score = current_score + boost
            logger.debug(f"[LSTM] ↑ UP ({lstm_prob:.2f}) → score +{boost:.2f}")
        elif direction == "DOWN":
            penalty = -1.5 * (confidence - 0.5)  # max -0.75
            new_score = current_score + penalty
            logger.debug(f"[LSTM] ↓ DOWN ({lstm_prob:.2f}) → score {penalty:.2f}")
        else:
            new_score = current_score  # NEUTRAL = لا تغيير
            logger.debug(f"[LSTM] ↔ NEUTRAL ({lstm_prob:.2f}) → no change")

        return new_score, result

    @property
    def is_active(self):
        return self.model is not None
