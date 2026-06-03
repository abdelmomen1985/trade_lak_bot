# ============================================================
# Trade Lak — Performance Tracker (24-Hour Monitor)
# مراقب الأداء الشامل لـ 24 ساعة مع احتساب رسوم OKX
# ============================================================
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── رسوم OKX الحقيقية (Taker = 0.1%) ──────────────────────
OKX_TAKER_FEE = 0.001   # 0.1% لكل عملية
OKX_MAKER_FEE = 0.0008  # 0.08% للـ Maker
# رسوم الصفقة الكاملة (شراء + بيع) = 0.2%
ROUND_TRIP_FEE = OKX_TAKER_FEE * 2

# الحد الأدنى للربح الصافي بعد الرسوم
# صفقة $19.5: رسوم = $0.039 → يجب أن يكون الربح > $0.039
MIN_PROFIT_AFTER_FEE_PCT = 0.25  # 0.25% = 2.5x الرسوم (هامش أمان)


class TradeRecord:
    """سجل صفقة واحدة مع تتبع الرسوم والربح الصافي"""

    def __init__(self, symbol: str, direction: str, entry_price: float,
                 amount_usdt: float, confidence: float, entry_time: float = None):
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.amount_usdt = amount_usdt
        self.confidence = confidence
        self.entry_time = entry_time or time.time()

        # رسوم الدخول
        self.entry_fee = amount_usdt * OKX_TAKER_FEE
        self.entry_fee_pct = OKX_TAKER_FEE * 100

        # بيانات الخروج
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[float] = None
        self.exit_reason: Optional[str] = None
        self.exit_fee: float = 0.0

        # P&L
        self.gross_pnl_usdt: float = 0.0
        self.gross_pnl_pct: float = 0.0
        self.net_pnl_usdt: float = 0.0
        self.net_pnl_pct: float = 0.0
        self.total_fees: float = 0.0
        self.is_fee_killer: bool = False  # هل الرسوم أكلت الربح؟

    def close(self, exit_price: float, exit_reason: str = "unknown"):
        """إغلاق الصفقة وحساب الربح الصافي"""
        self.exit_price = exit_price
        self.exit_time = time.time()
        self.exit_reason = exit_reason

        # حساب الربح الإجمالي
        if self.direction in ('SPOT_BUY', 'LONG'):
            self.gross_pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100
        else:  # SHORT
            self.gross_pnl_pct = (self.entry_price - exit_price) / self.entry_price * 100

        self.gross_pnl_usdt = self.amount_usdt * (self.gross_pnl_pct / 100)

        # رسوم الخروج
        exit_amount = self.amount_usdt + self.gross_pnl_usdt
        self.exit_fee = exit_amount * OKX_TAKER_FEE
        self.total_fees = self.entry_fee + self.exit_fee

        # الربح الصافي
        self.net_pnl_usdt = self.gross_pnl_usdt - self.total_fees
        self.net_pnl_pct = self.net_pnl_usdt / self.amount_usdt * 100

        # هل الرسوم أكلت الربح؟
        if self.gross_pnl_usdt > 0 and self.net_pnl_usdt <= 0:
            self.is_fee_killer = True

    def duration_minutes(self) -> float:
        """مدة الصفقة بالدقائق"""
        end = self.exit_time or time.time()
        return (end - self.entry_time) / 60

    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'amount_usdt': self.amount_usdt,
            'confidence': self.confidence,
            'entry_time': datetime.fromtimestamp(self.entry_time).isoformat(),
            'exit_time': datetime.fromtimestamp(self.exit_time).isoformat() if self.exit_time else None,
            'exit_reason': self.exit_reason,
            'gross_pnl_usdt': round(self.gross_pnl_usdt, 4),
            'gross_pnl_pct': round(self.gross_pnl_pct, 4),
            'entry_fee': round(self.entry_fee, 4),
            'exit_fee': round(self.exit_fee, 4),
            'total_fees': round(self.total_fees, 4),
            'net_pnl_usdt': round(self.net_pnl_usdt, 4),
            'net_pnl_pct': round(self.net_pnl_pct, 4),
            'duration_minutes': round(self.duration_minutes(), 1),
            'is_fee_killer': self.is_fee_killer,
        }


class PerformanceTracker:
    """
    مراقب الأداء الشامل لـ Trade Lak
    يتتبع كل صفقة مع الرسوم ويولّد تقارير دورية
    """

    def __init__(self, notifier=None, total_capital: float = 1104.98):
        self.notifier = notifier
        self.total_capital = total_capital
        self.start_time = time.time()
        self.start_portfolio_value: Optional[float] = None

        # سجل الصفقات
        self.open_trades: Dict[str, TradeRecord] = {}
        self.closed_trades: List[TradeRecord] = []

        # إحصائيات متراكمة
        self.total_fees_paid: float = 0.0
        self.total_gross_pnl: float = 0.0
        self.total_net_pnl: float = 0.0
        self.fee_killer_count: int = 0  # صفقات أكلت الرسوم الربح

        # تتبع الأداء كل ساعة
        self.hourly_snapshots: List[dict] = []
        self.last_hourly_check = time.time()
        self.last_4h_check = time.time()
        self.last_24h_check = time.time()

        # تحميل البيانات المحفوظة
        self._load_data()
        logger.info("✅ Performance Tracker مُهيَّأ — يراقب الأداء مع احتساب رسوم OKX (0.1%)")

    def _load_data(self):
        """تحميل البيانات المحفوظة"""
        try:
            import os
            path = '/root/trade_lak_bot/data/performance_tracker.json'
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                self.total_fees_paid = data.get('total_fees_paid', 0)
                self.total_gross_pnl = data.get('total_gross_pnl', 0)
                self.total_net_pnl = data.get('total_net_pnl', 0)
                self.fee_killer_count = data.get('fee_killer_count', 0)
                self.hourly_snapshots = data.get('hourly_snapshots', [])
                logger.info(f"📂 تم تحميل بيانات الأداء: {len(self.hourly_snapshots)} لقطة ساعية")
        except Exception as e:
            logger.debug(f"لا توجد بيانات محفوظة: {e}")

    def _save_data(self):
        """حفظ البيانات"""
        try:
            import os
            os.makedirs('/root/trade_lak_bot/data', exist_ok=True)
            data = {
                'total_fees_paid': self.total_fees_paid,
                'total_gross_pnl': self.total_gross_pnl,
                'total_net_pnl': self.total_net_pnl,
                'fee_killer_count': self.fee_killer_count,
                'hourly_snapshots': self.hourly_snapshots[-48:],  # آخر 48 ساعة
                'closed_trades': [t.to_dict() for t in self.closed_trades[-100:]],
                'last_updated': datetime.now().isoformat(),
            }
            with open('/root/trade_lak_bot/data/performance_tracker.json', 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"خطأ في حفظ بيانات الأداء: {e}")

    def record_trade_open(self, symbol: str, direction: str, entry_price: float,
                          amount_usdt: float, confidence: float):
        """تسجيل فتح صفقة جديدة"""
        record = TradeRecord(symbol, direction, entry_price, amount_usdt, confidence)
        self.open_trades[symbol] = record
        logger.info(
            f"📊 [Tracker] فتح: {symbol} | {direction} | "
            f"${amount_usdt:.2f} @ ${entry_price:.4f} | "
            f"رسوم دخول: ${record.entry_fee:.4f}"
        )

    def record_trade_close(self, symbol: str, exit_price: float,
                           exit_reason: str = "unknown") -> Optional[TradeRecord]:
        """تسجيل إغلاق صفقة وحساب الربح الصافي"""
        if symbol not in self.open_trades:
            return None

        record = self.open_trades.pop(symbol)
        record.close(exit_price, exit_reason)

        self.closed_trades.append(record)
        self.total_fees_paid += record.total_fees
        self.total_gross_pnl += record.gross_pnl_usdt
        self.total_net_pnl += record.net_pnl_usdt

        if record.is_fee_killer:
            self.fee_killer_count += 1

        # تحذير إذا كانت الرسوم أكلت الربح
        if record.is_fee_killer:
            msg = (
                f"⚠️ رسوم OKX أكلت الربح!\n"
                f"العملة: {symbol}\n"
                f"الربح الإجمالي: +${record.gross_pnl_usdt:.4f} ({record.gross_pnl_pct:+.3f}%)\n"
                f"الرسوم: -${record.total_fees:.4f}\n"
                f"الربح الصافي: ${record.net_pnl_usdt:.4f} ❌"
            )
            logger.warning(msg)
            if self.notifier:
                try:
                    self.notifier.send_telegram(msg, "⚠️ تحذير رسوم")
                except Exception:
                    pass
        else:
            emoji = "✅" if record.net_pnl_usdt > 0 else "❌"
            logger.info(
                f"📊 [Tracker] إغلاق: {symbol} | {exit_reason} | "
                f"إجمالي: {record.gross_pnl_pct:+.3f}% | "
                f"رسوم: -${record.total_fees:.4f} | "
                f"صافي: {record.net_pnl_pct:+.3f}% {emoji}"
            )

        self._save_data()
        return record

    def get_current_stats(self) -> dict:
        """إحصائيات الأداء الحالية"""
        closed = self.closed_trades
        if not closed:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_fees': self.total_fees_paid,
                'gross_pnl': self.total_gross_pnl,
                'net_pnl': self.total_net_pnl,
                'fee_killer_count': self.fee_killer_count,
                'open_trades': len(self.open_trades),
            }

        winners = [t for t in closed if t.net_pnl_usdt > 0]
        losers = [t for t in closed if t.net_pnl_usdt <= 0]
        fee_killers = [t for t in closed if t.is_fee_killer]

        avg_win = sum(t.net_pnl_pct for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.net_pnl_pct for t in losers) / len(losers) if losers else 0
        avg_duration = sum(t.duration_minutes() for t in closed) / len(closed)

        # أصغر ربح (هل يغطي الرسوم؟)
        min_win_pct = min((t.gross_pnl_pct for t in winners), default=0)

        return {
            'total_trades': len(closed),
            'open_trades': len(self.open_trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': len(winners) / len(closed) * 100,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'avg_duration_min': avg_duration,
            'total_fees': round(self.total_fees_paid, 4),
            'gross_pnl': round(self.total_gross_pnl, 4),
            'net_pnl': round(self.total_net_pnl, 4),
            'fee_killer_count': self.fee_killer_count,
            'fee_killer_pct': len(fee_killers) / len(closed) * 100 if closed else 0,
            'min_win_pct': min_win_pct,
            'breakeven_pct': ROUND_TRIP_FEE * 100,
        }

    def take_hourly_snapshot(self, portfolio_value: float):
        """أخذ لقطة ساعية للأداء"""
        stats = self.get_current_stats()
        snapshot = {
            'time': datetime.now().isoformat(),
            'portfolio_value': portfolio_value,
            'net_pnl': stats['net_pnl'],
            'total_fees': stats['total_fees'],
            'trades_count': stats['total_trades'],
            'win_rate': stats['win_rate'],
        }
        self.hourly_snapshots.append(snapshot)
        self._save_data()
        return snapshot

    def check_periodic_reports(self, portfolio_value: float):
        """فحص وإرسال التقارير الدورية"""
        now = time.time()

        # تقرير ساعي
        if now - self.last_hourly_check >= 3600:
            self.last_hourly_check = now
            self._send_hourly_report(portfolio_value)
            self.take_hourly_snapshot(portfolio_value)

        # تقرير 4 ساعات
        if now - self.last_4h_check >= 14400:
            self.last_4h_check = now
            self._send_4h_report(portfolio_value)

        # تقرير 24 ساعة
        if now - self.last_24h_check >= 86400:
            self.last_24h_check = now
            self._send_24h_report(portfolio_value)

    def _send_hourly_report(self, portfolio_value: float):
        """تقرير ساعي مختصر"""
        stats = self.get_current_stats()
        uptime_h = (time.time() - self.start_time) / 3600

        msg = (
            f"📊 تقرير ساعي — Trade Lak\n"
            f"{'─'*30}\n"
            f"⏱️ وقت التشغيل: {uptime_h:.1f} ساعة\n"
            f"💼 قيمة المحفظة: ${portfolio_value:.2f}\n"
            f"📈 صافي الربح: ${stats['net_pnl']:+.2f}\n"
            f"💸 رسوم مدفوعة: ${stats['total_fees']:.4f}\n"
            f"🔢 صفقات مغلقة: {stats['total_trades']}\n"
            f"🎯 Win Rate: {stats['win_rate']:.1f}%\n"
            f"📂 صفقات مفتوحة: {stats['open_trades']}\n"
        )

        if stats['fee_killer_count'] > 0:
            msg += f"⚠️ صفقات أكلت الرسوم ربحها: {stats['fee_killer_count']}\n"

        logger.info(msg)
        if self.notifier:
            try:
                self.notifier.send_telegram(msg, "📊 تقرير ساعي")
            except Exception:
                pass

    def _send_4h_report(self, portfolio_value: float):
        """تقرير 4 ساعات تفصيلي"""
        stats = self.get_current_stats()

        # تحليل الرسوم
        fee_impact = (stats['total_fees'] / abs(stats['gross_pnl'])) * 100 if stats['gross_pnl'] != 0 else 0

        msg = (
            f"📊 تقرير 4 ساعات — Trade Lak\n"
            f"{'─'*35}\n"
            f"💼 المحفظة: ${portfolio_value:.2f}\n"
            f"\n"
            f"📈 الأداء:\n"
            f"  ربح إجمالي: ${stats['gross_pnl']:+.2f}\n"
            f"  رسوم OKX: -${stats['total_fees']:.4f}\n"
            f"  ربح صافي: ${stats['net_pnl']:+.2f}\n"
            f"  تأثير الرسوم: {fee_impact:.1f}% من الربح\n"
            f"\n"
            f"📊 الصفقات:\n"
            f"  إجمالي: {stats['total_trades']}\n"
            f"  رابحة: {stats['winners']} | خاسرة: {stats['losers']}\n"
            f"  Win Rate: {stats['win_rate']:.1f}%\n"
            f"  متوسط مدة الصفقة: {stats['avg_duration_min']:.0f} دقيقة\n"
            f"\n"
            f"💸 تحليل الرسوم:\n"
            f"  نقطة التعادل: {stats['breakeven_pct']:.2f}% (0.2%)\n"
            f"  صفقات أكلت الرسوم ربحها: {stats['fee_killer_count']}\n"
            f"  نسبتها: {stats['fee_killer_pct']:.1f}%\n"
        )

        if stats['fee_killer_pct'] > 20:
            msg += f"\n⚠️ تحذير: {stats['fee_killer_pct']:.0f}% من الصفقات لا تغطي الرسوم!\n"
            msg += "💡 توصية: رفع حد الربح الأدنى أو زيادة حجم الصفقة\n"

        logger.info(msg)
        if self.notifier:
            try:
                self.notifier.send_telegram(msg, "📊 تقرير 4 ساعات")
            except Exception:
                pass

    def _send_24h_report(self, portfolio_value: float):
        """تقرير 24 ساعة الشامل مع توصيات"""
        stats = self.get_current_stats()

        # تحليل الساعات الأفضل
        best_hours = self._analyze_best_hours()

        # توصيات بناءً على البيانات
        recommendations = self._generate_recommendations(stats)

        msg = (
            f"📊 تقرير 24 ساعة الشامل — Trade Lak\n"
            f"{'═'*40}\n"
            f"\n"
            f"💼 المحفظة:\n"
            f"  القيمة الحالية: ${portfolio_value:.2f}\n"
            f"  رأس المال المُودَع: ${self.total_capital:.2f}\n"
            f"  الربح الإجمالي: ${portfolio_value - self.total_capital:+.2f} "
            f"({(portfolio_value - self.total_capital) / self.total_capital * 100:+.2f}%)\n"
            f"\n"
            f"📈 أداء اليوم:\n"
            f"  ربح إجمالي: ${stats['gross_pnl']:+.2f}\n"
            f"  رسوم OKX المدفوعة: -${stats['total_fees']:.4f}\n"
            f"  ربح صافي: ${stats['net_pnl']:+.2f}\n"
            f"\n"
            f"📊 إحصائيات الصفقات:\n"
            f"  إجمالي الصفقات: {stats['total_trades']}\n"
            f"  رابحة: {stats['winners']} | خاسرة: {stats['losers']}\n"
            f"  Win Rate: {stats['win_rate']:.1f}%\n"
            f"  متوسط ربح الصفقة الرابحة: {stats['avg_win_pct']:+.3f}%\n"
            f"  متوسط خسارة الصفقة الخاسرة: {stats['avg_loss_pct']:+.3f}%\n"
            f"  متوسط مدة الصفقة: {stats['avg_duration_min']:.0f} دقيقة\n"
            f"\n"
            f"💸 تحليل الرسوم:\n"
            f"  نقطة التعادل: 0.20% لكل صفقة\n"
            f"  صفقات أكلت الرسوم ربحها: {stats['fee_killer_count']} ({stats['fee_killer_pct']:.1f}%)\n"
            f"\n"
            f"💡 التوصيات:\n"
        )

        for i, rec in enumerate(recommendations, 1):
            msg += f"  {i}. {rec}\n"

        logger.info(msg)
        if self.notifier:
            try:
                self.notifier.send_telegram(msg, "📊 تقرير 24 ساعة")
            except Exception:
                pass

    def _analyze_best_hours(self) -> list:
        """تحليل أفضل ساعات التداول"""
        hour_pnl = {}
        for trade in self.closed_trades:
            hour = datetime.fromtimestamp(trade.entry_time).hour
            if hour not in hour_pnl:
                hour_pnl[hour] = []
            hour_pnl[hour].append(trade.net_pnl_pct)

        best = sorted(hour_pnl.items(), key=lambda x: sum(x[1]), reverse=True)
        return [(h, sum(pnls)) for h, pnls in best[:3]]

    def _generate_recommendations(self, stats: dict) -> list:
        """توليد توصيات ذكية بناءً على الأداء"""
        recs = []

        # توصية 1: الرسوم
        if stats['fee_killer_pct'] > 15:
            recs.append(
                f"رفع حد الربح الأدنى من 0.25% إلى 0.5% "
                f"({stats['fee_killer_pct']:.0f}% من الصفقات لا تغطي الرسوم)"
            )

        # توصية 2: Win Rate
        if stats['win_rate'] < 50:
            recs.append(
                f"رفع حد الثقة من 25% إلى 30% "
                f"(Win Rate {stats['win_rate']:.0f}% أقل من المطلوب)"
            )
        elif stats['win_rate'] > 70:
            recs.append(
                f"Win Rate ممتاز ({stats['win_rate']:.0f}%) — يمكن زيادة حجم الصفقة بأمان"
            )

        # توصية 3: مدة الصفقة
        if stats.get('avg_duration_min', 0) < 30:
            recs.append(
                "الصفقات قصيرة جداً — فكر في رفع TP لتحقيق أرباح أكبر"
            )

        # توصية 4: حجم الصفقة
        if stats['net_pnl'] < 0 and stats['total_fees'] > abs(stats['net_pnl']) * 0.5:
            recs.append(
                "الرسوم تمثل أكثر من 50% من الخسارة — زيادة حجم الصفقة تقلل تأثير الرسوم"
            )

        if not recs:
            recs.append("الأداء جيد — استمر في نفس الاستراتيجية")

        return recs

    def get_fee_analysis_for_trade(self, amount_usdt: float, target_pct: float) -> dict:
        """
        تحليل جدوى الصفقة قبل تنفيذها
        هل الهدف يغطي الرسوم؟
        """
        entry_fee = amount_usdt * OKX_TAKER_FEE
        exit_fee = amount_usdt * (1 + target_pct / 100) * OKX_TAKER_FEE
        total_fees = entry_fee + exit_fee
        gross_profit = amount_usdt * (target_pct / 100)
        net_profit = gross_profit - total_fees
        breakeven_pct = ROUND_TRIP_FEE * 100  # 0.2%

        return {
            'amount_usdt': amount_usdt,
            'target_pct': target_pct,
            'entry_fee': round(entry_fee, 4),
            'exit_fee': round(exit_fee, 4),
            'total_fees': round(total_fees, 4),
            'gross_profit': round(gross_profit, 4),
            'net_profit': round(net_profit, 4),
            'is_profitable': net_profit > 0,
            'breakeven_pct': breakeven_pct,
            'fee_impact_pct': round(total_fees / gross_profit * 100, 1) if gross_profit > 0 else 999,
        }
