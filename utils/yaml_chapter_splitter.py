#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YAML Chapter Splitter
Tách file YAML theo trường ID Chapter_X_Segment_Y và gộp các segment theo chapter
"""

import yaml
import re
import os
from typing import Dict, List, Tuple
from pathlib import Path


class CustomDumper(yaml.Dumper):
    def represent_scalar(self, tag, value, style=None):
        if tag == 'tag:yaml.org,2002:str' and "\n" in value:
            style = '|'
        return super().represent_scalar(tag, value, style)

# Hàm riêng để xử lý chuỗi đa dòng
def represent_multiline_string(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


class YAMLChapterSplitter:
    def __init__(self, input_file: str):
        """
        Khởi tạo splitter với file input
        
        Args:
            input_file (str): Đường dẫn đến file YAML input
        """
        self.input_file = input_file
        self.data = None
        self.chapters = {}
        
    def load_yaml(self) -> bool:
        """
        Load file YAML
        
        Returns:
            bool: True nếu load thành công, False nếu thất bại
        """
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                self.data = yaml.safe_load(f)
            return True
        except Exception as e:
            print(f"Lỗi khi load file YAML: {e}")
            return False
    
    def parse_chapters(self) -> Dict[int, List[Dict]]:
        """
        Parse và nhóm các segment theo chapter
        
        Returns:
            Dict[int, List[Dict]]: Dictionary với key là số chapter, value là list các segment
        """
        if not self.data:
            print("Chưa load dữ liệu YAML")
            return {}
        
        chapters = {}
        
        # Giả sử data là list các segment
        if isinstance(self.data, list):
            segments = self.data
        else:
            print("Dữ liệu không phải list segments")
            return {}
        
        for segment in segments:
            if not isinstance(segment, dict) or 'id' not in segment:
                continue
                
            segment_id = segment['id']
            match = re.match(r'Chapter_(\d+)_Segment_\d+', segment_id)
            
            if match:
                chapter_num = int(match.group(1))
                if chapter_num not in chapters:
                    chapters[chapter_num] = []
                chapters[chapter_num].append(segment)
        
        self.chapters = chapters
        return chapters
    
    def get_chapter_range(self) -> Tuple[int, int]:
        """
        Lấy khoảng chapter có sẵn trong file
        
        Returns:
            Tuple[int, int]: (chapter_min, chapter_max)
        """
        if not self.chapters:
            return (0, 0)
        
        chapter_numbers = sorted(self.chapters.keys())
        return (chapter_numbers[0], chapter_numbers[-1])
    
    def merge_chapter_segments(self, chapter_num: int) -> Dict:
        """
        Gộp các segment của một chapter
        
        Args:
            chapter_num (int): Số chapter cần gộp
            
        Returns:
            Dict: Chapter đã gộp với title và content
        """
        if chapter_num not in self.chapters:
            return None
        
        segments = self.chapters[chapter_num]
        if not segments:
            return None
        
        # Lấy title từ segment đầu tiên
        first_segment = segments[0]
        title = first_segment.get('title', f'Chapter {chapter_num}')
        
        # Gộp content từ tất cả segments, giữ nguyên cấu trúc line gốc
        content_parts = []
        for segment in segments:
            if 'content' in segment:
                # Giữ nguyên content gốc, không tách nhỏ
                content_parts.append(segment['content'])
        
        # Nối các content với 2 dòng trắng giữa chúng
        merged_content = '\n\n'.join(content_parts)
        
        return {
            'id': f'Chapter_{chapter_num}',
            'title': title,
            'content': merged_content
        }
    
    def split_by_range(self, start_chapter: int, end_chapter: int) -> List[Dict]:
        """
        Tách chapters theo khoảng
        
        Args:
            start_chapter (int): Chapter bắt đầu
            end_chapter (int): Chapter kết thúc
            
        Returns:
            List[Dict]: List các chapter đã gộp
        """
        merged_chapters = []
        
        for chapter_num in range(start_chapter, end_chapter + 1):
            if chapter_num in self.chapters:
                merged_chapter = self.merge_chapter_segments(chapter_num)
                if merged_chapter:
                    merged_chapters.append(merged_chapter)
        
        return merged_chapters
    
    def save_yaml(self, chapters: List[Dict], output_file: str) -> bool:
        """
        Lưu chapters ra file YAML
        
        Args:
            chapters (List[Dict]): List các chapter cần lưu
            output_file (str): Tên file output
            
        Returns:
            bool: True nếu lưu thành công, False nếu thất bại
        """
        try:
            # Đăng ký custom representer cho multi-line strings
            yaml.add_representer(str, represent_multiline_string, Dumper=CustomDumper)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(
                    chapters, 
                    f, 
                    default_flow_style=False, 
                    allow_unicode=True, 
                    sort_keys=False,
                    Dumper=CustomDumper
                )
            return True
        except Exception as e:
            print(f"Lỗi khi lưu file YAML: {e}")
            return False
    
    def process_by_range_size(self, range_size: int) -> List[str]:
        """
        Xử lý chính: tự động tách file theo range size
        
        Args:
            range_size (int): Số chapter mỗi file
            
        Returns:
            List[str]: Danh sách tên file output đã tạo
        """
        # Load file
        if not self.load_yaml():
            return []
        
        # Parse chapters
        self.parse_chapters()
        
        # Lấy khoảng chapter có sẵn
        available_range = self.get_chapter_range()
        print(f"Khoảng chapter có sẵn: {available_range[0]} - {available_range[1]}")
        
        if available_range[0] == 0 and available_range[1] == 0:
            print("Không có chapter nào trong file!")
            return []
        
        total_chapters = available_range[1] - available_range[0] + 1
        num_files = (total_chapters + range_size - 1) // range_size  # Làm tròn lên
        
        print(f"Tổng số chapters: {total_chapters}")
        print(f"Sẽ tạo {num_files} file với {range_size} chapters/file")
        
        output_files = []
        input_path = Path(self.input_file)
        
        for i in range(num_files):
            start_chapter = available_range[0] + i * range_size
            end_chapter = min(available_range[0] + (i + 1) * range_size - 1, available_range[1])
            
            print(f"\nĐang xử lý file {i+1}/{num_files}: Chapter {start_chapter} - {end_chapter}")
            
            # Tách chapters cho range này
            merged_chapters = self.split_by_range(start_chapter, end_chapter)
            
            if merged_chapters:
                # Tạo tên file output
                output_filename = f"{start_chapter}_{end_chapter}.yaml"
                output_file = input_path.parent / output_filename
                
                # Lưu file
                if self.save_yaml(merged_chapters, str(output_file)):
                    print(f"  ✓ Đã lưu {len(merged_chapters)} chapters vào: {output_file}")
                    output_files.append(str(output_file))
                else:
                    print(f"  ✗ Lỗi khi lưu file: {output_file}")
            else:
                print(f"  ✗ Không có chapter nào trong khoảng {start_chapter} - {end_chapter}")
        
        return output_files

    def process(self, start_chapter: int, end_chapter: int) -> str:
        """
        Xử lý chính: load, parse, tách và lưu file (cho một khoảng cụ thể)
        
        Args:
            start_chapter (int): Chapter bắt đầu
            end_chapter (int): Chapter kết thúc
            
        Returns:
            str: Tên file output nếu thành công, None nếu thất bại
        """
        # Load file
        if not self.load_yaml():
            return None
        
        # Parse chapters
        self.parse_chapters()
        
        # Kiểm tra khoảng chapter
        available_range = self.get_chapter_range()
        print(f"Khoảng chapter có sẵn: {available_range[0]} - {available_range[1]}")
        
        if start_chapter < available_range[0] or end_chapter > available_range[1]:
            print(f"Khoảng chapter không hợp lệ. Chỉ có chapter {available_range[0]} - {available_range[1]}")
            return None
        
        # Tách chapters
        merged_chapters = self.split_by_range(start_chapter, end_chapter)
        
        if not merged_chapters:
            print("Không có chapter nào trong khoảng đã chọn")
            return None
        
        # Tạo tên file output
        input_path = Path(self.input_file)
        output_filename = f"{start_chapter}_{end_chapter}.yaml"
        output_file = input_path.parent / output_filename
        
        # Lưu file
        if self.save_yaml(merged_chapters, str(output_file)):
            print(f"Đã lưu {len(merged_chapters)} chapters vào file: {output_file}")
            return str(output_file)
        else:
            return None


def main():
    """Hàm main để chạy chương trình"""
    print("=== YAML Chapter Splitter ===")
    
    # Nhập đường dẫn file input
    input_file = input("Nhập đường dẫn file YAML input: ").strip()
    
    if not os.path.exists(input_file):
        print("File không tồn tại!")
        return
    
    # Khởi tạo splitter
    splitter = YAMLChapterSplitter(input_file)
    
    # Load và hiển thị thông tin
    if not splitter.load_yaml():
        return
    
    splitter.parse_chapters()
    chapter_range = splitter.get_chapter_range()
    
    if chapter_range[0] == 0 and chapter_range[1] == 0:
        print("Không tìm thấy chapter nào trong file!")
        return
    
    print(f"Tìm thấy {len(splitter.chapters)} chapters từ {chapter_range[0]} đến {chapter_range[1]}")
    
    # Chọn chế độ
    print("\nChọn chế độ:")
    print("1. Tự động tách theo range size (ví dụ: 50 chapters/file)")
    print("2. Tách một khoảng cụ thể")
    
    while True:
        try:
            choice = int(input("Nhập lựa chọn (1 hoặc 2): "))
            if choice in [1, 2]:
                break
            else:
                print("Vui lòng nhập 1 hoặc 2!")
        except ValueError:
            print("Vui lòng nhập số nguyên!")
    
    if choice == 1:
        # Chế độ tự động tách theo range size
        while True:
            try:
                range_size = int(input("Nhập số chapter mỗi file (ví dụ: 50): "))
                if range_size > 0:
                    break
                else:
                    print("Số chapter phải lớn hơn 0!")
            except ValueError:
                print("Vui lòng nhập số nguyên!")
        
        # Xử lý và lưu file
        output_files = splitter.process_by_range_size(range_size)
        
        if output_files:
            print(f"\n✓ Hoàn thành! Đã tạo {len(output_files)} file:")
            for file_path in output_files:
                print(f"  - {file_path}")
        else:
            print("✗ Có lỗi xảy ra trong quá trình xử lý!")
    
    else:
        # Chế độ tách một khoảng cụ thể
        while True:
            try:
                start_chapter = int(input(f"Nhập chapter bắt đầu (từ {chapter_range[0]}): "))
                end_chapter = int(input(f"Nhập chapter kết thúc (đến {chapter_range[1]}): "))
                
                if start_chapter <= end_chapter and start_chapter >= chapter_range[0] and end_chapter <= chapter_range[1]:
                    break
                else:
                    print("Khoảng chapter không hợp lệ!")
            except ValueError:
                print("Vui lòng nhập số nguyên!")
        
        # Xử lý và lưu file
        output_file = splitter.process(start_chapter, end_chapter)
        
        if output_file:
            print(f"✓ Hoàn thành! File output: {output_file}")
        else:
            print("✗ Có lỗi xảy ra trong quá trình xử lý!")


if __name__ == "__main__":
    main() 