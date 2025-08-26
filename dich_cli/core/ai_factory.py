#!/usr/bin/env python3
"""
AI Factory - Factory pattern để tạo AI clients phù hợp
"""

import json
import os
from typing import Dict, Union

from .openai_client import OpenAIClient
from .gemini_client import GeminiClient
from .vertex_client import VertexClient
from .key_rotator import KeyRotator


# Global key rotator instance
_global_key_rotator = None


class AIClientFactory:
    """Factory để tạo AI clients dựa trên config."""
    
    @staticmethod
    def create_client(api_config: Dict, secret_config: Dict) -> Union[OpenAIClient, GeminiClient, VertexClient]:
        """
        Tạo client phù hợp dựa trên config với multi-key rotation support.
        
        Args:
            api_config: Config cho API (model, temperature, etc.)
            secret_config: Secret credentials (có thể chứa multiple keys)
            
        Returns:
            AI Client instance
        """
        global _global_key_rotator
        
        # Initialize rotator nếu chưa có
        if _global_key_rotator is None:
            print("🔄 AI Factory: Initializing KeyRotator...")
            _global_key_rotator = KeyRotator(secret_config)
            # Hiển thị thông tin tổng quan
            status = _global_key_rotator.get_status()
            print(f"📊 KeyRotator Status: {status}")
        
        # Lấy provider từ config
        provider = api_config.get('provider', 'openai').lower()
        
        if provider == 'vertex':
            # Vertex vẫn dùng cách cũ (key cố định)
            key_config = _global_key_rotator.get_next_key(provider)
            if key_config is None:
                available_providers = list(_global_key_rotator.get_status().keys())
                raise ValueError(f"Không tìm thấy key nào cho provider: {provider}. Available: {available_providers}")
            return VertexClient(api_config, key_config)
            
        elif provider == 'gemini':
            # Gemini dùng per-request rotation
            return GeminiClient(api_config, _global_key_rotator)
            
        elif provider == 'openai':
            # OpenAI vẫn dùng cách cũ (key cố định)
            key_config = _global_key_rotator.get_next_key(provider)
            if key_config is None:
                available_providers = list(_global_key_rotator.get_status().keys())
                raise ValueError(f"Không tìm thấy key nào cho provider: {provider}. Available: {available_providers}")
            return OpenAIClient(api_config, key_config)
            
        else:
            raise ValueError(f"Provider không hỗ trợ: {provider}. Chỉ hỗ trợ: openai, gemini, vertex")
    
    @staticmethod
    def get_provider_name(api_config: Dict) -> str:
        """
        Trả về tên provider dựa trên config.
        
        Args:
            api_config: Config cho API
            
        Returns:
            str: "vertex", "gemini", hoặc "openai"
        """
        return api_config.get('provider', 'openai').lower()
    
    @staticmethod
    def get_sdk_code(api_config: Dict) -> str:
        """
        Trả về SDK code cho naming convention dựa trên provider.
        
        Args:
            api_config: Config cho API
            
        Returns:
            str: "oai", "gmn", hoặc "vtx"
        """
        provider = api_config.get('provider', 'openai').lower()
        mapping = {
            'openai': 'oai',
            'gemini': 'gmn', 
            'vertex': 'vtx'
        }
        return mapping.get(provider, 'oai')
    
    @staticmethod
    def get_key_rotator_status() -> Dict:
        """
        Lấy thông tin về trạng thái của key rotator.
        
        Returns:
            Dict: Status info cho từng provider
        """
        global _global_key_rotator
        if _global_key_rotator is None:
            return {}
        return _global_key_rotator.get_status()
    
    @staticmethod
    def has_multiple_keys(provider: str) -> bool:
        """
        Check xem provider có nhiều hơn 1 key không.
        
        Args:
            provider: "openai", "gemini", hoặc "vertex"
            
        Returns:
            bool: True nếu có > 1 key
        """
        global _global_key_rotator
        if _global_key_rotator is None:
            return False
        return _global_key_rotator.has_multiple_keys(provider)


def load_configs() -> tuple[Dict, Dict]:
    """
    Load cả config.json và secrets.json.
    
    Returns:
        Tuple[config, secret]: Config chính và secret credentials
    """
    # Load config.json từ thư mục dich_cli/
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.json')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError("File config.json không tồn tại")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Load secrets.json từ thư mục gốc (Dich/)
    # script_dir = dich_cli/, parent = Dich/
    parent_dir = os.path.dirname(script_dir)
    secrets_path = os.path.join(parent_dir, 'secrets.json')
    
    if not os.path.exists(secrets_path):
        # Fallback: tìm trong thư mục dich_cli/ (cho compatibility)
        fallback_path = os.path.join(script_dir, 'secret.json')
        if os.path.exists(fallback_path):
            secrets_path = fallback_path
        else:
            # Tạo từ template nếu chưa có
            template_path = os.path.join(script_dir, 'secret_template.json')
            if os.path.exists(template_path):
                raise FileNotFoundError(
                    f"File secrets.json không tồn tại ở thư mục gốc: {secrets_path}\n"
                    f"Hãy copy {template_path} thành secrets.json ở thư mục gốc và điền API keys."
                )
            else:
                raise FileNotFoundError(f"File secrets.json không tồn tại: {secrets_path}")
    
    with open(secrets_path, 'r', encoding='utf-8') as f:
        secret = json.load(f)
    
    print(f"✅ Loaded secrets from: {secrets_path}")
    return config, secret
