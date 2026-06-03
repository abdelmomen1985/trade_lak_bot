#!/usr/bin/env python3
"""
whale_alert_checker.py
فحص نشاط الحيتان عبر OKX وCoinGlass

الاستخدام:
    python3 whale_alert_checker.py --symbol BTC
    python3 whale_alert_checker.py --symbol ETH --threshold 100000
"""

import requests
import argparse
from datetime import datetime


OKX_BASE = "https://www.okx.com/api/v5/market"


def get_order_book(symbol: str, depth: int = 400) -> dict:
    """تحليل Order Book للكشف عن جدران الحيتان"""
    try:
        inst_id = f"{symbol}-USDT"
        resp = requests.get(
            f"{OKX_BASE}/books",
            params={'instId': inst_id, 'sz': str(depth)},
            timeout=5
        )
        data = resp.json()
        if data.get('code') != '0' or not data.get('data'):
            return {}

        book = data['data'][0]
        bids = [[float(b[0]), float(b[1])] for b in book['bids']]
        asks = [[float(a[0]), float(a[1])] for a in book['asks']]

        if not bids or not asks:
            return {}

        # حساب المتوسطات
        avg_bid_size = sum(b[1] for b in bids[:50]) / 50
        avg_ask_size = sum(a[1] for a in asks[:50]) / 50

        # الكشف عن الجدران الكبيرة (أكبر من 5x المتوسط)
        large_bids = [(b[0], b[1]) for b in bids if b[1] > avg_bid_size * 5]
        large_asks = [(a[0], a[1]) for a in asks if a[1] > avg_ask_size * 5]

        # حساب نسبة Bid/Ask
        total_bid_value = sum(b[0] * b[1] for b in bids[:100])
        total_ask_value = sum(a[0] * a[1] for a in asks[:100])
        bid_ask_ratio = total_bid_value / total_ask_value if total_ask_value > 0 else 1

        return {
            'symbol': symbol,
            'current_price': bids[0][0] if bids else 0,
            'bid_ask_ratio': round(bid_ask_ratio, 3),
            'large_buy_walls': large_bids[:3],
            'large_sell_walls': large_asks[:3],
            'whale_signal': interpret_whale_signal(bid_ask_ratio, large_bids, large_asks),
        }
    except Exception as e:
        return {'error': str(e)}


def get_funding_rate(symbol: str) -> float:
    """جلب معدل التمويل الحالي"""
    try:
        inst_id = f"{symbol}-USDT-SWAP"
        resp = requests.get(
            "https://www.okx.com/api/v5/public/funding-rate",
            params={'instId': inst_id},
            timeout=5
        )
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            return float(data['data'][0]['fundingRate'])
    except Exception:
        pass
    return 0.0


def get_open_interest(symbol: str) -> dict:
    """جلب Open Interest"""
    try:
        inst_id = f"{symbol}-USDT-SWAP"
        resp = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history",
            params={'instId': inst_id, 'period': '1H', 'limit': '2'},
            timeout=5
        )
        data = resp.json()
        if data.get('code') == '0' and data.get('data') and len(data['data']) >= 2:
            current_oi = float(data['data'][0][1])
            prev_oi = float(data['data'][1][1])
            oi_change = (current_oi - prev_oi) / prev_oi * 100 if prev_oi > 0 else 0
            return {'current': current_oi, 'change_1h': round(oi_change, 2)}
    except Exception:
        pass
    return {'current': 0, 'change_1h': 0}


def interpret_whale_signal(bid_ask_ratio: float, large_bids: list, large_asks: list) -> str:
    """تفسير إشارة الحوت"""
    score = 0

    if bid_ask_ratio > 1.5:
        score += 2
    elif bid_ask_ratio > 1.2:
        score += 1
    elif bid_ask_ratio < 0.7:
        score -= 2
    elif bid_ask_ratio < 0.9:
        score -= 1

    if len(large_bids) > len(large_asks):
        score += 1
    elif len(large_asks) > len(large_bids):
        score -= 1

    if score >= 2:
        return "🟢 تراكم قوي — حيتان تشتري"
    elif score == 1:
        return "🟡 تراكم خفيف — ضغط شراء"
    elif score == 0:
        return "⚪ محايد — لا إشارة واضحة"
    elif score == -1:
        return "🟠 ضغط بيع خفيف — حذر"
    else:
        return "🔴 توزيع — حيتان تبيع"


def analyze_whale_activity(symbol: str) -> dict:
    """تحليل شامل لنشاط الحيتان"""
    print(f"\n🐋 تحليل نشاط الحيتان لـ {symbol}/USDT")
    print("─" * 50)

    ob = get_order_book(symbol)
    funding = get_funding_rate(symbol)
    oi = get_open_interest(symbol)

    # تفسير Funding Rate
    if funding < -0.005:
        funding_signal = "🟢 سلبي — حيتان تشتري Spot"
    elif funding < 0.005:
        funding_signal = "⚪ محايد"
    elif funding < 0.015:
        funding_signal = "🟡 إيجابي — سوق مضارب"
    else:
        funding_signal = "🔴 مرتفع جداً — خطر تصفية"

    # تفسير OI
    oi_signal = ""
    if oi['change_1h'] > 2:
        oi_signal = "📈 OI يرتفع بسرعة — مراكز جديدة"
    elif oi['change_1h'] > 0:
        oi_signal = "📊 OI يرتفع — تراكم"
    elif oi['change_1h'] < -2:
        oi_signal = "📉 OI ينخفض بسرعة — إغلاق مراكز"
    else:
        oi_signal = "📊 OI مستقر"

    result = {
        'symbol': symbol,
        'timestamp': datetime.now().isoformat(),
        'order_book': ob,
        'funding_rate': funding,
        'funding_signal': funding_signal,
        'open_interest': oi,
        'oi_signal': oi_signal,
        'overall_whale_signal': ob.get('whale_signal', 'N/A'),
    }

    # طباعة النتائج
    print(f"💰 السعر الحالي: ${ob.get('current_price', 0):,.4f}")
    print(f"📊 Bid/Ask Ratio: {ob.get('bid_ask_ratio', 0):.3f}")
    print(f"🐋 إشارة الحوت: {ob.get('whale_signal', 'N/A')}")
    print(f"💸 Funding Rate: {funding:.4%} — {funding_signal}")
    print(f"📈 Open Interest (1h): {oi['change_1h']:+.2f}% — {oi_signal}")

    if ob.get('large_buy_walls'):
        print(f"\n🟢 جدران شراء كبيرة:")
        for price, size in ob['large_buy_walls']:
            print(f"   ${price:,.4f} — {size:,.0f} وحدة")

    if ob.get('large_sell_walls'):
        print(f"\n🔴 جدران بيع كبيرة:")
        for price, size in ob['large_sell_walls']:
            print(f"   ${price:,.4f} — {size:,.0f} وحدة")

    # توصية نهائية
    print("\n" + "─" * 50)
    whale_score = 0
    if ob.get('bid_ask_ratio', 1) > 1.3:
        whale_score += 1
    if funding < -0.003:
        whale_score += 1
    if oi['change_1h'] > 1:
        whale_score += 1

    if whale_score >= 2:
        print("✅ توصية: إشارة حوت قوية — مناسب للدخول")
    elif whale_score == 1:
        print("⚠️ توصية: إشارة ضعيفة — انتظر تأكيداً إضافياً")
    else:
        print("❌ توصية: لا إشارة حوت — تجنب الدخول الآن")

    return result


def main():
    parser = argparse.ArgumentParser(description='فحص نشاط الحيتان')
    parser.add_argument('--symbol', default='BTC', help='رمز العملة (مثال: BTC, ETH)')
    parser.add_argument('--threshold', type=float, default=50000,
                        help='الحد الأدنى لحجم الجدار بالوحدات')
    args = parser.parse_args()

    analyze_whale_activity(args.symbol.upper())


if __name__ == '__main__':
    main()
