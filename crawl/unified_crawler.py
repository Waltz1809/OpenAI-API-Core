#!/usr/bin/env python3
"""
Unified Novel Crawler
====================

Crawler với config JSON, retry mechanism và single TXT output
Hỗ trợ crawl nhiều series từ tw.linovelib.com
"""

import os
import json
import time
import re
import logging
import yaml
from datetime import datetime
from playwright.sync_api import sync_playwright
from parsers.tw_parser import TWLinovelibParser
from parsers.hjwzw_parser import HjwzwParser
from parsers.zhswx_parser import ZhswxParser
from parsers.dxmwx_parser import DxmwxParser
from parsers.shuba_parser import ShubaParser
from parsers.czbooks_parser import CZBooksParser
from parsers.piaotia_parser import PiaotiaParser
from parsers.quanben_parser import QuanbenParser
from parsers.sto55_parser import Sto55Parser
from chapter_detection import enhance_chapter_detection

from clean_logger import CleanLogger, PiaotiaLogger
import sys


class UnifiedCrawler:
    """Main crawler với config và retry mechanism"""
    
    def __init__(self, config_file="config.json"):
        """
        Args:
            config_file: Đường dẫn đến file config JSON
        """
        self.config_file = config_file
        self.config = self.load_config()
        self.settings = self.config.get('settings', {})
        
        # Browser instances
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Stats
        self.error_count = 0
        self.restart_threshold = self.settings.get('browser_restart_after_errors', 5)
        self.current_parser = None  # Parser hiện tại cho series
        

        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Thiết lập logging system"""
        log_dir = self.settings.get('log_dir', 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"crawler_{timestamp}.log")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # Console output
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Crawler khởi động")
        self.logger.info(f"📋 Config file: {self.config_file}")
        print(f"📝 Log file: {log_file}")
    
    def load_config(self):
        """Load config từ JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Lỗi load config: {e}")
            return {"series": [], "settings": {}}
    
    def start_browser(self):
        """Khởi động browser với anti-detection"""
        try:
            if self.playwright:
                self.close_browser()
            
            self.playwright = sync_playwright().start()
            
            # Browser engine: lấy từ config hoặc mặc định là chromium
            browser_type = self.settings.get('browser', 'chromium').lower()
            headless_mode = self.settings.get('headless', True)
            print(f"🌐 Khởi động browser: {browser_type.title()}")
            print(f"👁️  Headless mode: {'Bật' if headless_mode else 'TẮT (Debug mode)'}")
            
            # Chọn browser engine
            if browser_type == 'edge':
                self.browser = self.playwright.chromium.launch(
                    headless=headless_mode,
                    channel='msedge',  # Sử dụng Microsoft Edge
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ]
                )
            elif browser_type == 'firefox':
                self.browser = self.playwright.firefox.launch(
                    headless=headless_mode,
                    args=['--no-sandbox']
                )
            elif browser_type == 'webkit':
                self.browser = self.playwright.webkit.launch(
                    headless=headless_mode,
                    args=['--no-sandbox']
                )
            else:  # chromium (mặc định)
                self.browser = self.playwright.chromium.launch(
                    headless=headless_mode,
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ]
                )
            
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            self.page = self.context.new_page()
            self.page.set_default_timeout(self.settings.get('timeout', 30000))
            
            # Anti-detection script
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
            """)
            
            print("🌐 Browser đã khởi động")
            return True
            
        except Exception as e:
            print(f"❌ Lỗi khởi động browser: {e}")
            return False
    
    def close_browser(self):
        """Đóng browser và cleanup"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            
        except Exception as e:
            print(f"⚠️  Lỗi đóng browser: {e}")
    

    
    def get_parser(self, url):
        """Chọn parser phù hợp dựa trên URL"""
        if "hjwzw.com" in url:
            return HjwzwParser
        elif "linovelib.com" in url:
            return TWLinovelibParser
        elif "zhswx.com" in url:
            return ZhswxParser
        elif "dxmwx.org" in url or "dxmwx.com" in url:
            return DxmwxParser
        elif "czbooks.net" in url:
            return CZBooksParser
        elif "piaotia.com" in url:
            return PiaotiaParser
        elif "quanben.io" in url:
            return QuanbenParser
        elif "sto55.com" in url:
            return Sto55Parser
        elif any(domain in url for domain in ["69shuba.com", "69shu.com", "69xinshu.com", "69shu.pro", "69shuba.pro"]):
            # Ưu tiên sử dụng requests parser (tránh timeout với Playwright)
            # Hỗ trợ tất cả domains: 69shuba.com, 69shu.com, 69xinshu.com, 69shu.pro, 69shuba.pro
            return ShubaParser
        else:
            print(f"⚠️  Không tìm thấy parser cho URL: {url}")
            return None

    def get_parser_by_type(self, parser_type):
        """Chọn parser dựa trên type string"""
        parser_map = {
            'hjwzw': HjwzwParser,
            'tw': TWLinovelibParser,
            'linovelib': TWLinovelibParser,
            'zhswx': ZhswxParser,
            'dxmwx': DxmwxParser,
            'czbooks': CZBooksParser,
            'piaotia': PiaotiaParser,
            'quanben': QuanbenParser,
            'shuba': ShubaParser,
            '69shuba': ShubaParser,
            'sto55': Sto55Parser
        }

        parser_cls = parser_map.get(parser_type.lower())
        if not parser_cls:
            print(f"⚠️  Không tìm thấy parser cho type: {parser_type}")
            print(f"📋 Available types: {list(parser_map.keys())}")
        return parser_cls
    
    def crawl_with_retry(self, url):
        """
        Crawl một URL với retry mechanism
        
        Returns:
            dict hoặc None nếu fail
        """
        max_retries = self.settings.get('max_retries', 3)
        retry_delay = self.settings.get('retry_delay', 10)
        
        for attempt in range(max_retries + 1):
            try:
                # Navigate to page
                print(f"📖 Crawl attempt {attempt + 1}: {url}")
                self.logger.info(f"📖 Crawl attempt {attempt + 1}: {url}")
                
                if not self.page:
                    raise Exception("Browser page không khả dụng")
                
                self.page.goto(url, wait_until='networkidle')
                time.sleep(2)  # Đợi content load
                
                # Sử dụng parser từ series config (đã được set ở run_all_series)
                parser = self.current_parser
                if not parser:
                    raise Exception("Không có parser được set")
                
                result = parser.extract_content(self.page, url)
                
                if result['success']:
                    self.error_count = 0  # Reset error count
                    result['original_url'] = url # Lưu lại URL gốc
                    self.logger.info(f"✅ Crawl thành công: {result.get('title', 'No title')}")
                    return result
                else:
                    raise Exception("Failed to extract content")
                    
            except Exception as e:
                self.error_count += 1
                error_msg = f"⚠️  Attempt {attempt + 1} failed: {e}"
                print(error_msg)
                self.logger.warning(error_msg)
                
                # Restart browser nếu quá nhiều lỗi
                if self.error_count >= self.restart_threshold:
                    restart_msg = "🔄 Restart browser do quá nhiều lỗi..."
                    print(restart_msg)
                    self.logger.warning(restart_msg)
                    self.start_browser()
                    self.error_count = 0
                
                if attempt < max_retries:
                    retry_msg = f"⏳ Retry sau {retry_delay} giây..."
                    print(retry_msg)
                    self.logger.info(retry_msg)
                    time.sleep(retry_delay)
                else:
                    fail_msg = f"💥 Thất bại hoàn toàn sau {max_retries + 1} attempts"
                    print(fail_msg)
                    self.logger.error(fail_msg)
                    return None
    
    def run_all_series(self):
        """Chạy crawl cho tất cả series trong config"""
        if not self.start_browser():
            print("❌ Không thể khởi động browser")
            return

        try:
            series_list = self.config.get('series', [])
            enabled_series = [s for s in series_list if s.get('enabled', True)]

            print(f"🚀 Sẽ crawl {len(enabled_series)} series")
            self.logger.info(f"🚀 Sẽ crawl {len(enabled_series)} series")

            for i, series in enumerate(enabled_series):
                print(f"\n{'='*60}")
                print(f"Series {i+1}/{len(enabled_series)}: {series['name']}")
                print('='*60)

                self.logger.info(f"📚 Bắt đầu series {i+1}/{len(enabled_series)}: {series['name']}")

                output_file = series.get('output_file', f"{series['name']}.txt")

                # Đảm bảo thư mục tồn tại
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    print(f"📁 Tạo thư mục: {output_dir}")
                    self.logger.info(f"📁 Tạo thư mục: {output_dir}")

                # JSON-only approach: tất cả parsers đều dùng JSON mapping
                json_mapping = series.get('json_mapping')
                parser_type = series.get('parser', '')

                if not json_mapping:
                    print("❌ Thiếu json_mapping trong series config")
                    self.logger.error("❌ Thiếu json_mapping trong series config")
                    continue

                if not parser_type:
                    print("❌ Thiếu parser type trong series config")
                    self.logger.error("❌ Thiếu parser type trong series config")
                    continue

                print(f"📋 Sử dụng JSON mapping cho parser {parser_type}: {json_mapping}")
                self.logger.info(f"📋 Sử dụng JSON mapping cho parser {parser_type}: {json_mapping}")

                parser_cls = self.get_parser_by_type(parser_type)
                if not parser_cls:
                    print(f"❌ Không tìm thấy parser cho type: {parser_type}")
                    self.logger.error(f"❌ Không tìm thấy parser cho type: {parser_type}")
                    continue
                
                # Set parser cho series này
                self.current_parser = parser_cls

                # Tạo instance của parser để gọi method
                parser_instance = parser_cls()

                # JSON-only: chỉ dùng get_catalog_links_from_config
                enhanced_method = getattr(parser_instance, 'get_catalog_links_from_config', None)
                if enhanced_method and callable(enhanced_method):
                    links = enhanced_method(self.page, "", series)  # catalog_url không cần thiết
                else:
                    print("❌ Parser không có method get_catalog_links_from_config")
                    self.logger.error("❌ Parser không có method get_catalog_links_from_config")
                    continue
                if not links:
                    print("❌ Không tìm thấy link chương trong mục lục")
                    self.logger.error("❌ Không tìm thấy link chương trong mục lục")
                    continue

                # Kiểm tra kiểu dữ liệu của links
                if not isinstance(links, (list, tuple)):
                    print(f"❌ Links không đúng định dạng: {type(links)}")
                    self.logger.error(f"❌ Links không đúng định dạng: {type(links)}")
                    continue

                print(f"� Tìm thấy {len(links)} chương trong mục lục")
                self.logger.info(f"📖 Tìm thấy {len(links)} chương trong mục lục")

                # Xử lý start_chapter từ config
                config_start_chapter = series.get('start_chapter', 1)
                max_chapters = series.get('max_chapters', None)
                delay = self.settings.get('delay_between_requests', 3)
                current_volume = None
                
                # Xác định file mode: nếu start_chapter > 1 thì append, ngược lại ghi đè
                file_mode = 'a' if config_start_chapter > 1 else 'w'
                
                if config_start_chapter > 1:
                    print(f"🎯 Bắt đầu từ chapter {config_start_chapter} (theo config) - Mode: APPEND")
                    self.logger.info(f"🎯 Bắt đầu từ chapter {config_start_chapter} (theo config) - Mode: APPEND")
                else:
                    print(f"🎯 Bắt đầu từ chapter {config_start_chapter} - Mode: OVERWRITE")
                    self.logger.info(f"🎯 Bắt đầu từ chapter {config_start_chapter} - Mode: OVERWRITE")

                # Tính start_index từ config_start_chapter
                start_index = config_start_chapter - 1  # Chuyển từ chapter number sang array index
                
                # Tính end_index
                if max_chapters is None:
                    end_index = len(links)
                else:
                    # max_chapters là tổng số chapters muốn crawl (tính từ đầu)
                    # Nếu start_chapter = 501, max_chapters = 600 -> crawl từ 501 đến 600
                    end_index = min(len(links), max_chapters)

                print(f"🎯 Sẽ crawl từ index {start_index} đến {end_index-1} (tổng {end_index-start_index} chapters)")
                self.logger.info(f"🎯 Sẽ crawl từ index {start_index} đến {end_index-1} (tổng {end_index-start_index} chapters)")

                try:
                    with open(output_file, file_mode, encoding='utf-8') as f:
                        if file_mode == 'w':
                            f.write(f"=== {series['name']} ===\n\n")

                        for idx in range(start_index, end_index):
                            link_data = links[idx]

                            # Xử lý cả dict (từ JSON) và string (từ parser thường)
                            if isinstance(link_data, dict):
                                urls = link_data.get('urls', [link_data.get('url')])  # Support multiple URLs
                                chapter_num = link_data.get('chapter_num', idx + 1)
                                chapter_title = link_data.get('title', '')
                            else:
                                urls = [link_data]  # String URL
                                chapter_num = idx + 1
                                chapter_title = ''

                            # Sử dụng chapter_num từ JSON mapping, fallback về index + 1
                            actual_chapter_num = chapter_num if chapter_num is not None else (idx + 1)
                            chapter_info = f"Chapter {actual_chapter_num}"
                            print(f"📖 Crawl {chapter_info} ({len(urls)} URLs): {chapter_title}")
                            self.logger.info(f"📖 Crawl {chapter_info} ({len(urls)} URLs): {chapter_title}")

                            # Crawl tất cả URLs và merge content
                            merged_content = []
                            merged_title = ""
                            merged_volume = ""

                            for url_idx, url in enumerate(urls):
                                print(f"  📄 Crawl URL {url_idx + 1}/{len(urls)}: {url}")
                                self.logger.info(f"  📄 Crawl URL {url_idx + 1}/{len(urls)}: {url}")

                                result = self.crawl_with_retry(url)
                                if not result:
                                    warn_msg = f"⚠️  Bỏ qua URL {url_idx + 1} của {chapter_info}"
                                    print(warn_msg)
                                    self.logger.warning(warn_msg)
                                    continue

                                title = result.get('title', '').strip()
                                volume = result.get('volume', '').strip()
                                content = result.get('content', '').strip()

                                # Lấy title và volume từ URL đầu tiên
                                if url_idx == 0:
                                    merged_title = title
                                    merged_volume = volume

                                # Merge content
                                if content:
                                    if url_idx == 0:
                                        # Main content: chỉ append content, không thêm title (đã có "Chương X:")
                                        merged_content.append(content)
                                    else:
                                        # Sub content: thêm title (vì title là nội dung) + content
                                        if title:
                                            merged_content.append(f"{title}\n\n{content}")
                                        else:
                                            merged_content.append(content)

                                # Delay giữa các URLs
                                if url_idx < len(urls) - 1:
                                    time.sleep(1)  # Delay ngắn giữa URLs của cùng chapter

                            # Xử lý merged content
                            final_content = '\n\n'.join(merged_content) if merged_content else ''

                            if not final_content:
                                warn_msg = f"⚠️  Bỏ qua {chapter_info} do không có content"
                                print(warn_msg)
                                self.logger.warning(warn_msg)
                                continue

                            self.logger.info(f"📝 Ghi {chapter_info}: {merged_title[:50]}... (merged từ {len(urls)} URLs)")

                            output_lines = []
                            if merged_volume and merged_volume != current_volume:
                                current_volume = merged_volume
                                output_lines.append(f"\n{current_volume}:")

                            forced_title = f"{chapter_info}: {merged_title}" if merged_title else f"{chapter_info}:"
                            output_lines.append(f"\n{forced_title}")

                            if final_content:
                                parser_cls_for_clean = self.get_parser_by_type(parser_type)  # Dùng parser từ config
                                if parser_cls_for_clean:
                                    # Tạo instance của parser để gọi method
                                    parser_instance_for_clean = parser_cls_for_clean()
                                    clean_method = getattr(parser_instance_for_clean, 'clean_content', None)
                                    if clean_method and callable(clean_method):
                                        clean_content = clean_method(final_content)
                                    else:
                                        clean_content = final_content
                                else:
                                    clean_content = final_content
                                output_lines.append(clean_content)
                                output_lines.append("")

                            f.write('\n'.join(output_lines))
                            f.flush()

                            print(f"⏳ Đợi {delay} giây...")
                            time.sleep(delay)

                        completion_msg = f"🎉 Hoàn thành {series['name']} theo mục lục: {end_index} chapters"
                        print(completion_msg)
                        self.logger.info(completion_msg)

                except Exception as e:
                    error_msg = f"❌ Lỗi khi đang crawl (catalog) và ghi file '{output_file}': {e}"
                    print(error_msg)
                    self.logger.error(error_msg)

        except KeyboardInterrupt:
            interrupt_msg = "\n⚠️  Người dùng dừng crawler"
            print(interrupt_msg)
            self.logger.warning(interrupt_msg)
        except Exception as e:
            critical_msg = f"❌ Lỗi nghiêm trọng: {e}"
            print(critical_msg)
            self.logger.critical(critical_msg)
        finally:
            self.logger.info("🔒 Đóng browser")
            self.close_browser()

    def crawl_series_to_yaml(self, series):
        """Crawl series và xuất trực tiếp ra YAML format với sorting"""
        try:
            print(f"\n🚀 Bắt đầu crawl series: {series['name']}")
            self.logger.info(f"🚀 Bắt đầu crawl series: {series['name']}")
            
            # Setup parser
            parser_type = series.get('parser', 'tw')
            parser_cls = self.get_parser_by_type(parser_type)
            if not parser_cls:
                error_msg = f"❌ Parser '{parser_type}' không được hỗ trợ"
                print(error_msg)
                self.logger.error(error_msg)
                return False
            
            self.current_parser = parser_cls
            
            # Setup output file
            output_dir = self.settings.get('output_dir', 'output')
            os.makedirs(output_dir, exist_ok=True)
            
            # Tạo tên file YAML
            safe_name = re.sub(r'[^\w\-_\.]', '_', series['name'])
            output_file = os.path.join(output_dir, f"{safe_name}.yaml")
            
            # JSON-only approach: tất cả parsers đều dùng JSON mapping
            json_mapping = series.get('json_mapping')
            
            if not json_mapping:
                print("❌ Thiếu json_mapping trong series config")
                self.logger.error("❌ Thiếu json_mapping trong series config")
                return False
            
            print(f"📋 Sử dụng JSON mapping cho parser {parser_type}: {json_mapping}")
            self.logger.info(f"📋 Sử dụng JSON mapping cho parser {parser_type}: {json_mapping}")
            
            # Tạo instance của parser để gọi method
            parser_instance = parser_cls()
            
            # JSON-only: chỉ dùng get_catalog_links_from_config
            enhanced_method = getattr(parser_instance, 'get_catalog_links_from_config', None)
            if enhanced_method and callable(enhanced_method):
                links = enhanced_method(self.page, "", series)  # catalog_url không cần thiết
            else:
                print("❌ Parser không có method get_catalog_links_from_config")
                self.logger.error("❌ Parser không có method get_catalog_links_from_config")
                return False
            
            if not links:
                error_msg = f"❌ Không tìm thấy link chương trong JSON mapping"
                print(error_msg)
                self.logger.error(error_msg)
                return False
            
            print(f"✅ Tìm thấy {len(links)} chapters trong JSON mapping")
            self.logger.info(f"✅ Tìm thấy {len(links)} chapters trong JSON mapping")
            
            # Crawl settings
            delay = series.get('delay', self.settings.get('delay', 2))
            max_chapters = series.get('max_chapters')
            start_chapter = series.get('start_chapter', 1)
            
            # Tính toán range
            start_index = start_chapter - 1  # Chuyển từ chapter number sang array index
            
            if max_chapters is None:
                end_index = len(links)
            else:
                # max_chapters là tổng số chapters muốn crawl (tính từ đầu)
                end_index = min(len(links), max_chapters)
            
            # Warning cho YAML mode nếu resume
            if start_chapter > 1 and os.path.exists(output_file):
                print(f"⚠️  YAML mode: File {output_file} đã tồn tại và sẽ bị GHI ĐÈ")
                print(f"⚠️  YAML không hỗ trợ append. Nếu muốn giữ data cũ, hãy backup file trước!")
                self.logger.warning(f"YAML mode: File {output_file} sẽ bị ghi đè (không hỗ trợ append)")
            
            print(f"📊 Sẽ crawl từ index {start_index} đến {end_index-1} (chapters {start_chapter} đến {end_index})")
            self.logger.info(f"📊 Sẽ crawl từ index {start_index} đến {end_index-1} (chapters {start_chapter} đến {end_index})")
            
            # Collect all chapters data
            chapters_data = []
            
            for idx in range(start_index, end_index):
                link_data = links[idx]
                
                # Xử lý cả dict (từ JSON) và string (từ parser thường)
                if isinstance(link_data, dict):
                    urls = link_data.get('urls', [link_data.get('url')])
                    chapter_num = link_data.get('chapter_num', idx + 1)
                    chapter_title = link_data.get('title', '')
                else:
                    urls = [link_data]
                    chapter_num = idx + 1
                    chapter_title = ''
                
                actual_chapter_num = chapter_num if chapter_num is not None else (idx + 1)
                chapter_info = f"Chapter {actual_chapter_num}"
                print(f"📖 Crawl {chapter_info} ({len(urls)} URLs): {chapter_title}")
                
                # Crawl tất cả URLs và merge content
                merged_content = []
                merged_title = ""
                merged_volume = ""
                
                for url_idx, url in enumerate(urls):
                    print(f"  📄 Crawl URL {url_idx + 1}/{len(urls)}: {url}")
                    
                    result = self.crawl_with_retry(url)
                    if not result:
                        print(f"⚠️  Bỏ qua URL {url_idx + 1} của {chapter_info}")
                        continue
                    
                    title = result.get('title', '').strip()
                    volume = result.get('volume', '').strip()
                    content = result.get('content', '').strip()
                    
                    # Lấy title và volume từ URL đầu tiên
                    if url_idx == 0:
                        merged_title = title
                        merged_volume = volume
                    
                    # Merge content
                    if content:
                        if url_idx == 0:
                            merged_content.append(content)
                        else:
                            if title:
                                merged_content.append(f"{title}\n\n{content}")
                            else:
                                merged_content.append(content)
                    
                    # Delay giữa các URLs
                    if url_idx < len(urls) - 1:
                        time.sleep(1)
                
                # Xử lý merged content
                final_content = '\n\n'.join(merged_content) if merged_content else ''
                
                if not final_content:
                    print(f"⚠️  Bỏ qua {chapter_info} do không có content")
                    continue
                
                # Clean content
                parser_cls_for_clean = self.get_parser_by_type(parser_type)
                if parser_cls_for_clean:
                    parser_instance_for_clean = parser_cls_for_clean()
                    clean_method = getattr(parser_instance_for_clean, 'clean_content', None)
                    if clean_method and callable(clean_method):
                        clean_content = clean_method(final_content)
                    else:
                        clean_content = final_content
                else:
                    clean_content = final_content
                
                # Tạo segment data
                segment_id = f"Chapter_{actual_chapter_num}_Segment_1"
                chapter_data = {
                    "id": segment_id,
                    "title": merged_title or f"Chapter {actual_chapter_num}",
                    "content": clean_content
                }
                
                chapters_data.append({
                    'data': chapter_data,
                    'chapter_num': actual_chapter_num,
                    'volume': merged_volume
                })
                
                print(f"⏳ Đợi {delay} giây...")
                time.sleep(delay)
            
            # SORTING: Sắp xếp chapters theo chapter_num
            chapters_data.sort(key=lambda x: x['chapter_num'])
            
            # Tạo YAML segments
            yaml_segments = []
            for chapter_info in chapters_data:
                yaml_segments.append(chapter_info['data'])
            
            # Ghi YAML file
            print(f"💾 Ghi YAML file: {output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_segments, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
            completion_msg = f"🎉 Hoàn thành {series['name']}: {len(yaml_segments)} chapters -> {output_file}"
            print(completion_msg)
            self.logger.info(completion_msg)
            
            return True
            
        except Exception as e:
            error_msg = f"❌ Lỗi crawl series '{series['name']}': {e}"
            print(error_msg)
            self.logger.error(error_msg)
            return False

    def run_all_series_yaml(self):
        """Chạy tất cả series với YAML output format"""
        try:
            self.start_browser()
            
            series_list = self.config.get('series', [])
            if not series_list:
                print("❌ Không tìm thấy series nào trong config")
                return
            
            print(f"📚 Tìm thấy {len(series_list)} series")
            
            for series in series_list:
                if not series.get('enabled', True):
                    print(f"⏭️  Bỏ qua series '{series['name']}' (disabled)")
                    continue
                
                success = self.crawl_series_to_yaml(series)
                if not success:
                    print(f"❌ Thất bại crawl series '{series['name']}'")
                    continue
                
                print(f"✅ Hoàn thành series '{series['name']}'")
                
                # Delay giữa các series
                series_delay = self.settings.get('series_delay', 5)
                if series_delay > 0:
                    print(f"⏳ Đợi {series_delay} giây trước khi crawl series tiếp theo...")
                    time.sleep(series_delay)
            
            print("🎉 Hoàn thành tất cả series!")
            
        except KeyboardInterrupt:
            print("\n⚠️  Người dùng dừng crawler")
        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng: {e}")
        finally:
            self.logger.info("🔒 Đóng browser")
            self.close_browser()


def main():
    """Main function"""
    import sys
    import io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("🚀 Unified Novel Crawler")
    print("=" * 60)
    
    # Tìm file config trong nhiều vị trí
    config_files = [
        "config.json",
        "crawler_config.json", 
        "series_config.json"
    ]
    
    # Các thư mục để tìm config
    search_dirs = [
        os.getcwd(),  # Thư mục hiện tại
        os.path.dirname(os.path.abspath(__file__)),  # Thư mục chứa script
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),  # Parent directory
    ]
    
    found_config = None
    found_dir = None
    
    print(f"🔍 Tìm config trong các thư mục:")
    for search_dir in search_dirs:
        print(f"   📁 {search_dir}")
        for config_file in config_files:
            config_path = os.path.join(search_dir, config_file)
            if os.path.exists(config_path):
                found_config = os.path.abspath(config_path)  # Sử dụng absolute path
                found_dir = search_dir
                print(f"✅ Tìm thấy file config: {config_path}")
                break
        if found_config:
            break
    
    if not found_config:
        print(f"\n❌ Không tìm thấy config file trong các thư mục đã tìm")
        print(f"📝 Hỗ trợ các file: {', '.join(config_files)}")
        
        # Nếu không tìm thấy, hỏi người dùng
        config_file = input("Nhập path file config (hoặc Enter để thoát): ").strip()
        if not config_file:
            print("❌ Cần file config để chạy!")
            return
        
        if not os.path.exists(config_file):
            print(f"❌ Không tìm thấy config file: {config_file}")
            return
        
        found_config = os.path.abspath(config_file)
    
    print(f"📋 Sử dụng config: {found_config}")
    print(f"📂 Working directory: {os.getcwd()}")
    
    # Thêm thư mục script vào Python path để import modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    crawler = UnifiedCrawler(found_config)
    
    # Hỏi người dùng về output format
    print("\n📋 Chọn output format:")
    print("1. TXT (format cũ)")
    print("2. YAML (format mới với sorting)")
    
    while True:
        choice = input("Nhập lựa chọn (1 hoặc 2): ").strip()
        if choice == '1':
            print("📝 Sử dụng TXT output format")
            crawler.run_all_series()
            break
        elif choice == '2':
            print("📝 Sử dụng YAML output format với sorting")
            crawler.run_all_series_yaml()
            break
        else:
            print("❌ Lựa chọn không hợp lệ! Vui lòng nhập 1 hoặc 2.")

if __name__ == "__main__":
    main()