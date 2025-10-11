# 📚 Web Novel Crawler - Hướng Dẫn Sử Dụng

Tool crawl truyện web từ các trang tiểu thuyết trực tuyến với 2 phương thức chính.

## 🌐 Sites Hỗ Trợ

| Parser | Website | Mô tả |
|--------|---------|-------|
| `shuba` | www.69shuba.com | Trang truyện tiếng Trung chính |
| `piaotia` | www.piaotia.com | Trang truyện tiếng Trung |
| `quanben` | quanben.io | Trang truyện tiếng Trung |
| `czbooks` | czbooks.net | Trang truyện tiếng Trung |
| `dxmwx` | dxmwx.org | Trang truyện tiếng Trung |
| `zhswx` | tw.zhswx.com | Trang truyện tiếng Trung (TW) |
| `hjwzw` | tw.hjwzw.com | Trang truyện tiếng Trung (TW) |
| `tw` | tw.linovelib.com | Trang truyện tiếng Trung (TW) |

---

## 🚀 Phương Thức 1: JSON Mapping (Khuyến nghị)

### ✅ Ưu điểm
- 🛡️ **An toàn**: Không sợ site troll gắn link sai
- 🎯 **Chính xác**: Kiểm soát hoàn toàn danh sách chapters
- 📊 **Linh hoạt**: Có thể skip chapters không mong muốn

### ❌ Nhược điểm
- 🔧 **Phức tạp**: Cần chuẩn bị JSON mapping
- ⏱️ **Mất thời gian**: Phải tạo JSON từ HTML mục lục

### 📋 Các Bước Thực Hiện

#### Bước 1: Tạo JSON Mapping
1. Vào **mục lục chương** của truyện trên site hỗ trợ
2. **Ctrl + S** tải file HTML về
3. Đưa file HTML cho AI với prompt:

```
Đọc qua file HTML, trích xuất cho tôi 1 file JSON với 3 field index, title và url. Tuân thủ các quy tắc sau:

1. Index đếm từ 1
2. Tên title KHÔNG ĐƯỢC PHÉP dịch
3. Loại bỏ các title không rõ số chương, kiểu như thông báo hoặc chia sẻ cảm nghĩ
4. Vì những quy tắc 1 và 3 nên số index và số chương phải giống nhau. Có 614 chương, vì vậy có 614 index
5. Số index và tên title phải giống nhau. Ví dụ index là 2 thì title phải là 第2章. Nếu không thì đọc tiếp quy tắc số 6
6. Giả sử có index nào đó mà bạn ko tìm thấy title và url của nó, hãy đánh index đó nhưng title và url trống. Ví dụ bạn không thấy chương 45, thì khi này sẽ là:
   - index: 45
   - title: 
   - url: 
7. Lưu ý cho quy tắc 6: Nếu có 1 index không tìm thấy chương, thì index tiếp theo, tên title vẫn bắt buộc phải trùng với số index. Ví dụ index 45 không thấy, thì index tiếp theo phải là:
   - index: 46
   - title: 第46章
   - url: abc.com

Lưu ý: Tôi cần bạn đưa tôi file JSON chứ không phải viết code cho việc đấy. Tôi chỉ cần file JSON!
```

#### Bước 2: Cấu hình và Chạy
1. Đặt file JSON vào thư mục `test/python/crawl_json/`
2. Sửa file `test/python/crawl/config.json`:
   ```json
   {
     "series": [
       {
         "name": "Tên Truyện",
         "parser": "shuba",
         "json_mapping": "crawl_json/ten_file.json",
         "output_file": "output/ten_truyen.txt",
         "start_chapter": 1,
         "max_chapters": 10,
         "enabled": true
       }
     ],
     "settings": {
       "headless": false,
       "browser": "edge",
       "timeout": 30000,
       "delay_between_requests": 5,
       "max_retries": 3,
       "retry_delay": 10
     }
   }
   ```
3. Chạy crawler:
   ```bash
   cd test/python/crawl
   python unified_crawler.py
   ```

---

## ⚡ Phương Thức 2: Shuba Single (Nhanh gọn)

### ✅ Ưu điểm
- 🚀 **Nhanh gọn**: Chỉ cần URL chương đầu tiên
- 🎯 **Dễ dùng**: Không cần config phức tạp
- 🔄 **Tự động**: Tự động theo dõi next_url

### ❌ Nhược điểm
- ⚠️ **Rủi ro**: Site có thể troll gắn link sai
- 🛑 **Không kiểm soát**: Khó skip chapters không mong muốn

### 📋 Cách Sử Dụng

#### Command Line
```bash
cd test/python/crawl

# Crawl từ chương đầu tiên, không giới hạn
python shuba_single.py https://www.69shuba.com/txt/85122/39443144

# Crawl tối đa 10 chương
python shuba_single.py https://www.69shuba.com/txt/85122/39443144 10

# Crawl 10 chương, lưu vào file tùy chỉnh
python shuba_single.py https://www.69shuba.com/txt/85122/39443144 10 my_novel.txt
```

#### Python Script
```python
from shuba_single import ShubaSingleCrawler

# Tạo crawler
crawler = ShubaSingleCrawler("output.txt")

# Crawl từ chương đầu tiên
crawler.crawl_from_first_chapter(
    first_url="https://www.69shuba.com/txt/85122/39443144",
    max_chapters=10
)
```

---

## 🔧 Cài Đặt và Yêu Cầu

### Yêu Cầu Hệ Thống
- Python 3.7+
- Microsoft Edge Browser
- Windows 10/11

### Cài Đặt Dependencies
```bash
pip install playwright
playwright install msedge
```

---

## 📝 Lưu Ý Quan Trọng

### 🛡️ Bảo Mật
- Tool sử dụng **headless=False** để hiển thị browser (debug mode)
- Có thể gặp **CAPTCHA** ở lần đầu tiên - cần giải thủ công
- **Delay 3-5 giây** giữa các request để tránh bị block