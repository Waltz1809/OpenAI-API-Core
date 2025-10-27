"""
YAML to Chapters JSON Converter
Chuyển đổi file YAML thành JSON theo từng chương để tiện fetch web
"""

import yaml
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional


class YamlToChaptersJsonConverter:
    """Tool chuyển đổi YAML thành JSON theo chương."""
    
    def __init__(self):
        self.chapter_pattern = re.compile(r'Chapter_(\d+)')
    
    def load_yaml(self, yaml_file: str) -> List[Dict]:
        """Load YAML file."""
        print(f"📖 Đang load file: {yaml_file}")
        
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        print(f"✅ Đã load {len(data)} segments")
        return data
    
    def group_by_chapters(self, segments: List[Dict]) -> Dict[int, List[Dict]]:
        """Nhóm segments theo chương."""
        chapters = defaultdict(list)
        
        for segment in segments:
            segment_id = segment.get('id', '')
            match = self.chapter_pattern.search(segment_id)
            
            if match:
                chapter_num = int(match.group(1))
                chapters[chapter_num].append(segment)
            else:
                print(f"⚠️ Không thể parse chapter từ: {segment_id}")
        
        return dict(chapters)
    
    def create_chapter_json(self, chapter_num: int, segments: List[Dict]) -> Dict:
        """Tạo JSON structure cho một chương."""
        # Lấy title từ segment đầu tiên
        chapter_title = segments[0].get('title', f'Chương {chapter_num}') if segments else f'Chương {chapter_num}'
        
        chapter_data = {
            "chapter_number": chapter_num,
            "chapter_title": chapter_title,
            "total_segments": len(segments),
            "segments": []
        }
        
        for segment in segments:
            segment_data = {
                "id": segment.get('id', ''),
                "title": segment.get('title', ''),
                "content": segment.get('content', '')
            }
            chapter_data["segments"].append(segment_data)
        
        return chapter_data
    
    def convert_to_chapters(self, yaml_file: str, output_dir: Optional[str] = None):
        """Chuyển đổi YAML thành JSON files theo chương."""
        # Determine output directory
        if output_dir is None:
            yaml_dir = os.path.dirname(yaml_file)
            base_name = os.path.splitext(os.path.basename(yaml_file))[0]
            output_dir = os.path.join(yaml_dir, f"{base_name}_chapters")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 Output dir: {output_dir}")
        
        # Load and process
        segments = self.load_yaml(yaml_file)
        chapters = self.group_by_chapters(segments)
        
        print(f"📚 Tìm thấy {len(chapters)} chương")
        
        # Create JSON files
        created_files = []
        for chapter_num in sorted(chapters.keys()):
            chapter_segments = chapters[chapter_num]
            chapter_data = self.create_chapter_json(chapter_num, chapter_segments)
            
            # Create filename
            json_filename = f"chapter_{chapter_num:03d}.json"
            json_path = os.path.join(output_dir, json_filename)
            
            # Save JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(chapter_data, f, ensure_ascii=False, indent=2)
            
            created_files.append(json_path)
            print(f"✅ Chapter {chapter_num}: {len(chapter_segments)} segments → {json_filename}")
        
        # Create index file
        index_data = {
            "source_file": os.path.basename(yaml_file),
            "total_chapters": len(chapters),
            "total_segments": sum(len(segs) for segs in chapters.values()),
            "chapters": [
                {
                    "chapter_number": num,
                    "filename": f"chapter_{num:03d}.json", 
                    "segments_count": len(chapters[num]),
                    "title": chapters[num][0].get('title', f'Chương {num}') if chapters[num] else f'Chương {num}'
                }
                for num in sorted(chapters.keys())
            ]
        }
        
        index_path = os.path.join(output_dir, "index.json")
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n🎉 Hoàn thành!")
        print(f"📁 Thư mục: {output_dir}")
        print(f"📄 Files: {len(created_files)} chapter files + 1 index file")
        print(f"📋 Index: {index_path}")
        
        return output_dir, created_files


def main():
    """Interactive interface."""
    print("🔄 YAML to Chapters JSON Converter")
    print("=" * 40)
    
    # Input YAML file
    while True:
        yaml_file = input("📁 Nhập đường dẫn file YAML: ").strip().strip('"')
        
        if not yaml_file:
            print("❌ Vui lòng nhập đường dẫn file!")
            continue
            
        if not os.path.exists(yaml_file):
            print(f"❌ File không tồn tại: {yaml_file}")
            continue
            
        if not yaml_file.lower().endswith('.yaml'):
            print(f"❌ File phải có đuôi .yaml!")
            continue
            
        break
    
    # Optional output directory
    output_dir = input("📂 Thư mục output (Enter = tự động): ").strip().strip('"')
    if not output_dir:
        output_dir = None
    
    print("\n🚀 Bắt đầu chuyển đổi...")
    print("-" * 40)
    
    converter = YamlToChaptersJsonConverter()
    try:
        output_path, files = converter.convert_to_chapters(yaml_file, output_dir)
        
        print("\n🎉 Chuyển đổi thành công!")
        print(f"📁 Kết quả tại: {output_path}")
        
        # Ask if user wants to continue
        while True:
            choice = input("\n❓ Muốn chuyển đổi file khác? (y/n): ").strip().lower()
            if choice in ['y', 'yes', 'có']:
                print("\n" + "=" * 40)
                main()  # Recursive call
                break
            elif choice in ['n', 'no', 'không']:
                print("👋 Bye!")
                break
            else:
                print("❌ Vui lòng nhập 'y' hoặc 'n'")
                
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        input("\nNhấn Enter để thoát...")


if __name__ == "__main__":
    main()