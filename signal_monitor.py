#!/usr/bin/env python3
"""
signal_monitor.py — مراقبة الصفقات المنشورة على قناة Trade Lak Signal
يرسل إشعاراً عند:
  • ضرب وقف الخسارة (SL)
  • تحقق أي هدف (TP1 / TP2 / TP3)
يقرأ الإشارات من: data/signal_channel_active.json
يحفظ الحالة في:  data/signal_monitor_state.json
"""

import os, sys, json, time, logging, requests
import numpy as np
from datetime import datetime

# ── المسارات ──────────────────────────────────────────────
BASE_DIR      = "/root/trade_lak_bot"
SIGNALS_FILE  = os.path.join(BASE_DIR, "data", "signal_channel_active.json")
STATE_FILE    = os.path.join(BASE_DIR, "data", "signal_monitor_state.json")
LOG_FILE      = os.path.join(BASE_DIR, "signal_monitor.log")

# ── إعدادات Telegram ──────────────────────────────────────
# قناة Trade Lak Signal
SIGNAL_CHAT_ID = "-1003834970832"

# قراءة توكن البوت من config.py
sys.path.insert(0, BASE_DIR)
try:
    from config import TELEGRAM_BOT_TOKEN
except Exception:
    # محاولة قراءة من ملف .env أو متغيرات البيئة
    TELEGRAM_BOT_TOKEN = "8835139388:AAH9AVb06Nq8WbNkVsZ5bS1Dqrd10Wdvc84"
    if not TELEGRAM_BOT_TOKEN:
        # قراءة من config.py مباشرة
        try:
            with open(os.path.join(BASE_DIR, "config.py")) as f:
                for line in f:
                    if "TELEGRAM_BOT_TOKEN" in line and "=" in line:
                        TELEGRAM_BOT_TOKEN = line.split("=")[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

# ── إعداد السجلات ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal_monitor")

# ── دوال مساعدة ───────────────────────────────────────────
def now_str():
    return datetime.now().strftime("%Y/%m/%d %H:%M")

def fmt_price(price: float) -> str:
    """تنسيق السعر بشكل واضح — يتعامل مع الأرقام الصغيرة جداً كـ PEPE"""
    if price == 0:
        return "0"
    if price < 0.000001:
        # مثل: 0.000000002377 → 0.000002377
        return f"{price:.10f}".rstrip('0')
    elif price < 0.001:
        # مثل: 0.00000238 → 0.00000238
        return f"{price:.8f}".rstrip('0')
    elif price < 1:
        return f"{price:.6f}".rstrip('0')
    elif price < 10:
        return f"{price:.4f}".rstrip('0')
    elif price < 1000:
        return f"{price:.2f}"
    else:
        return f"{price:,.2f}"

def send_telegram(msg: str) -> bool:
    """إرسال رسالة إلى قناة Trade Lak Signal"""
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN غير متوفر!")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": SIGNAL_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=15)
        if r.status_code == 200:
            return True
        else:
            log.warning(f"Telegram error: {r.status_code} — {r.text[:200]}")
            return False
    except Exception as e:
        log.error(f"خطأ في إرسال Telegram: {e}")
        return False

def get_current_price(symbol: str) -> float:
    """جلب السعر الحالي من OKX"""
    try:
        # تحويل BTC/USDT → BTC-USDT
        inst_id = symbol.replace("/", "-")
        url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            return float(data["data"][0]["last"])
    except Exception as e:
        log.warning(f"خطأ في جلب سعر {symbol}: {e}")
    return 0.0

def load_signals() -> dict:
    """تحميل الإشارات النشطة من الملف"""
    try:
        if os.path.exists(SIGNALS_FILE):
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"خطأ في تحميل الإشارات: {e}")
    return {}

def load_state() -> dict:
    """تحميل حالة المراقبة (الأهداف المحققة، SL المضروبة)"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_state(state: dict):
    """حفظ حالة المراقبة"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"خطأ في حفظ الحالة: {e}")

def send_tp_hit(symbol: str, tp_num: int, tp_price: float,
                current_price: float, entry: float, remaining: list):
    """إرسال إشعار تحقق هدف"""
    coin = symbol.replace("/USDT", "").replace("-USDT", "")
    profit = ((current_price - entry) / entry) * 100
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    labels = {1: "الأول", 2: "الثاني", 3: "الثالث"}
    medal = medals.get(tp_num, "🎯")
    label = labels.get(tp_num, str(tp_num))

    remaining_text = ""
    if remaining:
        remaining_text = "\n📌 <b>الأهداف المتبقية:</b>\n"
        for i, t in enumerate(remaining, tp_num + 1):
            t_pct = ((t - entry) / entry) * 100
            lbl = labels.get(i, str(i))
            remaining_text += f"  {'🥈' if i==2 else '🥉'} الهدف {lbl}: <b>${t:,.6g}</b>  (+{t_pct:.1f}%)\n"

    sl_advice = ""
    if tp_num == 1:
        sl_advice = "\n💡 <b>نصيحة:</b> انقل وقف الخسارة إلى نقطة الدخول لحماية رأس المال"
    elif tp_num == 2:
        sl_advice = "\n💡 <b>نصيحة:</b> ارفع وقف الخسارة فوق نقطة الدخول لتأمين الربح"

    msg = (
        f"{medal} <b>تحقق الهدف {label}!</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 السعر الحالي: <b>${fmt_price(current_price)}</b>\n"
        f"📥 سعر الدخول: <b>${fmt_price(entry)}</b>\n"
        f"✅ الهدف {label}: <b>${fmt_price(tp_price)}</b>\n"
        f"📈 الربح المحقق: <b>+{profit:.2f}%</b>\n"
        f"{remaining_text}"
        f"{sl_advice}\n"
        f"{'─' * 32}\n"
        f"🕐 {now_str()}"
    )
    if send_telegram(msg):
        log.info(f"✅ TP{tp_num} تحقق لـ {symbol} @ ${current_price:,.6g} (+{profit:.2f}%)")
        return True
    return False

def send_sl_hit(symbol: str, sl_price: float, current_price: float, entry: float):
    """إرسال إشعار ضرب وقف الخسارة"""
    coin = symbol.replace("/USDT", "").replace("-USDT", "")
    loss = ((current_price - entry) / entry) * 100

    msg = (
        f"🛑 <b>وقف الخسارة مُفعَّل!</b>\n"
        f"{'─' * 32}\n"
        f"🪙 <b>{coin}/USDT</b>\n"
        f"💰 السعر الحالي: <b>${fmt_price(current_price)}</b>\n"
        f"📥 سعر الدخول: <b>${fmt_price(entry)}</b>\n"
        f"🛑 وقف الخسارة: <b>${fmt_price(sl_price)}</b>\n"
        f"📉 الخسارة: <b>{loss:.2f}%</b>\n"
        f"{'─' * 32}\n"
        f"⚠️ <b>تم إغلاق الإشارة — الصفقة انتهت</b>\n"
        f"🕐 {now_str()}"
    )
    if send_telegram(msg):
        log.info(f"🛑 SL ضُرب لـ {symbol} @ ${current_price:,.6g} ({loss:.2f}%)")
        return True
    return False

# ── إعدادات Stop Hunt Protection ─────────────────────────
# نسبة الهامش الإضافي تحت SL لتجنب صيد الـ wicks
SL_WICK_BUFFER = 0.005   # 0.5% تحت SL المحدد
# نسبة الارتداد المطلوبة لإعادة الدخول بعد ضرب SL
REENTRY_BOUNCE = 0.015   # 1.5% ارتداد فوق SL = إشارة إعادة دخول
# مهلة إعادة الدخول (ساعة واحدة من ضرب SL)
REENTRY_WINDOW = 3600

def calc_atr_for_symbol(symbol: str, period: int = 14) -> float:
    """ATR 4H للعملة من OKX"""
    try:
        inst_id = symbol.replace("/", "-")
        r = requests.get(
            f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=4H&limit={period+5}",
            timeout=8
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            candles = list(reversed(data["data"]))
            trs = []
            for i in range(1, len(candles)):
                h = float(candles[i][2])
                l = float(candles[i][3])
                pc = float(candles[i-1][4])
                trs.append(max(h - l, abs(h - pc), abs(l - pc)))
            if trs:
                return float(np.mean(trs[-period:]))
    except Exception:
        pass
    return 0.0

def calc_support_for_symbol(symbol: str, period: int = 20) -> float:
    """أدنى سعر في آخر period شمعة 4H كدعم حقيقي"""
    try:
        inst_id = symbol.replace("/", "-")
        r = requests.get(
            f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=4H&limit={period}",
            timeout=8
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            return float(min(float(c[3]) for c in data["data"]))
    except Exception:
        pass
    return 0.0

def calc_sl_smart(symbol: str, entry: float, stored_sl: float) -> float:
    """
    SL ذكي: 1.5% تحت الدعم أو ATR كحد أدنى — أيهما أوسع
    """
    support = calc_support_for_symbol(symbol)
    atr     = calc_atr_for_symbol(symbol)
    if support > 0 and atr > 0:
        sl_pct = support * 0.985
        sl_atr = support - atr
        new_sl = min(sl_pct, sl_atr)
        log.info(f"[{symbol}] SL ذكي: support={support:.6g} ATR={atr:.6g} → SL={new_sl:.6g} (مخزن={stored_sl:.6g})")
        return new_sl
    return stored_sl

def send_reentry_alert(symbol: str, sl_price: float, current_price: float, entry: float, tps: list):
    """إرسال تنبيه إعادة الدخول بعد Stop Hunt"""
    bounce_pct = (current_price - sl_price) / sl_price * 100
    tp_text = ""
    for i, tp in enumerate(tps, 1):
        if tp:
            tp_text += f"\n🎯 TP{i}: <b>${fmt_price(tp)}</b>"
    msg = (
        f"🔄 <b>إعادة دخول محتملة — {symbol}</b>\n"
        f"{'─' * 30}\n"
        f"⚡ ارتداد بعد Stop Hunt\n"
        f"💰 السعر الحالي: <b>${fmt_price(current_price)}</b>\n"
        f"📥 سعر الدخول الأصلي: <b>${fmt_price(entry)}</b>\n"
        f"🛑 SL المضروب: <b>${fmt_price(sl_price)}</b>\n"
        f"📈 الارتداد: <b>+{bounce_pct:.2f}%</b>\n"
        f"{'─' * 30}"
        f"{tp_text}\n"
        f"{'─' * 30}\n"
        f"⚠️ السعر ارتد بعد ضرب SL — فرصة إعادة دخول\n"
        f"🕐 {now_str()}"
    )
    if send_telegram(msg):
        log.info(f"🔄 تنبيه إعادة دخول أُرسل: {symbol} @ ${current_price:.6g}")
        return True
    return False

def check_signals():
    """الدورة الرئيسية — فحص جميع الإشارات النشطة"""
    signals = load_signals()
    if not signals:
        log.info("لا توجد إشارات نشطة حالياً")
        return

    state = load_state()
    state_changed = False

    for symbol, sig in signals.items():
        try:
            entry = float(sig.get("entry", 0))
            tp1   = float(sig.get("tp1", 0))
            tp2   = float(sig.get("tp2", 0))
            tp3   = float(sig.get("tp3", 0))
            sl    = float(sig.get("sl", 0))

            if not entry or not sl:
                continue

            # ── SL ثابت من التوصية المُرسلة — لا يُعاد حسابه ديناميكياً ──
            # SL المحدد في التوصية هو المرجع الوحيد — لا يتغيّر بتغيّر السوق

            # جلب السعر الحالي
            current = get_current_price(symbol)
            if not current:
                log.warning(f"لم يُجلب سعر {symbol}")
                continue

            log.info(f"[{symbol}] السعر={current:.6g} | Entry={entry:.6g} | SL={sl:.6g} | TP1={tp1:.6g} | TP2={tp2:.6g} | TP3={tp3:.6g}")

            # تهيئة الحالة لهذه الإشارة
            if symbol not in state:
                state[symbol] = {"tp_hit": [], "sl_hit": False}

            sym_state = state[symbol]

            # ── فحص وقف الخسارة (مع هامش مقاومة الـ wicks) ──
            # SL الفعلي = SL المحدد - 0.5% هامش إضافي لتجنب Stop Hunt
            sl_effective = sl * (1 - SL_WICK_BUFFER)
            if not sym_state.get("sl_hit") and current <= sl_effective:
                if send_sl_hit(symbol, sl, current, entry):
                    sym_state["sl_hit"] = True
                    sym_state["sl_hit_time"] = time.time()
                    sym_state["sl_hit_price"] = current
                    sym_state["reentry_sent"] = False
                    state_changed = True
                continue  # بعد SL لا نفحص الأهداف

            # ── فحص إعادة الدخول بعد Stop Hunt ──
            if sym_state.get("sl_hit") and not sym_state.get("reentry_sent"):
                sl_hit_time  = sym_state.get("sl_hit_time", 0)
                sl_hit_price = sym_state.get("sl_hit_price", sl)
                time_since   = time.time() - sl_hit_time
                # خلال ساعة من ضرب SL، إذا ارتد السعر 1.5% فوق SL
                if time_since <= REENTRY_WINDOW:
                    bounce_threshold = sl_hit_price * (1 + REENTRY_BOUNCE)
                    if current >= bounce_threshold:
                        tps = [tp1, tp2, tp3]
                        if send_reentry_alert(symbol, sl, current, entry, tps):
                            sym_state["reentry_sent"] = True
                            state_changed = True
                continue  # بعد SL لا نفحص الأهداف العادية

            # ── فحص الأهداف ──
            tp_hit = set(sym_state.get("tp_hit", []))

            # TP1
            if tp1 and 1 not in tp_hit and current >= tp1:
                remaining = []
                if tp2 and current < tp2: remaining.append(tp2)
                if tp3 and current < tp3: remaining.append(tp3)
                if send_tp_hit(symbol, 1, tp1, current, entry, remaining):
                    tp_hit.add(1)
                    state_changed = True

            # TP2
            if tp2 and 2 not in tp_hit and current >= tp2:
                remaining = [tp3] if (tp3 and current < tp3) else []
                if send_tp_hit(symbol, 2, tp2, current, entry, remaining):
                    tp_hit.add(2)
                    state_changed = True

            # TP3
            if tp3 and 3 not in tp_hit and current >= tp3:
                if send_tp_hit(symbol, 3, tp3, current, entry, []):
                    tp_hit.add(3)
                    state_changed = True

            sym_state["tp_hit"] = list(tp_hit)

        except Exception as e:
            log.error(f"خطأ في فحص {symbol}: {e}")

    if state_changed:
        save_state(state)

# ── الحلقة الرئيسية ───────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("🚀 signal_monitor بدأ التشغيل")
    log.info(f"📁 ملف الإشارات: {SIGNALS_FILE}")
    log.info(f"📢 قناة Signal: {SIGNAL_CHAT_ID}")
    log.info("=" * 50)

    INTERVAL = 300  # فحص كل 5 دقائق

    while True:
        try:
            check_signals()
        except Exception as e:
            log.error(f"خطأ في الحلقة الرئيسية: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
