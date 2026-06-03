#!/bin/bash

# ============================================================
# Trade Lak Bot v4 - Deployment Script
# بوت Trade لك v4 - سكريبت التثبيت على السيرفر
# ============================================================

set -e

echo "🚀 Trade Lak Bot v4 - Deployment Script"
echo "========================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================
# 1. Update System
# ============================================================

echo -e "${YELLOW}[1/7] Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# ============================================================
# 2. Install Python and Dependencies
# ============================================================

echo -e "${YELLOW}[2/7] Installing Python and dependencies...${NC}"
sudo apt-get install -y python3.11 python3-pip python3-venv git curl wget

# ============================================================
# 3. Create Bot Directory
# ============================================================

echo -e "${YELLOW}[3/7] Creating bot directory...${NC}"
BOT_DIR="/opt/trade_lak_bot"
sudo mkdir -p $BOT_DIR
sudo chown $USER:$USER $BOT_DIR

# ============================================================
# 4. Clone/Copy Bot Files
# ============================================================

echo -e "${YELLOW}[4/7] Setting up bot files...${NC}"
if [ -d "$BOT_DIR/.git" ]; then
    echo "Updating existing repository..."
    cd $BOT_DIR
    git pull origin main
else
    echo "Note: Copy bot files to $BOT_DIR manually or use git clone"
    echo "Example: cp -r /path/to/trade_lak_bot/* $BOT_DIR/"
fi

# ============================================================
# 5. Create Virtual Environment
# ============================================================

echo -e "${YELLOW}[5/7] Creating Python virtual environment...${NC}"
cd $BOT_DIR
python3 -m venv venv
source venv/bin/activate

# ============================================================
# 6. Install Python Dependencies
# ============================================================

echo -e "${YELLOW}[6/7] Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# ============================================================
# 7. Create Systemd Service
# ============================================================

echo -e "${YELLOW}[7/7] Creating systemd service...${NC}"

sudo tee /etc/systemd/system/trade-lak-bot.service > /dev/null <<EOF
[Unit]
Description=Trade Lak Bot v4 - Advanced AI Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin"
ExecStart=$BOT_DIR/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trade-lak-bot.service

# ============================================================
# 8. Create Directories
# ============================================================

echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p $BOT_DIR/logs
mkdir -p $BOT_DIR/models
mkdir -p $BOT_DIR/data

# ============================================================
# 9. Setup Logrotate
# ============================================================

echo -e "${YELLOW}Setting up log rotation...${NC}"

sudo tee /etc/logrotate.d/trade-lak-bot > /dev/null <<EOF
$BOT_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 $USER $USER
    sharedscripts
}
EOF

# ============================================================
# 10. Final Setup
# ============================================================

echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "📋 Next Steps:"
echo "1. Edit config/config.py with your API keys:"
echo "   nano $BOT_DIR/config/config.py"
echo ""
echo "2. Start the bot:"
echo "   sudo systemctl start trade-lak-bot"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status trade-lak-bot"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u trade-lak-bot -f"
echo ""
echo "5. Stop the bot:"
echo "   sudo systemctl stop trade-lak-bot"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "- Set DRY_RUN = True in config.py first to test"
echo "- Change to DRY_RUN = False only after testing"
echo "- Never share your API keys!"
echo ""
