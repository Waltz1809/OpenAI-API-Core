# Dịch CLI - Chương trình dịch thuật AI

Chương trình dịch thuật sử dụng AI APIs (OpenAI, Gemini, Vertex) với kiến trúc clean và đơn giản.

## Tính năng

- ✅ **Translate**: Dịch cả content và title trong 1 lần chạy
- ✅ **Auto-Retry tích hợp**: Tự động thử lại segments lỗi trong cùng workflow (không còn module retry riêng)
- ✅ **Context Analysis**: Phân tích ngữ cảnh văn bản
- ✅ **Multi-provider**: Hỗ trợ OpenAI, Gemini, Vertex AI (tách riêng clients)
- ✅ **Smart logging**: Naming convention `ddmmyy_giờ_SDK_tên.log`
- ✅ **Progress reports**: Báo cáo tiến độ tự động
- ✅ **Threading**: Xử lý đồng thời để tăng tốc

## Cài đặt

1. **Clone repository**
```bash
# Ví dụ
git clone <repo_url>
cd OpenAI-API-Core/src/job_2_translator
```

2. **Cài đặt dependencies** (tối thiểu)
```bash
pip install openai google-genai pyyaml
```

3. **Setup credentials**
```bash
# Tạo secrets.yml ở repo root (cùng cấp src/)
# Ví dụ tối giản:
# openai:
#   - api_key: sk-xxx
# gemini:
#   - api_key: AIza-xxx
# vertex:
#   - project_id: your-project
#     location: us-central1
#     access_token: ya29.xxx
```

4. **Cấu hình**
```bash
# Chỉnh sửa config.yml theo nhu cầu (nằm ngay trong thư mục job_2_translator)
```

## Sử dụng

### Chạy chương trình
```bash
python main.py
```

### Menu chính
```
1. Dịch thuật (Translate) - Dịch content + title (+ auto-retry lỗi)
2. Phân tích ngữ cảnh (Context) - Tạo context analysis
0. Thoát
```

### Workflow tiêu biểu

1. Dịch lần đầu:
   - Đặt YAML vào thư mục được chỉ định bởi `active_task.input_dir`
   - Chọn `1` (Translate)
   - Chương trình dịch cả content và (nếu bật) title

2. Retry tự động:
   - Diễn ra ngay trong workflow cho các segment lỗi tới `translate_api.max_retries`

3. Phân tích context:
   - Chọn `2` ở menu

## Cấu trúc Input YAML
```yaml
- id: Volume_1_Chapter_1_Segment_1
  title: 第一章 与女酒鬼共度一整晚
  content: |-
    中文内容...

    多个段落...
```

## Naming convention
- Log files: `ddmmyy_HHMM_SDK_filename.log`
- Output files: `ddmmyy_HHMM_SDK_filename.yaml`
- SDK codes: `gmn` (Gemini), `oai` (OpenAI), `vtx` (Vertex AI)

## config.yml (rút gọn ví dụ)
```yaml
active_task:
  task_name: "Dịch văn bản"
  input_dir: "file_input/volume_1"

translate_api:
  provider: gemini
  model: gemini-2.5-pro
  temperature: 1.3
  concurrent_requests: 10
  max_tokens: 12000
  thinking_budget: 2000
  delay: 45
  max_retries: 5


paths:
  output_trans: "file_output"
  log_trans: "inventory/logs/translator"
  context_dir: "inventory/context"
  prompt_file: "inventory/prompt/prompt.txt"
  title_prompt_file: "inventory/prompt/title_prompt.txt"
  context_prompt_file: "inventory/prompt/context_prompt.txt"

title_api:
  provider: gemini
  model: gemini-2.5-flash
  temperature: 1.3
  concurrent_requests: 20
  max_tokens: 100
  thinking_budget: 0
  delay: 0

title_translation:
  enabled: true

cleaner:
  enabled: true
  remove_thinking_blocks: true
```

## secrets.yml (đa-key hỗ trợ rotation)
```yaml
gemini:
  - api_key: AIza...
  - api_key: AIza...
openai:
  - api_key: sk-...
vertex:
  - project_id: your-project
    location: us-central1
    access_token: ya29....
```

## Content Cleaning
```yaml
cleaner:
  enabled: true
  remove_thinking_blocks: true
```

## Tips
- Giảm `concurrent_requests` nếu gặp rate limit.
- Tắt thinking bằng `thinking_budget: 0` khi không cần reasoning.
- Dùng nhiều key Gemini để phân tải.

## Troubleshooting nhanh
| Vấn đề | Giải pháp |
|--------|-----------|
| Không thấy secrets | Tạo `secret.yml` hoặc `secrets.yml` ở repo root |
| Rate limit | Giảm concurrent / tăng delay |
| Model lỗi | Đổi provider hoặc model khác |

## Ghi chú dọn dẹp
- Legacy `retry.py` đã được gỡ (stub còn lại sẽ bị xóa an toàn khi không còn import ngoài).
- Legacy `config.json` sẽ bị xóa (không còn sử dụng, thay bằng YAML).
