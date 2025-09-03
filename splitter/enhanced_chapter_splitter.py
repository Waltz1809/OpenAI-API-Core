import re
import yaml
import cn2an
import os

class CustomDumper(yaml.Dumper):
    def represent_scalar(self, tag, value, style=None):
        if tag == 'tag:yaml.org,2002:str' and "\n" in value:
            style = '|'
        return super().represent_scalar(tag, value, style)

# Hàm riêng để xử lý chuỗi đa dòng
def represent_multiline_string(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

def convert_chinese_number_to_arabic(chinese_number):
    """Chuyển đổi số Hán tự sang số Ả Rập."""
    try:
        return cn2an.cn2an(chinese_number, mode="smart")
    except ValueError:
        return None

def is_valid_chapter_number(chapter_number, previous_chapter, max_chapter):
    """Kiểm tra số chương hợp lệ."""
    if chapter_number is None:
        return False
    if chapter_number < 0 or chapter_number > max_chapter:
        return False
    if previous_chapter is None or chapter_number == previous_chapter + 1 or chapter_number == 1:
        return True
    return False

def get_output_filename(input_file, user_output, output_format, output_dir):
    """Xác định tên file đầu ra với logic thông minh tránh trùng lặp suffix."""
    # Đảm bảo thư mục tồn tại
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    if not user_output.strip():
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        # Kiểm tra xem base_name đã có suffix tương tự chưa
        # Danh sách các suffix cần kiểm tra
        similar_suffixes = ['_split', '_seg', '_segment', '_chapter', '_divided']
        
        # Kiểm tra xem tên file có kết thúc bằng suffix tương tự không
        has_similar_suffix = any(base_name.endswith(suffix) for suffix in similar_suffixes)
        
        if has_similar_suffix:
            # Nếu đã có suffix tương tự, không thêm _split nữa
            return os.path.join(output_dir, f"{base_name}.{output_format}")
        else:
            # Nếu chưa có suffix, thêm _split
            return os.path.join(output_dir, f"{base_name}_split.{output_format}")
    
    # Nếu user_output đã bao gồm đường dẫn đầy đủ, sử dụng nó trực tiếp
    if os.path.dirname(user_output):
        if not user_output.endswith(f'.{output_format}'):
            return f"{user_output}.{output_format}"
        return user_output
        
    # Nếu user_output chỉ là tên file, thêm đường dẫn thư mục
    if not user_output.endswith(f'.{output_format}'):
        return os.path.join(output_dir, f"{user_output}.{output_format}")
    return os.path.join(output_dir, user_output)

def remove_bom(text):
    """Loại bỏ BOM từ chuỗi văn bản."""
    if text.startswith('\ufeff'):
        return text[1:]
    return text

def detect_special_section(line):
    """Nhận diện các phần đặc biệt như lời mở đầu, lời kết, v.v."""
    # Loại bỏ BOM nếu có
    line = remove_bom(line)
    
    # Các pattern nhận diện phần đặc biệt
    epilogue_match = re.match(r'^(后记|後記)', line)
    foreword_match = re.match(r'^(前言|绪言|引言|序言)', line)
    final_chapter_match = re.match(r'^(终章|終章|尾声)', line)
    
    # Các định dạng mới từ người dùng
    prologue_maku_match = re.match(r'^(序幕／.*)$', line)
    if prologue_maku_match:
        return "prologue", prologue_maku_match.group(1).strip()
        
    final_maku_match = re.match(r'^(終幕／.*)$', line)
    if final_maku_match:
        return "final_chapter", final_maku_match.group(1).strip()
        
    interlude_match = re.match(r'^(里幕|幕间|幕間|特典|短篇|解說|断章|闲谈)', line)
    if interlude_match:
        return "interlude", line.strip()

    # Các pattern cho tiếng Anh
    prologue_match_en = re.match(r'^(Prologue)([:\s].*)?$', line, re.IGNORECASE)
    if prologue_match_en:
        return "prologue", line.strip()

    epilogue_match_en = re.match(r'^(Epilogue)([:\s].*)?$', line, re.IGNORECASE)
    if epilogue_match_en:
        return "epilogue", line.strip()

    interlude_match_en = re.match(r'^(Interlude)([:\s].*)?$', line, re.IGNORECASE)
    if interlude_match_en:
        return "interlude", line.strip()

    # Kiểm tra xem line có bắt đầu bằng "序章" không
    if line.startswith("序章"):
        # Cố gắng trích xuất nội dung trong dấu ngoặc
        match = re.search(r'序章[「『](.+?)[」』]', line)
        if match:
            return "prologue", f"序章: {match.group(1)}"
        else:
            return "prologue", "序章"
    elif epilogue_match:
        return "epilogue", line.strip()
    elif foreword_match:
        return "foreword", line.strip()
    elif final_chapter_match:
        # Xử lý chương kết (终章)
        # Cố gắng trích xuất nội dung trong dấu ngoặc nếu có
        match = re.search(r'终章[「『](.+?)[」』]', line)
        if match:
            return "final_chapter", f"终章: {match.group(1)}"
        else:
            return "final_chapter", "终章"
    
    return None, None

def detect_volume(line):
    """Nhận diện quyển (卷/quyển/volume/tập) và trả về số quyển và tiêu đề."""
    # Loại bỏ BOM nếu có
    line = remove_bom(line)
    
    # Các pattern nhận diện quyển trong tiếng Trung
    match_chinese = re.match(r'^第([零一二三四五六七八九十百千]+)卷\s*(.+)?', line)
    match_arabic = re.match(r'^第(\d{1,3})卷\s*(.+)?', line)
    
    # Pattern cho tiếng Việt
    match_vietnamese_quyen = re.match(r'^[Qq]uyển\s*(\d{1,3})[.:]?\s*(.*)$', line)
    match_vietnamese_tap = re.match(r'^[Tt]ập\s*(\d{1,3})[.:]?\s*(.*)$', line)
    
    # Pattern cho tiếng Anh
    match_english = re.match(r'^[Vv]olume\s*(\d{1,3})[.:]?\s*(.*)$', line)
    match_english_vol = re.match(r'^[Vv]ol\s*\.?\s*(\d{1,3})[.:]?\s*(.*)$', line)
    match_english_book = re.match(r'^[Bb]ook\s*(\d{1,3})[.:]?\s*(.*)$', line)
    
    # Pattern bắt dòng đơn giản chỉ có dấu ":" như "Quyển 6:"
    match_simple = re.match(r'^[Qq]uyển\s*(\d{1,3})\s*:$', line)
    
    volume_number = None
    title = None
    
    if match_chinese:
        volume_number = convert_chinese_number_to_arabic(match_chinese.group(1))
        title = match_chinese.group(0)
        if match_chinese.group(2):
            title = f"第{match_chinese.group(1)}卷 {match_chinese.group(2).strip()}"
    elif match_arabic:
        volume_number = int(match_arabic.group(1))
        title = match_arabic.group(0)
        if match_arabic.group(2):
            title = f"第{match_arabic.group(1)}卷 {match_arabic.group(2).strip()}"
    elif match_vietnamese_quyen:
        volume_number = int(match_vietnamese_quyen.group(1))
        title = f"Quyển {volume_number}"
        if match_vietnamese_quyen.group(2):
            title = f"Quyển {volume_number}: {match_vietnamese_quyen.group(2).strip()}"
    elif match_vietnamese_tap:
        volume_number = int(match_vietnamese_tap.group(1))
        title = f"Tập {volume_number}"
        if match_vietnamese_tap.group(2):
            title = f"Tập {volume_number}: {match_vietnamese_tap.group(2).strip()}"
    elif match_english:
        volume_number = int(match_english.group(1))
        title = f"Volume {volume_number}"
        if match_english.group(2):
            title = f"Volume {volume_number}: {match_english.group(2).strip()}"
    elif match_english_vol:
        volume_number = int(match_english_vol.group(1))
        title = f"Vol {volume_number}"
        if match_english_vol.group(2):
            title = f"Vol {volume_number}: {match_english_vol.group(2).strip()}"
    elif match_english_book:
        volume_number = int(match_english_book.group(1))
        title = f"Book {volume_number}"
        if match_english_book.group(2):
            title = f"Book {volume_number}: {match_english_book.group(2).strip()}"
    elif match_simple:
        volume_number = int(match_simple.group(1))
        title = f"Quyển {volume_number}"
    
    # Kiểm tra đặc biệt cho dòng đơn giản như "Quyển 6"
    if volume_number is None:
        simple_match = re.match(r'^[Qq]uyển\s*(\d{1,3})$', line)
        if simple_match:
            volume_number = int(simple_match.group(1))
            title = f"Quyển {volume_number}"
    
    return volume_number, title

def detect_chapter_title(line, max_chapter, previous_chapter_number):
    """Nhận diện tiêu đề chương và trả về số chương và tiêu đề."""
    # Loại bỏ BOM nếu có
    line = remove_bom(line)
    
    # Các pattern nhận diện tiêu đề chương, được đơn giản hóa để chỉ lấy số chương
    match_chinese = re.match(r'^第([零一二三四五六七八九十百千]+)章', line)
    match_arabic = re.match(r'^第(\d{1,3})章', line)
    match_vietnamese = re.match(r'^[Cc]hương\s*(\d{1,3})', line, re.IGNORECASE)
    match_chap = re.match(r'^[Cc]hapter\s*(\d{1,3})', line, re.IGNORECASE)
    match_chinese_hua = re.match(r'^第([零一二三四五六七八九十百千]+)话', line)
    match_arabic_hua = re.match(r'^第(\d{1,3})话', line)
    match_chinese_maku = re.match(r'^第([零一二三四五六七八九十百千]+)幕', line)
    match_arabic_maku = re.match(r'^第(\d{1,3})幕', line)

    chapter_number = None
    title = line.strip() # SỬA: Luôn lấy cả dòng làm tiêu đề để đảm bảo chính xác

    if match_chinese:
        chapter_number = convert_chinese_number_to_arabic(match_chinese.group(1))
    elif match_arabic:
        chapter_number = int(match_arabic.group(1))
    elif match_vietnamese:
        chapter_number = int(match_vietnamese.group(1))
    elif match_chap:
        chapter_number = int(match_chap.group(1))
    elif match_chinese_hua:
        chapter_number = convert_chinese_number_to_arabic(match_chinese_hua.group(1))
    elif match_arabic_hua:
        chapter_number = int(match_arabic_hua.group(1))
    elif match_chinese_maku:
        chapter_number = convert_chinese_number_to_arabic(match_chinese_maku.group(1))
    elif match_arabic_maku:
        chapter_number = int(match_arabic_maku.group(1))

    # Kiểm tra số chương có hợp lệ không
    if chapter_number is not None and is_valid_chapter_number(chapter_number, previous_chapter_number, max_chapter):
        return chapter_number, title # Trả về cả dòng đã được làm sạch
    return None, None

def split_content(file_path, max_chapter):
    """Tách file thành các chương, phần nhỏ và phần đặc biệt."""
    # Thử mở file với các mã hóa phổ biến để xử lý lỗi Unicode
    encodings_to_try = ['utf-16', 'utf-8', 'utf-8-sig', 'gbk', 'big5']
    content = None
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            print(f"✅ Đọc file thành công với mã hóa: {encoding}")
            break  # Thoát khỏi vòng lặp nếu đọc thành công
        except (UnicodeDecodeError, UnicodeError):
            print(f"⚠️  Thử mã hóa '{encoding}' thất bại, đang thử mã hóa tiếp theo...")
            continue  # Thử mã hóa tiếp theo
    
    if content is None:
        print(f"❌ Lỗi nghiêm trọng: Không thể đọc file '{file_path}' với bất kỳ mã hóa nào được hỗ trợ.")
        return []

    # Giờ chia thành các dòng để xử lý
    lines = content.splitlines()

    sections = []
    current_section = []
    previous_chapter_number = None
    seen_chapters = set()
    current_chapter_number = None
    current_section_id = None
    current_volume_number = None
    current_chapter_title = None
    current_chapter_for_segment = 0  # Số chương hiện tại để đánh ID segment
    has_final_chapter = False  # Biến để theo dõi nếu đã gặp chương kết
    
    # Biến để theo dõi số chương lớn nhất cho mỗi quyển
    max_chapter_by_volume = {}
    interlude_counter_by_volume = {}
    final_chapter_counter_by_volume = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Nhận diện phần đặc biệt (lời mở đầu, lời kết, v.v.)
        special_id, special_title = detect_special_section(line)
        
        # Nhận diện quyển
        volume_number, volume_title = detect_volume(line)
        
        # Nhận diện tiêu đề chương
        chapter_number, chapter_title = detect_chapter_title(line, max_chapter, previous_chapter_number)

        # Xử lý phần đặc biệt
        if special_id:
            # Trường hợp đặc biệt: nếu dòng này bắt đầu bằng "第X卷" và chứa "序章", 
            # và chưa xử lý volume, thì ưu tiên xử lý volume trước
            if "序章" in line and volume_number is None and "第" in line and "卷" in line:
                # Lấy phần volume từ đầu dòng đến trước "序章"
                volume_part = line.split("序章")[0].strip()
                if re.match(r'^第([零一二三四五六七八九十百千]+)卷', volume_part) or re.match(r'^第(\d{1,3})卷', volume_part):
                    volume_number, volume_title = detect_volume(volume_part)
                    if volume_number and current_section:
                        sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                        current_section = []
                    
                    if volume_number:
                        current_section_id = f"Volume_{volume_number}"
                        current_volume_number = volume_number
                        current_chapter_number = None
                        current_chapter_title = volume_title
                        current_section.append(volume_title)
                        
                        # Lấy phần prologue
                        prologue_part = line[len(volume_part):].strip()
                        if prologue_part:
                            sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                            current_section = []
                            
                            # Đặt ID có cả volume và prologue
                            if current_volume_number:
                                current_section_id = f"Volume_{current_volume_number}_Chapter_0"
                            else:
                                current_section_id = "Chapter_0"
                                
                            current_chapter_for_segment = 0
                            match = re.search(r'序章[「『](.+?)[」』]', prologue_part)
                            if match:
                                special_title = f"序章: {match.group(1)}"
                            else:
                                special_title = "序章"
                            current_chapter_title = special_title
                            current_section.append(special_title)
                        i += 1
                        continue
            
            # Xử lý prologue và các phần đặc biệt khác
            if current_section:
                sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                current_section = []

            # Đặt ID có cả volume và prologue nếu đang trong một volume
            if special_id == "prologue":
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_0"
                else:
                    current_section_id = "Chapter_0"
                current_chapter_for_segment = 0
            elif special_id == "final_chapter":
                # Xử lý nhiều final_chapter bằng cách sử dụng bộ đếm
                volume_key = current_volume_number or 0
                max_chapter_in_volume = max_chapter_by_volume.get(volume_key, 0)
                
                # Lấy và cập nhật bộ đếm final_chapter cho quyển hiện tại
                final_chapter_count = final_chapter_counter_by_volume.get(volume_key, 0)
                final_chapter_num = max_chapter_in_volume + 1 + final_chapter_count
                final_chapter_counter_by_volume[volume_key] = final_chapter_count + 1
                
                # Đặt ID có cả volume và final_chapter
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_{final_chapter_num}"
                else:
                    current_section_id = f"Chapter_{final_chapter_num}"
                current_chapter_for_segment = final_chapter_num
                has_final_chapter = True
            elif special_id == "epilogue":
                # Lấy số chương lớn nhất và số final_chapter đã thấy
                volume_key = current_volume_number or 0
                max_chapter_in_volume = max_chapter_by_volume.get(volume_key, 0)
                final_chapter_count = final_chapter_counter_by_volume.get(volume_key, 0)
                
                # Đặt ID cho epilogue, đảm bảo nó nằm sau tất cả các final_chapter
                epilogue_chapter_num = max_chapter_in_volume + 1 + final_chapter_count
                    
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_{epilogue_chapter_num}"
                else:
                    current_section_id = f"Chapter_{epilogue_chapter_num}"
                current_chapter_for_segment = epilogue_chapter_num
            elif special_id == "interlude":
                # Xử lý interlude bằng cách gán một số chương lớn (ví dụ: > 900) để tránh xung đột
                volume_key = current_volume_number or 0
                
                # Lấy và cập nhật bộ đếm interlude cho quyển hiện tại
                interlude_count = interlude_counter_by_volume.get(volume_key, 0)
                interlude_chapter_num = 901 + interlude_count
                interlude_counter_by_volume[volume_key] = interlude_count + 1

                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_{interlude_chapter_num}"
                else:
                    current_section_id = f"Chapter_{interlude_chapter_num}"
                current_chapter_for_segment = interlude_chapter_num
            else:
                # Các phần đặc biệt khác
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_{special_id}"
                else:
                    current_section_id = special_id
            
            current_chapter_number = None
            current_chapter_title = special_title
            current_section.append(special_title)
        
        # Xử lý quyển
        elif volume_number and volume_title:
            if current_section:
                sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                current_section = []
            
            # Khi gặp quyển mới, reset seen_chapters để tránh trùng lặp chapter ID giữa các quyển
            seen_chapters = set()
            previous_chapter_number = None
            has_final_chapter = False  # Reset biến theo dõi chương kết khi bắt đầu quyển mới
            current_chapter_for_segment = 0 # SỬA: Reset số chương cho quyển mới
            
            current_section_id = f"Volume_{volume_number}"
            current_volume_number = volume_number
            current_chapter_number = None
            current_chapter_title = volume_title
            current_section.append(volume_title)
        
        # Xử lý tiêu đề chương
        elif chapter_number and chapter_title:
            # Tạo key duy nhất kết hợp volume và chapter để tránh trùng lặp
            chapter_key = (current_volume_number, chapter_number)
            if chapter_key in seen_chapters:
                i += 1
                continue
            seen_chapters.add(chapter_key)

            if current_section:
                sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                current_section = []

            # Nếu đang trong một volume, thêm thông tin volume vào ID chapter
            if current_volume_number:
                current_section_id = f"Volume_{current_volume_number}_Chapter_{chapter_number}"
            else:
                current_section_id = f"Chapter_{chapter_number}"
                
            current_chapter_number = chapter_number
            current_chapter_for_segment = chapter_number
            previous_chapter_number = chapter_number
            current_chapter_title = chapter_title
            current_section.append(chapter_title)
            
            # Cập nhật max_chapter_by_volume
            volume_key = current_volume_number or 0  # Sử dụng 0 cho quyển mặc định
            max_chapter_by_volume[volume_key] = max(max_chapter_by_volume.get(volume_key, 0), chapter_number)
        
        # Xử lý nội dung thông thường
        else:
            if current_section is not None:
                current_section.append(line)
        
        i += 1
        
        # Nếu đã đến cuối file hoặc dòng tiếp theo là một tiêu đề mới, kết thúc phần hiện tại
        if i < len(lines):
            next_line = lines[i].strip()
            if next_line:
                # Kiểm tra xem dòng tiếp theo có phải là một tiêu đề mới không
                next_special_id, _ = detect_special_section(next_line)
                next_volume_number, _ = detect_volume(next_line)
                next_chapter_number, _ = detect_chapter_title(next_line, max_chapter, previous_chapter_number)
                
                if (next_special_id or next_volume_number or next_chapter_number) and current_section:
                    # Kiểm tra nếu section hiện tại chỉ có tiêu đề (không có nội dung), bỏ qua không lưu
                    if len(current_section) > 1:
                        sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                    
                    current_section = []

    # Thêm phần cuối cùng
    if current_section and len(current_section) > 1:
        sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))

    # Lọc bỏ các segment chỉ có tiêu đề mà không có nội dung
    sections = [s for s in sections if len(s[1]) > 1]

    return sections



def split_and_output(file_path, max_chars, max_chapter, output_path, mode, output_format):
    """Tách file thành các chương/phần và xuất ra file/thư mục."""
    sections = split_content(file_path, max_chapter)

    if output_format == "txt":
        if mode == "2":
            output_to_txt_simple_segments(sections, output_path)
        else:
            output_to_txt(sections, output_path, mode, max_chars)
    else:  # YAML format
        if mode == "2":
            output_to_yaml_simple_segments(sections, output_path)
        else:
            output_to_yaml(sections, output_path, mode, max_chars)

    print(f"\nHoàn thành! Kết quả đã được lưu tại: {os.path.abspath(output_path)}")




def output_to_txt_simple_segments(sections, output_file):
    """Xuất dữ liệu ra file TXT với ID segment đơn giản."""
    with open(output_file, 'w', encoding='utf-8') as out_file:
        segment_counter = 1
        
        for section_id, section_lines, chapter_title, chapter_number in sections:
            # Bỏ qua tiêu đề (line đầu tiên) và lấy nội dung
            content_lines = section_lines[1:]
            
            # Nếu không có nội dung, bỏ qua segment này
            if not content_lines:
                continue
            
            # Ghi ra file với ID đơn giản
            out_file.write(f"Segment_{segment_counter}\n")
            out_file.write(f"{chapter_title}\n")
            for content_line in content_lines:
                out_file.write(f"{content_line}\n\n")
            out_file.write("\n")
            
            segment_counter += 1

def output_to_yaml_simple_segments(sections, output_file):
    """Xuất dữ liệu ra file YAML với ID segment đơn giản."""
    all_segments = []
    segment_counter = 1
    
    for section_id, section_lines, chapter_title, chapter_number in sections:
        # Bỏ qua tiêu đề (line đầu tiên) và lấy nội dung
        content_lines = section_lines[1:]
        
        # Nếu không có nội dung, bỏ qua segment này
        if not content_lines:
            continue
            
        # Nối các dòng nội dung lại với dòng trống giữa mỗi dòng
        content = "\n\n".join(content_lines)

        all_segments.append({
            "id": f"Segment_{segment_counter}",
            "title": chapter_title,
            "content": content
        })
        segment_counter += 1

    # Đăng ký custom representer cho multi-line strings
    yaml.add_representer(str, represent_multiline_string, Dumper=CustomDumper)
    
    # Ghi dữ liệu vào file YAML
    with open(output_file, 'w', encoding='utf-8') as yaml_file:
        yaml.dump(
            all_segments,
            yaml_file,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            Dumper=CustomDumper
        )

def output_to_txt(sections, output_file, mode, max_chars):
    """Xuất dữ liệu ra file TXT."""
    with open(output_file, 'w', encoding='utf-8') as out_file:
        # Chỉ mode 1: Tách theo part dựa trên số ký tự
            global_part_id = 1  # Đếm segment toàn cục
            
            for section_id, section_lines, _, chapter_number in sections:
                # Nếu không có số chương hợp lệ, bỏ qua phần này
                if chapter_number is None or chapter_number < 0:
                    continue
                    
                title = section_lines[0]
                content_lines = section_lines[1:]
                current_part = []
                current_length = 0

                for line in content_lines:
                    line_length = len(re.sub(r'\s+', '', line))
                    if current_length + line_length > max_chars and current_part:
                        out_file.write(f"Chapter_{chapter_number}_Segment_{global_part_id}\n")
                        out_file.write(f"{title}\n")
                        for part_line in current_part:
                            out_file.write(f"{part_line}\n\n")
                        out_file.write("\n")
                        global_part_id += 1
                        current_part = []
                        current_length = 0

                    current_part.append(line)
                    current_length += line_length

                if current_part:
                    out_file.write(f"Chapter_{chapter_number}_Segment_{global_part_id}\n")
                    out_file.write(f"{title}\n")
                    for part_line in current_part:
                        out_file.write(f"{part_line}\n\n")
                    out_file.write("\n")
                    global_part_id += 1

def output_to_yaml(sections, output_file, mode, max_chars):
    """Xuất dữ liệu ra file YAML."""
    all_segments = []
    global_segment_counter = 1  # Đếm segment toàn cục

    # Nhóm các section theo volume
    volumes = {}
    for section_id, section_lines, chapter_title, chapter_number in sections:
        # Trích xuất thông tin volume từ section_id nếu có
        volume_match = re.search(r'Volume_(\d+)', section_id)
        volume_number = int(volume_match.group(1)) if volume_match else None
        
        if volume_number not in volumes:
            volumes[volume_number] = []
        
        volumes[volume_number].append((section_id, section_lines, chapter_title, chapter_number))
    
    # Xử lý từng volume
    for volume_number in sorted(volumes.keys()):
        volume_sections = volumes[volume_number]
        
        # Reset bộ đếm segment trong mỗi volume nếu cần
        volume_segment_counter = 1
        
        # Mode 1: Tách theo segment dựa trên số ký tự
        for section_id, section_lines, _, chapter_number in volume_sections:
            # Nếu không có số chương hợp lệ, bỏ qua phần này
            if chapter_number is None or chapter_number < 0:
                continue
                
            title = section_lines[0]
            content_lines = section_lines[1:]
            current_segment = []
            current_length = 0

            for line in content_lines:
                line_length = len(re.sub(r'\s+', '', line))
                if current_length + line_length > max_chars and current_segment:
                    # Tạo ID với thông tin volume nếu có
                    segment_id = f"Volume_{volume_number}_Chapter_{chapter_number}_Segment_{global_segment_counter}" if volume_number is not None else f"Chapter_{chapter_number}_Segment_{global_segment_counter}"
                    
                    all_segments.append({
                        "id": segment_id,
                        "title": title,
                        "content": "\n\n".join(current_segment)
                    })
                    global_segment_counter += 1
                    volume_segment_counter += 1
                    current_segment = []
                    current_length = 0

                current_segment.append(line)
                current_length += line_length

            if current_segment:
                # Tạo ID với thông tin volume nếu có
                segment_id = f"Volume_{volume_number}_Chapter_{chapter_number}_Segment_{global_segment_counter}" if volume_number is not None else f"Chapter_{chapter_number}_Segment_{global_segment_counter}"
                
                all_segments.append({
                    "id": segment_id,
                    "title": title,
                    "content": "\n\n".join(current_segment)
                })
                global_segment_counter += 1
                volume_segment_counter += 1

    # Đăng ký custom representer cho multi-line strings
    yaml.add_representer(str, represent_multiline_string, Dumper=CustomDumper)
    
    # Ghi dữ liệu vào file YAML
    with open(output_file, 'w', encoding='utf-8') as yaml_file:
        yaml.dump(
            all_segments,
            yaml_file,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            Dumper=CustomDumper
        )

def main():
    print("--- CHƯƠNG TRÌNH TÁCH NỘI DUNG VĂN BẢN NÂNG CAO ---")
    print("(Nhấn Enter để sử dụng giá trị mặc định)\n")
    
    # Nhập thông tin đầu vào
    input_file = input("Nhập file cần tách [input.txt]: ").strip() or "input.txt"
    
    print("\nChọn chế độ tách:")
    print("1 - Tách theo segment dựa trên số ký tự (ID: Chapter_X_Segment_Y)")
    print("2 - Tách đơn giản thành các segment (ID: Segment_X)")
    mode = input("Nhập lựa chọn (1 hoặc 2) [1]: ").strip() or "1"

    print("\nChọn định dạng đầu ra:")
    print("1 - TXT")
    print("2 - YAML")
    format_choice = input("Nhập lựa chọn (1 hoặc 2) [2]: ").strip() or "2"
    output_format = "txt" if format_choice == "1" else "yaml"
    
    user_output = input("Nhập tên file đầu ra (để trống sẽ tự tạo): ").strip()
    
    default_output_dir = "test/data/API_content"
    output_dir = input(f"Nhập đường dẫn thư mục lưu file (mặc định là '{default_output_dir}'): ").strip() or default_output_dir
    
    output_path = get_output_filename(input_file, user_output, output_format, output_dir)
    
    max_chapter = int(input("Nhập số chương tối đa [1000]: ").strip() or 1000)

    max_chars = None
    if mode == "1":
        max_chars = int(input(f"Nhập số ký tự tối đa cho mỗi {'segment' if output_format == 'yaml' else 'part'} [2000]: ").strip() or 2000)
    
    # Xác nhận
    print(f"\nXác nhận:")
    print(f"- Input: {input_file}")
    print(f"- File đầu ra: {output_path}")
    print(f"- Thư mục lưu trữ: {os.path.dirname(output_path)}")
    print(f"- Định dạng: {output_format.upper()}")
        
    if mode == "1":
        print(f"- Chế độ: Tách theo segment dựa trên số ký tự")
        print(f"- Số ký tự tối đa/{'segment' if output_format == 'yaml' else 'part'}: {max_chars}")
        print(f"- Format ID: Chapter_X_Segment_Y hoặc Volume_X_Chapter_Y_Segment_Z")
    else: # mode == "2"
        print(f"- Chế độ: Tách đơn giản thành các segment")
        print(f"- Format ID: Segment_X (đơn giản)")
    
    confirm = input("\nTiếp tục? (y/n) [y]: ").strip().lower() or "y"

    if confirm != 'y':
        print("Hủy thao tác!")
        return

    # Thực hiện tách file
    split_and_output(input_file, max_chars, max_chapter, output_path, mode, output_format)

if __name__ == "__main__":
    main() 