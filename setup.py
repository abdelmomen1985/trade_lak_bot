#!/usr/bin/env python3
# ============================================================
# Trade Lak Bot v4 - Setup Script
# بوت Trade لك v4 - سكريبت الإعداد
# ============================================================

import os
import sys
import json
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    dirs = ['logs', 'models', 'data', 'config']
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {dir_name}/")
        else:
            print_info(f"{dir_name}/ already exists")

def setup_config():
    """Setup configuration file"""
    print_header("Configuration Setup")
    
    config_path = Path('config/config.py')
    
    if config_path.exists():
        print_warning("config.py already exists")
        response = input("Do you want to reconfigure? (y/n): ").lower()
        if response != 'y':
            return
    
    print_info("Let's configure your bot!\n")
    
    # OKX API
    print("🔑 OKX API Configuration:")
    okx_api_key = input("OKX API Key: ").strip()
    okx_secret_key = input("OKX Secret Key: ").strip()
    okx_passphrase = input("OKX Passphrase: ").strip()
    
    # Telegram
    print("\n📱 Telegram Configuration (optional):")
    telegram_enabled = input("Enable Telegram? (y/n): ").lower() == 'y'
    telegram_token = ""
    telegram_chat_id = ""
    
    if telegram_enabled:
        telegram_token = input("Telegram Bot Token: ").strip()
        telegram_chat_id = input("Telegram Chat ID (press Enter to skip): ").strip()
    
    # CoinGlass
    print("\n💎 CoinGlass Configuration (optional):")
    coinglass_key = input("CoinGlass API Key (press Enter to skip): ").strip()
    
    # Trading Settings
    print("\n💰 Trading Settings:")
    total_capital = input("Total Capital ($) [default: 300]: ").strip() or "300"
    dry_run = input("Enable Dry Run mode? (y/n) [default: y]: ").lower() != 'n'
    
    # Update config
    try:
        config_content = config_path.read_text()
        
        # Replace values
        config_content = config_content.replace(
            'OKX_API_KEY      = ""',
            f'OKX_API_KEY      = "{okx_api_key}"'
        )
        config_content = config_content.replace(
            'OKX_SECRET_KEY   = ""',
            f'OKX_SECRET_KEY   = "{okx_secret_key}"'
        )
        config_content = config_content.replace(
            'OKX_PASSPHRASE   = ""',
            f'OKX_PASSPHRASE   = "{okx_passphrase}"'
        )
        config_content = config_content.replace(
            'TELEGRAM_ENABLED    = False',
            f'TELEGRAM_ENABLED    = {telegram_enabled}'
        )
        config_content = config_content.replace(
            'TELEGRAM_BOT_TOKEN  = "YOUR_TELEGRAM_BOT_TOKEN"',
            f'TELEGRAM_BOT_TOKEN  = "{telegram_token}"'
        )
        if telegram_chat_id:
            config_content = config_content.replace(
                'TELEGRAM_CHAT_ID    = "YOUR_CHAT_ID"',
                f'TELEGRAM_CHAT_ID    = "{telegram_chat_id}"'
            )
        if coinglass_key:
            config_content = config_content.replace(
                'COINGLASS_API_KEY = ""',
                f'COINGLASS_API_KEY = "{coinglass_key}"'
            )
        config_content = config_content.replace(
            'TOTAL_CAPITAL        = 300',
            f'TOTAL_CAPITAL        = {total_capital}'
        )
        config_content = config_content.replace(
            'DRY_RUN = False',
            f'DRY_RUN = {dry_run}'
        )
        
        config_path.write_text(config_content)
        print_success("Configuration saved!")
        
    except Exception as e:
        print_error(f"Failed to update config: {e}")

def check_dependencies():
    """Check if all dependencies are installed"""
    print_header("Checking Dependencies")
    
    required_packages = {
        'ccxt': 'CCXT',
        'requests': 'Requests',
        'numpy': 'NumPy',
        'pandas': 'Pandas',
        'sklearn': 'Scikit-learn',
        'joblib': 'Joblib',
    }
    
    missing_packages = []
    
    for package, name in required_packages.items():
        try:
            __import__(package)
            print_success(f"{name} is installed")
        except ImportError:
            print_error(f"{name} is NOT installed")
            missing_packages.append(package)
    
    if missing_packages:
        print_warning(f"\nMissing packages: {', '.join(missing_packages)}")
        response = input("Install missing packages? (y/n): ").lower()
        if response == 'y':
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            print_success("Packages installed!")
    else:
        print_success("All dependencies are installed!")

def test_bot():
    """Test bot startup"""
    print_header("Testing Bot")
    
    response = input("Test bot startup? (y/n): ").lower()
    if response != 'y':
        return
    
    print_info("Starting bot in test mode...")
    print_warning("The bot will run for 10 seconds then stop.\n")
    
    import subprocess
    import time
    
    try:
        process = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(10)
        process.terminate()
        
        print_success("Bot test completed!")
        
    except Exception as e:
        print_error(f"Bot test failed: {e}")

def main():
    """Main setup function"""
    print("\n")
    print("🚀 Trade Lak Bot v4 - Setup Wizard")
    print("بوت Trade لك v4 - معالج الإعداد")
    print("\n")
    
    # Step 1: Create directories
    create_directories()
    
    # Step 2: Check dependencies
    check_dependencies()
    
    # Step 3: Setup configuration
    setup_config()
    
    # Step 4: Test bot
    test_bot()
    
    # Final message
    print_header("Setup Complete!")
    print_success("Your bot is ready to run!")
    print("\n📋 Next Steps:")
    print("1. Review config/config.py")
    print("2. Change DRY_RUN to False when ready for live trading")
    print("3. Run: python3 main.py")
    print("\n⚠️  Important:")
    print("- Start with DRY_RUN = True")
    print("- Never share your API keys")
    print("- Monitor the bot regularly")
    print("\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {e}")
        sys.exit(1)
