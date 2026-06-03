#!/usr/bin/env python3
"""
analyze_trade_history.py
تحليل سجل الصفقات واستخراج الأنماط لتدريب البوت

الاستخدام:
    python3 analyze_trade_history.py --log /root/bot_log.txt
    python3 analyze_trade_history.py --log /root/bot_log.txt --output report.json
"""

import re
import json
import argparse
from datetime import datetime
from collections import defaultdict


def parse_trade_log(log_path: str) -> list:
    """استخراج الصفقات من ملف السجل"""
    trades = []
    current_trade = None

    open_pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*'
        r'OPENED.*?([A-Z]+/USDT).*?'
        r'entry[=:]?\s*([\d.]+).*?'
        r'confidence[=:]?\s*([\d.]+)',
        re.IGNORECASE
    )
    close_pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*'
        r'CLOSED.*?([A-Z]+/USDT).*?'
        r'P&L[=:]?\s*([+-]?[\d.]+)%',
        re.IGNORECASE
    )

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            open_match = open_pattern.search(line)
            if open_match:
                current_trade = {
                    'open_time': open_match.group(1),
                    'symbol': open_match.group(2),
                    'entry_price': float(open_match.group(3)),
                    'confidence': float(open_match.group(4)),
                    'sector': extract_sector(line),
                    'market': 'futures' if 'FUTURES' in line.upper() else 'spot',
                }

            close_match = close_pattern.search(line)
            if close_match and current_trade:
                symbol = close_match.group(2)
                if symbol == current_trade.get('symbol'):
                    current_trade['close_time'] = close_match.group(1)
                    current_trade['pnl_pct'] = float(close_match.group(3))
                    current_trade['result'] = 'WIN' if current_trade['pnl_pct'] > 0 else 'LOSS'
                    trades.append(current_trade)
                    current_trade = None

    return trades


def extract_sector(line: str) -> str:
    """استخراج اسم القطاع من السطر"""
    sectors = ['Layer1', 'Layer2', 'DeFi', 'Infrastructure', 'Payments',
               'Exchange', 'AI', 'Gaming', 'Privacy', 'RWA', 'Meme', 'BTC']
    for sector in sectors:
        if sector.lower() in line.lower():
            return sector
    return 'Unknown'


def analyze_trades(trades: list) -> dict:
    """تحليل شامل للصفقات"""
    if not trades:
        return {'error': 'No trades found'}

    total = len(trades)
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']

    win_rate = len(wins) / total * 100
    avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # تحليل حسب القطاع
    sector_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0})
    for trade in trades:
        sector = trade.get('sector', 'Unknown')
        if trade['result'] == 'WIN':
            sector_stats[sector]['wins'] += 1
        else:
            sector_stats[sector]['losses'] += 1
        sector_stats[sector]['total_pnl'] += trade['pnl_pct']

    # تحليل حسب مستوى الثقة
    confidence_buckets = defaultdict(lambda: {'wins': 0, 'losses': 0})
    for trade in trades:
        conf = trade.get('confidence', 0)
        bucket = f"{int(conf // 10) * 10}-{int(conf // 10) * 10 + 9}%"
        if trade['result'] == 'WIN':
            confidence_buckets[bucket]['wins'] += 1
        else:
            confidence_buckets[bucket]['losses'] += 1

    # أفضل وأسوأ الصفقات
    sorted_by_pnl = sorted(trades, key=lambda x: x['pnl_pct'], reverse=True)

    return {
        'summary': {
            'total_trades': total,
            'win_rate': round(win_rate, 2),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'total_pnl_pct': round(sum(t['pnl_pct'] for t in trades), 2),
        },
        'by_sector': {
            sector: {
                'win_rate': round(stats['wins'] / (stats['wins'] + stats['losses']) * 100, 1),
                'total_pnl': round(stats['total_pnl'], 2),
                'trades': stats['wins'] + stats['losses']
            }
            for sector, stats in sector_stats.items()
        },
        'by_confidence': dict(confidence_buckets),
        'best_trades': sorted_by_pnl[:5],
        'worst_trades': sorted_by_pnl[-5:],
        'recommendations': generate_recommendations(trades, sector_stats, confidence_buckets)
    }


def generate_recommendations(trades, sector_stats, confidence_buckets) -> list:
    """توليد توصيات لتحسين البوت"""
    recommendations = []

    # توصيات القطاعات
    for sector, stats in sector_stats.items():
        total_sector = stats['wins'] + stats['losses']
        if total_sector >= 3:
            win_rate = stats['wins'] / total_sector * 100
            if win_rate < 40:
                recommendations.append(
                    f"⚠️ قطاع {sector}: معدل نجاح {win_rate:.0f}% — فكر في رفع حد الثقة لهذا القطاع"
                )
            elif win_rate > 70:
                recommendations.append(
                    f"✅ قطاع {sector}: معدل نجاح {win_rate:.0f}% — يمكن زيادة حجم المراكز"
                )

    # توصيات الثقة
    for bucket, stats in confidence_buckets.items():
        total_bucket = stats['wins'] + stats['losses']
        if total_bucket >= 3:
            win_rate = stats['wins'] / total_bucket * 100
            if win_rate < 45:
                recommendations.append(
                    f"⚠️ ثقة {bucket}: معدل نجاح {win_rate:.0f}% — ارفع الحد الأدنى للثقة"
                )

    return recommendations


def main():
    parser = argparse.ArgumentParser(description='تحليل سجل صفقات البوت')
    parser.add_argument('--log', default='/root/bot_log.txt', help='مسار ملف السجل')
    parser.add_argument('--output', help='حفظ النتائج في ملف JSON')
    args = parser.parse_args()

    print(f"📊 تحليل سجل الصفقات: {args.log}")
    trades = parse_trade_log(args.log)
    print(f"✅ تم استخراج {len(trades)} صفقة")

    analysis = analyze_trades(trades)

    if args.output:
        with open(args.output, 'w', ensure_ascii=False) as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"✅ النتائج محفوظة في: {args.output}")
    else:
        print("\n" + "="*50)
        print("📈 ملخص الأداء:")
        summary = analysis.get('summary', {})
        for key, val in summary.items():
            print(f"  {key}: {val}")

        print("\n🏆 أداء القطاعات:")
        for sector, stats in analysis.get('by_sector', {}).items():
            print(f"  {sector}: {stats['win_rate']}% win rate | {stats['total_pnl']:+.1f}% PnL")

        print("\n💡 التوصيات:")
        for rec in analysis.get('recommendations', []):
            print(f"  {rec}")


if __name__ == '__main__':
    main()
