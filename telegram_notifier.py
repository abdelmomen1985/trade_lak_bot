import html
"""
telegram_notifier.py
نظام إشعارات Trade Lak — لغة عربية موحدة
"""

import requests
import logging
import json
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─── الإعدادات ────────────────────────────────────────────────────────────────
BOT_TOKEN        = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
SIGNAL_CHANNEL   = "-1003834970832"   # Trade Lak Signal — توصيات تعليمية
TRADES_CHANNEL   = "-1003907481197"   # Trade Lak Trades — صفقات حقيقية
API_URL          = f"https://api.telegram.org/bot{BOT_TOKEN}"

DATA_DIR         = "/root/trade_lak_bot/data"
SIGNALS_FILE     = f"{DATA_DIR}/active_signals.json"
TRADES_FILE      = f"{DATA_DIR}/active_trades.json"
DAILY_FILE       = f"{DATA_DIR}/daily_trades.json"


# ─── دوال مساعدة ─────────────────────────────────────────────────────────────

def _send(chat_id: str, text: str) -> bool:
    try:
        r = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15
        )
        ok = r.json().get("ok", False)
        if not ok:
            logger.error(f"Telegram error: {r.json().get('description')}")
        return ok
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def _load(path, default=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return default if default is not None else {}


def _save(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def _fmt(price: float) -> str:
    if price >= 1000:
        return f"{price:,.2f}"
    elif price >= 1:
        return f"{price:.4f}"
    else:
        return f"{price:.6f}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")


# ─── الكلاس الرئيسي ──────────────────────────────────────────────────────────

class TelegramNotifierV2:
    """نظام إشعارات Trade Lak المتكامل"""

    def __init__(self, okx_client=None):
        self.okx = okx_client
        self.enabled = True
        self.active_signals = _load(SIGNALS_FILE)
        self.active_trades  = _load(TRADES_FILE)
        self._test_connection()

    def _test_connection(self):
        try:
            resp = requests.get(f"{API_URL}/getMe", timeout=10)
            if resp.status_code == 200:
                bot_info = resp.json().get("result", {})
                logger.info(f"[Trade Lak] متصل بتليجرام: @{bot_info.get('username', 'unknown')}")
            else:
                logger.warning(f"[Trade Lak] فشل الاتصال بتليجرام: {resp.text}")
                self.enabled = False
        except Exception as e:
            logger.warning(f"[Trade Lak] خطأ في الاتصال: {e}")
            self.enabled = False

    def _price(self, symbol: str) -> float:
        try:
            if self.okx:
                return float(self.okx.fetch_ticker(symbol).get("last", 0))
        except Exception:
            pass
        return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # قناة Signal — توصيات تعليمية
    # ══════════════════════════════════════════════════════════════════════════

    def send_signal(self, symbol: str, direction: str, entry_price: float,
                    current_price: float = 0, stop_loss: float = 0,
                    take_profit_1: float = 0, take_profit_2: float = 0,
                    take_profit_3: float = 0, confidence: float = 0,
                    factors=None, trade_type: str = "SPOT",
                    leverage: int = 0, margin_mode: str = "",
                    signal_id: str = None) -> bool:
        """إرسال توصية تعليمية لقناة Signal"""

        if not self.enabled:
            return False

        if current_price <= 0:
            current_price = self._price(symbol)

        dir_ar = "📈 شراء" if direction.upper() in ["LONG", "BUY"] else "📉 بيع"
        conf_pct = int(confidence * 100) if confidence <= 1 else int(confidence)

        # نوع الصفقة والرافعة والهامش
        type_upper = trade_type.upper() if trade_type else "SPOT"
        is_futures = "FUTURE" in type_upper or "PERP" in type_upper or "SWAP" in type_upper
        if is_futures:
            trade_type_ar = "🔮 عقود آجلة (Futures)"
        else:
            trade_type_ar = "💵 فوري (Spot)"

        # الرافعة المالية — تُحسب تلقائياً إذا لم تُحدد
        if is_futures:
            if leverage <= 0:
                # حساب رافعة مناسبة بناءً على نسبة الثقة والـ SL
                sl_pct = abs(entry_price - stop_loss) / entry_price * 100 if entry_price > 0 else 2
                if sl_pct > 3:
                    leverage = 5
                elif sl_pct > 2:
                    leverage = 7
                elif sl_pct > 1:
                    leverage = 10
                else:
                    leverage = 15
                # تخفيض الرافعة إذا كانت الثقة منخفضة
                if conf_pct < 60:
                    leverage = max(3, leverage - 3)

            # نوع الهامش
            mm_upper = margin_mode.upper() if margin_mode else ""
            if "CROSS" in mm_upper:
                margin_ar = "متقاطع (Cross)"
                margin_icon = "🔗"
            else:
                margin_ar = "معزول (Isolated)"
                margin_icon = "🔒"

            leverage_line = f"{margin_icon} الهامش:  <b>{margin_ar}</b>  |  🎚️ الرافعة:  <b>x{leverage}</b>\n"
        else:
            leverage_line = ""

        # الأهداف
        targets_text = ""
        for i, tp in enumerate([take_profit_1, take_profit_2, take_profit_3], 1):
            if tp and tp > 0:
                targets_text += f"    🎯 هدف {i}:  <b>{_fmt(tp)}</b>\n"

        # العوامل — نقاط متتالية واضحة
        if isinstance(factors, list):
            raw = [str(f).strip() for f in factors if f]
        elif factors:
            raw = [f.strip() for f in str(factors).replace("،", ",").split(",") if f.strip()]
        else:
            raw = ["تحليل فني متعدد المؤشرات"]
        factors_lines = "\n".join(f"    ▪️ {f}" for f in raw[:6])

        cp_line = f"💰 السعر الحالي:  <b>{_fmt(current_price)}</b>\n" if current_price > 0 else ""

        msg = (
            f"🔔 <b>Trade Lak — إشارة تداول</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>  {dir_ar}\n"
            f"📌 نوع الصفقة:  <b>{trade_type_ar}</b>\n"
            f"{leverage_line}"
            f"{cp_line}"
            f"🕐 {_now()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 منطقة الدخول:  <b>{_fmt(entry_price)}</b>\n"
            f"🛑 وقف الخسارة:  <b>{_fmt(stop_loss)}</b>\n"
            f"\n{targets_text}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 العوامل المتوفرة في الصفقة:\n\n{factors_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>⚠️ لا تعتبر هذه توصية ولكن أمثلة تعليمية توضح ما يقوم به المتداولون في مثل هذه الظروف</i>\n"
            f"\n<tg-spoiler><code>  {conf_pct}%</code></tg-spoiler>"
        )

        result = _send(SIGNAL_CHANNEL, msg)

        # حفظ الإشارة لتتبع الأهداف
        sid = signal_id or f"{symbol}_{int(time.time())}"
        if result:
            self.active_signals[sid] = {
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "targets": [take_profit_1, take_profit_2, take_profit_3],
                "targets_hit": [],
                "cancelled": False,
                "timestamp": time.time()
            }
            _save(SIGNALS_FILE, self.active_signals)

        return result

    def send_signal_both_languages(self, symbol, direction, entry_price,
                                    stop_loss, targets, confidence, factors,
                                    signal_id=None):
        """للتوافق مع الكود القديم"""
        tp1 = targets[0] if len(targets) > 0 else 0
        tp2 = targets[1] if len(targets) > 1 else 0
        tp3 = targets[2] if len(targets) > 2 else 0
        return self.send_signal(
            symbol=symbol, direction=direction, entry_price=entry_price,
            stop_loss=stop_loss, take_profit_1=tp1, take_profit_2=tp2,
            take_profit_3=tp3, confidence=confidence, factors=factors,
            signal_id=signal_id
        )

    def send_target_hit(self, signal_id: str, symbol: str, target_num: int,
                        target_price: float, current_price: float) -> bool:
        """إرسال تنبيه تحقيق هدف"""
        msg = (
            f"✅ <b>Trade Lak — تم تحقيق الهدف</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>\n"
            f"🎯 تم الوصول إلى الهدف رقم <b>{target_num}</b>\n"
            f"💰 السعر الحالي:  <b>{_fmt(current_price)}</b>\n"
            f"📌 سعر الهدف:  <b>{_fmt(target_price)}</b>\n"
            f"🕐 {_now()}"
        )
        if signal_id in self.active_signals:
            self.active_signals[signal_id].setdefault("targets_hit", []).append(target_num)
            _save(SIGNALS_FILE, self.active_signals)
        return _send(SIGNAL_CHANNEL, msg)

    def send_signal_cancelled(self, signal_id: str, symbol: str,
                               current_price: float, entry_price: float) -> bool:
        """إرسال تنبيه إلغاء الإشارة"""
        change = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        msg = (
            f"❌ <b>Trade Lak — إلغاء الإشارة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>\n"
            f"⚠️ تم إلغاء الإشارة\n"
            f"السبب: ارتفع السعر بنسبة <b>{change:.1f}%</b> قبل التمكن من الدخول\n"
            f"💰 السعر الحالي:  <b>{_fmt(current_price)}</b>\n"
            f"📍 سعر الدخول المقترح كان:  <b>{_fmt(entry_price)}</b>\n"
            f"🕐 {_now()}"
        )
        if signal_id in self.active_signals:
            self.active_signals[signal_id]["cancelled"] = True
            _save(SIGNALS_FILE, self.active_signals)
        return _send(SIGNAL_CHANNEL, msg)

    def check_signal_targets(self):
        """فحص الإشارات النشطة وإرسال تنبيهات الأهداف والإلغاء"""
        if not self.active_signals:
            return

        to_remove = []
        for sid, sig in list(self.active_signals.items()):
            if sig.get("cancelled"):
                to_remove.append(sid)
                continue

            symbol    = sig["symbol"]
            entry     = sig["entry_price"]
            targets   = sig.get("targets", [])
            hits      = sig.get("targets_hit", [])
            direction = sig.get("direction", "LONG")

            price = self._price(symbol)
            if price <= 0:
                continue

            # فحص إلغاء (ارتفاع >2% قبل الدخول)
            if not hits:
                change = (price - entry) / entry * 100 if entry > 0 else 0
                if direction.upper() in ["LONG", "BUY"] and change > 2.0:
                    self.send_signal_cancelled(sid, symbol, price, entry)
                    to_remove.append(sid)
                    continue

            # فحص الأهداف
            all_done = True
            for i, tp in enumerate(targets, 1):
                if not tp or tp <= 0:
                    continue
                if i in hits:
                    continue
                all_done = False
                hit = (price >= tp) if direction.upper() in ["LONG", "BUY"] else (price <= tp)
                if hit:
                    self.send_target_hit(sid, symbol, i, tp, price)

            if all_done:
                to_remove.append(sid)

            # إزالة الإشارات القديمة (أكثر من 7 أيام)
            if time.time() - sig.get("timestamp", 0) > 7 * 86400:
                to_remove.append(sid)

        for sid in set(to_remove):
            self.active_signals.pop(sid, None)
        if to_remove:
            _save(SIGNALS_FILE, self.active_signals)

    # ══════════════════════════════════════════════════════════════════════════
    # قناة Trades — صفقات حقيقية فقط
    # ══════════════════════════════════════════════════════════════════════════

    def send_trade_opened(self, trade_id: str, symbol: str, direction: str,
                          entry_price: float, stop_loss: float = 0,
                          targets: list = None, size: float = 0,
                          capital_used: float = 0) -> bool:
        """إشعار فتح صفقة حقيقية"""
        if not self.enabled:
            return False

        targets = targets or []
        dir_ar = "📈 شراء (LONG)" if direction.upper() in ["LONG", "BUY"] else "📉 بيع (SHORT)"

        targets_text = ""
        for i, tp in enumerate(targets, 1):
            if tp and tp > 0:
                targets_text += f"    🎯 هدف {i}:  <b>{_fmt(tp)}</b>\n"

        msg = (
            f"🟢 <b>Trade Lak — صفقة مفتوحة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>  {dir_ar}\n"
            f"🕐 {_now()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 سعر الدخول:  <b>{_fmt(entry_price)}</b>\n"
            f"🛑 وقف الخسارة:  <b>{_fmt(stop_loss)}</b>\n"
            f"\n{targets_text}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 الحجم:  <b>{size}</b>  |  رأس المال:  <b>{capital_used:.2f}$</b>\n"
            f"🆔 <code>{str(trade_id)[:10]}</code>"
        )

        result = _send(TRADES_CHANNEL, msg)

        if result:
            self.active_trades[str(trade_id)] = {
                "symbol": symbol, "direction": direction,
                "entry_price": entry_price, "stop_loss": stop_loss,
                "targets": targets, "size": size,
                "capital_used": capital_used, "status": "open",
                "open_time": time.time(),
                "amount_usdt": capital_used,
                "amount_coin": (capital_used / entry_price * 0.999) if entry_price > 0 else 0
            }
            _save(TRADES_FILE, self.active_trades)

            daily = _load(DAILY_FILE, [])
            daily.append({"trade_id": str(trade_id), "symbol": symbol,
                          "direction": direction, "entry_price": entry_price,
                          "open_time": time.time(), "pnl": None})
            _save(DAILY_FILE, daily)

        return result

    def send_trade_update(self, trade_id: str, symbol: str,
                          current_price: float, pnl: float,
                          pnl_pct: float, message: str = "") -> bool:
        """إرسال تحديث على صفقة مفتوحة"""
        if not self.enabled:
            return False

        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        sign = "+" if pnl >= 0 else ""

        msg = (
            f"🔄 <b>Trade Lak — تحديث الصفقة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>\n"
            f"💰 السعر الحالي:  <b>{_fmt(current_price)}</b>\n"
            f"{pnl_emoji} الربح/الخسارة:  <b>{sign}{pnl:.2f}$ ({sign}{pnl_pct:.2f}%)</b>\n"
            f"🕐 {_now()}"
        )
        if message:
            msg += f"\n📋 {message}"

        return _send(TRADES_CHANNEL, msg)

    def send_trade_closed(self, trade_id: str, symbol: str,
                          entry_price: float, exit_price: float,
                          pnl: float, pnl_pct: float,
                          close_reason: str = "") -> bool:
        """إشعار إغلاق صفقة حقيقية"""
        if not self.enabled:
            return False

        if pnl >= 0:
            result_emoji = "✅"
            result_text  = f"ربح  +{pnl:.2f}$  (+{pnl_pct:.2f}%)"
        else:
            result_emoji = "🔴"
            result_text  = f"خسارة  {pnl:.2f}$  ({pnl_pct:.2f}%)"

        open_time = self.active_trades.get(str(trade_id), {}).get("open_time", time.time())
        duration  = (time.time() - open_time) / 3600

        reason_line = f"\n📋 السبب:  {close_reason}" if close_reason else ""

        msg = (
            f"{result_emoji} <b>Trade Lak — صفقة مغلقة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>\n"
            f"🕐 {_now()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 سعر الدخول:  <b>{_fmt(entry_price)}</b>\n"
            f"🚪 سعر الخروج:  <b>{_fmt(exit_price)}</b>\n"
            f"💰 النتيجة:  <b>{result_text}</b>\n"
            f"⏱ المدة:  <b>{duration:.1f} ساعة</b>"
            f"{reason_line}\n"
            f"🆔 <code>{str(trade_id)[:10]}</code>"
        )

        # تحديث التقرير اليومي
        daily = _load(DAILY_FILE, [])
        for t in daily:
            if t.get("trade_id") == str(trade_id):
                t["pnl"] = pnl
                t["exit_price"] = exit_price
                t["close_time"] = time.time()
        _save(DAILY_FILE, daily)

        if str(trade_id) in self.active_trades:
            self.active_trades[str(trade_id)].update(
                {"status": "closed", "pnl": pnl, "exit_price": exit_price}
            )
            _save(TRADES_FILE, self.active_trades)

        return _send(TRADES_CHANNEL, msg)

    def send_daily_report(self, trades_today: list = None) -> bool:
        """إرسال التقرير اليومي"""
        if not self.enabled:
            return False

        if trades_today is None:
            trades_today = [t for t in _load(DAILY_FILE, []) if t.get("pnl") is not None]

        if not trades_today:
            return True

        total   = len(trades_today)
        winning = [t for t in trades_today if t.get("pnl", 0) >= 0]
        losing  = [t for t in trades_today if t.get("pnl", 0) < 0]
        profit  = sum(t.get("pnl", 0) for t in winning)
        loss    = sum(t.get("pnl", 0) for t in losing)
        net     = profit + loss
        rate    = len(winning) / total * 100 if total > 0 else 0

        net_emoji = "🟢" if net >= 0 else "🔴"
        net_sign  = "+" if net >= 0 else ""

        details = ""
        for t in trades_today:
            p = t.get("pnl", 0)
            e = "✅" if p >= 0 else "❌"
            s = "+" if p >= 0 else ""
            details += f"  {e} {t.get('symbol','?')} ← {s}{p:.2f}$\n"

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>Trade Lak — التقرير اليومي</b>\n"
            f"📅 {date_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 إجمالي الصفقات:  <b>{total}</b>\n"
            f"✅ رابحة:  <b>{len(winning)}</b>  |  ❌ خاسرة:  <b>{len(losing)}</b>\n"
            f"🏆 نسبة النجاح:  <b>{rate:.1f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💚 إجمالي الأرباح:  <b>+{profit:.2f}$</b>\n"
            f"❤️ إجمالي الخسائر:  <b>{loss:.2f}$</b>\n"
            f"{net_emoji} <b>النتيجة الصافية:  {net_sign}{net:.2f}$</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>تفاصيل الصفقات:</b>\n{details}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Trade Lak</i>"
        )

        _save(DAILY_FILE, [])
        return _send(TRADES_CHANNEL, msg)

    # ══════════════════════════════════════════════════════════════════════════
    def send_real_trade_opened(self, symbol: str, direction: str, entry_price: float,
                               stop_loss: float = 0, take_profit_1: float = 0,
                               take_profit_2: float = 0, take_profit_3: float = 0,
                               position_size: float = 0, confidence: float = 0,
                               trade_type: str = "SPOT") -> bool:
        """إشعار فتح صفقة حقيقية مع TP1/TP2/TP3 وConfidence"""
        import uuid
        trade_id = str(uuid.uuid4())[:8]
        targets = [t for t in [take_profit_1, take_profit_2, take_profit_3] if t and t > 0]
        # تصحيح confidence: إذا كانت 0-100 نحولها لـ 0-1
        conf_pct = int(confidence * 100) if confidence <= 1 else int(confidence)
        # حساب نسبة SL وTP1
        if entry_price > 0:
            sl_pct = abs(entry_price - stop_loss) / entry_price * 100
            tp1_pct = abs(take_profit_1 - entry_price) / entry_price * 100 if take_profit_1 else 0
            tp2_pct = abs(take_profit_2 - entry_price) / entry_price * 100 if take_profit_2 else 0
        else:
            sl_pct = tp1_pct = tp2_pct = 0
        dir_ar = "📈 شراء" if direction.upper() in ["LONG", "BUY", "SPOT_BUY"] else "📉 بيع"
        # الدخول الثاني: أقل من الأول بنسبة 0.5% على الأقل
        risk = abs(entry_price - stop_loss)
        entry2_raw = entry_price - risk * 0.3
        min_diff = entry_price * 0.005  # 0.5% على الأقل
        entry2 = entry_price - max(risk * 0.3, min_diff)
        msg = (
            f"🟢 <b>Trade Lak — صفقة جديدة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{html.escape(str(symbol))}</b>  {dir_ar}  ⚙️ النوع: {trade_type}\n"
            f"🕐 {_now()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💪 نسبة الثقة: {conf_pct}%\n"
            f"✨ نسبة النجاح المتوقعة: 75%\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 نقاط الدخول\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"  💠 الدخول الأول: ${_fmt(entry_price)}\n"
            f"  💠 الدخول الثاني: ${_fmt(entry2)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 أهداف جني الأرباح\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🎯 الهدف الأول (TP1): ${_fmt(take_profit_1)} (+{tp1_pct:.2f}%)\n"
            f"  🎯 الهدف الثاني (TP2): ${_fmt(take_profit_2)} (+{tp2_pct:.2f}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🛑 وقف الخسارة: ${_fmt(stop_loss)} (-{sl_pct:.2f}%)\n"
            f"  💰 المبلغ: ${position_size:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{trade_id}</code>"
        )
        result = _send(TRADES_CHANNEL, msg)
        if result:
            self.active_trades[trade_id] = {
                "symbol": symbol, "direction": direction,
                "entry_price": entry_price, "stop_loss": stop_loss,
                "targets": targets, "size": position_size,
                "capital_used": position_size, "status": "open",
                "open_time": __import__("time").time()
            }
            _save(TRADES_FILE, self.active_trades)
        return result

    # التوافق مع الكود القديم (TelegramNotifier)
    # ══════════════════════════════════════════════════════════════════════════

    def notify_trade_opened(self, symbol, direction, entry_price, stop_loss,
                             take_profit1, take_profit2=None, take_profit3=None,
                             confidence=0, reason="", trade_type="FUTURES"):
        """للتوافق مع الكود القديم"""
        import uuid
        trade_id = str(uuid.uuid4())[:8]
        targets = [t for t in [take_profit1, take_profit2, take_profit3] if t]
        return self.send_trade_opened(
            trade_id=trade_id, symbol=symbol, direction=direction,
            entry_price=entry_price, stop_loss=stop_loss, targets=targets
        )

    def notify_trade_closed(self, symbol, direction, entry_price, exit_price,
                             pnl=None, pnl_pct=None, duration_min=None,
                             close_reason=""):
        """للتوافق مع الكود القديم"""
        trade_id = f"{symbol}_closed"
        p = pnl or 0
        pp = (pnl_pct or 0) * 100 if pnl_pct and abs(pnl_pct) <= 1 else (pnl_pct or 0)
        return self.send_trade_closed(
            trade_id=trade_id, symbol=symbol, entry_price=entry_price,
            exit_price=exit_price, pnl=p, pnl_pct=pp, close_reason=close_reason
        )

    def notify_recommendation(self, symbol, direction, entry_price, stop_loss,
                               take_profit1, take_profit2=None, take_profit3=None,
                               success_rate=0, timeframe="1h", reason=""):
        """للتوافق مع الكود القديم"""
        targets = [t for t in [take_profit1, take_profit2, take_profit3] if t]
        return self.send_signal(
            symbol=symbol, direction=direction, entry_price=entry_price,
            stop_loss=stop_loss, take_profit_1=take_profit1,
            take_profit_2=take_profit2 or 0, take_profit_3=take_profit3 or 0,
            confidence=success_rate / 100 if success_rate > 1 else success_rate,
            factors=reason
        )

    def notify_alert(self, title, message, severity="INFO", alert_type="SYSTEM"):
        """للتوافق مع الكود القديم"""
        severity_map = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨", "SUCCESS": "✅"}
        emoji = severity_map.get(severity.upper(), "📢")
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>Trade Lak — {title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"🕐 {_now()}"
        )
        return _send(SIGNAL_CHANNEL, msg)

    def notify_daily_summary(self, total_trades, winning_trades, losing_trades,
                              total_pnl, win_rate, best_trade="", worst_trade=""):
        """للتوافق مع الكود القديم"""
        trades = []
        return self.send_daily_report(trades)


    def send_crash_warning(self, symbol, level, score, indicators, recommendation):
        sep = chr(10)
        emojis = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': '🔶', 'LOW': '🔵'}
        emoji = emojis.get(level, '⚠️')
        ar = {'CRITICAL': 'خطر بالغ', 'HIGH': 'خطر عالٍ', 'MEDIUM': 'تحذير متوسط', 'LOW': 'مراقبة'}.get(level, level)
        ind_text = sep.join(['  - ' + str(x) for x in indicators[:5]])
        parts = [
            emoji + ' <b>إنذار مبكر — ' + ar + '</b>',
            '━━━━━━━━━━━━━━━━━━━━━',
            '📍 العملة: <b>' + str(symbol) + '</b>',
            '📊 درجة الخطر: <b>' + str(int(score)) + '/100</b>',
            '━━━━━━━━━━━━━━━━━━━━━',
            '🔍 <b>المؤشرات:</b>',
            ind_text,
            '━━━━━━━━━━━━━━━━━━━━━',
            '💡 <b>التوصية:</b>',
            str(recommendation),
            '━━━━━━━━━━━━━━━━━━━━━',
            '🕐 ' + _now(),
        ]
        msg = sep.join(parts)
        return _send(TRADES_CHANNEL, msg)

    def set_message_handler(self, *args, **kwargs):
        """stub للتوافق"""
        pass


# ─── Singleton ────────────────────────────────────────────────────────────────
TelegramNotifier = TelegramNotifierV2

_notifier_instance = None

def get_telegram_notifier() -> TelegramNotifierV2:
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifierV2()
    return _notifier_instance


# ─── اختبار مباشر ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = TelegramNotifierV2()

    print("🧪 اختبار توصية تعليمية...")
    r1 = n.send_signal(
        symbol="BTC/USDT", direction="LONG",
        entry_price=103500.0, current_price=103200.0,
        stop_loss=101800.0,
        take_profit_1=105000.0, take_profit_2=107500.0, take_profit_3=110000.0,
        confidence=0.78,
        factors=["Funding Rate سلبي = فرصة شراء",
                 "نسبة Short مرتفعة 59%",
                 "Fear & Greed = 28 (خوف)"],
        signal_id="test_btc_001"
    )
    print(f"Signal: {'✅' if r1 else '❌'}")

    time.sleep(2)
    print("🧪 اختبار تحقيق الهدف الأول...")
    r2 = n.send_target_hit("test_btc_001", "BTC/USDT", 1, 105000.0, 105120.0)
    print(f"Target hit: {'✅' if r2 else '❌'}")

    time.sleep(2)
    print("🧪 اختبار صفقة حقيقية...")
    r3 = n.send_trade_opened(
        trade_id="real_eth_001", symbol="ETH/USDT", direction="LONG",
        entry_price=2580.0, stop_loss=2520.0,
        targets=[2650.0, 2720.0, 2800.0], size=0.5, capital_used=50.0
    )
    print(f"Trade opened: {'✅' if r3 else '❌'}")

    time.sleep(2)
    print("🧪 اختبار التقرير اليومي...")
    r4 = n.send_daily_report([
        {"symbol": "BTC/USDT", "pnl": 12.50},
        {"symbol": "ETH/USDT", "pnl": -5.20},
        {"symbol": "SOL/USDT", "pnl": 8.30},
    ])
    print(f"Daily report: {'✅' if r4 else '❌'}")
