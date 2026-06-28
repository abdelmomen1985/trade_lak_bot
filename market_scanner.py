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
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

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
MIN_SCORE_ALERT   = 5        # حد الإشعار الفوري
MIN_SCORE_WATCH   = 4        # حد الإضافة لقائمة المراقبة
ALERT_COOLDOWN    = 7200     # ساعتان بين تنبيهين لنفس العملة

# عملات مستثناة (stablecoins + wrapped + meme منخفض السيولة)
EXCLUDED = {
    "USDT","USDC","BUSD","DAI","TUSD","USDP","FRAX","LUSD","USDD","GUSD",
    "WBTC","WETH","STETH","RETH","CBETH","WSTETH",
    "BTC","ETH",  # كبيرة جداً — سيولة مختلفة
}

# ── دوال مساعدة ───────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.error(f"خطأ Telegram: {e}")
        return False

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

def get_ohlcv(inst_id: str, bar: str = "4H", limit: int = 50) -> list:
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

    closes_4h = get_ohlcv(inst_id, "4H", 50)
    closes_1h = get_ohlcv(inst_id, "1H", 50)

    if len(closes_4h) < 25 or len(closes_1h) < 15:
        return None

    rsi_4h     = calc_rsi(closes_4h)
    rsi_1h     = calc_rsi(closes_1h)
    bb_l, bb_m, bb_u = calc_bb(closes_4h)
    macd_hist  = calc_macd_hist(closes_4h)

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

        # إرسال تنبيه للفرص القوية فقط
        if score >= MIN_SCORE_ALERT:
            cooldown_ok = (now - last_alerts.get(base, 0)) > ALERT_COOLDOWN
            if cooldown_ok:
                emoji = "🔥" if score >= 7 else ("🟢" if score >= 6 else "🟡")
                reasons_text = "\n".join(f"  • {r}" for r in op["reasons"])
                vol_str = fmt_vol(op["vol_usdt"])
                msg = (
                    f"{emoji} <b>فرصة دخول — {base}/USDT</b>\n"
                    f"{'─' * 30}\n"
                    f"💰 السعر: <b>${op['price']:,.6g}</b> ({op['change']:+.1f}%)\n"
                    f"📊 Score: <b>{score}/10</b>\n"
                    f"📈 RSI 4H: <b>{op['rsi_4h']:.1f}</b>  |  RSI 1H: <b>{op['rsi_1h']:.1f}</b>\n"
                    f"💧 حجم 24H: <b>{vol_str} USDT</b>\n"
                    f"{'─' * 30}\n"
                    f"{reasons_text}\n"
                    f"{'─' * 30}\n"
                    f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}"
                )
                if send_telegram(msg):
                    last_alerts[base] = now
                    alerts_sent += 1
                    log.info(f"📢 تنبيه أُرسل: {base} (score={score})")

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
