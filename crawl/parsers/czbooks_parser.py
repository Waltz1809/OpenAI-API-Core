#!/usr/bin/env python3
"""
CZBooksParser Parser Module
============================

Parser chuyên dụng cho czbooks.net
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class CZBooksParser(StandardParserMixin):
    """Parser cho czbooks.net"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang chương czbooks.net
        
        Args:
            page: Playwright page object
            current_url: URL hiện tại
            
        Returns:
            dict: {
                'title': str,
                'content': str, 
                'next_url': str,
                'success': bool
            }
        """
        try:
            # Extract title từ <div class="name">
            title_el = page.query_selector('.name')
            title = title_el.inner_text().strip() if title_el else "Không có tiêu đề"
            
            # Extract content từ <div class="content">
            content_el = page.query_selector('.content')
            if not content_el:
                return {
                    'title': title,
                    'content': '',
                    'next_url': '',
                    'success': False
                }
            
            # Lấy HTML content và clean up
            content_html = content_el.inner_html()
            
            # Convert <br> thành newlines và clean HTML tags
            content = content_html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
            content = re.sub(r'<[^>]+>', '', content)  # Remove HTML tags
            content = re.sub(r'\n\s*\n', '\n\n', content)  # Clean multiple newlines
            content = content.strip()
            
            # Extract next chapter URL
            next_url = ""
            next_el = page.query_selector('a.next-chapter')
            if next_el:
                next_href = next_el.get_attribute('href')
                if next_href:
                    next_url = urljoin(current_url, next_href)
            
            return {
                'title': title,
                'content': content,
                'next_url': next_url,
                'success': True
            }
            
        except Exception as e:
            print(f"⚠️  Lỗi extract content: {e}")
            return {
                'title': "Lỗi",
                'content': f"Lỗi trích xuất: {e}",
                'next_url': '',
                'success': False
            }
