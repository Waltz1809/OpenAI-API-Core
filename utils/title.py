import yaml

# Bóc tiêu đề từ file YAML

def extract_unique_titles_to_txt(input_file, output_file):
    """
    Trích xuất các tiêu đề duy nhất từ các chương và lưu vào file TXT.
    """
    try:
        # Đọc file YAML
        with open(input_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Sử dụng set để đảm bảo tiêu đề duy nhất và giữ thứ tự theo file gốc
        unique_titles = []
        seen_titles = set()

        for segment in data:
            if 'title' in segment and segment['title'] and segment['title'] not in seen_titles:
                unique_titles.append(segment['title'])
                seen_titles.add(segment['title'])

        # Lưu tiêu đề vào file TXT
        with open(output_file, 'w', encoding='utf-8') as f:
            for title in unique_titles:
                f.write(title + "\n")

        print(f"Tiêu đề đã được trích xuất và lưu vào '{output_file}'.")
    except FileNotFoundError:
        print(f"Không tìm thấy file '{input_file}'. Hãy kiểm tra lại đường dẫn.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    print("--- Chương trình trích xuất tiêu đề từ YAML và lưu vào TXT ---")
    input_file = input("Nhập tên file YAML đầu vào (mặc định: content.yaml): ").strip() or "content.yaml"
    output_file = input("Nhập tên file TXT đầu ra (mặc định: title.txt): ").strip() or "title.txt"

    extract_unique_titles_to_txt(input_file, output_file)
