#!/usr/bin/env python3
"""
Workflow Dịch Thuật và Dọn Dẹp Tự Động
MODULE này được gọi bởi master_workflow.py
"""

import yaml
import time
import openai
import re
import json
import os
import threading
import queue
from datetime import datetime
import sys

# Thay thế toàn bộ logic import phức tạp bằng một dòng import tuyệt đối
from clean_segment import process_yaml as clean_yaml_file, CustomDumper

# --- Các hàm và class giữ nguyên ---

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

def get_log_filename(output_filename, log_dir):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    base = os.path.splitext(os.path.basename(output_filename))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"{base}_{timestamp}.log")

def write_log(log_file, segment_id, status, error=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {segment_id}: {status}"
    if error:
        log_message += f" - Lỗi: {error}"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")
    print(log_message)

def title_worker(q, result_dict, client, system_prompt, model, temperature, log_file, lock, delay):
    """Hàm worker cho thread xử lý dịch title. Tối ưu cho workflow."""
    while not q.empty():
        try:
            item = q.get(block=False)
            chapter_id, original_title = item
            
            try:
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Dịch tiêu đề sau từ tiếng Trung sang tiếng Việt, giữ cho ngắn gọn và phù hợp:\n\n{original_title}"}
                    ],
                    model=model,
                    temperature=temperature,
                    max_tokens=200
                )
                
                api_content = response.choices[0].message.content if response.choices and response.choices[0].message else None
                if not api_content:
                    raise ValueError("API không trả về nội dung dịch.")
                
                translated_title = api_content.strip().replace('"', '')
                with lock:
                    result_dict[chapter_id] = translated_title
                    write_log(log_file, f"Title - Chapter: {chapter_id}", "THÀNH CÔNG", f"'{original_title}' -> '{translated_title}'")

            except Exception as e:
                with lock:
                    result_dict[chapter_id] = original_title # Giữ lại title gốc nếu lỗi
                    write_log(log_file, f"Title - Chapter: {chapter_id}", "THẤT BẠI", str(e))
            
            q.task_done()
            time.sleep(delay)
        except queue.Empty:
            break

def translate_titles_in_data(segments, client, system_prompt, config, log_file):
    """
    Dịch các tiêu đề có trong dữ liệu segment.
    Sử dụng lại logic tối ưu: nhóm theo chương, dịch 1 lần.
    """
    print("\n" + "-"*20 + " BƯỚC 1.5: DỊCH TIÊU ĐỀ " + "-"*20)

    # 1. Nhóm các segment theo chương và lấy tiêu đề duy nhất
    chapters_to_translate = {}
    chapter_id_pattern = re.compile(r'(Volume_\d+_Chapter_\d+|Chapter_\d+)')

    for segment in segments:
        chapter_id_match = chapter_id_pattern.search(segment.get('id', ''))
        chapter_id = chapter_id_match.group(0) if chapter_id_match else segment.get('id')
        if not chapter_id:
            continue
        original_title = segment.get('title')
        if original_title and original_title.strip() and chapter_id not in chapters_to_translate:
            chapters_to_translate[chapter_id] = original_title

    if not chapters_to_translate:
        print("Không tìm thấy tiêu đề mới cần dịch. Bỏ qua.")
        return segments
    
    print(f"🔍 Tìm thấy {len(chapters_to_translate)} tiêu đề chương duy nhất cần dịch.")

    # 2. Dịch các tiêu đề bằng threading
    q = queue.Queue()
    translated_titles_map = {}
    lock = threading.Lock()
    
    for chapter_id, title in chapters_to_translate.items():
        q.put((chapter_id, title))
        translated_titles_map[chapter_id] = None # Khởi tạo

    api_config = config['translate_api_settings'] # Dùng chung API setting với content
    title_config = config['title_translation_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), len(chapters_to_translate))
    threads = []
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=title_worker,
            args=(q, translated_titles_map, client, system_prompt, api_config["model"], 
                  api_config["temperature"], log_file, lock, api_config.get("delay", 1))
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()

    # 3. Cập nhật lại dữ liệu YAML gốc với các tiêu đề đã dịch
    update_count = 0
    for segment in segments:
        chapter_id_match = chapter_id_pattern.search(segment.get('id', ''))
        chapter_id = chapter_id_match.group(0) if chapter_id_match else segment.get('id')

        if chapter_id and chapter_id in translated_titles_map:
            translated_title = translated_titles_map[chapter_id]
            if segment.get('title') != translated_title:
                segment['title'] = translated_title
                update_count += 1
    
    print(f"🔄 Đã áp dụng bản dịch tiêu đề cho {update_count} segment.")
    return segments

def worker(q, result_dict, client, system_prompt, model, temperature, max_tokens, log_file, total_segments, lock, delay):
    while not q.empty():
        try:
            idx, segment = q.get(block=False)
            segment_id = segment['id']
            with lock:
                current_processed = len([v for v in result_dict.values() if v is not None])
                print(f"\n[{current_processed + 1}/{total_segments}] Đang dịch {segment_id}...")
            try:
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Dịch đoạn văn sau từ tiếng Trung sang tiếng Việt:\n\n{segment['content']}"}
                    ],
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                translated = response.choices[0].message.content
                translated_segment = {'id': segment['id'], 'title': segment['title'], 'content': translated}
                with lock:
                    result_dict[idx] = translated_segment
                    write_log(log_file, segment_id, "THÀNH CÔNG")
            except Exception as e:
                with lock:
                    result_dict[idx] = segment
                    write_log(log_file, segment_id, "THẤT BẠI", str(e))
            q.task_done()
            time.sleep(delay)
        except queue.Empty:
            break

def translate_with_threading(segments_to_translate, client, system_prompt, config, log_file):
    q = queue.Queue()
    result_dict = {}
    lock = threading.Lock()
    total_segments = len(segments_to_translate)
    for idx, segment in enumerate(segments_to_translate):
        q.put((idx, segment))
        result_dict[idx] = None
    
    # Ở đây, config là master_config
    api_config = config['translate_api_settings']
    num_threads = min(api_config.get("concurrent_requests", 5), len(segments_to_translate))
    threads = []
    
    for _ in range(num_threads):
        t = threading.Thread(
            target=worker,
            args=(
                q, result_dict, client, system_prompt, 
                api_config["model"], api_config["temperature"], 
                api_config.get("max_tokens", 4000), log_file, total_segments, lock,
                api_config.get("delay", 1)
            )
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    results = []
    failed_count = 0
    for idx in sorted(result_dict.keys()):
        if result_dict[idx] is not None:
            results.append(result_dict[idx])
        else:
            failed_count += 1
            
    if failed_count > 0:
        print(f"⚠️  Cảnh báo: Có {failed_count} segment không xử lý được (queue empty).")
        
    return results

def translation_workflow(master_config):
    """
    Hàm chính điều phối quy trình dịch và dọn dẹp.
    Nhận toàn bộ cấu hình từ master_workflow.
    """
    # =========================================================
    # SỬA LỖI Ở ĐÂY: Dùng 'translate_api_settings' thay vì 'api_settings'
    # =========================================================
    api_config = master_config['translate_api_settings']
    
    paths = master_config['paths']
    active_task = master_config['active_task']
    cleaner_settings = master_config['cleaner_settings']
    title_settings = master_config.get('title_translation_settings', {})

    input_file = active_task.get('source_yaml_file')
    if not input_file or not os.path.exists(input_file):
        print(f"❌ Lỗi: File nguồn '{input_file}' không hợp lệ hoặc không tồn tại.")
        return

    output_base = os.path.splitext(os.path.basename(input_file))[0]
    
    # Định nghĩa đường dẫn file
    final_output_file = os.path.join(paths['output_dir'], f"{output_base}_cleaned.yaml")
    temp_trans_file = os.path.join(paths['output_dir'], f"{output_base}_temp_trans.yaml")

    system_prompt_file = paths.get('prompt_file')
    if not system_prompt_file or not os.path.exists(system_prompt_file):
        print(f"❌ Lỗi: File prompt hệ thống '{system_prompt_file}' không hợp lệ hoặc không tồn tại.")
        return

    # Mặc định dịch toàn bộ file
    print("\nChế độ dịch: Dịch toàn bộ file.")
    data = load_yaml(input_file)
    if not data:
        print("Không thể đọc file YAML hoặc file trống!")
        return
    segments_to_translate = data

    # ================= BƯỚC 1: DỊCH THUẬT =================
    print("\n" + "-"*20 + " BƯỚC 1: DỊCH THUẬT " + "-"*20)
    log_file = get_log_filename(final_output_file, paths['log_dir'])
    client = openai.OpenAI(api_key=api_config["api_key"], base_url=api_config["base_url"])
    system_prompt = load_prompt(system_prompt_file)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Tác vụ: {active_task.get('task_name', 'Không tên')}\n")
        f.write(f"Input: {input_file}\nOutput: {final_output_file}\nModel: {api_config['model']}\n\n")
    
    total_segments = len(segments_to_translate)
    print(f"Bắt đầu dịch {total_segments} segment với {api_config['concurrent_requests']} threads...")
    
    translated_segments = translate_with_threading(
        segments_to_translate, client, system_prompt, master_config, log_file
    )
    
    if not translated_segments:
        print("\n❌ Dịch thuật thất bại, không có segment nào được trả về. Dừng workflow.")
        return

    # ================= BƯỚC 1.5: DỊCH TIÊU ĐỀ (TÙY CHỌN) =================
    if title_settings.get('enabled', False):
        title_prompt_file = title_settings.get('title_prompt_file')
        if not title_prompt_file or not os.path.exists(title_prompt_file):
            print(f"⚠️  Cảnh báo: Không tìm thấy file prompt cho tiêu đề tại '{title_prompt_file}'. Bỏ qua dịch tiêu đề.")
        else:
            title_system_prompt = load_prompt(title_prompt_file)
            translated_segments = translate_titles_in_data(
                translated_segments, client, title_system_prompt, master_config, log_file
            )

    save_yaml(translated_segments, temp_trans_file)
    print(f"\n✅ Bước 1 hoàn thành! Kết quả dịch thô lưu tại: {temp_trans_file}")

    # ================= BƯỚC 2: DỌN DẸP KẾT QUẢ =================
    if cleaner_settings.get('enabled', False):
        print("\n" + "-"*20 + " BƯỚC 2: DỌN DẸP KẾT QUẢ " + "-"*20)
        try:
            print(f"Đang dọn dẹp file: {temp_trans_file}")
            clean_yaml_file(temp_trans_file, final_output_file)
            print(f"✅ Bước 2 hoàn thành! Kết quả đã dọn dẹp lưu tại: {final_output_file}")
        except Exception as e:
            print(f"❌ Lỗi trong quá trình dọn dẹp: {e}")
            print(f"Giữ lại file dịch thô tại: {temp_trans_file}")
            return
        finally:
            if os.path.exists(temp_trans_file):
                os.remove(temp_trans_file)
                print(f"Đã xóa file tạm: {temp_trans_file}")
    else:
        print("\n" + "-"*20 + " BƯỚC 2: DỌN DẸP KẾT QUẢ (BỎ QUA) " + "-"*20)
        os.rename(temp_trans_file, final_output_file)
        print(f"✅ Kết quả cuối cùng lưu tại: {final_output_file}")

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- KẾT THÚC WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Tổng số segment đã xử lý: {total_segments}\n")
    
    print("\n🎉 DỊCH THUẬT HOÀN TẤT! 🎉")
    print(f"Kết quả cuối cùng: {final_output_file}")
    print(f"Log chi tiết: {log_file}")

if __name__ == "__main__":
    # Logic gọi workflow chính sẽ được thêm ở đây
    print("Khởi tạo workflow...")