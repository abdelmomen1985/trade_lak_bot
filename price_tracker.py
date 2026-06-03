"""
price_tracker.py
نظام تتبع الأهداف ومراقبة الأسعار في الخلفية
يعمل كـ thread منفصل داخل البوت
"""

import threading
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceTracker:
    """
    يراقب الأسعار كل 60 ثانية ويرسل تنبيهات عند:
    1. تحقيق أي هدف من أهداف الإشارات
    2. ارتفاع السعر >2% قبل الدخول (إلغاء الإشارة)
    3. إرسال التقرير اليومي عند منتصف الليل
    """

    def __init__(self, okx_client, notifier, check_interval: int = 60):
        self.okx = okx_client
        self.notifier = notifier
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._daily_report_sent = {}  # {date_str: True}
        self._trades_today = []  # قائمة صفقات اليوم للتقرير

    def start(self):
        """بدء تشغيل tracker في thread منفصل"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PriceTracker")
        self._thread.start()
        logger.info("✅ PriceTracker started — monitoring signals every 60s")

    def stop(self):
        """إيقاف tracker"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("PriceTracker stopped")

    def add_trade_to_daily(self, trade_data: dict):
        """إضافة صفقة مغلقة لقائمة اليوم"""
        self._trades_today.append(trade_data)

    def _run_loop(self):
        """الحلقة الرئيسية للمراقبة"""
        while self._running:
            try:
                # فحص الإشارات النشطة
                self.notifier.check_signal_targets()

                # فحص التقرير اليومي (عند 23:55 UTC)
                self._check_daily_report()

            except Exception as e:
                logger.error(f"PriceTracker error: {e}")

            time.sleep(self.check_interval)

    def _check_daily_report(self):
        """إرسال التقرير اليومي عند 23:55 UTC"""
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")

        # إرسال التقرير مرة واحدة يومياً عند 23:55
        if now.hour == 23 and now.minute >= 55:
            if date_str not in self._daily_report_sent:
                if self._trades_today:
                    logger.info(f"Sending daily report for {date_str} ({len(self._trades_today)} trades)")
                    self.notifier.send_daily_report(self._trades_today)
                    self._daily_report_sent[date_str] = True
                    self._trades_today = []  # إعادة تعيين قائمة اليوم
                else:
                    # لا توجد صفقات اليوم
                    self._daily_report_sent[date_str] = True
