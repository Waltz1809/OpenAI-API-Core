#!/usr/bin/env python3
"""
ShubaParser - Parser cho 69shuba.com
====================================

Parser chính cho www.69shuba.com sử dụng Playwright
Đọc từ JSON mapping và extract content từ div.txtnav
"""

import re
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin
from .base_parser import StandardParserMixin

# Add dich_cli to path để sử dụng PathHelper
project_root = Path(__file__).parent.parent.parent.parent.parent  # parsers -> crawl -> python -> test -> Dich
sys.path.insert(0, str(project_root / "dich_cli"))
from core.path_helper import get_path_helper  # type: ignore[import]


class ShubaParser(StandardParserMixin):
    """Parser cho www.69shuba.com"""
    
    @staticmethod
    def extract_content(page, current_url):
        """
        Extract content từ một trang www.69shuba.com
        
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
            print(f"  🔍 Debug: Bắt đầu extract content từ {current_url}")
            
            # Extract title từ h1.hide720 hoặc từ JavaScript bookinfo
            title = "Không có tiêu đề"
            
            # Thử lấy từ h1 element
            title_el = page.query_selector('h1.hide720')
            if title_el:
                title = title_el.inner_text().strip()
                print(f"  ✅ Tìm thấy title từ h1: {title}")
            else:
                # Fallback: lấy từ JavaScript bookinfo.chaptername
                page_source = page.content()
                match = re.search(r'chaptername:\s*[\'"]([^\'"]+)[\'"]', page_source)
                if match:
                    title = match.group(1)
                    print(f"  ✅ Tìm thấy title từ JS: {title}")
                else:
                    print(f"  ⚠️  Không tìm thấy title!")
            
            
            # Volume không có trên site này
            volume = ""
            
            # Extract content từ div.txtnav - lấy toàn bộ trước, sau đó clean
            content = ""
            content_container = page.query_selector('div.txtnav')
            if content_container:
                print(f"  ✅ Tìm thấy div.txtnav")
                # Lấy toàn bộ HTML content của div.txtnav
                content_html = content_container.inner_html()
                print(f"  📏 HTML content length: {len(content_html)} chars")
                
                # Clean HTML bằng cách loại bỏ các phần không cần thiết
                content_text = ShubaParser._clean_html_content(content_html, title)
                content = content_text.strip()
                print(f"  📝 Cleaned content length: {len(content)} chars")
            else:
                print(f"  ❌ KHÔNG tìm thấy div.txtnav!")
                content = ""
            
            # Extract next URL từ JavaScript bookinfo.next_page
            next_url = None
            try:
                page_source = page.content()
                match = re.search(r'next_page:\s*[\'"]([^\'"]+)[\'"]', page_source)
                if match:
                    next_page = match.group(1)
                    if next_page and next_page != 'index.html':
                        # Build absolute URL
                        base_url = '/'.join(current_url.split('/')[:-1])
                        next_url = f"{base_url}/{next_page}"
                        print(f"  ➡️  Next URL: {next_url}")
                    else:
                        print(f"  🏁 Không có next URL (có thể là chapter cuối)")
            except Exception as e:
                print(f"  ⚠️  Lỗi extract next_url: {e}")
                next_url = None
            
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
            print(f"❌ Lỗi parse content 69shuba: {e}")
            import traceback
            traceback.print_exc()
            return {
                'title': None,
                'volume': None,
                'content': None,
                'next_url': None,
                'success': False
            }
    
    @staticmethod
    def _clean_html_content(html_content, extracted_title=None):
        """Clean HTML content và convert sang text"""
        if not html_content:
            return ""
        
        # Loại bỏ các phần không cần thiết trước khi parse
        # Loại bỏ h1.hide720 (title)
        html_content = re.sub(r'<h1[^>]*class="hide720"[^>]*>.*?</h1>', '', html_content, flags=re.DOTALL)
        
        # Loại bỏ div.txtinfo (author, date info)
        html_content = re.sub(r'<div[^>]*class="txtinfo[^"]*"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        
        # Loại bỏ div#txtright (ads/scripts)
        html_content = re.sub(r'<div[^>]*id="txtright"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        
        # Loại bỏ div.bottom-ad (ads)
        html_content = re.sub(r'<div[^>]*class="bottom-ad"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        
        # Loại bỏ scripts
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        
        # Loại bỏ các div ads khác
        html_content = re.sub(r'<div[^>]*class="contentadv"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        
        # Convert HTML entities
        html_content = html_content.replace('&#8195;&#8195;', '    ')  # Em spaces
        html_content = html_content.replace('<br>', '\n')
        html_content = html_content.replace('<br/>', '\n')
        html_content = html_content.replace('<br />', '\n')
        
        # Loại bỏ các thẻ HTML còn lại
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Loại bỏ title đã extract khỏi content (nếu có)
        if extracted_title:
            # Loại bỏ dòng đầu tiên nếu nó giống với title đã extract
            lines = html_content.split('\n')
            if lines and lines[0].strip() == extracted_title.strip():
                lines = lines[1:]  # Bỏ dòng đầu tiên
                html_content = '\n'.join(lines)
        
        # Clean up whitespace
        lines = []
        for line in html_content.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
        
        # Thêm dấu ' vào dòng đầu tiên (sau khi đã clean)
        if lines:
            lines[0] = "'" + lines[0]
        
        return '\n\n'.join(lines)

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
        
        # Normalize Chinese spaces
        content = re.sub(r'　+', '　　', content)
        
        return content.strip()
    
    @staticmethod
    def get_catalog_links_from_config(page, catalog_url, series_config):
        """
        Lấy danh sách links từ JSON mapping
        
        Args:
            page: Playwright page (KHÔNG SỬ DỤNG, chỉ để compatible)
            catalog_url: URL của trang mục lục (không cần thiết nếu dùng JSON)
            series_config: Dict config của series
            
        Returns:
            list: Danh sách chapter URLs hoặc dicts
        """
        # Ưu tiên JSON mapping
        json_mapping = series_config.get('json_mapping')
        if json_mapping:
            # Sử dụng PathHelper để resolve path (tự động xử lý relative/absolute)
            ph = get_path_helper()
            json_path = ph.resolve(json_mapping)
            
            if not os.path.exists(json_path):
                print(f"  ❌ Không tìm thấy file JSON: {json_mapping}")
                print(f"     Đã thử: {json_path}")
                return []
            
            print(f"  📖 Đọc JSON mapping: {ph.relative_to_project(json_path)}")
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                links = []
                for item in data:
                    # Support both single URL and multiple URLs
                    urls = item.get('urls', [item.get('url')])
                    if isinstance(urls, str):
                        urls = [urls]
                    
                    links.append({
                        'chapter_num': item.get('chapter_num'),
                        'title': item.get('title', ''),
                        'url': urls[0] if urls else None,
                        'urls': urls
                    })
                
                print(f"  ✅ Đọc được {len(links)} chapters từ JSON")
                return links
                
            except Exception as e:
                print(f"  ❌ Lỗi đọc JSON mapping: {e}")
                return []
        
        print("  ❌ Không có JSON mapping")
        return []