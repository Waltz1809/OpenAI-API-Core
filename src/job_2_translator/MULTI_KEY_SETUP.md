# Multi-Key Configuration Example
# Ví dụ cách config multiple API keys cho Dich CLI

## secrets.yml format (supports both single and multiple keys)

### Option 1: Single key per provider
```yaml
openai_api_key: sk-your-openai-key
openai_base_url: https://api.openai.com/v1
gemini_api_key: AIza-your-gemini-key
vertex_project_id: your-vertex-project
vertex_location: global
```

### Option 2: Multiple keys per provider (round-robin)
```yaml
openai_keys:
    - api_key: sk-project1-key
        base_url: https://api.openai.com/v1
    - api_key: sk-project2-key
        base_url: https://api.openai.com/v1
    - api_key: sk-deepseek-key
        base_url: https://api.deepseek.com/v1

gemini_keys:
    - api_key: AIza-project1-key
    - api_key: AIza-project2-key
    - api_key: AIza-project3-key

vertex_keys:
    - project_id: my-vertex-project1
        location: global
    - project_id: my-vertex-project2
        location: us-central1
```

### Option 3: Mixed format (single + multi) vẫn hỗ trợ
```yaml
openai_keys:
    - api_key: sk-key1
        base_url: https://api.openai.com/v1
    - api_key: sk-key2
        base_url: https://api.deepseek.com/v1
gemini_api_key: AIza-single-key
vertex_project_id: single-vertex-project
vertex_location: global
```

## Lợi ích của Multi-Key Setup

1. **Tăng throughput**: 3 keys = 3x requests/minute
2. **Tận dụng free tier**: Mỗi GCP project có quota riêng
3. **Load balancing**: Requests được phân bổ đều
4. **Fault tolerance**: Key nào lỗi thì dùng key khác

## Cách hoạt động

- **Round-robin rotation**: Key1 → Key2 → Key3 → Key1...
- **Thread-safe**: Mỗi thread lấy key khác nhau
- **Automatic fallback**: Tự động dùng legacy format nếu không có multi-key
- **No tracking**: Không cần phức tạp về quota, chỉ xoay vòng đơn giản

## Log output mẫu

```
🔧 SDK: OAI
🤖 Content Model: deepseek-reasoner
🔑 Content Keys: 3 keys (round-robin)
🏷️ Title Model: deepseek-chat (OAI)
🔑 Title Keys: 3 keys (round-robin)
```

## Setup cho từng provider

### Google Gemini (miễn phí)
1. Tạo nhiều projects trên Google Cloud Console
2. Enable Generative AI API cho mỗi project  
3. Tạo API key cho mỗi project
4. Mỗi project có 15 requests/minute free

### OpenAI/DeepSeek
1. Tạo nhiều projects/accounts
2. Lấy API key cho mỗi account
3. Config base_url khác nhau nếu cần

### Vertex AI
1. Tạo nhiều GCP projects
2. Enable Vertex AI API
3. Setup authentication cho mỗi project