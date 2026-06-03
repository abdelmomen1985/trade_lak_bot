# 🚀 Trade Lak Bot v4 - Installation Guide on Contabo

**دليل تثبيت بوت Trade لك v4 على سيرفر Contabo**

---

## 📋 المتطلبات

- ✅ Contabo VPS (Linux - Ubuntu 22.04 أو أحدث)
- ✅ SSH Access
- ✅ OKX API Keys
- ✅ Telegram Bot Token (اختياري)
- ✅ CoinGlass API Key (اختياري)

---

## 🔧 خطوات التثبيت

### الخطوة 1️⃣: الاتصال بالسيرفر عبر SSH

```bash
ssh root@YOUR_SERVER_IP
```

استبدل `YOUR_SERVER_IP` بـ IP السيرفر الخاص بك

**مثال:**
```bash
ssh root@123.45.67.89
```

### الخطوة 2️⃣: تحديث النظام

```bash
apt-get update
apt-get upgrade -y
```

### الخطوة 3️⃣: تثبيت المتطلبات الأساسية

```bash
apt-get install -y python3.11 python3-pip python3-venv git curl wget
```

### الخطوة 4️⃣: إنشاء مجلد البوت

```bash
mkdir -p /opt/trade_lak_bot
cd /opt/trade_lak_bot
```

### الخطوة 5️⃣: رفع ملفات البوت

**من جهازك المحلي:**

```bash
scp -r /path/to/trade_lak_bot/* root@YOUR_SERVER_IP:/opt/trade_lak_bot/
```

**أو استخدم Git:**

```bash
cd /opt/trade_lak_bot
git clone <your_repo_url> .
```

### الخطوة 6️⃣: إنشاء Virtual Environment

```bash
cd /opt/trade_lak_bot
python3 -m venv venv
source venv/bin/activate
```

### الخطوة 7️⃣: تثبيت المكتبات

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### الخطوة 8️⃣: إعداد الإعدادات

```bash
nano config/config.py
```

**أضف بيانات API:**

```python
# OKX API Credentials
OKX_API_KEY      = "your_api_key_here"
OKX_SECRET_KEY   = "your_secret_key_here"
OKX_PASSPHRASE   = "your_passphrase_here"

# Telegram
TELEGRAM_ENABLED    = True
TELEGRAM_BOT_TOKEN  = "your_bot_token_here"
TELEGRAM_CHAT_ID    = "your_chat_id_here"  # سيتم الحصول عليه تلقائياً

# CoinGlass (اختياري)
COINGLASS_API_KEY = "your_coinglass_key_here"

# وضع الاختبار (غيّره لـ False بعد الاختبار)
DRY_RUN = True
```

**احفظ واخرج:**
- اضغط: `Ctrl + X`
- اضغط: `Y`
- اضغط: `Enter`

### الخطوة 9️⃣: اختبار البوت

```bash
source venv/bin/activate
python3 main.py
```

**يجب أن ترى:**
```
✅ ML Model initialized
✅ Multi-Strategy Engine initialized
✅ Advanced Intelligence Engine initialized
✅ Telegram Notifier initialized
🤖 البوت يعمل الآن...
```

اضغط `Ctrl + C` للإيقاف

### الخطوة 1️⃣0️⃣: إنشاء Systemd Service

```bash
sudo tee /etc/systemd/system/trade-lak-bot.service > /dev/null <<EOF
[Unit]
Description=Trade Lak Bot v4 - Advanced AI Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trade_lak_bot
Environment="PATH=/opt/trade_lak_bot/venv/bin"
ExecStart=/opt/trade_lak_bot/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### الخطوة 1️⃣1️⃣: تفعيل الخدمة

```bash
sudo systemctl daemon-reload
sudo systemctl enable trade-lak-bot.service
```

### الخطوة 1️⃣2️⃣: تشغيل البوت

```bash
sudo systemctl start trade-lak-bot
```

### الخطوة 1️⃣3️⃣: التحقق من الحالة

```bash
sudo systemctl status trade-lak-bot
```

يجب أن ترى: `active (running)`

---

## 📊 أوامر مفيدة

### عرض السجلات الحية

```bash
sudo journalctl -u trade-lak-bot -f
```

### إيقاف البوت

```bash
sudo systemctl stop trade-lak-bot
```

### إعادة تشغيل البوت

```bash
sudo systemctl restart trade-lak-bot
```

### حالة البوت

```bash
sudo systemctl status trade-lak-bot
```

### عرض آخر 100 سطر من السجلات

```bash
sudo journalctl -u trade-lak-bot -n 100
```

### عرض السجلات من ساعة محددة

```bash
sudo journalctl -u trade-lak-bot --since "2 hours ago"
```

---

## 🔒 الأمان

### 1. تعطيل SSH للـ Root

```bash
sudo sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 2. تفعيل Firewall

```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 3. إنشاء مستخدم عادي

```bash
sudo adduser botuser
sudo usermod -aG sudo botuser
```

---

## 🐛 استكشاف الأخطاء

### البوت لا يبدأ

```bash
# عرض السجلات
sudo journalctl -u trade-lak-bot -n 50

# تحقق من الأخطاء في الملف
python3 /opt/trade_lak_bot/main.py
```

### خطأ في الاستيراد

```bash
cd /opt/trade_lak_bot
source venv/bin/activate
pip install -r requirements.txt
```

### لا توجد صفقات

- تحقق من `DRY_RUN = False` في config.py
- تحقق من رصيد OKX
- تحقق من API Keys الصحيحة

---

## 📈 المراقبة والصيانة

### إنشاء نسخة احتياطية

```bash
tar -czf trade_lak_bot_backup.tar.gz /opt/trade_lak_bot/
```

### تحديث البوت

```bash
cd /opt/trade_lak_bot
git pull origin main
sudo systemctl restart trade-lak-bot
```

### مراقبة استخدام الموارد

```bash
top
```

---

## ⚠️ تحذيرات مهمة

1. **ابدأ دائماً بـ DRY_RUN = True** للتأكد من أن كل شيء يعمل
2. **لا تشارك API Keys** مع أحد
3. **لا تفعّل صلاحية Withdraw** في OKX
4. **راقب البوت بانتظام** خلال الأيام الأولى
5. **احفظ نسخة احتياطية** من الإعدادات

---

## 📞 الدعم

للمساعدة:
- البريد: louai.amoudi@gmail.com
- تليجرام: @Lamo_Dbot

---

**تم التثبيت بنجاح! 🎉**
