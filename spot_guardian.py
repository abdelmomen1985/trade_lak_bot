#!/usr/bin/env python3
"""
Spot Guardian v2 — حارس الأصول الفورية مع Trailing Stop
المنطق:
  المرحلة 1 (قبل التعادل):  SL = avg_buy × (1 - 3%)
  المرحلة 2 (عند التعادل):  SL يُرفع إلى avg_buy (لا خسارة)
  المرحلة 3 (بعد التعادل):  SL يتتبع أعلى سعر - 1.5% (Trailing)
  
  التعادل يُعتبر محققاً عندما يتجاوز السعر avg_buy × 1.001 (+0.1%)
"""
import sys, os, time, json, logging
sys.path.insert(0, '/root/trade_lak_bot')
from core.okx_client import OKXClient
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SpotGuardian] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/root/trade_lak_bot/logs/spot_guardian.log', encoding='utf-8'),
    ]
)
log = logging.getLogger('SpotGuardian')

# ─── إعدادات الحماية ──────────────────────────────────────────────────────────
STOP_LOSS_PCT       = 0.03    # 3% وقف خسارة قبل التعادل
WARNING_PCT         = 0.02    # 2% تحذير مبكر
BREAKEVEN_TRIGGER   = 0.001   # +0.1% فوق avg_buy = وصلنا للتعادل
TRAILING_PCT        = 0.015   # 1.5% trailing بعد التعادل
CHECK_INTERVAL      = 60      # فحص كل 60 ثانية
STATE_FILE          = '/root/trade_lak_bot/spot_guardian_state.json'

# الأصول المراقبة
WATCHED_ASSETS = {
    'BTC':  {'avg_buy': 59511.0000, 'min_qty': 1e-05},
    'AVAX': {'avg_buy': 6.1431,     'min_qty': 0.01},
}

# ─── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(msg: str):
    try:
        import yaml, requests
        with open('/root/trade_lak_bot/config_production.yaml') as f:
            cfg = yaml.safe_load(f)
        token   = cfg['telegram']['bot_token']
        chat_id = cfg['telegram'].get('trade_chat_id') or cfg['telegram'].get('chat_id')
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ─── إدارة الحالة ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {}

def save_state(state: dict):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error(f"State save error: {e}")

# ─── حساب وقف الخسارة الديناميكي ─────────────────────────────────────────────
def compute_sl(asset: str, avg_buy: float, current_price: float, state: dict) -> tuple:
    """
    يُعيد (sl_price, phase, peak_price)
    phase: 'initial' | 'breakeven' | 'trailing'
    """
    asset_state = state.get(asset, {})
    peak_price  = asset_state.get('peak_price', avg_buy)
    phase       = asset_state.get('phase', 'initial')

    # تحديث أعلى سعر مُسجَّل
    if current_price > peak_price:
        peak_price = current_price
        asset_state['peak_price'] = peak_price

    breakeven_price = avg_buy * (1 + BREAKEVEN_TRIGGER)

    if phase == 'initial':
        if current_price >= breakeven_price:
            # انتقال إلى مرحلة التعادل
            phase = 'breakeven'
            asset_state['phase'] = phase
            log.info(f"🎯 {asset}: وصلنا التعادل! الانتقال إلى Breakeven Stop")
            send_telegram(
                f"🎯 <b>Spot Guardian — تعادل محقق!</b>\n"
                f"العملة: <b>{asset}</b>\n"
                f"السعر الحالي: ${current_price:,.4f}\n"
                f"متوسط الشراء: ${avg_buy:,.4f}\n"
                f"✅ وقف الخسارة رُفع إلى نقطة الدخول (${avg_buy:,.4f})\n"
                f"📈 سيتتبع الارتفاع بـ Trailing Stop 1.5%"
            )

    if phase in ('breakeven', 'trailing'):
        # الانتقال إلى Trailing بعد ارتفاع +0.5% فوق التعادل
        if current_price >= avg_buy * 1.005 and phase == 'breakeven':
            phase = 'trailing'
            asset_state['phase'] = phase
            log.info(f"📈 {asset}: تفعيل Trailing Stop 1.5%")

        if phase == 'trailing':
            sl_price = peak_price * (1 - TRAILING_PCT)
            # لا يقل SL عن avg_buy أبداً
            sl_price = max(sl_price, avg_buy)
        else:
            # breakeven: SL = avg_buy بالضبط
            sl_price = avg_buy

    else:
        # initial: SL = avg_buy - 3%
        sl_price = avg_buy * (1 - STOP_LOSS_PCT)

    state[asset] = asset_state
    return sl_price, phase, peak_price

# ─── الحلقة الرئيسية ──────────────────────────────────────────────────────────
def run():
    log.info("🚀 Spot Guardian v2 يعمل — Trailing Stop مفعّل")
    log.info(f"   SL قبل التعادل: {STOP_LOSS_PCT*100:.0f}% | Trailing بعده: {TRAILING_PCT*100:.1f}%")

    exchange = OKXClient()
    state    = load_state()


    for asset, config in WATCHED_ASSETS.items():
        if asset not in state:
            state[asset] = {
                'avg_buy':   config['avg_buy'],
                'peak_price': config['avg_buy'],
                'phase':     'initial',
                'warned':    False,
            }
    save_state(state)

    while True:
        try:
            for asset, config in list(WATCHED_ASSETS.items()):
                if config['avg_buy'] is None:
                    continue

                symbol = f"{asset}/USDT"
                try:
                    ticker   = exchange.get_ticker(symbol, market='spot')
                    if not ticker:
                        log.warning(f"{asset}: لم يُعثر على سعر")
                        continue
                    bal = exchange.spot.fetch_balance()
                    free_qty = float(bal['free'].get(asset, 0) or 0)
                except Exception as e:
                    log.error(f"{asset}: فشل جلب البيانات: {e}")
                    continue

                current_price = float(ticker['price'])
                avg_buy       = config['avg_buy']

                # حساب وقف الخسارة الديناميكي
                sl_price, phase, peak_price = compute_sl(asset, avg_buy, current_price, state)
                save_state(state)

                change_pct = (current_price - avg_buy) / avg_buy * 100
                warn_price = avg_buy * (1 - WARNING_PCT)

                # رمز المرحلة
                phase_icon = {'initial': '🔵', 'breakeven': '🟡', 'trailing': '🟢'}.get(phase, '⚪')

                log.info(
                    f"{asset}: ${current_price:.4f} | avg=${avg_buy:.4f} | "
                    f"{change_pct:+.2f}% | SL=${sl_price:.4f} | "
                    f"{phase_icon} {phase} | peak=${peak_price:.4f}"
                )

                # ─── تحذير مبكر (فقط في مرحلة initial) ───────────────────
                if phase == 'initial':
                    if current_price <= warn_price and not state.get(asset, {}).get('warned', False):
                        send_telegram(
                            f"⚠️ <b>تحذير Spot Guardian</b>\n"
                            f"العملة: {asset}\n"
                            f"السعر الحالي: ${current_price:,.4f}\n"
                            f"متوسط الشراء: ${avg_buy:,.4f}\n"
                            f"التغيير: {change_pct:+.2f}%\n"
                            f"⚡ وقف الخسارة عند: ${sl_price:,.4f} (-3%)\n"
                            f"اقتربنا من مستوى الخطر!"
                        )
                        log.warning(f"⚠️ {asset}: تحذير مبكر عند ${current_price:.4f}")
                        state[asset]['warned'] = True
                        save_state(state)
                    elif current_price > warn_price and state.get(asset, {}).get('warned', False):
                        state[asset]['warned'] = False
                        save_state(state)

                # ─── تفعيل وقف الخسارة ────────────────────────────────────
                if current_price <= sl_price:
                    log.warning(
                        f"🚨 {asset}: تفعيل وقف الخسارة! "
                        f"السعر=${current_price:.4f} <= SL=${sl_price:.4f} [{phase}]"
                    )
                    if free_qty >= config['min_qty']:
                        try:
                            order      = exchange.spot_sell(symbol, free_qty, full_exit=True)
                            sold_value = free_qty * current_price
                            pnl        = (current_price - avg_buy) * free_qty
                            pnl_icon   = "✅ ربح" if pnl >= 0 else "🔴 خسارة"

                            msg = (
                                f"{'🟢' if pnl >= 0 else '🔴'} <b>Spot Guardian — تفعيل وقف الخسارة</b>\n"
                                f"العملة: <b>{asset}</b>\n"
                                f"المرحلة: {phase_icon} {phase}\n"
                                f"تم البيع: {free_qty:.6f} {asset}\n"
                                f"سعر البيع: ${current_price:,.4f}\n"
                                f"متوسط الشراء: ${avg_buy:,.4f}\n"
                                f"أعلى سعر مُسجَّل: ${peak_price:,.4f}\n"
                                f"{pnl_icon}: ${pnl:+,.2f} ({change_pct:+.2f}%)\n"
                                f"القيمة المستردة: ${sold_value:,.2f}\n"
                                f"رقم الأمر: {str(order.get('id','?'))[:16]}..."
                            )
                            send_telegram(msg)
                            log.info(f"✅ {asset}: تم البيع | ${sold_value:.2f} | P&L: ${pnl:+.2f}")

                            WATCHED_ASSETS[asset]['avg_buy'] = None
                            if asset in state:
                                del state[asset]
                            save_state(state)
                        except Exception as e:
                            log.error(f"❌ {asset}: فشل البيع: {e}")
                            send_telegram(
                                f"❌ <b>Spot Guardian — فشل البيع!</b>\n"
                                f"العملة: {asset}\nالخطأ: {e}"
                            )
                    else:
                        log.warning(f"⚠️ {asset}: الكمية الحرة ({free_qty:.6f}) أقل من الحد الأدنى")

        except Exception as e:
            log.error(f"خطأ في الحلقة الرئيسية: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    os.makedirs('/root/trade_lak_bot/logs', exist_ok=True)
    run()
