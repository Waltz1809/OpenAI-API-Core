# Splitter - Công Cụ Tách Văn Bản

Công cụ tách văn bản thô thành segments phù hợp cho dịch thuật AI. Hỗ trợ 2 chế độ: Auto Splitter (khuyến nghị) và Manual Splitter.

## 🚀 Cách Sử Dụng

### Auto Splitter (Khuyến nghị)

Workflow tự động với cấu hình từ `config.json`:

```bash
cd splitter
python auto_splitter.py
```

**Tính năng:**
- ✅ Tự động scan và xử lý nhiều files
- ✅ Tracking files đã xử lý, skip files duplicate
- ✅ Hỗ trợ Light Novel & Web Novel với cấu hình riêng
- ✅ Dry run mode để preview trước khi thực thi
- ✅ Error logging chi tiết

### Manual Splitter

Tách thủ công từng file một:

```bash
cd splitter
python enhanced_chapter_splitter.py
```

## ⚙️ Cấu Hình

### config.json Structure

```json
{
  "input_base_dir": "test/source/raw_txt",
  "output_base_dir": "test/data/API_content",
  "tracking_file": "auto_splitter_history.json",
  
  "run_settings": {
    "dry_run": false,
    "auto_process_missing": false,
    "force_reprocess": false,
    "show_progress": true
  },
  
  "content_types": {
    "LightNovel": {
      "input_subdir": "LightNovel",
      "output_subdir": "LightNovel", 
      "segment_chars": 5000,
      "context_chars": 50000,
      "segment_suffix": "5k"
    },
    "WebNovel": {
      "input_subdir": "WebNovel",
      "output_subdir": "WebNovel",
      "segment_chars": 1500,
      "context_chars": 50000,
      "segment_suffix": "1k5"
    }
  },
  
  "modes": {
    "segment_mode": {
      "enabled": true,
      "mode": "1",
      "description": "Tách thành segments cho translation"
    },
    "context_mode": {
      "enabled": true,
      "suffix": "context",
      "mode": "1", 
      "description": "Tách theo chương để phân tích context"
    }
  }
}
```

### Giải Thích Cấu Hình

**Run Settings:**
- `dry_run`: `true` = chỉ preview, `false` = thực thi
- `auto_process_missing`: `true` = chỉ xử lý files thiếu (🆕), `false` = xử lý tất cả
- `force_reprocess`: `true` = xử lý lại tất cả files kể cả đã có

**Content Types:**
- `segment_chars`: Số ký tự tối đa cho mỗi segment dịch thuật
- `context_chars`: Số ký tự cho context analysis (thường lớn hơn)
- `segment_suffix`: Hậu tố để phân biệt loại content

**Modes:**
- `segment_mode`: Tách thành segments nhỏ cho translation
- `context_mode`: Tách theo chương cho context analysis

## 📁 Cấu Trúc Input/Output

### Input Structure
```
test/source/raw_txt/
├── LightNovel/
│   ├── series1/
│   │   └── volume1.txt
│   └── series2/
│       └── volume1.txt
└── WebNovel/
    ├── novel1/
    │   └── chapters.txt
    └── novel2/
        └── chapters.txt
```

### Output Structure
```
test/data/API_content/
├── LightNovel/
│   ├── series1/
│   │   ├── volume1_5k.yaml          # Segments cho translation
│   │   └── volume1_context.yaml     # Context analysis
│   └── series2/
│       ├── volume1_5k.yaml
│       └── volume1_context.yaml
└── WebNovel/
    ├── novel1/
    │   ├── chapters_1k5.yaml
    │   └── chapters_context.yaml
    └── novel2/
        ├── chapters_1k5.yaml
        └── chapters_context.yaml
```

## 📝 Format Input

### Định Dạng Văn Bản Đầu Vào

```
Quyển 1:
Chương 1: Tiêu đề chương 1
Nội dung chương 1...
Đoạn văn 1.

Đoạn văn 2.

Chương 2: Tiêu đề chương 2  
Nội dung chương 2...

Quyển 2:
Chương 1: Tiêu đề chương 1 quyển 2
Nội dung...
```

### Output YAML Format

**Segment Mode:**
```yaml
- id: "Volume_1_Chapter_1_Segment_1"
  title: "Chương 1: Tiêu đề chương 1"
  content: |-
    Nội dung segment 1...
    
    Đoạn văn trong segment.

- id: "Volume_1_Chapter_1_Segment_2"
  title: "Chương 1: Tiêu đề chương 1"
  content: |-
    Nội dung segment 2...
```

**Context Mode:**
```yaml
- id: "Volume_1_Chapter_1_Context"
  title: "Chương 1: Tiêu đề chương 1"
  content: |-
    Toàn bộ nội dung chương 1...
    (Không tách segments, giữ nguyên chương)
```

## 🔧 Tính Năng Nâng Cao

### Tracking System

Auto Splitter tự động track files đã xử lý trong `auto_splitter_history.json`:

```json
{
  "path/to/file.txt": {
    "segment_mode": {
      "processed": true,
      "output_path": "output/file_5k.yaml",
      "timestamp": "2024-01-01T12:00:00"
    },
    "context_mode": {
      "processed": true,
      "output_path": "output/file_context.yaml", 
      "timestamp": "2024-01-01T12:00:00"
    }
  }
}
```

### Filters

```json
"filters": {
  "include_folders": [],
  "exclude_folders": ["backup", "temp", ".git"],
  "file_patterns": ["*.txt"],
  "min_file_size_bytes": 100,
  "exclude_files": ["V20MMR2.txt"]
}
```

### Status Indicators

- 🆕 = File mới, sẽ được xử lý
- ✅ = File đã xử lý, skip
- ❌ = File có lỗi

## 🐛 Troubleshooting

### Lỗi Thường Gặp

**1. "Input directory not found"**
- Kiểm tra đường dẫn `input_base_dir` trong config.json
- Tạo thư mục input nếu chưa có

**2. "No files found to process"**
- Kiểm tra `file_patterns` trong filters
- Verify files có đúng extension không
- Kiểm tra `exclude_folders` có loại trừ thư mục cần thiết không

**3. "Permission denied"**
- Kiểm tra quyền write vào `output_base_dir`
- Chạy với quyền admin nếu cần

### Debug Tips

- Bật `dry_run: true` để preview trước khi thực thi
- Bật `show_progress: true` để xem tiến độ chi tiết
- Kiểm tra `auto_splitter_errors.log` nếu có lỗi
- Sử dụng `force_reprocess: true` để xử lý lại tất cả files

## 📊 Performance

### Khuyến Nghị Cấu Hình

**Light Novel:**
- `segment_chars`: 5000 (phù hợp cho GPT-4, Gemini)
- `context_chars`: 50000 (cho context analysis)

**Web Novel:**
- `segment_chars`: 1500 (ngắn hơn, phù hợp cho web novel)
- `context_chars`: 50000

### Tối Ưu Hóa

- Sử dụng Auto Splitter cho batch processing
- Enable tracking để tránh xử lý duplicate
- Sử dụng filters để loại trừ files không cần thiết
- Test với `dry_run` trước khi chạy production
