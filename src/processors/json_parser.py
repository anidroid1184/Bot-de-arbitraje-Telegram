"""
JSON Parser for intercepted network requests from Betburger and Surebet.

Extracts arbitrage data directly from API responses captured by PlaywrightCapture,
avoiding HTML parsing for faster, more reliable data extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class RequestJsonParser:
    """Parses JSON from intercepted network requests."""
    
    def __init__(self):
        # Patterns to identify arbitrage-related requests
        self.betburger_patterns = [
            r'/api/.*pro_search',
            r'/api/.*arbs',
            r'/api/.*valuebets'
        ]
        
        self.surebet_patterns = [
            r'/api/',
            r'/valuebets',
            r'/surebets',
            r'/arbs',
            r'/users/'
        ]
    
    def is_arbitrage_request(self, url: str, source: str = None) -> bool:
        """Check if URL contains arbitrage data."""
        if source == "betburger":
            return any(re.search(pattern, url) for pattern in self.betburger_patterns)
        elif source == "surebet":
            return any(re.search(pattern, url) for pattern in self.surebet_patterns)
        else:
            # Auto-detect source
            if "betburger.com" in url:
                return any(re.search(pattern, url) for pattern in self.betburger_patterns)
            elif "surebet.com" in url:
                return any(re.search(pattern, url) for pattern in self.surebet_patterns)
        
        return False
    
    def extract_json_from_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract JSON payload from request data."""
        try:
            # Check if response has JSON content
            if not request_data.get("json_data"):
                return None
            
            json_content = request_data["json_data"]
            
            # Validate it's proper JSON
            if isinstance(json_content, str):
                json_content = json.loads(json_content)
            
            return json_content
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug("Failed to extract JSON from request", error=str(e), url=request_data.get("url"))
            return None
    
    def detect_filter_id(self, json_data: Dict[str, Any], url: str) -> Optional[str]:
        """Detect filter_id from JSON data or URL."""
        # Check JSON for filter_id
        if isinstance(json_data, dict):
            # Direct filter_id field
            if "filter_id" in json_data:
                return str(json_data["filter_id"])
            
            # Nested in data structure
            if "data" in json_data and isinstance(json_data["data"], dict):
                if "filter_id" in json_data["data"]:
                    return str(json_data["data"]["filter_id"])
            
            # Check for common ID patterns
            for key in ["id", "filterId", "profileId", "profile_id"]:
                if key in json_data:
                    return str(json_data[key])
        
        # Extract from URL parameters
        filter_match = re.search(r'filter[_-]?id[=:](\d+)', url)
        if filter_match:
            return filter_match.group(1)
        
        # Extract numeric IDs from URL path
        id_match = re.search(r'/(\d{6,})', url)
        if id_match:
            return id_match.group(1)
        
        return None
    
    def parse_request_batch(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse a batch of intercepted requests for arbitrage data."""
        arbitrage_requests = []
        
        for request_data in requests:
            url = request_data.get("url", "")
            
            # Skip non-arbitrage requests
            if not self.is_arbitrage_request(url):
                continue
            
            # Extract JSON content
            json_content = self.extract_json_from_request(request_data)
            if not json_content:
                continue
            
            # Detect source platform
            source = "betburger" if "betburger.com" in url else "surebet"
            
            # Detect filter_id
            filter_id = self.detect_filter_id(json_content, url)
            
            # Build processed request
            processed_request = {
                "source": source,
                "url": url,
                "method": request_data.get("method", "GET"),
                "status": request_data.get("status"),
                "timestamp": request_data.get("timestamp", datetime.utcnow().isoformat()),
                "json_data": json_content,
                "filter_id": filter_id,
                "raw_request": request_data  # Keep original for debugging
            }
            
            arbitrage_requests.append(processed_request)
            
            logger.info(
                "Parsed arbitrage request",
                source=source,
                url=url,
                filter_id=filter_id,
                has_json=bool(json_content)
            )
        
        return arbitrage_requests


def create_parser() -> RequestJsonParser:
    """Factory function to create JSON parser."""
    return RequestJsonParser()
