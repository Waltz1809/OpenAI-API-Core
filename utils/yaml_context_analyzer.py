#!/usr/bin/env python3
"""
YAML Context Analyzer - Tiện ích phân tích ngữ cảnh từ file YAML
Đọc file YAML, gửi từng segment đến API để tạo tóm tắt ngữ cảnh,
sau đó ghi kết quả vào một file YAML mới.

TÍNH NĂNG:
- Hỗ trợ cả Gemini và OpenAI
- Tính toán chi phí dự kiến
- Thinking budget cho Gemini 2.5 series
- Safety settings có thể tùy chỉnh
- Token usage tracking

CÁCH DÙNG:
1. Chỉnh sửa config trong yaml_context_analyzer_config.json:
   - "api_provider": "gemini" hoặc "openai"
   - "thinking_budget": 0 (tắt), 1024 (cố định), -1 (dynamic) [chỉ Gemini]
   - Đường dẫn source_yaml_file và system_prompt_file
2. Chạy: python yaml_context_analyzer.py

API PROVIDERS:
- "gemini": Google Gemini API (hỗ trợ thinking cho 2.5 series)
- "openai": OpenAI API (GPT models)

THINKING BUDGET (chỉ Gemini):
- 0: TẮT thinking (tiết kiệm token, nhanh hơn)
- 1024: Bật thinking với budget cố định
- -1: Dynamic thinking (model tự quyết định)

CHI PHÍ:
- Tự động tính toán dựa trên pricing data từ model_pricing.json
- Hiển thị breakdown chi tiết input/output/thinking tokens
"""

import os
import sys
import yaml
import json
import threading
import queue
import time
from datetime import datetime

# Thêm đường dẫn để import CustomDumper
script_dir = os.path.dirname(os.path.abspath(__file__))
enhanced_dir = os.path.abspath(os.path.join(script_dir, '../enhanced'))
sys.path.append(enhanced_dir)

try:
    from clean_segment import CustomDumper
except ImportError:
    print("Cảnh báo: Không thể import CustomDumper. Sẽ sử dụng Dumper mặc định của PyYAML.")
    CustomDumper = yaml.Dumper

# --- SDK Imports (sẽ import tùy theo config) ---
# SDK imports sẽ được thực hiện trong hàm main() tùy theo config

# --- Pricing Functions ---
def load_pricing_data():
    """Load pricing data từ file JSON."""
    pricing_file = os.path.join(enhanced_dir, 'model_pricing.json')
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

def supports_thinking_model(model_name):
    """Kiểm tra xem model có hỗ trợ thinking hay không (chỉ 2.5 series)."""
    return any(version in model_name.lower() for version in ['2.5', '2-5'])

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

def write_log(log_file, segment_id, status, error=None, token_info=None):
    """Ghi log chi tiết cho từng segment."""
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

# --- Logic Phân Tích ---

def analysis_worker_gemini(q, result_dict, client, model_name, generation_config, system_prompt, lock, total_segments, token_stats, delay, log_file):
    """Worker cho thread phân tích segment sử dụng Gemini API."""
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
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=generation_config
                )
                
                # Kiểm tra xem prompt có bị chặn không
                if not response.candidates:
                    block_reason = "Không rõ"
                    if response.prompt_feedback:
                        block_reason = response.prompt_feedback.block_reason.name
                    raise Exception(f"Prompt bị chặn bởi bộ lọc an toàn: {block_reason}")

                # Lấy token usage (Native SDK)
                token_info = None
                try:
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        input_tokens = response.usage_metadata.prompt_token_count
                        output_tokens = response.usage_metadata.candidates_token_count
                        total_tokens = response.usage_metadata.total_token_count
                        
                        # Lấy thinking tokens nếu model hỗ trợ
                        thinking_tokens = 0
                        if supports_thinking_model(model_name):
                            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
                        
                        token_info = {
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens,
                            'thinking_tokens': thinking_tokens,
                            'total_tokens': total_tokens
                        }
                        with lock:
                            token_stats['total_input'] += input_tokens
                            token_stats['total_output'] += output_tokens
                            token_stats['total_thinking'] += thinking_tokens
                            token_stats['total_overall'] += total_tokens
                            token_stats['request_count'] += 1
                except AttributeError:
                    pass
                
                summary_text = response.text
                if not summary_text or not summary_text.strip():
                    raise Exception("Model trả về content trống - có thể do thinking budget quá cao hoặc lỗi API")
                
                new_segment = {
                    'id': segment_id,
                    'title': original_title,
                    'content': summary_text.strip()
                }
                with lock:
                    result_dict[index] = new_segment
                    write_log(log_file, segment_id, "THÀNH CÔNG", token_info=token_info)

            except Exception as e:
                with lock:
                    result_dict[index] = segment # Giữ lại segment gốc
                    write_log(log_file, segment_id, "THẤT BẠI", str(e))
            
            q.task_done()
            time.sleep(delay)

        except queue.Empty:
            break

def analysis_worker_openai(q, result_dict, client, model_name, system_prompt, lock, total_segments, token_stats, delay, log_file, temperature, max_tokens):
    """Worker cho thread phân tích segment sử dụng OpenAI API."""
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
                # Tạo prompt cho OpenAI
                full_prompt = f"{system_prompt}\n\nDưới đây là nội dung cần tóm tắt:\n\n---\n\n{content}"
                
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Dưới đây là nội dung cần tóm tắt:\n\n---\n\n{content}"}
                    ],
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Lấy token usage (OpenAI)
                token_info = None
                try:
                    if hasattr(response, 'usage') and response.usage:
                        input_tokens = response.usage.prompt_tokens
                        output_tokens = response.usage.completion_tokens
                        total_tokens = response.usage.total_tokens
                        
                        token_info = {
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens,
                            'thinking_tokens': 0,  # OpenAI không có thinking tokens
                            'total_tokens': total_tokens
                        }
                        with lock:
                            token_stats['total_input'] += input_tokens
                            token_stats['total_output'] += output_tokens
                            token_stats['total_thinking'] += 0
                            token_stats['total_overall'] += total_tokens
                            token_stats['request_count'] += 1
                except AttributeError:
                    pass
                
                summary_text = response.choices[0].message.content
                if not summary_text or not summary_text.strip():
                    raise Exception("Model trả về content trống")
                
                new_segment = {
                    'id': segment_id,
                    'title': original_title,
                    'content': summary_text.strip()
                }
                with lock:
                    result_dict[index] = new_segment
                    write_log(log_file, segment_id, "THÀNH CÔNG", token_info=token_info)

            except Exception as e:
                with lock:
                    result_dict[index] = segment # Giữ lại segment gốc
                    write_log(log_file, segment_id, "THẤT BẠI", str(e))
            
            q.task_done()
            time.sleep(delay)

        except queue.Empty:
            break

def analyze_and_summarize_threaded(segments, sdk_components, system_prompt, config, log_file):
    """Xử lý tóm tắt các segment bằng threading với SDK linh động."""
    q = queue.Queue()
    # Dùng dict để đảm bảo thứ tự của các segment được giữ nguyên
    result_dict = {}
    lock = threading.Lock()
    total_segments = len(segments)
    
    # Khởi tạo token statistics
    token_stats = {
        'total_input': 0,
        'total_output': 0,
        'total_thinking': 0,
        'total_overall': 0,
        'request_count': 0
    }
    
    for i, seg in enumerate(segments):
        q.put((i, seg))

    api_config = config['api_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), total_segments)
    threads = []
    
    print(f"\nBắt đầu tóm tắt {total_segments} segment với {num_threads} threads...")
    
    # Tùy theo API provider để gọi worker function khác nhau
    api_provider = api_config.get('api_provider', 'gemini')
    delay = api_config.get('delay', 1)
    
    if api_provider == 'openai':
        # OpenAI API
        client = sdk_components['client']
        model_name = sdk_components['model_name']
        temperature = sdk_components['temperature']
        max_tokens = sdk_components['max_tokens']
        
        for _ in range(num_threads):
            t = threading.Thread(
                target=analysis_worker_openai,
                args=(
                    q, result_dict, client, model_name, system_prompt,
                    lock, total_segments, token_stats, delay, log_file, temperature, max_tokens
                )
            )
            t.daemon = True
            t.start()
            threads.append(t)
    else:
        # Gemini API
        client = sdk_components['client']
        model_name = sdk_components['model_name']
        generation_config = sdk_components['generation_config']
        
        for _ in range(num_threads):
            t = threading.Thread(
                target=analysis_worker_gemini,
                args=(
                    q, result_dict, client, model_name, generation_config, system_prompt,
                    lock, total_segments, token_stats, delay, log_file
                )
            )
            t.daemon = True
            t.start()
            threads.append(t)
    
    q.join() # Chờ queue được xử lý hết
    
    # Chuyển đổi dict kết quả thành list theo đúng thứ tự
    final_results = [result_dict[i] for i in sorted(result_dict.keys())]
    return final_results, token_stats

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
    if "YOUR_API_KEY" in api_config.get("api_key", ""):
        api_provider = api_config.get('api_provider', 'gemini')
        api_key = input(f"Vui lòng nhập {api_provider.upper()} API Key của bạn: ").strip()
        if not api_key:
            print("API key là bắt buộc. Dừng chương trình.")
            sys.exit(1)
        api_config['api_key'] = api_key
    
    print(f"\nBắt đầu phân tích file: {yaml_file}")
    print(f"Sử dụng system prompt: {prompt_file}")
    
    # 4. Khởi tạo API client tùy theo config
    api_provider = api_config.get('api_provider', 'gemini')
    model_name = api_config["model"]
    print(f"🔧 Sử dụng API: {api_provider}")
    
    sdk_components = {}
    
    try:
        if api_provider == 'openai':
            # Import OpenAI SDK
            import openai
            
            client = openai.OpenAI(
                api_key=api_config["api_key"],
                base_url=api_config.get("base_url", "https://api.openai.com/v1")
            )
            
            sdk_components = {
                'client': client,
                'model_name': model_name,
                'temperature': api_config["temperature"],
                'max_tokens': api_config.get("max_tokens", 4000)
            }
            
            print(f"✅ (OpenAI) Đã khởi tạo thành công model: {model_name}")
            
        else:
            # Import Gemini Native SDK
            from google import genai
            from google.genai import types
            
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
                "temperature": api_config["temperature"],
                "max_output_tokens": api_config.get("max_tokens", 4000)
            }
            
            # Kiểm tra xem model có hỗ trợ thinking không
            if supports_thinking_model(model_name):
                thinking_budget = api_config.get('thinking_budget', 0)  # Mặc định = 0
                if thinking_budget is not None:
                    try:
                        generation_config_params['thinking_config'] = types.ThinkingConfig(
                            thinking_budget=int(thinking_budget)
                        )
                        if thinking_budget == 0:
                            print(f"💡 Đã TẮT thinking (thinking_budget = 0) để tiết kiệm token")
                        else:
                            print(f"💡 Đã áp dụng thinking_budget: {thinking_budget}")
                    except Exception as e:
                        print(f"⚠️ Lỗi khi áp dụng thinking_budget: {e}. Bỏ qua...")
            else:
                print(f"ℹ️ Model {model_name} không hỗ trợ thinking - bỏ qua thinking_config")

            generation_config = types.GenerateContentConfig(**generation_config_params, safety_settings=safety_settings)
            
            sdk_components = {
                'client': client,
                'model_name': model_name,
                'generation_config': generation_config
            }
            
            print(f"✅ (Gemini) Đã khởi tạo thành công model: {model_name}")
            
    except Exception as e:
        print(f"❌ Lỗi khởi tạo API client: {e}")
        sys.exit(1)

    # 5. Tạo log file và thực thi phân tích
    base_filename = os.path.splitext(os.path.basename(yaml_file))[0]
    output_dir = paths_config.get("output_dir", "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    log_file = os.path.join(output_dir, f"{base_filename}_context.txt")
    
    # Ghi log ban đầu
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU YAML CONTEXT ANALYZER {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"File nguồn: {yaml_file}\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"API Provider: {api_provider}\n")
        f.write(f"Tổng segments: {len(segments)}\n\n")
    
    summarized_segments, token_stats = analyze_and_summarize_threaded(segments, sdk_components, system_prompt, config, log_file)

    if not summarized_segments:
        print("\nKhông có kết quả nào được xử lý. Dừng chương trình.")
        sys.exit(1)
        
    # 6. Lưu kết quả
    save_output_yaml(summarized_segments, output_dir, base_filename)
    
    # 7. Ghi token summary vào log
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- TOKEN USAGE SUMMARY ---\n")
        f.write(f"Tổng số request thành công: {token_stats['request_count']}\n")
        f.write(f"Tổng Input tokens: {token_stats['total_input']:,}\n")
        f.write(f"Tổng Output tokens: {token_stats['total_output']:,}\n")
        if api_provider == 'gemini' and supports_thinking_model(model_name):
            f.write(f"Tổng Thinking tokens: {token_stats['total_thinking']:,}\n")
        f.write(f"Tổng tokens sử dụng: {token_stats['total_overall']:,}\n")
        if token_stats['request_count'] > 0:
            avg_input = token_stats['total_input'] / token_stats['request_count']
            avg_output = token_stats['total_output'] / token_stats['request_count']
            f.write(f"Trung bình Input tokens/request: {avg_input:.1f}\n")
            f.write(f"Trung bình Output tokens/request: {avg_output:.1f}\n")
            if api_provider == 'gemini' and supports_thinking_model(model_name):
                avg_thinking = token_stats['total_thinking'] / token_stats['request_count']
                f.write(f"Trung bình Thinking tokens/request: {avg_thinking:.1f}\n")
        
        # Ghi thông tin chi phí vào log
        f.write(f"\n--- CHI PHÍ DỰ KIẾN ---\n")
        cost_info = calculate_total_cost(token_stats, model_name)
        if cost_info:
            f.write(f"Chi phí Input tokens: ${cost_info['input_cost']:.6f}\n")
            f.write(f"Chi phí Output tokens: ${cost_info['output_cost']:.6f}\n")
            if cost_info['thinking_cost'] > 0:
                f.write(f"Chi phí Thinking tokens: ${cost_info['thinking_cost']:.6f}\n")
            f.write(f"TỔNG CHI PHÍ DỰ KIẾN: ${cost_info['total_cost']:.6f} {cost_info['currency']}\n")
        else:
            f.write(f"Không tìm thấy thông tin giá cả cho model: {model_name}\n")
        
        f.write(f"\n--- KẾT THÚC ANALYZER {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    # 8. Hiển thị chi phí
    cost_info = calculate_total_cost(token_stats, model_name)
    
    print("\n📊 TOKEN USAGE SUMMARY:")
    print(f"├─ Số request thành công: {token_stats['request_count']}")
    print(f"├─ Tổng Input tokens: {token_stats['total_input']:,}")
    print(f"├─ Tổng Output tokens: {token_stats['total_output']:,}")
    if api_provider == 'gemini' and supports_thinking_model(model_name):
        print(f"├─ Tổng Thinking tokens: {token_stats['total_thinking']:,}")
    print(f"└─ Tổng tokens sử dụng: {token_stats['total_overall']:,}")
    
    if token_stats['request_count'] > 0:
        avg_input = token_stats['total_input'] / token_stats['request_count']
        avg_output = token_stats['total_output'] / token_stats['request_count']
        if api_provider == 'gemini' and supports_thinking_model(model_name) and token_stats['total_thinking'] > 0:
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
        print(f"└─ ⚠️ Không tìm thấy thông tin giá cả cho model: {model_name}")
    
    print("\n🎉 Phân tích hoàn tất!")
    print(f"📄 Log chi tiết: {log_file}")

if __name__ == "__main__":
    main() 