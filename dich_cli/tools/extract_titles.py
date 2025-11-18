#!/usr/bin/env python3
"""
Extract Titles Tool - Đưa line đầu tiên của content lên field title
Dùng sau khi dịch xong để có title đã được dịch
"""

import sys
import yaml
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.path_helper import get_path_helper


class TitleExtractor:
    """Extract title từ dòng đầu của content"""
    
    def __init__(self):
        self.ph = get_path_helper()
    
    def extract_titles(self, input_file, output_file=None, remove_from_content=False):
        """
        Extract titles từ content và update field title
        
        Args:
            input_file: File YAML input
            output_file: File YAML output (None = overwrite input)
            remove_from_content: True = xóa title khỏi content, False = giữ nguyên
        """
        # Resolve paths
        input_path = self.ph.resolve(input_file)
        if not self.ph.exists(input_path):
            raise FileNotFoundError(f"File không tồn tại: {input_file}")
        
        if output_file is None:
            output_path = input_path
        else:
            output_path = self.ph.resolve(output_file)
            self.ph.ensure_dir(output_path, is_file=True)
        
        print(f"📖 Đang load: {self.ph.relative_to_project(input_path)}")
        
        # Load YAML
        with open(input_path, 'r', encoding='utf-8') as f:
            segments = yaml.safe_load(f)
        
        if not segments:
            print("⚠️ File rỗng hoặc không có segments")
            return
        
        print(f"📊 Tổng: {len(segments)} segments")
        
        # Process segments
        updated = 0
        for segment in segments:
            if 'content' not in segment or not segment['content']:
                continue
            
            content = segment['content']
            lines = content.split('\n')
            
            # Bỏ qua các dòng rỗng ở đầu
            first_line_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    first_line_idx = i
                    break
            
            if first_line_idx >= len(lines):
                continue
            
            first_line = lines[first_line_idx].strip()
            
            # Loại bỏ dấu ' ở đầu nếu có
            if first_line.startswith("'"):
                first_line = first_line[1:].strip()
            
            # Update title
            if first_line:
                segment['title'] = first_line
                updated += 1
                
                # Remove from content nếu cần
                if remove_from_content:
                    # Xóa line đầu tiên (và dòng rỗng tiếp theo nếu có)
                    remaining_lines = lines[first_line_idx + 1:]
                    
                    # Bỏ qua dòng rỗng ngay sau title
                    while remaining_lines and not remaining_lines[0].strip():
                        remaining_lines = remaining_lines[1:]
                    
                    segment['content'] = '\n'.join(remaining_lines)
        
        print(f"✅ Đã update {updated}/{len(segments)} segments")
        
        # Save YAML
        print(f"💾 Đang lưu: {self.ph.relative_to_project(output_path)}")
        
        # Custom representer cho multi-line strings
        def represent_str(dumper, data):
            if '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)
        
        yaml.add_representer(str, represent_str)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(segments, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        
        print(f"🎉 Hoàn thành!")
        print(f"📁 Output: {self.ph.relative_to_project(output_path)}")


def main():
    """Interactive CLI"""
    print("=" * 60)
    print("  EXTRACT TITLES TOOL")
    print("=" * 60)
    
    extractor = TitleExtractor()
    
    # Input file
    while True:
        input_file = input("\nNhập path file YAML (relative to project root): ").strip().strip('"\'')
        
        if not input_file:
            print("❌ Vui lòng nhập path!")
            continue
        
        try:
            resolved = extractor.ph.resolve(input_file)
            if not extractor.ph.exists(resolved):
                print(f"❌ File không tồn tại: {input_file}")
                continue
            break
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            continue
    
    # Output file
    print("\nOutput file:")
    print("  Enter = ghi đè file gốc")
    print("  Path = lưu file mới")
    output_file = input("Path: ").strip().strip('"\'')
    
    if not output_file:
        output_file = None
        print("ℹ️ Sẽ ghi đè file gốc")
    
    # Remove from content?
    print("\nXóa title khỏi content sau khi extract?")
    print("  y = Xóa (content chỉ còn nội dung chính)")
    print("  n = Giữ nguyên (title vẫn ở đầu content)")
    remove_choice = input("Choice (y/n): ").strip().lower()
    remove_from_content = remove_choice == 'y'
    
    # Confirm
    print("\n" + "=" * 60)
    print("THÔNG TIN:")
    print(f"  Input:  {input_file}")
    print(f"  Output: {output_file or '(overwrite input)'}")
    print(f"  Remove from content: {remove_from_content}")
    print("=" * 60)
    
    confirm = input("\nBắt đầu? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '']:
        print("❌ Đã hủy!")
        return
    
    # Extract
    try:
        extractor.extract_titles(input_file, output_file, remove_from_content)
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

