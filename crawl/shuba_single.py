#!/usr/bin/env python3
"""
Shuba Single Crawler - Crawl từ chương đầu tiên
================================================

Crawler độc lập cho 69shuba.com, bắt đầu từ URL chương đầu tiên
và tự động crawl theo next_url cho đến hết truyện.
"""

import re
import json
import os
import sys
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin


class ShubaSingleCrawler:
    """Crawler độc lập cho 69shuba.com"""
    
    def __init__(self, output_file="shuba_single_output.txt"):
        self.output_file = output_file
        self.playwright = None
        self.browser = None
        self.page = None
        self.crawled_urls = set()  # Track URLs đã crawl để tránh loop
        
    def start_browser(self):
        """Khởi động browser Edge"""
        print("🌐 Khởi động browser Edge...")
        self.playwright = sync_playwright().start()
        
        # Sử dụng Edge browser
        self.browser = self.playwright.chromium.launch(
            headless=False,  # Hiển thị browser để debug
            channel='msedge',
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security'
            ]
        )
        
        self.page = self.browser.new_page()
        
        # Set user agent
        self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        })
        
        print("✅ Browser khởi động thành công")
    
    def close_browser(self):
        """Đóng browser"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("🔒 Browser đã đóng")
    
    def extract_content(self, url):
        """
        Extract content từ một trang 69shuba.com
        Sử dụng logic từ shuba_parser.py
        """
        try:
            print(f"📖 Crawling: {url}")
            
            # Navigate to page
            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state('networkidle')
            
            # Extract title từ h1.hide720 hoặc từ JavaScript bookinfo
            title = "Không có tiêu đề"
            
            # Thử lấy từ h1 element
            title_el = self.page.query_selector('h1.hide720')
            if title_el:
                title = title_el.inner_text().strip()
                print(f"  ✅ Title: {title}")
            else:
                # Fallback: lấy từ JavaScript bookinfo.chaptername
                page_source = self.page.content()
                match = re.search(r'chaptername:\s*[\'"]([^\'"]+)[\'"]', page_source)
                if match:
                    title = match.group(1)
                    print(f"  ✅ Title từ JS: {title}")
                else:
                    print(f"  ⚠️  Không tìm thấy title!")
            
            # Extract content từ div.txtnav
            content = ""
            content_container = self.page.query_selector('div.txtnav')
            if content_container:
                print(f"  ✅ Tìm thấy div.txtnav")
                content_html = content_container.inner_html()
                print(f"  📏 HTML content length: {len(content_html)} chars")
                
                # Clean HTML content
                content_text = self._clean_html_content(content_html, title)
                content = content_text.strip()
                print(f"  📝 Cleaned content length: {len(content)} chars")
            else:
                print(f"  ❌ KHÔNG tìm thấy div.txtnav!")
                content = ""
            
            # Extract next URL từ JavaScript bookinfo.next_page
            next_url = None
            try:
                page_source = self.page.content()
                match = re.search(r'next_page:\s*[\'"]([^\'"]+)[\'"]', page_source)
                if match:
                    next_page = match.group(1)
                    if next_page and next_page != 'index.html':
                        # Kiểm tra xem next_page đã là absolute URL chưa
                        if next_page.startswith('http'):
                            next_url = next_page  # Đã là absolute URL
                        else:
                            # Build absolute URL từ relative path
                            base_url = '/'.join(url.split('/')[:-1])
                            next_url = f"{base_url}/{next_page}"
                        print(f"  ➡️  Next URL: {next_url}")
                    else:
                        print(f"  🏁 Không có next URL (có thể là chapter cuối)")
            except Exception as e:
                print(f"  ⚠️  Lỗi extract next_url: {e}")
                next_url = None
            
            return {
                'title': title,
                'content': content,
                'next_url': next_url,
                'success': bool(content)
            }
            
        except Exception as e:
            print(f"❌ Lỗi crawl {url}: {e}")
            return {
                'title': None,
                'content': None,
                'next_url': None,
                'success': False
            }
    
    def _clean_html_content(self, html_content, extracted_title=None):
        """
        Clean HTML content và convert sang text
        Logic từ shuba_parser.py
        """
        if not html_content:
            return ""
        
        # Loại bỏ các phần không cần thiết
        html_content = re.sub(r'<h1[^>]*class="hide720"[^>]*>.*?</h1>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<div[^>]*class="txtinfo[^"]*"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<div[^>]*id="txtright"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<div[^>]*class="bottom-ad"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
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
    
    def crawl_from_first_chapter(self, first_url, max_chapters=None):
        """
        Crawl từ chương đầu tiên cho đến hết
        
        Args:
            first_url: URL của chương đầu tiên
            max_chapters: Giới hạn số chương (None = không giới hạn)
        """
        print(f"🚀 Bắt đầu crawl từ: {first_url}")
        print(f"📁 Output file: {self.output_file}")
        if max_chapters:
            print(f"📊 Giới hạn: {max_chapters} chương")
        
        # Khởi động browser
        self.start_browser()
        
        try:
            # Tạo output file
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write("=== Shuba Single Crawler Output ===\n\n")
            
            current_url = first_url
            chapter_count = 0
            
            while current_url and current_url not in self.crawled_urls:
                # Kiểm tra giới hạn
                if max_chapters and chapter_count >= max_chapters:
                    print(f"📊 Đã đạt giới hạn {max_chapters} chương")
                    break
                
                # Crawl chapter hiện tại
                result = self.extract_content(current_url)
                
                if not result['success']:
                    print(f"❌ Không thể crawl: {current_url}")
                    break
                
                # Ghi vào file
                self._write_chapter_to_file(result, chapter_count + 1)
                
                # Đánh dấu đã crawl
                self.crawled_urls.add(current_url)
                chapter_count += 1
                
                print(f"✅ Hoàn thành chương {chapter_count}: {result['title']}")
                
                # Chuyển sang chương tiếp theo
                current_url = result['next_url']
                
                if current_url:
                    print(f"⏳ Đợi 3 giây trước khi crawl tiếp...")
                    import time
                    time.sleep(3)
            
            print(f"🎉 Hoàn thành crawl: {chapter_count} chương")
            print(f"📁 Kết quả lưu tại: {self.output_file}")
            
        except KeyboardInterrupt:
            print("\n⏹️  Crawl bị dừng bởi user")
        except Exception as e:
            print(f"❌ Lỗi trong quá trình crawl: {e}")
        finally:
            self.close_browser()
    
    def _write_chapter_to_file(self, result, chapter_num):
        """Ghi chapter vào file output"""
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(f"Chapter {chapter_num}: {result['title']}\n")
                if result['content']:
                    f.write(f"{result['content']}\n\n")
                else:
                    f.write("(Không có nội dung)\n\n")
        except Exception as e:
            print(f"❌ Lỗi ghi file: {e}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python shuba_single.py <first_chapter_url> [max_chapters] [output_file]")
        print("Example: python shuba_single.py https://www.69shuba.com/txt/85122/39443144 10")
        return
    
    first_url = sys.argv[1]
    max_chapters = int(sys.argv[2]) if len(sys.argv) > 2 else None
    output_file = sys.argv[3] if len(sys.argv) > 3 else "shuba_single_output.txt"
    
    crawler = ShubaSingleCrawler(output_file)
    crawler.crawl_from_first_chapter(first_url, max_chapters)


if __name__ == "__main__":
    main()
