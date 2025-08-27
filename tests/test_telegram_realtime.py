"""
Real-time test for Telegram sender with enhanced arbitrage data.

This test creates realistic arbitrage data with all critical fields
and sends it to Telegram to verify the formatting and data extraction.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processors.arbitrage_data import ArbitrageData, BookmakerSelection
from notifications.telegram_sender import TelegramSender


def create_realistic_betburger_alert():
    """Create realistic Betburger arbitrage alert with all critical data."""
    
    # Event starts in 45 minutes
    event_start = (datetime.utcnow() + timedelta(minutes=45)).isoformat() + "Z"
    
    return ArbitrageData(
        source="betburger",
        profile="premium_football",
        timestamp_utc=datetime.utcnow().isoformat() + "Z",
        
        # Event details
        sport="football",
        league="Premier League",
        match="Arsenal vs Chelsea",
        market="1X2",
        market_details="Full Time Result - Home Win",
        competition="English Premier League 2025/26",
        country="England",
        
        # Bookmaker selections
        selection_a=BookmakerSelection(bookmaker="bet365", odd=2.15),
        selection_b=BookmakerSelection(bookmaker="pinnacle", odd=1.92),
        
        # Profit metrics
        roi_pct=4.8,
        stake_recommendation=250.0,
        
        # Timing (CRITICAL)
        event_start=event_start,
        time_to_start_minutes=45,
        is_live=False,
        
        # Links (CRITICAL)
        target_link="https://betburger.com/arb/12345",
        bookmaker_links={
            "bet365": "https://bet365.com/sport/football/12345",
            "pinnacle": "https://pinnacle.com/en/soccer/england/premier-league/arsenal-vs-chelsea/123456"
        },
        
        # Additional data
        filter_id="1218070",
        
        # Raw data for debugging
        raw_data={
            "original_url": "https://betburger.com/api/pro_search",
            "detected_at": datetime.utcnow().isoformat()
        }
    )


def create_realistic_surebet_alert():
    """Create realistic Surebet valuebet alert with all critical data."""
    
    # Event starts in 15 minutes (high urgency)
    event_start = (datetime.utcnow() + timedelta(minutes=15)).isoformat() + "Z"
    
    return ArbitrageData(
        source="surebet",
        profile="tennis_valuebets",
        timestamp_utc=datetime.utcnow().isoformat() + "Z",
        
        # Event details
        sport="tennis",
        league="ATP Masters 1000",
        match="Djokovic vs Alcaraz",
        market="Winner",
        market_details="Match Winner - Djokovic",
        competition="ATP Masters 1000 Miami",
        country="USA",
        
        # Bookmaker selection (valuebet has only one)
        selection_a=BookmakerSelection(bookmaker="pinnacle", odd=2.75),
        selection_b=None,  # No second selection for valuebets
        
        # Profit metrics
        value_pct=8.3,
        stake_recommendation=150.0,
        
        # Timing (CRITICAL - high urgency)
        event_start=event_start,
        time_to_start_minutes=15,
        is_live=False,
        
        # Links (CRITICAL)
        target_link="https://surebet.com/valuebet/67890",
        bookmaker_links={
            "pinnacle": "https://pinnacle.com/en/tennis/atp/miami/djokovic-vs-alcaraz/789012"
        },
        
        # Additional data
        filter_id="sb_tennis_001",
        
        # Raw data for debugging
        raw_data={
            "original_url": "https://es.surebet.com/api/valuebets",
            "detected_at": datetime.utcnow().isoformat()
        }
    )


def create_critical_urgency_alert():
    """Create critical urgency alert (starts in 3 minutes)."""
    
    # Event starts in 3 minutes (CRITICAL)
    event_start = (datetime.utcnow() + timedelta(minutes=3)).isoformat() + "Z"
    
    return ArbitrageData(
        source="betburger",
        profile="live_alerts",
        timestamp_utc=datetime.utcnow().isoformat() + "Z",
        
        # Event details
        sport="basketball",
        league="NBA",
        match="Lakers vs Warriors",
        market="Total Points",
        market_details="Total Points Over 215.5",
        
        # Bookmaker selections
        selection_a=BookmakerSelection(bookmaker="draftkings", odd=1.95),
        selection_b=BookmakerSelection(bookmaker="fanduel", odd=2.05),
        
        # Profit metrics
        roi_pct=6.2,
        stake_recommendation=500.0,
        
        # Timing (CRITICAL URGENCY)
        event_start=event_start,
        time_to_start_minutes=3,
        is_live=False,
        
        # Links
        bookmaker_links={
            "draftkings": "https://draftkings.com/bet/nba/lakers-warriors/123",
            "fanduel": "https://fanduel.com/bet/nba/lakers-warriors/456"
        },
        
        filter_id="live_nba_001"
    )


def test_telegram_formatting():
    """Test message formatting without sending."""
    print("🧪 Testing Telegram Message Formatting...\n")
    
    sender = TelegramSender()  # No token needed for formatting test
    
    # Test different alert types
    alerts = [
        ("Betburger Football (Medium Urgency)", create_realistic_betburger_alert()),
        ("Surebet Tennis (High Urgency)", create_realistic_surebet_alert()),
        ("Critical NBA Alert (3 min)", create_critical_urgency_alert())
    ]
    
    for name, alert in alerts:
        print(f"📋 {name}:")
        print("=" * 50)
        message = sender.format_arbitrage_message(alert)
        print(message)
        print("\n" + "=" * 50 + "\n")


def test_telegram_send_real():
    """Send real alerts to Telegram for verification."""
    print("📱 Testing Real Telegram Sending...\n")
    
    # Check for bot token
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment")
        print("Set it with: export TELEGRAM_BOT_TOKEN='your_token_here'")
        return False
    
    # Check for test channel
    test_channel = os.environ.get("TELEGRAM_TEST_CHANNEL")
    if not test_channel:
        print("❌ TELEGRAM_TEST_CHANNEL not found in environment")
        print("Set it with: export TELEGRAM_TEST_CHANNEL='@your_test_channel'")
        return False
    
    sender = TelegramSender(bot_token)
    
    # Send test message first
    print("📤 Sending test message...")
    if sender.send_test_message(test_channel):
        print("✅ Test message sent successfully")
    else:
        print("❌ Failed to send test message")
        return False
    
    # Send realistic alerts
    alerts = [
        create_realistic_betburger_alert(),
        create_realistic_surebet_alert(),
        create_critical_urgency_alert()
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"📤 Sending alert {i}/3 ({alert.source} - {alert.sport})...")
        
        if sender.send_alert(alert, test_channel):
            print(f"✅ Alert {i} sent successfully")
        else:
            print(f"❌ Failed to send alert {i}")
        
        # Small delay between messages
        import time
        time.sleep(2)
    
    print("\n🎉 All alerts sent! Check your Telegram channel.")
    return True


def main():
    """Run Telegram real-time tests."""
    print("🚀 Telegram Real-Time Testing\n")
    
    # Always test formatting
    test_telegram_formatting()
    
    # Ask user if they want to send real messages
    print("Do you want to send real messages to Telegram? (y/n): ", end="")
    try:
        response = input().strip().lower()
        if response in ['y', 'yes']:
            test_telegram_send_real()
        else:
            print("📋 Formatting test completed. Set environment variables to test real sending.")
    except KeyboardInterrupt:
        print("\n👋 Test cancelled by user")


if __name__ == "__main__":
    main()
