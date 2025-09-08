#!/usr/bin/env python3
"""
Dịch CLI - Chương trình dịch thuật sử dụng AI APIs
Entry point chính với menu interactive
"""

import sys
import os
import pathlib
import threading
import queue
from typing import List

def find_project_root() -> pathlib.Path:
    """Locate the project root (three levels up from this file).
    This duplicates the logic used in other jobs but is self-contained
    to keep jobs independent (no cross-imports).
    """
    return pathlib.Path(__file__).resolve().parent.parent.parent


# Resolve and switch to project root
project_root = find_project_root()
os.chdir(project_root)

def _resolve_path(p: str) -> str:
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.join(str(project_root), p)

# Add core modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'workflows'))

from core.ai_factory import load_configs
from workflows.translate import TranslateWorkflow
from workflows.analyze import AnalyzeWorkflow


def show_menu():
    """Hiển thị menu chọn workflow."""
    print("\n" + "="*50)
    print("           DỊCH CLI - MENU CHÍNH")
    print("="*50)
    print("1. Dịch thuật (Translate)")
    print("2. Phân tích ngữ cảnh (Context Analysis)")
    print("0. Thoát")
    print("="*50)


def get_user_choice():
    """Lấy lựa chọn từ user."""
    while True:
        try:
            choice = input("Nhập lựa chọn của bạn (0-3): ").strip()
            
            if choice in ['0', '1', '2']:
                return choice
            else:
                print("❌ Lựa chọn không hợp lệ! Vui lòng nhập 0, 1, 2, hoặc 3.")
        except KeyboardInterrupt:
            print("\n\n⏹️ Đã hủy chương trình.")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Lỗi: {e}")


def _collect_yaml_files(input_dir: str) -> List[str]:
    files: List[str] = []
    for root, _dirs, fnames in os.walk(input_dir):
        for fname in fnames:
            if fname.lower().endswith(('.yml', '.yaml')):
                files.append(os.path.join(root, fname))
    return files


def run_workflow(choice: str, config: dict, secret: dict):
    """Chạy workflow tương ứng với lựa chọn (đa luồng ở cấp file)."""
    try:
        if choice not in ('1', '2'):
            return True

        mode_translate = (choice == '1')
        print("\n🚀 BẮT ĐẦU WORKFLOW:" + (" DỊCH THUẬT" if mode_translate else " PHÂN TÍCH NGỮ CẢNH"))

        input_dir = config['active_task'].get('input_dir')
        if not input_dir:
            raise ValueError("Thiếu 'input_dir' trong config.active_task")
        input_dir = _resolve_path(input_dir)
        if not os.path.isdir(input_dir):
            raise FileNotFoundError(f"Không tìm thấy thư mục input_dir: {input_dir}")
        print(f"📁 Thư mục nguồn: {input_dir}")

        all_files = _collect_yaml_files(input_dir)
        if not all_files:
            print("⚠️ Không tìm thấy file YAML nào.")
            return True

        print(f"📊 Tổng số file: {len(all_files)}")

        worker_threads = config['translate_api'].get('worker_threads', 1)
        worker_threads = max(1, int(worker_threads))
        print(f"🧵 Số worker threads: {worker_threads}")

        q: queue.Queue[str] = queue.Queue()
        for f in all_files:
            q.put(f)

        q_lock = threading.Lock()
        print_lock = threading.Lock()
        results = {
            'processed': 0,
            'failed': 0
        }

        def worker(worker_id: int):
            while True:
                try:
                    path = q.get_nowait()
                except queue.Empty:
                    break
                try:
                    with print_lock:
                        print(f"➡️  [T{worker_id}] File: {path}")
                    if mode_translate:
                        wf = TranslateWorkflow(config, secret, input_file=path)
                    else:
                        wf = AnalyzeWorkflow(config, secret, input_file=path)
                    wf.run()
                    with q_lock:
                        results['processed'] += 1
                except Exception as e:
                    with print_lock:
                        print(f"❌ [T{worker_id}] Lỗi file {path}: {e}")
                    with q_lock:
                        results['failed'] += 1
                finally:
                    q.task_done()

        threads: List[threading.Thread] = []
        for i in range(worker_threads):
            t = threading.Thread(target=worker, args=(i+1,), daemon=True)
            t.start()
            threads.append(t)

        q.join()
        for t in threads:
            t.join()

        print("\n📊 TỔNG KẾT FILE-LEVEL:")
        print(f"   ✅ Thành công: {results['processed']}")
        print(f"   ❌ Thất bại:  {results['failed']}")
        return results['failed'] == 0

    except Exception as e:
        print(f"❌ Lỗi trong quá trình thực thi: {e}")
        return False

def main():
    """Hàm main chính."""
    print("🎯 DỊCH CLI - Chương trình dịch thuật AI")
    print("   Phiên bản mới - Clean & Simple")
    
    try:
        # Load configs
        config, secret = load_configs()
        print("✅ Đã load config thành công")

        while True:
            show_menu()
            choice = get_user_choice()
            
            if choice == '0':
                print("👋 Cảm ơn bạn đã sử dụng Dịch CLI!")
                break
            
            # Chạy workflow
            success = run_workflow(choice, config, secret)
            
            if success:
                print("\n🎉 Workflow hoàn thành!")
                
                # Hỏi có muốn tiếp tục không
                continue_choice = input("\nBạn có muốn tiếp tục với workflow khác? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    print("👋 Cảm ơn bạn đã sử dụng Dịch CLI!")
                    break
            else:
                print("\n💥 Workflow thất bại! Kiểm tra lại config và thử lại.")
    except Exception as e:
        print(f"❌ Lỗi khởi tạo: {e}")
        print("💡 Hãy kiểm tra file config.yml và secret.yml ở repo root")
        sys.exit(1)


if __name__ == "__main__":
    main()
