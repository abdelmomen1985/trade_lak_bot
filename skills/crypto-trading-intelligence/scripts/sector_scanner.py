#!/usr/bin/env python3
"""
sector_scanner.py
فحص القطاعات وترتيبها حسب قوة السيولة والزخم

الاستخدام:
    python3 sector_scanner.py
    python3 sector_scanner.py --top 3
    python3 sector_scanner.py --sector DeFi
"""

import requests
import argparse
from datetime import datetime

# تعريف القطاعات وعملاتها
SECTORS = {
    'Layer1':         ['ETH', 'SOL', 'ADA', 'AVAX', 'ICP', 'NEAR', 'ATOM'],
    'Layer2':         ['ARB', 'OP', 'MATIC', 'ZKJ', 'STRK', 'IMX'],
    'DeFi':           ['AAVE', 'UNI', 'CRV', 'COMP', 'MKR', 'DYDX'],
    'Infrastructure': ['LINK', 'LPT', 'GRT', 'API3', 'BAND'],
    'Payments':       ['XRP', 'XLM', 'LTC', 'TRX', 'BCH'],
    'Exchange':       ['BNB', 'OKB', 'CRO'],
    'AI_Data':        ['FET', 'OCEAN', 'RNDR', 'TAO', 'AGIX'],
    'Gaming_NFT':     ['AXS', 'SAND', 'MANA', 'GALA', 'ENJ'],
    'Privacy':        ['XMR', 'ZEC', 'DASH'],
    'RWA_Staking':    ['CFG', 'ONDO', 'LDO', 'RPL'],
    'Meme':           ['DOGE', 'SHIB', 'PEPE', 'FLOKI'],
    'BTC_Ecosystem':  ['STX', 'ORDI', 'RUNE'],
}

OKX_BASE = "https://www.okx.com/api/v5/market"


def get_ticker(symbol: str) -> dict:
    """جلب بيانات العملة من OKX"""
    try:
        inst_id = f"{symbol}-USDT"
        resp = requests.get(f"{OKX_BASE}/ticker", params={'instId': inst_id}, timeout=5)
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            d = data['data'][0]
            return {
                'symbol': symbol,
                'price': float(d['last']),
                'price_change_24h': float(d['sodUtc8']) and (float(d['last']) - float(d['sodUtc8'])) / float(d['sodUtc8']) * 100 if float(d.get('sodUtc8', 0)) > 0 else 0,
                'volume_24h': float(d['volCcy24h']),
                'open_24h': float(d.get('open24h', d['last'])),
            }
    except Exception:
        pass
    return None


def calculate_sector_score(coins_data: list) -> float:
    """حساب نقاط القطاع"""
    if not coins_data:
        return 0
    scores = []
    for coin in coins_data:
        price_change = coin.get('price_change_24h', 0)
        # نقاط بسيطة بدون OI (لا يتطلب API مدفوع)
        score = price_change * 0.6 + (1 if price_change > 0 else -1) * 0.4
        scores.append(score)
    return sum(scores) / len(scores)


def scan_all_sectors(top_n: int = None) -> list:
    """فحص جميع القطاعات وترتيبها"""
    print(f"🔍 فحص {len(SECTORS)} قطاع...")
    results = []

    for sector_name, coins in SECTORS.items():
        sector_coins = []
        for coin in coins[:5]:  # فحص أول 5 عملات فقط
            ticker = get_ticker(coin)
            if ticker:
                sector_coins.append(ticker)

        if sector_coins:
            score = calculate_sector_score(sector_coins)
            best_coin = max(sector_coins, key=lambda x: x.get('price_change_24h', 0))
            results.append({
                'sector': sector_name,
                'score': round(score, 2),
                'coins_analyzed': len(sector_coins),
                'best_coin': best_coin['symbol'],
                'best_coin_change': round(best_coin.get('price_change_24h', 0), 2),
                'avg_change': round(
                    sum(c.get('price_change_24h', 0) for c in sector_coins) / len(sector_coins), 2
                ),
            })

    # ترتيب حسب النقاط
    results.sort(key=lambda x: x['score'], reverse=True)

    if top_n:
        results = results[:top_n]

    return results


def print_results(results: list):
    """طباعة النتائج بشكل منسق"""
    print(f"\n{'='*60}")
    print(f"📊 تقرير القطاعات — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    medals = ['🥇', '🥈', '🥉']
    for i, r in enumerate(results):
        medal = medals[i] if i < 3 else f"  {i+1}."
        bonus = ""
        if i == 0:
            bonus = " (+20% ثقة)"
        elif i == 1:
            bonus = " (+12% ثقة)"
        elif i == 2:
            bonus = " (+7% ثقة)"

        print(f"{medal} {r['sector']:<18} | نقاط: {r['score']:>+6.2f} | "
              f"أفضل: {r['best_coin']:<8} {r['best_coin_change']:>+6.2f}%{bonus}")

    print(f"{'='*60}")
    if results:
        print(f"\n🚀 القطاع الأقوى: {results[0]['sector']}")
        print(f"💡 العملة المرشحة للانفجار: {results[0]['best_coin']}/USDT")


def main():
    parser = argparse.ArgumentParser(description='فحص قطاعات العملات الرقمية')
    parser.add_argument('--top', type=int, default=None, help='عرض أفضل N قطاعات')
    parser.add_argument('--sector', help='تحليل قطاع محدد')
    args = parser.parse_args()

    if args.sector:
        sector_coins = SECTORS.get(args.sector, [])
        if not sector_coins:
            print(f"❌ القطاع '{args.sector}' غير موجود")
            print(f"القطاعات المتاحة: {', '.join(SECTORS.keys())}")
            return
        results = scan_all_sectors()
        sector_result = next((r for r in results if r['sector'] == args.sector), None)
        if sector_result:
            print_results([sector_result])
    else:
        results = scan_all_sectors(top_n=args.top)
        print_results(results)


if __name__ == '__main__':
    main()
