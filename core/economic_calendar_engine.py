"""
Economic Calendar Engine
محرك مراقبة الأحداث الاقتصادية والتقارير
Monitors economic events, forecasts, and market impact
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import requests
import logging

logger = logging.getLogger(__name__)


class EventImpact(Enum):
    """Event impact levels"""
    LOW = "Low"              # منخفض
    MEDIUM = "Medium"        # متوسط
    HIGH = "High"            # عالي
    VERY_HIGH = "Very High"  # عالي جداً
    CRITICAL = "Critical"    # حرج


class EventType(Enum):
    """Types of economic events"""
    INTEREST_RATE = "Interest Rate"              # سعر الفائدة
    UNEMPLOYMENT = "Unemployment"                # البطالة
    INFLATION = "Inflation"                      # التضخم
    GDP = "GDP"                                  # الناتج المحلي الإجمالي
    EMPLOYMENT = "Employment"                    # التوظيف
    RETAIL_SALES = "Retail Sales"                # المبيعات بالتجزئة
    HOUSING = "Housing"                          # الإسكان
    MANUFACTURING = "Manufacturing"              # التصنيع
    TRADE = "Trade"                              # التجارة
    CONSUMER_CONFIDENCE = "Consumer Confidence"  # ثقة المستهلك
    PMI = "PMI"                                  # مؤشر مديري المشتريات
    CENTRAL_BANK = "Central Bank"                # البنك المركزي
    EARNINGS = "Earnings"                        # الأرباح
    OTHER = "Other"                              # أخرى


@dataclass
class EconomicEvent:
    """Economic event data"""
    event_id: str
    name: str                    # اسم الحدث
    event_type: EventType
    country: str                 # الدولة (USD, EUR, GBP, JPY, etc.)
    scheduled_time: datetime     # الوقت المجدول
    impact: EventImpact          # درجة التأثير
    forecast: float              # التنبؤ
    previous: float              # القيمة السابقة
    actual: Optional[float] = None  # القيمة الفعلية (بعد الإعلان)
    unit: str = ""               # الوحدة (%, M, B, etc.)
    importance: int = 0          # درجة الأهمية (0-100)
    volatility_expected: float = 0.0  # التذبذب المتوقع


@dataclass
class EventAlert:
    """Alert for upcoming event"""
    event: EconomicEvent
    time_until: timedelta        # الوقت المتبقي
    action: str                  # الإجراء المقترح
    recommendation: str          # التوصية
    risk_level: str              # مستوى الخطر


@dataclass
class EventImpactAnalysis:
    """Analysis of event impact on market"""
    event: EconomicEvent
    expected_volatility: float   # التذبذب المتوقع (0-100)
    affected_pairs: List[str]    # العملات المتأثرة
    buy_pressure: float          # ضغط الشراء (-100 to +100)
    sell_pressure: float         # ضغط البيع (-100 to +100)
    recommendation: str          # التوصية
    confidence: float            # الثقة (0-1)


class EconomicCalendarEngine:
    """Monitors and analyzes economic events"""
    
    def __init__(self):
        """Initialize economic calendar engine"""
        self.events = []
        self.historical_events = []
        self.event_impacts = {}
        self.upcoming_events = []
        self.load_calendar()
    
    def load_calendar(self):
        """Load economic calendar events"""
        # Hard-coded major economic events for 2026
        self.events = [
            # Federal Reserve Events
            EconomicEvent(
                event_id="FED_RATE_001",
                name="FOMC Interest Rate Decision",
                event_type=EventType.INTEREST_RATE,
                country="USD",
                scheduled_time=datetime(2026, 6, 16, 18, 0),
                impact=EventImpact.CRITICAL,
                forecast=5.25,
                previous=5.25,
                unit="%",
                importance=100,
                volatility_expected=2.5
            ),
            EconomicEvent(
                event_id="FED_RATE_002",
                name="FOMC Interest Rate Decision",
                event_type=EventType.INTEREST_RATE,
                country="USD",
                scheduled_time=datetime(2026, 7, 28, 18, 0),
                impact=EventImpact.CRITICAL,
                forecast=5.25,
                previous=5.25,
                unit="%",
                importance=100,
                volatility_expected=2.5
            ),
            
            # US Employment Data
            EconomicEvent(
                event_id="NFP_001",
                name="Non-Farm Payroll",
                event_type=EventType.EMPLOYMENT,
                country="USD",
                scheduled_time=datetime(2026, 6, 5, 12, 30),
                impact=EventImpact.VERY_HIGH,
                forecast=200000,
                previous=175000,
                unit="K",
                importance=95,
                volatility_expected=1.8
            ),
            EconomicEvent(
                event_id="UNEMP_001",
                name="Unemployment Rate",
                event_type=EventType.UNEMPLOYMENT,
                country="USD",
                scheduled_time=datetime(2026, 6, 5, 12, 30),
                impact=EventImpact.VERY_HIGH,
                forecast=3.9,
                previous=3.9,
                unit="%",
                importance=90,
                volatility_expected=1.5
            ),
            
            # US Inflation Data
            EconomicEvent(
                event_id="CPI_001",
                name="Consumer Price Index (CPI)",
                event_type=EventType.INFLATION,
                country="USD",
                scheduled_time=datetime(2026, 6, 10, 12, 30),
                impact=EventImpact.VERY_HIGH,
                forecast=3.2,
                previous=3.4,
                unit="%",
                importance=95,
                volatility_expected=2.0
            ),
            EconomicEvent(
                event_id="PPI_001",
                name="Producer Price Index (PPI)",
                event_type=EventType.INFLATION,
                country="USD",
                scheduled_time=datetime(2026, 6, 11, 12, 30),
                impact=EventImpact.HIGH,
                forecast=2.8,
                previous=3.0,
                unit="%",
                importance=80,
                volatility_expected=1.2
            ),
            
            # ECB Events
            EconomicEvent(
                event_id="ECB_RATE_001",
                name="ECB Interest Rate Decision",
                event_type=EventType.INTEREST_RATE,
                country="EUR",
                scheduled_time=datetime(2026, 6, 17, 13, 0),
                impact=EventImpact.CRITICAL,
                forecast=4.00,
                previous=4.00,
                unit="%",
                importance=100,
                volatility_expected=2.0
            ),
            
            # Bank of England Events
            EconomicEvent(
                event_id="BOE_RATE_001",
                name="Bank of England Interest Rate",
                event_type=EventType.INTEREST_RATE,
                country="GBP",
                scheduled_time=datetime(2026, 6, 18, 12, 0),
                impact=EventImpact.CRITICAL,
                forecast=5.25,
                previous=5.25,
                unit="%",
                importance=100,
                volatility_expected=1.8
            ),
            
            # Bank of Japan Events
            EconomicEvent(
                event_id="BOJ_RATE_001",
                name="Bank of Japan Interest Rate",
                event_type=EventType.INTEREST_RATE,
                country="JPY",
                scheduled_time=datetime(2026, 7, 29, 6, 0),
                impact=EventImpact.CRITICAL,
                forecast=-0.10,
                previous=-0.10,
                unit="%",
                importance=100,
                volatility_expected=2.2
            ),
            
            # GDP Data
            EconomicEvent(
                event_id="GDP_US_001",
                name="US GDP (Preliminary)",
                event_type=EventType.GDP,
                country="USD",
                scheduled_time=datetime(2026, 6, 25, 12, 30),
                impact=EventImpact.VERY_HIGH,
                forecast=2.5,
                previous=2.4,
                unit="%",
                importance=90,
                volatility_expected=1.5
            ),
            
            # Retail Sales
            EconomicEvent(
                event_id="RETAIL_001",
                name="Retail Sales",
                event_type=EventType.RETAIL_SALES,
                country="USD",
                scheduled_time=datetime(2026, 6, 15, 12, 30),
                impact=EventImpact.HIGH,
                forecast=0.3,
                previous=0.1,
                unit="%",
                importance=80,
                volatility_expected=1.0
            ),
            
            # Manufacturing PMI
            EconomicEvent(
                event_id="PMI_MFG_001",
                name="Manufacturing PMI",
                event_type=EventType.PMI,
                country="USD",
                scheduled_time=datetime(2026, 6, 1, 13, 45),
                impact=EventImpact.MEDIUM,
                forecast=52.5,
                previous=52.0,
                unit="",
                importance=70,
                volatility_expected=0.8
            ),
            
            # Services PMI
            EconomicEvent(
                event_id="PMI_SVC_001",
                name="Services PMI",
                event_type=EventType.PMI,
                country="USD",
                scheduled_time=datetime(2026, 6, 5, 13, 45),
                impact=EventImpact.MEDIUM,
                forecast=54.0,
                previous=53.5,
                unit="",
                importance=70,
                volatility_expected=0.8
            ),
        ]
        
        logger.info(f"✅ تم تحميل {len(self.events)} حدث اقتصادي")
    
    def get_upcoming_events(self, hours_ahead: int = 24) -> List[EventAlert]:
        """Get upcoming events in the next N hours"""
        now = datetime.now()
        upcoming = []
        
        for event in self.events:
            time_until = event.scheduled_time - now
            
            # Only include future events within the time window
            if timedelta(0) <= time_until <= timedelta(hours=hours_ahead):
                # Determine action based on impact and time
                if time_until < timedelta(hours=1):
                    action = "🚨 IMMINENT"
                    recommendation = f"❌ تجنب التداول! الحدث بعد {time_until.seconds // 60} دقيقة"
                    risk_level = "CRITICAL"
                elif time_until < timedelta(hours=4):
                    action = "⚠️ SOON"
                    recommendation = f"⚠️ كن حذراً! الحدث بعد {time_until.seconds // 3600} ساعات"
                    risk_level = "HIGH"
                else:
                    action = "📢 UPCOMING"
                    recommendation = f"📢 حدث قادم: {event.name}"
                    risk_level = "MEDIUM"
                
                alert = EventAlert(
                    event=event,
                    time_until=time_until,
                    action=action,
                    recommendation=recommendation,
                    risk_level=risk_level
                )
                upcoming.append(alert)
        
        # Sort by time
        upcoming.sort(key=lambda x: x.time_until)
        return upcoming
    
    def analyze_event_impact(self, event: EconomicEvent) -> EventImpactAnalysis:
        """Analyze expected impact of an economic event"""
        
        # Impact mapping
        impact_volatility_map = {
            EventImpact.LOW: 0.3,
            EventImpact.MEDIUM: 0.8,
            EventImpact.HIGH: 1.5,
            EventImpact.VERY_HIGH: 2.2,
            EventImpact.CRITICAL: 3.0
        }
        
        # Currency-specific pairs
        currency_pairs = {
            'USD': ['BTC/USDT', 'ETH/USDT', 'EURUSD', 'GBPUSD', 'JPYUSD'],
            'EUR': ['EURUSD', 'EURGBP', 'EURJPY'],
            'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY'],
            'JPY': ['JPYUSD', 'EURJPY', 'GBPJPY']
        }
        
        # Calculate expected volatility
        base_volatility = impact_volatility_map.get(event.impact, 1.0)
        expected_volatility = base_volatility * event.volatility_expected
        
        # Determine buy/sell pressure based on forecast vs previous
        if event.forecast > event.previous:
            buy_pressure = (event.forecast - event.previous) / event.previous * 100
            sell_pressure = -buy_pressure * 0.3
        elif event.forecast < event.previous:
            sell_pressure = (event.previous - event.forecast) / event.previous * 100
            buy_pressure = -sell_pressure * 0.3
        else:
            buy_pressure = 0
            sell_pressure = 0
        
        # Get affected pairs
        affected_pairs = currency_pairs.get(event.country, [])
        
        # Generate recommendation
        if event.impact == EventImpact.CRITICAL:
            recommendation = f"🚫 تجنب التداول تماماً! حدث حرج: {event.name}"
            confidence = 0.95
        elif event.impact == EventImpact.VERY_HIGH:
            if buy_pressure > 0:
                recommendation = f"🟢 توقع ضغط شراء قوي على {event.country}"
            else:
                recommendation = f"🔴 توقع ضغط بيع قوي على {event.country}"
            confidence = 0.85
        elif event.impact == EventImpact.HIGH:
            recommendation = f"⚠️ توقع تذبذب على {event.country}"
            confidence = 0.75
        else:
            recommendation = f"📊 حدث اقتصادي: {event.name}"
            confidence = 0.60
        
        analysis = EventImpactAnalysis(
            event=event,
            expected_volatility=min(expected_volatility * 100, 100),
            affected_pairs=affected_pairs,
            buy_pressure=buy_pressure,
            sell_pressure=sell_pressure,
            recommendation=recommendation,
            confidence=confidence
        )
        
        return analysis
    
    def should_trade_during_event(self, event: EconomicEvent) -> Tuple[bool, str, float]:
        """Determine if it's safe to trade during an event"""
        
        now = datetime.now()
        time_until = event.scheduled_time - now
        
        # Don't trade within 1 hour before event
        if time_until < timedelta(hours=1) and time_until > timedelta(0):
            return False, f"🚫 لا تتداول! الحدث بعد {time_until.seconds // 60} دقيقة", 0.0
        
        # Don't trade during critical events
        if event.impact in (EventImpact.CRITICAL, EventImpact.VERY_HIGH):
            if time_until < timedelta(hours=2):
                return False, f"🚫 لا تتداول! حدث حرج قادم", 0.0
        
        # Can trade during low/medium impact events
        if event.impact in (EventImpact.LOW, EventImpact.MEDIUM):
            return True, f"✅ يمكن التداول. حدث منخفض التأثير", 0.7
        
        return True, f"⚠️ كن حذراً. حدث اقتصادي قادم", 0.5
    
    def get_event_by_id(self, event_id: str) -> Optional[EconomicEvent]:
        """Get event by ID"""
        for event in self.events:
            if event.event_id == event_id:
                return event
        return None
    
    def get_events_by_country(self, country: str) -> List[EconomicEvent]:
        """Get events for a specific country"""
        return [e for e in self.events if e.country == country]
    
    def get_events_by_type(self, event_type: EventType) -> List[EconomicEvent]:
        """Get events by type"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_by_impact(self, impact: EventImpact) -> List[EconomicEvent]:
        """Get events by impact level"""
        return [e for e in self.events if e.impact == impact]
    
    def record_actual_result(self, event_id: str, actual_value: float):
        """Record actual event result for learning"""
        event = self.get_event_by_id(event_id)
        if event:
            event.actual = actual_value
            
            # Calculate accuracy
            forecast_error = abs(event.actual - event.forecast) / event.forecast * 100
            logger.info(f"📊 {event.name}: Forecast={event.forecast}, Actual={actual_value}, Error={forecast_error:.1f}%")
            
            self.historical_events.append(event)
    
    def get_calendar_summary(self, days_ahead: int = 7) -> Dict:
        """Get calendar summary for next N days"""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)
        
        events_in_range = [
            e for e in self.events
            if now <= e.scheduled_time <= end_date
        ]
        
        # Group by impact
        by_impact = {}
        for impact in EventImpact:
            by_impact[impact.value] = [
                e for e in events_in_range if e.impact == impact
            ]
        
        # Group by country
        by_country = {}
        for event in events_in_range:
            if event.country not in by_country:
                by_country[event.country] = []
            by_country[event.country].append(event)
        
        return {
            'total_events': len(events_in_range),
            'by_impact': by_impact,
            'by_country': by_country,
            'critical_count': len(by_impact.get('Critical', [])),
            'very_high_count': len(by_impact.get('Very High', [])),
            'high_count': len(by_impact.get('High', []))
        }
    
    def get_status(self) -> Dict:
        """Get engine status"""
        upcoming = self.get_upcoming_events(hours_ahead=24)
        
        return {
            'total_events': len(self.events),
            'upcoming_24h': len(upcoming),
            'historical_events': len(self.historical_events),
            'next_event': upcoming[0].event.name if upcoming else 'None',
            'next_event_time': upcoming[0].event.scheduled_time if upcoming else None
        }


# Example usage
if __name__ == "__main__":
    engine = EconomicCalendarEngine()
    
    print("\n" + "="*80)
    print("📅 Economic Calendar Engine - Test")
    print("="*80)
    
    # Get upcoming events
    print("\n🔔 الأحداث القادمة (24 ساعة):")
    print("-" * 80)
    upcoming = engine.get_upcoming_events(hours_ahead=24)
    if upcoming:
        for alert in upcoming[:5]:
            print(f"\n{alert.action} {alert.event.name}")
            print(f"   الوقت: {alert.event.scheduled_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"   التأثير: {alert.event.impact.value}")
            print(f"   التوصية: {alert.recommendation}")
    else:
        print("   ✅ لا توجد أحداث في الـ 24 ساعة القادمة")
    
    # Get calendar summary
    print("\n\n📊 ملخص التقويم (7 أيام):")
    print("-" * 80)
    summary = engine.get_calendar_summary(days_ahead=7)
    print(f"إجمالي الأحداث: {summary['total_events']}")
    print(f"أحداث حرجة: {summary['critical_count']}")
    print(f"أحداث عالية جداً: {summary['very_high_count']}")
    print(f"أحداث عالية: {summary['high_count']}")
    
    # Analyze specific event
    print("\n\n📈 تحليل حدث محدد:")
    print("-" * 80)
    fed_event = engine.get_event_by_id("FED_RATE_001")
    if fed_event:
        analysis = engine.analyze_event_impact(fed_event)
        print(f"الحدث: {fed_event.name}")
        print(f"الوقت: {fed_event.scheduled_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"التأثير المتوقع: {analysis.expected_volatility:.1f}%")
        print(f"العملات المتأثرة: {', '.join(analysis.affected_pairs)}")
        print(f"ضغط الشراء: {analysis.buy_pressure:+.1f}")
        print(f"ضغط البيع: {analysis.sell_pressure:+.1f}")
        print(f"التوصية: {analysis.recommendation}")
        print(f"الثقة: {analysis.confidence:.0%}")
    
    # Events by country
    print("\n\n🌍 الأحداث حسب الدول:")
    print("-" * 80)
    for country in ['USD', 'EUR', 'GBP', 'JPY']:
        events = engine.get_events_by_country(country)
        if events:
            print(f"{country}: {len(events)} أحداث")
            for event in events[:2]:
                print(f"   • {event.name} ({event.impact.value})")
    
    # Events by impact
    print("\n\n⚠️ الأحداث حسب التأثير:")
    print("-" * 80)
    critical = engine.get_events_by_impact(EventImpact.CRITICAL)
    very_high = engine.get_events_by_impact(EventImpact.VERY_HIGH)
    high = engine.get_events_by_impact(EventImpact.HIGH)
    
    print(f"🚫 حرج: {len(critical)} أحداث")
    print(f"🔴 عالي جداً: {len(very_high)} أحداث")
    print(f"🟠 عالي: {len(high)} أحداث")
    
    # Engine status
    print("\n\n📊 حالة المحرك:")
    print("-" * 80)
    status = engine.get_status()
    print(f"إجمالي الأحداث: {status['total_events']}")
    print(f"الأحداث القادمة (24 ساعة): {status['upcoming_24h']}")
    print(f"الأحداث التاريخية: {status['historical_events']}")
    print(f"الحدث التالي: {status['next_event']}")
    
    print("\n" + "="*80)
