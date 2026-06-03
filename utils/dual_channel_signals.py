"""
dual_channel_signals.py — نظام إشعارات Trade Lak الكامل
=========================================================

القناة 1: Trade Lak Liquidity  (-1003942444248)
  → تنبيه أول عند رصد سيولة عالية (OI + Funding + CVD + Volume)

القناة 2: Trade Lak Signal     (-1003834970832)
  → إشارة دخول كاملة (سعر دخول + TP1/TP2/TP3 + SL)
  → إشعار تحقق هدف (TP1 أو TP2 أو TP3)
  → تنبيه انخفاض سيولة لعملة صدرت بها إشارة سابقاً
"""

import requests
import logging
import time
import os
import json
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# إعدادات القناتين
# ─────────────────────────────────────────────
BOT_TOKEN         = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
LIQUIDITY_CHAT_ID = "-1003942444248"   # Trade Lak Liquidity
SIGNAL_CHAT_ID    = "-1003834970832"   # Trade Lak Signal
TRADE_CHAT_ID     = "-1003907481197"   # Trade Lak Trade
API_URL           = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# ملف حفظ الإشارات النشطة على القرص
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_PERSIST_FILE   = os.path.join(_BASE_DIR, "data", "signal_channel_active.json")
LIQUIDITY_PERSIST_FILE = os.path.join(_BASE_DIR, "data", "liquidity_cooldown.json")
LIQWARN_PERSIST_FILE   = os.path.join(_BASE_DIR, "data", "liqwarn_cooldown.json")

# Cooldown لتجنب التكرار
SIGNAL_COOLDOWN_HOURS   = 4    # لا تُرسل نفس إشارة الدخول مرتين خلال 4 ساعات
LIQUIDITY_COOLDOWN_HOURS = 4   # نفس الشيء لإشارات السيولة
# cooldown مخصص لكل مستوى (ساعات) — كلما ارتفع المستوى قل الـ cooldown
LIQUIDITY_COOLDOWN_BY_LEVEL = {1: 8, 2: 6, 3: 4, 4: 2, 5: 1}
LIQWARN_COOLDOWN_MINS   = 720  # 12 ساعة   # لا تُرسل تنبيه انخفاض سيولة أكثر من مرة/ساعة لنفس العملة

# ─────────────────────────────────────────────
# نظام المستويات الخمسة للسيولة
# ─────────────────────────────────────────────
# المستوى 1 (🔵): سيولة تبدأ بالتراكم — OI +2% أو حجم +20%
# المستوى 2 (🟢): سيولة جيدة — OI +5% + حجم +40%
# المستوى 3 (🟡): سيولة قوية — OI +8% + حجم +70% + CVD إيجابي
# المستوى 4 (🟠): سيولة عالية جداً — OI +12% + حجم +100% + Funding سلبي
# المستوى 5 (🔴): سيولة انفجارية — OI +18% + حجم +150% + تصفيات ضخمة
LIQ_LEVELS = [
    # (level, icon, label, min_score, oi_threshold, vol_threshold, description)
    (1, "🔵", "تنبيه أول",    1, 2.0,  20.0, "سيولة تبدأ بالتراكم"),
    (2, "🟢", "تنبيه ثاني",   2, 5.0,  40.0, "سيولة جيدة"),
    (3, "🟡", "تنبيه ثالث",   3, 8.0,  70.0, "سيولة قوية"),
    (4, "🟠", "تنبيه رابع",   4, 12.0, 100.0, "سيولة عالية جداً"),
    (5, "🔴", "تنبيه خامس",   5, 18.0, 150.0, "سيولة انفجارية"),
]

# مستويات انخفاض السيولة (5 مستويات أيضاً)
LIQ_DROP_LEVELS = [
    # (level, icon, label, min_signals, advice)
    (1, "🔵", "تراجع طفيف",    1, "💡 راقب الوضع — لا تدخل جديد"),
    (2, "🟢", "تراجع ملحوظ",   2, "💡 فكر في تأمين جزء من الأرباح"),
    (3, "🟡", "تراجع متوسط",   3, "⚠️ حرك SL إلى Break Even إذا لم تفعل"),
    (4, "🟠", "تراجع حاد",     4, "🚨 أغلق 50% من الصفقة وأمّن الأرباح"),
    (5, "🔴", "انهيار سيولة",  5, "🚨🚨 أغلق الصفقة كاملة — خطر انعكاس حاد"),
]

# ─────────────────────────────────────────────
# ذاكرة الإشارات الصادرة (في الذاكرة — تُعاد عند إعادة التشغيل)
# ─────────────────────────────────────────────
_liquidity_sent:  Dict[str, float] = {}   # symbol → timestamp
_signal_sent:     Dict[str, float] = {}   # symbol → timestamp
_liqwarn_sent:    Dict[str, float] = {}   # symbol → timestamp
_active_signals:  Dict[str, dict]  = {}   # symbol → signal_data (للمراقبة اللاحقة)
_tp_hit:          Dict[str, set]   = {}   # symbol → {1, 2, 3} الأهداف التي تحققت
_liq_snapshot:    Dict[str, dict]  = {}   # symbol → {oi, volume, ts} آخر قراءة سيولة



def _save_active_signals() -> None:
    """حفظ الإشارات النشطة على القرص"""
    try:
        os.makedirs(os.path.dirname(SIGNALS_PERSIST_FILE), exist_ok=True)
        serializable = {}
        for sym, data in _active_signals.items():
            entry = dict(data)
            if "tp_hit" in entry and isinstance(entry["tp_hit"], set):
                entry["tp_hit"] = list(entry["tp_hit"])
            serializable[sym] = entry
        with open(SIGNALS_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[Signal] فشل حفظ الإشارات: {e}")

def _load_active_signals() -> None:
    """تحميل الإشارات النشطة من القرص عند بدء التشغيل"""
    global _active_signals, _tp_hit
    try:
        if not os.path.exists(SIGNALS_PERSIST_FILE):
            return
        with open(SIGNALS_PERSIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        loaded = 0
        for sym, entry in data.items():
            tp_hit_list = entry.pop("tp_hit", [])
            _active_signals[sym] = entry
            _tp_hit[sym] = set(tp_hit_list)
            loaded += 1
        if loaded:
            logger.info(f"[Signal] تم تحميل {loaded} إشارة نشطة: {list(_active_signals.keys())}")
    except Exception as e:
        logger.warning(f"[Signal] فشل تحميل الإشارات: {e}")

_load_active_signals()

def _save_liquidity_cooldown() -> None:
    """حفظ cooldown السيولة على القرص لمنع التكرار بعد إعادة التشغيل"""
    try:
        os.makedirs(os.path.dirname(LIQUIDITY_PERSIST_FILE), exist_ok=True)
        with open(LIQUIDITY_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(_liquidity_sent, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[Liquidity] فشل حفظ cooldown: {e}")

def _load_liquidity_cooldown() -> None:
    """تحميل cooldown السيولة من القرص عند بدء التشغيل"""
    global _liquidity_sent
    try:
        if not os.path.exists(LIQUIDITY_PERSIST_FILE):
            return
        with open(LIQUIDITY_PERSIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = time.time()
        _liquidity_sent.update({k: v for k, v in data.items() if (now - v) < 86400})
        if _liquidity_sent:
            logger.info(f"[Liquidity] تم تحميل cooldown لـ {len(_liquidity_sent)} عملة")
    except Exception as e:
        logger.warning(f"[Liquidity] فشل تحميل cooldown: {e}")

_load_liquidity_cooldown()


def _save_liqwarn_cooldown() -> None:
    try:
        os.makedirs(os.path.dirname(LIQWARN_PERSIST_FILE), exist_ok=True)
        with open(LIQWARN_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(_liqwarn_sent, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[LiqWarn] failed save: {e}")

def _load_liqwarn_cooldown() -> None:
    global _liqwarn_sent
    try:
        if not os.path.exists(LIQWARN_PERSIST_FILE):
            return
        with open(LIQWARN_PERSIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = time.time()
        _liqwarn_sent.update({k: v for k, v in data.items() if (now - v) < 86400})
        if _liqwarn_sent:
            logger.info(f"[LiqWarn] loaded {len(_liqwarn_sent)} entries")
    except Exception as e:
        logger.warning(f"[LiqWarn] failed load: {e}")

_load_liqwarn_cooldown()

def _send(chat_id: str, text: str) -> bool:
    """إرسال رسالة HTML لقناة محددة"""
    try:
        resp = requests.post(API_URL, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning(f"Telegram {resp.status_code}: {resp.text[:150]}")
        return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def _cooldown_ok(cache: dict, symbol: str, hours: float) -> bool:
    last = cache.get(symbol, 0)
    return (time.time() - last) > (hours * 3600)


def _now_str() -> str:
    return datetime.now().strftime('%H:%M   %Y-%m-%d')


# ═══════════════════════════════════════════════════════
# دالة مساعدة: حساب مستوى السيولة (1-5)
# ═══════════════════════════════════════════════════════
def _calc_liquidity_level(
    oi_change_pct: float,
    volume_change_pct: float,
    funding_rate: float,
    cvd_trend: str,
    liquidity_above: bool
) -> tuple:
    """
    يحسب مستوى السيولة من 1 إلى 5 بناءً على النسب المئوية
    يُعيد: (level, icon, label, description, score)
    """
    score = 0

    # OI
    if oi_change_pct >= 18:  score += 5
    elif oi_change_pct >= 12: score += 4
    elif oi_change_pct >= 8:  score += 3
    elif oi_change_pct >= 5:  score += 2
    elif oi_change_pct >= 2:  score += 1

    # Volume
    if volume_change_pct >= 150:  score += 5
    elif volume_change_pct >= 100: score += 4
    elif volume_change_pct >= 70:  score += 3
    elif volume_change_pct >= 40:  score += 2
    elif volume_change_pct >= 20:  score += 1

    # Funding (سلبي = إيجابي للشراء)
    if funding_rate < -0.03:  score += 2
    elif funding_rate < 0:    score += 1
    elif funding_rate > 0.03: score -= 1  # ضغط سلبي

    # CVD
    if cvd_trend == "إيجابي": score += 1

    # سيولة فوق السعر
    if liquidity_above: score += 2

    # تحديد المستوى
    level_idx = min(max(score - 1, 0), 4)  # 0-4
    # نعيد المستوى المناسب بناءً على الـ score
    if score >= 9:   lv = LIQ_LEVELS[4]  # 5
    elif score >= 7: lv = LIQ_LEVELS[3]  # 4
    elif score >= 5: lv = LIQ_LEVELS[2]  # 3
    elif score >= 3: lv = LIQ_LEVELS[1]  # 2
    else:            lv = LIQ_LEVELS[0]  # 1

    return lv[0], lv[1], lv[2], lv[6], score


def _calc_drop_level(drop_signals: int) -> tuple:
    """
    يحسب مستوى انخفاض السيولة من 1 إلى 5
    يُعيد: (level, icon, label, advice)
    """
    idx = min(max(drop_signals - 1, 0), 4)
    lv = LIQ_DROP_LEVELS[idx]
    return lv[0], lv[1], lv[2], lv[4]


# ═══════════════════════════════════════════════════════
# القناة 1: Trade Lak Liquidity — تنبيه سيولة (5 مستويات)
# ═══════════════════════════════════════════════════════
def send_liquidity_alert(
    symbol: str,
    sector: str,
    current_price: float,
    price_change_pct: float,
    oi_change_pct: float,
    funding_rate: float,
    volume_change_pct: float,
    cvd_trend: str = "إيجابي",
    liquidity_above: bool = False,
    reasons: list = None
) -> bool:
    """
    إرسال تنبيه سيولة إلى قناة Trade Lak Liquidity
    5 مستويات: كلما زادت النسب ارتفع المستوى
    """
    coin = symbol.replace('/USDT', '')

    # حساب المستوى أولاً لتحديد الـ cooldown المناسب
    level, icon, label, desc, score = _calc_liquidity_level(
        oi_change_pct, volume_change_pct, funding_rate, cvd_trend, liquidity_above
    )
    # cooldown مستقل لكل مستوى — المفتاح: symbol|level
    _cooldown_h = LIQUIDITY_COOLDOWN_BY_LEVEL.get(level, LIQUIDITY_COOLDOWN_HOURS)
    _liq_key = f"{symbol}|{level}"
    if not _cooldown_ok(_liquidity_sent, _liq_key, _cooldown_h):
        return False

    # شريط المستوى المرئي
    filled   = "█" * level
    empty    = "░" * (5 - level)
    bar      = f"{filled}{empty}  {level}/5"

    reasons_text = ""
    if reasons:
        for r in reasons:
            reasons_text += f"  • {r}\n"
    else:
        if oi_change_pct > 0:
            reasons_text += f"  • OI يرتفع: <b>{oi_change_pct:+.2f}%</b>\n"
        if funding_rate < 0:
            reasons_text += f"  • Funding سلبي: <b>{funding_rate:.4f}%</b>\n"
        elif abs(funding_rate) < 0.01:
            reasons_text += f"  • Funding محايد: <b>{funding_rate:.4f}%</b>\n"
        if volume_change_pct > 20:
            reasons_text += f"  • حجم التداول يرتفع: <b>{volume_change_pct:+.1f}%</b>\n"
        if cvd_trend == "إيجابي":
            reasons_text += f"  • CVD إيجابي — ضغط شراء متراكم\n"
        if liquidity_above:
            reasons_text += f"  • سيولة Long مركزة فوق السعر الحالي\n"

    # تحذير خاص للمستوى 4 و5
    extra = ""
    if level >= 4:
        extra = f"\n⚡ <b>سيولة استثنائية — راقب هذه العملة عن كثب</b>"
    if level == 5:
        extra = f"\n🔥 <b>سيولة انفجارية — فرصة نادرة!</b>"

    msg = (
        f"{icon} <b>{label} — {desc}</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>  [{sector}]\n"
        f"💰 السعر: <b>${current_price:,.6g}</b>  ({price_change_pct:+.2f}%)\n"
        f"{'─' * 32}\n"
        f"📈 OI: <b>{oi_change_pct:+.1f}%</b>   |   📦 الحجم: <b>{volume_change_pct:+.1f}%</b>\n"
        f"{'─' * 32}\n"
        f"📊 <b>مؤشرات السيولة:</b>\n"
        f"{reasons_text}"
        f"{'─' * 32}\n"
        f"📶 مستوى السيولة: <b>{bar}</b>\n"
        f"🔢 النقاط: <b>{score}</b>{extra}\n"
        f"🕐 {_now_str()}\n\n"
        f"<i>⚠️ تنبيه رصد سيولة — ليس توصية بالشراء أو البيع</i>"
    )

    success = _send(LIQUIDITY_CHAT_ID, msg)
    if success:
        _liquidity_sent[_liq_key] = time.time()
        _save_liquidity_cooldown()  # حفظ على القرص
        # حفظ قراءة السيولة لحساب نسبة الانخفاض لاحقاً
        update_liquidity_snapshot(symbol, oi_change_pct, volume_change_pct)
        logger.info(f"📡 [Liquidity] إشارة سيولة مستوى {level}: {symbol} (نقاط: {score})")
    return success


# ═══════════════════════════════════════════════════════
# القناة 2: Trade Lak Signal — إشارة دخول كاملة
# ═══════════════════════════════════════════════════════
def send_trade_signal(
    symbol: str,
    sector: str,
    current_price: float,
    entry_low: float,
    entry_high: float,
    tp1: float,
    tp2: float,
    tp3: float,
    sl: float,
    confidence: float,
    strategy: str = "Breakout+Retest",
    reasons: list = None,
    oi_change: float = 0.0,
    funding_rate: float = 0.0,
    volume_change: float = 0.0
) -> bool:
    """
    إرسال إشارة صفقة كاملة إلى قناة Trade Lak Signal
    تُرسل عند تحقق جميع شروط الدخول
    """
    if not _cooldown_ok(_signal_sent, symbol, SIGNAL_COOLDOWN_HOURS):
        return False

    coin = symbol.replace('/USDT', '')

    tp1_pct = ((tp1 - current_price) / current_price) * 100
    tp2_pct = ((tp2 - current_price) / current_price) * 100
    tp3_pct = ((tp3 - current_price) / current_price) * 100
    sl_pct  = ((sl  - current_price) / current_price) * 100

    reasons_text = ""
    if reasons:
        for r in reasons[:5]:
            reasons_text += f"  ✅ {r}\n"
    else:
        if oi_change > 2:
            reasons_text += f"  ✅ OI يرتفع {oi_change:+.1f}%\n"
        if volume_change > 30:
            reasons_text += f"  ✅ حجم تداول متصاعد {volume_change:+.1f}%\n"
        reasons_text += f"  ✅ استراتيجية: {strategy}\n"

    msg = (
        f"🟢 <b>إشارة دخول — {coin}/USDT</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>  [{sector}]\n"
        f"💰 السعر الحالي: <b>${current_price:,.6g}</b>\n"
        f"🎯 الاستراتيجية: <b>{strategy}</b>\n"
        f"📊 الثقة: <b>{confidence:.0f}%</b>\n"
        f"{'─' * 32}\n"
        f"📌 <b>نقطة الدخول:</b>\n"
        f"  المنطقة: <b>${entry_low:,.6g} – ${entry_high:,.6g}</b>\n"
        f"{'─' * 32}\n"
        f"🎯 <b>الأهداف:</b>\n"
        f"  🥇 الهدف الأول:  <b>${tp1:,.6g}</b>  (+{tp1_pct:.1f}%)\n"
        f"  🥈 الهدف الثاني: <b>${tp2:,.6g}</b>  (+{tp2_pct:.1f}%)\n"
        f"  🥉 الهدف الثالث: <b>${tp3:,.6g}</b>  (+{tp3_pct:.1f}%)\n"
        f"{'─' * 32}\n"
        f"🛑 <b>وقف الخسارة:</b> <b>${sl:,.6g}</b>  ({sl_pct:.1f}%)\n"
        f"{'─' * 32}\n"
        f"📈 <b>أسباب الدخول:</b>\n"
        f"{reasons_text}"
        f"{'─' * 32}\n"
        f"🕐 {_now_str()}\n\n"
        f"<i>⚠️ للأغراض التعليمية فقط — ليست توصية بالشراء أو البيع</i>"
    )

    success = _send(SIGNAL_CHAT_ID, msg)
    if success:
        _signal_sent[symbol] = time.time()
        # حفظ بيانات الإشارة للمراقبة اللاحقة
        _active_signals[symbol] = {
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
            'sl': sl, 'entry': current_price,
            'sector': sector, 'sent_at': time.time()
        }
        _tp_hit[symbol] = set()
        _save_active_signals()   # disk
        logger.info(f"📡 [Signal] إشارة دخول: {symbol}")
    return success


# ═══════════════════════════════════════════════════════
# القناة 2: Trade Lak Signal — إشعار تحقق هدف
# ═══════════════════════════════════════════════════════
def notify_target_hit(
    symbol: str,
    tp_number: int,          # 1 أو 2 أو 3
    tp_price: float,
    current_price: float,
    entry_price: float,
    remaining_targets: list = None  # أسعار الأهداف المتبقية
) -> bool:
    """
    إرسال إشعار تحقق هدف إلى قناة Trade Lak Signal
    يُستدعى عند وصول السعر لـ TP1 أو TP2 أو TP3
    """
    # تجنب إرسال نفس الهدف مرتين
    if symbol in _tp_hit and tp_number in _tp_hit[symbol]:
        return False

    coin   = symbol.replace('/USDT', '')
    profit = ((current_price - entry_price) / entry_price) * 100

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    medal  = medals.get(tp_number, "🎯")
    labels = {1: "الأول", 2: "الثاني", 3: "الثالث"}
    label  = labels.get(tp_number, str(tp_number))

    # بناء قسم الأهداف المتبقية
    remaining_text = ""
    if remaining_targets:
        remaining_text = "\n📌 <b>الأهداف المتبقية:</b>\n"
        for i, t in enumerate(remaining_targets, tp_number + 1):
            t_pct = ((t - entry_price) / entry_price) * 100
            remaining_text += f"  {'🥈' if i==2 else '🥉'} الهدف {labels.get(i,'')}: <b>${t:,.6g}</b>  (+{t_pct:.1f}%)\n"

    # توصية SL
    sl_advice = ""
    if tp_number == 1:
        sl_advice = "\n💡 <b>نصيحة:</b> انقل وقف الخسارة إلى نقطة الدخول لحماية رأس المال"
    elif tp_number == 2:
        sl_advice = "\n💡 <b>نصيحة:</b> ارفع وقف الخسارة فوق نقطة الدخول لتأمين الربح"

    msg = (
        f"{medal} <b>تحقق الهدف {label}!</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 السعر الحالي: <b>${current_price:,.6g}</b>\n"
        f"📥 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"✅ الهدف {label}: <b>${tp_price:,.6g}</b>\n"
        f"📈 الربح المحقق: <b>+{profit:.2f}%</b>\n"
        f"{remaining_text}"
        f"{sl_advice}\n"
        f"{'─' * 32}\n"
        f"🕐 {_now_str()}\n\n"
        f"<i>⚠️ للأغراض التعليمية فقط — ليست توصية بالشراء أو البيع</i>"
    )

    success = _send(SIGNAL_CHAT_ID, msg)
    if success:
        if symbol not in _tp_hit:
            _tp_hit[symbol] = set()
        _tp_hit[symbol].add(tp_number)
        logger.info(f"🎯 [Signal] تحقق الهدف {tp_number} لـ {symbol} (+{profit:.2f}%)")
    return success


# ═══════════════════════════════════════════════════════
# القناة 2: Trade Lak Signal — تنبيه انخفاض السيولة
# ═══════════════════════════════════════════════════════
def notify_liquidity_drop(
    symbol: str,
    current_price: float,
    entry_price: float,
    oi_change_pct: float,       # تغيير OI (سلبي = انخفاض)
    volume_drop_pct: float,     # انخفاض الحجم (%)
    funding_rate: float,        # Funding الحالي
    cvd_trend: str = "سلبي",   # اتجاه CVD
    drop_severity: str = "متوسط",  # خفيف / متوسط / حاد
    reasons: list = None
) -> bool:
    """
    إرسال تنبيه انخفاض سيولة لعملة صدرت بها إشارة سابقاً
    يُرسل إلى قناة Trade Lak Signal
    """
    # تحقق أن هناك إشارة نشطة لهذه العملة
    if symbol not in _active_signals:
        return False

    # Cooldown — لا تُرسل أكثر من مرة كل ساعة
    if not _cooldown_ok(_liqwarn_sent, symbol, LIQWARN_COOLDOWN_MINS / 60):
        return False

    coin    = symbol.replace('/USDT', '')
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    pnl_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"

    # حساب مستوى الانخفاض (1-5) بناءً على عدد الإشارات
    drop_signals_count = 0
    if oi_change_pct < -3:    drop_signals_count += 1
    if volume_drop_pct > 20:  drop_signals_count += 1
    if funding_rate > 0.03:   drop_signals_count += 1
    if cvd_trend == "سلبي":   drop_signals_count += 1
    if oi_change_pct < -10:   drop_signals_count += 1  # انخفاض حاد جداً = +1 إضافي

    drop_level, icon, level_label, advice = _calc_drop_level(drop_signals_count)

    # شريط المستوى المرئي
    filled = "█" * drop_level
    empty  = "░" * (5 - drop_level)
    bar    = f"{filled}{empty}  {drop_level}/5"

    # جلب نسبة الانخفاض الحقيقية من السجل المحفوظ
    drop_data = get_liquidity_drop_pct(symbol, abs(oi_change_pct), abs(volume_drop_pct))
    real_oi_drop  = drop_data['oi_drop_pct']
    real_vol_drop = drop_data['vol_drop_pct']
    drop_pct_str  = ""
    if drop_data['has_snapshot']:
        drop_pct_str = f"\n📉 نسبة الانخفاض: OI <b>-{real_oi_drop:.1f}%</b>  |  حجم <b>-{real_vol_drop:.1f}%</b>"

    reasons_text = ""
    if reasons:
        for r in reasons:
            reasons_text += f"  ⚠️ {r}\n"
    else:
        if oi_change_pct < -3:
            reasons_text += f"  ⚠️ OI ينخفض: <b>{oi_change_pct:.2f}%</b>"
            if real_oi_drop > 0:
                reasons_text += f" (من الذروة: <b>-{real_oi_drop:.1f}%</b>)"
            reasons_text += "\n"
        if volume_drop_pct > 20:
            reasons_text += f"  ⚠️ حجم التداول انخفض: <b>-{volume_drop_pct:.1f}%</b>"
            if real_vol_drop > 0:
                reasons_text += f" (من الذروة: <b>-{real_vol_drop:.1f}%</b>)"
            reasons_text += "\n"
        if funding_rate > 0.03:
            reasons_text += f"  ⚠️ Funding مرتفع جداً: <b>{funding_rate:.4f}%</b> (خطر)\n"
        if cvd_trend == "سلبي":
            reasons_text += f"  ⚠️ CVD سلبي — ضغط بيع متراكم\n"

    msg = (
        f"{icon} <b>{level_label} — انخفاض سيولة ({coin}/USDT)</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>  (إشارة نشطة)\n"
        f"💰 السعر الحالي: <b>${current_price:,.6g}</b>\n"
        f"📥 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"📊 الوضع الحالي: <b>{pnl_str}</b>\n"
        f"{drop_pct_str}\n"
        f"{'─' * 32}\n"
        f"📉 <b>مؤشرات انخفاض السيولة:</b>\n"
        f"{reasons_text}"
        f"{'─' * 32}\n"
        f"📶 مستوى الانخفاض: <b>{bar}</b>\n"
        f"{advice}\n"
        f"{'─' * 32}\n"
        f"🕐 {_now_str()}\n\n"
        f"<i>⚠️ للأغراض التعليمية فقط — ليست توصية بالشراء أو البيع</i>"
    )

    # أرسل فقط لقناة Signal — لأن هذه العملة صدرت بها توصية سابقاً
    success = _send(SIGNAL_CHAT_ID, msg)
    if success:
        _liqwarn_sent[symbol] = time.time()
        _save_liqwarn_cooldown()
        logger.info(f"⚠️ [Signal] تنبيه انخفاض سيولة مستوى {drop_level}: {symbol}")
    return success


# ═══════════════════════════════════════════════════════
# دالة مراقبة الأهداف — تُستدعى من حلقة المراقبة
# ═══════════════════════════════════════════════════════
def update_liquidity_snapshot(symbol: str, oi: float, volume: float) -> None:
    """
    تحديث سجل السيولة لعملة — يُستدعى عند كل إرسال تنبيه سيولة عالية
    حتى يمكن حساب نسبة الانخفاض لاحقاً
    """
    _liq_snapshot[symbol] = {'oi': oi, 'volume': volume, 'ts': time.time()}


def get_liquidity_drop_pct(symbol: str, current_oi: float, current_volume: float) -> dict:
    """
    يحسب نسبة انخفاض السيولة مقارنةً بآخر قراءة محفوظة
    يُعيد: {'oi_drop_pct': float, 'vol_drop_pct': float, 'has_snapshot': bool}
    """
    snap = _liq_snapshot.get(symbol)
    if not snap or snap['oi'] == 0:
        return {'oi_drop_pct': 0.0, 'vol_drop_pct': 0.0, 'has_snapshot': False}
    oi_drop  = ((snap['oi']     - current_oi)     / snap['oi'])     * 100 if snap['oi']     > 0 else 0.0
    vol_drop = ((snap['volume'] - current_volume) / snap['volume']) * 100 if snap['volume'] > 0 else 0.0
    return {'oi_drop_pct': max(oi_drop, 0), 'vol_drop_pct': max(vol_drop, 0), 'has_snapshot': True}


def check_targets_and_liquidity(
    symbol: str,
    current_price: float,
    oi_change_pct: float = 0.0,
    volume_change_pct: float = 0.0,
    funding_rate: float = 0.0,
    cvd_trend: str = "محايد"
) -> None:
    """
    تُستدعى في كل دورة مراقبة للعملات التي صدرت بها إشارات
    تتحقق من: تحقق الأهداف + انخفاض السيولة
    """
    if symbol not in _active_signals:
        return

    sig = _active_signals[symbol]
    entry = sig['entry']
    tp1, tp2, tp3 = sig['tp1'], sig['tp2'], sig['tp3']

    # ── تحقق الأهداف ──
    if current_price >= tp1:
        remaining = []
        if current_price < tp2:
            remaining.append(tp2)
        if current_price < tp3:
            remaining.append(tp3)
        notify_target_hit(symbol, 1, tp1, current_price, entry, remaining)

    if current_price >= tp2:
        remaining = [tp3] if current_price < tp3 else []
        notify_target_hit(symbol, 2, tp2, current_price, entry, remaining)

    if current_price >= tp3:
        notify_target_hit(symbol, 3, tp3, current_price, entry, [])

    # ── تنبيه انخفاض السيولة ──
    liquidity_drop_signals = 0
    drop_reasons = []

    if oi_change_pct < -3:
        liquidity_drop_signals += 1
        drop_reasons.append(f"OI ينخفض: {oi_change_pct:.2f}%")

    if volume_change_pct < -25:
        liquidity_drop_signals += 1
        drop_reasons.append(f"حجم التداول انخفض: {volume_change_pct:.1f}%")

    if funding_rate > 0.03:
        liquidity_drop_signals += 1
        drop_reasons.append(f"Funding مرتفع جداً: {funding_rate:.4f}%")

    if cvd_trend == "سلبي":
        liquidity_drop_signals += 1
        drop_reasons.append("CVD سلبي — ضغط بيع متراكم")

    # إرسال تنبيه لأي مستوى (حتى 1 إشارة) — المستوى يُحدَّد تلقائياً
    if liquidity_drop_signals >= 1:
        notify_liquidity_drop(
            symbol=symbol,
            current_price=current_price,
            entry_price=entry,
            oi_change_pct=oi_change_pct,
            volume_drop_pct=abs(volume_change_pct),
            funding_rate=funding_rate,
            cvd_trend=cvd_trend,
            drop_severity="auto",   # يُحسب داخل notify_liquidity_drop
            reasons=drop_reasons
        )


# ═══════════════════════════════════════════════════════
# قناة Trade Lak Trade — صفقات البوت الفعلية + جميع التحديثات
# ═══════════════════════════════════════════════════════
def send_trade_opened(
    symbol: str,
    direction: str,          # SPOT_BUY / LONG / SHORT
    entry_price: float,
    tp1: float,
    tp2: float,
    tp3: float,
    sl: float,
    confidence: float,
    strategy: str = "Smart Entry",
    reasons: list = None
) -> bool:
    """
    إرسال إشعار دخول صفقة جديدة إلى قناة Trade Lak Trade
    بدون ذكر المبلغ
    """
    coin = symbol.replace('/USDT', '')

    dir_icons = {'SPOT_BUY': '🟢 شراء', 'LONG': '🟢 Long', 'SHORT': '🔴 Short'}
    dir_label = dir_icons.get(direction, direction)

    tp1_pct = ((tp1 - entry_price) / entry_price) * 100
    tp2_pct = ((tp2 - entry_price) / entry_price) * 100
    tp3_pct = ((tp3 - entry_price) / entry_price) * 100
    sl_pct  = ((sl  - entry_price) / entry_price) * 100

    reasons_text = ""
    if reasons:
        for r in reasons[:4]:
            reasons_text += f"  ✔️ {r}\n"

    _sep = '─' * 30
    msg = (
        f"🟢 <b>دخول صفقة جديدة</b>\n"
        f"{_sep}\n"
        f"🪙 <b>{coin}/USDT</b>  {dir_label}\n"
        f"💰 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"🎯 الاستراتيجية: <b>{strategy}</b>\n"
        f"📊 الثقة: <b>{confidence:.0f}%</b>\n"
        f"{_sep}\n"
        f"🎯 <b>الأهداف:</b>\n"
        f"  🥇 TP1: <b>${tp1:,.6g}</b>  (+{tp1_pct:.1f}%)\n"
        f"  🥈 TP2: <b>${tp2:,.6g}</b>  (+{tp2_pct:.1f}%)\n"
        f"  🥉 TP3: <b>${tp3:,.6g}</b>  (+{tp3_pct:.1f}%)\n"
        f"🛑 <b>SL:</b> <b>${sl:,.6g}</b>  ({sl_pct:.1f}%)\n"
        f"{_sep}\n"
        f"{reasons_text}"
        f"🕐 {_now_str()}"
    )
    success = _send(TRADE_CHAT_ID, msg)
    if success:
        logger.info(f"🟢 [Trade] دخول: {symbol} @ ${entry_price:,.6g}")
    return success


def send_trade_tp_hit(
    symbol: str,
    tp_number: int,
    tp_price: float,
    entry_price: float,
    current_price: float,
    remaining_targets: list = None
) -> bool:
    """
    إشعار تحقق هدف على قناة Trade
    """
    coin   = symbol.replace('/USDT', '')
    profit = ((current_price - entry_price) / entry_price) * 100
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    labels = {1: "الأول", 2: "الثاني", 3: "الثالث"}
    medal  = medals.get(tp_number, "🎯")
    label  = labels.get(tp_number, str(tp_number))

    remaining_text = ""
    if remaining_targets:
        remaining_text = "\n📌 <b>الأهداف المتبقية:</b>\n"
        for i, t in enumerate(remaining_targets, tp_number + 1):
            t_pct = ((t - entry_price) / entry_price) * 100
            remaining_text += f"  {medals.get(i, '🎯')} TP{i}: <b>${t:,.6g}</b>  (+{t_pct:.1f}%)\n"

    sl_advice = ""
    if tp_number == 1:
        sl_advice = "\n🔒 تم تحريك SL إلى نقطة الدخول (Break Even)"
    elif tp_number == 2:
        sl_advice = "\n🔒 تم تحريك SL فوق نقطة الدخول (Profit Lock)"

    _sep = '─' * 30
    msg = (
        f"{medal} <b>تحقق الهدف {label}!</b>\n"
        f"{_sep}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"✅ سعر الهدف {label}: <b>${tp_price:,.6g}</b>\n"
        f"📈 الربح: <b>+{profit:.2f}%</b>\n"
        f"{remaining_text}"
        f"{sl_advice}\n"
        f"{_sep}\n"
        f"🕐 {_now_str()}"
    )
    success = _send(TRADE_CHAT_ID, msg)
    if success:
        logger.info(f"{medal} [Trade] تحقق TP{tp_number}: {symbol} (+{profit:.2f}%)")
    return success


def send_trade_sl_update(
    symbol: str,
    old_sl: float,
    new_sl: float,
    entry_price: float,
    current_price: float,
    reason: str = "تحريك تلقائي"
) -> bool:
    """
    إشعار تعديل SL على قناة Trade
    """
    coin    = symbol.replace('/USDT', '')
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    sl_type = "🔒 Break Even" if abs(new_sl - entry_price) / entry_price < 0.003 else "🔒 تشديد SL"

    _sep = '─' * 30
    msg = (
        f"🔄 <b>تحديث وقف الخسارة</b>\n"
        f"{_sep}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"📊 السعر الحالي: <b>${current_price:,.6g}</b>  ({pnl_pct:+.2f}%)\n"
        f"{_sep}\n"
        f"{sl_type}\n"
        f"  قديم: <b>${old_sl:,.6g}</b>\n"
        f"  جديد: <b>${new_sl:,.6g}</b>\n"
        f"💡 السبب: {reason}\n"
        f"{_sep}\n"
        f"🕐 {_now_str()}"
    )
    success = _send(TRADE_CHAT_ID, msg)
    if success:
        logger.info(f"🔄 [Trade] SL update: {symbol} {old_sl:.6g} → {new_sl:.6g}")
    return success


def send_trade_closed(
    symbol: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    duration_str: str,
    reason: str,
    direction: str = "SPOT_BUY"
) -> bool:
    """
    إشعار إغلاق صفقة على قناة Trade
    بدون ذكر المبلغ
    """
    coin = symbol.replace('/USDT', '')
    is_profit = pnl_pct >= 0
    emoji = "✅" if is_profit else "❌"
    result_label = "ربح" if is_profit else "خسارة"

    # تحديد سبب الإغلاق
    close_reasons = {
        'TP1': '🥇 تحقق الهدف الأول',
        'TP2': '🥈 تحقق الهدف الثاني',
        'TP3': '🥉 تحقق الهدف الثالث',
        'SL':  '🛑 وقف الخسارة',
        'MANUAL': '👋 إغلاق يدوي',
    }
    reason_label = close_reasons.get(reason.upper().split()[0] if reason else '', f"🔄 {reason}")

    _sep = '─' * 30
    _sign = '+' if is_profit else ''
    msg = (
        f"{emoji} <b>إغلاق صفقة — {result_label}</b>\n"
        f"{_sep}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"💰 سعر الخروج: <b>${exit_price:,.6g}</b>\n"
        f"📈 النتيجة: <b>{_sign}{pnl_pct:.2f}%</b>\n"
        f"⏱ المدة: <b>{duration_str}</b>\n"
        f"📌 سبب الإغلاق: {reason_label}\n"
        f"{_sep}\n"
        f"🕐 {_now_str()}"
    )
    success = _send(TRADE_CHAT_ID, msg)
    if success:
        logger.info(f"{emoji} [Trade] إغلاق: {symbol} {pnl_pct:+.2f}% ({reason})")
    return success


def send_trade_liq_warning(
    symbol: str,
    entry_price: float,
    current_price: float,
    pnl_pct: float,
    reasons: list = None,
    severity: str = "متوسط"
) -> bool:
    """
    تنبيه انخفاض سيولة لصفقة مفتوحة على قناة Trade
    """
    coin = symbol.replace('/USDT', '')
    # حساب مستوى الانخفاض من الأسباب
    drop_count = len(reasons) if reasons else 1
    drop_level, icon, level_label, advice = _calc_drop_level(drop_count)

    # شريط المستوى
    filled = "█" * drop_level
    empty  = "░" * (5 - drop_level)
    bar    = f"{filled}{empty}  {drop_level}/5"

    reasons_text = ""
    if reasons:
        for r in reasons:
            reasons_text += f"  ⚠️ {r}\n"

    _sep = '─' * 30
    msg = (
        f"{icon} <b>{level_label} — انخفاض سيولة ({coin}/USDT)</b>\n"
        f"{_sep}\n"
        f"🪙 <b>{coin}/USDT</b>  (صفقة مفتوحة)\n"
        f"💰 سعر الدخول: <b>${entry_price:,.6g}</b>\n"
        f"💰 السعر الحالي: <b>${current_price:,.6g}</b>  ({pnl_pct:+.2f}%)\n"
        f"{_sep}\n"
        f"📉 مؤشرات السيولة:\n"
        f"{reasons_text}"
        f"📶 مستوى الانخفاض: <b>{bar}</b>\n"
        f"{advice}\n"
        f"{_sep}\n"
        f"🕐 {_now_str()}"
    )
    success = _send(TRADE_CHAT_ID, msg)
    if success:
        logger.info(f"{icon} [Trade] تنبيه سيولة مستوى {drop_level}: {symbol}")
    return success


def remove_active_signal(symbol: str) -> None:
    """إزالة الإشارة النشطة عند إغلاق الصفقة"""
    _active_signals.pop(symbol, None)
    _tp_hit.pop(symbol, None)
    _save_active_signals()   # disk_remove
    logger.info(f"🗑️ [Signal] إزالة إشارة نشطة: {symbol}")


def get_active_signals() -> dict:
    """إرجاع قائمة الإشارات النشطة"""
    return dict(_active_signals)

def has_active_signal(symbol: str) -> bool:
    """التحقق إذا كانت هناك إشارة نشطة لهذه العملة على قناة Signal"""
    return symbol in _active_signals

def get_signal_entry(symbol: str) -> float:
    """إرجاع سعر دخول الإشارة النشطة (0 إذا لم توجد)"""
    sig = _active_signals.get(symbol)
    return sig["entry"] if sig else 0.0


# ─────────────────────────────────────────────
# اختبار الاتصال بالقناتين
# ─────────────────────────────────────────────
def test_channels() -> None:
    now = _now_str()

    _sep0 = '─' * 30
    msg1 = (
        f"🔵 <b>Trade Lak Liquidity — متصل ✅</b>\n"
        f"{_sep0}\n"
        f"تنبيهات السيولة العالية ستظهر هنا\n"
        f"🕐 {now}"
    )
    r1 = _send(LIQUIDITY_CHAT_ID, msg1)
    _s1 = '✅ متصل' if r1 else '❌ فشل'
    print(f"Liquidity Channel: {_s1}")

    _sep = '─' * 30
    msg2 = (
        f"🟢 <b>Trade Lak Signal — متصل ✅</b>\n"
        f"{_sep}\n"
        f"ستصلك على هذه القناة:\n"
        f"  🟢 إشارات الدخول مع الأهداف\n"
        f"  🥇 إشعارات تحقق الأهداف\n"
        f"  🟠 تنبيهات انخفاض السيولة\n"
        f"🕐 {now}"
    )
    r2 = _send(SIGNAL_CHAT_ID, msg2)
    _s2 = '✅ متصل' if r2 else '❌ فشل'
    print(f"Signal Channel:    {_s2}")

    msg3 = (
        f"🟢 <b>Trade Lak Trade — متصل ✅</b>\n"
        f"{_sep}\n"
        f"ستصلك على هذه القناة جميع تحديثات صفقات البوت:\n"
        f"  🟢 دخول صفقة (بدون ذكر المبلغ)\n"
        f"  🥇 تحقق أهداف\n"
        f"  🔄 تحديث SL\n"
        f"  ✅ إغلاق صفقة\n"
        f"  🟠 تنبيه انخفاض سيولة\n"
        f"🕐 {now}"
    )
    r3 = _send(TRADE_CHAT_ID, msg3)
    _s3 = '✅ متصل' if r3 else '❌ فشل'
    print(f"Trade Channel:     {_s3}")


if __name__ == "__main__":
    test_channels()
