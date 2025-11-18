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
from .path_helper import get_path_helper


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
    Load cả config.json và secrets.json sử dụng PathHelper.
    
    Returns:
        Tuple[config, secret]: Config chính và secret credentials
    """
    ph = get_path_helper()
    
    # Load config.json từ thư mục dich_cli/
    config_path = ph.resolve('dich_cli/config.json')
    
    if not ph.exists(config_path):
        raise FileNotFoundError(f"File config.json không tồn tại: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Load secrets.json từ thư mục gốc (Dich/)
    secrets_path = ph.resolve('secrets.json')
    
    if not ph.exists(secrets_path):
        # Fallback: tìm secrets_2.json
        secrets_path = ph.resolve('secrets_2.json')
        if not ph.exists(secrets_path):
            # Fallback: tìm trong thư mục dich_cli/
            secrets_path = ph.resolve('dich_cli/secret.json')
            if not ph.exists(secrets_path):
                raise FileNotFoundError(
                    f"File secrets.json không tồn tại.\n"
                    f"Tìm kiếm ở: secrets.json, secrets_2.json, dich_cli/secret.json\n"
                    f"Project root: {ph.project_root}"
                )
    
    with open(secrets_path, 'r', encoding='utf-8') as f:
        secret = json.load(f)
    
    print(f"✅ Config: {ph.relative_to_project(config_path)}")
    print(f"✅ Secrets: {ph.relative_to_project(secrets_path)}")
    return config, secret
