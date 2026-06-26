# ============================================================
# Trade Lak Bot - Autonomous Strategy Engine
# محرك الاستراتيجية المستقل — يتخذ جميع القرارات بنفسه
# ============================================================

import logging
import json
import os
from datetime import datetime
import numpy as np
from config.config import (
    TOTAL_CAPITAL, SPOT_CAPITAL_PCT, FUTURES_CAPITAL_PCT,
    SPOT_RISK_PER_TRADE, FUTURES_RISK_PER_TRADE, FUTURES_LEVERAGE,
    MAX_STOP_LOSS_PCT, MIN_TAKE_PROFIT_RR,
    TRAILING_STOP, TRAILING_STOP_PCT,
    MAX_SPOT_TRADES, MAX_FUTURES_TRADES, MIN_TRADE_AMOUNT,
    MIN_SCORE_FOR_SPOT, MIN_SCORE_FOR_FUTURES, MIN_SCORE_FOR_SHORT,
    RSI_OVERSOLD, RSI_OVERBOUGHT
)

logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    محرك الاستراتيجية المستقل بالكامل
    Fully autonomous strategy engine — no human input needed
    """

    TRADES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'open_trades.json')

    def __init__(self, okx_client, coinglass_client):
        self.okx = okx_client
        self.coinglass = coinglass_client
        self.open_spot_trades = {}      # الصفقات المفتوحة في Spot
        self.open_futures_trades = {}   # الصفقات المفتوحة في Futures
        # تحميل الصفقات المحفوظة عند الإقلاع
        self._load_trades()
        self._trades_mtime = os.path.getmtime(self.TRADES_FILE) if os.path.exists(self.TRADES_FILE) else 0

    # ----------------------------------------------------------------
    # حفظ واسترداد الصفقات / Persistence
    # ----------------------------------------------------------------
    def _save_trades(self):
        """حفظ الصفقات المفتوحة في ملف JSON للاسترداد عند إعادة التشغيل"""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.TRADES_FILE)), exist_ok=True)
            def serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            data = {
                'spot': self.open_spot_trades,
                'futures': self.open_futures_trades,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.TRADES_FILE, 'w') as f:
                json.dump(data, f, default=serialize, indent=2)
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الصفقات: {e}")

    def _load_trades(self):
        """تحميل الصفقات المحفوظة عند إعادة التشغيل"""
        try:
            if not os.path.exists(self.TRADES_FILE):
                logger.info("📂 لا توجد صفقات محفوظة — بدء نظيف")
                return
            with open(self.TRADES_FILE, 'r') as f:
                data = json.load(f)
            def parse_trade(trade):
                """تحويل open_time من string إلى datetime"""
                if 'open_time' in trade and isinstance(trade['open_time'], str):
                    try:
                        trade['open_time'] = datetime.fromisoformat(trade['open_time'])
                    except Exception:
                        trade['open_time'] = datetime.now()
                return trade
            spot = data.get('spot', {})
            futures = data.get('futures', {})
            self.open_spot_trades = {k: parse_trade(v) for k, v in spot.items()}
            self.open_futures_trades = {k: parse_trade(v) for k, v in futures.items()}
            total = len(self.open_spot_trades) + len(self.open_futures_trades)
            if total > 0:
                logger.info(f"♻️ تم استرداد {total} صفقة مفتوحة من الملف:")
                for sym in self.open_spot_trades:
                    t = self.open_spot_trades[sym]
                    logger.info(f"   📌 SPOT  {sym} | دخول: ${t['entry_price']:.6f} | TP: ${t['take_profit']:.6f} | SL: ${t['stop_loss']:.6f}")
                for sym in self.open_futures_trades:
                    t = self.open_futures_trades[sym]
                    logger.info(f"   📌 FUT   {sym} | دخول: ${t['entry_price']:.6f} | TP: ${t['take_profit']:.6f} | SL: ${t['stop_loss']:.6f}")
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الصفقات: {e}")
            self.open_spot_trades = {}
            self.open_futures_trades = {}

    # ----------------------------------------------------------------
    # حساب أحجام الصفقات / Position Sizing
    # ----------------------------------------------------------------

    def calculate_spot_position(self, available_spot_capital):
        """حساب حجم صفقة Spot بناءً على 3% مخاطرة"""
        risk_amount = available_spot_capital * SPOT_RISK_PER_TRADE
        position_size = risk_amount / MAX_STOP_LOSS_PCT
        return max(position_size, MIN_TRADE_AMOUNT)

    def calculate_futures_position(self, available_futures_capital):
        """حساب حجم صفقة Futures بناءً على 2% مخاطرة مع رافعة 3x"""
        risk_amount = available_futures_capital * FUTURES_RISK_PER_TRADE
        position_size = risk_amount / MAX_STOP_LOSS_PCT
        return max(position_size, MIN_TRADE_AMOUNT)

    # ----------------------------------------------------------------
    # Stop Loss و Take Profit الذكي / Smart SL & TP
    # ----------------------------------------------------------------

    def calculate_smart_sl_tp(self, entry_price, ohlcv_data, direction):
        """
        يحسب Stop Loss و Take Profit بشكل ذكي بناءً على:
        - أدنى/أعلى نقطة في آخر 20 شمعة
        - نسبة ATR (Average True Range) للتقلب
        - نسبة مخاطرة/مكافأة لا تقل عن 1:1.5
        """
        if not ohlcv_data or len(ohlcv_data) < 20:
            if direction in ('LONG', 'SPOT_BUY'):
                sl = entry_price * (1 - MAX_STOP_LOSS_PCT)
                tp = entry_price * (1 + MAX_STOP_LOSS_PCT * MIN_TAKE_PROFIT_RR)
            else:
                sl = entry_price * (1 + MAX_STOP_LOSS_PCT)
                tp = entry_price * (1 - MAX_STOP_LOSS_PCT * MIN_TAKE_PROFIT_RR)
            return sl, tp

        highs  = [c[2] for c in ohlcv_data[-20:]]
        lows   = [c[3] for c in ohlcv_data[-20:]]
        closes = [c[4] for c in ohlcv_data[-20:]]

        # حساب ATR
        atr = self._calculate_atr(ohlcv_data[-20:])

        if direction in ('LONG', 'SPOT_BUY'):
            # SL: أسفل أدنى نقطة بهامش ATR × 0.5
            raw_sl = min(lows) - (atr * 0.5)
            # تأكد أن SL لا يتجاوز الحد الأقصى
            sl = max(raw_sl, entry_price * (1 - MAX_STOP_LOSS_PCT))
            # TP: نسبة 1:2 من المخاطرة
            risk = entry_price - sl
            tp = entry_price + (risk * 2)

        else:  # SHORT
            raw_sl = max(highs) + (atr * 0.5)
            sl = min(raw_sl, entry_price * (1 + MAX_STOP_LOSS_PCT))
            risk = sl - entry_price
            tp = entry_price - (risk * 2)

        logger.info(
            f"SL/TP ذكي | الدخول: {entry_price:.6f} | "
            f"SL: {sl:.6f} | TP: {tp:.6f} | ATR: {atr:.6f}"
        )
        return sl, tp

    def _calculate_atr(self, ohlcv, period=14):
        """حساب Average True Range"""
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low  = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return np.mean(trs[-period:]) if trs else 0

    # ----------------------------------------------------------------
    # التحليل الفني / Technical Analysis
    # ----------------------------------------------------------------

    def technical_analysis(self, ohlcv_data):
        """تحليل RSI + EMA + Bollinger Bands"""
        if not ohlcv_data or len(ohlcv_data) < 50:
            return {"signal": "NEUTRAL", "rsi": 50, "trend": "SIDEWAYS"}

        closes = [c[4] for c in ohlcv_data]
        rsi    = self._calculate_rsi(closes, 14)
        ema20  = self._calculate_ema(closes, 20)
        ema50  = self._calculate_ema(closes, 50)

        trend = "UP" if ema20[-1] > ema50[-1] else "DOWN"

        # إشارة الشراء: RSI منخفض + اتجاه صاعد
        if rsi < RSI_OVERSOLD and trend == "UP":
            signal = "BUY"
        elif rsi < RSI_OVERSOLD + 5 and trend == "UP":
            signal = "BUY"
        # إشارة البيع: RSI مرتفع + اتجاه هابط
        elif rsi > RSI_OVERBOUGHT and trend == "DOWN":
            signal = "SELL"
        elif rsi > RSI_OVERBOUGHT - 5 and trend == "DOWN":
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        return {
            "signal": signal, "rsi": rsi,
            "trend": trend, "ema20": ema20[-1], "ema50": ema50[-1]
        }

    def _calculate_rsi(self, closes, period=14):
        deltas = np.diff(closes)
        gains  = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_ema(self, closes, period):
        ema = [sum(closes[:period]) / period]
        k   = 2 / (period + 1)
        for price in closes[period:]:
            ema.append((price - ema[-1]) * k + ema[-1])
        return ema

    # ----------------------------------------------------------------
    # قرار الدخول المستقل / Autonomous Entry Decision
    # ----------------------------------------------------------------

    def decide_trade(self, opportunity):
        """
        القرار النهائي المستقل: هل ندخل؟ وفي أي سوق؟
        Fully autonomous final decision
        Returns: dict with action details or None
        """
        score       = opportunity['score']
        direction   = opportunity['direction']
        market_type = opportunity['market_type']
        symbol      = opportunity['symbol']

        # التحقق من حدود الصفقات المفتوحة
        spot_full    = len(self.open_spot_trades) >= MAX_SPOT_TRADES
        futures_full = len(self.open_futures_trades) >= MAX_FUTURES_TRADES

        # تجنب تكرار الصفقة على نفس العملة
        if symbol in self.open_spot_trades or symbol in self.open_futures_trades:
            return None

        actions = []

        # --- قرار Spot ---
        if direction == 'LONG' and not spot_full:
            if score >= MIN_SCORE_FOR_SPOT and market_type in ('spot', 'both'):
                actions.append({'market': 'spot', 'direction': 'SPOT_BUY'})

        # --- قرار Futures Long ---
        if direction == 'LONG' and not futures_full:
            if score >= MIN_SCORE_FOR_FUTURES and market_type in ('futures', 'both'):
                actions.append({'market': 'futures', 'direction': 'LONG'})

        # --- قرار Futures Short ---
        if direction == 'SHORT' and not futures_full:
            if score >= MIN_SCORE_FOR_SHORT and market_type == 'futures':
                actions.append({'market': 'futures', 'direction': 'SHORT'})

        return actions if actions else None

    # ----------------------------------------------------------------
    # مراقبة الصفقات المفتوحة / Monitor Open Trades
    # ----------------------------------------------------------------


    def _reload_if_changed(self):
        """إعادة تحميل الصفقات إذا تغيّر الملف خارجياً"""
        try:
            if not os.path.exists(self.TRADES_FILE):
                return
            mtime = os.path.getmtime(self.TRADES_FILE)
            if mtime > self._trades_mtime:
                logger.info("♻️ open_trades.json تغيّر — إعادة التحميل...")
                self._load_trades()
                self._trades_mtime = mtime
        except Exception as e:
            logger.debug(f"_reload_if_changed خطأ: {e}")

    def check_exit_conditions(self, symbol, current_price, market):
        """
        فحص شروط الخروج التلقائي
        Checks SL / TP / Trailing Stop automatically
        """
        self._reload_if_changed()
        trades = self.open_spot_trades if market == 'spot' else self.open_futures_trades
        if symbol not in trades:
            return False, None

        trade = trades[symbol]
        entry  = trade['entry_price']
        sl     = trade['stop_loss']
        tp     = trade['take_profit']
        direc  = trade['direction']

        # تحديث Trailing Stop للصفقات الرابحة
        if TRAILING_STOP:
            if direc in ('SPOT_BUY', 'LONG') and current_price > trade.get('best_price', entry):
                trade['best_price'] = current_price
                new_sl = current_price * (1 - TRAILING_STOP_PCT)
                if new_sl > sl:
                    trade['stop_loss'] = new_sl
                    sl = new_sl
                    logger.info(f"Trailing Stop محدّث لـ {symbol} ({market}): {sl:.6f}")
                    self._save_trades()

            elif direc == 'SHORT' and current_price < trade.get('best_price', entry):
                trade['best_price'] = current_price
                new_sl = current_price * (1 + TRAILING_STOP_PCT)
                if new_sl < sl:
                    trade['stop_loss'] = new_sl
                    sl = new_sl
                    logger.info(f"Trailing Stop محدّث لـ {symbol} SHORT: {sl:.6f}")

        # فحص Stop Loss
        if direc in ('SPOT_BUY', 'LONG') and current_price <= sl:
            return True, 'STOP_LOSS'
        if direc == 'SHORT' and current_price >= sl:
            return True, 'STOP_LOSS'

        # فحص Take Profit
        if direc in ('SPOT_BUY', 'LONG') and current_price >= tp:
            return True, 'TAKE_PROFIT'
        if direc == 'SHORT' and current_price <= tp:
            return True, 'TAKE_PROFIT'

        return False, None
