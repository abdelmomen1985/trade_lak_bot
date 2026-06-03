"""
capital_guard.py — نظام حماية رأس المال وخطة المضاعفة
=======================================================

الوظائف:
1. إيقاف تلقائي 24 ساعة عند خسارتين متتاليتين
2. رفع حجم الصفقة تلقائياً عند تجاوز عتبات رأس المال
3. تقرير أسبوعي كل يوم أحد (يُرسل عبر Telegram)
"""

import json
import logging
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# مسارات الملفات
# ─────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
DATA_DIR       = BASE_DIR / "data"
GUARD_FILE     = DATA_DIR / "capital_guard_state.json"
TRADE_HIST_CSV = BASE_DIR / "logs" / "trades_history.csv"

# ─────────────────────────────────────────────
# عتبات رفع حجم الصفقة (خطة المضاعفة 30x)
# ─────────────────────────────────────────────
# رأس المال الابتدائي: $1,412
# الهدف النهائي: $42,743 في 13 أسبوعاً
CAPITAL_TIERS = [
    # (عتبة رأس المال, حجم الصفقة الجديد, الوصف)
    (1412,   300,  "المرحلة 1 — البداية"),
    (3000,   450,  "المرحلة 2 — رأس المال تجاوز $3K"),
    (6000,   700,  "المرحلة 3 — رأس المال تجاوز $6K"),
    (12000,  1200, "المرحلة 4 — رأس المال تجاوز $12K"),
    (25000,  2500, "المرحلة 5 — رأس المال تجاوز $25K"),
]

# ─────────────────────────────────────────────
# إعدادات الحماية
# ─────────────────────────────────────────────
MAX_CONSECUTIVE_LOSSES = 2      # عدد الخسائر المتتالية قبل الإيقاف
COOLDOWN_HOURS         = 12     # ساعات الراحة بعد الإيقاف
MAX_DAILY_LOSS_PCT     = 0.06   # الحد الأقصى للخسارة اليومية 6%
WEEKLY_REPORT_DAY      = 6      # 6 = الأحد (0=الاثنين)
WEEKLY_REPORT_HOUR     = 8      # 8 صباحاً


def _load_state() -> dict:
    """تحميل حالة الحماية من الملف"""
    default = {
        "consecutive_losses": 0,
        "last_loss_time": 0,
        "cooldown_until": 0,
        "current_tier": 0,
        "current_trade_size": 300,
        "total_capital": 1412.25,
        "week_start_capital": 1412.25,
        "week_start_time": time.time(),
        "last_weekly_report": 0,
        "daily_loss_today": 0.0,
        "last_day_reset": datetime.now().strftime("%Y-%m-%d"),
        "trade_count_today": 0,
        "wins_today": 0,
        "losses_today": 0,
    }
    try:
        DATA_DIR.mkdir(exist_ok=True)
        if GUARD_FILE.exists():
            with open(GUARD_FILE) as f:
                saved = json.load(f)
                default.update(saved)
    except Exception as e:
        logger.warning(f"capital_guard: لم يتمكن من تحميل الحالة: {e}")
    return default


def _save_state(state: dict):
    """حفظ حالة الحماية"""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(GUARD_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"capital_guard: خطأ في الحفظ: {e}")


def _reset_daily_if_needed(state: dict) -> dict:
    """إعادة تعيين العدادات اليومية عند منتصف الليل"""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_day_reset") != today:
        state["daily_loss_today"]  = 0.0
        state["trade_count_today"] = 0
        state["wins_today"]        = 0
        state["losses_today"]      = 0
        state["last_day_reset"]    = today
        logger.info("📅 capital_guard: إعادة تعيين العدادات اليومية")
    return state


def _get_current_tier(capital: float) -> tuple:
    """تحديد المرحلة الحالية بناءً على رأس المال"""
    current = CAPITAL_TIERS[0]
    for tier in CAPITAL_TIERS:
        if capital >= tier[0]:
            current = tier
    return current


class CapitalGuard:
    """
    نظام حماية رأس المال وخطة المضاعفة
    يُستدعى من main.py في كل صفقة
    """

    def __init__(self, telegram_bot_token: str = None, chat_ids: list = None,
                 private_chat_id: str = None):
        self.state = _load_state()
        self.bot_token = telegram_bot_token
        # التقارير الداخلية تذهب فقط للمحادثة الخاصة بالمالك
        self.private_chat_id = private_chat_id
        self.chat_ids = chat_ids or []  # محتفظ للتوافق فقط
        logger.info(
            f"✅ CapitalGuard initialized — "
            f"رأس المال: ${self.state['total_capital']:,.2f} | "
            f"حجم الصفقة: ${self.state['current_trade_size']} | "
            f"خسائر متتالية: {self.state['consecutive_losses']}"
        )

    def _send_telegram(self, message: str):
        """إرسال رسالة تيليجرام للمحادثة الخاصة بالمالك فقط"""
        if not self.bot_token:
            return
        # إرسال للمحادثة الخاصة فقط — ليس للقنوات العامة
        target = self.private_chat_id
        if not target:
            return
        import requests
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": target, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            logger.error(f"capital_guard telegram error: {e}")

    def is_trading_allowed(self) -> tuple:
        """
        التحقق من السماح بالتداول
        يُعيد: (مسموح: bool, السبب: str)
        """
        self.state = _reset_daily_if_needed(self.state)

        # فحص فترة الراحة
        if time.time() < self.state["cooldown_until"]:
            remaining = (self.state["cooldown_until"] - time.time()) / 3600
            return False, f"⏸️ فترة راحة إلزامية — متبقي {remaining:.1f} ساعة"

        # فحص الخسارة اليومية
        capital = self.state["total_capital"]
        if capital > 0:
            daily_loss_pct = self.state["daily_loss_today"] / capital
            if daily_loss_pct >= MAX_DAILY_LOSS_PCT:
                return False, f"🛑 تجاوز الحد الأقصى للخسارة اليومية ({daily_loss_pct*100:.1f}%)"

        return True, "✅ التداول مسموح"

    def on_trade_closed(self, symbol: str, profit_usdt: float, profit_pct: float,
                        exit_reason: str, capital_after: float):
        """
        يُستدعى عند إغلاق كل صفقة
        يُحدِّث العدادات ويتخذ قرار الإيقاف إذا لزم
        """
        self.state = _reset_daily_if_needed(self.state)
        self.state["total_capital"]    = capital_after
        self.state["trade_count_today"] += 1

        is_loss = profit_usdt < 0

        if is_loss:
            self.state["consecutive_losses"] += 1
            self.state["last_loss_time"]      = time.time()
            self.state["daily_loss_today"]   += abs(profit_usdt)
            self.state["losses_today"]        += 1
            logger.warning(
                f"📉 capital_guard: خسارة #{self.state['consecutive_losses']} "
                f"— {symbol} | {profit_pct:+.2f}% | ${profit_usdt:+.2f}"
            )

            # ─── إيقاف عند خسارتين متتاليتين ───
            if self.state["consecutive_losses"] >= MAX_CONSECUTIVE_LOSSES:
                cooldown_until = time.time() + (COOLDOWN_HOURS * 3600)
                self.state["cooldown_until"]      = cooldown_until
                self.state["consecutive_losses"]  = 0  # إعادة العداد

                resume_time = datetime.fromtimestamp(cooldown_until).strftime("%Y-%m-%d %H:%M")
                msg = (
                    f"⏸️ <b>إيقاف تلقائي — خسارتان متتاليتان</b>\n"
                    f"{'─' * 30}\n"
                    f"📉 آخر خسارة: <b>{symbol}</b> ({profit_pct:+.2f}%)\n"
                    f"⏰ فترة الراحة: <b>24 ساعة</b>\n"
                    f"▶️ استئناف التداول: <b>{resume_time}</b>\n"
                    f"{'─' * 30}\n"
                    f"💡 <i>وقت للمراجعة وتحليل السبب</i>"
                )
                self._send_telegram(msg)
                logger.warning(f"⏸️ capital_guard: إيقاف 24 ساعة — استئناف: {resume_time}")

        else:
            # ربح — إعادة تعيين عداد الخسائر المتتالية
            self.state["consecutive_losses"] = 0
            self.state["wins_today"]         += 1
            logger.info(
                f"✅ capital_guard: ربح — {symbol} | {profit_pct:+.2f}% | ${profit_usdt:+.2f}"
            )

        # ─── فحص رفع حجم الصفقة ───
        self._check_tier_upgrade(capital_after)

        _save_state(self.state)

    def _check_tier_upgrade(self, capital: float):
        """رفع حجم الصفقة تلقائياً عند تجاوز عتبة جديدة"""
        tier_capital, tier_size, tier_desc = _get_current_tier(capital)
        old_size = self.state["current_trade_size"]

        if tier_size > old_size:
            self.state["current_trade_size"] = tier_size
            msg = (
                f"🚀 <b>ترقية تلقائية — {tier_desc}</b>\n"
                f"{'─' * 30}\n"
                f"💰 رأس المال الحالي: <b>${capital:,.2f}</b>\n"
                f"📈 حجم الصفقة الجديد: <b>${tier_size}</b>\n"
                f"   (كان: ${old_size})\n"
                f"{'─' * 30}\n"
                f"🎯 <i>خطة المضاعفة 30x تسير بالمسار الصحيح!</i>"
            )
            self._send_telegram(msg)
            logger.info(f"🚀 capital_guard: ترقية حجم الصفقة ${old_size} → ${tier_size}")

    def get_trade_size(self) -> int:
        """إرجاع حجم الصفقة الحالي"""
        return self.state["current_trade_size"]

    def check_weekly_report(self):
        """
        يُستدعى في كل دورة — يُرسل التقرير الأسبوعي كل يوم أحد الساعة 8 صباحاً
        """
        now = datetime.now()
        # الأحد = 6 في Python (0=الاثنين)
        if now.weekday() != WEEKLY_REPORT_DAY:
            return
        if now.hour != WEEKLY_REPORT_HOUR:
            return

        # تجنب الإرسال مرتين في نفس الأسبوع
        last_report = self.state.get("last_weekly_report", 0)
        if (time.time() - last_report) < (6 * 24 * 3600):  # أقل من 6 أيام
            return

        self._send_weekly_report()
        self.state["last_weekly_report"]  = time.time()
        self.state["week_start_capital"]  = self.state["total_capital"]
        self.state["week_start_time"]     = time.time()
        _save_state(self.state)

    def _send_weekly_report(self):
        """إرسال التقرير الأسبوعي"""
        capital_now   = self.state["total_capital"]
        capital_start = self.state.get("week_start_capital", 1412.25)
        week_pnl      = capital_now - capital_start
        week_pnl_pct  = (week_pnl / capital_start * 100) if capital_start > 0 else 0

        # تحديد الأسبوع الحالي في الخطة
        plan_start = 1412.25
        week_num = 1
        target = plan_start
        for w in range(1, 14):
            target = target * 1.30
            if capital_now < target:
                week_num = w
                break

        # المستهدف للأسبوع القادم
        next_target = capital_now * 1.30

        # حالة الخطة
        if week_pnl_pct >= 30:
            status_icon = "🟢"
            status_text = "متقدم على الخطة!"
        elif week_pnl_pct >= 20:
            status_icon = "🟡"
            status_text = "قريب من الهدف"
        elif week_pnl_pct >= 0:
            status_icon = "🟠"
            status_text = "متأخر عن الهدف"
        else:
            status_icon = "🔴"
            status_text = "أسبوع خاسر"

        now_str = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>التقرير الأسبوعي — Trade Lak</b>\n"
            f"{'═' * 32}\n"
            f"📅 التاريخ: <b>{now_str}</b>\n"
            f"{'─' * 32}\n"
            f"💰 رأس المال الحالي: <b>${capital_now:,.2f}</b>\n"
            f"📈 ربح/خسارة الأسبوع: <b>{week_pnl:+,.2f}$ ({week_pnl_pct:+.1f}%)</b>\n"
            f"{'─' * 32}\n"
            f"🎯 <b>خطة المضاعفة 30x:</b>\n"
            f"   الأسبوع: <b>{week_num}/13</b>\n"
            f"   الهدف الأسبوعي: <b>+30%</b>\n"
            f"   مستهدف الأسبوع القادم: <b>${next_target:,.2f}</b>\n"
            f"{'─' * 32}\n"
            f"{status_icon} الحالة: <b>{status_text}</b>\n"
            f"{'─' * 32}\n"
            f"📦 حجم الصفقة الحالي: <b>${self.state['current_trade_size']}</b>\n"
            f"🔢 صفقات اليوم: {self.state.get('trade_count_today', 0)} "
            f"(✅{self.state.get('wins_today', 0)} / ❌{self.state.get('losses_today', 0)})\n"
            f"{'═' * 32}\n"
            f"<i>🤖 Trade Lak — تقرير تلقائي كل أحد</i>"
        )
        self._send_telegram(msg)
        logger.info(f"📊 capital_guard: تم إرسال التقرير الأسبوعي")

    def update_capital(self, new_capital: float):
        """تحديث رأس المال يدوياً"""
        self.state["total_capital"] = new_capital
        _save_state(self.state)
