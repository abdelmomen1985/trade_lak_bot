# 🔐 API Keys Setup Guide

**دليل الحصول على مفاتيح API المطلوبة**

---

## 1️⃣ OKX API Keys (مطلوب)

### الخطوات:

1. اذهب إلى: https://www.okx.com
2. سجل الدخول بحسابك
3. اضغط على **صورتك** (أعلى اليمين)
4. اختر **Account Settings** أو **إعدادات الحساب**
5. اختر **API Management** أو **إدارة API**
6. اضغط **Create API Key** أو **إنشاء مفتاح API**

### إعدادات المفتاح:

```
API Key Name: Trade Lak Bot
Passphrase: MyBot@2024 (اختر كلمة قوية)
IP Whitelist: (اتركها فارغة أو أضف IP السيرفر)
```

### الصلاحيات المطلوبة:

```
✅ Trade (التداول)
✅ Read (القراءة)
❌ Withdraw (لا تفعّل هذا!)
```

### البيانات التي ستحصل عليها:

```
API Key: abcd1234efgh5678ijkl9012mnop3456
Secret Key: xyz9876wvu5432tsr4321qpon9876mlk
Passphrase: MyBot@2024
```

---

## 2️⃣ Telegram Bot Token (اختياري لكن مهم)

### الخطوات:

1. افتح تليجرام
2. ابحث عن: `@BotFather`
3. اكتب: `/newbot`
4. اختر اسم البوت: `Trade Lak Bot`
5. اختر username: `trade_lak_bot_username`
6. احصل على الـ Token

### البيانات التي ستحصل عليها:

```
Bot Token: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh
Bot Username: @trade_lak_bot_username
Bot Link: https://t.me/trade_lak_bot_username
```

### الحصول على Chat ID:

1. أرسل أي رسالة للبوت
2. اذهب إلى: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. استبدل `<YOUR_TOKEN>` بـ Token الحقيقي
4. ابحث عن `"chat":{"id":123456789}`
5. الرقم هو Chat ID

---

## 3️⃣ CoinGlass API Key (اختياري)

### الخطوات:

1. اذهب إلى: https://www.coinglass.com/api
2. اضغط **Sign Up** أو **تسجيل**
3. أنشئ حساب مجاني
4. اذهب إلى **API Keys**
5. اضغط **Create API Key**
6. احصل على الـ Key

### البيانات التي ستحصل عليها:

```
API Key: your_coinglass_api_key_here
```

---

## 4️⃣ Contabo SSH Credentials (للسيرفر)

### الخطوات:

1. اذهب إلى: https://my.contabo.com
2. سجل الدخول
3. اختر السيرفر الخاص بك
4. ستجد:

```
IP Address: 123.45.67.89
SSH Port: 22 (عادة)
Root Password: (في البريد أو في اللوحة)
```

---

## 📝 ملخص البيانات المطلوبة

```
=== OKX ===
API Key: ___________________________
Secret Key: ___________________________
Passphrase: ___________________________

=== Telegram ===
Bot Token: ___________________________
Chat ID: ___________________________

=== CoinGlass ===
API Key: ___________________________

=== Contabo ===
IP Address: ___________________________
SSH Port: ___________________________
Root Password: ___________________________
```

---

## ⚠️ تحذيرات أمان

### لا تفعل هذا:

❌ لا تشارك API Keys مع أحد
❌ لا تضع API Keys في ملفات عامة
❌ لا تفعّل صلاحية Withdraw في OKX
❌ لا تستخدم كلمات مرور ضعيفة
❌ لا تحفظ البيانات في ملفات نصية عادية

### افعل هذا:

✅ استخدم كلمات مرور قوية
✅ احفظ البيانات في مكان آمن
✅ استخدم 2FA (Two-Factor Authentication)
✅ راجع صلاحيات API بانتظام
✅ غيّر كلمات المرور بانتظام

---

## 🔄 تحديث API Keys

### إذا احتجت لتغيير API Keys:

1. عدّل `config/config.py`
2. أعد تشغيل البوت
3. تحقق من السجلات

---

## 🆘 استكشاف الأخطاء

### خطأ: "Invalid API Key"

- تحقق من نسخ البيانات بشكل صحيح
- تحقق من عدم وجود مسافات إضافية
- تحقق من صحة الـ Passphrase

### خطأ: "IP not in whitelist"

- أضف IP السيرفر إلى OKX whitelist
- أو اتركها فارغة (أقل أماناً لكن يعمل)

### خطأ: "Telegram bot not responding"

- تحقق من صحة Bot Token
- تحقق من Chat ID
- جرّب `/start` مع البوت

---

## 📞 الدعم

للمساعدة:
- البريد: louai.amoudi@gmail.com
- تليجرام: @Lamo_Dbot

---

**تم! الآن لديك كل البيانات المطلوبة! 🎉**
