# Dịch CLI - Chương trình dịch thuật AI

Chương trình dịch thuật sử dụng AI APIs (OpenAI, Gemini, Vertex) với kiến trúc clean và đơn giản.

## Tính năng

- ✅ **Translate**: Dịch cả content và title trong 1 lần chạy
- ✅ **Retry**: Tự động dịch lại các segments thất bại  
- ✅ **Context Analysis**: Phân tích ngữ cảnh văn bản
- ✅ **Multi-provider**: Hỗ trợ OpenAI, Gemini, Vertex AI (tách riêng clients)
- ✅ **Smart logging**: Naming convention `ddmmyy_giờ_SDK_tên.log`
- ✅ **Progress reports**: Báo cáo tiến độ tự động
- ✅ **Threading**: Xử lý đồng thời để tăng tốc
- ✅ **Chapter filtering**: Lọc theo volume/chapter range

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
cp dich_cli/secret_template.json secrets.json
# Chỉnh sửa secrets.json với API keys của bạn
```

4. **Cấu hình**
```bash
# Chỉnh sửa config.json theo nhu cầu
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
1. Dịch thuật (Translate) - Dịch content + title
2. Dịch lại segments lỗi (Retry) - Sửa lỗi tự động  
3. Phân tích ngữ cảnh (Context) - Tạo context analysis
0. Thoát
```

### Workflow tiêu biểu

1. **Dịch lần đầu**:
   - Chọn `1` (Translate)
   - Chương trình dịch cả content và title
   - Kiểm tra log để xem segments thất bại

2. **Retry nếu có lỗi**:
   - Chọn `2` (Retry) 
   - Chương trình tự động tìm log mới nhất
   - Retry các segments thất bại và patch vào file gốc

3. **Phân tích context**:
   - Chọn `3` (Context Analysis)
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
├── secrets.json        # API credentials (gitignored)
└── dich_cli/           # Chương trình chính
    ├── config.json     # Cấu hình chính
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

### config.json structure
```json
{
  "active_task": {
    "task_name": "Tên tác vụ",
    "source_yaml_file": "đường/dẫn/input.yaml"
  },
  
  "translate_api": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "temperature": 0.7,
    "concurrent_requests": 5,
    "max_tokens": 4000,
    "thinking_budget": 0
  },
  
  "retry_api": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "concurrent_requests": 3,
    "max_tokens": 4000,
    "max_retries": 3
  },
  
  "context_api": {
    "provider": "vertex",
    "model": "gemini-2.5-flash", 
    "temperature": 0.5,
    "concurrent_requests": 3,
    "max_tokens": 1500,
    "thinking_budget": 0
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
}
```

### secrets.json structure (ở thư mục gốc)  
```json
{
  "openai_api_key": "sk-...",
  "openai_base_url": "https://api.openai.com/v1",
  "gemini_api_key": "AIza...",
  "vertex_project_id": "your-vertex-project",
  "vertex_location": "global"
}
```

### Provider Selection
Chỉ cần set field `provider` trong mỗi API config:
- **OpenAI**: `"provider": "openai"`
- **Gemini**: `"provider": "gemini"`
- **Vertex AI**: `"provider": "vertex"`

## Tính năng nâng cao

### Chapter Range Filtering
```json
"chapter_range": {
  "enabled": true,
  "start_volume": 1,
  "end_volume": 2, 
  "start_chapter": 5,
  "end_chapter": 10
}
```

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

1. **"File secrets.json không tồn tại"**
   - Copy `dich_cli/secret_template.json` thành `secrets.json` ở thư mục gốc
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
