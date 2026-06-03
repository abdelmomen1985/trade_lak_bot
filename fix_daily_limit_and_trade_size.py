#!/usr/bin/env python3
"""
إصلاح شامل لنظام الحد اليومي وحجم الصفقة:
1. حفظ _daily_capital_used في capital_guard_state.json (يستمر عبر إعادة التشغيل)
2. حجم كل صفقة بين $100 و$170 بدون حد لعدد الصفقات
3. إزالة فحص max_trades (لا حد لعدد الصفقات طالما الرصيد يسمح)
"""

import re

MAIN_PY = '/root/trade_lak_bot/main.py'
CONFIG_PY = '/root/trade_lak_bot/core/config.py'

# ─── قراءة الملفات ───
with open(MAIN_PY, 'r', encoding='utf-8') as f:
    main_content = f.read()

with open(CONFIG_PY, 'r', encoding='utf-8') as f:
    config_content = f.read()

changes = []

# ══════════════════════════════════════════════════════════════════════
# 1. رفع MAX_SPOT_TRADES و MAX_FUTURES_TRADES إلى قيمة كبيرة جداً
#    (بدلاً من حذف الفحص نرفع الحد لـ 999 لضمان عدم التأثير)
# ══════════════════════════════════════════════════════════════════════
old_max_spot = 'MAX_SPOT_TRADES     = 3         # الحد الأقصى لصفقات Spot المفتوحة'
new_max_spot = 'MAX_SPOT_TRADES     = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح'
if old_max_spot in config_content:
    config_content = config_content.replace(old_max_spot, new_max_spot)
    changes.append('✅ MAX_SPOT_TRADES رُفع إلى 999')
else:
    # محاولة بديلة
    config_content = re.sub(
        r'MAX_SPOT_TRADES\s*=\s*\d+.*',
        'MAX_SPOT_TRADES     = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح',
        config_content
    )
    changes.append('✅ MAX_SPOT_TRADES رُفع إلى 999 (regex)')

old_max_futures = 'MAX_FUTURES_TRADES  = 2         # الحد الأقصى لصفقات Futures المفتوحة'
new_max_futures = 'MAX_FUTURES_TRADES  = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح'
if old_max_futures in config_content:
    config_content = config_content.replace(old_max_futures, new_max_futures)
    changes.append('✅ MAX_FUTURES_TRADES رُفع إلى 999')
else:
    config_content = re.sub(
        r'MAX_FUTURES_TRADES\s*=\s*\d+.*',
        'MAX_FUTURES_TRADES  = 999       # لا حد لعدد الصفقات — طالما الرصيد يسمح',
        config_content
    )
    changes.append('✅ MAX_FUTURES_TRADES رُفع إلى 999 (regex)')

# ══════════════════════════════════════════════════════════════════════
# 2. تعديل TRADE_MIN_USDT من $50 إلى $100 في main.py (3 مواضع)
#    وTRADE_MAX_USDT يبقى $170
# ══════════════════════════════════════════════════════════════════════
# الموضع 1 (حول سطر 1201)
old_min_1 = "            TRADE_MIN_USDT = 50.0    # الحد الأدنى لكل صفقة (مُعدَّل)"
new_min_1 = "            TRADE_MIN_USDT = 100.0   # الحد الأدنى لكل صفقة $100"
if old_min_1 in main_content:
    main_content = main_content.replace(old_min_1, new_min_1)
    changes.append('✅ TRADE_MIN_USDT موضع 1 → $100')

# الموضع 2 (حول سطر 1583)
old_min_2 = "            TRADE_MIN_USDT = 50.0\n            TRADE_MAX_USDT = 170.0\n            total_trade_usdt = TRADE_MAX_USDT\n"
new_min_2 = "            TRADE_MIN_USDT = 100.0   # الحد الأدنى $100\n            TRADE_MAX_USDT = 170.0   # الحد الأقصى $170\n            total_trade_usdt = TRADE_MAX_USDT\n"
if old_min_2 in main_content:
    main_content = main_content.replace(old_min_2, new_min_2)
    changes.append('✅ TRADE_MIN_USDT موضع 2 → $100')

# الموضع 3 (حول سطر 1802)
old_min_3 = "            TRADE_MIN_USDT = 50.0\n            TRADE_MAX_USDT = 170.0\n            total_trade_usdt = TRADE_MAX_USDT\n"
# هذا نفس النص — سيُعالج بـ replace all
main_content = main_content.replace(
    "            TRADE_MIN_USDT = 50.0\n",
    "            TRADE_MIN_USDT = 100.0   # الحد الأدنى $100\n"
)
changes.append('✅ جميع مواضع TRADE_MIN_USDT = 50.0 → 100.0')

# ══════════════════════════════════════════════════════════════════════
# 3. تعديل الحد الأدنى للرصيد من 50 إلى 100 في فحوصات الرصيد
# ══════════════════════════════════════════════════════════════════════
# فحص الرصيد عند الدخول التدريجي
old_avail_check = "            if avail < 50.0:\n                logger.warning(f\"⚠️ رصيد غير كافٍ للدخول التدريجي: ${avail:.2f} < ${TRADE_MIN_USDT}\")\n                return"
new_avail_check = "            if avail < 100.0:\n                logger.warning(f\"⚠️ رصيد غير كافٍ للدخول التدريجي: ${avail:.2f} < ${TRADE_MIN_USDT}\")\n                return"
if old_avail_check in main_content:
    main_content = main_content.replace(old_avail_check, new_avail_check)
    changes.append('✅ فحص الرصيد الأدنى → $100')

# ══════════════════════════════════════════════════════════════════════
# 4. تعديل الحجم الكلي في DCA: كان $300-$350، الآن $100-$170
#    total_trade_usdt = TRADE_MAX_USDT = $170 (بدون تغيير)
#    لكن نضمن أن الحجم المُخفَّض لا يقل عن $100
# ══════════════════════════════════════════════════════════════════════
old_lga_size = "                total_trade_usdt = max(TRADE_MIN_USDT * _lga_size_multiplier, 30.0)"
new_lga_size = "                total_trade_usdt = max(TRADE_MIN_USDT * _lga_size_multiplier, 100.0)"
if old_lga_size in main_content:
    main_content = main_content.replace(old_lga_size, new_lga_size)
    changes.append('✅ الحجم المُخفَّض لا يقل عن $100')

# تعديل الحجم عند الرصيد المنخفض
old_avail_adj = "                total_trade_usdt = max(avail * 0.95, 50.0)"
new_avail_adj = "                total_trade_usdt = max(avail * 0.95, 100.0)"
if old_avail_adj in main_content:
    main_content = main_content.replace(old_avail_adj, new_avail_adj)
    changes.append('✅ تعديل الحجم عند الرصيد المنخفض → $100 حد أدنى')

# ══════════════════════════════════════════════════════════════════════
# 5. إضافة حفظ/تحميل _daily_capital_used من capital_guard_state.json
#    نضيف دالة مساعدة في __init__ وفي الحلقة الرئيسية
# ══════════════════════════════════════════════════════════════════════

# أ) تعديل كود إعادة الضبط اليومي (سطر 1146) لحفظ الحالة في الملف
old_daily_reset_block = """            _daily_used = getattr(self, '_daily_capital_used', 0.0)
            _daily_reset = getattr(self, '_daily_reset_time', 0.0)
            if _time_module.time() - _daily_reset > 86400:
                self._daily_capital_used = 0.0
                self._daily_reset_time = _time_module.time()
                _daily_used = 0.0
            _DAILY_LIMIT = 170.0
            if _daily_used >= _DAILY_LIMIT:
                logger.warning(f"⛔ حد رأس المال اليومي: ${_daily_used:.2f}/${_DAILY_LIMIT} — لا صفقات جديدة")
                return"""

new_daily_reset_block = """            # ── تحميل العداد اليومي من الملف (يستمر عبر إعادة التشغيل) ──
            _cg_path = os.path.join(os.path.dirname(__file__), 'data', 'capital_guard_state.json')
            try:
                import json as _json_mod
                with open(_cg_path, 'r') as _f:
                    _cg_state = _json_mod.load(_f)
                _saved_daily = float(_cg_state.get('daily_capital_used', 0.0))
                _saved_reset = float(_cg_state.get('daily_reset_time', 0.0))
                # إذا كانت القيمة المحفوظة أحدث من الذاكرة → استخدمها
                if _saved_reset > getattr(self, '_daily_reset_time', 0.0):
                    self._daily_capital_used = _saved_daily
                    self._daily_reset_time = _saved_reset
            except Exception:
                pass
            _daily_used = getattr(self, '_daily_capital_used', 0.0)
            _daily_reset = getattr(self, '_daily_reset_time', 0.0)
            if _time_module.time() - _daily_reset > 86400:
                self._daily_capital_used = 0.0
                self._daily_reset_time = _time_module.time()
                _daily_used = 0.0
                # حفظ التصفير في الملف
                try:
                    import json as _json_mod
                    with open(_cg_path, 'r') as _f:
                        _cg_state = _json_mod.load(_f)
                    _cg_state['daily_capital_used'] = 0.0
                    _cg_state['daily_reset_time'] = self._daily_reset_time
                    with open(_cg_path, 'w') as _f:
                        _json_mod.dump(_cg_state, _f, indent=2)
                    logger.info("🔄 [DailyLimit] تم تصفير العداد اليومي وحفظه في الملف")
                except Exception as _e:
                    logger.warning(f"⚠️ [DailyLimit] فشل حفظ التصفير: {_e}")
            _DAILY_LIMIT = 170.0
            if _daily_used >= _DAILY_LIMIT:
                logger.warning(f"⛔ حد رأس المال اليومي: ${_daily_used:.2f}/${_DAILY_LIMIT} — لا صفقات جديدة")
                return"""

if old_daily_reset_block in main_content:
    main_content = main_content.replace(old_daily_reset_block, new_daily_reset_block)
    changes.append('✅ إضافة تحميل/حفظ العداد اليومي من الملف')
else:
    changes.append('⚠️ لم يُعثر على كتلة إعادة الضبط اليومي — يحتاج فحص يدوي')

# ب) تعديل مواضع تحديث العداد لتحفظ في الملف أيضاً
# موضع 1 (سطر 533) — بعد فتح صفقة spot
old_update_1 = """                self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice1_usdt
                logger.info(f"💰 [DailyLimit] إجمالي اليوم بعد الصفقة: ${self._daily_capital_used:.2f}/170.0")"""
new_update_1 = """                self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice1_usdt
                logger.info(f"💰 [DailyLimit] إجمالي اليوم بعد الصفقة: ${self._daily_capital_used:.2f}/170.0")
                # حفظ العداد في الملف
                try:
                    import json as _json_cg, os as _os_cg
                    _cg_p = _os_cg.path.join(_os_cg.path.dirname(__file__), 'data', 'capital_guard_state.json')
                    with open(_cg_p, 'r') as _ff: _cg_s = _json_cg.load(_ff)
                    _cg_s['daily_capital_used'] = self._daily_capital_used
                    _cg_s['daily_reset_time'] = getattr(self, '_daily_reset_time', 0.0)
                    with open(_cg_p, 'w') as _ff: _json_cg.dump(_cg_s, _ff, indent=2)
                except Exception: pass"""
if old_update_1 in main_content:
    main_content = main_content.replace(old_update_1, new_update_1)
    changes.append('✅ حفظ العداد بعد فتح صفقة (موضع 1)')

# موضع 2 (سطر 1264) — بعد شريحة DCA الأولى
old_update_2 = """                self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice1_usdt
                logger.info(f"💰 [DailyLimit] إجمالي اليوم: ${self._daily_capital_used:.2f}/170.0")"""
new_update_2 = """                self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice1_usdt
                logger.info(f"💰 [DailyLimit] إجمالي اليوم: ${self._daily_capital_used:.2f}/170.0")
                # حفظ العداد في الملف
                try:
                    import json as _json_cg, os as _os_cg
                    _cg_p = _os_cg.path.join(_os_cg.path.dirname(__file__), 'data', 'capital_guard_state.json')
                    with open(_cg_p, 'r') as _ff: _cg_s = _json_cg.load(_ff)
                    _cg_s['daily_capital_used'] = self._daily_capital_used
                    _cg_s['daily_reset_time'] = getattr(self, '_daily_reset_time', 0.0)
                    with open(_cg_p, 'w') as _ff: _json_cg.dump(_cg_s, _ff, indent=2)
                except Exception: pass"""
if old_update_2 in main_content:
    main_content = main_content.replace(old_update_2, new_update_2)
    changes.append('✅ حفظ العداد بعد شريحة DCA الأولى (موضع 2)')

# موضع 3 (سطر 2868) — بعد شرائح DCA الإضافية
old_update_3 = """                            self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice_usdt
                            logger.info(
                                f"✅ [DCA] شريحة نُفِّذت: {symbol} | "
                                f"${slice_usdt:.2f} @ ${current_price:.4f} | "
                                f"متوسط الدخول: ${avg_entry:.4f} | "
                                f"إجمالي اليوم: ${self._daily_capital_used:.2f}/170.0"
                            )"""
new_update_3 = """                            self._daily_capital_used = getattr(self, '_daily_capital_used', 0.0) + slice_usdt
                            logger.info(
                                f"✅ [DCA] شريحة نُفِّذت: {symbol} | "
                                f"${slice_usdt:.2f} @ ${current_price:.4f} | "
                                f"متوسط الدخول: ${avg_entry:.4f} | "
                                f"إجمالي اليوم: ${self._daily_capital_used:.2f}/170.0"
                            )
                            # حفظ العداد في الملف
                            try:
                                import json as _json_cg, os as _os_cg
                                _cg_p = _os_cg.path.join(_os_cg.path.dirname(__file__), 'data', 'capital_guard_state.json')
                                with open(_cg_p, 'r') as _ff: _cg_s = _json_cg.load(_ff)
                                _cg_s['daily_capital_used'] = self._daily_capital_used
                                _cg_s['daily_reset_time'] = getattr(self, '_daily_reset_time', 0.0)
                                with open(_cg_p, 'w') as _ff: _json_cg.dump(_cg_s, _ff, indent=2)
                            except Exception: pass"""
if old_update_3 in main_content:
    main_content = main_content.replace(old_update_3, new_update_3)
    changes.append('✅ حفظ العداد بعد شرائح DCA الإضافية (موضع 3)')

# ══════════════════════════════════════════════════════════════════════
# 6. إضافة daily_capital_used إلى capital_guard_state.json إذا لم يكن موجوداً
# ══════════════════════════════════════════════════════════════════════
import json, os, time

cg_path = '/root/trade_lak_bot/data/capital_guard_state.json'
# سيتم تنفيذ هذا مباشرة على السيرفر عبر سكريبت منفصل

# ══════════════════════════════════════════════════════════════════════
# حفظ الملفات المُعدَّلة
# ══════════════════════════════════════════════════════════════════════
with open(MAIN_PY, 'w', encoding='utf-8') as f:
    f.write(main_content)

with open(CONFIG_PY, 'w', encoding='utf-8') as f:
    f.write(config_content)

print("=" * 60)
print("تقرير التغييرات:")
for c in changes:
    print(c)
print("=" * 60)
print(f"إجمالي التغييرات: {len(changes)}")

# تحديث capital_guard_state.json لإضافة الحقول الجديدة
import json, time as _time
try:
    with open(cg_path, 'r') as f:
        cg_state = json.load(f)
    if 'daily_capital_used' not in cg_state:
        cg_state['daily_capital_used'] = 0.0
    if 'daily_reset_time' not in cg_state:
        cg_state['daily_reset_time'] = _time.time()
    with open(cg_path, 'w') as f:
        json.dump(cg_state, f, indent=2)
    print("✅ capital_guard_state.json مُحدَّث بالحقول الجديدة")
except Exception as e:
    print(f"⚠️ خطأ في تحديث capital_guard_state.json: {e}")
