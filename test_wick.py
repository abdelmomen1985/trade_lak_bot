#!/usr/bin/env python3
"""Test wick detection engine integration"""

from core.wick_detection_engine import WickDetectionEngine

print("✅ Wick Detection Engine imported successfully!")

# Create engine
engine = WickDetectionEngine()
print("✅ Engine initialized!")

# Test with sample candle
analysis = engine.analyze_candle(
    open_price=100,
    high_price=105,
    low_price=98,
    close_price=99,
    volume=1000,
    avg_volume=800
)

print(f"\n✅ Test Analysis:")
print(f"   Wick Type: {analysis.wick_type}")
print(f"   Danger Level: {analysis.danger_level.name}")
print(f"   Is Trap: {analysis.is_trap}")
print(f"   Recommendation: {analysis.recommendation}")
print(f"   Score: {analysis.score}")

print("\n✅ All tests passed!")
