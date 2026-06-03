"""
Dashboard Notifier - Trade Lak Bot
يرسل بيانات الصفقات والتوصيات والتنبيهات إلى لوحة التحكم
Dashboard URL: https://tradelakdash-cmxz8kc9.manus.space
"""
import logging
import requests
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DASHBOARD_URL = "https://tradelakdash-cmxz8kc9.manus.space"
BOT_API_KEY = "trade-lak-bot-key-2024"
HEADERS = {
    "x-bot-api-key": BOT_API_KEY,
    "Content-Type": "application/json"
}
TIMEOUT = 15  # seconds


class DashboardNotifier:
    """
    يرسل بيانات البوت الحقيقية إلى لوحة التحكم تلقائياً
    """
    # تخزين trade_ids لربط الفتح بالإغلاق
    _open_trade_ids: dict = {}  # symbol -> dashboard_trade_id

    def __init__(self, dashboard_url: str = DASHBOARD_URL, api_key: str = BOT_API_KEY):
        self.base_url = dashboard_url.rstrip("/")
        self.headers = {
            "x-bot-api-key": api_key,
            "Content-Type": "application/json"
        }
        self._enabled = True
        # اختبار الاتصال عند التهيئة
        self._check_connection()

    def _check_connection(self):
        """اختبار الاتصال بلوحة التحكم"""
        try:
            resp = requests.get(
                f"{self.base_url}/api/bot/status",
                headers=self.headers,
                timeout=5
            )
            if resp.status_code == 200:
                logger.info("✅ Dashboard Notifier: Connected to Trade Lak Dashboard")
            else:
                logger.warning(f"⚠️ Dashboard Notifier: Unexpected status {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Dashboard Notifier: Connection check failed: {e}")
            # لا نوقف البوت إذا فشل الاتصال

    def _post(self, endpoint: str, data: dict) -> bool:
        """إرسال طلب POST للوحة التحكم"""
        if not self._enabled:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/api/bot/{endpoint}",
                headers=self.headers,
                json=data,
                timeout=TIMEOUT
            )
            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"[Dashboard] POST /{endpoint} failed: {resp.status_code} - {resp.text[:100]}")
                return False
        except Exception as e:
            logger.warning(f"[Dashboard] POST /{endpoint} error: {e}")
            return False

    # ─── Trades ──────────────────────────────────────────────────────────────

    def notify_trade_opened(self, trade_data: Dict) -> bool:
        """
        إخطار لوحة التحكم بفتح صفقة جديدة
        trade_data يجب أن يحتوي على:
          symbol, direction, entryPrice, stopLoss, takeProfit1/2/3,
          positionSize, confidence, successRate, reason, analysis, tradeType
        """
        symbol = trade_data.get("symbol", "")
        direction = trade_data.get("direction", trade_data.get("trade_type", "BUY"))
        # تطبيع اتجاه الصفقة
        if direction in ("SPOT_BUY",):
            direction = "BUY"
        elif direction in ("SPOT_SELL",):
            direction = "SELL"

        payload = {
            "symbol": symbol,
            "tradeType": trade_data.get("tradeType", trade_data.get("trade_type", "SPOT")).upper(),
            "direction": direction,
            "entryPrice": float(trade_data.get("entryPrice", trade_data.get("entry_price", 0))),
            "entryPrice2": float(trade_data.get("entryPrice2", trade_data.get("entry_price_2", 0))) or None,
            "stopLoss": float(trade_data.get("stopLoss", trade_data.get("stop_loss", 0))) or None,
            "takeProfit1": float(trade_data.get("takeProfit1", trade_data.get("take_profit_1", 0))) or None,
            "takeProfit2": float(trade_data.get("takeProfit2", trade_data.get("take_profit_2", 0))) or None,
            "takeProfit3": float(trade_data.get("takeProfit3", trade_data.get("take_profit_3", 0))) or None,
            "positionSize": float(trade_data.get("positionSize", trade_data.get("position_size", 0))) or None,
            "confidence": round(float(trade_data.get("confidence", 0)) * 100, 2) if float(trade_data.get("confidence", 0)) <= 1.0 else round(float(trade_data.get("confidence", 0)), 2),
            "successRate": round(float(trade_data.get("successRate", trade_data.get("success_rate", 0))), 2),
            "reason": str(trade_data.get("reason", "")),
            "analysis": str(trade_data.get("analysis", "")),
        }
        # إزالة القيم None
        payload = {k: v for k, v in payload.items() if v is not None and v != 0.0 or k in ("symbol", "direction", "entryPrice", "tradeType")}

        # إرسال وتخزين trade_id من الرد مباشرة
        try:
            resp = requests.post(
                f"{self.base_url}/api/bot/trade",
                headers=self.headers,
                json=payload,
                timeout=TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                trade_obj = data.get("trade", {})
                # Handle both dict response (dev) and list response (production MySQL raw)
                if isinstance(trade_obj, dict):
                    trade_id_resp = trade_obj.get("id")
                elif isinstance(trade_obj, list) and trade_obj:
                    trade_id_resp = trade_obj[0].get("insertId") if isinstance(trade_obj[0], dict) else None
                else:
                    trade_id_resp = None
                if trade_id_resp:
                    DashboardNotifier._open_trade_ids[symbol] = trade_id_resp
                    logger.info(f"📊 [Dashboard] Trade opened: {symbol} {direction} (id={trade_id_resp})")
                    return {'id': trade_id_resp, 'success': True}
                else:
                    logger.info(f"📊 [Dashboard] Trade opened: {symbol} {direction}")
                return True
            else:
                logger.warning(f"[Dashboard] POST /trade failed: {resp.status_code} - {resp.text[:100]}")
                return False
        except Exception as e:
            logger.warning(f"[Dashboard] notify_trade_opened error: {e}")
            return False

    def notify_trade_closed(self, trade_id: Optional[int] = None, trade_data: Dict = None) -> bool:
        """
        إخطار لوحة التحكم بإغلاق صفقة
        trade_data يجب أن يحتوي على:
          symbol, exitPrice, profitLoss, profitLossPct, closeReason
        """
        if trade_data is None:
            trade_data = {}

        symbol = trade_data.get("symbol", "")
        exit_price = float(trade_data.get("exitPrice", trade_data.get("exit_price", 0)))
        pnl = float(trade_data.get("profitLoss", trade_data.get("profit_loss", 0)))
        pnl_pct = float(trade_data.get("profitLossPct", trade_data.get("profit_loss_pct", 0)))
        close_reason = str(trade_data.get("closeReason", trade_data.get("reason", trade_data.get("close_reason", "BOT_AUTO"))))

        # محاولة الحصول على trade_id من الذاكرة
        if not trade_id and symbol in DashboardNotifier._open_trade_ids:
            trade_id = DashboardNotifier._open_trade_ids.pop(symbol, None)

        payload = {
            "action": "close",
            "symbol": symbol,
            "exitPrice": exit_price,
            "profitLoss": pnl,
            "profitLossPct": pnl_pct,
            "closeReason": close_reason,
        }
        if trade_id:
            payload["id"] = trade_id

        ok = self._post("trade", payload)
        if ok:
            emoji = "✅" if pnl >= 0 else "❌"
            logger.info(f"📊 [Dashboard] Trade closed: {symbol} {emoji} {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
        return ok

    def notify_trade_tp_hit(self, trade_id: int, symbol: str, tp_level: int, current_price: float) -> bool:
        """إخطار بوصول الصفقة لهدف الربح"""
        tp_field = f"tp{tp_level}Hit"
        payload = {
            "action": "update",
            "id": trade_id,
            "symbol": symbol,
            "currentPrice": current_price,
            tp_field: True,
        }
        ok = self._post("trade", payload)
        if ok:
            logger.info(f"📊 [Dashboard] TP{tp_level} hit: {symbol} @ {current_price}")
        return ok

    def notify_trade_sl_hit(self, trade_id: int, symbol: str, current_price: float) -> bool:
        """إخطار بضرب وقف الخسارة"""
        payload = {
            "action": "update",
            "id": trade_id,
            "symbol": symbol,
            "currentPrice": current_price,
            "slHit": True,
        }
        ok = self._post("trade", payload)
        if ok:
            logger.info(f"📊 [Dashboard] SL hit: {symbol} @ {current_price}")
        return ok

    # ─── Recommendations ─────────────────────────────────────────────────────

    def notify_recommendation(self, rec_data: Dict) -> bool:
        """
        إرسال توصية تداول للوحة التحكم
        rec_data يجب أن يحتوي على:
          symbol, direction, entryPrice, stopLoss, takeProfit1/2/3,
          successRate, confidence, reason, analysis
        """
        symbol = rec_data.get("symbol", "")
        direction = rec_data.get("direction", "BUY")
        if direction in ("SPOT_BUY",):
            direction = "BUY"
        elif direction in ("SPOT_SELL",):
            direction = "SELL"

        payload = {
            "symbol": symbol,
            "tradeType": rec_data.get("tradeType", rec_data.get("trade_type", "SPOT")).upper(),
            "direction": direction,
            "entryPrice": float(rec_data.get("entryPrice", rec_data.get("entry_price", rec_data.get("current_price", 0)))),
            "entryPrice2": float(rec_data.get("entryPrice2", rec_data.get("entry_price_2", 0))) or None,
            "stopLoss": float(rec_data.get("stopLoss", rec_data.get("stop_loss", 0))) or None,
            "takeProfit1": float(rec_data.get("takeProfit1", rec_data.get("take_profit_1", rec_data.get("take_profit", 0)))) or None,
            "takeProfit2": float(rec_data.get("takeProfit2", rec_data.get("take_profit_2", 0))) or None,
            "takeProfit3": float(rec_data.get("takeProfit3", rec_data.get("take_profit_3", 0))) or None,
            "successRate": float(rec_data.get("successRate", rec_data.get("success_rate", 0))),
            "confidence": float(rec_data.get("confidence", 0)) * 100 if float(rec_data.get("confidence", 0)) <= 1 else float(rec_data.get("confidence", 0)),
            "reason": str(rec_data.get("reason", "")),
            "analysis": str(rec_data.get("analysis", "")),
        }
        payload = {k: v for k, v in payload.items() if v is not None and v != 0.0 or k in ("symbol", "direction", "entryPrice", "tradeType")}

        ok = self._post("recommendation", payload)
        if ok:
            logger.info(f"📊 [Dashboard] Recommendation sent: {symbol} {direction} (SR: {rec_data.get('success_rate', 0):.0f}%)")
        return ok

    # ─── Alerts ──────────────────────────────────────────────────────────────

    def notify_alert(self, alert_type: str, title: str, message: str,
                     symbol: str = None, trade_id: int = None,
                     severity: str = "INFO") -> bool:
        """إرسال تنبيه للوحة التحكم"""
        valid_types = ["TRADE_OPENED", "TRADE_CLOSED", "TP1_HIT", "TP2_HIT", "TP3_HIT", "SL_HIT", "RECOMMENDATION", "SYSTEM"]
        valid_severities = ["INFO", "SUCCESS", "WARNING", "DANGER"]

        payload = {
            "type": alert_type if alert_type in valid_types else "SYSTEM",
            "title": title[:200],
            "message": message,
            "severity": severity if severity in valid_severities else "INFO",
        }
        if symbol:
            payload["symbol"] = symbol
        if trade_id:
            payload["tradeId"] = trade_id

        return self._post("alert", payload)

    # ─── Backtests ───────────────────────────────────────────────────────────

    def notify_backtest_result(self, backtest_data: Dict) -> bool:
        """إرسال نتائج Backtesting للوحة التحكم"""
        payload = {
            "name": backtest_data.get("name", f"{backtest_data.get('symbol')} {backtest_data.get('strategy')}"),
            "symbol": backtest_data.get("symbol", ""),
            "strategy": backtest_data.get("strategy", ""),
            "timeframe": backtest_data.get("timeframe", "1h"),
            "startDate": backtest_data.get("startDate", backtest_data.get("start_date", "")),
            "endDate": backtest_data.get("endDate", backtest_data.get("end_date", "")),
            "initialCapital": float(backtest_data.get("initialCapital", backtest_data.get("initial_capital", 1000))),
            "finalCapital": float(backtest_data.get("finalCapital", backtest_data.get("final_capital", 0))) or None,
            "totalTrades": int(backtest_data.get("totalTrades", backtest_data.get("total_trades", 0))),
            "winningTrades": int(backtest_data.get("winningTrades", backtest_data.get("winning_trades", 0))),
            "losingTrades": int(backtest_data.get("losingTrades", backtest_data.get("losing_trades", 0))),
            "winRate": float(backtest_data.get("winRate", backtest_data.get("win_rate", 0))),
            "totalProfit": float(backtest_data.get("totalProfit", backtest_data.get("total_profit", 0))) or None,
            "maxDrawdown": float(backtest_data.get("maxDrawdown", backtest_data.get("max_drawdown", 0))) or None,
            "sharpeRatio": float(backtest_data.get("sharpeRatio", backtest_data.get("sharpe_ratio", 0))) or None,
            "resultData": backtest_data.get("resultData", backtest_data.get("result_data")),
        }
        ok = self._post("backtest", payload)
        if ok:
            logger.info(f"📊 [Dashboard] Backtest saved: {payload['symbol']} {payload['strategy']} WR:{payload['winRate']:.1f}%")
        return ok


    def notify_balance(self, spot_balance: float, futures_balance: float, total_balance: float) -> bool:
        """إرسال تحديث الرصيد الحقيقي للوحة التحكم"""
        payload = {
            "spotBalance": round(spot_balance, 2),
            "futuresBalance": round(futures_balance, 2),
            "totalBalance": round(total_balance, 2),
        }
        ok = self._post("balance", payload)
        if ok:
            logger.info(f"📊 [Dashboard] Balance updated: Spot=${spot_balance:.2f} | Futures=${futures_balance:.2f} | Total=${total_balance:.2f}")
        return ok

    def sync_open_trades(self, active_symbols: list, active_trade_ids: list = None) -> bool:
        """
        مزامنة الصفقات المفتوحة مع قاعدة البيانات عند بدء التشغيل.
        يُغلق أي صفقة في قاعدة البيانات غير موجودة في ذاكرة البوت.
        active_symbols: قائمة رموز الصفقات المفتوحة حالياً في ذاكرة البوت
        active_trade_ids: قائمة IDs الصفقات في لوحة التحكم (اختياري)
        """
        if not self._enabled:
            return False
        try:
            payload = {
                "activeSymbols": active_symbols,
                "activeTradeIds": active_trade_ids or [],
            }
            resp = requests.post(
                f"{self.base_url}/api/bot/sync-trades",
                headers=self.headers,
                json=payload,
                timeout=TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                closed = data.get("closedStale", 0)
                if closed > 0:
                    logger.info(f"📊 [Dashboard] Synced trades: closed {closed} stale open trades")
                else:
                    logger.info(f"📊 [Dashboard] Synced trades: all {data.get('totalOpen', 0)} open trades are active")
                return True
            else:
                logger.warning(f"[Dashboard] sync-trades failed: {resp.status_code} - {resp.text[:100]}")
                return False
        except Exception as e:
            logger.warning(f"[Dashboard] sync_open_trades error: {e}")
            return False

    def disable(self):
        """تعطيل الإرسال مؤقتاً"""
        self._enabled = False
        logger.info("[Dashboard] Notifier disabled")

    def enable(self):
        """تفعيل الإرسال"""
        self._enabled = True
        logger.info("[Dashboard] Notifier enabled")


# ─── Singleton helper ────────────────────────────────────────────────────────
_notifier_instance: Optional[DashboardNotifier] = None

def get_dashboard_notifier() -> DashboardNotifier:
    """الحصول على نسخة واحدة من DashboardNotifier"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = DashboardNotifier()
    return _notifier_instance
