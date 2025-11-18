#!/usr/bin/env python3
"""
YAML Processor module - Xử lý load/save YAML với custom format
"""

import os
import yaml
import re
from typing import List, Dict, Optional
from .path_helper import get_path_helper


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
        ph = get_path_helper()
        resolved_path = ph.resolve(file_path)
        
        if not ph.exists(resolved_path):
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
        
        with open(resolved_path, 'r', encoding='utf-8') as f:
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
        ph = get_path_helper()
        # Tạo thư mục nếu chưa có
        resolved_path = ph.ensure_dir(file_path, is_file=True)
        
        with open(resolved_path, 'w', encoding='utf-8') as f:
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
    
    def create_temp_filename(self, base_name: str, temp_dir: str, sdk_type: str) -> str:
        """
        Tạo tên file temp để ghi incremental.
        
        Args:
            base_name: Tên base của file
            temp_dir: Thư mục temp
            sdk_type: "gmn" hoặc "oai"
        
        Returns:
            str: Đường dẫn file temp đầy đủ
        """
        from datetime import datetime
        
        now = datetime.now()
        date_part = now.strftime("%d%m%y")
        time_part = now.strftime("%H%M")
        
        filename = f"{date_part}_{time_part}_{sdk_type}_{base_name}_temp.yaml"
        
        # Tạo thư mục nếu chưa có
        os.makedirs(temp_dir, exist_ok=True)
        
        return os.path.join(temp_dir, filename)
    
    def append_segment_to_temp(self, segment: Dict, temp_file: str):
        """
        Ghi thêm một segment vào file temp (append mode).
        Thread-safe cho concurrent writes.
        
        Args:
            segment: Segment data
            temp_file: Đường dẫn file temp
        """
        ph = get_path_helper()
        resolved_temp = ph.resolve(temp_file)
        
        # Try import fcntl (chỉ có trên Unix/Linux)
        try:
            import fcntl
            HAS_FCNTL = True
        except ImportError:
            HAS_FCNTL = False
        
        # Load existing data hoặc tạo mới
        if os.path.exists(resolved_temp):
            try:
                with open(resolved_temp, 'r', encoding='utf-8') as f:
                    # Lock file for reading (nếu có fcntl)
                    if HAS_FCNTL:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                            data = yaml.safe_load(f) or []
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except (AttributeError, OSError):
                            data = yaml.safe_load(f) or []
                    else:
                        # Windows: không có file locking
                        data = yaml.safe_load(f) or []
            except Exception:
                data = []
        else:
            data = []
        
        # Append segment mới
        data.append(segment)
        
        # Write lại toàn bộ file
        ph.ensure_dir(resolved_temp, is_file=True)
        with open(resolved_temp, 'w', encoding='utf-8') as f:
            if HAS_FCNTL:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False, 
                             Dumper=CustomDumper, default_flow_style=False)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (AttributeError, OSError):
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False, 
                             Dumper=CustomDumper, default_flow_style=False)
            else:
                # Windows: không có file locking
                yaml.dump(data, f, allow_unicode=True, sort_keys=False, 
                         Dumper=CustomDumper, default_flow_style=False)
    
    def sort_by_original_order(self, translated_segments: List[Dict], 
                               original_segments: List[Dict]) -> List[Dict]:
        """
        Sắp xếp translated segments theo thứ tự của original segments dựa vào field 'id'.
        
        Args:
            translated_segments: Segments đã dịch (không đúng thứ tự)
            original_segments: Segments gốc (đúng thứ tự)
        
        Returns:
            List[Dict]: Translated segments đã được sắp xếp
        """
        # Tạo mapping id -> segment
        translated_map = {seg['id']: seg for seg in translated_segments}
        
        # Sắp xếp theo thứ tự original
        sorted_segments = []
        for orig_seg in original_segments:
            seg_id = orig_seg['id']
            if seg_id in translated_map:
                sorted_segments.append(translated_map[seg_id])
            else:
                # Nếu segment không được dịch, dùng original
                sorted_segments.append(orig_seg)
        
        return sorted_segments
    
    def split_segments_by_volume(self, segments: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Chia segments thành groups theo Volume.
        
        Args:
            segments: Danh sách segments
            
        Returns:
            Dict[batch_name, segments]: {
                'Vol1': [segments of volume 1],
                'Vol2': [segments of volume 2],
                ...
            }
        """
        volume_groups = {}
        
        for segment in segments:
            volume, chapter = self.parse_chapter_info(segment.get('id', ''))
            batch_name = f"Vol{volume}"
            
            if batch_name not in volume_groups:
                volume_groups[batch_name] = []
            
            volume_groups[batch_name].append(segment)
        
        # Sort keys để đảm bảo thứ tự Volume
        sorted_groups = {}
        for key in sorted(volume_groups.keys(), key=lambda x: int(x.replace('Vol', ''))):
            sorted_groups[key] = volume_groups[key]
        
        return sorted_groups
    
    def split_segments_by_chapter_range(self, segments: List[Dict], 
                                       chapters_per_batch: int) -> Dict[str, List[Dict]]:
        """
        Chia segments thành groups theo chapter range.
        
        Args:
            segments: Danh sách segments
            chapters_per_batch: Số chapters mỗi batch (ví dụ: 100)
            
        Returns:
            Dict[batch_name, segments]: {
                'Ch001-100': [segments],
                'Ch101-200': [segments],
                ...
            }
        """
        # Lấy danh sách unique chapters và segment tương ứng
        chapter_to_segments = {}
        
        for segment in segments:
            volume, chapter = self.parse_chapter_info(segment.get('id', ''))
            
            if chapter not in chapter_to_segments:
                chapter_to_segments[chapter] = []
            
            chapter_to_segments[chapter].append(segment)
        
        # Sort chapters
        sorted_chapters = sorted(chapter_to_segments.keys())
        
        if not sorted_chapters:
            return {}
        
        # Group chapters thành batches
        batch_groups = {}
        
        for chapter in sorted_chapters:
            # Tính batch number (1-indexed)
            batch_idx = (chapter - 1) // chapters_per_batch
            start_chapter = batch_idx * chapters_per_batch + 1
            end_chapter = start_chapter + chapters_per_batch - 1
            
            # Tạo batch name với zero-padding
            batch_name = f"Ch{start_chapter:03d}-{end_chapter:03d}"
            
            if batch_name not in batch_groups:
                batch_groups[batch_name] = []
            
            # Thêm tất cả segments của chapter này
            batch_groups[batch_name].extend(chapter_to_segments[chapter])
        
        return batch_groups