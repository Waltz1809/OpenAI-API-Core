# Dịch CLI - Chương Trình Dịch Thuật AI

Chương trình dịch thuật chính với giao diện CLI, hỗ trợ đa provider AI (OpenAI, Gemini, Vertex AI) với kiến trúc clean và hiệu suất cao.

## ✨ Tính Năng Chính

- 🎯 **Translate**: Dịch cả content và title trong 1 lần chạy
- 🔄 **Retry**: Tự động dịch lại các segments thất bại
- 📊 **Context Analysis**: Phân tích ngữ cảnh văn bản
- 🤖 **Multi-provider**: Hỗ trợ OpenAI, Gemini, Vertex AI với clients riêng biệt
- 📝 **Smart Logging**: Naming convention `ddmmyy_HHMM_SDK_filename.log`
- 📈 **Progress Reports**: Báo cáo tiến độ tự động và chi tiết
- ⚡ **Threading**: Xử lý đồng thời để tăng tốc độ
- 🎛️ **Chapter Filtering**: Lọc theo volume/chapter range
- 🔑 **Multi-Key Support**: Load balancing với nhiều API keys
- 🧹 **Auto Cleaning**: Tự động xóa thinking blocks

## 🚀 Cài Đặt & Setup

### 1. Dependencies
```bash
# Cài đặt các thư viện cần thiết
pip install openai google-genai pyyaml
```

### 2. API Credentials
Tạo file `secrets.json` ở **thư mục gốc project** (không phải trong dich_cli/):

```json
{
    "openai_keys": [
        {
            "api_key": "sk-your-openai-key",
            "base_url": "https://api.openai.com/v1"
        }
    ],
    "gemini_keys": [
        {
            "api_key": "AIza-your-gemini-key"
        },
        {
            "api_key": "AIza-another-key"
        }
    ],
    "vertex_keys": [
        {
            "project_id": "your-vertex-project",
            "location": "global"
        }
    ]
}
```

> **Lưu ý**: File `secrets.json` đã được git ignore để bảo mật API keys.

### 3. Cấu Hình
Chỉnh sửa `dich_cli/config.json` theo nhu cầu:
- Đường dẫn file input YAML
- Model settings cho từng workflow
- Output directories
- Provider selection

## 🎮 Sử Dụng

### Chạy Chương Trình
```bash
cd dich_cli
python main.py
```

### Menu Chính
```
=== DỊCH THUẬT AI CLI ===
1. 🎯 Dịch thuật (Translate) - Dịch content + title
2. 🔄 Dịch lại segments lỗi (Retry) - Sửa lỗi tự động
3. 📊 Phân tích ngữ cảnh (Context) - Tạo context analysis
0. ❌ Thoát

Chọn chức năng (0-3):
```

### 📋 Workflow Tiêu Biểu

#### 1. Dịch Lần Đầu (Translate)
```bash
# Chọn 1 trong menu
1. Dịch thuật (Translate)

# Chương trình sẽ:
✅ Đọc file YAML từ config
✅ Dịch cả content và title
✅ Tạo file output với timestamp
✅ Ghi log chi tiết các segments
✅ Tạo progress report
```

#### 2. Retry Segments Lỗi
```bash
# Chọn 2 trong menu
2. Dịch lại segments lỗi (Retry)

# Chương trình sẽ:
✅ Tự động tìm log file mới nhất
✅ Parse các segments thất bại
✅ Retry với API settings riêng
✅ Patch kết quả vào file gốc
✅ Update progress report
```

#### 3. Context Analysis
```bash
# Chọn 3 trong menu
3. Phân tích ngữ cảnh (Context)

# Chương trình sẽ:
✅ Phân tích ngữ cảnh từng chương
✅ Tạo context summary
✅ Lưu vào thư mục context/
✅ Hỗ trợ cho dịch thuật chính xác hơn
```

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
