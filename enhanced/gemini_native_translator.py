#!/usr/bin/env python3
"""
Workflow Dịch Thuật sử dụng Google Gemini Native SDK
MODULE này được gọi bởi master_workflow.py khi có tùy chọn.

CẤU HÌNH QUAN TRỌNG:
1. thinking_budget = 0: TẮT thinking (tiết kiệm token, tốc độ nhanh)
2. thinking_budget = 1024: Bật thinking với budget cố định
3. thinking_budget = -1: Dynamic thinking (model tự quyết định)
4. Safety settings: Đã TẮT TẤT CẢ (BLOCK_NONE)

VÍ DỤ CONFIG:
{
  "translate_api_settings": {
    "api_key": "your_gemini_api_key",
    "model": "gemini-2.5-flash",
    "temperature": 0.7,
    "max_tokens": 4000,
    "thinking_budget": 0,
    "concurrent_requests": 3,
    "delay": 1
  }
}
"""

import os
import sys
import yaml
import time
import queue
import threading
from datetime import datetime

# SDK của Google - sử dụng package mới
from google import genai
from google.genai import types

# Import các thành phần cần thiết từ các module khác
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)
from clean_segment import CustomDumper

# --- Các hàm tiện ích chung ---

def load_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(data, file_path):
    output_dir = os.path.dirname(file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)

def load_prompt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def write_log(log_file, segment_id, status, error=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {segment_id}: {status}"
    if error:
        log_message += f" - Lỗi: {error}"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")
    print(log_message)

def clean_content(content):
    """
    Làm sạch và format lại content từ Gemini:
    - Thêm 1 dòng trắng giữa mỗi dòng để dễ đọc (nếu chưa có)
    - Loại bỏ khoảng trắng thừa
    - Giữ nguyên format nếu đã có dòng trống sẵn
    """
    if not content:
        return content
    
    # Kiểm tra xem content đã có dòng trống giữa các dòng chưa
    lines = content.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    # Nếu số dòng gốc gấp đôi số dòng có nội dung, có thể đã có format sẵn
    if len(lines) >= len(non_empty_lines) * 1.5:
        # Đã có format tốt, chỉ loại bỏ khoảng trắng thừa
        return '\n'.join(line.strip() if line.strip() else "" for line in lines)
    
    # Chưa có format, thêm dòng trắng giữa mỗi dòng
    formatted_lines = []
    for i, line in enumerate(non_empty_lines):
        formatted_lines.append(line)
        # Thêm dòng trắng giữa các dòng (trừ dòng cuối cùng)
        if i < len(non_empty_lines) - 1:
            formatted_lines.append("")
    
    return '\n'.join(formatted_lines)

# --- Logic dịch thuật với Gemini Native SDK ---

def gemini_worker(q, result_dict, client, model_name, generation_config, system_prompt, log_file, total_segments, lock, delay):
    """Hàm worker cho thread xử lý dịch với Gemini Native SDK."""
    while not q.empty():
        try:
            idx, segment = q.get(block=False)
            segment_id = segment['id']
            with lock:
                current_processed = len([v for v in result_dict.values() if v is not None])
                print(f"\n[{current_processed + 1}/{total_segments}] (Gemini SDK) Đang dịch {segment_id}...")
            
            try:
                # Kết hợp system prompt và user prompt
                full_prompt = f"{system_prompt}\n\nDịch đoạn văn sau từ tiếng Trung sang tiếng Việt:\n\n{segment['content']}"
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=generation_config
                )
                
                # Kiểm tra xem prompt có bị chặn không trước khi truy cập kết quả
                if not response.candidates:
                    # Lấy lý do bị chặn từ prompt_feedback
                    block_reason = "Không rõ"
                    if response.prompt_feedback:
                        block_reason = response.prompt_feedback.block_reason.name
                    raise Exception(f"Prompt bị chặn bởi bộ lọc an toàn: {block_reason}")

                translated = response.text
                
                # Debug: Kiểm tra content có trống không
                if not translated or not translated.strip():
                    raise Exception("Model trả về content trống - có thể do thinking budget quá cao hoặc lỗi API")
                
                # Làm sạch và format lại content
                cleaned_content = clean_content(translated)
                translated_segment = {'id': segment['id'], 'title': segment['title'], 'content': cleaned_content}
                
                with lock:
                    result_dict[idx] = translated_segment
                    write_log(log_file, segment_id, "THÀNH CÔNG")
            
            except Exception as e:
                with lock:
                    result_dict[idx] = segment # Giữ lại segment gốc nếu lỗi
                    write_log(log_file, segment_id, "THẤT BẠI", str(e))
            
            q.task_done()
            time.sleep(delay)
        except queue.Empty:
            break

def translate_with_gemini_threading(segments_to_translate, client, model_name, generation_config, system_prompt, config, log_file):
    """Hàm điều phối threading cho Gemini SDK."""
    q = queue.Queue()
    result_dict = {}
    lock = threading.Lock()
    total_segments = len(segments_to_translate)
    
    for idx, segment in enumerate(segments_to_translate):
        q.put((idx, segment))
        result_dict[idx] = None
    
    api_config = config['translate_api_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), len(segments_to_translate))
    threads = []
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=gemini_worker,
            args=(
                q, result_dict, client, model_name, generation_config, system_prompt, 
                log_file, total_segments, lock,
                api_config.get("delay", 1)
            )
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    results = []
    for idx in sorted(result_dict.keys()):
        if result_dict[idx] is not None:
            results.append(result_dict[idx])
    return results

def gemini_native_workflow(master_config):
    """
    Workflow chính cho việc dịch bằng Gemini Native SDK.
    """
    print("\n" + "="*20 + " BẮT ĐẦU WORKFLOW GEMINI NATIVE SDK " + "="*20)
    
    api_config = master_config['translate_api_settings']
    paths = master_config['paths']
    active_task = master_config['active_task']

    input_file = active_task.get('source_yaml_file')
    system_prompt_file = paths.get('prompt_file')

    # --- Sửa đổi logic đặt tên file để nhất quán ---
    # 1. Tạo base name và timestamp
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 2. Tạo tên file output và log nhất quán
    # Ví dụ: tanaka_cleaned_gemini_native_20250623_174711
    output_basename_with_timestamp = f"{base_name}_cleaned_gemini_native_{timestamp}"
    
    final_output_file = os.path.join(paths['output_dir'], f"{output_basename_with_timestamp}.yaml")
    log_file = os.path.join(paths['log_dir'], f"{output_basename_with_timestamp}.log")

    # Đảm bảo thư mục tồn tại
    if not os.path.exists(paths['output_dir']):
        os.makedirs(paths['output_dir'])
    if not os.path.exists(paths['log_dir']):
        os.makedirs(paths['log_dir'])
    # --- Kết thúc sửa đổi ---

    # --- Khởi tạo Gemini Client ---
    try:
        client = genai.Client(api_key=api_config["api_key"])
        
        # Cấu hình an toàn - TẮT TẤT CẢ
        safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, 
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, 
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, 
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
        ]
        
        # Cấu hình sinh nội dung
        generation_config_params = {
            "temperature": api_config['temperature'],
            "max_output_tokens": api_config.get('max_tokens', 4000)
        }
        
        # Thêm thinking_config - mặc định là 0 (disable thinking) để tiết kiệm token
        thinking_budget = api_config.get('thinking_budget', 0)  # Mặc định = 0
        if thinking_budget is not None:
            try:
                # Theo documentation mới của Gemini API
                generation_config_params['thinking_config'] = types.ThinkingConfig(
                    thinking_budget=int(thinking_budget)
                )
                if thinking_budget == 0:
                    print(f"💡 (Gemini SDK) Đã TẮT thinking (thinking_budget = 0) để tiết kiệm token")
                else:
                    print(f"💡 (Gemini SDK) Đã áp dụng thinking_budget: {thinking_budget}")
            except Exception as e:
                print(f"⚠️ (Gemini SDK) Lỗi khi áp dụng thinking_budget: {e}. Bỏ qua...")

        generation_config = types.GenerateContentConfig(**generation_config_params, safety_settings=safety_settings)
        
        print(f"✅ (Gemini SDK) Đã khởi tạo thành công client và config cho model: {api_config['model']}")
    except Exception as e:
        print(f"❌ (Gemini SDK) Lỗi khởi tạo client: {e}")
        return

    system_prompt = load_prompt(system_prompt_file)
    segments_to_translate = load_yaml(input_file)
    total_segments = len(segments_to_translate)

    # Ghi log ban đầu
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU GEMINI NATIVE WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Tác vụ: {active_task.get('task_name', 'Không tên')}\n")
        f.write(f"Input: {input_file}\nOutput: {final_output_file}\nModel: {api_config['model']}\n\n")

    print(f"Bắt đầu dịch {total_segments} segment với {api_config['concurrent_requests']} threads...")

    translated_segments = translate_with_gemini_threading(
        segments_to_translate, client, api_config['model'], generation_config, system_prompt, master_config, log_file
    )
    
    if not translated_segments:
        print("\n❌ Dịch thuật thất bại, không có segment nào được trả về. Dừng workflow.")
        return

    # Lưu kết quả cuối cùng (bỏ qua bước dọn dẹp vì workflow này chỉ dịch)
    save_yaml(translated_segments, final_output_file)

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- KẾT THÚC WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    print("\n🎉 (Gemini SDK) DỊCH THUẬT HOÀN TẤT! 🎉")
    print(f"Kết quả cuối cùng: {final_output_file}")
    print(f"Log chi tiết: {log_file}") 