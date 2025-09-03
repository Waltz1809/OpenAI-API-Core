import asyncio
import json
from playwright.async_api import async_playwright

async def find_selectors():
    """
    Mở trình duyệt và dừng kịch bản để cho phép sử dụng Playwright Inspector
    nhằm tìm và thử nghiệm selector một cách tương tác.
    """
    # --- BƯỚC 1: ĐỌC CẤU HÌNH ---
    print("--- BƯỚC 1: ĐỌC CẤU HÌNH ---")
    try:
        with open('test_auto/config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file 'test_auto/config.json'.")
        print("Vui lòng đảm bảo bạn đang chạy script từ thư mục gốc của dự án.")
        return
    except Exception as e:
        print(f"Lỗi khi đọc file config: {e}")
        return

    # --- BƯỚC 2: KHỞI TẠO TRÌNH DUYỆT VÀ ĐĂNG NHẬP ---
    print("\n--- BƯỚC 2: KHỞI TẠO TRÌNH DUYỆT VÀ ĐĂNG NHẬP ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="msedge")
        page = await browser.new_page()

        await page.goto("https://docln.net/login")
        await page.locator("#name").fill(config['credentials']['username'])
        await page.locator("#password").fill(config['credentials']['password'])

        print("==============================================================")
        print(">> Vui lòng giải reCAPTCHA và nhấn 'Đăng nhập'.")
        print(">> Sau khi đăng nhập xong, kịch bản sẽ tự động tiếp tục.")
        print("==============================================================")
        
        # Chờ người dùng đăng nhập thành công
        try:
            await page.wait_for_url("https://docln.net", timeout=300000) # Chờ tối đa 5 phút
            print("✅ Đăng nhập thành công!")
        except Exception:
            print("❌ Không thể xác nhận đăng nhập sau 5 phút. Kịch bản sẽ dừng.")
            await browser.close()
            return

        # --- BƯỚC 3: ĐIỀU HƯỚNG TỚI TRANG ĐÍCH ĐỂ KIỂM TRA ---
        # Lấy URL quản lý đầu tiên từ config làm trang mẫu
        volumes_to_upload = config.get('volumes_to_upload', [])
        volume_config = config.get('volume_config', {})
        chapter_config = config.get('chapter_config', {})
        mode = config.get('mode', 'volume')
        
        target_url = None
        if mode == 'volume' and volume_config.get('volumes_to_upload'):
            volumes_list = volume_config['volumes_to_upload']
            if volumes_list and volumes_list[0].get('management_url'):
                target_url = volumes_list[0]['management_url']
        elif mode == 'chapter' and chapter_config.get('yaml_files'):
            yaml_files = chapter_config['yaml_files']
            if yaml_files and yaml_files[0].get('management_url'):
                target_url = yaml_files[0]['management_url']
        elif volumes_to_upload and volumes_to_upload[0].get('management_url'):
            # Fallback for old config structure
            target_url = volumes_to_upload[0]['management_url']
        
        if not target_url:
            print("❌ Lỗi: Không tìm thấy 'management_url' trong cấu hình.")
            print(f"Kiểm tra cấu hình cho mode '{mode}' hoặc cấu hình cũ.")
            await browser.close()
            return
        print(f"\n--- BƯỚC 3: ĐIỀU HƯỚNG TỚI TRANG KIỂM TRA ---")
        print(f"Đang điều hướng tới: {target_url}")
        await page.goto(target_url)

        # --- BƯỚC 4: DỪNG LẠI ĐỂ KIỂM TRA ---
        print("\n======================= PLAYWRIGHT INSPECTOR =======================")
        print(">> Trình duyệt đã dừng lại. Cửa sổ Playwright Inspector đã mở.")
        print(">> Hướng dẫn sử dụng:")
        print("   1. Nhấp vào nút 'Pick locator' (biểu tượng con trỏ) trong Inspector.")
        print("   2. Di chuột và nhấp vào phần tử bạn muốn lấy selector trên trang web.")
        print("   3. Selector sẽ xuất hiện trong ô 'Locator' của Inspector.")
        print("   4. Bạn có thể sao chép selector đó và dán vào file config.json.")
        print("   5. Nhấn nút 'Resume' (biểu tượng play) hoặc đóng cửa sổ Inspector để kết thúc kịch bản.")
        print("====================================================================")
        
        await page.pause()

        print("\nKịch bản kết thúc. Đóng trình duyệt.")
        await browser.close()

if __name__ == "__main__":
    print("--- CÔNG CỤ TÌM SELECTOR BẰNG PLAYWRIGHT INSPECTOR ---")
    print("Chạy lệnh 'python test_auto/selector_finder.py' để bắt đầu.")
    asyncio.run(find_selectors()) 