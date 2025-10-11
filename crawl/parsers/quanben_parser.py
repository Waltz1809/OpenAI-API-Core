#!/usr/bin/env python3
"""
QuanbenParser Parser Module
============================

Parser chuyên dụng cho quanben.io
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class QuanbenParser(StandardParserMixin):
    """Parser cho quanben.io"""
    
    @staticmethod
    def extract_content(page, url):
        """
        Extract content từ trang chapter quanben.io
        
        Args:
            page: Playwright page object
            url: URL của chapter
            
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
            # Extract title từ h1.headline
            title_element = page.query_selector('h1.headline')
            title = title_element.inner_text().strip() if title_element else ""
            
            # Extract content từ div.articlebody
            content_parts = []
            content_div = page.query_selector('div.articlebody #content')
            
            if content_div:
                # Lấy tất cả <p> elements
                p_elements = content_div.query_selector_all('p')
                
                for p_el in p_elements:
                    text = p_el.inner_text().strip()
                    if text:
                        content_parts.append(text)
                
                content = '\n\n'.join(content_parts)
            else:
                content = ""
            
            # Extract next URL (nếu cần)
            next_url = QuanbenParser._extract_next_url(page, url)
            
            return {
                'title': title,
                'volume': "",  # Quanben không có volume structure rõ ràng
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
        """Clean content, loại bỏ các ký tự thừa và PAGE comments"""
        if not content:
            return content

        # Remove zero-width characters và các ký tự đặc biệt
        replacements = {
            '\u200b': '',  # Zero-width space
            '\ufeff': '',  # BOM
            '\u00a0': ' ', # Non-breaking space
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        # Remove PAGE comments (<!--PAGE 1-->, <!--PAGE 2-->, etc.)
        content = re.sub(r'<!--PAGE \d+-->', '', content)

        # Clean multiple newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Remove leading/trailing whitespace
        return content.strip()
