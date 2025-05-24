import yaml
import re
import os

# Cái này là để clean lại đoạn trả về. Vì dù đã có rule nhưng thi thoảng API vẫn trả về không theo format mà sẽ hơi lỗi tí.
# Kiểu: Em chào anh /n/n Anh chào em

# YAML Dumper tùy chỉnh để giữ định dạng đẹp
class CustomDumper(yaml.Dumper):
    def represent_scalar(self, tag, value, style=None):
        """Dùng '|' để đảm bảo văn bản giữ đúng định dạng xuống dòng"""
        if "\n" in value:
            style = "|"
        return super().represent_scalar(tag, value, style)

def clean_text(text):
    """Xử lý văn bản để đảm bảo không có khoảng trống thừa giữa các dòng, và cách dòng mỗi đoạn."""
    # Kiểm tra nếu text là None thì trả về chuỗi rỗng
    if text is None:
        return ""
    
    # Xóa các phần nằm giữa <think> và </think>
    lines = text.split("\n")
    filtered_lines = []
    in_thinking_block = False
    
    for line in lines:
        if line.strip().startswith("<think>"):
            in_thinking_block = True
            continue
        elif line.strip().startswith("</think>"):
            in_thinking_block = False
            continue
        
        if not in_thinking_block:
            filtered_lines.append(line)
    
    # Tiếp tục xử lý với danh sách dòng đã được lọc
    clean_lines = []
    
    for line in filtered_lines:
        # Loại bỏ khoảng trắng dư thừa nhưng giữ nguyên xuống dòng
        clean_line = " ".join(line.split())  # Xóa khoảng trắng thừa trong dòng
        if clean_line:  # Chỉ thêm dòng nếu không bị rỗng
            clean_lines.append(clean_line)
            clean_lines.append("")  # Thêm dòng trống sau mỗi dòng thực tế

    return "\n".join(clean_lines).strip()  # Giữ đúng xuống dòng thực tế, loại bỏ dòng trống cuối

def process_yaml(input_file, output_file):
    """Xử lý file YAML để giữ đúng format nội dung."""
    try:
        # Đảm bảo thư mục đầu ra tồn tại
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        with open(input_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        for segment in data:
            if 'content' in segment:
                segment['content'] = clean_text(segment['content'])

        # Lưu lại file YAML sau khi xử lý
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, Dumper=CustomDumper)

        print(f"File '{output_file}' đã được xử lý và lưu thành công.")
    except FileNotFoundError:
        print(f"Không tìm thấy file '{input_file}'. Hãy kiểm tra lại.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    print("--- Chương trình làm sạch file YAML ---")
    input_file = input("Nhập tên file YAML đầu vào: ").strip()
    output_prefix = input("Nhập tên file YAML đầu ra (không cần hậu tố): ").strip()
    
    # Hỏi đường dẫn thư mục lưu file
    output_dir = input("Nhập đường dẫn thư mục lưu file (mặc định là thư mục hiện tại, nhấn Enter để dùng giá trị mặc định): ").strip() or "."
    
    # Tạo đường dẫn đầy đủ
    if output_dir != ".":
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = os.path.join(output_dir, f"{output_prefix}_edit.yaml")
    else:
        output_file = f"{output_prefix}_edit.yaml"
    
    print(f"File sẽ được lưu tại: {os.path.abspath(output_file)}")
    process_yaml(input_file, output_file)
