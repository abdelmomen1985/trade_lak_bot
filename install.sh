#!/bin/bash
# ============================================================
# Trade Lak Bot - Auto Installation Script
# سكريبت التثبيت التلقائي لبوت Trade لك
# ============================================================
# الاستخدام: bash install.sh
# ============================================================

echo "======================================================"
echo "  Trade Lak Bot - سكريبت التثبيت التلقائي"
echo "======================================================"

# تحديث النظام
echo "[1/6] تحديث النظام..."
sudo apt-get update -y && sudo apt-get upgrade -y

# تثبيت Python 3 و pip
echo "[2/6] تثبيت Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# إنشاء بيئة افتراضية
echo "[3/6] إنشاء بيئة Python الافتراضية..."
python3 -m venv venv
source venv/bin/activate

# تثبيت المكتبات
echo "[4/6] تثبيت المكتبات المطلوبة..."
pip install --upgrade pip
pip install -r requirements.txt

# إنشاء مجلد السجلات
echo "[5/6] إنشاء مجلدات السجلات..."
mkdir -p logs

# إعداد خدمة systemd للتشغيل التلقائي
echo "[6/6] إعداد التشغيل التلقائي عند إعادة تشغيل السيرفر..."
CURRENT_DIR=$(pwd)
cat > /tmp/tradelak.service << EOF
[Unit]
Description=Trade Lak Bot - بوت التداول الذكي
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 main.py
Restart=always
RestartSec=30
StandardOutput=append:$CURRENT_DIR/logs/bot.log
StandardError=append:$CURRENT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/tradelak.service /etc/systemd/system/tradelak.service
sudo systemctl daemon-reload
sudo systemctl enable tradelak

echo ""
echo "======================================================"
echo "  التثبيت اكتمل بنجاح!"
echo "======================================================"
echo ""
echo "الخطوة التالية:"
echo "  1. افتح ملف الإعدادات: nano config/config.py"
echo "  2. أدخل API Keys الخاصة بك (OKX + CoinGlass)"
echo "  3. غيّر DRY_RUN = False عند الاستعداد للتداول الحقيقي"
echo ""
echo "أوامر التشغيل:"
echo "  تشغيل البوت:        sudo systemctl start tradelak"
echo "  إيقاف البوت:        sudo systemctl stop tradelak"
echo "  حالة البوت:         sudo systemctl status tradelak"
echo "  عرض السجلات:        tail -f logs/bot.log"
echo "  اختبار يدوي:        python3 main.py --dry-run"
echo "======================================================"
