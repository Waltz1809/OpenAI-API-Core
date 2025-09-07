#!/usr/bin/env python3
"""
AI Factory - Factory pattern để tạo AI clients phù hợp
"""

import json  # may be used elsewhere
import yaml
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
    """Load cấu hình cố định với logic rõ ràng về path:

    - Config: <repo_root>/src/job_2_translator/config.yml
    - Secrets: ưu tiên <repo_root>/secret.yml; fallback sang <repo_root>/secrets.yml

    main.py sẽ đảm bảo current working directory = <repo_root>, nhưng ở đây chúng ta vẫn
    dùng absolute path để tránh phụ thuộc CWD.
    """

    # Xác định thư mục job_2_translator (file này nằm trong: <repo_root>/src/job_2_translator/core/ai_factory.py)
    core_dir = os.path.dirname(os.path.abspath(__file__))          # .../src/job_2_translator/core
    job_dir = os.path.dirname(core_dir)                            # .../src/job_2_translator
    config_path = os.path.join(job_dir, 'config.yml')              # .../src/job_2_translator/config.yml
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Không tìm thấy config.yml tại: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
    print(f"✅ Loaded config: {config_path}")

    # Repo root: job_dir = <repo_root>/src/job_2_translator -> parent twice lên repo root
    repo_root = os.path.abspath(os.path.join(job_dir, '..', '..'))
    # Secrets: chấp nhận secret.yml hoặc secrets.yml
    secrets_primary = os.path.join(repo_root, 'secret.yml')
    secrets_alt = os.path.join(repo_root, 'secrets.yml')
    if os.path.isfile(secrets_primary):
        secrets_path = secrets_primary
    elif os.path.isfile(secrets_alt):
        secrets_path = secrets_alt
        print("ℹ️  Dùng 'secrets.yml' (fallback) – nên đổi tên thành 'secret.yml' để đồng nhất tài liệu.")
    else:
        raise FileNotFoundError(
            "Không tìm thấy secret.yml hoặc secrets.yml ở repo root.\n" \
            f"Tạo một trong hai file tại: {repo_root}\n" \
            "Ví dụ minimal:\n" \
            "openai:\n  - api_key: sk-...\n" \
            "gemini:\n  - api_key: AIza...\n" \
            "vertex:\n  - project_id: your-project\n    location: us-central1\n    access_token: ya29...."
        )
    with open(secrets_path, 'r', encoding='utf-8') as f:
        secret = yaml.safe_load(f) or {}
    print(f"✅ Loaded secrets: {secrets_path}")

    return config, secret
