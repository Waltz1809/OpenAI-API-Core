#!/usr/bin/env python3
"""
Hệ thống tự động phân tích log và retry segment thất bại
Kết hợp log_analyzer.py và retry_translator.py thành một workflow tự động
"""

import os
import sys
import yaml
import openai
from datetime import datetime
import re

# Chuyển đổi sang import tuyệt đối để tương thích với master_workflow
from log_analyzer import LogAnalyzer
from retry_translator import retry_failed_segments, load_json, load_prompt, get_retry_log_filename
from clean_segment import CustomDumper, clean_text

def create_sample_config():
    """Tạo file config mẫu nếu chưa có."""
    config = {
        "api": {
            "api_key": "",  # Người dùng phải điền
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
    return config

def retry_workflow(master_config):
    """
    Workflow tự động được điều khiển bởi master_workflow.
    Nhận master_config làm nguồn dữ liệu duy nhất.
    """
    print("="*60)
    print("    HỆ THỐNG TỰ ĐỘNG RETRY SEGMENT THẤT BẠI")
    print("="*60)
    print()

    # --- Lấy cấu hình từ master_config ---
    active_task = master_config['active_task']
    paths = master_config['paths']
    api_config = master_config['retry_api_settings']
    system_prompt_file = paths['prompt_file']
    max_retries = api_config.get('max_retries_on_fail', 3)
    
    # Xác định file YAML gốc (chưa dịch) và file YAML cần được vá lỗi
    source_yaml_file = active_task['source_yaml_file']
    log_file_to_analyze = active_task['source_log_file_for_retry']
    
    # --- Cải tiến: Thêm kiểm tra định dạng file log ---
    if not log_file_to_analyze.endswith('.log'):
        print(f"❌ Lỗi Cấu Hình: File '{log_file_to_analyze}' không phải là file log (.log).")
        print("   Vui lòng chỉ định file log GỐC được tạo ra từ quá trình 'translate'.")
        print("   Ví dụ: '.../logs/your_file_cleaned_YYYYMMDD_HHMMSS.log'")
        return

    # --- Tự động xác định file cần vá lỗi từ tên file log ---
    # Ví dụ: ".../log/vol1_cleaned_TIMESTAMP.log" -> "vol1_cleaned.yaml"
    log_basename_no_ext = os.path.splitext(os.path.basename(log_file_to_analyze))[0]
    # Xóa timestamp khỏi tên file, ví dụ: "vol1_cleaned_20250608_123456" -> "vol1_cleaned"
    target_yaml_basename_no_ext = re.sub(r'_\d{8}_\d{6}$', '', log_basename_no_ext)
    target_yaml_to_patch_path = os.path.join(paths['output_dir'], f"{target_yaml_basename_no_ext}.yaml")

    # Kiểm tra các file đầu vào
    if not os.path.exists(log_file_to_analyze):
        print(f"❌ Lỗi: File log nguồn '{log_file_to_analyze}' không tồn tại.")
        return
    if not os.path.exists(source_yaml_file):
        print(f"❌ Lỗi: File YAML nguồn '{source_yaml_file}' (để lấy nội dung gốc) không tồn tại.")
        return
    if not os.path.exists(target_yaml_to_patch_path):
        print(f"❌ Lỗi: Không tìm thấy file YAML đã dịch cần vá lỗi tại '{target_yaml_to_patch_path}'.")
        print("   File này được suy ra từ tên file log. Hãy đảm bảo chúng khớp nhau.")
        return
    if not os.path.exists(system_prompt_file):
        print(f"❌ Lỗi: File system prompt '{system_prompt_file}' không tồn tại.")
        return

    # --- Bước 1: Phân tích log ---
    print("📋 BƯỚC 1: PHÂN TÍCH FILE LOG")
    print("-" * 40)
    print(f"🔍 Đang phân tích file log: {log_file_to_analyze}")
    
    analyzer = LogAnalyzer(log_file_to_analyze)
    failed, successful = analyzer.parse_log()
    
    analyzer.print_summary()
    analyzer.print_error_statistics()
    
    if not failed:
        print("\n✅ Tuyệt vời! Không có segment nào thất bại.")
        return
    
    print(f"\n⚠️  Phát hiện {len(failed)} segment thất bại!")
    
    # --- Lưu danh sách segment thất bại vào thư mục tạm ---
    intermediate_dir = paths.get('intermediate_dir', os.path.join(paths['log_dir'], 'temp'))
    if not os.path.exists(intermediate_dir):
        os.makedirs(intermediate_dir)
    
    log_basename = os.path.splitext(os.path.basename(log_file_to_analyze))[0]
    failed_segments_file = os.path.join(intermediate_dir, f"{log_basename}_failed_segments.json")
    analyzer.save_failed_list(failed_segments_file)
    print(f"💾 Đã lưu danh sách segment thất bại vào thư mục tạm: {failed_segments_file}")
    
    # --- Bước 2: Dịch lại các segment thất bại ---
    print(f"\n🔄 BƯỚC 2: DỊCH LẠI {len(failed)} SEGMENT THẤT BẠI")
    print("-" * 40)
    
    # Tạo file log cho riêng lần retry này
    retry_log_file = get_retry_log_filename(failed_segments_file, paths['log_dir'])
    
    print(f"\n🚀 BẮT ĐẦU DỊCH LẠI")
    print(f"   - 🎯 File cần vá lỗi: {target_yaml_to_patch_path}")
    print(f"   - 📄 Log: {retry_log_file}")
    print(f"   - 🔧 Threads: {api_config['concurrent_requests']}")
    print(f"   - 🔄 Max retries: {max_retries}")
    print("-" * 40)
    
    client = openai.OpenAI(api_key=api_config["api_key"], base_url=api_config["base_url"])
    system_prompt = load_prompt(system_prompt_file)

    # Tạo một config tương thích cho hàm `retry_failed_segments`
    retry_translator_config = {
        "api": {
            "api_key": api_config['api_key'],
            "base_url": api_config['base_url'],
            "model": api_config['model'],
            "max_tokens": api_config.get('max_tokens', 4000)
        },
        "translation": {
            "temperature": api_config['temperature'],
            "concurrent_requests": api_config['concurrent_requests'],
            "delay": api_config.get('delay', 1)
        },
        "paths": paths
    }
    
    with open(retry_log_file, 'w', encoding='utf-8') as f:
        f.write(f"--- BẮT ĐẦU AUTO RETRY {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"Original log: {log_file_to_analyze}\n")
        f.write(f"Failed segments file: {failed_segments_file}\n")
        f.write(f"Original YAML: {source_yaml_file}\n")
        f.write(f"Output: {target_yaml_to_patch_path}\n")
        f.write(f"Model: {api_config['model']}\n")
        f.write(f"Max Retries: {max_retries}, Concurrent Requests: {api_config['concurrent_requests']}\n\n")
    
    try:
        # Bước 2a: Dịch lại và chỉ nhận kết quả của những segment đã được sửa
        fixed_segments = retry_failed_segments(
            failed_segments_file,
            source_yaml_file,
            client,
            system_prompt,
            retry_translator_config,
            retry_log_file,
            max_retries
        )
        
        # Bước 2b: Hợp nhất kết quả và ghi đè
        if fixed_segments:
            print("\n" + "="*20 + " BƯỚC 3: DỌN DẸP VÀ HỢP NHẤT " + "="*20)
            
            # --- BƯỚC 3a: Dọn dẹp nội dung đã dịch lại ---
            print(f"🧼 Đang dọn dẹp {len(fixed_segments)} segment đã được dịch lại...")
            for segment in fixed_segments:
                if 'content' in segment and segment['content']:
                    segment['content'] = clean_text(segment['content'])
            print("✅ Dọn dẹp hoàn tất.")

            # --- BƯỚC 3b: Hợp nhất kết quả vào file ---
            print(f"🔧 Đang hợp nhất {len(fixed_segments)} bản vá vào file: {target_yaml_to_patch_path}")

            # Đọc file gốc cần vá lỗi
            with open(target_yaml_to_patch_path, 'r', encoding='utf-8') as f:
                original_data = yaml.safe_load(f)

            # Tạo một dictionary để tra cứu các bản vá lỗi cho nhanh
            fixes_map = {segment['id']: segment['content'] for segment in fixed_segments}
            
            # Cập nhật nội dung trong file gốc
            update_count = 0
            for segment in original_data:
                if segment['id'] in fixes_map:
                    segment['content'] = fixes_map[segment['id']]
                    update_count += 1
            
            # Ghi đè file gốc với dữ liệu đã được cập nhật
            with open(target_yaml_to_patch_path, 'w', encoding='utf-8') as f:
                yaml.dump(original_data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)

            print(f"\n✅ HOÀN THÀNH! Đã cập nhật {update_count} segment.")
            print(f"📁 File '{target_yaml_to_patch_path}' đã được ghi đè với nội dung mới.")
        else:
            print(f"\n❌ Không có segment nào được dịch lại thành công. File gốc không thay đổi.")
        
        # Ghi log tổng kết
        with open(retry_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n--- KẾT THÚC AUTO RETRY {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            f.write(f"Tổng số segment retry thành công: {len(fixed_segments)}\n")
        
        print(f"📄 Log chi tiết của lần retry này: {retry_log_file}")
        
        # Phân tích kết quả của lần retry
        print(f"\n📈 PHÂN TÍCH KẾT QUẢ RETRY")
        print("-" * 30)
        
        retry_analyzer = LogAnalyzer(retry_log_file)
        retry_analyzer.parse_log()
        retry_analyzer.print_summary()
        retry_analyzer.print_error_statistics()
        
        if retry_analyzer.failed_segments:
            print(f"\n⚠️  Vẫn còn {len(retry_analyzer.failed_segments)} segment thất bại sau khi thử lại.")
            print("🔄 Bạn có thể chạy lại chế độ 'retry' với file log mới nhất để thử lại lần nữa.")
        else:
            print("\n🎉 Tất cả segment đã được retry thành công!")
        
    except Exception as e:
        print(f"\n❌ Lỗi trong quá trình retry: {e}")
        print(f"📄 Kiểm tra log chi tiết tại: {retry_log_file}")
    finally:
        # Dọn dẹp file JSON tạm
        if os.path.exists(failed_segments_file):
            os.remove(failed_segments_file)
            print(f"🗑️  Đã dọn dẹp file tạm: {failed_segments_file}")

# Xóa bỏ các hàm auto_workflow và main không còn sử dụng trong workflow mới
# if __name__ == "__main__":
#     main() 