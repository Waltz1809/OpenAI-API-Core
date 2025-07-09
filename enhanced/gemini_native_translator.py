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

# --- Các hàm pricing đơn giản ---

def load_pricing_data():
    """Load pricing data từ file JSON."""
    pricing_file = os.path.join(script_dir, 'model_pricing.json')
    try:
        with open(pricing_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"⚠️ Không tìm thấy file pricing: {pricing_file}")
        return None
    except Exception as e:
        print(f"⚠️ Lỗi load pricing data: {e}")
        return None

def calculate_total_cost(token_stats, model_name):
    """Tính tổng chi phí dựa trên token stats và model pricing."""
    pricing_data = load_pricing_data()
    if not pricing_data or 'models' not in pricing_data:
        return None
    
    models = pricing_data['models']
    if model_name not in models:
        return None
    
    model_pricing = models[model_name]
    input_tokens = token_stats.get('total_input', 0)
    output_tokens = token_stats.get('total_output', 0)
    thinking_tokens = token_stats.get('total_thinking', 0)
    
    # Tính chi phí (giá / 1M tokens)
    input_cost = (input_tokens * model_pricing['input_price']) / 1_000_000
    output_cost = (output_tokens * model_pricing['output_price']) / 1_000_000
    thinking_cost = (thinking_tokens * model_pricing['input_price']) / 1_000_000  # Thinking tokens tính như input
    
    total_cost = input_cost + output_cost + thinking_cost
    
    return {
        'input_cost': input_cost,
        'output_cost': output_cost,
        'thinking_cost': thinking_cost,
        'total_cost': total_cost,
        'currency': pricing_data.get('currency', 'USD')
    }

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

def write_log(log_file, segment_id, status, error=None, token_info=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {segment_id}: {status}"
    
    # Thêm thông tin token nếu có
    if token_info:
        input_tokens = token_info.get('input_tokens', 'N/A')
        output_tokens = token_info.get('output_tokens', 'N/A')
        thinking_tokens = token_info.get('thinking_tokens', 'N/A')
        total_tokens = token_info.get('total_tokens', 'N/A')
        
        if thinking_tokens != 'N/A' and thinking_tokens > 0:
            log_message += f" | Tokens: Input={input_tokens}, Output={output_tokens}, Thinking={thinking_tokens}, Total={total_tokens}"
        else:
            log_message += f" | Tokens: Input={input_tokens}, Output={output_tokens}, Total={total_tokens}"
    
    if error:
        log_message += f" - Lỗi: {error}"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")
    print(log_message)

def supports_thinking_model(model_name):
    """Kiểm tra xem model có hỗ trợ thinking hay không (chỉ 2.5 series)."""
    return any(version in model_name.lower() for version in ['2.5', '2-5'])

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

def gemini_worker(q, result_dict, client, model_name, generation_config, system_prompt, log_file, total_segments, lock, delay, token_stats):
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
                
                # Lấy thông tin token usage từ response
                token_info = None
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    try:
                        input_tokens = response.usage_metadata.prompt_token_count
                        output_tokens = response.usage_metadata.candidates_token_count
                        total_tokens = response.usage_metadata.total_token_count
                        
                        # Lấy thinking tokens nếu model hỗ trợ (chỉ 2.5 series)
                        thinking_tokens = 0
                        if supports_thinking_model(model_name):
                            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
                        
                        token_info = {
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens,
                            'thinking_tokens': thinking_tokens,
                            'total_tokens': total_tokens
                        }
                        
                        # Cập nhật token stats chung (thread-safe)
                        with lock:
                            token_stats['total_input'] += input_tokens
                            token_stats['total_output'] += output_tokens
                            token_stats['total_thinking'] += thinking_tokens
                            token_stats['total_overall'] += total_tokens
                            token_stats['request_count'] += 1
                    except AttributeError:
                        # Nếu không có usage_metadata hoặc cấu trúc khác, bỏ qua
                        pass
                
                # Làm sạch và format lại content
                cleaned_content = clean_content(translated)
                translated_segment = {'id': segment['id'], 'title': segment['title'], 'content': cleaned_content}
                
                with lock:
                    result_dict[idx] = translated_segment
                    write_log(log_file, segment_id, "THÀNH CÔNG", token_info=token_info)
            
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
    
    # Khởi tạo token statistics
    token_stats = {
        'total_input': 0,
        'total_output': 0,
        'total_thinking': 0,
        'total_overall': 0,
        'request_count': 0
    }
    
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
                api_config.get("delay", 1),
                token_stats
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
    
    return results, token_stats

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
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, 
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, 
                threshold=types.HarmBlockThreshold.OFF
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 
                threshold=types.HarmBlockThreshold.OFF
            ),
        ]
        
        # Cấu hình sinh nội dung
        generation_config_params = {
            "temperature": api_config['temperature'],
            "max_output_tokens": api_config.get('max_tokens', 4000)
        }
        
        # Kiểm tra xem model có hỗ trợ thinking không (chỉ 2.5 series)
        if supports_thinking_model(api_config['model']):
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
        else:
            print(f"ℹ️ (Gemini SDK) Model {api_config['model']} không hỗ trợ thinking - bỏ qua thinking_config")

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

    translated_segments, token_stats = translate_with_gemini_threading(
        segments_to_translate, client, api_config['model'], generation_config, system_prompt, master_config, log_file
    )
    
    if not translated_segments:
        print("\n❌ Dịch thuật thất bại, không có segment nào được trả về. Dừng workflow.")
        return

    # Lưu kết quả cuối cùng (bỏ qua bước dọn dẹp vì workflow này chỉ dịch)
    save_yaml(translated_segments, final_output_file)

    # Tính toán chi phí dự kiến
    cost_info = calculate_total_cost(token_stats, api_config['model'])
    
    # Ghi token summary và cost vào log
    model_supports_thinking = supports_thinking_model(api_config['model'])
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- TOKEN USAGE SUMMARY ---\n")
        f.write(f"Tổng số request thành công: {token_stats['request_count']}\n")
        f.write(f"Tổng Input tokens: {token_stats['total_input']:,}\n")
        f.write(f"Tổng Output tokens: {token_stats['total_output']:,}\n")
        if model_supports_thinking:
            f.write(f"Tổng Thinking tokens: {token_stats['total_thinking']:,}\n")
        f.write(f"Tổng tokens sử dụng: {token_stats['total_overall']:,}\n")
        if token_stats['request_count'] > 0:
            avg_input = token_stats['total_input'] / token_stats['request_count']
            avg_output = token_stats['total_output'] / token_stats['request_count']
            f.write(f"Trung bình Input tokens/request: {avg_input:.1f}\n")
            f.write(f"Trung bình Output tokens/request: {avg_output:.1f}\n")
            if model_supports_thinking:
                avg_thinking = token_stats['total_thinking'] / token_stats['request_count']
                f.write(f"Trung bình Thinking tokens/request: {avg_thinking:.1f}\n")
        
        # Ghi thông tin chi phí
        f.write(f"\n--- CHI PHÍ DỰ KIẾN ---\n")
        if cost_info:
            f.write(f"Chi phí Input tokens: ${cost_info['input_cost']:.6f}\n")
            f.write(f"Chi phí Output tokens: ${cost_info['output_cost']:.6f}\n")
            if cost_info['thinking_cost'] > 0:
                f.write(f"Chi phí Thinking tokens: ${cost_info['thinking_cost']:.6f}\n")
            f.write(f"TỔNG CHI PHÍ DỰ KIẾN: ${cost_info['total_cost']:.6f} {cost_info['currency']}\n")
        else:
            f.write(f"Không tìm thấy thông tin giá cả cho model: {api_config['model']}\n")
        
        f.write(f"\n--- KẾT THÚC WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    print("\n🎉 (Gemini SDK) DỊCH THUẬT HOÀN TẤT! 🎉")
    print(f"Kết quả cuối cùng: {final_output_file}")
    print(f"Log chi tiết: {log_file}")
    
    # Hiển thị token summary
    print(f"\n📊 TOKEN USAGE SUMMARY:")
    print(f"├─ Số request thành công: {token_stats['request_count']}")
    print(f"├─ Tổng Input tokens: {token_stats['total_input']:,}")
    print(f"├─ Tổng Output tokens: {token_stats['total_output']:,}")
    if model_supports_thinking:
        print(f"├─ Tổng Thinking tokens: {token_stats['total_thinking']:,}")
    print(f"└─ Tổng tokens sử dụng: {token_stats['total_overall']:,}")
    if token_stats['request_count'] > 0:
        avg_input = token_stats['total_input'] / token_stats['request_count']
        avg_output = token_stats['total_output'] / token_stats['request_count']
        if model_supports_thinking and token_stats['total_thinking'] > 0:
            avg_thinking = token_stats['total_thinking'] / token_stats['request_count']
            print(f"   Trung bình: {avg_input:.1f} input + {avg_output:.1f} output + {avg_thinking:.1f} thinking = {avg_input + avg_output + avg_thinking:.1f} tokens/request")
        else:
            print(f"   Trung bình: {avg_input:.1f} input + {avg_output:.1f} output = {avg_input + avg_output:.1f} tokens/request")
    
    # Hiển thị thông tin chi phí
    print(f"\n💰 CHI PHÍ DỰ KIẾN:")
    if cost_info:
        print(f"├─ Chi phí Input: ${cost_info['input_cost']:.6f}")
        print(f"├─ Chi phí Output: ${cost_info['output_cost']:.6f}")
        if cost_info['thinking_cost'] > 0:
            print(f"├─ Chi phí Thinking: ${cost_info['thinking_cost']:.6f}")
        print(f"└─ 💵 TỔNG: ${cost_info['total_cost']:.6f} {cost_info['currency']}")
    else:
        print(f"└─ ⚠️ Không tìm thấy thông tin giá cả cho model: {api_config['model']}") 