"""
Configuration management for the Text Splitter.
"""

import yaml
import pathlib
from typing import Dict, Any


class ConfigManager:
    """Handles configuration loading and validation."""
    
    def __init__(self, config_path: str = None):
        """Initialize with configuration file path."""
        if config_path is None:
            config_path = pathlib.Path(__file__).parent.parent / "config.yml"
        
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load config from {self.config_path}: {e}")
    
    def _validate_config(self):
        """Validate that all required configuration sections and parameters exist."""
        # Check main sections
        required_sections = ['paths', 'processing', 'logging']
        for section in required_sections:
            if section not in self.config:
                raise Exception(f"Required config section '{section}' is missing")
        
        # Check paths section
        paths_config = self.config['paths']
        required_paths = ['input', 'output', 'logs']
        for path in required_paths:
            if not paths_config.get(path):
                raise Exception(f"Required config parameter 'paths.{path}' is missing")
        
        # Check processing section
        processing_config = self.config['processing']
        required_processing = ['file_types', 'segment_length']
        for param in required_processing:
            if not processing_config.get(param):
                raise Exception(f"Required config parameter 'processing.{param}' is missing")
        
        # Validate file_types is a list
        if not isinstance(processing_config['file_types'], list):
            raise Exception("'processing.file_types' must be a list")
        
        # Validate segment_length is a number
        if not isinstance(processing_config['segment_length'], int) or processing_config['segment_length'] <= 0:
            raise Exception("'processing.segment_length' must be a positive integer")
        
        # Check logging section
        logging_config = self.config['logging']
        required_logging = ['enable_logging', 'skip_processed']
        for param in required_logging:
            if param not in logging_config:
                raise Exception(f"Required config parameter 'logging.{param}' is missing")
    
    def get(self, key: str, default=None):
        """Get configuration value by key."""
        return self.config.get(key, default)
    
    def get_paths(self) -> Dict[str, str]:
        """Get paths configuration."""
        return self.config['paths']
    
    def get_processing(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return self.config['processing']
    
    def get_logging(self) -> Dict[str, bool]:
        """Get logging configuration."""
        return self.config['logging']
