#!/usr/bin/env python3
"""
Add Segments to YAML Utility
============================

Script để chuyển đổi YAML file từ cấu trúc Chapter thành Chapter_Segment
Chuyển từ:
  - id: Chapter_1
    title: "..."
    content: |-
      line1
      line2

Thành:
  - id: Chapter_1_Segment_1
    title: "..."
    content: |-
      line1

      line2
"""

import yaml
import os
import sys
from pathlib import Path


def add_segments_to_yaml(input_file, output_file=None):
    """
    Chuyển đổi YAML file từ Chapter thành Chapter_Segment với line breaks

    Args:
        input_file: Path to input YAML file
        output_file: Path to output YAML file (optional, defaults to same name)
    """
    try:
        # Read input YAML
        with open(input_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Handle array format: [{"id": "Chapter_1", "title": "...", "content": "..."}, ...]
        if isinstance(data, list):
            transformed_data = []
            chapter_count = 0

            for item in data:
                if isinstance(item, dict) and 'id' in item and item['id'].startswith('Chapter_'):
                    chapter_count += 1
                    # Transform structure
                    new_item = {}

                    # Update ID to include Segment_1
                    old_id = item['id']
                    # Extract chapter number from Chapter_X
                    chapter_num = old_id.replace('Chapter_', '')
                    new_item['id'] = f"{old_id}_Segment_{chapter_num}"

                    # Keep title
                    if 'title' in item:
                        new_item['title'] = item['title']

                    # Process content - add line breaks between lines
                    if 'content' in item and item['content']:
                        content = item['content']
                        if isinstance(content, str):
                            # Split content into lines and add empty lines between them
                            lines = content.strip().split('\n')
                            # Add empty line between each content line
                            processed_lines = []
                            for i, line in enumerate(lines):
                                processed_lines.append(line)
                                # Add empty line after each line except the last one
                                if i < len(lines) - 1:
                                    processed_lines.append('')
                            new_item['content'] = '\n'.join(processed_lines)
                        else:
                            new_item['content'] = content

                    transformed_data.append(new_item)
                    print(f"✅ Processed {old_id} -> {new_item['id']}")
                else:
                    # Giữ nguyên items khác
                    transformed_data.append(item)
                    print(f"ℹ️  Kept item unchanged")
        else:
            print(f"❌ YAML file format không được hỗ trợ: {type(data)}")
            return False

        # Determine output file - use same name as input
        if output_file is None:
            output_file = input_file

        # Write output YAML manually to ensure proper formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in transformed_data:
                f.write(f"- id: {item['id']}\n")
                if 'title' in item:
                    f.write(f"  title: {item['title']}\n")
                if 'content' in item and item['content']:
                    f.write("  content: |-\n")
                    # Write each line of content with proper indentation
                    content_lines = item['content'].split('\n')
                    for line in content_lines:
                        if line.strip():  # Non-empty line
                            f.write(f"    {line}\n")
                        else:  # Empty line
                            f.write("    \n")
                f.write("\n")  # Add blank line between items

        print(f"🎉 Hoàn thành! Processed {chapter_count} chapters")
        print(f"📁 Input:  {input_file}")
        print(f"📁 Output: {output_file}")

        return True

    except Exception as e:
        print(f"❌ Lỗi xử lý YAML: {e}")
        return False


def main():
    """Main function với interactive input"""
    print("🚀 Add Segments to YAML Utility")
    print("=" * 50)

    # Hỏi input file
    while True:
        input_file = input("📂 Nhập path file YAML đầu vào: ").strip()
        if not input_file:
            print("❌ Vui lòng nhập path file!")
            continue

        # Remove quotes nếu có
        input_file = input_file.strip('"\'')

        if not os.path.exists(input_file):
            print(f"❌ File không tồn tại: {input_file}")
            continue

        break

    # Hỏi output directory
    while True:
        output_dir = input("📁 Nhập thư mục đầu ra: ").strip()
        if not output_dir:
            print("❌ Vui lòng nhập thư mục!")
            continue

        # Remove quotes nếu có
        output_dir = output_dir.strip('"\'')

        # Tạo thư mục nếu chưa có
        try:
            os.makedirs(output_dir, exist_ok=True)
            break
        except Exception as e:
            print(f"❌ Không thể tạo thư mục {output_dir}: {e}")
            continue

    # Tạo output file path (copy tên file đầu vào)
    input_path = Path(input_file)
    output_file = os.path.join(output_dir, input_path.name)

    print(f"\n📋 Thông tin:")
    print(f"   📂 Input:  {input_file}")
    print(f"   📁 Output: {output_file}")

    # Confirm
    confirm = input("\n❓ Tiếp tục? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '']:
        print("❌ Hủy bỏ!")
        sys.exit(0)

    success = add_segments_to_yaml(input_file, output_file)

    if success:
        print("\n✅ Thành công!")
    else:
        print("\n❌ Thất bại!")
        sys.exit(1)


if __name__ == "__main__":
    main()
