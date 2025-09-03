import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError
from collections import defaultdict
import re

try:
    import yaml
except ImportError:
    print("Lỗi: Thư viện PyYAML chưa được cài đặt.")
    print("Vui lòng chạy lệnh sau trong terminal: pip install pyyaml")
    exit()

async def process_volume_mode(config, all_segments, page, selectors):
    """Xử lý mode volume - như cách cũ"""
    volume_config = config.get('volume_config', {})
    volumes_to_upload_list = volume_config.get('volumes_to_upload', [])
    
    if not volumes_to_upload_list:
        print("Lỗi: Không tìm thấy danh sách 'volumes_to_upload' trong volume_config hoặc danh sách rỗng.")
        return False

    # Lặp qua từng volume trong danh sách
    for volume_info in volumes_to_upload_list:
        volume_id_prefix = volume_info.get('volume_id_prefix')
        upload_url = volume_info.get('management_url')

        if not volume_id_prefix or not upload_url:
            print(f"⚠️  Bỏ qua một mục trong 'volumes_to_upload' vì thiếu 'volume_id_prefix' hoặc 'management_url'.")
            continue
        
        print(f"\n========================================================")
        print(f" BẮT ĐẦU XỬ LÝ VOLUME: {volume_id_prefix}")
        print(f"========================================================")

        # Lọc và nhóm các segment theo từng chương của volume hiện tại một cách CHÍNH XÁC
        chapters = defaultdict(list)
        # Regex để trích xuất ID chương đầy đủ (ví dụ: "Volume_1_Chapter_0")
        # Điều này đảm bảo chỉ lấy các chương thuộc đúng volume hiện tại (tránh lỗi Volume_1 và Volume_11)
        chapter_id_pattern = re.compile(f"({re.escape(volume_id_prefix)}_Chapter_\\d+)")

        for segment in all_segments:
            match = chapter_id_pattern.search(segment['id'])
            if match:
                # Key giờ sẽ là ID đầy đủ và duy nhất, ví dụ: "Volume_1_Chapter_0"
                chapter_key = match.group(1)
                chapters[chapter_key].append(segment)

        if not chapters:
            print(f"Không tìm thấy chương nào cho '{volume_id_prefix}' trong file YAML. Chuyển sang volume tiếp theo.")
            continue
        
        print(f"Tìm thấy {len(chapters)} chương để đăng cho {volume_id_prefix}.")
        
        # Sắp xếp các chương theo đúng thứ tự, dựa trên số chương trong key mới
        # Ví dụ key "Volume_1_Chapter_0" -> split: ['Volume', '1', 'Chapter', '0'] -> lấy phần tử cuối
        sorted_chapters = sorted(chapters.items(), key=lambda item: int(item[0].split('_')[-1]))

        # Áp dụng giới hạn chapter_range nếu có
        chapter_range = config.get('chapter_range')
        if chapter_range and chapter_range > 0:
            sorted_chapters = sorted_chapters[:chapter_range]
            print(f"Giới hạn upload chỉ {chapter_range} chương đầu tiên cho {volume_id_prefix}.")

        success = await upload_chapters(sorted_chapters, volume_id_prefix, upload_url, page, selectors, config)
        if not success:
            return False
            
    return True


async def process_chapter_mode(config, page, selectors):
    """Xử lý mode chapter - mỗi file YAML tương ứng với 1 URL management"""
    chapter_config = config.get('chapter_config', {})
    yaml_files = chapter_config.get('yaml_files', [])
    
    if not yaml_files:
        print("Lỗi: Không tìm thấy danh sách 'yaml_files' trong chapter_config hoặc danh sách rỗng.")
        return False

    for file_info in yaml_files:
        yaml_filepath = file_info.get('yaml_filepath')
        upload_url = file_info.get('management_url')
        
        if not yaml_filepath or not upload_url:
            print(f"⚠️  Bỏ qua một mục trong 'yaml_files' vì thiếu 'yaml_filepath' hoặc 'management_url'.")
            continue
            
        print(f"\n========================================================")
        print(f" BẮT ĐẦU XỬ LÝ FILE: {yaml_filepath}")
        print(f" URL: {upload_url}")
        print(f"========================================================")
        
        # Đọc file YAML
        try:
            with open(yaml_filepath, 'r', encoding='utf-8') as f:
                segments = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Lỗi: Không tìm thấy file {yaml_filepath}")
            continue
        except Exception as e:
            print(f"❌ Lỗi khi đọc file {yaml_filepath}: {e}")
            continue
            
        # Nhóm các segment theo chương (Chapter_X_Segment_Y)
        chapters = defaultdict(list)
        chapter_pattern = re.compile(r"(Chapter_(\d+))_Segment_\d+")
        
        for segment in segments:
            match = chapter_pattern.search(segment['id'])
            if match:
                chapter_key = match.group(1)  # "Chapter_1", "Chapter_2", etc.
                chapter_num = int(match.group(2))  # Số chương để sắp xếp
                chapters[chapter_key].append(segment)
        
        if not chapters:
            print(f"Không tìm thấy chương nào với cấu trúc Chapter_X_Segment_Y trong file {yaml_filepath}.")
            continue
            
        print(f"Tìm thấy {len(chapters)} chương để đăng từ file {yaml_filepath}.")
        
        # Sắp xếp các chương theo số thứ tự
        sorted_chapters = sorted(chapters.items(), key=lambda item: int(item[0].split('_')[1]))

        # Áp dụng giới hạn chapter_range nếu có
        chapter_range = config.get('chapter_range')
        if chapter_range and chapter_range > 0:
            sorted_chapters = sorted_chapters[:chapter_range]
            print(f"Giới hạn upload chỉ {chapter_range} chương đầu tiên từ file {yaml_filepath}.")

        success = await upload_chapters(sorted_chapters, f"File: {yaml_filepath}", upload_url, page, selectors, config)
        if not success:
            return False
            
    return True


async def upload_chapters(sorted_chapters, source_name, upload_url, page, selectors, config):
    """Upload các chương lên website"""
    for i, (chapter_key, segments_in_chapter) in enumerate(sorted_chapters):
        print(f"\n({i+1}/{len(sorted_chapters)}) Đang chuẩn bị đăng chương: {chapter_key} (từ {source_name})")
        
        # Sắp xếp các segment trong chương theo đúng thứ tự (Segment_1, Segment_2, ...)
        def get_segment_num(seg):
            match = re.search(r'Segment_(\d+)', seg.get('id', ''))
            return int(match.group(1)) if match else 0
        
        sorted_segments = sorted(segments_in_chapter, key=get_segment_num)

        if not sorted_segments:
            print(f"Bỏ qua chương {chapter_key} vì không có segment nào.")
            continue
        
        # Kết hợp các segment thành một nội dung hoàn chỉnh
        full_content = "\n\n".join([s.get('content', '') for s in sorted_segments])
        
        # Lấy tiêu đề chương từ trường 'title' của segment đầu tiên
        chapter_title = sorted_segments[0].get('title', f'Chương {chapter_key.split("_")[-1]}')
        print(f"Tiêu đề: {chapter_title}")

        try:
            # 1. Điều hướng đến trang tạo chương mới cho mỗi lần lặp
            print("Điều hướng đến trang tạo chương...")
            await page.goto(upload_url)

            # 2. Điền form
            print("Đang chờ form tải...")
            form_frame = page.frame_locator('iframe[name="action"]')
            
            # Chờ và điền tiêu đề
            print("Điền tiêu đề chương...")
            title_locator = form_frame.locator(selectors['title'])
            await title_locator.wait_for(state='visible', timeout=30000) # Chờ tối đa 30s
            await title_locator.fill(chapter_title)
            
            # Chờ và điền nội dung bằng phương pháp clipboard để ổn định hơn
            print("Điền nội dung chương...")
            editor_frame = form_frame.frame_locator(selectors['editor_iframe'])
            editor_body_locator = editor_frame.locator(selectors['editor_body'])
            await editor_body_locator.wait_for(state='visible', timeout=60000) # Tăng timeout chờ editor sẵn sàng

            # Sử dụng clipboard để dán nội dung lớn, sẽ ổn định hơn .fill()
            print(f"-> Chuẩn bị dán nội dung lớn ({len(full_content)} ký tự) bằng clipboard...")
            await page.evaluate('''(text) => navigator.clipboard.writeText(text)''', full_content)
            
            await editor_body_locator.click() # Click để focus vào editor
            await page.keyboard.press('Control+V') # Dán nội dung
            print("-> Đã dán nội dung thành công.")
            
            # 3. (Tùy chọn) Chọn trạng thái 'Chưa hoàn thành'
            if config.get('set_as_incomplete', False):
                radio_selector = selectors.get('incomplete_radio_button')
                if radio_selector:
                    try:
                        print("Chọn trạng thái 'Chưa hoàn thành'...")
                        await form_frame.locator(radio_selector).click(timeout=3000)
                        print("-> Đã chọn 'Chưa hoàn thành'.")
                    except TimeoutError:
                        print(f"⚠️  Không tìm thấy radio button 'Chưa hoàn thành' với selector '{radio_selector}'. Bỏ qua bước này.")
                    except Exception as e:
                        print(f"⚠️  Lỗi khi chọn radio button 'Chưa hoàn thành': {e}")
            
            # 4. Gửi form
            await form_frame.locator(selectors['submit_button']).click()
            
            print(f"✅ Đã gửi yêu cầu đăng cho {chapter_key}. Chờ 15 giây trước khi tiếp tục...")
            await page.wait_for_timeout(15000) # Chờ 15 giây để server xử lý và tránh bị block

        except Exception as e:
            print(f"❌ LỖI khi đang đăng {chapter_key}: {e}")
            print("Kịch bản sẽ dừng lại. Vui lòng kiểm tra lỗi và chạy lại nếu cần.")
            await page.pause() # Dừng lại để bạn debug
            return False # Dừng quá trình upload
            
    return True


async def main():
    # --- BƯỚC 1: ĐỌC CẤU HÌNH ---
    print("--- BƯỚC 1: ĐỌC CẤU HÌNH ---")
    try:
        with open('test/python/test_auto/config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file cấu hình. Chi tiết: {e}")
        return
    except Exception as e:
        print(f"Lỗi khi đọc file cấu hình: {e}")
        return

    # Kiểm tra mode
    mode = config.get('mode', 'volume')
    if mode not in ['volume', 'chapter']:
        print(f"Lỗi: Mode '{mode}' không hợp lệ. Chỉ hỗ trợ 'volume' hoặc 'chapter'.")
        return
        
    print(f"Chế độ được chọn: {mode.upper()}")

    # Đọc dữ liệu YAML cho mode volume
    all_segments = None
    if mode == 'volume':
        volume_config = config.get('volume_config', {})
        yaml_filepath = volume_config.get('yaml_filepath')
        if not yaml_filepath:
            print("Lỗi: Không tìm thấy 'yaml_filepath' trong 'volume_config'.")
            return
            
        try:
            with open(yaml_filepath, 'r', encoding='utf-8') as f:
                all_segments = yaml.safe_load(f)
            print(f"Đã đọc file YAML: {yaml_filepath}")
        except FileNotFoundError:
            print(f"Lỗi: Không tìm thấy file YAML: {yaml_filepath}")
            return
        except Exception as e:
            print(f"Lỗi khi đọc file YAML: {e}")
            return

    # --- BƯỚC 2: KHỞI TẠO TRÌNH DUYỆT VÀ ĐĂNG NHẬP ---
    print("\n--- BƯỚC 2: ĐĂNG NHẬP ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="msedge")
        # Tạo context riêng và cấp quyền truy cập clipboard
        context = await browser.new_context()
        await context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page = await context.new_page()

        await page.goto("https://docln.sbs/login")
        await page.locator("#name").fill(config['credentials']['username'])
        await page.locator("#password").fill(config['credentials']['password'])

        print("==============================================================")
        print(">> Vui lòng giải reCAPTCHA và nhấn 'Đăng nhập'.")
        print(">> Sau khi đăng nhập xong, quay lại đây và nhấn Enter.")
        print("==============================================================")
        input("Nhấn Enter để bắt đầu quá trình đăng hàng loạt...")

        # --- BƯỚC 3: ĐĂNG TẢI HÀNG LOẠT ---
        print("\n--- BƯỚC 3: BẮT ĐẦU ĐĂNG HÀNG LOẠT ---")
        selectors = config.get('selectors', {})
        
        success = False
        if mode == 'volume':
            success = await process_volume_mode(config, all_segments, page, selectors)
        elif mode == 'chapter':
            success = await process_chapter_mode(config, page, selectors)

        if success:
            print("\n🎉🎉🎉 Quá trình đăng hàng loạt đã hoàn tất! 🎉🎉🎉")
        else:
            print("\n❌ Quá trình đăng hàng loạt đã bị dừng do có lỗi xảy ra.")
            
        print("Trình duyệt sẽ đóng sau 60 giây.")
        await asyncio.sleep(60)
        await browser.close()

if __name__ == "__main__":
    # Để chạy được file script này, bạn cần cài đặt một vài thứ:
    # 1. Cài đặt Python từ trang chủ: https://www.python.org/downloads/
    #    (Trong lúc cài, nhớ tick vào ô "Add Python to PATH")
    #
    # 2. Mở cửa sổ dòng lệnh (Command Prompt, PowerShell hoặc Terminal) và chạy 2 lệnh sau:
    #    pip install "playwright==1.44.0"
    #    playwright install
    #    (Lệnh 'playwright install' sẽ tự động cài đặt trình duyệt Edge nếu cần)
    #
    # 3. Sau khi cài đặt xong, bạn có thể chạy file này bằng lệnh:
    #    python main.py
    #    (Hãy chắc chắn bạn đang ở trong thư mục test_auto khi chạy lệnh)

    asyncio.run(main()) 