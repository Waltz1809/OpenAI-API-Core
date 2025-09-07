#!/usr/bin/env python3
"""
Dịch CLI - Chương trình dịch thuật sử dụng AI APIs
Entry point chính với menu interactive
"""

import sys
import os

# Change working directory to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# Add core modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'workflows'))

from core.ai_factory import load_configs
from workflows.translate import TranslateWorkflow
from workflows.retry import RetryWorkflow  
from workflows.analyze import AnalyzeWorkflow


def show_menu():
    """Hiển thị menu chọn workflow."""
    print("\n" + "="*50)
    print("           DỊCH CLI - MENU CHÍNH")
    print("="*50)
    print("1. Dịch thuật (Translate)")
    print("2. Dịch lại các segment lỗi (Retry)")  
    print("3. Phân tích ngữ cảnh (Context Analysis)")
    print("0. Thoát")
    print("="*50)


def get_user_choice():
    """Lấy lựa chọn từ user."""
    while True:
        try:
            choice = input("Nhập lựa chọn của bạn (0-3): ").strip()
            
            if choice in ['0', '1', '2', '3']:
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
            print(f"📁 File nguồn: {config['active_task']['source_yaml_file']}")
            workflow = TranslateWorkflow(config, secret)
            workflow.run()
            
        elif choice == '2':
            print(f"\n🔄 BẮT ĐẦU WORKFLOW: RETRY")
            workflow = RetryWorkflow(config, secret)
            workflow.run()
            
        elif choice == '3':
            print(f"\n🔍 BẮT ĐẦU WORKFLOW: PHÂN TÍCH NGỮ CẢNH")
            print(f"📁 File nguồn: {config['active_task']['source_yaml_file']}")
            workflow = AnalyzeWorkflow(config, secret)
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
        print("💡 Hãy kiểm tra file config.json và secret.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
