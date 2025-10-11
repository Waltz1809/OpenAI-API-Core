#!/usr/bin/env python3
"""
Piaotia Parser Module
====================

Parser chuyên dụng cho www.piaotia.com
Trích xuất: title, content, next_url

Refactored to JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class PiaotiaParser(StandardParserMixin):
    """Parser cho www.piaotia.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang www.piaotia.com

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
            # Extract title từ h1 - lấy phần sau tên truyện
            title_el = page.query_selector('h1')
            title = "Không có tiêu đề"
            if title_el:
                title_text = title_el.inner_text().strip()
                # Tách lấy phần chapter title (sau tên truyện)
                # Format: "尸人 第286章"
                parts = title_text.split(' ', 1)
                if len(parts) > 1:
                    title = parts[1].strip()
                else:
                    title = title_text

            # Volume không có trên site này
            volume = ""

            # Extract content từ div#content
            content = ""
            content_div = page.query_selector('#content')
            if content_div:
                # Lấy HTML content
                content_html = content_div.inner_html()

                # Tìm vị trí bắt đầu content thực sự (sau <br> đầu tiên)
                first_br = content_html.find('<br>')
                if first_br != -1:
                    # Lấy phần sau <br> đầu tiên
                    content_html = content_html[first_br + 4:]  # +4 để bỏ qua "<br>"

                    # Tìm vị trí kết thúc content (trước navigation cuối)
                    # Loại bỏ phần navigation cuối và ads
                    end_markers = ['<div class="bottomlink">', '<center><script', '<div id="Commenddiv"']
                    for marker in end_markers:
                        end_pos = content_html.find(marker)
                        if end_pos != -1:
                            content_html = content_html[:end_pos]
                            break

                    # Clean HTML và convert thành text
                    # Replace <br> với newlines
                    content_html = content_html.replace('<br><br>', '\n\n')
                    content_html = content_html.replace('<br>', '\n')

                    # Remove HTML tags
                    content = re.sub(r'<[^>]+>', '', content_html)

                    # Decode HTML entities
                    content = content.replace('&nbsp;', ' ')
                    content = content.replace('&lt;', '<')
                    content = content.replace('&gt;', '>')
                    content = content.replace('&amp;', '&')

                    # Clean up whitespace và format
                    lines = content.split('\n')
                    clean_lines = []

                    for line in lines:
                        line = line.strip()
                        # Skip empty lines và navigation text
                        if not line:
                            continue
                        if any(nav in line for nav in ['上一章', '下一章', '目录', 'www.piaotia.com', '飘天文学']):
                            continue
                        if line.startswith('第') and line.endswith('章') and len(line) < 20:
                            # Chapter title - add with spacing
                            if clean_lines:
                                clean_lines.append('')
                            clean_lines.append(line)
                            clean_lines.append('')
                        else:
                            clean_lines.append(line)

                    # Join lines với double newlines để tạo paragraph breaks
                    content = '\n\n'.join(clean_lines)

                    # Basic cleaning only
                    content = PiaotiaParser.clean_content(content)

            # Extract next URL từ navigation links
            next_url = ""
            try:
                # Tìm link "下一章" hoặc "下一页"
                next_links = page.query_selector_all('a')
                for link in next_links:
                    link_text = link.inner_text().strip()
                    if '下一章' in link_text or '下一页' in link_text:
                        href = link.get_attribute('href')
                        if href:
                            next_url = urljoin(current_url, href)
                            break
            except Exception:
                pass

            return {
                'title': title,
                'volume': volume,
                'content': content,
                'next_url': next_url,
                'success': True
            }

        except Exception as e:
            print(f"⚠️  Lỗi extract content từ piaotia: {e}")
            return {
                'title': "",
                'volume': "",
                'content': "",
                'next_url': "",
                'success': False
            }
    
    @staticmethod
    def _split_into_paragraphs(content):
        """
        Tách content thành các đoạn văn dựa trên dấu câu và context

        Args:
            content (str): Raw content

        Returns:
            str: Content với paragraph breaks
        """
        if not content:
            return ""

        # Tách mỗi câu thành dòng riêng với dòng trống
        # Pattern 1: Sau dấu câu kết thúc (。！？) + bất kỳ ký tự nào (không phải space hoặc newline)
        content = re.sub(r'([。！？])([^\s\n])', r'\1\n\n\2', content)

        # Pattern 2: Sau dấu ngoặc kép đóng + bất kỳ ký tự nào (không phải space hoặc newline)
        content = re.sub(r'([""」])([^\s\n])', r'\1\n\n\2', content)

        # Pattern 3: Sau dấu câu + space + ký tự (để handle trường hợp có space)
        content = re.sub(r'([。！？])\s+([^\s\n])', r'\1\n\n\2', content)

        # Pattern 4: Sau dấu ngoặc kép đóng + space + ký tự
        content = re.sub(r'([""」])\s+([^\s\n])', r'\1\n\n\2', content)

        # Clean up multiple newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Remove leading/trailing whitespace from each line
        lines = content.split('\n')
        clean_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if line:  # Only add non-empty lines
                if i == 0:
                    clean_lines.append("'" + line)  # Thêm dấu ' vào dòng đầu tiên
                else:
                    clean_lines.append(line)
            elif clean_lines and clean_lines[-1]:  # Add empty line only if previous line wasn't empty
                clean_lines.append('')

        return '\n'.join(clean_lines)

    @staticmethod
    def clean_content(content):
        """
        Clean content cho piaotia.com

        Args:
            content (str): Raw content

        Returns:
            str: Cleaned content
        """
        if not content:
            return ""

        # Remove HTML entities
        content = content.replace('&nbsp;', ' ')
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        content = content.replace('&amp;', '&')

        # Remove extra whitespace (but preserve newlines)
        content = re.sub(r'[ \t]+', ' ', content)  # Only collapse spaces and tabs, not newlines
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Collapse multiple newlines to double newlines

        # Remove ads và watermarks
        content = re.sub(r'飘天文学.*?www\.piaotia\.com', '', content, flags=re.IGNORECASE)
        content = re.sub(r'www\.piaotia\.com', '', content, flags=re.IGNORECASE)

        content = content.strip()
        return content
