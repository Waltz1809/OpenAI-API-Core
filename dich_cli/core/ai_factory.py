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


class AIClientFactory:
    """Factory để tạo AI clients dựa trên config."""
    
    @staticmethod
    def create_client(api_config: Dict, secret_config: Dict) -> Union[OpenAIClient, GeminiClient, VertexClient]:
        """
        Tạo client phù hợp dựa trên config.
        
        Args:
            api_config: Config cho API (model, temperature, etc.)
            secret_config: Secret credentials
            
        Returns:
            AI Client instance
        """
        # Lấy provider từ config
        provider = api_config.get('provider', 'openai').lower()
        
        if provider == 'vertex':
            # Kiểm tra required credentials cho Vertex
            required_vertex_keys = ['vertex_project_id']
            missing_keys = [key for key in required_vertex_keys if key not in secret_config]
            if missing_keys:
                raise ValueError(f"Vertex AI thiếu credentials: {missing_keys}")
            
            return VertexClient(api_config, secret_config)
            
        elif provider == 'gemini':
            # Kiểm tra required credentials cho Gemini
            if 'gemini_api_key' not in secret_config:
                raise ValueError("Gemini thiếu 'gemini_api_key' trong secret config")
            
            return GeminiClient(api_config, secret_config)
            
        elif provider == 'openai':
            # OpenAI
            if 'openai_api_key' not in secret_config:
                raise ValueError("OpenAI thiếu 'openai_api_key' trong secret config")
            
            return OpenAIClient(api_config, secret_config)
            
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
