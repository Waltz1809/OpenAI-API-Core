# Dịch CLI - Chương trình dịch thuật AI

Chương trình dịch thuật sử dụng AI APIs (OpenAI, Gemini, Vertex) với kiến trúc clean và đơn giản.

## Tính năng

- ✅ **Translate**: Dịch cả content và title trong 1 lần chạy
- ✅ **Auto-Retry tích hợp**: Tự động thử lại segments lỗi sau dịch  
- ✅ **Context Analysis**: Phân tích ngữ cảnh văn bản
- ✅ **Multi-provider**: Hỗ trợ OpenAI, Gemini, Vertex AI (tách riêng clients)
- ✅ **Smart logging**: Naming convention `ddmmyy_giờ_SDK_tên.log`
- ✅ **Progress reports**: Báo cáo tiến độ tự động
- ✅ **Threading**: Xử lý đồng thời để tăng tốc
<!-- Chapter filtering removed -->

## Cài đặt

1. **Clone repository**
```bash
git clone <repo_url>
cd dich_cli
```

2. **Cài đặt dependencies**
```bash
pip install openai google-genai pyyaml
```

3. **Setup credentials**
```bash
# Copy template từ dich_cli/ lên thư mục gốc và điền API keys
cp dich_cli/secret_template.yml secrets.yml
# Chỉnh sửa secrets.yml với API keys của bạn
```

4. **Cấu hình**
```bash
# Chỉnh sửa config.yml theo nhu cầu
# - Đường dẫn file input
# - Model settings cho từng workflow
# - Output directories
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

1. **Dịch lần đầu**:
   - Chọn `1` (Translate)
   - Chương trình dịch cả content và title
   - Kiểm tra log để xem segments thất bại

2. **Retry tự động**:
  - Sau khi dịch xong, các segments lỗi sẽ được retry ngay trong cùng workflow
  - Điều chỉnh số lần bằng `translate_api.max_retries`

3. **Phân tích context**:
  - Chọn `2` ở menu
  - Tạo file phân tích ngữ cảnh riêng

## Cấu trúc file

### Input YAML format
```yaml
- id: Volume_1_Chapter_1_Segment_1
  title: 第一章 与女酒鬼共度一整晚  
  content: |-
    中文内容...
    
    多个段落...
```

### Output structure
```
Dich/                   # Thư mục gốc  
├── secrets.yml         # API credentials (gitignored)
└── dich_cli/           # Chương trình chính
  ├── config.yml      # Cấu hình chính (YAML)
    ├── core/           # Core modules
    │   ├── openai_client.py   # OpenAI client
    │   ├── gemini_client.py   # Gemini client  
    │   ├── vertex_client.py   # Vertex AI client
    │   ├── ai_factory.py      # Client factory
    │   ├── yaml_processor.py  # YAML handler
    │   └── logger.py          # Smart logger
    ├── workflows/      # Workflow implementations
    ├── output/
    │   ├── translation/ # File dịch
    │   └── context/     # File phân tích context + log
    ├── logs/
    │   └── translation/ # Log dịch thuật  
    └── reports/        # Báo cáo tiến độ
```

### Naming convention
- **Log files**: `ddmmyy_HHMM_SDK_filename.log`
- **Output files**: `ddmmyy_HHMM_SDK_filename.yaml`
- **SDK codes**: `gmn` (Gemini), `oai` (OpenAI), `vtx` (Vertex AI)

## Cấu hình

### config.yml structure
```yaml
active_task:
  task_name: "Tên tác vụ"
  source_yaml_file: "đường/dẫn/input.yaml"

translate_api:
  provider: gemini
  model: gemini-2.5-flash
  temperature: 0.7
  concurrent_requests: 5
  max_tokens: 4000
  thinking_budget: 0
  max_retries: 2
  delay: 3

context_api:
  provider: vertex
  model: gemini-2.5-flash
  temperature: 0.5
  concurrent_requests: 3
  max_tokens: 1500
  thinking_budget: 0

title_api:
  provider: gemini
  model: gemini-2.5-flash
  temperature: 0.5
  concurrent_requests: 2
  max_tokens: 50
  thinking_budget: 0
  delay: 3
```

### secrets.yml structure (ở thư mục gốc)  
```yaml
openai_api_key: "sk-..."
openai_base_url: "https://api.openai.com/v1"
gemini_api_key: "AIza..."
vertex_project_id: "your-vertex-project"
vertex_location: "global"
```

### Provider Selection
Chỉ cần set field `provider` trong mỗi API config:
- **OpenAI**: `"provider": "openai"`
- **Gemini**: `"provider": "gemini"`
- **Vertex AI**: `"provider": "vertex"`

## Tính năng nâng cao

### Title Translation
```json
"title_translation": {
  "enabled": true
},

"title_api": {
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "temperature": 0.5,
  "concurrent_requests": 2,
  "max_tokens": 50,
  "thinking_budget": 0,
  "delay": 3
}
```

**Lưu ý**: Title có API config riêng để tối ưu token và tránh thinking thừa thãi.

### Content Cleaning
```json  
"cleaner": {
  "enabled": true,
  "remove_thinking_blocks": true
}
```

## Troubleshooting

### Lỗi thường gặp

1. **"File secrets.yml không tồn tại"**
  - Copy `dich_cli/secret_template.yml` thành `secrets.yml` ở thư mục gốc
  - Điền đúng API keys

2. **"Prompt bị chặn"**
   - Đối với Gemini: Safety settings đã được tắt hết
   - Thử model khác hoặc provider khác

3. **Rate limit**
   - Giảm `concurrent_requests` trong config
   - Tăng `delay` giữa các requests

4. **Thinking budget lỗi**
   - Chỉ có Gemini 2.5 series hỗ trợ
   - Set `thinking_budget: 0` để tắt

### Performance tips

- Gemini 2.5-flash: Nhanh, rẻ, chất lượng tốt
- OpenAI GPT-4o-mini: Backup tốt cho retry
- Concurrent requests: 3-5 cho Gemini, 5-10 cho OpenAI
- Thinking budget: 0 (tắt) để tiết kiệm token

## Support

Nếu gặp vấn đề, kiểm tra:
1. File log chi tiết trong `logs/`
2. Báo cáo tiến độ trong `reports/`
3. Config và secret files đúng format
