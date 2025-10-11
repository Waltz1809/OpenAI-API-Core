#!/usr/bin/env python3
"""
DxmwxParser Parser Module
==========================

Parser chuyên dụng cho dxmwx.org
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class DxmwxParser(StandardParserMixin):
    """Parser cho dxmwx.org"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang dxmwx.org

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
            # Extract title từ h1#ChapterTitle, fallback sang JS var ChapterTitle
            title_el = page.query_selector('#ChapterTitle')
            title = title_el.inner_text().strip() if title_el else None

            if not title:
                page_source = page.content()
                m = re.search(r'var\s+ChapterTitle\s*=\s*"([^"]+)"', page_source)
                if m:
                    title = m.group(1).strip()

            if not title:
                title = "Không có tiêu đề"

            # DXMWX không có volume trên trang chapter
            volume = ""

            # Extract content từ #Lab_Contents p[id^="txt_"]
            content_parts = []
            content_container = page.query_selector('#Lab_Contents')

            if content_container:
                p_elements = content_container.query_selector_all('p[id^="txt_"]')
                if p_elements:
                    for p_el in p_elements:
                        text = p_el.inner_text().strip()
                        if not text:
                            continue
                        # Loại bỏ số đếm ở cuối dòng (ví dụ: … 38)
                        text = re.sub(r'[ \u3000]*\d{1,3}$', '', text)
                        if text:
                            content_parts.append(text)
                else:
                    # Fallback: dùng toàn bộ text trong container, tách theo dòng
                    full_text = content_container.inner_text()
                    for line in full_text.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        line = re.sub(r'[ \u3000]*\d{1,3}$', '', line)
                        if line:
                            content_parts.append(line)

            content = '\n\n'.join(content_parts) if content_parts else ""

            # Extract next URL
            next_url = DxmwxParser._extract_next_url(page, current_url)

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

        # Loại bỏ số đếm ở cuối các đoạn (an toàn nếu còn sót)
        def strip_trailing_numbers(paragraph: str) -> str:
            return re.sub(r'[ \u3000]*\d{1,3}$', '', paragraph.strip())

        cleaned_paragraphs = [strip_trailing_numbers(p) for p in content.split('\n\n')]
        content = '\n\n'.join([p for p in cleaned_paragraphs if p])

        # Fix excessive line breaks
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

        return content.strip()
