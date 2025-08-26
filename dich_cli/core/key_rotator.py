#!/usr/bin/env python3
"""
Key Rotator - Round-robin rotation cho multiple API keys
"""

from typing import Dict, List, Any, Optional
import threading


class KeyRotator:
    """Class để handle round-robin rotation của API keys."""
    
    def __init__(self, secrets_config: Dict):
        """
        Initialize KeyRotator với secrets config.
        
        Args:
            secrets_config: Config chứa API keys
        """
        self.secrets_config = secrets_config
        self.rotators = {}  # {provider: {'keys': [...], 'index': 0, 'lock': Lock}}
        self._setup_rotators()
    
    def _setup_rotators(self):
        """Setup rotators cho từng provider."""
        # OpenAI keys
        openai_keys = self._get_keys_for_provider('openai')
        if openai_keys:
            self.rotators['openai'] = {
                'keys': openai_keys,
                'index': 0,
                'lock': threading.Lock()
            }
            print(f"🔑 KeyRotator: Loaded {len(openai_keys)} OpenAI keys")
        
        # Gemini keys
        gemini_keys = self._get_keys_for_provider('gemini')
        if gemini_keys:
            self.rotators['gemini'] = {
                'keys': gemini_keys,
                'index': 0,
                'lock': threading.Lock()
            }
            print(f"🔑 KeyRotator: Loaded {len(gemini_keys)} Gemini keys")
            # Debug: hiển thị partial info của từng key
            for i, key in enumerate(gemini_keys):
                api_key = key.get('api_key', 'N/A')
                masked_key = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else api_key
                print(f"   Key {i+1}: {masked_key}")
        
        # Vertex keys
        vertex_keys = self._get_keys_for_provider('vertex')
        if vertex_keys:
            self.rotators['vertex'] = {
                'keys': vertex_keys,
                'index': 0,
                'lock': threading.Lock()
            }
            print(f"🔑 KeyRotator: Loaded {len(vertex_keys)} Vertex keys")
    
    def _get_keys_for_provider(self, provider: str) -> List[Dict]:
        """
        Lấy keys cho provider cụ thể, support backward compatibility.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            List[Dict]: Danh sách keys cho provider
        """
        keys = []
        
        if provider == 'openai':
            # Ưu tiên multi-key format
            if 'openai_keys' in self.secrets_config:
                keys = self.secrets_config['openai_keys']
            # Fallback to legacy format
            elif 'openai_api_key' in self.secrets_config:
                keys = [{
                    'api_key': self.secrets_config['openai_api_key'],
                    'base_url': self.secrets_config.get('openai_base_url', 'https://api.openai.com/v1')
                }]
        
        elif provider == 'gemini':
            # Ưu tiên multi-key format
            if 'gemini_keys' in self.secrets_config:
                keys = self.secrets_config['gemini_keys']
            # Fallback to legacy format
            elif 'gemini_api_key' in self.secrets_config:
                keys = [{
                    'api_key': self.secrets_config['gemini_api_key']
                }]
        
        elif provider == 'vertex':
            # Ưu tiên multi-key format
            if 'vertex_keys' in self.secrets_config:
                keys = self.secrets_config['vertex_keys']
            # Fallback to legacy format
            elif 'vertex_project_id' in self.secrets_config:
                keys = [{
                    'project_id': self.secrets_config['vertex_project_id'],
                    'location': self.secrets_config.get('vertex_location', 'global')
                }]
        
        return keys
    
    def get_next_key(self, provider: str) -> Optional[Dict]:
        """
        Lấy key tiếp theo cho provider theo round-robin.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            Dict: Key config hoặc None nếu không có key
        """
        if provider not in self.rotators:
            print(f"⚠️  KeyRotator: Provider '{provider}' không tồn tại trong rotators")
            return None
        
        rotator = self.rotators[provider]
        
        with rotator['lock']:
            keys = rotator['keys']
            if not keys:
                print(f"⚠️  KeyRotator: Provider '{provider}' không có keys")
                return None
            
            # Lấy key hiện tại
            current_index = rotator['index']
            current_key = keys[current_index]
            
            # Debug: log key được sử dụng
            if provider == 'gemini':
                api_key = current_key.get('api_key', 'N/A')
                masked_key = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else api_key
                print(f"🔄 KeyRotator: Using Gemini key {current_index + 1}/{len(keys)} ({masked_key})")
            
            # Rotate index cho lần sau
            new_index = (rotator['index'] + 1) % len(keys)
            rotator['index'] = new_index
            
            return current_key.copy()  # Return copy để tránh modification
    
    def get_all_keys(self, provider: str) -> List[Dict]:
        """
        Lấy tất cả keys cho provider.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            List[Dict]: Danh sách tất cả keys
        """
        if provider not in self.rotators:
            return []
        
        return self.rotators[provider]['keys'].copy()
    
    def get_key_count(self, provider: str) -> int:
        """
        Đếm số lượng keys cho provider.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            int: Số lượng keys
        """
        if provider not in self.rotators:
            return 0
        
        return len(self.rotators[provider]['keys'])
    
    def has_multiple_keys(self, provider: str) -> bool:
        """
        Check xem provider có nhiều hơn 1 key không.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            bool: True nếu có > 1 key
        """
        return self.get_key_count(provider) > 1
    
    def reset_rotation(self, provider: str):
        """
        Reset rotation index về 0 cho provider.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
        """
        if provider not in self.rotators:
            return
        
        with self.rotators[provider]['lock']:
            self.rotators[provider]['index'] = 0
    
    def get_status(self) -> Dict[str, Dict]:
        """
        Lấy status của tất cả rotators.
        
        Returns:
            Dict: Status info cho từng provider
        """
        status = {}
        
        for provider, rotator in self.rotators.items():
            with rotator['lock']:
                status[provider] = {
                    'key_count': len(rotator['keys']),
                    'current_index': rotator['index'],
                    'has_multiple': len(rotator['keys']) > 1
                }
        
        return status