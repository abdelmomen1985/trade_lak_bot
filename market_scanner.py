#!/usr/bin/env python3
"""
market_scanner.py — مسح شامل لأكثر من 100 عملة على OKX
يبحث عن فرص دخول ويضيف الواعدة منها لقائمة المراقبة تلقائياً
يعمل كل 30 دقيقة
"""

import sys, os, json, time, requests, numpy as np, logging
from datetime import datetime

BASE_DIR = "/root/trade_lak_bot"
sys.path.insert(0, BASE_DIR)
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SIGNAL_CHAT, TELEGRAM_LIQUIDITY_CHAT

# ── ملف قائمة المراقبة الديناميكية ─────────────────────────
DYNAMIC_WATCHLIST_FILE = os.path.join(BASE_DIR, "data", "dynamic_watchlist.json")
SCANNER_STATE_FILE     = os.path.join(BASE_DIR, "data", "scanner_state.json")
LOG_FILE               = os.path.join(BASE_DIR, "logs", "market_scanner.log")

# ── إعداد السجلات ─────────────────────────────────────────
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Scanner] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("market_scanner")

# ── إعدادات المسح ─────────────────────────────────────────
SCAN_INTERVAL     = 1800   # كل 30 دقيقة
MIN_VOL_USDT      = 500_000  # حجم تداول 24H أدنى (USDT)
MIN_SCORE_ENTRY   = 7        # حد إرسال توصية الدخول على قناة Signal
MIN_SCORE_WATCH   = 4        # حد الإضافة لقائمة المراقبة الداخلية (صامتة)
ALERT_COOLDOWN    = 14400    # 4 ساعات بين توصيتين لنفس العملة
VOL_SPIKE_RATIO   = 3.0      # 300% من المتوسط = حجم استثنائي (مؤقت حتى انتهاء التجربة)
VOL_SPIKE_COOLDOWN = 7200   # 2 ساعة بين تنبيهي حجم لنفس العملة
VOL_SPIKE_STATE_FILE = os.path.join(BASE_DIR, "data", "vol_spike_state.json")

# عملات مستثناة (stablecoins + wrapped + meme منخفض السيولة)
EXCLUDED = {
    "USDT","USDC","BUSD","DAI","TUSD","USDP","FRAX","LUSD","USDD","GUSD",
    "WBTC","WETH","STETH","RETH","CBETH","WSTETH",
    "BTC","ETH",  # كبيرة جداً — سيولة مختلفة
}

# ── دوال مساعدة ───────────────────────────────────────────
def send_telegram(msg: str, chat_id: str = None) -> bool:
    target = chat_id or TELEGRAM_CHAT_ID
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": target,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.error(f"خطأ Telegram: {e}")
        return False

def send_signal_entry(op: dict):
    """إرسال توصية دخول على قناة Trade Lak Signal"""
    base    = op["base"]
    price   = op["price"]
    entry   = price
    atr_4h  = op.get("atr_4h", entry * 0.02)
    support = op.get("support", entry * 0.97)

    # ── حساب SL: 1.5% تحت الدعم الحقيقي أو ATR كحد أدنى ──
    sl_pct_based = support * 0.985          # 1.5% تحت الدعم
    sl_atr_based = support - atr_4h         # ATR تحت الدعم
    sl = round(min(sl_pct_based, sl_atr_based), 8)  # الأوسع (الأبعد) هو الأكثر أماناً

    # ── التحقق من نسبة R/R ≥ 1.5:1 ──
    tp1 = round(entry * 1.03, 8)
    tp2 = round(entry * 1.05, 8)
    tp3 = round(entry * 1.08, 8)
    risk   = entry - sl
    reward = tp1 - entry
    rr     = reward / risk if risk > 0 else 0
    if rr < 1.5:
        log.info(f"[{base}] إشارة مُلغاة — R/R={rr:.2f} أقل من 1.5:1 (SL واسع جداً)")
        return False

    sl_pct = (sl - entry) / entry * 100  # سالب

    def fp(v):
        if v < 0.001: return f"{v:.8f}".rstrip('0')
        if v < 1:    return f"{v:.6f}".rstrip('0')
        if v < 1000: return f"{v:.4f}"
        return f"{v:,.2f}"

    reasons_text = "  •  ".join(op["reasons"])
    vol_str = f"{op['vol_usdt']/1_000_000:.1f}M" if op['vol_usdt'] >= 1_000_000 else f"{op['vol_usdt']/1_000:.0f}K"
    stars = '\u2b50' * min(op['score'] // 2, 5)
    rr_display = f"{rr:.1f}:1"

    msg = (
        f"📡 <b>إشارة دخول | {base}/USDT</b>\n"
        f"──────────────────────────────\n"
        f"\n"
        f"💰 <b>السعر الحالي:</b>  {fp(entry)}\n"
        f"\n"
        f"📥 <b>نقطة الدخول:</b>  {fp(entry)}\n"
        f"\n"
        f"🖇 <b>الهدف الأول:</b>   {fp(tp1)} <b>(+3.0%)</b>\n"
        f"🖇 <b>الهدف الثاني:</b>  {fp(tp2)} <b>(+5.0%)</b>\n"
        f"🖇 <b>الهدف الثالث:</b>  {fp(tp3)} <b>(+8.0%)</b>\n"
        f"\n"
        f"🔴 <b>وقف الخسارة:</b>  {fp(sl)} <b>({sl_pct:.1f}%)</b>\n"
        f"⚖️ <b>نسبة المخاطرة:</b>  {rr_display}\n"
        f"\n"
        f"──────────────────────────────\n"
        f"{stars} <b>قوة الإشارة ({op['score']}/10)</b>\n"
        f"\n"
        f"📊 RSI 4H: <b>{op['rsi_4h']:.0f}</b>  |  RSI 1H: <b>{op['rsi_1h']:.0f}</b>  |  حجم: <b>{vol_str}</b>\n"
        f"\n"
        f"──────────────────────────────\n"
        f"⚠️ هذه الإشارة لأهداف تعليمية\n"
        f"وليست نصيحة استثمارية بالبيع أو الشراء\n"
        f"──────────────────────────────\n"
        f"🕐 {datetime.now().strftime('%H:%M  |  %Y/%m/%d')}"
    )
    sent = send_telegram(msg, chat_id=TELEGRAM_SIGNAL_CHAT)
    if sent:
        # ── حفظ الإشارة في signal_channel_active.json لمراقبتها ──
        try:
            sig_file = os.path.join(BASE_DIR, "data", "signal_channel_active.json")
            try:
                with open(sig_file) as f:
                    active = json.load(f)
            except Exception:
                active = {}
            active[f"{base}/USDT"] = {
                "entry":    entry,
                "tp1":      tp1,
                "tp2":      tp2,
                "tp3":      tp3,
                "sl":       sl,
                "sector":   "Scanner",
                "sent_at":  int(time.time()),
            }
            with open(sig_file, "w") as f:
                json.dump(active, f, ensure_ascii=False, indent=2)
            log.info(f"[{base}] ✅ تم حفظ الإشارة في signal_channel_active.json")
        except Exception as e:
            log.error(f"[{base}] خطأ في حفظ الإشارة: {e}")
    return sent

def send_reinforce_advice(op: dict, existing: dict) -> bool:
    """إرسال نصيحة تعزيز أو توسيع SL لإشارة مفتوحة قوية"""
    base   = op["base"]
    price  = op["price"]
    entry  = existing.get("entry", price)
    sl_old = existing.get("sl", price * 0.97)
    tp1    = existing.get("tp1", price * 1.03)
    tp2    = existing.get("tp2", price * 1.05)
    tp3    = existing.get("tp3", price * 1.08)
    pnl    = (price - entry) / entry * 100

    def fp(v):
        if v < 0.001: return f"{v:.8f}".rstrip('0')
        if v < 1:    return f"{v:.6f}".rstrip('0')
        if v < 1000: return f"{v:.4f}"
        return f"{v:,.2f}"

    stars = '\u2b50' * min(op['score'] // 2, 5)
    pnl_icon = "📈" if pnl >= 0 else "📉"
    vol_str = f"{op['vol_usdt']/1_000_000:.1f}M" if op['vol_usdt'] >= 1_000_000 else f"{op['vol_usdt']/1_000:.0f}K"

    # اقتراح توسيع SL الجديد: 1% تحت السعر الحالي
    sl_new = round(price * 0.985, 8)
    sl_new_pct = (sl_new - entry) / entry * 100

    msg = (
        f"💪 <b>نصيحة تعزيز | {base}/USDT</b>\n"
        f"──────────────────────────────\n"
        f"\n"
        f"📌 <b>الإشارة مفتوحة ولا تزال قوية</b>\n"
        f"\n"
        f"💰 <b>سعر الدخول:</b>  {fp(entry)}\n"
        f"{pnl_icon} <b>السعر الحالي:</b>  {fp(price)} <b>({pnl:+.1f}%)</b>\n"
        f"\n"
        f"🖇 <b>الهدف الأول:</b>   {fp(tp1)}\n"
        f"🖇 <b>الهدف الثاني:</b>  {fp(tp2)}\n"
        f"🖇 <b>الهدف الثالث:</b>  {fp(tp3)}\n"
        f"\n"
        f"🔴 <b>وقف الخسارة الحالي:</b>  {fp(sl_old)}\n"
        f"🔰 <b>وقف الخسارة المقترح:</b>  {fp(sl_new)} <b>({sl_new_pct:+.1f}%)</b>\n"
        f"\n"
        f"──────────────────────────────\n"
        f"{stars} <b>قوة الإشارة ({op['score']}/10)</b>\n"
        f"\n"
        f"📊 RSI 4H: <b>{op['rsi_4h']:.0f}</b>  |  RSI 1H: <b>{op['rsi_1h']:.0f}</b>  |  حجم: <b>{vol_str}</b>\n"
        f"\n"
        f"──────────────────────────────\n"
        f"💡 يمكنك تعزيز المركز أو توسيع وقف الخسارة\n"
        f"للحفاظ على الصفقة مع استمرار الزخم\n"
        f"──────────────────────────────\n"
        f"⚠️ هذه الإشارة لأهداف تعليمية\n"
        f"وليست نصيحة استثمارية بالبيع أو الشراء\n"
        f"──────────────────────────────\n"
        f"🕐 {datetime.now().strftime('%H:%M  |  %Y/%m/%d')}"
    )
    return send_telegram(msg, chat_id=TELEGRAM_SIGNAL_CHAT)

def get_all_spot_symbols() -> list:
    """جلب جميع أزواج USDT من OKX Spot"""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
            timeout=15
        )
        data = r.json()
        if data.get("code") == "0":
            symbols = []
            for t in data["data"]:
                inst = t["instId"]
                if not inst.endswith("-USDT"):
                    continue
                base = inst.replace("-USDT", "")
                if base in EXCLUDED:
                    continue
                vol_usdt = float(t.get("volCcy24h", 0))
                if vol_usdt < MIN_VOL_USDT:
                    continue
                symbols.append({
                    "instId": inst,
                    "base": base,
                    "price": float(t["last"]),
                    "change_pct": (float(t["last"]) - float(t["open24h"])) / float(t["open24h"]) * 100 if float(t.get("open24h", 0)) > 0 else 0,
                    "vol_usdt": vol_usdt,
                })
            # ترتيب حسب الحجم تنازلياً
            symbols.sort(key=lambda x: x["vol_usdt"], reverse=True)
            return symbols[:150]  # أعلى 150 عملة حجماً
    except Exception as e:
        log.error(f"خطأ في جلب الرموز: {e}")
    return []

def get_ohlcv_full(inst_id: str, bar: str, limit: int = 50):
    """جلب OHLCV كاملاً (closes, highs, lows)"""
    try:
        r = requests.get(
            f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}",
            timeout=10
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            candles = list(reversed(data["data"]))
            closes = [float(c[4]) for c in candles]
            highs  = [float(c[2]) for c in candles]
            lows   = [float(c[3]) for c in candles]
            return closes, highs, lows
    except Exception:
        pass
    return [], [], []

def get_ohlcv(inst_id: str, bar: str, limit: int = 50) -> list:
    try:
        r = requests.get(
            f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}",
            timeout=10
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            return [float(c[4]) for c in reversed(data["data"])]
    except Exception:
        pass
    return []

def calc_rsi(closes, period=14) -> float:
    if len(closes) < period + 1:
        return 50.0
    closes = np.array(closes, dtype=float)
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g  = np.mean(gains[:period])
    avg_l  = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return 100 - (100 / (1 + avg_g / avg_l))

def calc_bb(closes, period=20):
    if len(closes) < period:
        return None, None, None
    arr = np.array(closes[-period:], dtype=float)
    mid = np.mean(arr)
    std = np.std(arr)
    return mid - 2 * std, mid, mid + 2 * std

def calc_atr(highs, lows, closes, period=14) -> float:
    """Average True Range — يقيس التقلب الفعلي للعملة"""
    if len(closes) < period + 1:
        return closes[-1] * 0.02 if closes else 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)
    atr = np.mean(trs[-period:])
    return float(atr)

def calc_support(lows, period=20) -> float:
    """أدنى نقطة في آخر period شمعة كدعم حقيقي"""
    return float(min(lows[-period:])) if len(lows) >= period else float(min(lows))

def calc_macd_hist(closes, fast=12, slow=26, signal=9) -> float:
    if len(closes) < slow + signal:
        return 0.0
    closes = np.array(closes, dtype=float)
    def ema(data, p):
        k = 2 / (p + 1)
        r = [data[0]]
        for v in data[1:]:
            r.append(v * k + r[-1] * (1 - k))
        return np.array(r)
    macd_line   = ema(closes, fast) - ema(closes, slow)
    signal_line = ema(macd_line, signal)
    return (macd_line - signal_line)[-1]

def score_coin(sym_info: dict) -> dict | None:
    """تحليل عملة وإرجاع النتيجة"""
    inst_id = sym_info["instId"]
    price   = sym_info["price"]
    change  = sym_info["change_pct"]
    closes_4h, highs_4h, lows_4h = get_ohlcv_full(inst_id, "4H", 50)
    closes_1h = get_ohlcv(inst_id, "1H", 50)
    if len(closes_4h) < 25 or len(closes_1h) < 15:
        return None
    rsi_4h     = calc_rsi(closes_4h)
    rsi_1h     = calc_rsi(closes_1h)
    bb_l, bb_m, bb_u = calc_bb(closes_4h)
    macd_hist  = calc_macd_hist(closes_4h)
    atr_4h     = calc_atr(highs_4h, lows_4h, closes_4h)
    support    = calc_support(lows_4h)

    score   = 0
    reasons = []

    # ── شروط الدخول ──────────────────────────────────────
    # RSI 4H منخفض جداً (ذروة بيع)
    if rsi_4h < 25:
        score += 3
        reasons.append(f"RSI 4H={rsi_4h:.1f} ذروة بيع 🔥")
    elif rsi_4h < 32:
        score += 2
        reasons.append(f"RSI 4H={rsi_4h:.1f} منخفض")
    elif rsi_4h < 40:
        score += 1
        reasons.append(f"RSI 4H={rsi_4h:.1f} تراجع")

    # RSI 1H منخفض
    if rsi_1h < 30:
        score += 2
        reasons.append(f"RSI 1H={rsi_1h:.1f} ذروة بيع")
    elif rsi_1h < 40:
        score += 1
        reasons.append(f"RSI 1H={rsi_1h:.1f} منخفض")

    # قريب من BB السفلي أو تحته
    if bb_l and price <= bb_l * 1.02:
        score += 2
        reasons.append(f"عند BB Lower ({bb_l:.5g})")
    elif bb_l and price <= bb_l * 1.05:
        score += 1
        reasons.append(f"قريب من BB Lower")

    # MACD يتحسن
    if macd_hist > 0:
        score += 1
        reasons.append("MACD إيجابي")
    elif macd_hist > -0.0001 * price:
        score += 1
        reasons.append("MACD يتعافى")

    # تراجع طفيف (تجميع)
    if -8 <= change <= -1:
        score += 1
        reasons.append(f"تراجع {change:.1f}% (تجميع)")

    # تراجع كبير (فرصة انتعاش)
    if change < -8:
        score += 1
        reasons.append(f"تراجع حاد {change:.1f}% (فرصة؟)")

    return {
        "base":      sym_info["base"],
        "inst_id":   inst_id,
        "price":     price,
        "change":    change,
        "rsi_4h":    rsi_4h,
        "rsi_1h":    rsi_1h,
        "bb_lower":  bb_l,
        "macd_hist": macd_hist,
        "score":     score,
        "reasons":   reasons,
        "vol_usdt":  sym_info["vol_usdt"],
        "atr_4h":    atr_4h,
        "support":   support,
    }

def load_state() -> dict:
    try:
        if os.path.exists(SCANNER_STATE_FILE):
            with open(SCANNER_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_alerts": {}, "watchlist": {}}

def save_state(state: dict):
    try:
        with open(SCANNER_STATE_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"خطأ في حفظ الحالة: {e}")

def load_dynamic_watchlist() -> dict:
    try:
        if os.path.exists(DYNAMIC_WATCHLIST_FILE):
            with open(DYNAMIC_WATCHLIST_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_dynamic_watchlist(wl: dict):
    try:
        with open(DYNAMIC_WATCHLIST_FILE, "w") as f:
            json.dump(wl, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"خطأ في حفظ قائمة المراقبة: {e}")

def fmt_vol(vol: float) -> str:
    if vol >= 1_000_000:
        return f"{vol/1_000_000:.1f}M"
    return f"{vol/1_000:.0f}K"

def load_vol_spike_state() -> dict:
    if os.path.exists(VOL_SPIKE_STATE_FILE):
        try:
            with open(VOL_SPIKE_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_vol_spike_state(state: dict):
    with open(VOL_SPIKE_STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def check_volume_spike(sym_info: dict) -> dict | None:
    """يفحص إذا كان حجم الشمعة الحالية أكثر من VOL_SPIKE_RATIO x المتوسط"""
    inst_id = sym_info["instId"]
    base    = inst_id.replace("-USDT", "")
    try:
        r = requests.get(
            f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=1H&limit=50",
            timeout=10
        )
        data = r.json()
        if data.get("code") != "0" or not data.get("data"):
            return None
        candles = list(reversed(data["data"]))
        if len(candles) < 25:
            return None
        # الشمعة الأخيرة (الحالية)
        last = candles[-1]
        last_vol = float(last[6]) if len(last) > 6 and last[6] else float(last[5]) * float(last[4])
        # متوسط حجم آخر 24 شمعة (بدون الأخيرة)
        prev_vols = []
        for c in candles[-25:-1]:
            v = float(c[6]) if len(c) > 6 and c[6] else float(c[5]) * float(c[4])
            prev_vols.append(v)
        if not prev_vols:
            return None
        avg_vol = sum(prev_vols) / len(prev_vols)
        if avg_vol < 500:  # تجاهل العملات ذات الحجم الضئيل جداً
            return None
        ratio = last_vol / avg_vol if avg_vol > 0 else 0
        if ratio < VOL_SPIKE_RATIO:
            return None
        open_price  = float(last[1])
        close_price = float(last[4])
        price_change = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
        # ── فقط الحجم الإيجابي (ارتفاع السعر) يدل على انفجار صعودي ──
        if price_change <= 0:
            return None
        return {
            "inst_id":      inst_id,
            "base":         base,
            "price":        close_price,
            "vol_usdt":     last_vol,
            "avg_vol":      avg_vol,
            "ratio":        ratio,
            "price_change": price_change,
        }
    except Exception as e:
        log.debug(f"خطأ في فحص حجم {inst_id}: {e}")
        return None

def send_volume_spike_alert(spike: dict) -> bool:
    """إرسال تنبيه الحجم الاستثنائي على قناة Signal"""
    SEP = "\u2500" * 30
    ratio_pct = spike["ratio"] * 100
    direction = "\U0001f4c8" if spike["price_change"] > 0 else "\U0001f4c9"

    def fp(v):
        if v == 0: return "0"
        if v < 0.001: return f"{v:.8f}".rstrip('0')
        if v < 1:    return f"{v:.6f}".rstrip('0')
        if v < 1000: return f"{v:.4f}"
        return f"{v:,.2f}"

    msg = (
        f"\u26a1 <b>\u062d\u062c\u0645 \u0627\u0633\u062a\u062b\u0646\u0627\u0626\u064a \u2014 {spike['base']}/USDT</b>\n"
        f"{SEP}\n"
        f"\U0001f4b0 \u0627\u0644\u0633\u0639\u0631 \u0627\u0644\u062d\u0627\u0644\u064a: <b>${fp(spike['price'])}</b>\n"
        f"{direction} \u0627\u0644\u062a\u063a\u064a\u0631 \u0641\u064a \u0627\u0644\u0634\u0645\u0639\u0629: <b>{spike['price_change']:+.2f}%</b>\n"
        f"\U0001f4a7 \u062d\u062c\u0645 \u0627\u0644\u0634\u0645\u0639\u0629: <b>${spike['vol_usdt']:,.0f}</b>\n"
        f"\U0001f4ca \u0645\u062a\u0648\u0633\u0637 \u0627\u0644\u062d\u062c\u0645 \u0627\u0644\u0639\u0627\u062f\u064a: <b>${spike['avg_vol']:,.0f}</b>\n"
        f"\U0001f525 \u0646\u0633\u0628\u0629 \u0627\u0644\u062d\u062c\u0645: <b>{ratio_pct:.0f}%</b> \u0645\u0646 \u0627\u0644\u0645\u062a\u0648\u0633\u0637\n"
        f"{SEP}\n"
        f"\u26a0\ufe0f \u0642\u062f \u064a\u0634\u064a\u0631 \u0625\u0644\u0649 \u062e\u0628\u0631 \u0623\u0648 \u062a\u062f\u062e\u0644 \u0645\u0641\u0627\u062c\u0626 \u2014 \u0631\u0627\u0642\u0628 \u0627\u0644\u062d\u0631\u0643\u0629\n"
        f"\U0001f550 {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )
    return send_telegram(msg, chat_id=TELEGRAM_LIQUIDITY_CHAT)

def run_volume_spike_scan(symbols: list):
    """مسح الحجم الاستثنائي — فقط للعملات ذات إشارات نشطة في Signal"""
    # ── جلب العملات ذات الإشارات النشطة فقط ──
    sig_file = os.path.join(BASE_DIR, "data", "signal_channel_active.json")
    try:
        with open(sig_file) as f:
            active_signals = json.load(f)
    except Exception:
        active_signals = {}

    if not active_signals:
        log.info("⚡ لا توجد إشارات نشطة — تخطي فحص الحجم الاستثنائي")
        return

    # استخراج أسماء العملات النشطة
    active_bases = set()
    for key in active_signals.keys():
        base = key.replace("-USDT", "").replace("/USDT", "").upper()
        active_bases.add(base)

    log.info(f"⚡ فحص حجم استثنائي لـ {len(active_bases)} عملة نشطة: {', '.join(active_bases)}")

    # تصفية symbols لتشمل فقط العملات النشطة
    filtered_symbols = [s for s in symbols if s.get("instId", "").replace("-USDT", "").upper() in active_bases]

    if not filtered_symbols:
        log.info("⚡ لا توجد عملات نشطة ضمن قائمة المسح")
        return

    spike_state = load_vol_spike_state()
    now = time.time()
    spikes_found = 0
    for sym in filtered_symbols:
        try:
            spike = check_volume_spike(sym)
            if spike:
                base = spike["base"]
                last_spike_time = spike_state.get(base, 0)
                if (now - last_spike_time) > VOL_SPIKE_COOLDOWN:
                    if send_volume_spike_alert(spike):
                        spike_state[base] = now
                        spikes_found += 1
                        log.info(f"[{base}] حجم استثنائي: {spike['ratio']:.1f}x ({spike['price_change']:+.1f}%)")
            time.sleep(0.1)
        except Exception as e:
            log.debug(f"خطأ في فحص حجم {sym.get('instId','?')}: {e}")
    save_vol_spike_state(spike_state)
    if spikes_found:
        log.info(f"تنبيهات حجم استثنائي أُرسلت: {spikes_found}")

def run_scan():
    log.info("=" * 50)
    log.info(f"🔍 بدء مسح السوق — {datetime.now().strftime('%Y/%m/%d %H:%M')}")

    state    = load_state()
    dyn_wl   = load_dynamic_watchlist()
    now      = time.time()
    last_alerts = state.get("last_alerts", {})

    # 1. جلب جميع العملات
    symbols = get_all_spot_symbols()
    log.info(f"📊 تم جلب {len(symbols)} عملة للمسح")
    # ── مسح الحجم الاستثنائي (Volume Spike) ──────────────────
    log.info("⚡ فحص الحجم الاستثنائي...")
    run_volume_spike_scan(symbols)  # فقط للعملات ذات إشارات مفتوحة في Signal

    opportunities = []
    scanned = 0

    for sym in symbols:
        try:
            result = score_coin(sym)
            if result and result["score"] >= MIN_SCORE_WATCH:
                opportunities.append(result)
            scanned += 1
            # تأخير بسيط لتجنب rate limit
            time.sleep(0.15)
        except Exception as e:
            log.warning(f"خطأ في {sym['instId']}: {e}")

    log.info(f"✅ تم مسح {scanned} عملة — وجدنا {len(opportunities)} فرصة")

    # ترتيب حسب الـ score تنازلياً
    opportunities.sort(key=lambda x: x["score"], reverse=True)

    # 2. معالجة الفرص
    new_in_watchlist = []
    alerts_sent      = 0

    for op in opportunities:
        base  = op["base"]
        score = op["score"]

        # إضافة لقائمة المراقبة الديناميكية
        if base not in dyn_wl:
            dyn_wl[base] = {
                "symbol":    op["inst_id"],
                "score":     score,
                "rsi_4h":    round(op["rsi_4h"], 1),
                "price":     op["price"],
                "added_at":  datetime.now().strftime("%Y/%m/%d %H:%M"),
                "reasons":   op["reasons"],
            }
            new_in_watchlist.append(base)
            log.info(f"➕ أُضيف {base} للمراقبة (score={score})")
        else:
            # تحديث البيانات
            dyn_wl[base]["score"]   = score
            dyn_wl[base]["rsi_4h"]  = round(op["rsi_4h"], 1)
            dyn_wl[base]["price"]   = op["price"]

        # ── إرسال توصية دخول على قناة Signal فقط عند score ≥ 7 ──
        if score >= MIN_SCORE_ENTRY:
            cooldown_ok = (now - last_alerts.get(base, 0)) > ALERT_COOLDOWN
            if cooldown_ok:
                # ── فحص إذا كانت العملة لها إشارة مفتوحة ──
                try:
                    sig_file = os.path.join(BASE_DIR, "data", "signal_channel_active.json")
                    with open(sig_file) as _sf:
                        _active = json.load(_sf)
                except Exception:
                    _active = {}
                sym_key = f"{base}/USDT"
                if sym_key in _active:
                    # العملة لها إشارة مفتوحة — أرسل نصيحة تعزيز فقط إذا كان score ≥ 9
                    if score >= 9:
                        if send_reinforce_advice(op, _active[sym_key]):
                            last_alerts[base] = now
                            alerts_sent += 1
                            log.info(f"💪 نصيحة تعزيز أُرسلت: {base} (score={score})")
                    else:
                        log.info(f"⏭️ تخطي {base} — إشارة مفتوحة بالفعل (score={score})")
                else:
                    # لا توجد إشارة مفتوحة — أرسل إشارة دخول جديدة
                    if send_signal_entry(op):
                        last_alerts[base] = now
                        alerts_sent += 1
                        log.info(f"🟢 توصية دخول أُرسلت: {base} (score={score})")

    # 3. تنظيف العملات القديمة من القائمة الديناميكية (أكثر من 48 ساعة بدون تحديث)
    to_remove = []
    for base, info in dyn_wl.items():
        if base not in [op["base"] for op in opportunities]:
            to_remove.append(base)
    for base in to_remove:
        del dyn_wl[base]
        log.info(f"🗑️ حُذف {base} من المراقبة (لم يعد مؤهلاً)")

    # 4. حفظ
    save_dynamic_watchlist(dyn_wl)
    state["last_alerts"] = last_alerts
    save_state(state)

    # 5. ملخص إذا وُجدت إضافات جديدة
    if new_in_watchlist:
        log.info(f"📋 عملات جديدة في المراقبة: {', '.join(new_in_watchlist)}")

    log.info(f"📤 تنبيهات أُرسلت: {alerts_sent} | قائمة المراقبة: {len(dyn_wl)} عملة")
    log.info("=" * 50)

def main():
    log.info("🚀 market_scanner بدأ التشغيل")
    while True:
        try:
            run_scan()
        except Exception as e:
            log.error(f"خطأ في الحلقة الرئيسية: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
