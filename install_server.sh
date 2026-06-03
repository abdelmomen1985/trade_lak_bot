#!/bin/bash

# ============================================================================
# Trade Lak Bot - Server Installation Script
# ============================================================================

echo "🚀 Trade Lak Bot - Server Installation"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Step 1: Update System
# ============================================================================
echo -e "${YELLOW}Step 1: Updating system...${NC}"
apt-get update
apt-get upgrade -y

# ============================================================================
# Step 2: Install Python and Dependencies
# ============================================================================
echo -e "${YELLOW}Step 2: Installing Python and dependencies...${NC}"
apt-get install -y python3.11 python3.11-dev python3.11-venv
apt-get install -y python3-pip
apt-get install -y git wget curl
apt-get install -y build-essential libssl-dev libffi-dev
apt-get install -y sqlite3

# ============================================================================
# Step 3: Create Bot Directory
# ============================================================================
echo -e "${YELLOW}Step 3: Creating bot directory...${NC}"
mkdir -p /root/trade_lak_bot
cd /root/trade_lak_bot

# ============================================================================
# Step 4: Create Virtual Environment
# ============================================================================
echo -e "${YELLOW}Step 4: Creating virtual environment...${NC}"
python3.11 -m venv venv
source venv/bin/activate

# ============================================================================
# Step 5: Install Python Packages
# ============================================================================
echo -e "${YELLOW}Step 5: Installing Python packages...${NC}"
pip install --upgrade pip setuptools wheel

# Core packages
pip install ccxt
pip install python-telegram-bot
pip install requests
pip install numpy
pip install pandas
pip install scikit-learn
pip install pyyaml
pip install python-dotenv

# Data processing
pip install sqlalchemy
pip install sqlite3

# Async support
pip install aiohttp
pip install asyncio

# Logging
pip install python-json-logger

# Monitoring
pip install psutil

# ML packages (optional but recommended)
pip install tensorflow
pip install torch

echo -e "${GREEN}✅ Python packages installed${NC}"

# ============================================================================
# Step 6: Create Directory Structure
# ============================================================================
echo -e "${YELLOW}Step 6: Creating directory structure...${NC}"
mkdir -p /root/trade_lak_bot/core
mkdir -p /root/trade_lak_bot/utils
mkdir -p /root/trade_lak_bot/data
mkdir -p /root/trade_lak_bot/data/models
mkdir -p /root/trade_lak_bot/data/historical_data
mkdir -p /root/trade_lak_bot/logs

echo -e "${GREEN}✅ Directory structure created${NC}"

# ============================================================================
# Step 7: Create Systemd Service
# ============================================================================
echo -e "${YELLOW}Step 7: Creating systemd service...${NC}"

cat > /etc/systemd/system/trade-lak-bot.service << 'EOF'
[Unit]
Description=Trade Lak Bot - Advanced AI Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/trade_lak_bot
Environment="PATH=/root/trade_lak_bot/venv/bin"
ExecStart=/root/trade_lak_bot/venv/bin/python /root/trade_lak_bot/main.py
Restart=always
RestartSec=10
StandardOutput=append:/root/trade_lak_bot/logs/bot.log
StandardError=append:/root/trade_lak_bot/logs/bot.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable trade-lak-bot.service

echo -e "${GREEN}✅ Systemd service created${NC}"

# ============================================================================
# Step 8: Create Cron Jobs
# ============================================================================
echo -e "${YELLOW}Step 8: Setting up cron jobs...${NC}"

# Daily backup at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * cd /root/trade_lak_bot && tar -czf data/backup_\$(date +\%Y\%m\%d).tar.gz data/") | crontab -

# Weekly restart at Sunday 3 AM
(crontab -l 2>/dev/null; echo "0 3 * * 0 systemctl restart trade-lak-bot") | crontab -

echo -e "${GREEN}✅ Cron jobs configured${NC}"

# ============================================================================
# Step 9: Create Firewall Rules (if UFW is enabled)
# ============================================================================
echo -e "${YELLOW}Step 9: Configuring firewall...${NC}"

# Check if UFW is enabled
if command -v ufw &> /dev/null; then
    # Allow SSH
    ufw allow 22/tcp
    
    # Allow HTTP/HTTPS (if needed for API)
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    echo -e "${GREEN}✅ Firewall rules configured${NC}"
else
    echo -e "${YELLOW}⚠️ UFW not found, skipping firewall configuration${NC}"
fi

# ============================================================================
# Step 10: Create Log Rotation
# ============================================================================
echo -e "${YELLOW}Step 10: Setting up log rotation...${NC}"

cat > /etc/logrotate.d/trade-lak-bot << 'EOF'
/root/trade_lak_bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
}
EOF

echo -e "${GREEN}✅ Log rotation configured${NC}"

# ============================================================================
# Step 11: Create Health Check Script
# ============================================================================
echo -e "${YELLOW}Step 11: Creating health check script...${NC}"

cat > /root/trade_lak_bot/health_check.sh << 'EOF'
#!/bin/bash

# Check if bot is running
if systemctl is-active --quiet trade-lak-bot; then
    echo "✅ Bot is running"
    exit 0
else
    echo "❌ Bot is not running"
    exit 1
fi
EOF

chmod +x /root/trade_lak_bot/health_check.sh

echo -e "${GREEN}✅ Health check script created${NC}"

# ============================================================================
# Step 12: Create Monitoring Script
# ============================================================================
echo -e "${YELLOW}Step 12: Creating monitoring script...${NC}"

cat > /root/trade_lak_bot/monitor.sh << 'EOF'
#!/bin/bash

echo "Trade Lak Bot - System Monitoring"
echo "=================================="

# Check CPU usage
echo "CPU Usage:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}'

# Check Memory usage
echo "Memory Usage:"
free -h | grep Mem

# Check Disk usage
echo "Disk Usage:"
df -h /root/trade_lak_bot

# Check Bot Status
echo "Bot Status:"
systemctl status trade-lak-bot --no-pager

# Check Recent Logs
echo "Recent Logs:"
tail -20 /root/trade_lak_bot/logs/bot.log
EOF

chmod +x /root/trade_lak_bot/monitor.sh

echo -e "${GREEN}✅ Monitoring script created${NC}"

# ============================================================================
# Step 13: Create Update Script
# ============================================================================
echo -e "${YELLOW}Step 13: Creating update script...${NC}"

cat > /root/trade_lak_bot/update.sh << 'EOF'
#!/bin/bash

echo "Updating Trade Lak Bot..."

# Stop the bot
systemctl stop trade-lak-bot

# Backup current version
cp -r /root/trade_lak_bot /root/trade_lak_bot.backup.$(date +%Y%m%d_%H%M%S)

# Update packages
source /root/trade_lak_bot/venv/bin/activate
pip install --upgrade -r requirements.txt

# Start the bot
systemctl start trade-lak-bot

echo "✅ Update completed"
EOF

chmod +x /root/trade_lak_bot/update.sh

echo -e "${GREEN}✅ Update script created${NC}"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${GREEN}========================================"
echo "✅ Installation Completed Successfully!"
echo "========================================${NC}"
echo ""
echo "📋 Next Steps:"
echo "1. Copy bot files to /root/trade_lak_bot/"
echo "2. Copy config_production.yaml to /root/trade_lak_bot/"
echo "3. Run: systemctl start trade-lak-bot"
echo "4. Check logs: tail -f /root/trade_lak_bot/logs/bot.log"
echo ""
echo "🔧 Useful Commands:"
echo "  Start bot:     systemctl start trade-lak-bot"
echo "  Stop bot:      systemctl stop trade-lak-bot"
echo "  Status:        systemctl status trade-lak-bot"
echo "  Logs:          tail -f /root/trade_lak_bot/logs/bot.log"
echo "  Monitor:       /root/trade_lak_bot/monitor.sh"
echo "  Update:        /root/trade_lak_bot/update.sh"
echo ""
echo "📞 Support: Check logs for any errors"
echo ""
