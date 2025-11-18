#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB Bilingual Splitter
Tách nội dung song ngữ (Trung-Nhật) từ EPUB thành 2 file YAML riêng biệt
"""

import os
import re
import yaml
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup


class CustomDumper(yaml.Dumper):
    """Custom YAML Dumper để format đẹp cho multi-line strings"""
    def represent_scalar(self, tag, value, style=None):
        if tag == 'tag:yaml.org,2002:str' and "\n" in value:
            style = '|'
        return super().represent_scalar(tag, value, style)


def represent_multiline_string(dumper, data):
    """Representer cho multi-line strings"""
    if "\n" in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


class EPUBBilingualSplitter:
    """Class để tách nội dung song ngữ từ EPUB"""
    
    def __init__(self, epub_path: str):
        """
        Khởi tạo splitter
        
        Args:
            epub_path: Đường dẫn đến file EPUB
        """
        self.epub_path = epub_path
        self.temp_dir = None
        self.chinese_segments = []
        self.japanese_segments = []
        
    def extract_epub(self) -> str:
        """
        Giải nén EPUB file
        
        Returns:
            str: Đường dẫn đến thư mục đã giải nén
        """
        # Tạo thư mục temp để giải nén
        epub_name = Path(self.epub_path).stem
        temp_dir = Path(self.epub_path).parent / f"_temp_{epub_name}"
        
        # Giải nén EPUB (thực chất là file ZIP)
        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        self.temp_dir = temp_dir
        print(f"✓ Đã giải nén EPUB vào: {temp_dir}")
        return str(temp_dir)
    
    def find_xhtml_files(self) -> List[str]:
        """
        Tìm tất cả file XHTML trong EPUB (trừ TOC và p-001)
        
        Returns:
            List[str]: Danh sách đường dẫn đến các file XHTML
        """
        if not self.temp_dir:
            return []
        
        xhtml_files = []
        
        # Tìm tất cả file .xhtml
        for file in Path(self.temp_dir).rglob("*.xhtml"):
            # Bỏ qua các file đặc biệt
            file_name = file.name.lower()
            
            # Bỏ qua p-001.xhtml
            if file_name == 'p-001.xhtml':
                continue
                
            if any(skip in file_name for skip in ['toc', 'nav', 'cover', 'copyright']):
                continue
            xhtml_files.append(str(file))
        
        # Sort theo tên file để đảm bảo thứ tự
        xhtml_files.sort()
        
        print(f"✓ Tìm thấy {len(xhtml_files)} file XHTML (đã bỏ qua p-001)")
        return xhtml_files
    
    def parse_xhtml_file(self, xhtml_path: str, chapter_number: int, max_chars: int = 2000) -> Tuple[List[Dict], List[Dict]]:
        """
        Parse một file XHTML và tách nội dung Trung-Nhật
        
        Args:
            xhtml_path: Đường dẫn đến file XHTML
            chapter_number: Số thứ tự chapter
            max_chars: Số ký tự tối đa cho mỗi segment
            
        Returns:
            Tuple[List[Dict], List[Dict]]: (chinese_segments, japanese_segments)
        """
        with open(xhtml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Tìm thẻ <div class="main">
        main_div = soup.find('div', class_='main')
        
        if not main_div:
            print(f"   ⚠️  Không tìm thấy <div class='main'> trong {Path(xhtml_path).name}")
            return ([], [])
        
        # Lấy tất cả thẻ <p> trong main_div
        paragraphs = main_div.find_all('p')
        
        if len(paragraphs) < 2:
            print(f"   ⚠️  Không đủ paragraphs trong {Path(xhtml_path).name}")
            return ([], [])
        
        # 2 dòng đầu tiên là title (1 Trung, 1 Nhật)
        chinese_title = None
        japanese_title = None
        
        # Xác định title dựa vào style
        for i in range(min(2, len(paragraphs))):
            p = paragraphs[i]
            text = p.get_text(strip=True)
            style = p.get('style', '')
            
            if 'opacity' in style.lower() and '0.4' in style:
                japanese_title = text
            else:
                chinese_title = text
        
        # Fallback nếu không tìm được title
        if not chinese_title:
            chinese_title = f"Chapter {chapter_number}"
        if not japanese_title:
            japanese_title = f"Chapter {chapter_number}"
        
        # Lấy nội dung từ dòng thứ 3 trở đi
        chinese_content = []
        japanese_content = []
        
        for p in paragraphs[2:]:  # Bỏ qua 2 dòng title
            text = p.get_text(strip=True)
            if not text:
                continue
            
            # Kiểm tra style attribute
            style = p.get('style', '')
            
            # Nếu có opacity:0.4 thì là tiếng Nhật
            if 'opacity' in style.lower() and '0.4' in style:
                japanese_content.append(text)
            else:
                # Còn lại là tiếng Trung
                chinese_content.append(text)
        
        # Chia thành segments theo max_chars
        chinese_segments = self._split_into_segments(
            chinese_content, chinese_title, chapter_number, max_chars
        )
        japanese_segments = self._split_into_segments(
            japanese_content, japanese_title, chapter_number, max_chars
        )
        
        return (chinese_segments, japanese_segments)
    
    def _split_into_segments(self, content_lines: List[str], title: str, 
                            chapter_number: int, max_chars: int) -> List[Dict]:
        """
        Chia nội dung thành các segments dựa trên số ký tự
        
        Args:
            content_lines: List các dòng nội dung
            title: Tiêu đề chapter
            chapter_number: Số chapter
            max_chars: Số ký tự tối đa mỗi segment
            
        Returns:
            List[Dict]: List các segment
        """
        if not content_lines:
            return []
        
        segments = []
        current_segment = []
        current_length = 0
        segment_counter = 1
        
        for line in content_lines:
            # Đếm ký tự không có khoảng trắng
            line_length = len(re.sub(r'\s+', '', line))
            
            # Nếu thêm dòng này vượt quá max_chars và đã có nội dung, tạo segment mới
            if current_length + line_length > max_chars and current_segment:
                # Tạo segment: bắt đầu bằng title (có dấu ' ở đầu), sau đó là các dòng content
                # Mỗi dòng cách nhau bởi 2 dòng trống
                all_lines = [f"'{title}"] + current_segment
                segment_content = '\n\n'.join(all_lines)
                
                segments.append({
                    'id': f'Chapter_{chapter_number}_Segment_{segment_counter}',
                    'title': title,
                    'content': segment_content
                })
                
                segment_counter += 1
                current_segment = []
                current_length = 0
            
            current_segment.append(line)
            current_length += line_length
        
        # Thêm segment cuối cùng
        if current_segment:
            # Tạo segment: bắt đầu bằng title (có dấu ' ở đầu), sau đó là các dòng content
            all_lines = [f"'{title}"] + current_segment
            segment_content = '\n\n'.join(all_lines)
            
            segments.append({
                'id': f'Chapter_{chapter_number}_Segment_{segment_counter}',
                'title': title,
                'content': segment_content
            })
        
        return segments
    
    def detect_chapter_number(self, file_path: str) -> int:
        """
        Phát hiện số chapter từ tên file
        
        Args:
            file_path: Đường dẫn file
            
        Returns:
            int: Số chapter (hoặc None nếu không phát hiện được)
        """
        file_name = Path(file_path).stem
        
        # Thử tìm số trong tên file (ví dụ: p-014.xhtml -> 14)
        match = re.search(r'(\d+)', file_name)
        if match:
            return int(match.group(1))
        
        return None
    
    def process(self, max_chars: int = 2000) -> Tuple[List[Dict], List[Dict]]:
        """
        Xử lý toàn bộ EPUB và tách nội dung
        
        Args:
            max_chars: Số ký tự tối đa cho mỗi segment
        
        Returns:
            Tuple[List[Dict], List[Dict]]: (chinese_segments, japanese_segments)
        """
        print(f"\n📖 Đang xử lý EPUB: {Path(self.epub_path).name}")
        print(f"   Tham số: max_chars = {max_chars}")
        
        # 1. Giải nén EPUB
        self.extract_epub()
        
        # 2. Tìm các file XHTML
        xhtml_files = self.find_xhtml_files()
        
        if not xhtml_files:
            print("❌ Không tìm thấy file XHTML nào!")
            return ([], [])
        
        # 3. Parse từng file
        chinese_segments = []
        japanese_segments = []
        
        for idx, xhtml_file in enumerate(xhtml_files, 0):  # Bắt đầu từ 0
            print(f"   [{idx+1}/{len(xhtml_files)}] {Path(xhtml_file).name}")
            
            # Phát hiện số chapter từ tên file
            chapter_num = self.detect_chapter_number(xhtml_file)
            
            # Nếu không phát hiện được, dùng index (bắt đầu từ 0)
            if chapter_num is None:
                chapter_num = idx
            else:
                # Trừ 2 để bắt đầu từ Chapter_0 (vì p-002 -> Chapter_0)
                chapter_num = chapter_num - 2
            
            # Parse file
            ch_segs, jp_segs = self.parse_xhtml_file(xhtml_file, chapter_num, max_chars)
            
            chinese_segments.extend(ch_segs)
            japanese_segments.extend(jp_segs)
        
        self.chinese_segments = chinese_segments
        self.japanese_segments = japanese_segments
        
        print(f"\n✓ Tách xong:")
        print(f"   - Trung: {len(chinese_segments)} segments")
        print(f"   - Nhật: {len(japanese_segments)} segments")
        
        return (chinese_segments, japanese_segments)
    
    def save_yaml(self, segments: List[Dict], output_path: str) -> bool:
        """
        Lưu segments ra file YAML
        
        Args:
            segments: List các segment
            output_path: Đường dẫn file output
            
        Returns:
            bool: True nếu thành công
        """
        try:
            # Đăng ký custom representer
            yaml.add_representer(str, represent_multiline_string, Dumper=CustomDumper)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    segments,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                    Dumper=CustomDumper
                )
            
            print(f"   ✓ Đã lưu: {output_path}")
            return True
            
        except Exception as e:
            print(f"   ✗ Lỗi khi lưu file: {e}")
            return False
    
    def cleanup(self):
        """Dọn dẹp thư mục temp"""
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir)
            print(f"✓ Đã dọn dẹp thư mục temp")
    
    def split_and_save(self, output_dir: str = None, max_chars: int = 2000):
        """
        Xử lý và lưu cả 2 file YAML
        
        Args:
            output_dir: Thư mục output (mặc định = cùng thư mục với EPUB)
            max_chars: Số ký tự tối đa cho mỗi segment
        """
        # Process
        chinese_segments, japanese_segments = self.process(max_chars)
        
        if not chinese_segments and not japanese_segments:
            print("❌ Không có nội dung nào được tách!")
            return
        
        # Xác định output directory
        if output_dir is None:
            output_dir = Path(self.epub_path).parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Tạo tên file output
        epub_name = Path(self.epub_path).stem
        
        print(f"\n💾 Đang lưu file YAML...")
        
        # Lưu file Trung
        if chinese_segments:
            chinese_path = output_dir / f"{epub_name}_chinese.yaml"
            self.save_yaml(chinese_segments, str(chinese_path))
        
        # Lưu file Nhật
        if japanese_segments:
            japanese_path = output_dir / f"{epub_name}_japanese.yaml"
            self.save_yaml(japanese_segments, str(japanese_path))
        
        # Cleanup
        self.cleanup()
        
        print(f"\n✅ Hoàn thành!")


def main():
    """Interactive interface"""
    print("=" * 70)
    print("  EPUB BILINGUAL SPLITTER - Tách Song Ngữ Trung-Nhật")
    print("=" * 70)
    
    # Nhập file EPUB
    while True:
        epub_path = input("\nNhập đường dẫn file EPUB: ").strip().strip('"\'')
        
        if not epub_path:
            print("❌ Vui lòng nhập đường dẫn file!")
            continue
        
        if not os.path.exists(epub_path):
            print(f"❌ File không tồn tại: {epub_path}")
            continue
        
        if not epub_path.lower().endswith('.epub'):
            print("❌ File phải có định dạng .epub!")
            continue
        
        break
    
    # Nhập output directory (optional)
    print("\nThư mục lưu output:")
    print("   (Enter = cùng thư mục với EPUB)")
    output_dir = input("   Path: ").strip().strip('"\'')
    
    if not output_dir:
        output_dir = None
    
    # Nhập max_chars
    print("\nSố ký tự tối đa mỗi segment:")
    max_chars_input = input("   [mặc định = 2000]: ").strip()
    max_chars = int(max_chars_input) if max_chars_input else 2000
    
    # Confirm
    print("\n" + "=" * 70)
    print("THÔNG TIN:")
    print(f"   Input:      {epub_path}")
    print(f"   Output:     {output_dir or Path(epub_path).parent}")
    print(f"   Max chars:  {max_chars}")
    
    confirm = input("\nBắt đầu tách? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', 'có', '']:
        print("Đã hủy!")
        return
    
    # Process
    try:
        splitter = EPUBBilingualSplitter(epub_path)
        splitter.split_and_save(output_dir, max_chars)
        
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Đã hủy chương trình.")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        input("\nNhấn Enter để thoát...")

