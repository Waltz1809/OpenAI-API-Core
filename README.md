# OpenAI API Core - Công cụ Dịch Thuật Nâng cao

Một bộ công cụ dòng lệnh dựa trên Python được thiết kế để tự động hóa quy trình dịch thuật các tệp văn bản lớn (định dạng YAML) bằng cách sử dụng các API tương thích với OpenAI.

## Tính năng nổi bật

- **Hai luồng hoạt động chính**: `translate` (dịch mới) và `retry` (thử lại các phần dịch lỗi).
- **Cấu hình tập trung**: Toàn bộ quy trình được điều khiển bởi một tệp `workflow_config.json` duy nhất.
- **Tùy chỉnh API linh hoạt**: Cho phép cài đặt các thông số API (model, endpoint, concurrency) riêng biệt cho lần dịch đầu và cho các lần thử lại.
- **Tự động dọn dẹp**: Tùy chọn xóa bỏ các "khối suy nghĩ" (thinking blocks) không mong muốn từ kết quả của API.
- **Quản lý đường dẫn**: Dễ dàng tùy chỉnh các đường dẫn cho tệp đầu vào, đầu ra, log và prompt.
- **Phát hiện log tự động**: Chế độ `retry` có thể tự động tìm và sử dụng tệp log mới nhất để dịch lại các phần bị lỗi.

## Hướng dẫn sử dụng

### 1. Cài đặt

Clone Repo
Install OpenAI lib
Install cn2an
Install PyYaml

### 2. Chuẩn bị tệp tin

- **Tệp cần dịch**: Tệp .txt chứa văn bản/bộ truyện muốn dịch. Định dạng tốt nhất là:
Quyển X:
Chương Y:
Nội dung chương.
- **Tệp Prompt**: Tạo một tệp `.txt` chứa prompt (câu lệnh hướng dẫn) chi tiết để định hướng cho mô hình ngôn ngữ khi dịch.

### 3. Cấu hình

Mở tệp `enhanced/workflow_config.json` và chỉnh sửa các thông số cho phù hợp với nhu cầu của bạn.

```json
{
  "active_task": {
    "task_name": "Dich-sach-chuong-1",
    "workflow_mode": "translate", // Chế độ: 'translate' hoặc 'retry'
    "source_yaml_file": "duong/dan/den/sach.yaml",
    "source_log_file_for_retry": "LATEST" // 'LATEST' hoặc đường dẫn đến file .log
  },
  "translate_api_settings": {
    "api_key": "YOUR_API_KEY",
    "base_url": "YOUR_API_ENDPOINT",
    "model": "gpt-4-turbo",
    "concurrent_requests": 6
    // ... các cài đặt khác
  },
  "retry_api_settings": {
    "api_key": "YOUR_API_KEY",
    "base_url": "YOUR_API_ENDPOINT",
    "model": "gpt-4-vision-preview",
    "concurrent_requests": 3
    // ... các cài đặt khác
  },
  "paths": {
    "output_dir": "ket-qua/output",
    "log_dir": "ket-qua/logs",
    "prompt_file": "duong/dan/den/prompt.txt"
    // ... các cài đặt khác
  }
}
```

### 4. Chạy chương trình

Tách file cần dịch thành định dạng .yaml với file enhanced_chapter_splitter.py

Sau khi đã cấu hình xong, di chuyển vào thư mục `enhanced` và thực thi tệp `master_workflow.py`.

Chương trình sẽ tự động đọc tệp cấu hình và chạy luồng công việc (`translate` hoặc `retry`) tương ứng.

## Giải thích chi tiết `workflow_config.json`

- `active_task`: Khu vực chính để điều khiển tác vụ.
  - `task_name`: Tên định danh cho tác vụ của bạn (hữu ích cho việc quản lý log).
  - `workflow_mode`: Chọn `"translate"` để dịch một tệp YAML từ đầu hoặc `"retry"` để chỉ dịch lại các segment bị lỗi dựa trên một tệp log.
  - `source_yaml_file`: Đường dẫn đến tệp YAML nguồn cần dịch.
  - `source_log_file_for_retry`: Dành cho chế độ `retry`. Đặt là `"LATEST"` để tự động tìm tệp log mới nhất trong `log_dir`, hoặc chỉ định đường dẫn trực tiếp đến một tệp `.log`.
- `translate_api_settings`: Cấu hình API cho lần dịch đầu tiên.
- `retry_api_settings`: Cấu hình API dành riêng cho việc dịch lại các segment lỗi. Bạn có thể sử dụng một model khác hoặc giảm số lượng request đồng thời để tăng khả năng thành công.
- `cleaner_settings`: Cài đặt cho việc làm sạch đầu ra.
  - `enabled`: `true` để bật, `false` để tắt.
  - `remove_thinking_blocks`: `true` sẽ tự động xóa các khối `<thinking>...</thinking>` khỏi tệp kết quả.
- `paths`: Định nghĩa các đường dẫn làm việc cho dự án.
  - `output_dir`: Thư mục lưu các tệp dịch thuật hoàn chỉnh.
  - `log_dir`: Thư mục lưu các tệp log.
  - `prompt_file`: Đường dẫn đến tệp chứa prompt dịch thuật.
  - `intermediate_dir`: Thư mục chứa các tệp xử lý trung gian.
