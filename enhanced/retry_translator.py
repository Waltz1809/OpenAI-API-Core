import yaml
import time
import openai
import json
import os
import threading
import queue
from datetime import datetime
from typing import List, Dict, Any
from log_analyzer import LogAnalyzer

class CustomDumper(yaml.Dumper):
    def represent_scalar(self, tag, value, style=None):
        if tag == 'tag:yaml.org,2002:str' and "\n" in value:
            style = '|'
        return super().represent_scalar(tag, value, style)

def load_yaml(file_path):
    """Tải file YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(data, file_path):
    """Lưu file YAML."""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)

def load_json(file_path):
    """Tải file JSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    """Lưu file JSON."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_prompt(file_path):
    """Tải nội dung prompt từ file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def write_log(log_file, segment_id, status, error=None):
    """Ghi log kết quả xử lý theo thời gian thực."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {segment_id}: {status}"
    if error:
        log_message += f" - Lỗi: {error}"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")
    
    # In ra màn hình cùng nội dung
    print(log_message)

def find_segment_by_id(segments, segment_id):
    """Tìm segment theo ID."""
    for segment in segments:
        if segment.get('id') == segment_id:
            return segment
    return None

def retry_worker(q, result_dict, failed_segments_data, client, system_prompt, model, temperature, max_tokens, log_file, total_segments, lock, original_segments, max_retries=3):
    """Hàm worker cho thread xử lý các segment retry từ queue."""
    while not q.empty():
        try:
            idx, failed_segment_info = q.get(block=False)
            segment_id = failed_segment_info['segment_id']
            
            with lock:
                current_segment = len([v for v in result_dict.values() if v is not None]) + 1
                print(f"\n[{current_segment}/{total_segments}] Đang retry {segment_id}...")
            
            # Tìm segment gốc từ danh sách original
            original_segment = find_segment_by_id(original_segments, segment_id)
            if not original_segment:
                with lock:
                    result_dict[idx] = None
                    status = "THẤT BẠI - Không tìm thấy segment gốc"
                    write_log(log_file, segment_id, status)
                q.task_done()
                continue
            
            # Retry với số lần tối đa
            success = False
            last_error = None
            
            for retry_attempt in range(max_retries):
                try:
                    if retry_attempt > 0:
                        with lock:
                            print(f"    Thử lại lần {retry_attempt + 1}/{max_retries} cho {segment_id}...")
                    
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Dịch từ tiếng Trung sang tiếng Việt toàn bộ đoạn văn sau:\n\n{original_segment['content']}"}
                        ],
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    if response and response.choices and len(response.choices) > 0 and response.choices[0].message:
                        translated = response.choices[0].message.content
                        if translated:  # Kiểm tra nội dung có tồn tại
                            translated_segment = {
                                'id': original_segment['id'],
                                'title': original_segment['title'],
                                'content': translated
                            }
                            
                            with lock:
                                result_dict[idx] = translated_segment
                                status = f"THÀNH CÔNG (retry {retry_attempt + 1}/{max_retries})"
                                write_log(log_file, segment_id, status)
                            
                            success = True
                            break
                        else:
                            last_error = "Response content is empty"
                    else:
                        last_error = "Invalid response structure"
                        
                except Exception as e:
                    last_error = str(e)
                    if retry_attempt < max_retries - 1:
                        time.sleep(2 ** retry_attempt)  # Exponential backoff
                    continue
            
            if not success:
                with lock:
                    result_dict[idx] = None
                    status = f"THẤT BẠI sau {max_retries} lần thử"
                    write_log(log_file, segment_id, status, last_error)
            
            q.task_done()
            
            # Chờ giữa các request để tránh quá tải API
            time.sleep(1)
            
        except queue.Empty:
            break

def retry_failed_segments(failed_segments_file, original_yaml_file, client, system_prompt, config, log_file, max_retries=3):
    """Retry các segment thất bại."""
    
    # Đọc danh sách segment thất bại
    failed_data = load_json(failed_segments_file)
    failed_segments = failed_data['failed_segments']
    
    # Đọc file YAML gốc để lấy nội dung
    original_segments = load_yaml(original_yaml_file)
    
    if not failed_segments:
        print("Không có segment nào cần retry!")
        return []
    
    print(f"Chuẩn bị retry {len(failed_segments)} segment thất bại...")
    
    q = queue.Queue()
    result_dict = {}
    lock = threading.Lock()
    total_segments = len(failed_segments)
    
    # Đưa failed segment vào queue
    for idx, failed_segment in enumerate(failed_segments):
        q.put((idx, failed_segment))
        result_dict[idx] = None
    
    # Tạo threads
    num_threads = min(config["translation"]["concurrent_requests"], len(failed_segments))
    threads = []
    
    print(f"Sử dụng {num_threads} threads đồng thời với tối đa {max_retries} lần thử cho mỗi segment...")
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=retry_worker,
            args=(
                q, result_dict, failed_data, client, system_prompt, 
                config["api"]["model"], config["translation"]["temperature"], 
                config["api"]["max_tokens"], log_file, total_segments, lock,
                original_segments, max_retries
            )
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Đợi tất cả threads hoàn thành
    for t in threads:
        t.join()
    
    # Thu thập kết quả theo thứ tự index
    results = []
    for idx in sorted(result_dict.keys()):
        if result_dict[idx] is not None:
            results.append(result_dict[idx])
    
    return results

def get_retry_log_filename(failed_segments_file, log_dir):
    """Tạo tên file log cho retry."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    base = os.path.splitext(os.path.basename(failed_segments_file))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"{base}_retry_{timestamp}.log")

def main():
    print("\n--- CHƯƠNG TRÌNH RETRY SEGMENT THẤT BẠI ---")
    print("(Tự động retry các segment dịch thất bại với multithreading)\n")
    
    # Nhập file JSON chứa danh sách segment thất bại
    failed_segments_file = input("Nhập đường dẫn file JSON chứa danh sách segment thất bại: ").strip()
    while not failed_segments_file or not os.path.exists(failed_segments_file):
        print("File không tồn tại, vui lòng nhập lại!")
        failed_segments_file = input("Nhập đường dẫn file JSON chứa danh sách segment thất bại: ").strip()
    
    # Đọc thông tin từ file failed segments
    failed_data = load_json(failed_segments_file)
    print(f"\nThông tin từ file failed segments:")
    print(f"- Tổng số segment thất bại: {failed_data['total_failed']}")
    print(f"- File log gốc: {failed_data['log_file']}")
    print(f"- Thời gian phân tích: {failed_data['analysis_time']}")
    
    # Nhập file YAML gốc
    original_yaml = input("\nNhập đường dẫn file YAML gốc (để lấy nội dung segment): ").strip()
    while not original_yaml or not os.path.exists(original_yaml):
        print("File YAML gốc không tồn tại, vui lòng nhập lại!")
        original_yaml = input("Nhập đường dẫn file YAML gốc: ").strip()
    
    # Nhập file cấu hình
    config_file = input("Nhập đường dẫn file cấu hình JSON: ").strip()
    while not config_file or not os.path.exists(config_file):
        print("File cấu hình không tồn tại, vui lòng nhập lại!")
        config_file = input("Nhập đường dẫn file cấu hình JSON: ").strip()
    
    # Đọc config
    config = load_json(config_file)
    
    # Nhập file system prompt
    system_prompt_file = input("Nhập đường dẫn file system prompt: ").strip()
    while not system_prompt_file or not os.path.exists(system_prompt_file):
        print("File prompt không tồn tại, vui lòng nhập lại!")
        system_prompt_file = input("Nhập đường dẫn file system prompt: ").strip()
    
    # Cấu hình retry
    max_retries = input("Số lần thử tối đa cho mỗi segment (mặc định: 3): ").strip()
    max_retries = int(max_retries) if max_retries.isdigit() else 3
    
    concurrent_requests = input(f"Số request đồng thời (mặc định: {config['translation']['concurrent_requests']}): ").strip()
    if concurrent_requests.isdigit():
        config["translation"]["concurrent_requests"] = int(concurrent_requests)
    
    # Nhập tên file output
    output_base = input("Tên file kết quả retry (không cần hậu tố): ").strip()
    while not output_base:
        print("Vui lòng nhập tên file kết quả!")
        output_base = input("Tên file kết quả retry: ").strip()
    
    # Tạo đường dẫn output
    output_dir = config.get('paths', {}).get('output_dir', 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_file = os.path.join(output_dir, f"{output_base}_retry.yaml")
    
    # Tạo file log cho retry
    log_dir = config.get('paths', {}).get('log_dir', 'logs')
    retry_log_file = get_retry_log_filename(failed_segments_file, log_dir)
    
    # Khởi tạo client
    client = openai.OpenAI(api_key=config["api"]["api_key"], base_url=config["api"]["base_url"])
    system_prompt = load_prompt(system_prompt_file)
    
    # Khởi tạo file log
    with open(retry_log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU RETRY {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Failed segments file: {failed_segments_file}\nOriginal YAML: {original_yaml}\n")
        f.write(f"Output: {output_file}\nModel: {config['api']['model']}\n")
        f.write(f"Max Retries: {max_retries}, Concurrent Requests: {config['translation']['concurrent_requests']}\n\n")
    
    # Bắt đầu retry
    print(f"\nBắt đầu retry với {config['translation']['concurrent_requests']} threads đồng thời...")
    print(f"Mỗi segment sẽ được thử tối đa {max_retries} lần...")
    print(f"Log chi tiết: {retry_log_file}")
    
    retry_results = retry_failed_segments(
        failed_segments_file,
        original_yaml,
        client,
        system_prompt,
        config,
        retry_log_file,
        max_retries
    )
    
    # Lưu kết quả
    if retry_results:
        save_yaml(retry_results, output_file)
        print(f"\nĐã lưu {len(retry_results)} segment thành công vào: {output_file}")
    else:
        print(f"\nKhông có segment nào retry thành công!")
    
    # Kết thúc log
    with open(retry_log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- KẾT THÚC RETRY {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Tổng số segment retry thành công: {len(retry_results)}\n")
    
    print(f"Log chi tiết tại: {retry_log_file}")
    
    # Phân tích lại log retry nếu muốn
    analyze_retry = input(f"\nBạn có muốn phân tích kết quả retry ngay không? (y/n): ").strip().lower()
    if analyze_retry == 'y':
        analyzer = LogAnalyzer(retry_log_file)
        analyzer.parse_log()
        analyzer.print_summary()
        analyzer.print_error_statistics()

if __name__ == "__main__":
    main() 