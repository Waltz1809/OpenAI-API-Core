#!/usr/bin/env python3
"""
TWLinovelibParser Parser Module
================================

Parser chuyên dụng cho tw.linovelib.com
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class TWLinovelibParser(StandardParserMixin):
    """Parser cho tw.linovelib.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang tw.linovelib.com
        
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
            # Extract title từ h1#atitle
            title_el = page.query_selector('#atitle')
            title = title_el.inner_text().strip() if title_el else "Không có tiêu đề"
            
            # Extract volume từ h3 ngay sau h1#atitle
            volume = ""
            try:
                # Tìm h3 đầu tiên trong page
                volume_el = page.query_selector('h3')
                if volume_el:
                    volume_text = volume_el.inner_text().strip()
                    # Chỉ lấy nếu chứa "卷" hoặc volume info
                    if '卷' in volume_text or 'Vol' in volume_text:
                        volume = volume_text
            except Exception:
                pass
            
            # Extract content từ #acontent p
            content_parts = []
            content_elements = page.query_selector_all('#acontent p')
            
            for el in content_elements:
                text = el.inner_text().strip()
                if text:  # Skip paragraphs trống
                    content_parts.append(text)
            
            content = '\n\n'.join(content_parts)
            
            # Extract next URL từ ReadParams JavaScript
            next_url = TWLinovelibParser._extract_next_url(page, current_url)
            
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
