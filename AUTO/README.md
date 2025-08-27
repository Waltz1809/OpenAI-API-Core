# Auto Upload Tool - Hướng dẫn sử dụng

Tool này hỗ trợ 2 chế độ làm việc khác nhau tùy thuộc vào cấu trúc dữ liệu của bạn.

## 🔧 Cấu hình

### Mode 1: Volume Mode (Chế độ Volume)
Sử dụng khi YAML có cấu trúc `Volume_X_Chapter_Y_Segment_Z`

```json
{
    "mode": "volume",
    "credentials": {
        "username": "your_username",
        "password": "your_password"
    },
    "volume_config": {
        "yaml_filepath": "path/to/your/volume.yaml",
        "volumes_to_upload": [
            {
                "volume_id_prefix": "Volume_1",
                "management_url": "https://docln.sbs/action/series/22142/manage?book_id=30122&action=createchapter"
            },
            {
                "volume_id_prefix": "Volume_2",
                "management_url": "https://docln.sbs/action/series/22142/manage?book_id=30123&action=createchapter"
            }
        ]
    },
    "set_as_incomplete": true,
    "chapter_range": 5,
    "selectors": {
        "title": "role=textbox",
        "editor_iframe": "iframe[title=\"Vùng văn bản phong phú\"]",
        "editor_body": "#tinymce",
        "submit_button": "role=button[name=\"Thêm chương\"]",
        "incomplete_radio_button": "role=radio[name=\"Chưa hoàn thành\"]"
    }
}
```

### Mode 2: Chapter Mode (Chế độ Chapter)
Sử dụng khi YAML có cấu trúc `Chapter_X_Segment_Y` và bạn muốn mỗi file YAML đăng lên 1 URL khác nhau

```json
{
    "mode": "chapter",
    "credentials": {
        "username": "your_username",
        "password": "your_password"
    },
    "chapter_config": {
        "yaml_files": [
            {
                "yaml_filepath": "path/to/chapter1.yaml",
                "management_url": "https://docln.sbs/action/series/22142/manage?book_id=30122&action=createchapter"
            },
            {
                "yaml_filepath": "path/to/chapter2.yaml",
                "management_url": "https://docln.sbs/action/series/22143/manage?book_id=30123&action=createchapter"
            },
            {
                "yaml_filepath": "path/to/chapter3.yaml",
                "management_url": "https://docln.sbs/action/series/22144/manage?book_id=30124&action=createchapter"
            }
        ]
    },
    "set_as_incomplete": true,
    "chapter_range": 3,
    "selectors": {
        "title": "role=textbox",
        "editor_iframe": "iframe[title=\"Vùng văn bản phong phú\"]",
        "editor_body": "#tinymce",
        "submit_button": "role=button[name=\"Thêm chương\"]",
        "incomplete_radio_button": "role=radio[name=\"Chưa hoàn thành\"]"
    }
}
```

## 🚀 Cách sử dụng

1. **Cài đặt dependencies:**
   ```bash
   pip install "playwright==1.44.0" pyyaml
   playwright install
   ```

2. **Cấu hình config.json:**
   - Chọn mode phù hợp (`"volume"` hoặc `"chapter"`)
   - Điền thông tin đăng nhập
   - Cấu hình đường dẫn file YAML và URL management
   - Tùy chọn: Thiết lập `chapter_range` để giới hạn số chương upload (mặc định: upload tất cả)

3. **Chạy script:**
   ```bash
   python main.py
   ```

## 🔍 Cấu trúc dữ liệu YAML

### Volume Mode
```yaml
- id: "Volume_1_Chapter_1_Segment_1"
  title: "Chương 1: Khởi đầu"
  content: "Nội dung segment 1..."
  
- id: "Volume_1_Chapter_1_Segment_2"
  title: "Chương 1: Khởi đầu"
  content: "Nội dung segment 2..."
  
- id: "Volume_1_Chapter_2_Segment_1"
  title: "Chương 2: Phát triển"
  content: "Nội dung segment 1..."
```

### Chapter Mode
```yaml
- id: "Chapter_1_Segment_1"
  title: "Chương 1: Khởi đầu"
  content: "Nội dung segment 1..."
  
- id: "Chapter_1_Segment_2"
  title: "Chương 1: Khởi đầu"
  content: "Nội dung segment 2..."
  
- id: "Chapter_2_Segment_1"
  title: "Chương 2: Phát triển"
  content: "Nội dung segment 1..."
```

## ⚡ Tính năng

- ✅ Hỗ trợ 2 chế độ làm việc linh hoạt
- ✅ Upload nhiều volume/chapter song song
- ✅ Tự động sắp xếp chapter và segment theo thứ tự
- ✅ Xử lý nội dung lớn bằng clipboard
- ✅ Tùy chọn đánh dấu "Chưa hoàn thành"
- ✅ Xử lý lỗi và tạm dừng để debug
- ✅ Chờ delay giữa các request để tránh bị block
- ✅ **Giới hạn số chương upload với `chapter_range`**

## 🔧 Tham số chapter_range

Tham số `chapter_range` cho phép bạn giới hạn số lượng chương được upload từ mỗi file:

- **Giá trị số nguyên dương** (ví dụ: `5`): Chỉ upload 5 chương đầu tiên
- **`null` hoặc `0`**: Upload tất cả chương có trong file (mặc định)
- **Không có tham số**: Upload tất cả chương có trong file

**Ví dụ:**
```json
{
    "chapter_range": 10,  // Chỉ upload 10 chương đầu tiên từ mỗi file
    // ... các cấu hình khác
}
```

Tính năng này hữu ích khi:
- Bạn muốn test với một số lượng chương nhỏ trước
- File YAML có quá nhiều chương và bạn chỉ muốn upload một phần
- Bạn muốn chia nhỏ quá trình upload thành nhiều lần

## 📝 Ghi chú

- Script sẽ tự động nhóm các segment theo chapter
- Các segment trong cùng 1 chapter sẽ được nối với nhau bằng 2 dòng trống
- Title của chapter sẽ lấy từ segment đầu tiên trong chapter đó
- Script sẽ dừng lại khi gặp lỗi để bạn có thể debug