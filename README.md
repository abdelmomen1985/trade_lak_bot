# 🚀 Trade Lak Bot v4

### Advanced AI-Powered Crypto Trading Bot | بوت تداول ذكي متقدم بالذكاء الاصطناعي

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Private-red.svg)](#-license)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Exchange](https://img.shields.io/badge/Exchange-OKX%20%7C%20Bybit-orange.svg)]()

> **🇸🇦 [النسخة العربية](#-المحتوى-بالعربية) | 🇬🇧 English Version Below**

---

## 📖 Overview

**Trade Lak Bot v4** is a sophisticated cryptocurrency trading bot that combines **machine learning**, **multi-strategy analysis**, and **whale tracking** to execute intelligent trades on OKX and Bybit exchanges.

### Key Highlights

- 🤖 **ML-Powered Decisions** — Random Forest & Gradient Boosting models that learn from every trade
- 📊 **5 Parallel Strategies** — Momentum, Mean Reversion, Breakout, Volume Profile, and ML-Based
- 🛡️ **Advanced Risk Management** — 4-level Circuit Breaker system with Kelly Criterion sizing
- 🐋 **Whale Tracking** — On-chain monitoring of large wallet movements
- 💎 **CoinGlass Integration** — Funding rates, long/short ratios, liquidation data
- 📢 **Telegram Alerts** — Real-time notifications for all trade events

---

## 🏗️ Architecture

```
trade_lak_bot/
├── main.py                      # 🎯 Main entry point & bot orchestrator
├── config/
│   └── config.py                # ⚙️ Configuration & API keys
├── core/
│   ├── okx_client.py            # 🔌 OKX exchange client
│   ├── bybit_client.py          # 🔌 Bybit exchange client
│   ├── exchange_router.py       # 🔀 Multi-exchange router
│   ├── coinglass_client.py      # 💎 CoinGlass data client
│   ├── ml_model.py              # 🤖 ML model (Random Forest + XGBoost)
│   ├── multi_strategy.py        # 📊 5-strategy engine
│   ├── advanced_risk_manager.py # 🛡️ Risk management system
│   ├── fake_break_detector.py   # 🎯 Core "Fake Break" strategy
│   ├── intelligence_engine.py   # 🧠 Intelligence aggregation
│   └── orderbook_analyzer.py    # 📖 Order book analysis
├── utils/
│   ├── telegram_notifier.py     # 📢 Telegram notifications
│   └── notifier.py              # 🔔 General notifications
├── models/                      # 💾 Trained ML models
├── data/                        # 📁 Market data & trade history
├── logs/                        # 📝 Application logs
├── skills/                      # 🎓 Trading skill definitions
└── requirements.txt             # 📦 Python dependencies
```

---

## ✨ Features

### 🤖 Machine Learning Engine
| Feature | Description |
|---------|-------------|
| **Random Forest** | Ensemble model for pattern recognition |
| **Gradient Boosting (XGBoost)** | Advanced sequential learning |
| **Feature Engineering** | 50+ technical indicators extracted per trade |
| **Continuous Learning** | Retrains on every closed trade |
| **Confidence Scoring** | Each prediction includes confidence % |

### 📊 Trading Strategies

1. **Momentum Strategy** — Follows trend continuation patterns
2. **Mean Reversion** — Buys oversold / sells overbought conditions
3. **Breakout Strategy** — Catches key level breakouts with volume confirmation
4. **Volume Profile** — Trades at high-volume nodes and liquidity zones
5. **ML-Based Strategy** — Pure AI-driven signal generation

### 🎯 Core Strategy: Fake Break (30% Weight)
The bot's signature strategy detects when whales hunt stop losses:
1. Identify support/resistance zones
2. Wait for liquidity grab (0.1%–2.5% break)
3. Confirm with candlestick patterns (Pin Bar, Engulfing)
4. Enter after confirmation with tight stop loss
5. Take profits at 3 levels (30%, 60%, previous high)

### 🛡️ Risk Management

```
┌─────────────────────────────────────────────────────────┐
│  Level 1: Daily Loss Limit      → 5% of capital        │
│  Level 2: Consecutive Losses    → 3 trades max         │
│  Level 3: Hourly Drawdown       → 3% circuit breaker   │
│  Level 4: Total Drawdown        → 10% emergency stop   │
├─────────────────────────────────────────────────────────┤
│  Position Sizing: Kelly Criterion                      │
│  Max Leverage: 3x (conservative)                       │
│  Correlation Filter: No correlated positions           │
│  Max Trades: 3 Spot + 2 Futures simultaneously         │
└─────────────────────────────────────────────────────────┘
```

### 📢 Telegram Integration
- ✅ Trade open/close notifications
- 📊 Daily & weekly performance reports
- ⚠️ Error & warning alerts
- 🎯 Signal notifications with entry/SL/TP
- 💰 Portfolio status updates

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager
- OKX API keys ([Get them here](https://www.okx.com/account/my-api))
- Telegram Bot Token (optional, [create via @BotFather](https://t.me/BotFather))

### 1. Clone & Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd trade_lak_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

Edit `config/config.py`:

```python
# ===== Exchange API Keys =====
OKX_API_KEY      = "your_api_key"
OKX_SECRET_KEY   = "your_secret_key"
OKX_PASSPHRASE   = "your_passphrase"

# ===== Telegram (Optional) =====
TELEGRAM_ENABLED    = True
TELEGRAM_BOT_TOKEN  = "your_bot_token"
TELEGRAM_CHAT_ID    = "your_chat_id"

# ===== Trading Settings =====
TOTAL_CAPITAL        = 300        # Starting capital in USD
SPOT_CAPITAL_PCT     = 0.65       # 65% for Spot trading
FUTURES_CAPITAL_PCT  = 0.35       # 35% for Futures trading

# ===== Safety Mode =====
DRY_RUN = True   # True = Paper trading | False = Live trading
```

### 3. Run

```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python main.py
```

**Expected output:**
```
✅ ML Model initialized
✅ Multi-Strategy Engine initialized
✅ Advanced Intelligence Engine initialized
✅ Telegram Notifier initialized
🤖 Bot is running...
```

---

## 🖥️ Production Deployment

### Using systemd (Recommended)

```bash
# Create service file
sudo tee /etc/systemd/system/trade-lak-bot.service > /dev/null <<EOF
[Unit]
Description=Trade Lak Bot v4
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trade_lak_bot
Environment="PATH=/opt/trade_lak_bot/venv/bin"
ExecStart=/opt/trade_lak_bot/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable trade-lak-bot
sudo systemctl start trade-lak-bot

# Check status
sudo systemctl status trade-lak-bot

# View logs
sudo journalctl -u trade-lak-bot -f
```

---

## ⚙️ Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `DRY_RUN` | bool | `True` | Paper trading mode |
| `TOTAL_CAPITAL` | float | `300` | Starting capital (USD) |
| `CHECK_INTERVAL` | int | `60` | Market scan interval (seconds) |
| `MAX_SPOT_TRADES` | int | `3` | Max concurrent spot positions |
| `MAX_FUTURES_TRADES` | int | `2` | Max concurrent futures positions |
| `TELEGRAM_ENABLED` | bool | `True` | Enable Telegram notifications |
| `COINGLASS_API_KEY` | str | - | CoinGlass API key (optional) |

---

## 📈 How It Works

```
    ┌──────────────────────────────────────────────────────┐
    │              MARKET SCAN (Every 60s)                 │
    └──────────────────────────┬───────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │         5 STRATEGIES RUN IN PARALLEL                 │
    │  ┌─────────┬─────────┬─────────┬─────────┬────────┐ │
    │  │Momentum │Mean Rev │Breakout │Volume   │   ML   │ │
    │  │         │         │         │Profile  │        │ │
    │  └────┬────┴────┬────┴────┬────┴────┬────┴────┬───┘ │
    └───────┼─────────┼─────────┼─────────┼─────────┼─────┘
            │         │         │         │         │
            ▼         ▼         ▼         ▼         ▼
    ┌──────────────────────────────────────────────────────┐
    │         SIGNAL AGGREGATION & ML SCORING              │
    │  • Weight: Fake Break 30%, ML 18%, Strategy 18%     │
    │  • On-chain 14%, Orderbook 12%, CoinGlass 8%        │
    └──────────────────────────┬───────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │            RISK MANAGEMENT CHECK                     │
    │  ✓ Position size (Kelly)  ✓ Correlation check       │
    │  ✓ Daily limit            ✓ Circuit breaker          │
    └──────────────────────────┬───────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │         EXECUTE TRADE (if signal ≥ threshold)        │
    │  • Entry price with limit order                     │
    │  • Stop loss (behind liquidity grab + 0.3%)         │
    │  • 3 Take-profit levels (30% / 60% / 100%)          │
    └──────────────────────────┬───────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │         MONITOR & MANAGE OPEN POSITIONS              │
    │  • Trailing stop adjustments                        │
    │  • Partial profit taking                            │
    │  • Emergency exit on reversal signals               │
    └──────────────────────────┬───────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │         CLOSE & LEARN                                │
    │  • Record trade outcome                             │
    │  • Retrain ML model with new data                   │
    │  • Send Telegram notification                       │
    │  • Update performance metrics                       │
    └──────────────────────────────────────────────────────┘
```

---

## 🔒 Security Best Practices

1. **Never share API keys** — Store in `config/config.py` only, never commit to git
2. **Disable withdrawal permissions** — Only enable trade permissions on OKX
3. **Start with DRY_RUN** — Test thoroughly before going live
4. **Use small capital** — Start with amounts you can afford to lose
5. **Monitor regularly** — Check logs and Telegram alerts daily
6. **Backup configs** — Keep encrypted backups of your settings

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) | Step-by-step server setup |
| [SKILL.md](SKILL.md) | Trading strategy deep-dive |
| [COMPREHENSIVE_REPORT.md](COMPREHENSIVE_REPORT.md) | Full system analysis |
| [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) | Visual architecture |
| [API_KEYS_GUIDE.md](API_KEYS_GUIDE.md) | How to get API keys |
| [known_issues.md](known_issues.md) | Known issues & workarounds |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot won't start | Check `logs/bot.log` for errors |
| No trades executing | Verify `DRY_RUN=False` and API keys are correct |
| Import errors | Run `pip install -r requirements.txt` in venv |
| Connection timeouts | Check server internet & firewall settings |
| Telegram not working | Verify bot token and chat ID |

---

## ⚠️ Disclaimer

**Cryptocurrency trading involves significant risk.**

- You may lose your entire capital
- Past performance does not guarantee future results
- Use this bot at your own risk
- Always start with paper trading (DRY_RUN=True)
- The authors are not responsible for any financial losses

---

## 📧 Support

- 📧 Email: louai.amoudi@gmail.com
- 💬 Telegram: [@Lamo_Dbot](https://t.me/Lamo_Dbot)

---

## 📄 License

This project is private and proprietary. All rights reserved.

---

## 🇸🇦 المحتوى بالعربية

# 🚀 بوت Trade لك v4 — بوت تداول ذكي متقدم

## نظرة عامة

بوت تداول ذكي يجمع بين **التعلم الآلي**، **تحليل الاستراتيجيات المتعددة**، و**تتبع الحيتان** لتنفيذ صفقات ذكية على منصتي OKX و Bybit.

### أبرز المميزات

- 🤖 **نماذج Machine Learning** — Random Forest و XGBoost يتعلمان من كل صفقة
- 📊 **5 استراتيجيات متوازية** — الزخم، الانعكاس، الاختراق، الملف الحجمي، والذكاء الاصطناعي
- 🛡️ **إدارة مخاطر متقدمة** — نظام Circuit Breaker بـ 4 مستويات
- 🐋 **تتبع الحيتان** — مراقبة تحركات المحافظ الكبيرة
- 📢 **تنبيهات تليجرام** — إشعارات فورية لكل الأحداث

### التثبيت السريع

```bash
git clone <your-repo-url>
cd trade_lak_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### ⚠️ تحذير مهم

**التداول بالعملات الرقمية ينطوي على مخاطر عالية!**
- قد تفقد كل رأس مالك
- استخدم البوت على مسؤوليتك الخاصة
- ابدأ دائماً بوضع الاختبار (DRY_RUN = True)
- ابدأ برأس مال صغير يمكنك تحمل خسارته

---

<p align="center">
  Made with ❤️ by Trade Lak Team<br>
  <strong>Version:</strong> 4.0.0<br>
  <strong>Last Updated:</strong> June 2026
</p>
