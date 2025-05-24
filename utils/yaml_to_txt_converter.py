import yaml
import re
import os

# Chuyển yaml thành txt dựa trên ID

def extract_chapter_info(segment_id):
    """Trích xuất thông tin quyển, chương và segment từ ID segment"""
    # Nhận diện dạng Volume_X_Chapter_Y_Segment_Z
    volume_chapter_segment_match = re.search(r'Volume_(\d+)_Chapter_(\d+)_Segment_(\d+)', segment_id, re.IGNORECASE)
    if volume_chapter_segment_match:
        volume_num = int(volume_chapter_segment_match.group(1))
        chapter_num = int(volume_chapter_segment_match.group(2))
        segment_num = int(volume_chapter_segment_match.group(3))
        return volume_num, chapter_num, segment_num
    
    # Nhận diện dạng Volume_X_Chapter_Y
    volume_chapter_match = re.search(r'Volume_(\d+)_Chapter_(\d+)', segment_id, re.IGNORECASE)
    if volume_chapter_match:
        volume_num = int(volume_chapter_match.group(1))
        chapter_num = int(volume_chapter_match.group(2))
        return volume_num, chapter_num, None
        
    # Nhận diện dạng Chapter_X_Segment_Y
    chapter_segment_match = re.search(r'Chapter_(\d+)_Segment_(\d+)', segment_id, re.IGNORECASE)
    if chapter_segment_match:
        chapter_num = int(chapter_segment_match.group(1))
        segment_num = int(chapter_segment_match.group(2))
        return None, chapter_num, segment_num
        
    # Nhận diện dạng Chapter_X
    chapter_match = re.search(r'Chapter_(\d+)', segment_id, re.IGNORECASE)
    if chapter_match:
        chapter_num = int(chapter_match.group(1))
        return None, chapter_num, None
        
    return None, None, None

def process_yaml_to_txt(yaml_file_path, output_dir="output"):
    # Đảm bảo thư mục output tồn tại
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Đọc file YAML
    with open(yaml_file_path, 'r', encoding='utf-8') as file:
        # Để hỗ trợ YAML không chuẩn, sử dụng safe_load
        raw_content = file.read()
        # Thêm --- vào đầu để yaml có thể parse đúng định dạng list
        yaml_content = yaml.safe_load("---\n" + raw_content)
    
    # Sắp xếp các segment theo quyển, chương và số thứ tự
    volumes = {}
    
    for segment in yaml_content:
        volume_num, chapter_num, segment_num = extract_chapter_info(segment['id'])
        
        if chapter_num is not None:
            # Tạo cấu trúc lưu trữ theo quyển và chương
            # Sử dụng None làm key cho trường hợp không có quyển
            volume_key = volume_num if volume_num is not None else None
            
            if volume_key not in volumes:
                volumes[volume_key] = {}
                
            if chapter_num not in volumes[volume_key]:
                volumes[volume_key][chapter_num] = {
                    'title': segment['title'],
                    'segments': []
                }
                
            volumes[volume_key][chapter_num]['segments'].append({
                'id': segment['id'],
                'content': segment['content'],
                'segment_num': segment_num if segment_num is not None else 0
            })
    
    # Sắp xếp các segment trong mỗi chương theo số segment
    for volume_key in volumes:
        for chapter_num in volumes[volume_key]:
            volumes[volume_key][chapter_num]['segments'].sort(key=lambda x: x['segment_num'])
    
    # Ghi kết quả vào các file TXT
    for volume_key in sorted([k for k in volumes.keys() if k is not None], key=lambda x: x):
        for chapter_num, chapter_data in sorted(volumes[volume_key].items()):
            # Tạo tên file đầu ra dựa trên thông tin quyển và chương
            output_file = os.path.join(output_dir, f"Quyen_{volume_key}_Chuong_{chapter_num}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as out_file:
                # Ghi tiêu đề chương
                out_file.write(f"Quyển {volume_key} - Chương {chapter_num}: {chapter_data['title']}\n\n")
                
                # Ghi nội dung gộp lại của tất cả segment trong chương này
                for segment in chapter_data['segments']:
                    out_file.write(segment['content'] + "\n\n")
            
            print(f"Đã tạo file: {output_file}")

    # Xử lý các chương không thuộc quyển nào (nếu có)
    if None in volumes:
        for chapter_num, chapter_data in sorted(volumes[None].items()):
            output_file = os.path.join(output_dir, f"Chuong_{chapter_num}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as out_file:
                # Ghi tiêu đề chương
                out_file.write(f"Chương {chapter_num}: {chapter_data['title']}\n\n")
                
                # Ghi nội dung gộp lại của tất cả segment trong chương này
                for segment in chapter_data['segments']:
                    out_file.write(segment['content'] + "\n\n")
            
            print(f"Đã tạo file: {output_file}")

if __name__ == "__main__":
    # Yêu cầu người dùng nhập đường dẫn file YAML
    yaml_file = input("Nhập đường dẫn đến file YAML (ví dụ: vol3_edit.yaml): ")
    
    # Yêu cầu người dùng nhập thư mục đầu ra (nếu để trống sẽ dùng giá trị mặc định "output")
    output_dir = input("Nhập thư mục đầu ra (mặc định là 'output', nhấn Enter để dùng giá trị mặc định): ")
    if not output_dir.strip():
        output_dir = "output"
    
    # Kiểm tra file YAML có tồn tại không
    if not os.path.exists(yaml_file):
        print(f"Lỗi: File '{yaml_file}' không tồn tại!")
    else:
        process_yaml_to_txt(yaml_file, output_dir) 