import yaml
import time
import openai
import re
import json
import os
import threading
import queue
from datetime import datetime

# Này để gửi request đến API rồi dịch

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

def get_log_filename(output_filename, log_dir):
    """Tạo tên file log với thời gian."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    base = os.path.splitext(os.path.basename(output_filename))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"{base}_{timestamp}.log")

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

def extract_chapter_number(segment_id):
    """Trích xuất số chapter từ ID segment."""
    match = re.search(r'[cC]hapter_(\d+)', segment_id, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def group_segments_by_chapter(segments):
    """Nhóm các segment theo chapter."""
    chapters = {}
    for segment in segments:
        chapter_num = extract_chapter_number(segment['id'])
        if chapter_num is not None:
            if chapter_num not in chapters:
                chapters[chapter_num] = []
            chapters[chapter_num].append(segment)
    return chapters

def translate_segment(segment, client, system_prompt, model, temperature, max_tokens):
    """Gửi nội dung segment tới API để dịch."""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Dịch từ tiếng Trung sang tiếng Việt toàn bộ đoạn văn sau:\n\n{segment['content']}"}
            ],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        translated = response.choices[0].message.content
        # Cập nhật nội dung đã dịch nhưng giữ nguyên ID và tiêu đề
        return {
            'id': segment['id'],
            'title': segment['title'],
            'content': translated
        }, None
    except Exception as e:
        return None, str(e)

def worker(q, result_dict, client, system_prompt, model, temperature, max_tokens, log_file, total_segments, lock):
    """Hàm worker cho thread xử lý các segment từ queue."""
    while not q.empty():
        try:
            idx, segment = q.get(block=False)
            segment_id = segment['id']
            
            with lock:
                current_segment = len([v for v in result_dict.values() if v is not None]) + 1
                print(f"\n[{current_segment}/{total_segments}] Đang dịch {segment_id}...")
            
            try:
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Dịch từ tiếng Trung sang tiếng Việt toàn bộ đoạn văn sau:\n\n{segment['content']}"}
                    ],
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                translated = response.choices[0].message.content
                translated_segment = {
                    'id': segment['id'],
                    'title': segment['title'],
                    'content': translated
                }
                
                with lock:
                    result_dict[idx] = translated_segment
                    status = "THÀNH CÔNG"
                    write_log(log_file, segment_id, status)
            
            except Exception as e:
                with lock:
                    result_dict[idx] = segment  # Giữ segment gốc nếu lỗi
                    status = "THẤT BẠI"
                    write_log(log_file, segment_id, status, str(e))
            
            q.task_done()
            
            # Chờ giữa các request để tránh quá tải API
            time.sleep(1)
            
        except queue.Empty:
            break

def translate_with_threading(segments_to_translate, client, system_prompt, config, log_file):
    """Xử lý dịch các segment bằng threading."""
    q = queue.Queue()
    result_dict = {}  # Sử dụng dict để lưu kết quả theo index
    lock = threading.Lock()
    total_segments = len(segments_to_translate)
    
    # Đưa segment vào queue
    for idx, segment in enumerate(segments_to_translate):
        q.put((idx, segment))
        result_dict[idx] = None
    
    # Tạo threads
    num_threads = min(config["translation"]["concurrent_requests"], len(segments_to_translate))
    threads = []
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=worker,
            args=(
                q, result_dict, client, system_prompt, 
                config["api"]["model"], config["translation"]["temperature"], 
                config["api"]["max_tokens"], log_file, total_segments, lock
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

def create_default_config():
    """Tạo file cấu hình mặc định và trả về đường dẫn."""
    config = {
        "api": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "max_tokens": 4000
        },
        "translation": {
            "temperature": 0.7,
            "concurrent_requests": 5,
            "delay": 1
        },
        "paths": {
            "output_dir": "output",
            "log_dir": "logs"
        }
    }
    
    config_path = "config.json"
    save_json(config, config_path)
    print(f"Đã tạo file cấu hình mặc định: {config_path}")
    return config_path

def main():
    print("\n--- CHƯƠNG TRÌNH DỊCH YAML NÂNG CAO V2 ---")
    print("(Phiên bản hỗ trợ multithreading và JSON config)\n")
    
    # Cho phép người dùng chọn file cấu hình có sẵn
    use_existing_config = input("Bạn đã có file cấu hình JSON? (y/n) [n]: ").strip().lower() or "n"
    
    if use_existing_config == "y":
        # Cho phép người dùng chọn file cấu hình
        config_file = input("Nhập đường dẫn file cấu hình JSON: ").strip()
        if not os.path.exists(config_file):
            print(f"File cấu hình {config_file} không tồn tại!")
            config_file = create_default_config()
    else:
        # Tạo file config mới
        config_file = create_default_config()
    
    print(f"Đọc cấu hình từ file: {config_file}")
    
    # Đọc config từ file
    config = load_json(config_file)
    
    # Đảm bảo config có phần paths
    if "paths" not in config:
        config["paths"] = {
            "output_dir": "output",
            "log_dir": "logs"
        }
    
    # Nhập các tham số cần thiết
    input_file = input("File YAML cần dịch: ").strip()
    while not input_file:
        print("Vui lòng nhập đường dẫn file YAML cần dịch!")
        input_file = input("File YAML cần dịch: ").strip()
    
    output_base = input("Tên file đầu ra (không cần hậu tố): ").strip()
    while not output_base:
        print("Vui lòng nhập tên file đầu ra!")
        output_base = input("Tên file đầu ra (không cần hậu tố): ").strip()
    
    # Hỏi đường dẫn thư mục đầu ra
    output_dir = input(f"Nhập đường dẫn thư mục lưu file kết quả dịch (mặc định: {config['paths']['output_dir']}): ").strip()
    if output_dir:
        config['paths']['output_dir'] = output_dir
    # Đảm bảo thư mục tồn tại
    if not os.path.exists(config['paths']['output_dir']):
        os.makedirs(config['paths']['output_dir'])
        
    # Hỏi đường dẫn thư mục log
    log_dir = input(f"Nhập đường dẫn thư mục lưu file log (mặc định: {config['paths']['log_dir']}): ").strip()
    if log_dir:
        config['paths']['log_dir'] = log_dir
    # Đảm bảo thư mục tồn tại
    if not os.path.exists(config['paths']['log_dir']):
        os.makedirs(config['paths']['log_dir'])
    
    # Cập nhật lại file config
    save_json(config, config_file)
    
    output_file = os.path.join(config['paths']['output_dir'], f"{output_base}_trans.yaml")
    
    system_prompt_file = input("File system prompt: ").strip()
    while not system_prompt_file or not os.path.exists(system_prompt_file):
        print("File prompt không tồn tại, vui lòng nhập lại!")
        system_prompt_file = input("File system prompt: ").strip()
    
    # Nếu API key trống, yêu cầu nhập
    if not config["api"]["api_key"]:
        config["api"]["api_key"] = input("API key (bắt buộc): ").strip()
        while not config["api"]["api_key"]:
            print("Vui lòng nhập API key!")
            config["api"]["api_key"] = input("API key: ").strip()
        
        # Cập nhật file config với API key
        save_json(config, config_file)
    
    # Chọn chế độ dịch
    print("\nChọn chế độ dịch:")
    print("1 - Dịch theo khoảng segment")
    print("2 - Dịch theo chapter")
    mode = input("Nhập lựa chọn (1 hoặc 2): ").strip()
    while mode not in ["1", "2"]:
        print("Lựa chọn không hợp lệ, vui lòng nhập 1 hoặc 2!")
        mode = input("Nhập lựa chọn (1 hoặc 2): ").strip()
    
    # Đọc dữ liệu đầu vào
    data = load_yaml(input_file)
    if not data:
        print("Không thể đọc file hoặc file trống!")
        return
    
    # Thiết lập phạm vi dịch
    if mode == "1":  # Dịch theo khoảng segment
        start_segment = int(input(f"Bắt đầu từ segment (1-{len(data)}) [1]: ").strip() or 1)
        end_segment_input = input(f"Kết thúc ở segment (1-{len(data)}, để trống nếu dịch hết): ").strip()
        end_segment = int(end_segment_input) if end_segment_input else len(data)
        
        # Kiểm tra phạm vi hợp lệ
        if start_segment < 1:
            start_segment = 1
        if end_segment > len(data):
            end_segment = len(data)
        if start_segment > end_segment:
            print("Lỗi: Segment bắt đầu lớn hơn segment kết thúc!")
            return
        
        segments_to_translate = data[start_segment-1:end_segment]
    else:  # Dịch theo chapter
        chapters = group_segments_by_chapter(data)
        if not chapters:
            print("Không tìm thấy chapter nào trong file YAML!")
            return
        
        print("\nCác chapter có sẵn:")
        chapter_numbers = sorted(chapters.keys())
        for chapter in chapter_numbers:
            print(f"Chapter {chapter}: {len(chapters[chapter])} segment")
        
        start_chapter = int(input(f"Bắt đầu từ chapter ({min(chapter_numbers)}-{max(chapter_numbers)}) [{min(chapter_numbers)}]: ").strip() or min(chapter_numbers))
        end_chapter_input = input(f"Kết thúc ở chapter ({min(chapter_numbers)}-{max(chapter_numbers)}, để trống nếu dịch hết): ").strip()
        end_chapter = int(end_chapter_input) if end_chapter_input else max(chapter_numbers)
        
        # Kiểm tra phạm vi hợp lệ
        if start_chapter not in chapter_numbers:
            print(f"Lỗi: Chapter {start_chapter} không tồn tại!")
            return
        if end_chapter not in chapter_numbers:
            print(f"Lỗi: Chapter {end_chapter} không tồn tại!")
            return
        if start_chapter > end_chapter:
            print("Lỗi: Chapter bắt đầu lớn hơn chapter kết thúc!")
            return
        
        # Tạo danh sách segment cần dịch từ các chapter đã chọn
        segments_to_translate = []
        for chapter in range(start_chapter, end_chapter + 1):
            if chapter in chapters:
                segments_to_translate.extend(chapters[chapter])
    
    # Tạo file log
    log_file = get_log_filename(output_file, config['paths']['log_dir'])
    
    # Khởi tạo client
    client = openai.OpenAI(api_key=config["api"]["api_key"], base_url=config["api"]["base_url"])
    system_prompt = load_prompt(system_prompt_file)
    
    # Khởi tạo file log
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU DỊCH {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Input: {input_file}\nOutput: {output_file}\nModel: {config['api']['model']}\n")
        f.write(f"Max Tokens: {config['api']['max_tokens']}, Temperature: {config['translation']['temperature']}\n")
        f.write(f"Mode: {'Segment' if mode == '1' else 'Chapter'}, Concurrent Requests: {config['translation']['concurrent_requests']}\n\n")
    
    # Xử lý dịch bằng threading
    total_segments = len(segments_to_translate)
    print(f"\nBắt đầu dịch {total_segments} segment với {config['translation']['concurrent_requests']} threads đồng thời...")
    
    translated_segments = translate_with_threading(
        segments_to_translate, 
        client, 
        system_prompt, 
        config, 
        log_file
    )
    
    # Lưu kết quả cuối cùng
    save_yaml(translated_segments, output_file)
    
    # Kết thúc log
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- KẾT THÚC DỊCH {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Tổng số segment đã xử lý: {total_segments}\n")
    
    print(f"\nHoàn thành! Kết quả lưu tại: {output_file}")
    print(f"Log chi tiết tại: {log_file}")

if __name__ == "__main__":
    main() 