import os
import sys
import re
import json
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class AdvancedNovelCrawler:
    def __init__(self, headless=True, delay=2, timeout=30000, browser_type='chromium'):
        """
        Khởi tạo crawler nâng cao với Playwright
        
        Args:
            headless: Chạy browser ẩn (True) hay hiển thị (False)
            delay: Thời gian delay giữa các request (giây)
            timeout: Timeout cho page load (ms)
            browser_type: 'chromium', 'firefox', hoặc 'edge'
        """
        self.headless = headless
        self.delay = delay
        self.timeout = timeout
        self.browser_type = browser_type
        self.browser = None
        self.context = None
        self.page = None
        
    def start_browser(self):
        """Khởi động browser"""
        self.playwright = sync_playwright().start()
        
        # Chọn browser engine
        if self.browser_type == 'edge':
            try:
                browser_engine = self.playwright.chromium
                channel = 'msedge'
            except:
                print("⚠️  Edge không khả dụng, chuyển sang Chromium")
                browser_engine = self.playwright.chromium
                channel = None
        elif self.browser_type == 'firefox':
            browser_engine = self.playwright.firefox
            channel = None
        else:
            browser_engine = self.playwright.chromium
            channel = None
        
        # Args chung để bypass detection
        common_args = [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-field-trial-config',
            '--disable-ipc-flooding-protection',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-extensions-except',
            '--disable-plugins-discovery',
            '--disable-component-extensions-with-background-pages'
        ]
        
        # Khởi tạo browser
        if channel:
            self.browser = browser_engine.launch(
                headless=self.headless,
                channel=channel,
                args=common_args
            )
        else:
            self.browser = browser_engine.launch(
                headless=self.headless,
                args=common_args
            )
        
        # Tạo context với fake fingerprint
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            viewport={'width': 1920, 'height': 1080},
            screen={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            color_scheme='light',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        
        # Adblock bypass scripts
        self.page.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        name: 'Chrome PDF Plugin',
                        description: 'Portable Document Format',
                        length: 1,
                    },
                    {
                        name: 'Chrome PDF Viewer',
                        description: '',
                        length: 1,
                    },
                    {
                        name: 'Native Client',
                        description: '',
                        length: 1,
                    }
                ],
            });
            
            // Mock language
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
            });
            
            // Mock chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Disable adblock detection
            Object.defineProperty(window, 'navigator', {
                value: new Proxy(navigator, {
                    has: (target, key) => (key === 'webdriver' ? false : key in target),
                    get: (target, key) =>
                        key === 'webdriver' ? undefined :
                        key === 'plugins' ? target.plugins :
                        key === 'languages' ? ['zh-CN', 'zh', 'en-US', 'en'] :
                        typeof target[key] === 'function' ? target[key].bind(target) : target[key]
                }),
                configurable: false
            });
            
            // Block common adblock detection
            const originalQuery = window.document.querySelector;
            const originalQueryAll = window.document.querySelectorAll;
            
            window.document.querySelector = function(selector) {
                if (selector && selector.includes && (
                    selector.includes('adblock') || 
                    selector.includes('ad-block') ||
                    selector.includes('adblocker')
                )) {
                    return null;
                }
                return originalQuery.call(this, selector);
            };
            
            window.document.querySelectorAll = function(selector) {
                if (selector && selector.includes && (
                    selector.includes('adblock') || 
                    selector.includes('ad-block') ||
                    selector.includes('adblocker')
                )) {
                    return [];
                }
                return originalQueryAll.call(this, selector);
            };
            
            // Mock common adblock detection variables
            window.canRunAds = true;
            window.isAdBlockActive = false;
            window.adBlockEnabled = false;
            window.blockAdBlock = undefined;
            window.AdBlockDetector = undefined;
            
            console.log('Anti-adblock bypass loaded');
        """)
        
    def close_browser(self):
        """Đóng browser"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def extract_content_from_page(self, url):
        """
        Trích xuất nội dung từ trang web.
        
        Args:
            url: URL của trang
            
        Returns:
            Tuple (tiêu đề, nội dung, next_url)
        """
        try:
            print(f"Đang tải trang: {url}")
            
            # Navigate đến trang
            response = self.page.goto(url, wait_until='networkidle')
            
            if not response or response.status >= 400:
                print(f"Lỗi HTTP {response.status if response else 'Unknown'}")
                return None, None, None
            
            # Đợi trang load
            self.page.wait_for_timeout(1000)
            
            # Remove adblock popup
            self.page.evaluate("""
                // Remove common adblock overlays
                const selectors = [
                    '[class*="adblock"]',
                    '[id*="adblock"]',
                    '[class*="ad-block"]', 
                    '[id*="ad-block"]',
                    '.adblock-overlay',
                    '.adblock-popup',
                    '.anti-adblock',
                    '.adblocker-overlay'
                ];
                
                selectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        if (el && el.style) {
                            el.style.display = 'none';
                            el.remove();
                        }
                    });
                });
                
                // Also try to click any "Continue" or "Disable adblock" buttons
                const buttons = document.querySelectorAll('button, a, div[role="button"]');
                buttons.forEach(btn => {
                    const text = btn.textContent.toLowerCase();
                    if (text.includes('continue') || text.includes('tiếp tục') || 
                        text.includes('đóng') || text.includes('close')) {
                        btn.click();
                    }
                });
            """)
            
            # Đợi content load đầy đủ
            print("⏳ Đợi content load...")
            self.page.wait_for_timeout(3000)
            
            # Kiểm tra lỗi
            page_content = self.page.content()
            error_indicators = [
                '內容加載失敗',
                '请刷新',
                '更換瀏覽器',
                '加载失败',
                'loading failed'
            ]
            
            for indicator in error_indicators:
                if indicator.lower() in page_content.lower():
                    print(f"⚠️  Phát hiện thông báo lỗi: {indicator}")
                    print("Thử refresh trang...")
                    self.page.reload(wait_until='networkidle')
                    self.page.wait_for_timeout(3000)
                    break
            
            # Lấy title
            title = self.page.evaluate("""
                () => {
                    const titleEl = document.querySelector('#mlfy_main_text h1');
                    return titleEl ? titleEl.innerText.trim() : 'Không có tiêu đề';
                }
            """)
            
            # Trích xuất nội dung trực tiếp
            content = self.page.evaluate("""
                () => {
                    const textContent = document.getElementById('TextContent');
                    if (!textContent) return null;
                    
                    const paragraphs = Array.from(textContent.querySelectorAll('p'));
                    return paragraphs.map(p => p.innerText.trim()).join('\\n\\n');
                }
            """)

            if not content:
                print(f"❌ Không thể trích xuất nội dung từ #TextContent")
                return title, None, None
            
            # Clean up content
            content = self.clean_content(content)
            
            # Tìm link trang tiếp theo
            next_url = self.page.evaluate(f"""
                () => {{
                    const navDiv = document.querySelector('.mlfy_page');
                    if (!navDiv) return null;
                    
                    const links = navDiv.querySelectorAll('a[href]');
                    for (let link of links) {{
                        if (link.textContent.includes('下一页')) {{
                            const href = link.getAttribute('href');
                            if (href.startsWith('http')) {{
                                return href;
                            }} else {{
                                return new URL(href, '{url}').href;
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            
            print(f"✅ Trích xuất thành công: {title}")
            return title, content, next_url
            
        except Exception as e:
            print(f"❌ Lỗi khi trích xuất từ {url}: {e}")
            return None, None, None
    
    def clean_content(self, content):
        """
        Clean content nhẹ nhàng, giữ nguyên structure
        """
        if not content:
            return content
            
        # Chỉ fix những encoding issues rõ ràng
        replacements = {
            '\u200b': '',  # Zero-width space
            '\u200c': '',  # Zero-width non-joiner
            '\u200d': '',  # Zero-width joiner
            '\ufeff': '',  # Byte order mark
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        # Chỉ remove excessive line breaks, không thay đổi structure
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        return content.strip()
    
    def _get_base_chapter_id(self, url):
        """
        Trích xuất ID chương cơ bản từ URL để gộp các phần của cùng một chương.
        Ví dụ: '.../274968.html' -> '274968'
               '.../274968_2.html' -> '274968'
        """
        if not url:
            return None
        try:
            filename = os.path.basename(urlparse(url).path)
            # Bỏ phần đuôi .html, ví dụ '274968_2'
            chapter_part = filename.split('.html')[0]
            # Lấy phần trước dấu '_', ví dụ '274968'
            base_chapter_id = chapter_part.split('_')[0]
            return base_chapter_id
        except (IndexError, AttributeError):
            print(f"⚠️  Không thể parse ID chương từ URL: {url}")
            return None
    
    def crawl_from_url(self, start_url, output_dir=None, max_chapters=None, save_format='txt'):
        """
        Crawl từ URL bắt đầu, có khả năng gộp các phần của cùng một chương.
        
        Args:
            start_url: URL bắt đầu
            output_dir: Thư mục lưu output
            max_chapters: Số chương tối đa cần crawl
            save_format: Định dạng lưu file
            
        Returns:
            List các (title, content, url) đã crawl
        """
        results = []
        current_url = start_url
        chapter_count = 0
        
        self.start_browser()
        
        try:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            while current_url and (max_chapters is None or chapter_count < max_chapters):
                print(f"\n🌐 Bắt đầu crawl chương {chapter_count + 1} từ: {current_url}")
                
                # Trích xuất nội dung trang đầu tiên của chương
                title, first_content, next_url = self.extract_content_from_page(current_url)
                
                if not title or not first_content:
                    print("❌ Không thể trích xuất nội dung, dừng crawl.")
                    break
                
                full_chapter_content = [first_content]
                page_in_chapter_url = current_url

                # Vòng lặp để gộp các phần của cùng một chương
                while True:
                    base_current_id = self._get_base_chapter_id(page_in_chapter_url)
                    base_next_id = self._get_base_chapter_id(next_url)
                    
                    if base_current_id and base_next_id and base_current_id == base_next_id:
                        # Trang tiếp theo là một phần của chương hiện tại
                        page_in_chapter_url = next_url
                        print(f"  Found chapter part: {page_in_chapter_url}")
                        
                        # Chỉ cần lấy nội dung và link trang kế tiếp
                        _, part_content, next_url = self.extract_content_from_page(page_in_chapter_url)
                        
                        if part_content:
                            full_chapter_content.append(part_content)
                        else:
                            print("  Không thể lấy nội dung phần này, kết thúc chương tại đây.")
                            break
                    else:
                        # Trang tiếp theo là chương mới hoặc đã hết, kết thúc chương hiện tại
                        break

                # Gộp nội dung và lưu
                final_content = '\n\n'.join(full_chapter_content)
                results.append((title, final_content, current_url))
                
                if output_dir:
                    self.save_content(
                        title, final_content, output_dir, chapter_count + 1, save_format
                    )
                else:
                    print(f"\n=== {title} ===")
                    print(final_content[:300] + "..." if len(final_content) > 300 else final_content)
                    print(f"\n(Đã gộp {len(full_chapter_content)} phần)")
                    print("\n" + "="*50 + "\n")

                chapter_count += 1
                current_url = next_url # Chuyển sang chương mới
                
                if current_url:
                    print(f"⏳ Đợi {self.delay} giây trước khi crawl chương tiếp theo...")
                    time.sleep(self.delay)
            
        except KeyboardInterrupt:
            print("\n⚠️  Người dùng dừng crawl")
        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng: {e}")
        finally:
            self.close_browser()
        
        print(f"\n🎉 Hoàn thành! Đã crawl {len(results)} chương.")
        return results
    
    def save_content(self, title, content, output_dir, page_num, save_format):
        """
        Lưu nội dung vào file
        
        Args:
            title: Tiêu đề
            content: Nội dung
            output_dir: Thư mục lưu
            page_num: Số thứ tự trang
            save_format: Định dạng lưu
        """
        # Tạo tên file an toàn
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        
        base_filename = f"{page_num:03d}_{safe_title}"
        
        if save_format in ['txt', 'both']:
            txt_file = os.path.join(output_dir, f"{base_filename}.txt")
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n\n{content}")
            print(f"📄 Đã lưu: {txt_file}")
        
        if save_format in ['json', 'both']:
            json_file = os.path.join(output_dir, f"{base_filename}.json")
            data = {
                'title': title,
                'content': content,
                'page_number': page_num
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"📋 Đã lưu: {json_file}")

def main():
    print("🚀 Advanced Novel Crawler với Font Analysis")
    print("=" * 60)
    
    # Chọn browser
    print("Chọn browser:")
    print("1. Edge (khuyến nghị)")
    print("2. Chromium")
    print("3. Firefox")
    
    browser_choice = input("Nhập lựa chọn (1/2/3) [mặc định: 1]: ").strip() or '1'
    
    if browser_choice == '1':
        browser_type = 'edge'
    elif browser_choice == '3':
        browser_type = 'firefox'
    else:
        browser_type = 'chromium'
    
    # Cấu hình crawler
    headless_input = input("Chạy browser ẩn? (y/n) [mặc định: n để debug]: ").strip().lower()
    headless = headless_input == 'y'
    
    delay_input = input("Delay giữa các trang (giây) [mặc định: 3]: ").strip()
    delay = int(delay_input) if delay_input else 3
    
    crawler = AdvancedNovelCrawler(headless=headless, delay=delay, browser_type=browser_type)
    
    # Crawl từ URL
    start_url = input("Nhập URL bắt đầu: ").strip()
    
    output_dir = input("Nhập thư mục lưu file (để trống để chỉ hiển thị): ").strip()
    if output_dir == "":
        output_dir = None
    
    max_chapters_input = input("Số chương tối đa (để trống = không giới hạn): ").strip()
    max_chapters = int(max_chapters_input) if max_chapters_input else None
    
    if output_dir:
        save_format = input("Định dạng lưu (txt/json/both) [mặc định: txt]: ").strip() or 'txt'
    else:
        save_format = 'txt'
    
    print(f"\n🔧 Sử dụng {browser_type.title()} browser")
    crawler.crawl_from_url(start_url, output_dir, max_chapters, save_format)

if __name__ == "__main__":
    main() 