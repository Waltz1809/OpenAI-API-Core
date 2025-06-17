#!/usr/bin/env python3
"""
Workflow Dịch Thuật Tiêu Đề (Title)
Script này đọc một file YAML, dịch tất cả các trường 'title'
sử dụng API OpenAI và ghi đè lại file gốc.
Script này hoạt động độc lập với master_workflow.
Tối ưu hóa bằng cách chỉ dịch mỗi tiêu đề chương một lần.
"""

import sys
import os
import yaml
import openai
import threading
import queue
import time
from datetime import datetime
import json
import re

# Thêm các đường dẫn cần thiết để import module từ các thư mục khác
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import các thành phần cần thiết
try:
    from clean_segment import CustomDumper
except ImportError:
    print("Lỗi: Không thể import CustomDumper từ clean_segment.py.")
    # Định nghĩa một Dumper thay thế nếu import lỗi
    class CustomDumper(yaml.Dumper):
        def represent_scalar(self, tag, value, style=None):
            if "\n" in value:
                style = "|"
            return super().represent_scalar(tag, value, style)

# --- Các hàm tiện ích ---

def load_yaml(file_path):
    """Tải file YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        # ruamel.yaml hoặc một thư viện hỗ trợ format tốt hơn sẽ lý tưởng
        # nhưng ở đây dùng PyYAML cho nhất quán với các script khác
        return yaml.safe_load(f)

def save_yaml_in_place(data, file_path):
    """Lưu dữ liệu vào file YAML, ghi đè file gốc."""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)

def create_default_config(config_path):
    """Tạo file cấu hình mặc định nếu chưa có."""
    default_config = {
        "source_yaml_file": "ĐƯỜNG_DẪN_TỚI_FILE_YAML_CỦA_BẠN.yaml",
        "api_settings": {
            "api_key": "YOUR_OPENAI_API_KEY_HERE",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "temperature": 0.5,
            "concurrent_requests": 5,
            "delay": 1
        },
        "paths": {
            "log_dir": "logs"
        }
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)
    print(f"✨ Đã tạo file cấu hình mẫu tại: {config_path}")
    print("   Vui lòng điền thông tin API key và đường dẫn file YAML vào đó.")

def load_config(config_path='title_translator_config.json'):
    """Tải file cấu hình."""
    config_full_path = os.path.join(script_dir, config_path)
    if not os.path.exists(config_full_path):
        create_default_config(config_full_path)
        return None
    try:
        with open(config_full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Lỗi không xác định khi đọc file cấu hình: {e}")
        return None

def get_log_filename(source_yaml_path, log_dir):
    """Tạo tên file log."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    base = os.path.splitext(os.path.basename(source_yaml_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"{base}_title_translation_{timestamp}.log")

def write_log(log_file, segment_id, status, details=""):
    """Ghi log kết quả xử lý."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {segment_id}: {status}"
    if details:
        log_message += f" - {details}"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")
    print(log_message)

# --- Logic dịch thuật chính ---

def title_worker(q, result_dict, client, system_prompt, model, temperature, log_file, lock, delay):
    """Hàm worker cho thread xử lý dịch title."""
    while not q.empty():
        try:
            # item là {'id': chapter_id, 'title': original_title}
            item = q.get(block=False)
            chapter_id = item['id']
            original_title = item['title']

            # Bỏ qua nếu không có title hoặc title trống
            if not original_title or not original_title.strip():
                with lock:
                    # Đánh dấu là không thay đổi
                    result_dict[chapter_id] = original_title
                q.task_done()
                continue
            
            try:
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        # Yêu cầu dịch rõ ràng cho tiêu đề
                        {"role": "user", "content": f"Dịch tiêu đề sau từ tiếng Trung sang tiếng Việt, giữ cho ngắn gọn và phù hợp:\n\n{original_title}"}
                    ],
                    model=model,
                    temperature=temperature,
                    max_tokens=5000 # Tiêu đề thường ngắn
                )
                
                # Kiểm tra xem API có trả về nội dung không
                api_content = None
                if response.choices and response.choices[0].message:
                    api_content = response.choices[0].message.content
                
                # Nếu không có nội dung, ghi lỗi và để khối except xử lý
                if not api_content:
                    raise ValueError("API không trả về nội dung dịch (có thể do bộ lọc nội dung).")

                translated_title = api_content.strip().replace('"', '')
                
                with lock:
                    result_dict[chapter_id] = translated_title
                    write_log(log_file, f"Chapter: {chapter_id}", "THÀNH CÔNG", f"'{original_title}' -> '{translated_title}'")
            
            except Exception as e:
                with lock:
                    # Giữ lại title gốc nếu có lỗi
                    result_dict[chapter_id] = original_title
                    write_log(log_file, f"Chapter: {chapter_id}", "THẤT BẠI", str(e))
            
            q.task_done()
            time.sleep(delay)
            
        except queue.Empty:
            break

def translate_titles_threaded(chapters_to_translate, client, system_prompt, config, log_file):
    """
    Xử lý dịch các title bằng threading.
    Nhận vào một dict các chapter cần dịch và trả về map đã dịch.
    """
    q = queue.Queue()
    # result_dict sẽ lưu chapter_id -> translated_title
    result_dict = {}
    lock = threading.Lock()
    
    # Đưa các chapter cần dịch vào queue
    for chapter_id, title in chapters_to_translate.items():
        q.put({'id': chapter_id, 'title': title})
        result_dict[chapter_id] = None # Khởi tạo
    
    api_config = config['api_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), len(chapters_to_translate))
    threads = []
    
    print(f"\nBắt đầu dịch {len(chapters_to_translate)} tiêu đề chương duy nhất với {num_threads} threads...")
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=title_worker,
            args=(
                q, result_dict, client, system_prompt, 
                api_config["model"], api_config["temperature"], 
                log_file, lock, api_config.get("delay", 1)
            )
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    return result_dict

# --- Main Workflow ---

def main():
    """Hàm chính để chạy script."""
    print("="*60)
    print("      WORKFLOW DỊCH TIÊU ĐỀ (TITLE TRANSLATOR)")
    print("="*60)
    
    # 1. Tải cấu hình
    config = load_config()
    if not config:
        sys.exit(1)
        
    api_config = config.get('api_settings')
    paths_config = config.get('paths')
    yaml_file_path = config.get('source_yaml_file')

    # 2. Kiểm tra cấu hình
    if not all([api_config, paths_config, yaml_file_path]):
        print("❌ Lỗi: Cấu hình 'api_settings', 'paths', hoặc 'source_yaml_file' bị thiếu.")
        sys.exit(1)

    if "YOUR_OPENAI_API_KEY" in api_config.get("api_key", "") or "ĐƯỜNG_DẪN" in yaml_file_path:
        print("❌ Lỗi: Vui lòng cấu hình API key và 'source_yaml_file' trong file 'title_translator_config.json'.")
        sys.exit(1)
        
    if not os.path.exists(yaml_file_path):
        print(f"❌ Lỗi: File nguồn '{yaml_file_path}' được chỉ định trong config không tồn tại.")
        sys.exit(1)

    # 3. Chuẩn bị client và prompt
    client = openai.OpenAI(api_key=api_config["api_key"], base_url=api_config["base_url"])
    system_prompt = "You are an expert translator specializing in Chinese to Vietnamese. Translate the given title accurately."
    
    # 4. Tải dữ liệu YAML
    try:
        yaml_data = load_yaml(yaml_file_path)
        if not isinstance(yaml_data, list):
            print("❌ Lỗi: Nội dung file YAML không phải là một danh sách (list).")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi khi đọc file YAML: {e}")
        sys.exit(1)

    # 5. Nhóm các segment theo chương và lấy tiêu đề duy nhất
    chapters_to_translate = {}
    chapter_id_pattern = re.compile(r'(Volume_\d+_Chapter_\d+|Chapter_\d+)')

    for segment in yaml_data:
        # Mặc định dùng ID segment nếu không khớp mẫu, để không bỏ sót
        chapter_id_match = chapter_id_pattern.search(segment.get('id', ''))
        chapter_id = chapter_id_match.group(0) if chapter_id_match else segment.get('id')

        if not chapter_id:
            continue

        original_title = segment.get('title')
        if original_title and original_title.strip() and chapter_id not in chapters_to_translate:
            chapters_to_translate[chapter_id] = original_title
            
    if not chapters_to_translate:
        print("✅ Không tìm thấy tiêu đề mới cần dịch. Đã hoàn thành.")
        sys.exit(0)
    
    print(f"🔍 Tìm thấy {len(chapters_to_translate)} tiêu đề chương duy nhất cần dịch.")

    # 6. Thiết lập log và tiến hành dịch
    log_file = get_log_filename(yaml_file_path, paths_config.get('log_dir', 'logs'))
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU DỊCH TIÊU ĐỀ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Source File: {yaml_file_path}\n")
        f.write(f"Model: {api_config['model']}\n\n")

    translated_titles_map = translate_titles_threaded(chapters_to_translate, client, system_prompt, config, log_file)
    
    # 7. Cập nhật lại dữ liệu YAML gốc với các tiêu đề đã dịch
    update_count = 0
    for segment in yaml_data:
        chapter_id_match = chapter_id_pattern.search(segment.get('id', ''))
        chapter_id = chapter_id_match.group(0) if chapter_id_match else segment.get('id')

        if chapter_id and chapter_id in translated_titles_map:
            translated_title = translated_titles_map[chapter_id]
            # Chỉ cập nhật nếu tiêu đề thực sự thay đổi
            if segment.get('title') != translated_title:
                segment['title'] = translated_title
                update_count += 1
    
    print(f"\n🔄 Đã áp dụng bản dịch cho {update_count} segment.")

    # 8. Lưu lại file
    try:
        save_yaml_in_place(yaml_data, yaml_file_path)
        print(f"\n✅ HOÀN THÀNH! Đã cập nhật các tiêu đề và ghi đè file: {yaml_file_path}")
    except Exception as e:
        print(f"\n❌ Lỗi khi ghi lại file YAML: {e}")

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- KẾT THÚC {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    print(f"📄 Log chi tiết đã được lưu tại: {log_file}")


if __name__ == "__main__":
    main() 