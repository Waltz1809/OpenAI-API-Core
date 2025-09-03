# OpenAI API Core - Bộ Công Cụ Dịch Thuật AI

Bộ công cụ Python hoàn chỉnh cho việc dịch thuật và xử lý văn bản sử dụng AI APIs (OpenAI, Gemini, Vertex AI).

## 📁 Cấu Trúc Project

| Chương trình | Mô tả | README |
|-------------|-------|---------|
| **dich_cli** | 🎯 Chương trình dịch thuật chính (CLI) | [📖 README](dich_cli/README.md) |
| **AUTO** | 🚀 Tool tự động upload lên website | [📖 README](AUTO/README.md) |
| **splitter** | ✂️ Công cụ tách văn bản thành segments | [📖 README](splitter/README.md) |
| **utils** | 🛠️ Các tiện ích hỗ trợ | [📖 README](utils/README.md) |

## 🚀 Quick Start

### 1. Cài đặt dependencies
```bash
pip install openai google-genai pyyaml playwright cn2an
playwright install  # Cho AUTO tool
```

### 2. Cấu hình API keys
Tạo file `secrets.json` ở thư mục gốc:
```json
{
    "openai_keys": [{"api_key": "sk-...", "base_url": "https://api.openai.com/v1"}],
    "gemini_keys": [{"api_key": "AIza..."}],
    "vertex_keys": [{"project_id": "your-project", "location": "global"}]
}
```

### 3. Workflow cơ bản
```bash
# 1. Tách văn bản
cd splitter && python auto_splitter.py

# 2. Dịch thuật
cd dich_cli && python main.py

# 3. Upload (tùy chọn)
cd AUTO && python main.py
```

## 📖 Chi Tiết

Xem README trong từng thư mục để biết hướng dẫn chi tiết:
- [dich_cli/README.md](dich_cli/README.md) - Hướng dẫn dịch thuật
- [AUTO/README.md](AUTO/README.md) - Hướng dẫn upload tự động
- [splitter/README.md](splitter/README.md) - Hướng dẫn tách văn bản
- [utils/README.md](utils/README.md) - Các tiện ích hỗ trợ



