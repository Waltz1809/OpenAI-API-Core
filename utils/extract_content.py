import os
import sys
from bs4 import BeautifulSoup
import re

# Bóc nội dung từ web linovelib

def extract_content(html_file_path, output_file_path=None):
    """
    Trích xuất tiêu đề và nội dung từ file HTML, loại bỏ các thẻ HTML.
    
    Args:
        html_file_path: Đường dẫn đến file HTML cần xử lý
        output_file_path: Đường dẫn để lưu nội dung đã trích xuất (mặc định là None, in ra console)
    
    Returns:
        Tuple (tiêu đề, nội dung)
    """
    # Đọc file HTML
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Parse HTML bằng BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Tìm thẻ div với id="mlfy_main_text"
    main_div = soup.find('div', id='mlfy_main_text')
    if not main_div:
        print("Không tìm thấy div với id='mlfy_main_text'")
        return None, None
    
    # Lấy tiêu đề từ thẻ h1
    title = main_div.find('h1').text.strip() if main_div.find('h1') else "Không có tiêu đề"
    
    # Lấy nội dung từ div id="TextContent"
    text_content_div = main_div.find('div', id='TextContent')
    if not text_content_div:
        print("Không tìm thấy div với id='TextContent'")
        return title, None
    
    # Lấy tất cả thẻ p trong TextContent
    paragraphs = text_content_div.find_all('p')
    content = "\n\n".join([p.text for p in paragraphs])
    
    # Nếu có đường dẫn output, lưu nội dung vào file
    if output_file_path:
        # Đảm bảo file xuất ra có đuôi .txt
        if not output_file_path.endswith('.txt'):
            output_file_path += '.txt'
            
        with open(output_file_path, 'w', encoding='utf-8') as out_file:
            out_file.write(f"{title}\n\n{content}")
        print(f"Đã lưu nội dung vào file {output_file_path}")
    else:
        print(f"Tiêu đề: {title}")
        print("\nNội dung:")
        print(content)
    
    return title, content

def main():
    # Sử dụng input để người dùng nhập đường dẫn
    print("Chương trình trích xuất nội dung từ file HTML")
    print("=============================================")
    
    # Nhập đường dẫn file HTML
    html_file_path = input("Nhập đường dẫn đến file HTML cần trích xuất: ").strip()
    
    # Kiểm tra file có tồn tại không
    if not os.path.exists(html_file_path):
        print(f"Lỗi: File {html_file_path} không tồn tại")
        return
    
    # Nhập tên file output (không cần đuôi .txt)
    output_filename = input("Nhập tên file xuất ra (để trống để hiển thị trên màn hình): ").strip()
    
    # Nếu người dùng không nhập gì thì output_file_path = None
    if output_filename == "":
        output_file_path = None
    else:
        # Thêm đuôi .txt vào tên file
        output_file_path = output_filename + ".txt"
    
    # Gọi hàm trích xuất nội dung
    extract_content(html_file_path, output_file_path)

if __name__ == "__main__":
    main() 