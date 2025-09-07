#!/usr/bin/env python3
"""
YAML Processor module - Xử lý load/save YAML với custom format
"""

import os
import yaml
import re
from typing import List, Dict, Optional


class CustomDumper(yaml.Dumper):
    """Custom YAML Dumper để giữ format literal block (|) như file cũ."""
    
    def represent_scalar(self, tag, value, style=None):
        if "\n" in str(value):
            style = "|"  # Literal block style - giữ nguyên newlines như file cũ
        return super().represent_scalar(tag, value, style)


class YamlProcessor:
    """Processor để xử lý YAML files với format custom."""
    
    def __init__(self):
        self.chapter_pattern = re.compile(r'(Volume_\d+_)?Chapter_(\d+)')
        self.segment_pattern = re.compile(r'Segment_(\d+)')
    
    def load_yaml(self, file_path: str) -> List[Dict]:
        """
        Load YAML file và validate format.
        
        Returns:
            List[Dict]: Danh sách segments với format [{id, title, content}, ...]
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, list):
            raise ValueError("YAML file phải chứa một danh sách (list)")
        
        # Validate format
        for i, segment in enumerate(data):
            if not isinstance(segment, dict):
                raise ValueError(f"Segment {i} không phải là dictionary")
            
            required_fields = ['id', 'title', 'content']
            for field in required_fields:
                if field not in segment:
                    raise ValueError(f"Segment {i} thiếu field '{field}'")
        
        return data
    
    def save_yaml(self, data: List[Dict], file_path: str):
        """
        Save data vào YAML file với format đẹp.
        
        Args:
            data: Danh sách segments
            file_path: Đường dẫn file output
        """
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, 
                     Dumper=CustomDumper, default_flow_style=False)
    
    def clean_content(self, content: str) -> str:
        """
        Clean content text - sử dụng logic từ file clean_segment.py đã test:
        - Xử lý escape sequences từ JSON response 
        - Xóa thinking blocks <think>...</think>
        - Xóa khoảng trắng thừa giữa các dòng, cách dòng mỗi đoạn
        """
        if content is None:
            return ""
        
        # Xử lý escape sequences từ JSON response
        content = content.replace('\\n', '\n')  # Newlines
        content = content.replace('\\"', '"')   # Quotes  
        content = content.replace('\\\\', '\\') # Backslashes
        
        # Xử lý pattern \\n\\ -> \n (backslash-n-backslash)
        content = content.replace('\\\n\\', '\n')
        
        # Xóa các phần nằm giữa <think> và </think>
        lines = content.split("\n")
        filtered_lines = []
        in_thinking_block = False
        
        for line in lines:
            if line.strip().startswith("<think>"):
                in_thinking_block = True
                continue
            elif line.strip().startswith("</think>"):
                in_thinking_block = False
                continue
            
            if not in_thinking_block:
                filtered_lines.append(line)
        
        # Tiếp tục xử lý với danh sách dòng đã được lọc (logic từ clean_segment.py)
        clean_lines = []
        
        for line in filtered_lines:
            # Loại bỏ khoảng trắng dư thừa nhưng giữ nguyên xuống dòng
            clean_line = " ".join(line.split())  # Xóa khoảng trắng thừa trong dòng
            if clean_line:  # Chỉ thêm dòng nếu không bị rỗng
                clean_lines.append(clean_line)
                clean_lines.append("")  # Thêm dòng trống sau mỗi dòng thực tế

        return "\n".join(clean_lines).strip()  # Giữ đúng xuống dòng thực tế, loại bỏ dòng trống cuối
    
    def parse_segment_info(self, segment_id: str) -> int:
        """
        Parse segment number từ segment ID.
        
        Returns:
            int: Segment number (từ Segment_X)
        """
        segment_match = self.segment_pattern.search(segment_id)
        if segment_match:
            return int(segment_match.group(1))
        return 0
    
    def filter_by_segment_range(self, segments: List[Dict], segment_range: Dict) -> List[Dict]:
        """
        Filter segments theo segment range.
        
        Args:
            segments: Danh sách segments
            segment_range: {"enabled": bool, "start_segment": int, "end_segment": int}
        
        Returns:
            List[Dict]: Segments đã được filter
        """
        if not segment_range.get('enabled', False):
            return segments
        
        start_seg = segment_range.get('start_segment', 1)
        end_seg = segment_range.get('end_segment', 999)
        
        filtered = []
        for segment in segments:
            segment_num = self.parse_segment_info(segment.get('id', ''))
            
            if start_seg <= segment_num <= end_seg:
                filtered.append(segment)
        
        return filtered
    
    def filter_segments(self, segments: List[Dict], filtering_config: Dict) -> List[Dict]:
        """
        Filter segments theo config mới với mode selection.
        
        Args:
            segments: Danh sách segments
            filtering_config: {
                "mode": "chapter" hoặc "segment",
                "chapter_range": {...},
                "segment_range": {...}
            }
        
        Returns:
            List[Dict]: Segments đã được filter
        """
        mode = filtering_config.get('mode', 'chapter')
        
        if mode == 'segment':
            return self.filter_by_segment_range(
                segments, 
                filtering_config.get('segment_range', {})
            )
        elif mode == 'chapter':
            return self.filter_by_chapter_range(
                segments, 
                filtering_config.get('chapter_range', {})
            )
        else:
            # Fallback: không filter
            return segments
    
    def parse_chapter_info(self, segment_id: str) -> tuple:
        """
        Parse thông tin volume/chapter từ segment ID.
        
        Returns:
            (volume, chapter): Tuple integers
        """
        chapter_match = self.chapter_pattern.search(segment_id)
        if chapter_match:
            volume = int(chapter_match.group(1).replace("Volume_", "").replace("_", "")) if chapter_match.group(1) else 1
            chapter = int(chapter_match.group(2))
            return (volume, chapter)
        return (1, 0)
    
    def get_unique_chapters(self, segments: List[Dict]) -> Dict[str, str]:
        """
        Lấy danh sách các chapter unique và title tương ứng.
        
        Returns:
            Dict[chapter_id, title]: Mapping chapter -> title để dịch title
        """
        chapters = {}
        
        for segment in segments:
            segment_id = segment.get('id', '')
            title = segment.get('title', '')
            
            # Extract chapter ID
            chapter_match = self.chapter_pattern.search(segment_id)
            if chapter_match:
                chapter_id = chapter_match.group(0)  # "Volume_X_Chapter_Y" hoặc "Chapter_Y"
                
                if chapter_id not in chapters and title.strip():
                    chapters[chapter_id] = title
        
        return chapters
    
    def filter_by_chapter_range(self, segments: List[Dict], chapter_range: Dict) -> List[Dict]:
        """
        Filter segments theo chapter range.
        
        Args:
            segments: Danh sách segments
            chapter_range: {"enabled": bool, "start_volume": int, "end_volume": int, 
                           "start_chapter": int, "end_chapter": int}
        
        Returns:
            List[Dict]: Segments đã được filter
        """
        if not chapter_range.get('enabled', False):
            return segments
        
        start_vol = chapter_range.get('start_volume', 1)
        end_vol = chapter_range.get('end_volume', 999)
        start_chap = chapter_range.get('start_chapter', 1)
        end_chap = chapter_range.get('end_chapter', 999)
        
        filtered = []
        for segment in segments:
            volume, chapter = self.parse_chapter_info(segment.get('id', ''))
            
            if (start_vol <= volume <= end_vol and 
                start_chap <= chapter <= end_chap):
                filtered.append(segment)
        
        return filtered
    
    def get_base_name(self, file_path: str) -> str:
        """Lấy base name từ file path để dùng cho naming convention."""
        return os.path.splitext(os.path.basename(file_path))[0]
    
    def create_output_filename(self, input_file: str, output_dir: str, 
                              sdk_type: str, mode: str = "translate") -> str:
        """
        Tạo tên file output theo naming convention: ddmmyy_giờ_SDK_tên.yaml
        
        Args:
            input_file: File đầu vào
            output_dir: Thư mục output
            sdk_type: "gmn" hoặc "oai"
            mode: "translate", "context"
        
        Returns:
            str: Đường dẫn file output đầy đủ
        """
        from datetime import datetime
        
        base_name = self.get_base_name(input_file)
        now = datetime.now()
        date_part = now.strftime("%d%m%y")
        time_part = now.strftime("%H%M")
        
        # Tránh duplicate suffix nếu base_name đã chứa mode
        if mode != "translate" and not base_name.endswith(f"_{mode}"):
            suffix = f"_{mode}"
        else:
            suffix = ""

        filename = f"{date_part}_{time_part}_{sdk_type}_{base_name}{suffix}.yaml"
        
        return os.path.join(output_dir, filename)
