#!/usr/bin/env python3
"""
OpenAI Client - Wrapper cho OpenAI và OpenAI-compatible APIs
"""

from typing import Dict, Tuple
import openai


class OpenAIClient:
    """Client cho OpenAI và OpenAI-compatible APIs."""
    
    def __init__(self, api_config: Dict, secret_config: Dict):
        """
        Initialize OpenAI client.
        
        Args:
            api_config: Config cho API (model, temperature, etc.)
            secret_config: Secret credentials
        """
        self.api_config = api_config
        self.secret_config = secret_config
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(
            api_key=secret_config['openai_api_key'],
            base_url=secret_config.get('openai_base_url', 'https://api.openai.com/v1')
        )
    
    def generate_content(self, system_prompt: str, user_prompt: str) -> Tuple[str, Dict]:
        """
        Generate content từ OpenAI API.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
        
        Returns:
            Tuple[content, token_info]: Nội dung và thông tin token
        """
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.api_config['model'],
                temperature=self.api_config['temperature'],
                max_tokens=self.api_config.get('max_tokens', 4000)
            )
            
            if not response.choices or not response.choices[0].message:
                raise Exception("API không trả về response hợp lệ")
            
            content = response.choices[0].message.content
            if not content:
                raise Exception("API trả về content trống")
            
            # Extract token info - DeepSeek compatible
            token_info = {
                "input": 0, 
                "output": 0, 
                "thinking": 0,
                "cache_hit": 0,
                "cache_miss": 0,
                "total": 0
            }
            
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                token_info["input"] = getattr(usage, 'prompt_tokens', 0)
                token_info["output"] = getattr(usage, 'completion_tokens', 0)
                token_info["cache_hit"] = getattr(usage, 'prompt_cache_hit_tokens', 0)
                token_info["cache_miss"] = getattr(usage, 'prompt_cache_miss_tokens', 0)
                token_info["total"] = getattr(usage, 'total_tokens', 0)
                
                # Lấy reasoning tokens từ completion_tokens_details
                if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                    token_info["thinking"] = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0)
            
            return content, token_info
            
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def get_sdk_type(self) -> str:
        """Trả về SDK type cho naming convention."""
        return "ds"
    
    def get_model_name(self) -> str:
        """Trả về tên model."""
        return self.api_config['model']
    
    def supports_thinking(self) -> bool:
        """DeepSeek models hỗ trợ reasoning tokens."""
        return True
