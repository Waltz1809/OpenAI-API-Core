# Utils - Tiện Ích Hỗ Trợ

Bộ công cụ tiện ích hỗ trợ cho việc xử lý văn bản, làm sạch dữ liệu và phân tích ngữ cảnh.

## 🛠️ Các Công Cụ

### 1. clean_segment.py - Làm Sạch YAML

Làm sạch file YAML đã dịch, xóa thinking blocks và format lại nội dung.

**Cách sử dụng:**
```bash
cd utils
python clean_segment.py
```

**Tính năng:**
- ✅ Xóa `<think>...</think>` blocks khỏi content
- ✅ Loại bỏ khoảng trắng thừa
- ✅ Giữ nguyên format xuống dòng
- ✅ Tự động tạo thư mục output

**Input/Output:**
```
Input:  original.yaml
Output: original_edit.yaml
```

### 2. yaml_to_txt_converter.py - Chuyển Đổi YAML sang TXT

Chuyển đổi file YAML đã dịch về format TXT để đọc hoặc xuất bản.

**Cách sử dụng:**
```bash
cd utils
python yaml_to_txt_converter.py
```

**Tính năng:**
- ✅ Nhóm segments theo Volume và Chapter
- ✅ Tự động sắp xếp theo thứ tự
- ✅ Tạo file TXT riêng cho mỗi chương
- ✅ Format chuẩn cho xuất bản

**Output Structure:**
```
output/
├── Quyen_1_Chuong_1.txt
├── Quyen_1_Chuong_2.txt
├── Quyen_2_Chuong_1.txt
└── ...
```

**Format Output:**
```
Quyển 1 - Chương 1: Tiêu đề chương

Nội dung segment 1...

Nội dung segment 2...
```
