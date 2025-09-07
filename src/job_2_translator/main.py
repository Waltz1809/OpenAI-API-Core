#!/usr/bin/env python3
"""
Dịch CLI - Chương trình dịch thuật sử dụng AI APIs
Entry point chính với menu interactive
"""

import sys
import os

# Determine repo root (this file: <repo_root>/src/job_2_translator/main.py)
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(repo_root)

def _resolve_path(p: str) -> str:
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.join(repo_root, p)

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


def run_workflow(choice: str, config: dict, secret: dict):
    """Chạy workflow tương ứng với lựa chọn."""
    try:
        if choice == '1':
            print(f"\n🚀 BẮT ĐẦU WORKFLOW: DỊCH THUẬT")
            input_dir = config['active_task'].get('input_dir')
            if not input_dir:
                raise ValueError("Thiếu 'input_dir' trong config.active_task")
            input_dir = _resolve_path(input_dir)
            if not os.path.isdir(input_dir):
                raise FileNotFoundError(f"Không tìm thấy thư mục input_dir: {input_dir}")
            print(f"📁 Thư mục nguồn: {input_dir}")

            # Duyệt tất cả YAML trong thư mục (đệ quy)
            for root, _dirs, files in os.walk(input_dir):
                for fname in files:
                    if not fname.lower().endswith(('.yml', '.yaml')):
                        continue
                    full_path = os.path.join(root, fname)
                    print(f"\n➡️  File: {full_path}")
                    workflow = TranslateWorkflow(config, secret, input_file=full_path)
                    workflow.run()
        elif choice == '2':
            print(f"\n🔍 BẮT ĐẦU WORKFLOW: PHÂN TÍCH NGỮ CẢNH")
            input_dir = config['active_task'].get('input_dir')
            if not input_dir:
                raise ValueError("Thiếu 'input_dir' trong config.active_task")
            input_dir = _resolve_path(input_dir)
            if not os.path.isdir(input_dir):
                raise FileNotFoundError(f"Không tìm thấy thư mục input_dir: {input_dir}")
            print(f"📁 Thư mục nguồn: {input_dir}")

            for root, _dirs, files in os.walk(input_dir):
                for fname in files:
                    if not fname.lower().endswith(('.yml', '.yaml')):
                        continue
                    full_path = os.path.join(root, fname)
                    print(f"\n➡️  File: {full_path}")
                    workflow = AnalyzeWorkflow(config, secret, input_file=full_path)
                    workflow.run()
    except Exception as e:
        print(f"❌ Lỗi trong quá trình thực thi: {e}")
        return False
    
    return True

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
