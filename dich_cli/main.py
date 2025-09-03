#!/usr/bin/env python3
"""
Dịch CLI - Chương trình dịch thuật sử dụng AI APIs
Đơn giản hóa: chỉ làm việc với folder từ config, không còn chọn file riêng.
"""

import sys
import os

# Add core modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'workflows'))

from core.ai_factory import load_configs
from workflows.translate import TranslateWorkflow
from workflows.retry import RetryWorkflow
from workflows.analyze import AnalyzeWorkflow


def show_menu():
    """Hiển thị menu chọn workflow."""
    print("\n" + "=" * 50)
    print("           DỊCH CLI - MENU CHÍNH")
    print("=" * 50)
    print("1. Dịch thuật (Translate)")
    print("2. Dịch lại các segment lỗi (Retry)")
    print("3. Phân tích ngữ cảnh (Context Analysis)")
    print("0. Thoát")
    print("=" * 50)


def get_user_choice():
    """Lấy lựa chọn từ user."""
    while True:
        try:
            choice = input("Nhập lựa chọn của bạn (0-3): ").strip()
            if choice in ['0', '1', '2', '3']:
                return choice
            print("❌ Lựa chọn không hợp lệ! Vui lòng nhập 0, 1, 2 hoặc 3.")
        except KeyboardInterrupt:
            print("\n\n⏹️ Đã hủy chương trình.")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Lỗi: {e}")


def collect_yaml_files(folder: str):
    """Tìm toàn bộ file YAML trong folder."""
    yaml_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.endswith((".yaml", ".yml")):
                yaml_files.append(os.path.join(root, f))
    return yaml_files


def run_workflow(choice: str, config: dict, secret: dict):
    """Chạy workflow trên toàn bộ folder từ config."""
    try:
        # Lấy folder nguồn từ config
        source_folder = config.get("active_task", {}).get("source_folder")
        if not source_folder or not os.path.isdir(source_folder):
            print(f"❌ Folder nguồn không tồn tại hoặc chưa cấu hình: {source_folder}")
            return False

        yaml_files = collect_yaml_files(source_folder)
        if not yaml_files:
            print(f"❌ Không tìm thấy file YAML nào trong folder: {source_folder}")
            return False

        # Mapping choice → workflow class
        workflow_map = {
            '1': TranslateWorkflow,
            '2': RetryWorkflow,
            '3': AnalyzeWorkflow
        }

        workflow_cls = workflow_map.get(choice)
        if not workflow_cls:
            print("❌ Workflow chưa hỗ trợ.")
            return False

        print(f"\n🚀 BẮT ĐẦU WORKFLOW: {workflow_cls.__name__}")
        print(f"📂 Folder nguồn: {source_folder}")
        print(f"📊 Số file YAML: {len(yaml_files)}")

        for yaml_file in yaml_files:
            print(f"\n📄 Xử lý file: {yaml_file}")
            config['active_task']['source_yaml_file'] = yaml_file  # vẫn giữ để workflow dùng
            workflow = workflow_cls(config, secret)
            try:
                workflow.run()
            except Exception as e:
                print(f"❌ Lỗi khi xử lý file {yaml_file}: {e}")

        print(f"\n🎉 Đã xử lý xong {len(yaml_files)} file trong folder!")
        return True

    except Exception as e:
        print(f"❌ Lỗi trong quá trình thực thi: {e}")
        return False


def main():
    """Hàm main chính."""
    print("🎯 DỊCH CLI - Chương trình dịch thuật AI")
    print("   Phiên bản gọn nhẹ - Folder only")

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
                cont = input("\nBạn có muốn tiếp tục với workflow khác? (y/n): ").strip().lower()
                if cont != 'y':
                    print("👋 Cảm ơn bạn đã sử dụng Dịch CLI!")
                    break
            else:
                print("\n💥 Workflow thất bại! Kiểm tra lại config và thử lại.")

    except Exception as e:
        print(f"❌ Lỗi khởi tạo: {e}")
        print("💡 Hãy kiểm tra file config.json và secret.json")
        sys.exit(1)


if __name__ == "__main__":
    main()