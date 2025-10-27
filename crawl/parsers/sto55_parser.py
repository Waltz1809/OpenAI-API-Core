#!/usr/bin/env python3
"""
Sto55 Parser Module
===================

Parser chuyên dụng cho sto55.com (思兔閱讀)
Trích xuất: title, content, next_url

Sử dụng JSON-only approach
"""

import re
from urllib.parse import urljoin
from .base_parser import BaseParser, StandardParserMixin


class Sto55Parser(StandardParserMixin):
    """Parser cho sto55.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang sto55.com

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
            # Extract title từ h1.pt10
            title = "Không có tiêu đề"
            title_el = page.query_selector('h1.pt10')
            if title_el:
                title = title_el.inner_text().strip()
                print(f"  ✅ Tìm thấy title: {title}")
            else:
                print(f"  ⚠️  Không tìm thấy title!")

            # Volume không có trên site này
            volume = ""

            # Extract content từ div.readcotent
            content = ""
            content_div = page.query_selector('div.readcotent')
            if content_div:
                print(f"  ✅ Tìm thấy div.readcotent")
                # Lấy HTML content
                content_html = content_div.inner_html()
                
                # Clean HTML và extract text
                content_text = Sto55Parser._clean_html_content(content_html)
                content = content_text.strip()
                print(f"  📝 Cleaned content length: {len(content)} chars")
            else:
                print(f"  ❌ KHÔNG tìm thấy div.readcotent!")
                content = ""

            # Extract next URL từ navigation links
            next_url = ""
            try:
                # Tìm link có id="linkNext"
                next_link = page.query_selector('#linkNext')
                if next_link:
                    href = next_link.get_attribute('href')
                    if href:
                        next_url = urljoin(current_url, href)
                        # Kiểm tra nếu next_url trỏ về catalog thì không có next
                        if '/book/' in next_url and next_url.count('/') == 4:
                            # URL format: https://sto55.com/book/57037/ (catalog)
                            # vs https://sto55.com/book/57037/28554626.html (chapter)
                            if not next_url.endswith('.html'):
                                next_url = ""
                        print(f"  ➡️  Next URL: {next_url}")
                    else:
                        print(f"  🏁 Không có next URL")
            except Exception as e:
                print(f"  ⚠️  Lỗi extract next_url: {e}")

            print(f"  📊 Kết quả extract:")
            print(f"    - Title: {title}")
            print(f"    - Content length: {len(content)}")
            print(f"    - Next URL: {next_url}")
            print(f"    - Success: {bool(content)}")

            return {
                'title': title,
                'volume': volume,
                'content': content,
                'next_url': next_url,
                'success': bool(content)
            }

        except Exception as e:
            print(f"⚠️  Lỗi extract content từ sto55: {e}")
            import traceback
            traceback.print_exc()
            return {
                'title': "",
                'volume': "",
                'content': "",
                'next_url': "",
                'success': False
            }
    
    @staticmethod
    def _clean_html_content(html_content):
        """
        Clean HTML content từ sto55.com
        
        Loại bỏ:
        - Ads (ADVERTISEMENT divs, adsbygoogle ins)
        - Scripts
        - Navigation text
        - Watermarks
        
        Args:
            html_content (str): Raw HTML content
            
        Returns:
            str: Cleaned text content
        """
        if not html_content:
            return ""
        
        # Loại bỏ script tags
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Loại bỏ ads divs
        html_content = re.sub(r'<div[^>]*class="ADVERTISEMENT"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Loại bỏ adsbygoogle ins tags
        html_content = re.sub(r'<ins[^>]*class="adsbygoogle"[^>]*>.*?</ins>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Loại bỏ div with style="text-align:center;" (chứa ads)
        html_content = re.sub(r'<div[^>]*style="text-align:center;"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Loại bỏ iframe tags
        html_content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace <br> với newlines
        html_content = html_content.replace('<br><br>', '\n\n')
        html_content = html_content.replace('<br>', '\n')
        html_content = html_content.replace('<br/>', '\n')
        html_content = html_content.replace('<br />', '\n')
        
        # Loại bỏ tất cả HTML tags còn lại
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        html_content = html_content.replace('&nbsp;', ' ')
        html_content = html_content.replace('&lt;', '<')
        html_content = html_content.replace('&gt;', '>')
        html_content = html_content.replace('&amp;', '&')
        html_content = html_content.replace('&#8195;&#8195;', '  ')
        
        # Split thành lines và clean
        lines = html_content.split('\n')
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip watermark lines
            if any(watermark in line for watermark in [
                '本章節來源於',
                'STO55.COM',
                'sto55.com',
                '𝕊𝕋𝕆𝟝𝟝',
                'ℂ𝕆𝕄'
            ]):
                continue
            
            # Skip ads text
            if 'ADVERTISEMENT' in line:
                continue
            
            # Thêm line hợp lệ
            clean_lines.append(line)
        
        # Thêm dấu ' vào dòng đầu tiên (nếu có)
        if clean_lines:
            clean_lines[0] = "'" + clean_lines[0]
        
        # Join với double newlines để tạo paragraphs
        return '\n\n'.join(clean_lines)
    
    @staticmethod
    def clean_content(content):
        """
        Clean content cho sto55.com
        
        Args:
            content (str): Raw content
            
        Returns:
            str: Cleaned content
        """
        if not content:
            return ""
        
        # Remove zero-width characters
        replacements = {
            '\u200b': '',  # Zero-width space
            '\u200c': '',  # Zero-width non-joiner
            '\u200d': '',  # Zero-width joiner
            '\ufeff': '',  # Byte order mark
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        # Remove extra whitespace (but preserve paragraph breaks)
        content = re.sub(r'[ \t]+', ' ', content)  # Collapse spaces and tabs
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Collapse multiple newlines
        
        # Remove any remaining watermarks
        content = re.sub(r'本章節來源於.*?COM', '', content, flags=re.IGNORECASE)
        content = re.sub(r'STO55\.COM', '', content, flags=re.IGNORECASE)
        
        return content.strip()

