#!/usr/bin/env python3
"""
Trade Lak - Multi-Timeframe Confirmation (MTF)
يتحقق من تطابق الإشارات عبر إطارات زمنية متعددة قبل الدخول
"""
import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


@dataclass
class MTFResult:
    """نتيجة تحليل Multi-Timeframe"""
    confirmed: bool             # هل الإشارة مؤكدة؟
    confidence_boost: float     # رفع في الثقة (+0 إلى +0.15)
    score_boost: float          # رفع في النقاط (+0 إلى +1.5)
    aligned_timeframes: int     # عدد الإطارات المتوافقة
    total_timeframes: int       # إجمالي الإطارات المفحوصة
    details: str                # تفاصيل التحليل
    trend_strength: float       # قوة الاتجاه (0-1)


class MultiTimeframeConfirmation:
    """
    نظام تأكيد متعدد الإطارات الزمنية
    
    يفحص الإطارات: 1m, 5m, 15m, 1h, 4h
    ويتحقق من:
    - اتجاه EMA (صاعد/هابط)
    - موضع السعر من EMA50
    - RSI في المنطقة المناسبة
    - MACD يدعم الاتجاه
    """

    # الأوزان لكل إطار زمني (الأطول = أهم)
    TIMEFRAME_WEIGHTS = {
        '1m':  0.05,
        '5m':  0.10,
        '15m': 0.20,
        '1h':  0.30,
        '4h':  0.35,
    }

    def __init__(self):
        self.min_aligned_timeframes = 3   # أدنى عدد إطارات متوافقة للتأكيد
        self.min_weighted_score = 0.55    # 55% وزن مرجح للتأكيد

    def _analyze_single_timeframe(self, df: pd.DataFrame,
                                   direction: str) -> Tuple[bool, float, str]:
        """
        تحليل إطار زمني واحد
        يعود بـ (متوافق, درجة الثقة, السبب)
        """
        if len(df) < 50:
            return False, 0.0, "بيانات غير كافية"

        score = 0.0
        reasons = []
        close = df['close']
        current = close.iloc[-1]

        # 1. EMA Alignment
        ema9 = close.ewm(span=9).mean().iloc[-1]
        ema21 = close.ewm(span=21).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]

        if direction == 'LONG':
            if ema9 > ema21 > ema50:
                score += 0.30
                reasons.append("EMA↑")
            elif ema9 > ema21:
                score += 0.15
                reasons.append("EMA~↑")
            # السعر فوق EMA50
            if current > ema50:
                score += 0.20
                reasons.append("P>EMA50")
        else:  # SHORT
            if ema9 < ema21 < ema50:
                score += 0.30
                reasons.append("EMA↓")
            elif ema9 < ema21:
                score += 0.15
                reasons.append("EMA~↓")
            if current < ema50:
                score += 0.20
                reasons.append("P<EMA50")

        # 2. RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

        if direction == 'LONG':
            if 40 < rsi < 65:
                score += 0.20
                reasons.append(f"RSI={rsi:.0f}✓")
            elif rsi < 40:
                score += 0.10  # ذروة بيع = فرصة
                reasons.append(f"RSI={rsi:.0f}↑")
        else:
            if 35 < rsi < 60:
                score += 0.20
                reasons.append(f"RSI={rsi:.0f}✓")
            elif rsi > 60:
                score += 0.10
                reasons.append(f"RSI={rsi:.0f}↓")

        # 3. MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_hist = macd_line - signal_line

        if direction == 'LONG':
            if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2]:
                score += 0.20
                reasons.append("MACD↑")
            elif macd_hist.iloc[-1] > 0:
                score += 0.10
                reasons.append("MACD+")
        else:
            if macd_hist.iloc[-1] < 0 and macd_hist.iloc[-1] < macd_hist.iloc[-2]:
                score += 0.20
                reasons.append("MACD↓")
            elif macd_hist.iloc[-1] < 0:
                score += 0.10
                reasons.append("MACD-")

        # 4. Volume Trend
        vol_avg = df['volume'].tail(20).mean()
        vol_current = df['volume'].iloc[-1]
        if vol_current > vol_avg * 1.3:
            score += 0.10
            reasons.append("Vol↑")

        aligned = score >= 0.50
        return aligned, score, " ".join(reasons)

    def confirm(self, symbol: str, direction: str,
                timeframe_data: Dict[str, pd.DataFrame]) -> MTFResult:
        """
        تأكيد الإشارة عبر إطارات زمنية متعددة
        
        timeframe_data: قاموس {timeframe: DataFrame}
        """
        try:
            available_tfs = [tf for tf in self.TIMEFRAME_WEIGHTS if tf in timeframe_data]

            if len(available_tfs) < 2:
                # إذا لم تتوفر بيانات كافية، نعطي تأكيداً محايداً
                return MTFResult(
                    confirmed=True,
                    confidence_boost=0.0,
                    score_boost=0.0,
                    aligned_timeframes=0,
                    total_timeframes=0,
                    details="بيانات MTF غير متوفرة",
                    trend_strength=0.5
                )

            results = {}
            weighted_score = 0.0
            total_weight = 0.0
            aligned_count = 0
            detail_parts = []

            for tf in available_tfs:
                weight = self.TIMEFRAME_WEIGHTS[tf]
                aligned, score, reason = self._analyze_single_timeframe(
                    timeframe_data[tf], direction
                )
                results[tf] = (aligned, score, reason)
                weighted_score += score * weight
                total_weight += weight
                if aligned:
                    aligned_count += 1
                detail_parts.append(f"{tf}:{'✅' if aligned else '❌'}({score:.0%})")

            if total_weight > 0:
                weighted_score /= total_weight

            # تحديد التأكيد
            confirmed = (
                aligned_count >= self.min_aligned_timeframes and
                weighted_score >= self.min_weighted_score
            )

            # حساب الرفع في الثقة والنقاط
            if confirmed:
                # كلما زاد التوافق كلما زاد الرفع
                alignment_ratio = aligned_count / len(available_tfs)
                confidence_boost = min(0.12, (alignment_ratio - 0.5) * 0.24)
                score_boost = min(1.5, (weighted_score - 0.5) * 3.0)
                trend_strength = weighted_score
            else:
                confidence_boost = max(-0.10, (weighted_score - 0.55) * 0.2)
                score_boost = max(-1.0, (weighted_score - 0.55) * 2.0)
                trend_strength = weighted_score

            result = MTFResult(
                confirmed=confirmed,
                confidence_boost=confidence_boost,
                score_boost=score_boost,
                aligned_timeframes=aligned_count,
                total_timeframes=len(available_tfs),
                details=" | ".join(detail_parts),
                trend_strength=trend_strength
            )

            status = "✅ مؤكد" if confirmed else "⚠️ غير مؤكد"
            logger.info(
                f"[MTF] {symbol} {direction}: {status} | "
                f"{aligned_count}/{len(available_tfs)} إطارات | "
                f"وزن={weighted_score:.0%} | "
                f"رفع={confidence_boost:+.0%}"
            )

            return result

        except Exception as e:
            logger.error(f"[MTF] ❌ خطأ في {symbol}: {e}")
            return MTFResult(
                confirmed=True, confidence_boost=0.0, score_boost=0.0,
                aligned_timeframes=0, total_timeframes=0,
                details=f"خطأ: {e}", trend_strength=0.5
            )

    def quick_confirm(self, symbol: str, direction: str,
                      df_1h: pd.DataFrame, df_4h: pd.DataFrame) -> MTFResult:
        """
        تأكيد سريع بإطارين فقط (1H + 4H) للأداء السريع
        """
        return self.confirm(symbol, direction, {'1h': df_1h, '4h': df_4h})


# Singleton
_mtf_engine = None

def get_mtf_engine() -> MultiTimeframeConfirmation:
    global _mtf_engine
    if _mtf_engine is None:
        _mtf_engine = MultiTimeframeConfirmation()
    return _mtf_engine
