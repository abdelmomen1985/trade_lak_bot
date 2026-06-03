
import sys, pickle, os
from datetime import datetime

sys.path.insert(0, '/root/trade_lak_bot')
sys.path.insert(0, '/root/trade_lak_bot/venv/lib/python3.12/site-packages')

# قراءة الصفقات
with open('/root/sync_trades.pkl', 'rb') as f:
    sync_trades = pickle.load(f)

# استيراد Strategy وحقن الصفقات
from core.strategy import TradingStrategy
import yaml

with open('/root/trade_lak_bot/config_production.yaml') as f:
    cfg_data = f.read()

# إنشاء ملف حالة مؤقت يقرأه البوت عند بدء التشغيل
state_file = '/root/trade_lak_bot/data/portfolio_sync.pkl'
os.makedirs('/root/trade_lak_bot/data', exist_ok=True)

with open(state_file, 'wb') as f:
    pickle.dump(sync_trades, f)

print(f"✅ تم حفظ {len(sync_trades)} صفقة في {state_file}")
for sym, trade in sync_trades.items():
    print(f"  {sym}: entry=${trade['entry_price']:.4f} | SL=${trade['stop_loss']:.4f}")
