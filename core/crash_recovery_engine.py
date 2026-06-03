"""
Crash Detection & Recovery Engine + Pump Detection
نظام كشف الانهيارات والتعافي وأوقات الضخ
يعمل في جميع حالات السوق
"""
import requests
import json
import time
import numpy as np
from datetime import datetime, timedelta


class CrashRecoveryEngine:
    """
    محرك كشف الانهيارات والتعافي
    يكشف:
    1. الانهيارات الوشيكة قبل حدوثها
    2. فرص التعافي بعد الانهيار
    3. أوقات الضخ (Pump)
    4. تلاعب صناع السوق
    """
    
    BINANCE_API = "https://api.binance.com/api/v3"
    
    def __init__(self):
        self.crash_threshold = -0.08    # هبوط 8% = انهيار
        self.pump_threshold = 0.08      # صعود 8% = ضخ
        self.recovery_threshold = 0.05  # صعود 5% بعد انهيار = تعافي
        self.alert_history = []
    
    # ============================================================
    # كشف الانهيار
    # ============================================================
    
    def detect_crash_signals(self, df, symbol):
        """
        كشف إشارات الانهيار المبكرة
        يفحص عدة مؤشرات لتحديد احتمال الانهيار
        """
        if df is None or len(df) < 50:
            return {"risk": "LOW", "score": 0, "signals": []}
        
        signals = []
        crash_score = 0
        
        close = df['close'].values
        volume = df['volume'].values
        
        # 1. هبوط سريع في السعر
        recent_change_1h = (close[-1] - close[-4]) / close[-4] if len(close) > 4 else 0
        recent_change_4h = (close[-1] - close[-16]) / close[-16] if len(close) > 16 else 0
        
        if recent_change_1h < -0.05:
            crash_score += 30
            signals.append(f"⚠️ هبوط {abs(recent_change_1h):.1%} في آخر ساعة")
        
        if recent_change_4h < -0.10:
            crash_score += 40
            signals.append(f"🚨 هبوط {abs(recent_change_4h):.1%} في آخر 4 ساعات")
        
        # 2. ارتفاع حجم التداول مع الهبوط (بيع مكثف)
        if len(volume) > 20:
            avg_volume = np.mean(volume[-20:])
            current_volume = volume[-1]
            volume_spike = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_spike > 3 and recent_change_1h < 0:
                crash_score += 25
                signals.append(f"📊 حجم تداول {volume_spike:.1f}x المعدل مع هبوط = بيع مكثف")
        
        # 3. كسر مستوى دعم مهم
        if 'ema200' in df.columns:
            ema200 = df['ema200'].values[-1]
            if close[-1] < ema200 and close[-5] > ema200:
                crash_score += 20
                signals.append("⚠️ كسر EMA200 للأسفل = إشارة هبوط قوية")
        
        # 4. RSI في منطقة البيع المفرط
        if 'rsi' in df.columns:
            rsi = df['rsi'].values[-1]
            rsi_prev = df['rsi'].values[-5] if len(df) > 5 else rsi
            
            if rsi < 25:
                signals.append(f"📉 RSI={rsi:.0f} منطقة بيع مفرط - قد يكون قاع")
                crash_score -= 10  # يقلل احتمال استمرار الهبوط
            elif rsi > 70 and rsi < rsi_prev:
                crash_score += 15
                signals.append(f"📉 RSI={rsi:.0f} يتراجع من منطقة شراء مفرط")
        
        # 5. MACD سلبي ومتسارع
        if 'macd_hist' in df.columns:
            macd_hist = df['macd_hist'].values
            if len(macd_hist) > 3:
                if macd_hist[-1] < 0 and macd_hist[-1] < macd_hist[-2] < macd_hist[-3]:
                    crash_score += 15
                    signals.append("📉 MACD يتسارع للأسفل")
        
        # 6. Bollinger Band Squeeze ثم انفجار للأسفل
        if 'bb_width' in df.columns and 'bb_lower' in df.columns:
            bb_width = df['bb_width'].values
            if len(bb_width) > 10:
                avg_width = np.mean(bb_width[-10:])
                if bb_width[-1] > avg_width * 1.5 and close[-1] < df['bb_lower'].values[-1]:
                    crash_score += 20
                    signals.append("💥 انفجار Bollinger Band للأسفل")
        
        # تحديد مستوى الخطر
        if crash_score >= 70:
            risk = "CRITICAL"
        elif crash_score >= 50:
            risk = "HIGH"
        elif crash_score >= 30:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        
        return {
            "symbol": symbol,
            "risk": risk,
            "score": crash_score,
            "signals": signals,
            "recommendation": self._get_crash_recommendation(risk),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_crash_recommendation(self, risk):
        """توصية بناءً على مستوى الخطر"""
        recommendations = {
            "CRITICAL": "🚨 خطر انهيار! أغلق المراكز الطويلة فوراً. لا تشتري الآن.",
            "HIGH": "⚠️ خطر عالٍ. قلل حجم المراكز. ضع وقف خسارة ضيق.",
            "MEDIUM": "⚡ حذر. تابع السوق عن كثب. لا تزيد مراكزك.",
            "LOW": "✅ السوق طبيعي. يمكن التداول بحذر."
        }
        return recommendations.get(risk, "")
    
    # ============================================================
    # كشف التعافي
    # ============================================================
    
    def detect_recovery_signals(self, df, symbol):
        """
        كشف فرص التعافي بعد الانهيار
        هذه من أفضل فرص الشراء
        """
        if df is None or len(df) < 50:
            return {"is_recovery": False, "confidence": 0}
        
        close = df['close'].values
        signals = []
        recovery_score = 0
        
        # 1. هل كان هناك انهيار مؤخراً؟
        max_recent = max(close[-48:]) if len(close) > 48 else close[-1]
        current = close[-1]
        drawdown = (current - max_recent) / max_recent
        
        if drawdown > -0.15:  # لم يكن هناك انهيار كافٍ
            return {"is_recovery": False, "confidence": 0, "reason": "لا يوجد انهيار مسبق"}
        
        # 2. هل بدأ التعافي؟
        recent_low = min(close[-24:]) if len(close) > 24 else current
        recovery_from_low = (current - recent_low) / recent_low
        
        if recovery_from_low > 0.03:
            recovery_score += 30
            signals.append(f"✅ ارتفاع {recovery_from_low:.1%} من القاع")
        
        # 3. حجم التداول يرتفع مع الصعود
        if len(df) > 20:
            volume = df['volume'].values
            avg_volume = np.mean(volume[-20:])
            if volume[-1] > avg_volume * 1.5 and close[-1] > close[-2]:
                recovery_score += 25
                signals.append("📊 حجم تداول مرتفع مع الصعود = شراء قوي")
        
        # 4. RSI يخرج من منطقة البيع المفرط
        if 'rsi' in df.columns:
            rsi = df['rsi'].values
            if len(rsi) > 5:
                if rsi.iloc[-1] > 30 and rsi.iloc[-5] < 25:
                    recovery_score += 20
                    signals.append(f"📈 RSI خرج من منطقة البيع المفرط: {rsi.iloc[-1]:.0f}")
        
        # 5. MACD يتحول للإيجابي
        if 'macd_hist' in df.columns:
            macd_hist = df['macd_hist'].values
            if len(macd_hist) > 3:
                if macd_hist[-1] > 0 and macd_hist[-3] < 0:
                    recovery_score += 25
                    signals.append("📈 MACD تحول للإيجابي")
        
        # 6. السعر يتجاوز EMA9
        if 'ema9' in df.columns:
            ema9 = df['ema9'].values[-1]
            if close[-1] > ema9 and close[-2] < ema9:
                recovery_score += 15
                signals.append("✅ السعر تجاوز EMA9 للأعلى")
        
        is_recovery = recovery_score >= 50
        confidence = min(recovery_score / 100, 0.95)
        
        return {
            "is_recovery": is_recovery,
            "confidence": confidence,
            "score": recovery_score,
            "drawdown_from_peak": abs(drawdown),
            "recovery_from_low": recovery_from_low,
            "signals": signals,
            "symbol": symbol,
            "recommendation": "🚀 فرصة تعافي ممتازة! الانهيار انتهى والسوق يتعافى." if is_recovery else "⏳ انتظر تأكيد التعافي"
        }
    
    # ============================================================
    # كشف الضخ (Pump)
    # ============================================================
    
    def detect_pump_signals(self, df, symbol):
        """
        كشف أوقات الضخ (Pump)
        يكشف ما إذا كانت العملة في مرحلة ضخ
        """
        if df is None or len(df) < 20:
            return {"is_pump": False, "stage": "UNKNOWN", "signals": [], "change_1h": 0, "change_4h": 0, "change_24h": 0, "volume_spike": 1, "recommendation": "", "symbol": symbol}
        
        close = df['close'].values
        volume = df['volume'].values
        
        # 1. ارتفاع سريع في السعر
        change_1h = (close[-1] - close[-4]) / close[-4] if len(close) > 4 else 0
        change_4h = (close[-1] - close[-16]) / close[-16] if len(close) > 16 else 0
        change_24h = (close[-1] - close[-96]) / close[-96] if len(close) > 96 else 0
        
        # 2. ارتفاع في حجم التداول
        avg_volume = np.mean(volume[-20:]) if len(volume) > 20 else volume[-1]
        volume_spike = volume[-1] / avg_volume if avg_volume > 0 else 1
        
        # تحديد مرحلة الضخ
        pump_stage = "NONE"
        signals = []
        
        if change_1h > 0.05 and volume_spike > 2:
            pump_stage = "EARLY_PUMP"
            signals.append(f"🚀 بداية ضخ: +{change_1h:.1%} مع حجم {volume_spike:.1f}x")
        
        elif change_4h > 0.10 and volume_spike > 3:
            pump_stage = "ACTIVE_PUMP"
            signals.append(f"🔥 ضخ نشط: +{change_4h:.1%} في 4 ساعات")
        
        elif change_24h > 0.20:
            pump_stage = "LATE_PUMP"
            signals.append(f"⚠️ ضخ متأخر: +{change_24h:.1%} في 24 ساعة - خطر الانهيار")
        
        # RSI في منطقة الشراء المفرط
        if 'rsi' in df.columns:
            rsi = df['rsi'].values[-1]
            if rsi > 80:
                signals.append(f"⚠️ RSI={rsi:.0f} شراء مفرط جداً - قمة وشيكة")
                if pump_stage == "ACTIVE_PUMP":
                    pump_stage = "LATE_PUMP"
        
        is_pump = pump_stage != "NONE"
        
        # توصية بناءً على مرحلة الضخ
        recommendations = {
            "EARLY_PUMP": "🚀 بداية ضخ! يمكن الدخول بحذر مع وقف خسارة ضيق",
            "ACTIVE_PUMP": "⚡ ضخ نشط! إذا دخلت، ضع هدف ربح قريب وخرج سريع",
            "LATE_PUMP": "🚨 ضخ متأخر! خطر الانهيار عالٍ. لا تشتري الآن.",
            "NONE": "😐 لا يوجد ضخ حالياً"
        }
        
        return {
            "is_pump": is_pump,
            "stage": pump_stage,
            "change_1h": change_1h,
            "change_4h": change_4h,
            "change_24h": change_24h,
            "volume_spike": volume_spike,
            "signals": signals,
            "recommendation": recommendations[pump_stage],
            "symbol": symbol
        }
    
    # ============================================================
    # تحليل شامل لحالة السوق
    # ============================================================
    
    def analyze_market_condition(self, df, symbol):
        """
        تحليل شامل لحالة السوق
        يحدد: صعود / هبوط / انهيار / ضخ / تعافي / محايد
        """
        crash = self.detect_crash_signals(df, symbol)
        recovery = self.detect_recovery_signals(df, symbol)
        pump = self.detect_pump_signals(df, symbol)
        
        # تحديد الحالة الرئيسية
        if crash["risk"] in ["CRITICAL", "HIGH"]:
            condition = "CRASH_WARNING"
            action = "AVOID_LONG"
            priority = "URGENT"
        elif recovery["is_recovery"] and recovery["confidence"] > 0.6:
            condition = "RECOVERY"
            action = "BUY_OPPORTUNITY"
            priority = "HIGH"
        elif pump["stage"] == "EARLY_PUMP":
            condition = "PUMP_EARLY"
            action = "CAUTIOUS_BUY"
            priority = "MEDIUM"
        elif pump["stage"] == "LATE_PUMP":
            condition = "PUMP_LATE"
            action = "AVOID_BUY"
            priority = "HIGH"
        else:
            condition = "NORMAL"
            action = "NORMAL_TRADING"
            priority = "LOW"
        
        return {
            "symbol": symbol,
            "condition": condition,
            "action": action,
            "priority": priority,
            "crash_analysis": crash,
            "recovery_analysis": recovery,
            "pump_analysis": pump,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_condition_emoji(self, condition):
        """الحصول على إيموجي لحالة السوق"""
        emojis = {
            "CRASH_WARNING": "🚨",
            "RECOVERY": "🚀",
            "PUMP_EARLY": "⚡",
            "PUMP_LATE": "⚠️",
            "NORMAL": "✅"
        }
        return emojis.get(condition, "❓")
    
    def format_for_telegram(self, analysis):
        """تنسيق التحليل لرسالة Telegram"""
        condition = analysis["condition"]
        emoji = self.get_condition_emoji(condition)
        
        condition_names = {
            "CRASH_WARNING": "تحذير انهيار",
            "RECOVERY": "فرصة تعافي",
            "PUMP_EARLY": "بداية ضخ",
            "PUMP_LATE": "ضخ متأخر",
            "NORMAL": "سوق طبيعي"
        }
        
        msg = f"{emoji} **حالة السوق:** {condition_names.get(condition, condition)}\n"
        
        if analysis["crash_analysis"]["signals"]:
            msg += f"   🔴 إشارات هبوط:\n"
            for s in analysis["crash_analysis"]["signals"][:2]:
                msg += f"      • {s}\n"
        
        if analysis["recovery_analysis"]["is_recovery"]:
            msg += f"   🟢 إشارات تعافي:\n"
            for s in analysis["recovery_analysis"]["signals"][:2]:
                msg += f"      • {s}\n"
        
        if analysis["pump_analysis"]["is_pump"]:
            msg += f"   ⚡ إشارات ضخ:\n"
            for s in analysis["pump_analysis"]["signals"][:2]:
                msg += f"      • {s}\n"
        
        return msg


# اختبار سريع
if __name__ == "__main__":
    engine = CrashRecoveryEngine()
    print("✅ CrashRecoveryEngine initialized successfully")
    print("Thresholds:")
    print(f"  Crash: {engine.crash_threshold:.0%}")
    print(f"  Pump: {engine.pump_threshold:.0%}")
    print(f"  Recovery: {engine.recovery_threshold:.0%}")
