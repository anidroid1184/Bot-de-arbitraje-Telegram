"""
Normalized data structure for arbitrage alerts from all platforms.

Provides a unified schema for Betburger and Surebet data, enabling
consistent processing through the pipeline regardless of source.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BookmakerSelection:
    """Represents a bookmaker selection with odds."""
    bookmaker: str
    odd: float
    
    def __post_init__(self):
        # Ensure odd is float
        if isinstance(self.odd, str):
            try:
                self.odd = float(self.odd)
            except ValueError:
                logger.warning("Invalid odd value", odd=self.odd, bookmaker=self.bookmaker)
                self.odd = 0.0


@dataclass
class ArbitrageData:
    """Unified arbitrage data structure for all platforms."""
    
    # Core identification
    source: str  # "betburger" | "surebet"
    profile: str
    timestamp_utc: str
    
    # Event details
    sport: Optional[str] = None
    league: Optional[str] = None
    match: Optional[str] = None
    market: Optional[str] = None
    market_details: Optional[str] = None  # Full market description
    
    # Bookmaker selections
    selection_a: Optional[BookmakerSelection] = None
    selection_b: Optional[BookmakerSelection] = None  # None for valuebets
    
    # Profit metrics
    roi_pct: Optional[float] = None      # Betburger arbitrage ROI
    value_pct: Optional[float] = None    # Surebet value percentage
    stake_recommendation: Optional[float] = None  # Recommended stake amount
    
    # Timing data (CRITICAL for client)
    event_start: Optional[str] = None    # ISO datetime string
    time_to_start_minutes: Optional[int] = None  # Minutes until event starts
    is_live: Optional[bool] = None       # Is this a live event
    
    # Links (CRITICAL for client)
    target_link: Optional[str] = None    # Generic link
    bookmaker_links: Optional[Dict[str, str]] = None  # Direct bookmaker links
    
    # Additional data
    filter_id: Optional[str] = None
    competition: Optional[str] = None    # Full competition name
    country: Optional[str] = None        # Country/region
    
    # Metadata
    raw_data: Optional[Dict[str, Any]] = None  # Original JSON for debugging
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        # Ensure timestamp is ISO format
        if self.timestamp_utc and not self.timestamp_utc.endswith('Z'):
            if 'T' not in self.timestamp_utc:
                # Assume it's a simple datetime, add UTC marker
                self.timestamp_utc = f"{self.timestamp_utc}Z"
            elif not (self.timestamp_utc.endswith('Z') or '+' in self.timestamp_utc):
                self.timestamp_utc = f"{self.timestamp_utc}Z"
    
    @property
    def is_arbitrage(self) -> bool:
        """True if this is an arbitrage opportunity (has selection_b)."""
        return self.selection_b is not None
    
    @property
    def is_valuebet(self) -> bool:
        """True if this is a value bet (no selection_b)."""
        return self.selection_b is None
    
    @property
    def profit_percentage(self) -> Optional[float]:
        """Get profit percentage regardless of source."""
        return self.roi_pct if self.roi_pct is not None else self.value_pct
    
    @property
    def minutes_to_start(self) -> Optional[int]:
        """Calculate minutes until event starts."""
        if not self.event_start:
            return None
        
        try:
            from datetime import datetime
            event_time = datetime.fromisoformat(self.event_start.replace('Z', '+00:00'))
            now = datetime.now(event_time.tzinfo)
            delta = event_time - now
            return max(0, int(delta.total_seconds() / 60))
        except:
            return self.time_to_start_minutes
    
    @property
    def urgency_level(self) -> str:
        """Get urgency level based on time to start."""
        minutes = self.minutes_to_start
        if minutes is None:
            return "unknown"
        elif minutes <= 5:
            return "critical"
        elif minutes <= 15:
            return "high"
        elif minutes <= 60:
            return "medium"
        else:
            return "low"
    
    @property
    def primary_bookmaker(self) -> Optional[str]:
        """Get the primary bookmaker name."""
        return self.selection_a.bookmaker if self.selection_a else None
    
    @property
    def secondary_bookmaker(self) -> Optional[str]:
        """Get the secondary bookmaker name (arbitrage only)."""
        return self.selection_b.bookmaker if self.selection_b else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling nested objects."""
        data = asdict(self)
        
        # Convert BookmakerSelection objects to dicts
        if self.selection_a:
            data['selection_a'] = asdict(self.selection_a)
        if self.selection_b:
            data['selection_b'] = asdict(self.selection_b)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageData':
        """Create ArbitrageData from dictionary."""
        # Handle BookmakerSelection objects
        selection_a = None
        if data.get('selection_a'):
            sel_a_data = data['selection_a']
            if isinstance(sel_a_data, dict):
                selection_a = BookmakerSelection(**sel_a_data)
        
        selection_b = None
        if data.get('selection_b'):
            sel_b_data = data['selection_b']
            if isinstance(sel_b_data, dict):
                selection_b = BookmakerSelection(**sel_b_data)
        
        # Create copy of data without selections
        clean_data = {k: v for k, v in data.items() if k not in ['selection_a', 'selection_b']}
        
        return cls(
            selection_a=selection_a,
            selection_b=selection_b,
            **clean_data
        )
    
    @classmethod
    def from_betburger_json(cls, json_data: Dict[str, Any], profile: str = "unknown", filter_id: str = None) -> 'ArbitrageData':
        """Create ArbitrageData from Betburger JSON response."""
        # Extract selections
        selection_a = None
        selection_b = None
        
        # Betburger typically has 'selections' or 'odds' array
        if 'selections' in json_data and len(json_data['selections']) >= 1:
            sel_a = json_data['selections'][0]
            selection_a = BookmakerSelection(
                bookmaker=sel_a.get('bookmaker', 'unknown'),
                odd=float(sel_a.get('odd', 0))
            )
            
            if len(json_data['selections']) >= 2:
                sel_b = json_data['selections'][1]
                selection_b = BookmakerSelection(
                    bookmaker=sel_b.get('bookmaker', 'unknown'),
                    odd=float(sel_b.get('odd', 0))
                )
        
        return cls(
            source="betburger",
            profile=profile,
            timestamp_utc=datetime.utcnow().isoformat() + "Z",
            sport=json_data.get('sport'),
            league=json_data.get('league'),
            match=json_data.get('match'),
            market=json_data.get('market'),
            selection_a=selection_a,
            selection_b=selection_b,
            roi_pct=json_data.get('roi_pct') or json_data.get('profit'),
            event_start=json_data.get('event_start'),
            target_link=json_data.get('target_link') or json_data.get('url'),
            filter_id=filter_id,
            raw_data=json_data
        )
    
    @classmethod
    def from_surebet_json(cls, json_data: Dict[str, Any], profile: str = "unknown", filter_id: str = None) -> 'ArbitrageData':
        """Create ArbitrageData from Surebet JSON response."""
        # Extract selection (Surebet usually has one selection for valuebets)
        selection_a = None
        
        if 'selection' in json_data:
            sel = json_data['selection']
            selection_a = BookmakerSelection(
                bookmaker=sel.get('bookmaker', 'unknown'),
                odd=float(sel.get('odd', 0))
            )
        elif 'bookmaker' in json_data and 'odd' in json_data:
            selection_a = BookmakerSelection(
                bookmaker=json_data.get('bookmaker', 'unknown'),
                odd=float(json_data.get('odd', 0))
            )
        
        return cls(
            source="surebet",
            profile=profile,
            timestamp_utc=datetime.utcnow().isoformat() + "Z",
            sport=json_data.get('sport'),
            league=json_data.get('league'),
            match=json_data.get('match'),
            market=json_data.get('market'),
            selection_a=selection_a,
            selection_b=None,  # Surebet valuebets typically have one selection
            value_pct=json_data.get('value_pct') or json_data.get('value'),
            target_link=json_data.get('target_link') or json_data.get('url'),
            filter_id=filter_id,
            raw_data=json_data
        )
