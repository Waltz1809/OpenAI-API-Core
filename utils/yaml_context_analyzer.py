#!/usr/bin/env python3
"""
YAML Context Analyzer - Tiện ích phân tích ngữ cảnh từ file YAML
Đọc file YAML, gửi từng segment đến API để tạo tóm tắt ngữ cảnh,
sau đó ghi kết quả vào một file YAML mới.
Đây là một tiện ích độc lập.
"""

import os
import sys
import yaml
import json
import openai
import threading
import queue
from datetime import datetime
import time

# Thêm đường dẫn để import CustomDumper
script_dir = os.path.dirname(os.path.abspath(__file__))
enhanced_dir = os.path.abspath(os.path.join(script_dir, '../enhanced'))
sys.path.append(enhanced_dir)

try:
    from clean_segment import CustomDumper
except ImportError:
    print("Cảnh báo: Không thể import CustomDumper. Sẽ sử dụng Dumper mặc định của PyYAML.")
    CustomDumper = yaml.Dumper

# --- Các hàm và Class tiện ích ---

def load_config(config_path='yaml_context_analyzer_config.json'):
    """Tải file cấu hình."""
    full_config_path = os.path.join(script_dir, config_path)
    if not os.path.exists(full_config_path):
        print(f"Lỗi: File cấu hình '{full_config_path}' không tồn tại.")
        return None
    try:
        with open(full_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi khi đọc file cấu hình: {e}")
        return None

def load_yaml(file_path):
    """Tải file YAML một cách an toàn."""
    if not os.path.exists(file_path):
        print(f"Lỗi: File YAML nguồn '{file_path}' không tồn tại.")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Lỗi khi đọc file YAML '{file_path}': {e}")
        return None

def load_prompt(file_path):
    """Tải nội dung prompt từ file."""
    if not os.path.exists(file_path):
        print(f"Lỗi: File prompt '{file_path}' không tồn tại.")
        return None
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# --- Logic Phân Tích ---

def analysis_worker(q, result_dict, client, system_prompt, model, temperature, max_tokens, lock, total_segments):
    """Worker cho thread phân tích segment và trả về tóm tắt text."""
    while not q.empty():
        try:
            index, segment = q.get(block=False)
            segment_id = segment.get('id', 'Unknown_ID')
            original_title = segment.get('title', '')
            content = segment.get('content', '')

            with lock:
                processed_count = len(result_dict)
                print(f"[{processed_count + 1}/{total_segments}] Đang phân tích: {segment_id}...")

            if not content.strip():
                with lock:
                    print(f"Cảnh báo: Bỏ qua segment {segment_id} vì không có nội dung.")
                # Vẫn tạo segment rỗng để giữ đúng thứ tự
                result_dict[index] = {'id': segment_id, 'title': original_title, 'content': ''}
                q.task_done()
                continue

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                # Kiểm tra API có trả về nội dung không
                if response.choices and response.choices[0].message and response.choices[0].message.content is not None:
                    summary_text = response.choices[0].message.content
                    new_segment = {
                        'id': segment_id,
                        'title': original_title,
                        'content': summary_text.strip()
                    }
                    result_dict[index] = new_segment
                else:
                    # Xử lý trường hợp không có nội dung (bị filter, etc.)
                    finish_reason = response.choices[0].finish_reason if response.choices else 'unknown'
                    with lock:
                        print(f"⚠️ Cảnh báo: API không trả về nội dung cho {segment_id} (lý do: {finish_reason}). Giữ lại nội dung gốc.")
                    result_dict[index] = segment # Giữ lại segment gốc

            except Exception as e:
                with lock:
                    print(f"❌ Lỗi API cho segment {segment_id}: {e}")
                # Nếu lỗi, giữ lại content gốc để không mất dữ liệu
                result_dict[index] = segment
            
            q.task_done()

        except queue.Empty:
            break

def analyze_and_summarize_threaded(segments, client, system_prompt, config):
    """Xử lý tóm tắt các segment bằng threading."""
    q = queue.Queue()
    # Dùng dict để đảm bảo thứ tự của các segment được giữ nguyên
    result_dict = {}
    lock = threading.Lock()
    total_segments = len(segments)
    
    for i, seg in enumerate(segments):
        q.put((i, seg))

    api_config = config['api_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), total_segments)
    threads = []
    
    print(f"\nBắt đầu tóm tắt {total_segments} segment với {num_threads} threads...")
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=analysis_worker,
            args=(
                q, result_dict, client, system_prompt,
                api_config["model"], api_config["temperature"], api_config["max_tokens"], lock, total_segments
            )
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    q.join() # Chờ queue được xử lý hết
    
    # Chuyển đổi dict kết quả thành list theo đúng thứ tự
    final_results = [result_dict[i] for i in sorted(result_dict.keys())]
    return final_results

def save_output_yaml(data, output_dir, base_filename):
    """Lưu danh sách các segment đã được xử lý ra file YAML."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_file_path = os.path.join(output_dir, f"{base_filename}_context.yaml")
    
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)
        print(f"✅ Kết quả đã được lưu vào file YAML: {output_file_path}")
    except Exception as e:
        print(f"❌ Lỗi khi lưu file YAML: {e}")


# --- Main Workflow ---
def main():
    """Hàm chính để chạy script."""
    print("="*60)
    print("      YAML CONTEXT ANALYZER - TIỆN ÍCH PHÂN TÍCH NGỮ CẢNH")
    print("="*60)

    # 1. Tải config
    config_path = 'yaml_context_analyzer_config.json'
    config = load_config(config_path)
    if not config:
        sys.exit(1)
    
    api_config = config['api_settings']
    paths_config = config['paths']

    # 2. Lấy thông tin từ config
    yaml_file = paths_config.get("source_yaml_file")
    if not yaml_file or "ĐƯỜNG_DẪN" in yaml_file:
        print(f"Lỗi: Vui lòng chỉ định 'source_yaml_file' hợp lệ trong file '{config_path}'.")
        sys.exit(1)
        
    segments = load_yaml(yaml_file)
    if not segments:
        sys.exit(1)

    prompt_file = paths_config.get("system_prompt_file")
    if not prompt_file or not os.path.exists(prompt_file):
        print(f"Lỗi: Vui lòng chỉ định 'system_prompt_file' hợp lệ trong file '{config_path}'.")
        sys.exit(1)

    system_prompt = load_prompt(prompt_file)
    if not system_prompt:
        sys.exit(1)

    # 3. Kiểm tra API key
    if "YOUR_OPENAI_API_KEY" in api_config.get("api_key", ""):
        api_key = input("Vui lòng nhập OpenAI API Key của bạn: ").strip()
        if not api_key:
            print("API key là bắt buộc. Dừng chương trình.")
            sys.exit(1)
        api_config['api_key'] = api_key
    
    print(f"\nBắt đầu phân tích file: {yaml_file}")
    print(f"Sử dụng system prompt: {prompt_file}")
    
    # 4. Chuẩn bị và thực thi
    client = openai.OpenAI(api_key=api_config["api_key"], base_url=api_config["base_url"])
    
    summarized_segments = analyze_and_summarize_threaded(segments, client, system_prompt, config)

    if not summarized_segments:
        print("\nKhông có kết quả nào được xử lý. Dừng chương trình.")
        sys.exit(1)
        
    # 5. Lưu kết quả
    base_filename = os.path.splitext(os.path.basename(yaml_file))[0]
    output_dir = paths_config.get("output_dir", "output")
    
    save_output_yaml(summarized_segments, output_dir, base_filename)
    
    print("\n🎉 Phân tích hoàn tất!")

if __name__ == "__main__":
    main() 