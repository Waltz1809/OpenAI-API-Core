#!/usr/bin/env python3
"""
YAML Context Analyzer - Tiện ích phân tích ngữ cảnh từ file YAML
Đọc file YAML, gửi từng segment đến API để tạo tóm tắt ngữ cảnh,
sau đó ghi kết quả vào một file YAML mới.
Đây là một tiện ích độc lập, sử dụng Google Gemini Native SDK.
"""

import os
import sys
import yaml
import json
import threading
import queue
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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

def analysis_worker(q, result_dict, model, system_prompt, lock, total_segments):
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
                result_dict[index] = {'id': segment_id, 'title': original_title, 'content': ''}
                q.task_done()
                continue

            try:
                # Tạo prompt hoàn chỉnh cho Gemini
                full_prompt = f"{system_prompt}\n\nDưới đây là nội dung cần tóm tắt:\n\n---\n\n{content}"
                
                response = model.generate_content(full_prompt)
                
                # Kiểm tra API có trả về nội dung không
                if response.text:
                    summary_text = response.text
                    new_segment = {
                        'id': segment_id,
                        'title': original_title,
                        'content': summary_text.strip()
                    }
                    result_dict[index] = new_segment
                else:
                    # Xử lý trường hợp không có nội dung (bị filter, etc.)
                    block_reason = "Không rõ"
                    if response.prompt_feedback:
                        block_reason = response.prompt_feedback.block_reason.name
                    with lock:
                        print(f"⚠️ Cảnh báo: API không trả về nội dung cho {segment_id} (lý do: {block_reason}). Giữ lại nội dung gốc.")
                    result_dict[index] = segment # Giữ lại segment gốc

            except Exception as e:
                with lock:
                    print(f"❌ Lỗi API cho segment {segment_id}: {e}")
                # Nếu lỗi, giữ lại content gốc để không mất dữ liệu
                result_dict[index] = segment
            
            q.task_done()

        except queue.Empty:
            break

def analyze_and_summarize_threaded(segments, model, system_prompt, config):
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
                q, result_dict, model, system_prompt,
                lock, total_segments
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
    if "YOUR_GEMINI_API_KEY" in api_config.get("api_key", ""):
        api_key = input("Vui lòng nhập Gemini API Key của bạn: ").strip()
        if not api_key:
            print("API key là bắt buộc. Dừng chương trình.")
            sys.exit(1)
        api_config['api_key'] = api_key
    
    print(f"\nBắt đầu phân tích file: {yaml_file}")
    print(f"Sử dụng system prompt: {prompt_file}")
    
    # 4. Chuẩn bị và thực thi
    try:
        genai.configure(api_key=api_config["api_key"])

        # Cấu hình an toàn
        safety_settings = [
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        ]
        
        # Cấu hình sinh nội dung
        gen_config_params = {
            "temperature": api_config["temperature"],
            "max_output_tokens": api_config["max_tokens"]
        }
        
        # Thêm thinking_budget nếu có
        if 'thinking_budget' in api_config and api_config['thinking_budget'] is not None:
            try:
                # Sửa lỗi: ThinkingConfig là một class riêng, không nằm trong GenerationConfig
                gen_config_params['thinking_config'] = genai.types.ThinkingConfig(
                    thinking_budget=int(api_config['thinking_budget'])
                )
                print(f"💡 Đã áp dụng thinking_budget: {api_config['thinking_budget']}")
            except AttributeError:
                print(f"⚠️ (Gemini SDK) Lỗi: Phiên bản 'google-generativeai' của bạn có thể quá cũ và không hỗ trợ 'ThinkingConfig'. Bỏ qua thinking_budget.")
            except Exception as e:
                print(f"⚠️ (Gemini SDK) Lỗi không xác định khi áp dụng thinking_budget: {e}. Bỏ qua...")

        generation_config = genai.types.GenerationConfig(**gen_config_params)

        model = genai.GenerativeModel(
            model_name=api_config["model"],
            safety_settings=safety_settings,
            generation_config=generation_config
        )
        print(f"✅ (Gemini SDK) Đã khởi tạo thành công model: {api_config['model']}")
    except Exception as e:
        print(f"❌ (Gemini SDK) Lỗi khởi tạo model: {e}")
        sys.exit(1)

    summarized_segments = analyze_and_summarize_threaded(segments, model, system_prompt, config)

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