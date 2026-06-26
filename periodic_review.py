#!/usr/bin/env python3
"""
Trade Lak — Periodic Review System / نظام المراجعة الدورية الشاملة
====================================================================
يعمل داخل الحلقة الرئيسية ويُشغِّل مراجعات بترددات مختلفة:

┌─────────────────────────────────────────────────────────────────┐
│  كل 30 دقيقة  → مراجعة الأداء الفوري (صفقات + سيولة + APIs)   │
│  كل ساعة      → مراجعة المحركات الذكية (Fake Break + Sector)   │
│  كل 4 ساعات   → مراجعة الكفاءة الكاملة (ML + Strategy + Risk) │
│  كل 24 ساعة   → مراجعة شاملة (تقرير يومي + تحديث ML)          │
└─────────────────────────────────────────────────────────────────┘

لماذا هذه الترددات؟
- 30 دقيقة: السوق يتغير بسرعة، الصفقات المفتوحة تحتاج رقابة مستمرة
- ساعة: كافية لرصد تحولات القطاعات وإشارات Fake Break
- 4 ساعات: تتوافق مع الشمعة 4H المستخدمة في الاستراتيجية
- 24 ساعة: تقرير يومي شامل + إعادة تدريب ML
"""

import os
import sys
import logging
import datetime
import requests
from typing import Optional

logger = logging.getLogger('PeriodicReview')


class PeriodicReviewSystem:
    """
    نظام المراجعة الدورية الشاملة لـ Trade Lak.
    يُنشئ تقارير Telegram مفصلة بترددات مختلفة.
    """

    # ── ترددات المراجعة (بالدقائق) ──
    REVIEW_30MIN  = 30    # مراجعة الأداء الفوري
    REVIEW_1H     = 60    # مراجعة المحركات الذكية
    REVIEW_4H     = 240   # مراجعة الكفاءة الكاملة
    REVIEW_24H    = 1440  # المراجعة الشاملة اليومية

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.last_30min  = datetime.datetime.min
        self.last_1h     = datetime.datetime.min
        self.last_4h     = datetime.datetime.min
        self.last_24h    = datetime.datetime.min
        # إحصائيات تراكمية
        self._api_errors = {}       # {api_name: error_count}
        self._trade_snapshots = []  # لقطات الصفقات عبر الزمن
        logger.info("✅ Periodic Review System مُهيَّأ")

    # ================================================================
    # الدالة الرئيسية — تُستدعى في كل دورة من main loop
    # ================================================================
    def tick(self):
        """
        يُستدعى في كل دورة من الحلقة الرئيسية (كل 60 ثانية).
        يُقرر أي مراجعة يجب تشغيلها الآن.
        """
        now = datetime.datetime.now()

        # مراجعة 30 دقيقة
        if (now - self.last_30min).total_seconds() >= self.REVIEW_30MIN * 60:
            self._run_30min_review(now)
            self.last_30min = now

        # مراجعة ساعة
        if (now - self.last_1h).total_seconds() >= self.REVIEW_1H * 60:
            self._run_1h_review(now)
            self.last_1h = now

        # مراجعة 4 ساعات
        if (now - self.last_4h).total_seconds() >= self.REVIEW_4H * 60:
            self._run_4h_review(now)
            self.last_4h = now

        # مراجعة 24 ساعة
        if (now - self.last_24h).total_seconds() >= self.REVIEW_24H * 60:
            self._run_24h_review(now)
            self.last_24h = now

    # ================================================================
    # مراجعة كل 30 دقيقة — الأداء الفوري
    # ================================================================
    def _run_30min_review(self, now: datetime.datetime):
        """
        مراجعة سريعة كل 30 دقيقة تشمل:
        - حالة الصفقات المفتوحة وأرباحها الحالية
        - فحص اتصال APIs الحيوية (OKX + CoinGlass)
        - تنبيه فوري إذا كانت صفقة في خطر
        """
        logger.info("⏱️ [30min] بدء المراجعة الدورية السريعة...")
        sections = []

        # 1. حالة الصفقات المفتوحة
        trades_section = self._check_open_trades_status()
        sections.append(trades_section)

        # 2. فحص اتصال APIs
        api_section = self._check_api_connections()
        sections.append(api_section)

        # 3. فحص الصفقات في خطر
        risk_section = self._check_trades_at_risk()
        if risk_section:
            sections.append(risk_section)

        # إرسال التقرير فقط إذا كان هناك شيء مهم
        has_warning = any("⚠️" in s or "🚨" in s for s in sections)
        if has_warning:
            msg = f"⏱️ <b>Trade Lak — مراجعة 30 دقيقة</b>\n"
            msg += f"🕐 {now.strftime('%H:%M')}\n\n"
            msg += "\n\n".join(sections)
            self._send(msg)
            logger.info("📤 [30min] أُرسل تقرير تحذيري")
        else:
            logger.info("✅ [30min] كل شيء طبيعي — لا تحذيرات")

    # ================================================================
    # مراجعة كل ساعة — المحركات الذكية
    # ================================================================
    def _run_1h_review(self, now: datetime.datetime):
        """
        مراجعة شاملة كل ساعة تشمل:
        - أداء محرك Fake Break (كم إشارة اكتشف؟ كم نجحت؟)
        - أداء محرك القطاعات (أي قطاع يقود؟)
        - أداء PostEntry Monitor (كم قرار EARLY_EXIT؟)
        - رصيد OKX الحالي مع مقارنة بالساعة السابقة
        - حالة Dashboard (هل يستقبل البيانات؟)
        """
        logger.info("🕐 [1h] بدء المراجعة الساعية...")
        sections = []

        # 1. أداء المحركات الذكية
        engines_section = self._check_smart_engines()
        sections.append(engines_section)

        # 2. تحليل القطاعات الحالي
        sector_section = self._check_sector_status()
        sections.append(sector_section)

        # 3. رصيد المحفظة
        balance_section = self._check_portfolio_balance()
        sections.append(balance_section)

        # 4. حالة Dashboard
        dashboard_section = self._check_dashboard_connection()
        sections.append(dashboard_section)

        msg = f"🕐 <b>Trade Lak — مراجعة ساعية</b>\n"
        msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n\n"
        msg += "\n\n".join(s for s in sections if s)
        self._send(msg)
        logger.info("📤 [1h] أُرسل التقرير الساعي")

    # ================================================================
    # مراجعة كل 4 ساعات — الكفاءة الكاملة
    # ================================================================
    def _run_4h_review(self, now: datetime.datetime):
        """
        مراجعة عميقة كل 4 ساعات (تتوافق مع شمعة 4H) تشمل:
        - كفاءة نموذج ML (دقة التنبؤات)
        - إحصائيات الاستراتيجية (win rate، avg profit، avg loss)
        - فحص إعدادات إدارة المخاطر
        - مراجعة جميع APIs المدفوعة (CoinGlass + CryptoPanic + Etherscan)
        - مقارنة أداء القطاعات (أي قطاع أعطى أفضل النتائج؟)
        - فحص نظام الفحص الصحي (هل startup_health_check يعمل؟)
        """
        logger.info("🕓 [4h] بدء مراجعة الكفاءة الكاملة...")
        sections = []

        # 1. كفاءة نموذج ML
        ml_section = self._check_ml_performance()
        sections.append(ml_section)

        # 2. إحصائيات الاستراتيجية
        strategy_section = self._check_strategy_stats()
        sections.append(strategy_section)

        # 3. فحص APIs المدفوعة
        paid_apis_section = self._check_paid_apis()
        sections.append(paid_apis_section)

        # 4. إعدادات إدارة المخاطر
        risk_section = self._check_risk_settings()
        sections.append(risk_section)

        # 5. ملخص الأوامر المنفذة
        commands_section = self._check_executed_commands()
        sections.append(commands_section)

        msg = f"🕓 <b>Trade Lak — مراجعة 4 ساعات</b>\n"
        msg += f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n\n"
        msg += "\n\n".join(s for s in sections if s)
        self._send(msg)
        logger.info("📤 [4h] أُرسل تقرير الكفاءة الكاملة")

    # ================================================================
    # مراجعة كل 24 ساعة — التقرير الشامل
    # ================================================================
    def _run_24h_review(self, now: datetime.datetime):
        """
        تقرير شامل يومي يشمل كل شيء:
        - ملخص يوم التداول الكامل
        - أفضل وأسوأ الصفقات
        - تحليل أسباب الخسائر
        - مقارنة الأداء مع الأيام السابقة
        - حالة جميع الأنظمة والمحركات
        - توصيات للتحسين
        """
        logger.info("📅 [24h] بدء التقرير الشامل اليومي...")
        sections = []

        # 1. ملخص اليوم
        daily_summary = self._build_daily_summary()
        sections.append(daily_summary)

        # 2. تحليل الصفقات
        trades_analysis = self._analyze_daily_trades()
        sections.append(trades_analysis)

        # 3. حالة جميع الأنظمة
        systems_health = self._check_all_systems_health()
        sections.append(systems_health)

        # 4. توصيات
        recommendations = self._generate_recommendations()
        sections.append(recommendations)

        msg = f"📅 <b>Trade Lak — التقرير الشامل اليومي</b>\n"
        msg += f"📆 {now.strftime('%Y-%m-%d')}\n\n"
        msg += "\n\n".join(s for s in sections if s)
        self._send(msg)
        logger.info("📤 [24h] أُرسل التقرير الشامل اليومي")

    # ================================================================
    # دوال الفحص الفردية
    # ================================================================

    def _check_open_trades_status(self) -> str:
        """فحص حالة الصفقات المفتوحة وأرباحها"""
        try:
            trades = self.bot.strategy.open_spot_trades
            if not trades:
                return "💼 <b>الصفقات المفتوحة:</b> لا توجد صفقات مفتوحة"

            lines = [f"💼 <b>الصفقات المفتوحة ({len(trades)}):</b>"]
            total_pnl = 0.0

            for sym, trade in trades.items():
                try:
                    ticker = self.bot.okx.get_ticker(sym, 'spot')
                    if ticker:
                        current = ticker['price']
                        entry = trade.get('entry_price', current)
                        pnl_pct = ((current - entry) / entry) * 100
                        total_pnl += pnl_pct
                        icon = "📈" if pnl_pct >= 0 else "📉"
                        sl = trade.get('stop_loss', 0)
                        sl_dist = ((current - sl) / current * 100) if sl else 0
                        lines.append(
                            f"  {icon} {sym.replace('/USDT','')} "
                            f"| P&L: {pnl_pct:+.2f}% "
                            f"| SL بعد: {sl_dist:.2f}%"
                        )
                except:
                    lines.append(f"  ⚪ {sym}: تعذّر جلب السعر")

            avg_pnl = total_pnl / len(trades) if trades else 0
            lines.append(f"\n  📊 متوسط P&L: {avg_pnl:+.2f}%")
            return "\n".join(lines)
        except Exception as e:
            return f"💼 <b>الصفقات:</b> خطأ في الفحص — {e}"

    def _check_api_connections(self) -> str:
        """فحص اتصال APIs الحيوية (كل 30 دقيقة)"""
        results = []
        apis = {
            'OKX':         self._test_okx,
            'CoinGlass':   self._test_coinglass,
            'Telegram':    self._test_telegram,
        }
        all_ok = True
        for name, test_fn in apis.items():
            try:
                ok, detail = test_fn()
                icon = "✅" if ok else "❌"
                if not ok:
                    all_ok = False
                    self._api_errors[name] = self._api_errors.get(name, 0) + 1
                results.append(f"  {icon} {name}: {detail}")
            except Exception as e:
                results.append(f"  ❌ {name}: {e}")
                all_ok = False

        header = "🔌 <b>APIs:</b> " + ("جميعها تعمل ✓" if all_ok else "⚠️ بعضها لا يعمل!")
        return header + "\n" + "\n".join(results)

    def _check_trades_at_risk(self) -> Optional[str]:
        """تنبيه إذا كانت صفقة قريبة من SL"""
        try:
            at_risk = []
            for sym, trade in self.bot.strategy.open_spot_trades.items():
                try:
                    ticker = self.bot.okx.get_ticker(sym, 'spot')
                    if not ticker:
                        continue
                    current = ticker['price']
                    sl = trade.get('stop_loss', 0)
                    if sl and current > 0:
                        sl_dist_pct = ((current - sl) / current) * 100
                        if sl_dist_pct < 0.5:  # أقل من 0.5% من SL
                            at_risk.append(f"🚨 {sym}: السعر {current:.4f} | SL {sl:.4f} | المسافة {sl_dist_pct:.2f}%")
                except:
                    pass
            if at_risk:
                return "🚨 <b>تحذير — صفقات قريبة من SL:</b>\n" + "\n".join(at_risk)
            return None
        except:
            return None

    def _check_smart_engines(self) -> str:
        """فحص أداء المحركات الذكية"""
        lines = ["🧠 <b>المحركات الذكية:</b>"]

        # FakeBreakDetector
        intel = getattr(self.bot, 'intel', None)
        if intel and hasattr(intel, 'fake_break_detector'):
            fbd = intel.fake_break_detector
            signals = getattr(fbd, 'signals_detected', 0)
            lines.append(f"  🎯 FakeBreak: {signals} إشارة مكتشفة")
        else:
            lines.append("  ⚠️ FakeBreak: غير متاح")

        # PostEntryMonitor
        pem = getattr(self.bot, 'post_entry_monitor', None)
        if pem:
            early_exits = getattr(pem, 'early_exits_count', 0)
            lines.append(f"  🛡️ PostEntry: {early_exits} خروج مبكر")
        else:
            lines.append("  ⚠️ PostEntry: غير نشط")

        # ML Model
        if intel and hasattr(intel, 'ml_model'):
            ml = intel.ml_model
            accuracy = getattr(ml, 'last_accuracy', None)
            if accuracy:
                lines.append(f"  🤖 ML Model: دقة {accuracy:.1%}")
            else:
                lines.append("  🤖 ML Model: لم يُدرَّب بعد")
        else:
            lines.append("  ⚠️ ML Model: غير متاح")

        return "\n".join(lines)

    def _check_sector_status(self) -> str:
        """فحص حالة القطاعات"""
        try:
            scanner = getattr(self.bot, 'scanner', None)
            if scanner and hasattr(scanner, 'sector_hunter'):
                hunter = scanner.sector_hunter
                top_sectors = getattr(hunter, 'last_top_sectors', [])
                if top_sectors:
                    lines = ["📊 <b>القطاعات الرائدة:</b>"]
                    for i, (sector, score) in enumerate(top_sectors[:3], 1):
                        medal = ["🥇", "🥈", "🥉"][i-1]
                        lines.append(f"  {medal} {sector}: {score:.1f} نقطة")
                    return "\n".join(lines)
            return "📊 <b>القطاعات:</b> لا بيانات متاحة بعد"
        except Exception as e:
            return f"📊 <b>القطاعات:</b> خطأ — {e}"

    def _check_portfolio_balance(self) -> str:
        """فحص رصيد المحفظة"""
        try:
            bal = self.bot.okx.get_balance()
            free = bal.get('free', 0)
            total = bal.get('total', 0)
            open_count = len(self.bot.strategy.open_spot_trades)

            # حفظ لقطة للمقارنة
            self._trade_snapshots.append({
                'time': datetime.datetime.now(),
                'total': total,
                'free': free,
                'open_trades': open_count,
            })
            # الاحتفاظ بآخر 48 لقطة فقط (48 ساعة)
            if len(self._trade_snapshots) > 48:
                self._trade_snapshots = self._trade_snapshots[-48:]

            # مقارنة مع الساعة السابقة
            change_str = ""
            if len(self._trade_snapshots) >= 2:
                prev = self._trade_snapshots[-2]
                change = total - prev['total']
                change_str = f" ({change:+.2f}$ منذ ساعة)"

            return (
                f"💰 <b>المحفظة:</b>\n"
                f"  رصيد حر: ${free:.2f}\n"
                f"  إجمالي USDT: ${total:.2f}{change_str}\n"
                f"  صفقات مفتوحة: {open_count}"
            )
        except Exception as e:
            return f"💰 <b>المحفظة:</b> خطأ — {e}"

    def _check_dashboard_connection(self) -> str:
        """فحص اتصال Dashboard"""
        try:
            dashboard = getattr(self.bot, 'dashboard', None)
            if not dashboard:
                return "📊 <b>Dashboard:</b> غير مُهيَّأ"

            # اختبار ping
            resp = requests.get(
                f"{dashboard.base_url}/api/bot/health",
                timeout=5
            )
            if resp.status_code == 200:
                return "📊 <b>Dashboard:</b> متصل ✓ — tradelakdash-cmxz8kc9.manus.space"
            else:
                return f"📊 <b>Dashboard:</b> ⚠️ استجابة {resp.status_code}"
        except Exception as e:
            return f"📊 <b>Dashboard:</b> ❌ غير متصل — {e}"

    def _check_ml_performance(self) -> str:
        """فحص كفاءة نموذج ML"""
        try:
            intel = getattr(self.bot, 'intel', None)
            if not intel:
                return "🤖 <b>ML Model:</b> غير متاح"

            lines = ["🤖 <b>كفاءة نموذج ML:</b>"]

            # إحصائيات التدريب
            trainer = getattr(intel, 'ml_trainer', None)
            if trainer:
                history = getattr(trainer, 'trade_history', [])
                lines.append(f"  📚 بيانات تدريب: {len(history)} صفقة")

            # دقة النموذج
            ml = getattr(intel, 'ml_model', None)
            if ml:
                accuracy = getattr(ml, 'last_accuracy', None)
                last_train = getattr(ml, 'last_training_time', None)
                if accuracy:
                    icon = "✅" if accuracy > 0.60 else "⚠️"
                    lines.append(f"  {icon} دقة التنبؤ: {accuracy:.1%} (الحد: 60%)")
                if last_train:
                    lines.append(f"  🕐 آخر تدريب: {last_train}")

            # آخر تشغيل للتدريب
            last_ml = getattr(self.bot, 'last_ml_training', None)
            if last_ml:
                elapsed = (datetime.datetime.now() - last_ml).seconds // 60
                lines.append(f"  ⏱️ منذ آخر تدريب: {elapsed} دقيقة")

            return "\n".join(lines)
        except Exception as e:
            return f"🤖 <b>ML Model:</b> خطأ — {e}"

    def _check_strategy_stats(self) -> str:
        """فحص إحصائيات الاستراتيجية"""
        try:
            total = getattr(self.bot, 'total_trades', 0)
            wins  = getattr(self.bot, 'winning_trades', 0)
            losses = getattr(self.bot, 'losing_trades', 0)
            win_rate = (wins / total * 100) if total > 0 else 0

            icon = "✅" if win_rate >= 55 else ("⚠️" if win_rate >= 40 else "❌")
            return (
                f"📈 <b>إحصائيات الاستراتيجية:</b>\n"
                f"  الصفقات الكلية: {total}\n"
                f"  ناجحة: {wins} ✅ | خاسرة: {losses} ❌\n"
                f"  {icon} نسبة النجاح: {win_rate:.1f}%\n"
                f"  الصفقات المفتوحة: {len(self.bot.strategy.open_spot_trades)}"
            )
        except Exception as e:
            return f"📈 <b>الإحصائيات:</b> خطأ — {e}"

    def _check_paid_apis(self) -> str:
        """فحص جميع APIs المدفوعة"""
        lines = ["💳 <b>APIs المدفوعة:</b>"]
        all_ok = True

        # 1. CoinGlass
        try:
            cg = self.bot.coinglass
            data = cg.get_funding_rate('BTC')
            if data is not None:
                lines.append("  ✅ CoinGlass (eaf8efd7...): يعمل — Funding Rate BTC متاح")
            else:
                lines.append("  ⚠️ CoinGlass: يستجيب لكن البيانات فارغة")
                all_ok = False
        except Exception as e:
            lines.append(f"  ❌ CoinGlass: {str(e)[:50]}")
            all_ok = False

        # 2. OKX API
        try:
            bal = self.bot.okx.spot.fetch_balance()
            usdt = bal.get('total', {}).get('USDT', 0)
            lines.append(f"  ✅ OKX API (f81a3505...): يعمل — رصيد ${usdt:.2f}")
        except Exception as e:
            lines.append(f"  ❌ OKX API: {str(e)[:50]}")
            all_ok = False

        except Exception as e:
            lines.append(f"  ❌ CryptoPanic: {str(e)[:40]}")

        # 4. Etherscan
        try:
            resp = requests.get(
                "https://api.etherscan.io/api?module=stats&action=ethprice&apikey=W994R5JJQQVGX1ZI8KD8ZIFAFZ52RSUMMC",
                timeout=8
            )
            if resp.status_code == 200 and resp.json().get('status') == '1':
                lines.append("  ✅ Etherscan (W994R5JJ...): يعمل")
            else:
                lines.append("  ⚠️ Etherscan: استجابة غير متوقعة")
        except Exception as e:
            lines.append(f"  ❌ Etherscan: {str(e)[:40]}")

        # 5. Dashboard
        try:
            dashboard = getattr(self.bot, 'dashboard', None)
            if dashboard:
                resp = requests.get(f"{dashboard.base_url}/api/bot/health", timeout=5)
                if resp.status_code == 200:
                    lines.append("  ✅ Dashboard (manus.space): متصل")
                else:
                    lines.append(f"  ⚠️ Dashboard: {resp.status_code}")
            else:
                lines.append("  ⚠️ Dashboard: غير مُهيَّأ")
        except Exception as e:
            lines.append(f"  ❌ Dashboard: {str(e)[:40]}")

        return "\n".join(lines)

    def _check_risk_settings(self) -> str:
        """فحص إعدادات إدارة المخاطر"""
        try:
            from config.config import (
                MAX_SPOT_TRADES, MIN_ORDER_USDT, TOTAL_CAPITAL, DRY_RUN
            )
            open_count = len(self.bot.strategy.open_spot_trades)
            utilization = (open_count / MAX_SPOT_TRADES * 100) if MAX_SPOT_TRADES > 0 else 0

            mode_icon = "🧪" if DRY_RUN else "💰"
            util_icon = "✅" if utilization < 80 else "⚠️"

            return (
                f"🛡️ <b>إدارة المخاطر:</b>\n"
                f"  {mode_icon} وضع التداول: {'اختبار' if DRY_RUN else 'حقيقي LIVE'}\n"
                f"  رأس المال: ${TOTAL_CAPITAL}\n"
                f"  الحد الأدنى للصفقة: ${MIN_ORDER_USDT}\n"
                f"  {util_icon} استخدام الحد: {open_count}/{MAX_SPOT_TRADES} ({utilization:.0f}%)"
            )
        except Exception as e:
            return f"🛡️ <b>المخاطر:</b> خطأ — {e}"

    def _check_executed_commands(self) -> str:
        """ملخص الأوامر المنفذة في آخر 4 ساعات"""
        try:
            total = getattr(self.bot, 'total_trades', 0)
            wins  = getattr(self.bot, 'winning_trades', 0)
            losses = getattr(self.bot, 'losing_trades', 0)
            open_count = len(self.bot.strategy.open_spot_trades)

            # أسماء العملات المفتوحة
            open_symbols = [s.replace('/USDT', '') for s in self.bot.strategy.open_spot_trades.keys()]
            symbols_str = ", ".join(open_symbols) if open_symbols else "لا يوجد"

            return (
                f"⚡ <b>ملخص الأوامر:</b>\n"
                f"  صفقات مُنفَّذة (كلي): {total}\n"
                f"  ناجحة: {wins} | خاسرة: {losses}\n"
                f"  مفتوحة الآن: {open_count}\n"
                f"  العملات: {symbols_str}"
            )
        except Exception as e:
            return f"⚡ <b>الأوامر:</b> خطأ — {e}"

    def _build_daily_summary(self) -> str:
        """ملخص اليوم الكامل"""
        try:
            total = getattr(self.bot, 'total_trades', 0)
            wins  = getattr(self.bot, 'winning_trades', 0)
            losses = getattr(self.bot, 'losing_trades', 0)
            win_rate = (wins / total * 100) if total > 0 else 0

            bal = self.bot.okx.get_balance()
            total_bal = bal.get('total', 0)
            free_bal  = bal.get('free', 0)

            return (
                f"📊 <b>ملخص اليوم:</b>\n"
                f"  الصفقات: {total} (✅{wins} / ❌{losses})\n"
                f"  نسبة النجاح: {win_rate:.1f}%\n"
                f"  رصيد USDT: ${total_bal:.2f}\n"
                f"  رصيد حر: ${free_bal:.2f}\n"
                f"  صفقات مفتوحة: {len(self.bot.strategy.open_spot_trades)}"
            )
        except Exception as e:
            return f"📊 <b>الملخص:</b> خطأ — {e}"

    def _analyze_daily_trades(self) -> str:
        """تحليل صفقات اليوم"""
        try:
            trades = self.bot.strategy.open_spot_trades
            if not trades:
                return "📋 <b>تحليل الصفقات:</b> لا توجد صفقات مفتوحة"

            lines = [f"📋 <b>الصفقات المفتوحة ({len(trades)}):</b>"]
            for sym, trade in trades.items():
                entry = trade.get('entry_price', 0)
                sl    = trade.get('stop_loss', 0)
                tp1   = trade.get('tp1', 0)
                open_time = trade.get('open_time', None)
                duration = ""
                if open_time:
                    mins = int((datetime.datetime.now() - open_time).total_seconds() / 60)
                    duration = f" | مدة: {mins}د"
                lines.append(
                    f"  • {sym.replace('/USDT','')}: دخول ${entry:.4f}"
                    f" | SL ${sl:.4f} | TP1 ${tp1:.4f}{duration}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"📋 <b>التحليل:</b> خطأ — {e}"

    def _check_all_systems_health(self) -> str:
        """حالة جميع الأنظمة"""
        systems = {
            "FakeBreakDetector": hasattr(getattr(self.bot, 'intel', None), 'fake_break_detector'),
            "PostEntryMonitor": getattr(self.bot, 'post_entry_monitor', None) is not None,
            "SectorHunter": True,  # تم التحقق منه في startup
            "ML Model": hasattr(getattr(self.bot, 'intel', None), 'ml_model'),
            "Dashboard": getattr(self.bot, 'dashboard', None) is not None,
            "Telegram": getattr(self.bot, 'telegram', None) is not None,
            "HealthCheck": True,  # يعمل لأننا هنا
        }
        lines = ["🏥 <b>حالة الأنظمة:</b>"]
        for name, status in systems.items():
            icon = "✅" if status else "❌"
            lines.append(f"  {icon} {name}")
        return "\n".join(lines)

    def _generate_recommendations(self) -> str:
        """توليد توصيات بناءً على الأداء"""
        recs = []
        try:
            total = getattr(self.bot, 'total_trades', 0)
            wins  = getattr(self.bot, 'winning_trades', 0)
            win_rate = (wins / total) if total > 0 else 0

            if total == 0:
                recs.append("⏳ لم تُنفَّذ أي صفقات اليوم — تحقق من إعدادات الثقة الدنيا")
            elif win_rate < 0.40:
                recs.append("⚠️ نسبة نجاح منخفضة — راجع إعدادات الثقة الدنيا (رفع من 60% إلى 65%)")
            elif win_rate > 0.70:
                recs.append("🎯 أداء ممتاز — يمكن زيادة حجم الصفقات بنسبة 10%")

            open_count = len(self.bot.strategy.open_spot_trades)
            if open_count == 0 and total == 0:
                recs.append("💡 تحقق من أن DRY_RUN=False وأن الرصيد كافٍ")

            if not recs:
                recs.append("✅ الأداء طبيعي — لا توصيات خاصة اليوم")

        except:
            recs.append("⚠️ تعذّر توليد التوصيات")

        return "💡 <b>التوصيات:</b>\n" + "\n".join(f"  {r}" for r in recs)

    # ================================================================
    # اختبارات APIs
    # ================================================================

    def _test_okx(self):
        bal = self.bot.okx.spot.fetch_balance()
        usdt = bal.get('total', {}).get('USDT', 0)
        return True, f"${usdt:.2f} USDT"

    def _test_coinglass(self):
        rate = self.bot.coinglass.get_funding_rate('BTC')
        if rate is not None:
            return True, f"Funding BTC: {rate:.4f}%"
        return False, "بيانات فارغة"

    def _test_cryptopanic(self):
        """فحص اتصال CryptoPanic API"""
        try:
            # المحاولة الأولى: مفتاح API المدفوع
            try:
                from config.config import CRYPTOPANIC_API_KEY
                token = CRYPTOPANIC_API_KEY
            except ImportError:
                token = 'afed90b669cebc6535f88540ecb1679ee551facc'

            resp = requests.get(
                f"https://cryptopanic.com/api/growth/v2/posts/"
                f"?auth_token={token}&public=true&filter=hot&currencies=BTC,ETH",
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get('results', []))
                return True, f"يعمل ✓ ({count} خبر حديثة)"
            elif resp.status_code == 403:
                return False, "مفتاح منتهي أو غير صحيح (403)"
            else:
                return False, f"استجابة غير متوقعة: {resp.status_code}"
        except requests.exceptions.Timeout:
            return False, "انتهى الوقت المحدد (timeout)"
        except Exception as e:
            return False, f"خطأ: {str(e)[:40]}"


    def _test_telegram(self):
        notifier = getattr(self.bot, 'notifier', None)
        if notifier:
            return True, "متاح"
        return False, "غير مُهيَّأ"

    # ================================================================
    # إرسال Telegram
    # ================================================================

    def _send(self, message: str):
        """Log only — Liquidity channel reserved for accumulation alerts only."""
        logger.info(f"[periodic log-only] {str(message)[:150]}")


# ================================================================
# دالة الاستخدام السريع
# ================================================================
def create_periodic_review(bot_instance) -> PeriodicReviewSystem:
    """
    إنشاء نظام المراجعة الدورية.
    
    الاستخدام في main.py:
        from periodic_review import create_periodic_review
        # في __init__:
        self.periodic_review = create_periodic_review(self)
        # في run() داخل while loop:
        self.periodic_review.tick()
    """
    return PeriodicReviewSystem(bot_instance)
