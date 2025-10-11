#!/usr/bin/env python3
"""
ZhswxParser Parser Module
==========================

Parser chuyên dụng cho tw.zhswx.com
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class ZhswxParser(StandardParserMixin):
    """Parser cho tw.zhswx.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang tw.zhswx.com
        
        Args:
            page: Playwright page object
            current_url: URL hiện tại
            
        Returns:
            dict: {
                'title': str,
                'volume': str,
                'content': str, 
                'next_url': str,
                'success': bool
            }
        """
        try:
            # Extract title từ h1
            title_el = page.query_selector('h1')
            title = title_el.inner_text().strip() if title_el else "Không có tiêu đề"
            
            # Volume không có trên trang chapter của site này
            volume = ""
            
            # Extract content từ div chứa nội dung chính
            content_parts = []
            content_container = page.query_selector('div[style*="font-size: 20px"][style*="width: 700px"][style*="text-indent: 2em"]')
            if content_container:
                # Lấy toàn bộ text và xử lý 
                full_text = content_container.inner_text()
                
                # Tách thành các đoạn dựa trên thẻ <br> và <p>
                # Lấy tất cả font elements (nội dung thực)
                font_elements = content_container.query_selector_all('font')
                for font_el in font_elements:
                    text = font_el.inner_text().strip()
                    if text:
                        content_parts.append(text)
                
                # Nếu không có font elements, fallback về text thuần
                if not content_parts:
                    lines = full_text.split('\n')
                    content_parts = [line.strip() for line in lines if line.strip()]

                content = '\n\n'.join(content_parts)
            else:
                content = ""
            
            # Extract next URL
            next_url = ZhswxParser._extract_next_url(page, current_url)
            
            return {
                'title': title,
                'volume': volume,
                'content': content,
                'next_url': next_url,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Lỗi parse content: {e}")
            return {
                'title': None,
                'volume': None,
                'content': None,
                'next_url': None,
                'success': False
            }
    @staticmethod
    def clean_content(content):
        """Clean content, giữ nguyên structure"""
        if not content:
            return content
        
        # Remove zero-width characters
        replacements = {
            '\u200b': '',  # Zero-width space
            '\u200c': '',  # Zero-width non-joiner  
            '\u200d': '',  # Zero-width joiner
            '\ufeff': '',  # Byte order mark
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        # Fix excessive line breaks
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        return content.strip()
