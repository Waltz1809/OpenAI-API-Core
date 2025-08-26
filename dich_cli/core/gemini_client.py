#!/usr/bin/env python3
"""
Gemini Client - Wrapper cho Google Gemini native SDK
"""

from typing import Dict, Tuple
from google import genai
from google.genai import types


class GeminiClient:
    """Client cho Google Gemini native SDK."""
    
    def __init__(self, api_config: Dict, key_rotator=None):
        """
        Initialize Gemini client.
        
        Args:
            api_config: Config cho API (model, temperature, etc.)
            key_rotator: KeyRotator instance cho multi-key support
        """
        self.api_config = api_config
        self.key_rotator = key_rotator
        
        # Safety settings - TẮT TẤT CẢ
        self.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF
            ),
        ]
    
    def generate_content(self, system_prompt: str, user_prompt: str) -> Tuple[str, Dict]:
        """
        Generate content từ Gemini API với per-request key rotation.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
        
        Returns:
            Tuple[content, token_info]: Nội dung và thông tin token
        """
        try:
            # Lấy key mới cho request này
            if self.key_rotator:
                key_config = self.key_rotator.get_next_key('gemini')
                if key_config is None:
                    raise Exception("Không thể lấy Gemini key cho request")
                client = genai.Client(api_key=key_config['api_key'])
            else:
                # Fallback cho compatibility
                raise Exception("KeyRotator không được cung cấp")
            
            # Setup generation config
            generation_config_params = {
                "temperature": self.api_config['temperature'],
                "max_output_tokens": self.api_config.get('max_tokens', 4000)
            }
            
            # Thêm thinking config nếu model hỗ trợ (2.5 series)
            model_name = self.api_config['model']
            if self._supports_thinking(model_name):
                thinking_budget = self.api_config.get('thinking_budget', 0)
                if thinking_budget is not None:
                    try:
                        generation_config_params['thinking_config'] = types.ThinkingConfig(
                            thinking_budget=int(thinking_budget)
                        )
                    except Exception:
                        pass  # Bỏ qua nếu lỗi thinking config
            
            generation_config = types.GenerateContentConfig(
                **generation_config_params,
                safety_settings=self.safety_settings,
                system_instruction=system_prompt  # Thêm system instruction
            )
            
            # Generate content với system instruction riêng
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,  # Chỉ user prompt
                config=generation_config
            )
            
            # Check if blocked
            if not response.candidates:
                block_reason = "Không rõ"
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason = getattr(response.prompt_feedback.block_reason, 'name', 'Unknown')
                raise Exception(f"Prompt bị chặn: {block_reason}")
            
            content = response.text
            if not content or not content.strip():
                raise Exception("Model trả về content trống")
            
            # Extract token info
            token_info = {"input": 0, "output": 0, "thinking": 0}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                try:
                    token_info["input"] = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                    token_info["output"] = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                    if self._supports_thinking(model_name):
                        thinking_count = getattr(response.usage_metadata, 'thoughts_token_count', 0)
                        token_info["thinking"] = thinking_count or 0
                except AttributeError:
                    pass
            
            return content, token_info
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def _supports_thinking(self, model_name: str) -> bool:
        """Check xem model có hỗ trợ thinking không (chỉ Gemini 2.5 series)."""
        return any(version in model_name.lower() for version in ['2.5', '2-5'])
    
    def get_sdk_type(self) -> str:
        """Trả về SDK type cho naming convention."""
        return "gmn"
    
    def get_model_name(self) -> str:
        """Trả về tên model."""
        return self.api_config['model']
    
    def supports_thinking(self) -> bool:
        """Check xem model hiện tại có hỗ trợ thinking không."""
        return self._supports_thinking(self.api_config['model'])
