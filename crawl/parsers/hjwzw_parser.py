#!/usr/bin/env python3
"""
HjwzwParser Parser Module
==========================

Parser chuyên dụng cho tw.hjwzw.com
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class HjwzwParser(StandardParserMixin):
    """Parser cho tw.hjwzw.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang tw.hjwzw.com
        
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
            
            # Extract content
            content_parts = []
            # Selector chính xác cho div chứa nội dung chương
            content_container = page.query_selector('div[style*="font-size: 20px"][style*="line-height: 30px"][style*="width: 750px"]')
            if content_container:
                # Lấy tất cả thẻ p bên trong
                p_elements = content_container.query_selector_all('p')
                
                for i, p_el in enumerate(p_elements):
                    # Check if <p> chứa <a href> (title paragraph)
                    has_link = p_el.query_selector('a[href]')
                    if has_link:
                        # Skip paragraph có link (title paragraph)
                        continue

                    text = p_el.inner_text().strip()
                    # Bỏ qua dòng đầu tiên chứa quảng cáo "請記住本站域名"
                    if i == 0 and ("請記住本站域名" in text or "黃金屋" in text):
                        continue
                    # Bỏ qua dòng có link đến trang chính của truyện
                    if text and not text.startswith("我的超能力每周刷新"):
                        content_parts.append(text)

                content = '\n\n'.join(content_parts)
            else:
                content = ""
            
            # Extract next URL
            next_url = HjwzwParser._extract_next_url(page, current_url)
            
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
        
        return content
