"""
Test suite for data processors - JSON Parser and ArbitrageData.

Tests the Pipeline JSON components with sample data to ensure
proper extraction and normalization of arbitrage data.
"""
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processors.json_parser import RequestJsonParser
from processors.arbitrage_data import ArbitrageData, BookmakerSelection


def test_json_parser_betburger():
    """Test JSON parser with Betburger-like request data."""
    parser = RequestJsonParser()
    
    # Mock intercepted request data
    mock_request = {
        "url": "https://betburger.com/api/pro_search?filter_id=1218070",
        "method": "POST",
        "status": 200,
        "timestamp": "2025-08-27T22:30:00Z",
        "json_data": {
            "sport": "football",
            "league": "La Liga",
            "match": "Team A vs Team B",
            "market": "1X2",
            "selections": [
                {"bookmaker": "bet365", "odd": 2.10},
                {"bookmaker": "winamax", "odd": 1.85}
            ],
            "roi_pct": 4.2,
            "target_link": "https://bet365.com/redirect"
        }
    }
    
    # Test URL pattern detection
    assert parser.is_arbitrage_request(mock_request["url"], "betburger")
    
    # Test JSON extraction
    json_content = parser.extract_json_from_request(mock_request)
    assert json_content is not None
    assert json_content["sport"] == "football"
    
    # Test filter_id detection
    filter_id = parser.detect_filter_id(json_content, mock_request["url"])
    assert filter_id == "1218070"
    
    # Test batch parsing
    processed = parser.parse_request_batch([mock_request])
    assert len(processed) == 1
    assert processed[0]["source"] == "betburger"
    assert processed[0]["filter_id"] == "1218070"
    
    print("✅ JSON Parser Betburger test passed")


def test_json_parser_surebet():
    """Test JSON parser with Surebet-like request data."""
    parser = RequestJsonParser()
    
    # Mock intercepted request data
    mock_request = {
        "url": "https://es.surebet.com/api/valuebets",
        "method": "GET", 
        "status": 200,
        "timestamp": "2025-08-27T22:30:00Z",
        "json_data": {
            "sport": "tennis",
            "league": "ATP",
            "match": "Player A vs Player B",
            "market": "Winner",
            "bookmaker": "pinnacle",
            "odd": 2.50,
            "value_pct": 6.5,
            "target_link": "https://pinnacle.com/redirect"
        }
    }
    
    # Test URL pattern detection
    assert parser.is_arbitrage_request(mock_request["url"], "surebet")
    
    # Test JSON extraction
    json_content = parser.extract_json_from_request(mock_request)
    assert json_content is not None
    assert json_content["sport"] == "tennis"
    
    # Test batch parsing
    processed = parser.parse_request_batch([mock_request])
    assert len(processed) == 1
    assert processed[0]["source"] == "surebet"
    
    print("✅ JSON Parser Surebet test passed")


def test_arbitrage_data_betburger():
    """Test ArbitrageData creation from Betburger JSON."""
    
    # Sample Betburger JSON
    betburger_json = {
        "sport": "football",
        "league": "Premier League",
        "match": "Arsenal vs Chelsea",
        "market": "1X2",
        "selections": [
            {"bookmaker": "bet365", "odd": 2.10},
            {"bookmaker": "pinnacle", "odd": 1.95}
        ],
        "roi_pct": 3.8,
        "event_start": "2025-08-28T15:00:00Z",
        "target_link": "https://bet365.com/redirect"
    }
    
    # Create ArbitrageData
    arb_data = ArbitrageData.from_betburger_json(
        betburger_json, 
        profile="premium_arbs",
        filter_id="1218070"
    )
    
    # Test properties
    assert arb_data.source == "betburger"
    assert arb_data.profile == "premium_arbs"
    assert arb_data.sport == "football"
    assert arb_data.is_arbitrage == True
    assert arb_data.is_valuebet == False
    assert arb_data.profit_percentage == 3.8
    assert arb_data.primary_bookmaker == "bet365"
    assert arb_data.secondary_bookmaker == "pinnacle"
    assert arb_data.filter_id == "1218070"
    
    # Test to_dict conversion
    data_dict = arb_data.to_dict()
    assert data_dict["source"] == "betburger"
    assert data_dict["selection_a"]["bookmaker"] == "bet365"
    
    print("✅ ArbitrageData Betburger test passed")


def test_arbitrage_data_surebet():
    """Test ArbitrageData creation from Surebet JSON."""
    
    # Sample Surebet JSON
    surebet_json = {
        "sport": "tennis",
        "league": "WTA",
        "match": "Player A vs Player B", 
        "market": "Winner",
        "bookmaker": "pinnacle",
        "odd": 2.75,
        "value_pct": 8.2,
        "target_link": "https://pinnacle.com/redirect"
    }
    
    # Create ArbitrageData
    arb_data = ArbitrageData.from_surebet_json(
        surebet_json,
        profile="value_tennis",
        filter_id="sb_001"
    )
    
    # Test properties
    assert arb_data.source == "surebet"
    assert arb_data.profile == "value_tennis"
    assert arb_data.sport == "tennis"
    assert arb_data.is_arbitrage == False
    assert arb_data.is_valuebet == True
    assert arb_data.profit_percentage == 8.2
    assert arb_data.primary_bookmaker == "pinnacle"
    assert arb_data.secondary_bookmaker is None
    assert arb_data.filter_id == "sb_001"
    
    print("✅ ArbitrageData Surebet test passed")


def test_with_sample_files():
    """Test with existing sample JSON files."""
    samples_dir = Path(__file__).parent.parent / "samples"
    
    # Test Betburger sample
    betburger_file = samples_dir / "betburger_valid.json"
    if betburger_file.exists():
        with open(betburger_file) as f:
            sample_data = json.load(f)
        
        # Convert to ArbitrageData using from_dict
        arb_data = ArbitrageData.from_dict(sample_data)
        assert arb_data.source == "betburger"
        assert arb_data.roi_pct == 4.2
        print("✅ Betburger sample file test passed")
    
    # Test Surebet sample
    surebet_file = samples_dir / "surebet_valid.json"
    if surebet_file.exists():
        with open(surebet_file) as f:
            sample_data = json.load(f)
        
        # Convert to ArbitrageData using from_dict
        arb_data = ArbitrageData.from_dict(sample_data)
        assert arb_data.source == "surebet"
        assert arb_data.value_pct == 6.5
        print("✅ Surebet sample file test passed")


def run_all_tests():
    """Run all processor tests."""
    print("🧪 Running Data Processor Tests...\n")
    
    try:
        test_json_parser_betburger()
        test_json_parser_surebet()
        test_arbitrage_data_betburger()
        test_arbitrage_data_surebet()
        test_with_sample_files()
        
        print("\n🎉 All tests passed! Data Processors are working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
