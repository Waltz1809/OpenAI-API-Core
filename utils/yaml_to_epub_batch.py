#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YAML to EPUB Batch Converter
Chuyển đổi hàng loạt file YAML thành EPUB với mục lục tự động
"""

import os
import sys
import glob
import re
from typing import Dict, List
from pathlib import Path

# Add dich_cli to path để sử dụng YamlProcessor
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "dich_cli"))

try:
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False

from core.yaml_processor import YamlProcessor  # type: ignore[import-not-found]


class YamlToEpubBatchConverter:
    """Batch converter để chuyển nhiều YAML files sang EPUB."""
    
    def __init__(self):
        self.processor = YamlProcessor()
        self.success_count = 0
        self.failed_count = 0
        self.failed_files = []
    
    def process_folder(self, folder_path: str, output_folder: str = None):
        """
        Xử lý tất cả YAML files trong folder.
        
        Args:
            folder_path: Folder chứa YAML files
            output_folder: Folder output (mặc định = folder_path)
        """
        if not EBOOKLIB_AVAILABLE:
            print("\nEPUB converter yeu cau thu vien 'ebooklib'")
            print("Cai dat bang lenh: pip install ebooklib")
            return
        
        # Tìm tất cả YAML files
        yaml_pattern = os.path.join(folder_path, "*.yaml")
        yaml_files = glob.glob(yaml_pattern)
        
        if not yaml_files:
            print(f"Khong tim thay file YAML nao trong: {folder_path}")
            return
        
        print(f"\nTim thay {len(yaml_files)} file YAML")
        print(f"Input folder: {folder_path}")
        
        # Xác định output folder
        if output_folder is None:
            output_folder = folder_path
        else:
            os.makedirs(output_folder, exist_ok=True)
        
        print(f"Output folder: {output_folder}")
        print("\n" + "="*60)
        
        # Process từng file
        for idx, yaml_file in enumerate(yaml_files, 1):
            print(f"\n[{idx}/{len(yaml_files)}] {os.path.basename(yaml_file)}")
            
            try:
                # Load YAML
                segments = self.processor.load_yaml(yaml_file)
                print(f"   > Loaded {len(segments)} segments")
                
                # Tự động tạo metadata từ filename
                metadata = self._auto_metadata_from_filename(yaml_file)
                
                # Tạo EPUB
                epub_file = self._create_epub(segments, metadata, yaml_file, output_folder)
                print(f"   > Created: {os.path.basename(epub_file)}")
                
                self.success_count += 1
                
            except Exception as e:
                print(f"   > Error: {e}")
                self.failed_count += 1
                self.failed_files.append(os.path.basename(yaml_file))
        
        # Summary
        self._print_summary()
    
    def _auto_metadata_from_filename(self, yaml_file: str) -> Dict:
        """Tự động tạo metadata từ filename."""
        filename = os.path.basename(yaml_file)
        
        # Extract book name từ filename
        # Ví dụ: "131025_1548_gmn_loan_mahou_shoujo_82_context.yaml"
        # => "Loan Mahou Shoujo"
        parts = filename.replace('.yaml', '').split('_')
        
        # Tìm phần tên sách (bỏ timestamp và sdk code)
        book_parts = []
        skip_next = False
        
        for i, part in enumerate(parts):
            # Skip timestamp parts (6 digits), sdk code (gmn/oai), và các suffix
            if part.isdigit() and len(part) == 6:  # timestamp
                skip_next = True
                continue
            if skip_next:  # sdk code
                skip_next = False
                continue
            if part in ['context', 'titles']:  # suffix
                continue
            if part.isdigit():  # chapter numbers
                continue
                
            book_parts.append(part.capitalize())
        
        # Fallback nếu không parse được
        if not book_parts:
            book_parts = [filename.replace('.yaml', '').replace('_', ' ').title()]
        
        book_title = ' '.join(book_parts)
        
        return {
            'title': book_title,
            'author': 'Unknown',
            'language': 'vi'
        }
    
    def _create_epub(self, segments: List[Dict], metadata: Dict, 
                    input_file: str, output_folder: str) -> str:
        """Tạo EPUB file từ segments."""
        # Tạo book
        book = epub.EpubBook()
        
        # Clean metadata before using
        clean_title = self._clean_xml_invalid_chars(metadata['title'])
        clean_author = self._clean_xml_invalid_chars(metadata['author'])
        
        # Set metadata
        book.set_identifier(f'id_{clean_title}')
        book.set_title(clean_title)
        book.set_language(metadata['language'])
        book.add_author(clean_author)
        
        # Group segments by chapter
        chapters_data = self._group_by_chapter(segments)
        
        if not chapters_data:
            raise ValueError("Không tìm thấy chapter nào có nội dung trong file")
        
        print(f"   > Found {len(chapters_data)} chapters with content")
        
        # Tạo chapters và TOC
        epub_chapters = []
        toc = []
        spine = ['nav']
        
        for chapter_info in chapters_data:
            chapter_id = self._clean_xml_invalid_chars(chapter_info['id'])
            chapter_title = self._clean_xml_invalid_chars(chapter_info['title'])
            chapter_content = chapter_info['content']
            
            # Tạo EPUB chapter
            chapter = epub.EpubHtml(
                title=chapter_title,
                file_name=f'chapter_{chapter_id}.xhtml',
                lang=metadata['language']
            )
            
            # Set content với CSS đẹp
            html_content = self._format_chapter_content(chapter_title, chapter_content)
            # Convert to bytes for lxml parser
            chapter.content = html_content.encode('utf-8')
            
            # Thêm vào book
            book.add_item(chapter)
            epub_chapters.append(chapter)
            
            # Thêm vào TOC và spine
            toc.append(chapter)
            spine.append(chapter)
        
        # Thêm CSS
        css = self._get_css()
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=css
        )
        book.add_item(nav_css)
        
        # Set TOC
        book.toc = tuple(toc)
        
        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Set spine
        book.spine = spine
        
        # Tạo output filename
        output_file = self._create_output_filename(input_file, metadata['title'], output_folder)
        
        # Write EPUB
        epub.write_epub(output_file, book, {})
        
        return output_file
    
    def _group_by_chapter(self, segments: List[Dict]) -> List[Dict]:
        """Group segments theo chapter."""
        chapters_dict = {}
        
        for segment in segments:
            segment_id = segment.get('id', '')
            title = segment.get('title', '')
            content = segment.get('content', '')
            
            # Extract chapter ID
            chapter_match = self.processor.chapter_pattern.search(segment_id)
            if chapter_match:
                chapter_id = chapter_match.group(0)
                
                if chapter_id not in chapters_dict:
                    # Clean title from invalid XML chars
                    clean_title = self._clean_xml_invalid_chars(title)
                    chapters_dict[chapter_id] = {
                        'id': chapter_id,
                        'title': clean_title,
                        'content': []
                    }
                
                # Append content (clean XML invalid chars)
                if content:
                    clean_content = self._clean_xml_invalid_chars(content)
                    chapters_dict[chapter_id]['content'].append(clean_content)
        
        # Sort chapters by numeric order, not string order
        def extract_chapter_number(chapter_id):
            """Extract chapter number for sorting."""
            # Pattern: Volume_X_Chapter_Y hoặc Chapter_X
            parts = re.findall(r'\d+', chapter_id)
            if len(parts) >= 2:  # Volume_X_Chapter_Y
                return (int(parts[0]), int(parts[1]))
            elif len(parts) == 1:  # Chapter_X
                return (0, int(parts[0]))
            return (0, 0)
        
        # Convert to list và merge content
        chapters_list = []
        for chapter_id in sorted(chapters_dict.keys(), key=extract_chapter_number):
            chapter_info = chapters_dict[chapter_id]
            merged_content = '\n\n'.join(chapter_info['content'])
            
            # Only add chapters that have actual content
            if merged_content.strip():
                chapter_info['content'] = merged_content
                chapters_list.append(chapter_info)
            else:
                print(f"   > Warning: {chapter_id} has no content, skipping...")
        
        return chapters_list
    
    def _clean_xml_invalid_chars(self, text: str) -> str:
        """Loại bỏ các ký tự không hợp lệ trong XML."""
        # XML 1.0 chỉ cho phép:
        # #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
        
        def is_valid_xml_char(char):
            codepoint = ord(char)
            return (
                codepoint == 0x9 or
                codepoint == 0xA or
                codepoint == 0xD or
                (0x20 <= codepoint <= 0xD7FF) or
                (0xE000 <= codepoint <= 0xFFFD) or
                (0x10000 <= codepoint <= 0x10FFFF)
            )
        
        return ''.join(char for char in text if is_valid_xml_char(char))
    
    def _format_chapter_content(self, title: str, content: str) -> str:
        """Format chapter content thành HTML."""
        # Clean invalid XML characters
        content = self._clean_xml_invalid_chars(content)
        title = self._clean_xml_invalid_chars(title)
        
        # Convert content thành paragraphs
        paragraphs = content.split('\n\n')
        html_paragraphs = []
        
        for p in paragraphs:
            if p.strip():
                # Xử lý line breaks trong paragraph
                lines = p.strip().split('\n')
                para_content = '<br/>'.join(lines)
                html_paragraphs.append(f'<p>{para_content}</p>')
        
        html = f'''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="../style/nav.css"/>
</head>
<body>
    <h1>{title}</h1>
    {''.join(html_paragraphs)}
</body>
</html>'''
        return html
    
    def _get_css(self) -> str:
        """Lấy CSS cho EPUB."""
        return '''
body {
    font-family: 'Georgia', 'Times New Roman', serif;
    line-height: 1.8;
    margin: 2em;
    text-align: justify;
}

h1 {
    font-size: 1.8em;
    font-weight: bold;
    margin-bottom: 1em;
    text-align: center;
    border-bottom: 2px solid #333;
    padding-bottom: 0.5em;
}

p {
    margin: 1em 0;
    text-indent: 2em;
}

p:first-of-type {
    text-indent: 0;
}
'''
    
    def _create_output_filename(self, input_file: str, book_title: str, output_folder: str) -> str:
        """Tạo tên file output cho EPUB."""
        # Clean book title cho filename
        safe_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_title = safe_title.replace(' ', '_')
        
        # Lấy base name từ input file để giữ naming convention
        input_basename = os.path.splitext(os.path.basename(input_file))[0]
        
        filename = f"{input_basename}.epub"
        
        return os.path.join(output_folder, filename)
    
    def _print_summary(self):
        """In summary sau khi xử lý."""
        print("\n" + "="*60)
        print("\nSUMMARY")
        print(f"Success: {self.success_count}")
        print(f"Failed:  {self.failed_count}")
        
        if self.failed_files:
            print("\nFailed files:")
            for f in self.failed_files:
                print(f"   - {f}")
        
        print("\nBatch conversion completed!")


def main():
    """Interactive interface."""
    print("=" * 60)
    print("  YAML to EPUB Batch Converter")
    print("=" * 60)
    
    # Check ebooklib
    if not EBOOKLIB_AVAILABLE:
        print("\nThieu thu vien 'ebooklib'")
        print("Cai dat: pip install ebooklib")
        input("\nNhan Enter de thoat...")
        return
    
    # Input folder
    while True:
        folder_path = input("\nNhap duong dan folder chua YAML files: ").strip().strip('"\'')
        
        if not folder_path:
            print("Vui long nhap duong dan folder!")
            continue
        
        if not os.path.exists(folder_path):
            print(f"Folder khong ton tai: {folder_path}")
            continue
        
        if not os.path.isdir(folder_path):
            print(f"Day khong phai folder: {folder_path}")
            continue
        
        break
    
    # Output folder (optional)
    print("\nOutput folder:")
    print("   (Enter = cung folder voi input)")
    output_folder = input("   Path: ").strip().strip('"\'')
    
    if not output_folder:
        output_folder = None
    
    # Confirm
    print("\n" + "="*60)
    print("THONG TIN:")
    print(f"   Input:  {folder_path}")
    print(f"   Output: {output_folder or folder_path}")
    
    confirm = input("\nBat dau chuyen doi? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', 'co', '']:
        print("Da huy!")
        return
    
    # Process
    converter = YamlToEpubBatchConverter()
    converter.process_folder(folder_path, output_folder)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDa huy chuong trinh.")
    except Exception as e:
        print(f"\nLoi: {e}")
        input("\nNhan Enter de thoat...")

