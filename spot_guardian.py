#!/usr/bin/env python3
"""
Spot Guardian — حارس الأصول الفورية
يراقب ETH وLINK وأي أصل Spot غير محمي بـ Grid
يبيع تلقائياً بسعر السوق عند انخفاض 5% من سعر الشراء
يرسل إشعار Telegram عند كل عملية بيع أو تحذير
"""
import sys, os, time, json, logging
sys.path.insert(0, '/root/trade_lak_bot')

from core.okx_client import OKXClient
from datetime import datetime

# إعداد اللوق
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SpotGuardian] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/root/trade_lak_bot/logs/spot_guardian.log', encoding='utf-8'),
    ]
)
log = logging.getLogger('SpotGuardian')

# ---- إعدادات الحماية ----
STOP_LOSS_PCT   = 0.03   # 3% وقف خسارة (تم تشديده من 5%)
WARNING_PCT     = 0.02   # 2% تحذير مبكر (تم تشديده)
CHECK_INTERVAL  = 60     # فحص كل 60 ثانية
STATE_FILE      = '/root/trade_lak_bot/spot_guardian_state.json'

# الأصول المراقبة مع متوسط سعر الشراء
# ETH: اشتُري بمتوسط $1,713
WATCHED_ASSETS = {
    'ETH': {'avg_buy': 1575.1900, 'min_qty': 0.001},
    'BTC': {'avg_buy': 59511.0000, 'min_qty': 1e-05},
    'BNB': {'avg_buy': 553.6000, 'min_qty': 0.001},
},
    'LINK': {'avg_buy': None, 'min_qty': 0.1},   # سيُحسب من السعر الحالي عند أول فحص
}

# ---- Telegram ----
def send_telegram(msg: str):
    try:
        import yaml, requests
        with open('/root/trade_lak_bot/config_production.yaml') as f:
            cfg = yaml.safe_load(f)
        token = cfg['telegram']['bot_token']
        chat_id = cfg['telegram'].get('trade_chat_id') or cfg['telegram'].get('chat_id')
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ---- تحميل/حفظ الحالة ----
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ---- الحلقة الرئيسية ----
def run():
    log.info("🛡️ Spot Guardian بدأ العمل")
    send_telegram("🛡️ <b>Spot Guardian</b> بدأ مراقبة الأصول\nيراقب: ETH, LINK\nوقف الخسارة: -5% من سعر الشراء")

    client = OKXClient()
    exchange = client.exchange
    state = load_state()

    while True:
        try:
            bal = exchange.fetch_balance()

            for asset, config in WATCHED_ASSETS.items():
                symbol = f'{asset}/USDT'
                info = bal.get(asset, {})
                total_qty = info.get('total', 0)
                free_qty = info.get('free', 0)
                used_qty = info.get('used', 0)

                # تجاهل إذا الكمية صغيرة جداً
                if total_qty < config['min_qty']:
                    continue

                # تجاهل إذا كل الكمية مقيّدة في Grid (محمية)
                if free_qty < config['min_qty'] and used_qty > 0:
                    continue

                # جلب السعر الحالي
                ticker = exchange.fetch_ticker(symbol)
                current_price = float(ticker['last'])

                # تحديد سعر الشراء
                avg_buy = config['avg_buy']
                if avg_buy is None:
                    # إذا لم يُحدَّد، استخدم السعر الحالي كمرجع
                    if asset not in state:
                        state[asset] = {'avg_buy': current_price, 'warned': False}
                        save_state(state)
                        log.info(f"{asset}: تم تسجيل سعر مرجعي ${current_price:.4f}")
                    avg_buy = state[asset]['avg_buy']
                else:
                    if asset not in state:
                        state[asset] = {'avg_buy': avg_buy, 'warned': False}
                        save_state(state)

                sl_price = avg_buy * (1 - STOP_LOSS_PCT)
                warn_price = avg_buy * (1 - WARNING_PCT)
                change_pct = (current_price - avg_buy) / avg_buy * 100

                log.info(
                    f"{asset}: السعر=${current_price:.4f} | متوسط الشراء=${avg_buy:.4f} | "
                    f"التغيير={change_pct:+.2f}% | SL=${sl_price:.4f}"
                )

                # ---- تحذير مبكر ----
                if current_price <= warn_price and not state.get(asset, {}).get('warned', False):
                    msg = (
                        f"⚠️ <b>تحذير Spot Guardian</b>\n"
                        f"العملة: {asset}\n"
                        f"السعر الحالي: ${current_price:,.4f}\n"
                        f"متوسط الشراء: ${avg_buy:,.4f}\n"
                        f"التغيير: {change_pct:+.2f}%\n"
                        f"⚡ وقف الخسارة عند: ${sl_price:,.4f} (-5%)\n"
                        f"اقتربنا من مستوى الخطر!"
                    )
                    send_telegram(msg)
                    log.warning(f"⚠️ {asset}: تحذير مبكر عند ${current_price:.4f}")
                    if asset not in state:
                        state[asset] = {}
                    state[asset]['warned'] = True
                    save_state(state)

                # إعادة ضبط التحذير إذا ارتفع السعر
                elif current_price > warn_price and state.get(asset, {}).get('warned', False):
                    state[asset]['warned'] = False
                    save_state(state)

                # ---- تفعيل وقف الخسارة ----
                if current_price <= sl_price:
                    log.warning(f"🚨 {asset}: تفعيل وقف الخسارة! السعر=${current_price:.4f} <= SL=${sl_price:.4f}")

                    if free_qty >= config['min_qty']:
                        try:
                            # بيع بسعر السوق فوراً
                            order = exchange.create_market_sell_order(symbol, free_qty)
                            sold_value = free_qty * current_price
                            loss = (current_price - avg_buy) * free_qty

                            msg = (
                                f"🔴 <b>Spot Guardian — تفعيل وقف الخسارة</b>\n"
                                f"العملة: {asset}\n"
                                f"تم البيع: {free_qty:.6f} {asset}\n"
                                f"سعر البيع: ${current_price:,.4f}\n"
                                f"متوسط الشراء: ${avg_buy:,.4f}\n"
                                f"الخسارة: ${loss:,.2f} ({change_pct:+.2f}%)\n"
                                f"القيمة المستردة: ${sold_value:,.2f}\n"
                                f"رقم الأمر: {order.get('id','?')[:16]}..."
                            )
                            send_telegram(msg)
                            log.info(f"✅ {asset}: تم البيع بسعر ${current_price:.4f} | استُرد ${sold_value:.2f}")

                            # إزالة الأصل من المراقبة بعد البيع
                            WATCHED_ASSETS[asset]['avg_buy'] = None
                            if asset in state:
                                del state[asset]
                            save_state(state)

                        except Exception as e:
                            log.error(f"❌ {asset}: فشل البيع: {e}")
                            send_telegram(f"❌ <b>Spot Guardian — فشل البيع!</b>\nالعملة: {asset}\nالخطأ: {e}")
                    else:
                        log.warning(f"⚠️ {asset}: الكمية الحرة ({free_qty:.6f}) أقل من الحد الأدنى")

        except Exception as e:
            log.error(f"خطأ في الحلقة الرئيسية: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    # إنشاء مجلد logs إذا لم يكن موجوداً
    os.makedirs('/root/trade_lak_bot/logs', exist_ok=True)
    run()
