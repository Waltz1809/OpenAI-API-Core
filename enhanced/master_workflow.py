#!/usr/bin/env python3
"""
Master Workflow - Script điều phối chính
Đọc file config và quyết định chạy workflow nào (dịch, retry, etc.)
"""

import json
import os
import sys

# Thêm các đường dẫn cần thiết để import module từ các thư mục khác
script_dir = os.path.dirname(os.path.abspath(__file__))
utils_test_dir = os.path.abspath(os.path.join(script_dir, '../utils_test'))
utils_dir = os.path.abspath(os.path.join(script_dir, '../utils'))
sys.path.append(utils_test_dir)
sys.path.append(utils_dir)
sys.path.append(script_dir)

# Import các workflow con
try:
    from translation_workflow import translation_workflow
    from auto_retry_system import retry_workflow
except ImportError as e:
    print(f"Lỗi import: {e}")
    print("Hãy đảm bảo các file workflow con (translation_workflow.py, auto_retry_system.py) tồn tại.")
    sys.exit(1)


def load_master_config(config_path='workflow_config.json'):
    """Tải và kiểm tra file cấu hình chính."""
    config_full_path = os.path.join(script_dir, config_path)
    if not os.path.exists(config_full_path):
        print(f"❌ Lỗi: File cấu hình '{config_full_path}' không tồn tại.")
        return None
    
    try:
        with open(config_full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if 'active_task' not in config or 'workflow_mode' not in config['active_task']:
            print("❌ Lỗi: File cấu hình thiếu 'active_task' hoặc 'workflow_mode'.")
            return None
            
        return config
    except Exception as e:
        print(f"❌ Lỗi không xác định khi đọc file cấu hình: {e}")
        return None

def run_translation_mode(config):
    """Chạy chế độ dịch thuật."""
    # Kiểm tra các trường bắt buộc cho chế độ này
    source_yaml = config['active_task'].get('source_yaml_file')
    prompt_file = config['paths'].get('prompt_file')

    if not source_yaml or not os.path.exists(source_yaml):
        print(f"❌ Lỗi (Chế độ Dịch): File nguồn 'source_yaml_file' ('{source_yaml}') không hợp lệ hoặc không tồn tại trong config.")
        return

    if not prompt_file or not os.path.exists(prompt_file):
        print(f"❌ Lỗi (Chế độ Dịch): File prompt 'prompt_file' ('{prompt_file}') không hợp lệ hoặc không tồn tại trong config.")
        return

    print("\n" + "="*60)
    print("🚀 Bắt đầu chế độ: DỊCH THUẬT (TRANSLATE)")
    print(f"   Tác vụ: {config['active_task'].get('task_name', 'Không có tên')}")
    print("="*60 + "\n")
    
    # Gọi workflow dịch thuật và truyền toàn bộ config vào
    translation_workflow(config)
    

def find_latest_log_file(log_dir):
    """
    Tìm file log (.log) được chỉnh sửa gần đây nhất trong một thư mục.
    Cải tiến: Chỉ tìm các file log của quá trình 'translate' (thường có '_cleaned_' trong tên).
    """
    if not os.path.isdir(log_dir):
        return None
    
    # Lọc chỉ những file log của quá trình translate (có chữ '_cleaned_')
    log_files = [
        os.path.join(log_dir, f) 
        for f in os.listdir(log_dir) 
        if f.endswith('.log') and '_cleaned_' in f
    ]
    
    if not log_files:
        return None
        
    latest_file = max(log_files, key=os.path.getmtime)
    return latest_file

def run_retry_mode(config):
    """Chạy chế độ retry."""
    source_log = config['active_task'].get('source_log_file_for_retry')
    
    # Tự động tìm file log mới nhất nếu được yêu cầu
    if source_log == "LATEST":
        log_dir = config.get('paths', {}).get('log_dir')
        if not log_dir:
            print("❌ Lỗi (Chế độ Retry): Không thể tự động tìm log khi 'paths.log_dir' không được định nghĩa trong config.")
            return
            
        print(f"🔎 Đang tự động tìm file log mới nhất trong: {log_dir}...")
        latest_log = find_latest_log_file(log_dir)
        
        if not latest_log:
            print(f"❌ Lỗi (Chế độ Retry): Không tìm thấy file log nào trong thư mục '{log_dir}'.")
            return
        
        source_log = latest_log
        print(f"✅ Đã tìm thấy file log mới nhất: {source_log}")
        # Cập nhật lại config để truyền đi cho đúng
        config['active_task']['source_log_file_for_retry'] = source_log

    # Kiểm tra các trường bắt buộc cho chế độ này
    if not source_log or not os.path.exists(source_log):
        print(f"❌ Lỗi (Chế độ Retry): File log 'source_log_file_for_retry' ('{source_log}') không hợp lệ hoặc không tồn tại.")
        return
        
    # Chế độ retry cần biết file YAML gốc để lấy nội dung segment.
    source_yaml = config['active_task'].get('source_yaml_file')
    if not source_yaml or not os.path.exists(source_yaml):
        print(f"❌ Lỗi (Chế độ Retry): Phải cung cấp 'source_yaml_file' hợp lệ trong config để retry.")
        return

    print("\n" + "="*60)
    print("🔄 Bắt đầu chế độ: DỊCH LẠI (RETRY)")
    print(f"   Tác vụ: {config['active_task'].get('task_name', 'Không có tên')}")
    print("="*60 + "\n")
    
    # Gọi workflow retry và truyền toàn bộ config vào
    retry_workflow(config)

def main():
    """Hàm chính để chạy master workflow."""
    print("=============================================")
    print("      KHỞI ĐỘNG MASTER WORKFLOW      ")
    print("=============================================")
    
    config = load_master_config()
    
    if config is None:
        print("\nDừng chương trình do lỗi cấu hình.")
        return
        
    mode = config['active_task'].get('workflow_mode')
    
    if mode == 'translate':
        run_translation_mode(config)
    elif mode == 'retry':
        run_retry_mode(config)
    else:
        print(f"❌ Lỗi: Chế độ workflow '{mode}' không được hỗ trợ.")
        print("Vui lòng chọn 'translate' hoặc 'retry' trong file workflow_config.json.")

if __name__ == "__main__":
    main() 