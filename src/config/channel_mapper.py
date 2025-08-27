"""
Channel mapper for Telegram notifications based on filters and profiles.

Loads configuration from YAML file and maps arbitrage data to appropriate channels
based on platform, profile, and filter criteria.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class ChannelMapper:
    """Maps arbitrage alerts to Telegram channels based on configuration."""
    
    def __init__(self, config_path: str = None):
        """Initialize channel mapper with configuration file."""
        if config_path is None:
            # Look for config in src/config folder first, then deprecated
            src_config = Path(__file__).parent / "config-configurada.yml"
            deprecated_config = Path(__file__).parent.parent.parent / "deprecated" / "config-configurada.yml"
            
            if src_config.exists():
                config_path = src_config
            elif deprecated_config.exists():
                config_path = deprecated_config
            else:
                config_path = src_config  # Default fallback
        
        self.config_path = Path(config_path)
        self.config = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.error("Configuration file not found", path=str(self.config_path))
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            logger.info("Configuration loaded successfully", 
                       betburger_profiles=len(self.config.get('betburger_profiles', {})),
                       surebet_profiles=len(self.config.get('surebet_profiles', {})))
            
            return True
            
        except Exception as e:
            logger.error("Failed to load configuration", error=str(e), path=str(self.config_path))
            return False
    
    def get_channel_for_profile(self, source: str, profile: str) -> Optional[str]:
        """Get Telegram channel ID for a specific profile."""
        if source == "betburger":
            profiles = self.config.get('betburger_profiles', {})
        elif source == "surebet":
            profiles = self.config.get('surebet_profiles', {})
        else:
            logger.warning("Unknown source platform", source=source)
            return None
        
        profile_config = profiles.get(profile)
        if not profile_config:
            logger.warning("Profile not found in configuration", source=source, profile=profile)
            return None
        
        return profile_config.get('channel_id')
    
    def get_channels_for_arbitrage(self, arb_data) -> List[str]:
        """Get all matching channels for arbitrage data based on filters."""
        from processors.arbitrage_data import ArbitrageData
        
        if not isinstance(arb_data, ArbitrageData):
            logger.error("Invalid arbitrage data type")
            return []
        
        matching_channels = []
        
        # Get profiles for the source platform
        if arb_data.source == "betburger":
            profiles = self.config.get('betburger_profiles', {})
        elif arb_data.source == "surebet":
            profiles = self.config.get('surebet_profiles', {})
        else:
            logger.warning("Unknown source platform", source=arb_data.source)
            return []
        
        # Check each profile's filters
        for profile_name, profile_config in profiles.items():
            if self._matches_profile_filters(arb_data, profile_config):
                channel_id = profile_config.get('channel_id')
                if channel_id:
                    matching_channels.append(channel_id)
                    logger.info("Alert matches profile", 
                               source=arb_data.source,
                               profile=profile_name,
                               channel=channel_id)
        
        # If no specific matches, try to match by profile name
        if not matching_channels and arb_data.profile:
            channel_id = self.get_channel_for_profile(arb_data.source, arb_data.profile)
            if channel_id:
                matching_channels.append(channel_id)
                logger.info("Alert matched by profile name", 
                           source=arb_data.source,
                           profile=arb_data.profile,
                           channel=channel_id)
        
        return matching_channels
    
    def _matches_profile_filters(self, arb_data, profile_config: Dict[str, Any]) -> bool:
        """Check if arbitrage data matches profile filters."""
        filters = profile_config.get('filters', [])
        
        for filter_rule in filters:
            if not isinstance(filter_rule, dict):
                continue
            
            # Check minimum ROI/value
            if 'min_roi' in filter_rule:
                if not arb_data.roi_pct or arb_data.roi_pct < filter_rule['min_roi']:
                    return False
            
            if 'min_value' in filter_rule:
                if not arb_data.value_pct or arb_data.value_pct < filter_rule['min_value']:
                    return False
            
            # Check sports
            if 'sports' in filter_rule:
                if not arb_data.sport or arb_data.sport.lower() not in [s.lower() for s in filter_rule['sports']]:
                    return False
            
            # Check bookmakers
            if 'bookmakers' in filter_rule:
                bookmaker_names = [bm.lower() for bm in filter_rule['bookmakers']]
                
                # Check if any of the selections match the bookmaker filter
                matches_bookmaker = False
                
                if arb_data.selection_a and arb_data.selection_a.bookmaker.lower() in bookmaker_names:
                    matches_bookmaker = True
                
                if arb_data.selection_b and arb_data.selection_b.bookmaker.lower() in bookmaker_names:
                    matches_bookmaker = True
                
                if not matches_bookmaker:
                    return False
        
        return True
    
    def get_error_channel(self) -> Optional[str]:
        """Get channel ID for technical errors."""
        return self.config.get('defaults', {}).get('notifications', {}).get('error_channel')
    
    def get_all_channels(self) -> Dict[str, str]:
        """Get all configured channels with their descriptions."""
        channels = {}
        
        # Betburger channels
        for profile_name, profile_config in self.config.get('betburger_profiles', {}).items():
            channel_id = profile_config.get('channel_id')
            description = profile_config.get('description', f"Betburger - {profile_name}")
            if channel_id:
                channels[channel_id] = description
        
        # Surebet channels
        for profile_name, profile_config in self.config.get('surebet_profiles', {}).items():
            channel_id = profile_config.get('channel_id')
            description = profile_config.get('description', f"Surebet - {profile_name}")
            if channel_id:
                channels[channel_id] = description
        
        # Support channels
        for support_name, support_config in self.config.get('support', {}).items():
            channel_id = support_config.get('channel_id')
            description = support_config.get('description', f"Support - {support_name}")
            if channel_id:
                channels[channel_id] = description
        
        return channels
    
    def validate_required_fields(self, arb_data, profile_name: str) -> bool:
        """Validate that arbitrage data has all required fields for a profile."""
        from processors.arbitrage_data import ArbitrageData
        
        if not isinstance(arb_data, ArbitrageData):
            return False
        
        # Get profile configuration
        if arb_data.source == "betburger":
            profiles = self.config.get('betburger_profiles', {})
        elif arb_data.source == "surebet":
            profiles = self.config.get('surebet_profiles', {})
        else:
            return False
        
        profile_config = profiles.get(profile_name)
        if not profile_config:
            return False
        
        required_fields = profile_config.get('required_fields', [])
        
        for field_path in required_fields:
            if not self._has_field(arb_data, field_path):
                logger.warning("Missing required field", 
                              profile=profile_name,
                              field=field_path,
                              source=arb_data.source)
                return False
        
        return True
    
    def _has_field(self, arb_data, field_path: str) -> bool:
        """Check if arbitrage data has a specific field (supports dot notation)."""
        parts = field_path.split('.')
        current = arb_data
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
                if current is None:
                    return False
            else:
                return False
        
        return True


def create_mapper(config_path: str = None) -> ChannelMapper:
    """Factory function to create channel mapper."""
    return ChannelMapper(config_path)
