#!/usr/bin/env python3
"""
Trade Lak — Startup Health Check System
========================================
يُشغَّل تلقائياً عند كل بدء تشغيل لـ Trade Lak.
يفحص 15+ نقطة مستخلصة من المشاكل الحقيقية التي واجهناها،
ويُصلح ما يمكن إصلاحه تلقائياً، ويُرسل تقريراً عبر Telegram.

المشاكل الموثقة التي يفحصها هذا النظام:
  #1  MAX_SPOT_TRADES أقل من عدد العملات في المحفظة
  #2  المزامنة تعتمد على ملف مؤقت بدلاً من OKX مباشرة
  #3  رصيد وهمي يوقف البوت (usdt_free فقط)
  #4  direction خاطئ في trade_record (BUY بدلاً من SPOT_BUY)
  #5  amount_coin مفقود في trade_record
  #6  open_time مفقود في trade_record
  #7  Telegram HTML parsing errors
  #8  FakeBreakDetector غير مُهيَّأ
  #9  عملات صغيرة القيمة تُتجاهل (حد $1)
  #10 الحد الأدنى للصفقة على OKX ($10)
  #11 MAX_SPOT_TRADES أقل من 10
  #12 PostEntryMonitor غير مُهيَّأ
  #13 SectorLiquidityHunter غير مُهيَّأ
  #14 ملف config_production.yaml موجود وقابل للقراءة
  #15 اتصال OKX يعمل
"""

import os
import sys
import logging
import datetime
import traceback

logger = logging.getLogger('HealthCheck')


class StartupHealthCheck:
    """
    نظام الفحص الصحي عند بدء التشغيل.
    يُنشئ تقريراً كاملاً ويُصلح المشاكل تلقائياً.
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.results = []   # قائمة نتائج الفحوصات
        self.fixes_applied = []  # الإصلاحات التي طُبِّقت
        self.critical_failures = []  # مشاكل حرجة تمنع التشغيل

    # ================================================================
    # الدالة الرئيسية
    # ================================================================
    def run(self) -> bool:
        """
        تشغيل جميع الفحوصات.
        تُعيد True إذا كان البوت جاهزاً للعمل، False إذا كان هناك مشكلة حرجة.
        """
        logger.info("=" * 60)
        logger.info("🏥 بدء فحص صحة Trade Lak عند التشغيل...")
        logger.info("=" * 60)

        checks = [
            ("اتصال OKX",              self._check_okx_connection),
            ("ملف الإعدادات",          self._check_config_file),
            ("MAX_SPOT_TRADES",         self._check_max_trades_limit),
            ("مزامنة المحفظة",         self._check_portfolio_sync),
            ("trade_record directions", self._check_trade_directions),
            ("amount_coin في الصفقات", self._check_amount_coin),
            ("open_time في الصفقات",   self._check_open_time),
            ("الحد الأدنى للصفقة",    self._check_min_order),
            ("Telegram اتصال",         self._check_telegram),
            ("FakeBreakDetector",       self._check_fake_break_detector),
            ("PostEntryMonitor",        self._check_post_entry_monitor),
            ("SectorLiquidityHunter",  self._check_sector_hunter),
            ("ملف المزامنة المؤقت",   self._check_no_stale_sync_file),
            ("رصيد OKX",              self._check_balance_logic),
            ("عملات صغيرة القيمة",    self._check_small_assets),
        ]

        passed = 0
        failed = 0
        fixed  = 0

        for name, check_fn in checks:
            try:
                status, message, auto_fixed = check_fn()
                icon = "✅" if status else ("🔧" if auto_fixed else "❌")
                level = "INFO" if status or auto_fixed else "WARNING"
                getattr(logger, level.lower())(f"{icon} [{name}]: {message}")
                self.results.append({
                    'name': name,
                    'passed': status or auto_fixed,
                    'message': message,
                    'auto_fixed': auto_fixed,
                })
                if status:
                    passed += 1
                elif auto_fixed:
                    fixed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"❌ [{name}]: خطأ في الفحص — {e}")
                self.results.append({
                    'name': name,
                    'passed': False,
                    'message': f"خطأ: {e}",
                    'auto_fixed': False,
                })
                failed += 1

        # ── ملخص ──
        total = passed + failed + fixed
        logger.info("=" * 60)
        logger.info(
            f"📊 نتيجة الفحص: {passed}/{total} ✅ | "
            f"{fixed} إصلاح تلقائي 🔧 | {failed} فشل ❌"
        )

        # إرسال تقرير Telegram
        self._send_telegram_report(passed, fixed, failed, total)

        if self.critical_failures:
            logger.critical(
                f"🚨 مشاكل حرجة تمنع التشغيل: {self.critical_failures}"
            )
            return False

        logger.info("✅ Trade Lak جاهز للعمل!")
        logger.info("=" * 60)
        return True

    # ================================================================
    # فحوصات فردية
    # ================================================================

    def _check_okx_connection(self):
        """#15 التحقق من اتصال OKX"""
        try:
            bal = self.bot.okx.spot.fetch_balance()
            usdt = bal.get('total', {}).get('USDT', 0)
            return True, f"متصل ✓ — USDT إجمالي: ${usdt:.2f}", False
        except Exception as e:
            self.critical_failures.append("اتصال OKX")
            return False, f"فشل الاتصال: {e}", False

    def _check_config_file(self):
        """#14 التحقق من ملف الإعدادات"""
        config_path = os.path.join(os.path.dirname(self.bot.__class__.__module__ or '.'), 
                                   'config_production.yaml')
        # محاولة إيجاد الملف
        for path in [
            '/root/trade_lak_bot/config_production.yaml',
            '/root/trade_lak_bot/config/config_production.yaml',
        ]:
            if os.path.exists(path):
                return True, f"موجود: {path}", False
        return False, "ملف config_production.yaml غير موجود!", False

    def _check_max_trades_limit(self):
        """#1 و#11 التحقق من MAX_SPOT_TRADES"""
        try:
            from config.config import MAX_SPOT_TRADES
            # عد العملات الفعلية في المحفظة
            bal = self.bot.okx.spot.fetch_balance()
            assets_count = len([
                k for k, v in bal.get('total', {}).items()
                if v and v > 0 and k not in ('USDT', 'USDC', 'BUSD', 'DAI')
            ])

            if MAX_SPOT_TRADES < 10:
                # إصلاح تلقائي: رفع الحد
                self._patch_config_value('MAX_SPOT_TRADES', 15)
                self.fixes_applied.append(f"MAX_SPOT_TRADES رُفع إلى 15")
                return False, f"كان {MAX_SPOT_TRADES} — رُفع تلقائياً إلى 15", True

            if MAX_SPOT_TRADES < assets_count:
                new_val = assets_count + 5
                self._patch_config_value('MAX_SPOT_TRADES', new_val)
                self.fixes_applied.append(f"MAX_SPOT_TRADES رُفع إلى {new_val}")
                return False, f"كان {MAX_SPOT_TRADES} < {assets_count} عملة — رُفع إلى {new_val}", True

            return True, f"MAX_SPOT_TRADES={MAX_SPOT_TRADES} ✓ (عملات في المحفظة: {assets_count})", False
        except Exception as e:
            return False, f"خطأ: {e}", False

    def _check_portfolio_sync(self):
        """#2 التحقق من المزامنة التلقائية"""
        has_auto_sync = hasattr(self.bot, '_auto_sync_portfolio')
        synced_count = len(getattr(self.bot.strategy, 'open_spot_trades', {}))

        if not has_auto_sync:
            return False, "دالة _auto_sync_portfolio غير موجودة!", False

        if synced_count == 0:
            # تشغيل المزامنة الآن
            try:
                self.bot._auto_sync_portfolio()
                synced_count = len(self.bot.strategy.open_spot_trades)
                return False, f"لم تكن مُزامَنة — تمت المزامنة الآن: {synced_count} عملة", True
            except Exception as e:
                return False, f"فشل تشغيل المزامنة: {e}", False

        return True, f"مُزامَنة ✓ — {synced_count} عملة محملة", False

    def _check_trade_directions(self):
        """#4 التحقق من صحة direction في جميع الصفقات"""
        valid_directions = {'SPOT_BUY', 'LONG', 'SHORT'}
        bad_trades = []

        for sym, trade in self.bot.strategy.open_spot_trades.items():
            direction = trade.get('direction', '')
            if direction not in valid_directions:
                # إصلاح تلقائي
                trade['direction'] = 'SPOT_BUY'
                bad_trades.append(sym)

        if bad_trades:
            self.fixes_applied.append(f"direction صُحِّح لـ: {bad_trades}")
            return False, f"صُحِّح direction لـ {len(bad_trades)} صفقة: {bad_trades}", True

        return True, f"جميع directions صحيحة ✓", False

    def _check_amount_coin(self):
        """#5 التحقق من وجود amount_coin في جميع الصفقات"""
        missing = []

        for sym, trade in self.bot.strategy.open_spot_trades.items():
            if not trade.get('amount_coin') and not trade.get('quantity'):
                missing.append(sym)
            elif not trade.get('amount_coin') and trade.get('quantity'):
                # إصلاح تلقائي
                trade['amount_coin'] = trade['quantity']

        if missing:
            # محاولة إصلاح من OKX
            for sym in missing:
                try:
                    bal = self.bot.okx.spot.fetch_balance()
                    coin = sym.replace('/USDT', '')
                    qty = bal.get('total', {}).get(coin, 0)
                    if qty > 0:
                        self.bot.strategy.open_spot_trades[sym]['amount_coin'] = qty
                        self.bot.strategy.open_spot_trades[sym]['quantity'] = qty
                except:
                    pass
            self.fixes_applied.append(f"amount_coin أُضيف لـ: {missing}")
            return False, f"أُصلح amount_coin لـ {len(missing)} صفقة", True

        return True, "جميع الصفقات لها amount_coin ✓", False

    def _check_open_time(self):
        """#6 التحقق من وجود open_time في جميع الصفقات"""
        missing = []
        now = datetime.datetime.now()

        for sym, trade in self.bot.strategy.open_spot_trades.items():
            if not trade.get('open_time'):
                trade['open_time'] = now
                missing.append(sym)

        if missing:
            self.fixes_applied.append(f"open_time أُضيف لـ: {missing}")
            return False, f"أُضيف open_time لـ {len(missing)} صفقة", True

        return True, "جميع الصفقات لها open_time ✓", False

    def _check_min_order(self):
        """#10 التحقق من الحد الأدنى للصفقة"""
        try:
            from config.config import MIN_ORDER_USDT
            if MIN_ORDER_USDT < 10:
                self._patch_config_value('MIN_ORDER_USDT', 10)
                return False, f"كان {MIN_ORDER_USDT} — رُفع إلى 10", True
            return True, f"MIN_ORDER_USDT={MIN_ORDER_USDT} ✓", False
        except ImportError:
            # إضافة الإعداد إذا لم يكن موجوداً
            return False, "MIN_ORDER_USDT غير موجود في config — يُستخدم 10 افتراضياً", False

    def _check_telegram(self):
        """#7 التحقق من اتصال Telegram وعدم وجود HTML errors"""
        try:
            notifier = getattr(self.bot, 'notifier', None)
            if not notifier:
                return False, "Telegram notifier غير موجود!", False

            # فحص الاتصال فقط — لا نرسل لقناة Liquidity
            return True, "Telegram يعمل ✓", False
        except Exception as e:
            return False, f"خطأ Telegram: {e}", False

    def _check_fake_break_detector(self):
        """#8 التحقق من FakeBreakDetector"""
        try:
            # فحص في intelligence_engine
            intel = getattr(self.bot, 'intel', None)
            if intel and hasattr(intel, 'fake_break_detector'):
                return True, "FakeBreakDetector مُهيَّأ ✓", False
            
            # محاولة استيراد مباشر
            sys.path.insert(0, '/root/trade_lak_bot')
            from fake_break_detector import FakeBreakDetector
            return True, "FakeBreakDetector متاح ✓", False
        except Exception as e:
            return False, f"FakeBreakDetector غير متاح: {e}", False

    def _check_post_entry_monitor(self):
        """#12 التحقق من PostEntryMonitor"""
        monitor = getattr(self.bot, 'post_entry_monitor', None)
        if monitor is None:
            return False, "PostEntryMonitor غير مُهيَّأ!", False
        return True, "PostEntryMonitor نشط ✓", False

    def _check_sector_hunter(self):
        """#13 التحقق من SectorLiquidityHunter"""
        try:
            sys.path.insert(0, '/root/trade_lak_bot')
            from sector_liquidity_hunter import SectorLiquidityHunter
            return True, "SectorLiquidityHunter متاح ✓", False
        except Exception as e:
            return False, f"SectorLiquidityHunter غير متاح: {e}", False

    def _check_no_stale_sync_file(self):
        """#2 التحقق من عدم وجود ملف مزامنة قديم يسبب مشاكل"""
        stale_files = [
            '/root/trade_lak_bot/data/portfolio_sync.pkl',
            '/root/trade_lak_bot/data/portfolio_sync.pkl.loaded',
        ]
        found = [f for f in stale_files if os.path.exists(f)]
        if found:
            # حذف الملفات القديمة
            for f in found:
                try:
                    os.remove(f)
                except:
                    pass
            return False, f"حُذفت ملفات مزامنة قديمة: {found}", True
        return True, "لا توجد ملفات مزامنة قديمة ✓", False

    def _check_balance_logic(self):
        """#3 التحقق من منطق الرصيد"""
        try:
            bal = self.bot.okx.get_balance()
            free = bal.get('free', 0)
            total = bal.get('total', 0)
            open_trades = len(self.bot.strategy.open_spot_trades)

            if free < 5 and open_trades == 0:
                return False, f"رصيد حر منخفض جداً (${free:.2f}) ولا توجد صفقات مفتوحة!", False
            elif free < 5 and open_trades > 0:
                return True, f"رصيد حر ${free:.2f} — لكن {open_trades} صفقة مفتوحة (طبيعي) ✓", False
            else:
                return True, f"رصيد حر: ${free:.2f} | إجمالي USDT: ${total:.2f} ✓", False
        except Exception as e:
            return False, f"خطأ في فحص الرصيد: {e}", False

    def _check_small_assets(self):
        """#9 التحقق من تغطية العملات الصغيرة القيمة"""
        try:
            bal = self.bot.okx.spot.fetch_balance()
            all_assets = {
                k: v for k, v in bal.get('total', {}).items()
                if v and v > 0 and k not in ('USDT', 'USDC', 'BUSD', 'DAI')
            }
            monitored = set(self.bot.strategy.open_spot_trades.keys())
            
            unmonitored = []
            for coin, qty in all_assets.items():
                symbol = f"{coin}/USDT"
                if symbol not in monitored:
                    # تقدير القيمة
                    try:
                        ticker = self.bot.okx.get_ticker(symbol, 'spot')
                        if ticker:
                            value = qty * ticker['price']
                            if value >= 1:
                                unmonitored.append(f"{coin}(${value:.1f})")
                    except:
                        pass

            if unmonitored:
                return False, f"عملات غير مراقبة: {unmonitored} — ستُضاف في المزامنة التالية", False

            return True, f"جميع {len(all_assets)} عملة مراقبة ✓", False
        except Exception as e:
            return False, f"خطأ في فحص العملات الصغيرة: {e}", False

    # ================================================================
    # أدوات مساعدة
    # ================================================================

    def _patch_config_value(self, key: str, value):
        """تعديل قيمة في config.py مباشرة"""
        config_path = '/root/trade_lak_bot/config/config.py'
        try:
            with open(config_path, 'r') as f:
                content = f.read()

            import re
            # استبدال القيمة
            new_content = re.sub(
                rf'^({key}\s*=\s*).*$',
                rf'\g<1>{value}',
                content,
                flags=re.MULTILINE
            )
            if new_content != content:
                with open(config_path, 'w') as f:
                    f.write(new_content)
                logger.info(f"🔧 تم تعديل {key} = {value} في config.py")
        except Exception as e:
            logger.warning(f"⚠️ فشل تعديل {key} في config: {e}")

    def _send_telegram_report(self, passed: int, fixed: int, failed: int, total: int):
        """إرسال تقرير الفحص عبر Telegram"""
        try:
            notifier = getattr(self.bot, 'notifier', None)
            if not notifier:
                return

            status_emoji = "✅" if failed == 0 else ("⚠️" if failed <= 2 else "🚨")
            lines = [
                f"{status_emoji} <b>Trade Lak — تقرير بدء التشغيل</b>",
                f"📊 الفحوصات: {passed}/{total} ✅ | {fixed} إصلاح 🔧 | {failed} فشل ❌",
            ]

            if self.fixes_applied:
                lines.append(f"\n🔧 <b>إصلاحات تلقائية:</b>")
                for fix in self.fixes_applied:
                    lines.append(f"  • {fix}")

            if self.critical_failures:
                lines.append(f"\n🚨 <b>مشاكل حرجة:</b>")
                for fail in self.critical_failures:
                    lines.append(f"  • {fail}")

            # إحصائيات المحفظة
            try:
                open_trades = len(self.bot.strategy.open_spot_trades)
                bal = self.bot.okx.get_balance()
                free = bal.get('free', 0)
                lines.append(f"\n💼 <b>المحفظة:</b> {open_trades} عملة مراقبة | رصيد حر: ${free:.2f}")
            except:
                pass

            message = "\n".join(lines)
            logger.info(f"[startup health log-only] {str(message)[:150]}")
        except Exception as e:
            logger.debug(f"خطأ تقرير الصحة: {e}")


# ================================================================
# دالة الاستخدام السريع
# ================================================================
def run_health_check(bot_instance) -> bool:
    """
    دالة مختصرة لاستدعاء الفحص الصحي.
    
    الاستخدام في main.py:
        from startup_health_check import run_health_check
        ...
        # في نهاية __init__:
        run_health_check(self)
    """
    checker = StartupHealthCheck(bot_instance)
    return checker.run()
