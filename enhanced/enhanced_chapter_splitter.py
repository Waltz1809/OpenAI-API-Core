import re
import yaml
import cn2an
import os

# Tách TXT thành các segment với ID là Volume_X_Chapter_Y_Segment_Z

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
    if chapter_number < 1 or chapter_number > max_chapter:
        return False
    if previous_chapter is None or chapter_number == previous_chapter + 1 or chapter_number == 1:
        return True
    return False

def get_output_filename(input_file, user_output, output_format, output_dir):
    """Xác định tên file đầu ra."""
    # Đảm bảo thư mục tồn tại
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    if not user_output.strip():
        base_name = os.path.splitext(os.path.basename(input_file))[0]
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
    prologue_match = re.match(r'^序章[「『](.+)[」』]', line)
    epilogue_match = re.match(r'^后记$', line)
    foreword_match = re.match(r'^(前言|绪言|引言|序言)$', line)
    final_chapter_match = re.match(r'^终章', line)
    
    # Kiểm tra xem line có bắt đầu bằng "序章" không
    if "序章" in line:
        # Cố gắng trích xuất nội dung trong dấu ngoặc
        match = re.search(r'序章[「『](.+?)[」』]', line)
        if match:
            return "prologue", f"序章: {match.group(1)}"
        else:
            return "prologue", "序章"
    elif epilogue_match:
        return "epilogue", "后记"
    elif foreword_match:
        return "foreword", foreword_match.group(1)
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

def detect_subsection(line):
    """Nhận diện các phần nhỏ trong chương (như 1.1, 1.2, v.v.)."""
    # Loại bỏ BOM nếu có
    line = remove_bom(line)
    
    # Pattern nhận diện phần nhỏ (như 1.1, 1.2, v.v.)
    subsection_match = re.match(r'^(\d+)\.(\d+)$', line)
    
    if subsection_match:
        chapter_num = int(subsection_match.group(1))
        subsection_num = int(subsection_match.group(2))
        return f"{chapter_num}.{subsection_num}", None
    
    return None, None

def detect_chapter_title(line, max_chapter, previous_chapter_number):
    """Nhận diện tiêu đề chương và trả về số chương và tiêu đề."""
    # Loại bỏ BOM nếu có
    line = remove_bom(line)
    
    # Các pattern nhận diện tiêu đề chương
    match_chinese = re.match(r'^第([零一二三四五六七八九十百千]+)章', line)
    match_arabic = re.match(r'^第(\d{1,3})章', line)
    match_vietnamese = re.match(r'^[Cc]hương\s*(\d{1,3})[.:]?\s*(.*)$', line)
    match_chap = re.match(r'^[Cc]hap\s*(\d{1,3})[.:]?\s*(.*)$', line)
    # Thêm pattern nhận diện 第X话 (tiếng Nhật: thoại/chương thứ X)
    match_chinese_hua = re.match(r'^第([零一二三四五六七八九十百千]+)话', line)
    match_arabic_hua = re.match(r'^第(\d{1,3})话', line)

    chapter_number = None
    title = None

    if match_chinese:
        chapter_number = convert_chinese_number_to_arabic(match_chinese.group(1))
        title = line
    elif match_arabic:
        chapter_number = int(match_arabic.group(1))
        title = line
    elif match_vietnamese:
        chapter_number = int(match_vietnamese.group(1))
        title = f"Chương {chapter_number}: {match_vietnamese.group(2)}"
    elif match_chap:
        chapter_number = int(match_chap.group(1))
        title = f"Chap {chapter_number}: {match_chap.group(2)}"
    elif match_chinese_hua:
        chapter_number = convert_chinese_number_to_arabic(match_chinese_hua.group(1))
        title = line
    elif match_arabic_hua:
        chapter_number = int(match_arabic_hua.group(1))
        title = line

    # Kiểm tra số chương có hợp lệ không
    if chapter_number and is_valid_chapter_number(chapter_number, previous_chapter_number, max_chapter):
        return chapter_number, title
    return None, None

def split_content(file_path, max_chapter):
    """Tách file thành các chương, phần nhỏ và phần đặc biệt."""
    # Đọc file và loại bỏ BOM nếu có
    with open(file_path, 'r', encoding='utf-8-sig') as file:
        content = file.read()
    
    # Tiền xử lý nội dung để xử lý các subsection marker
    # Chuyển đổi các subsection marker (như "1.1") thành đánh dấu đặc biệt để xử lý sau
    # Thêm "<subsection>" vào đầu dòng để đánh dấu
    pattern = r'(\n|\r\n|\r)(\d+\.\d+)(\n|\r\n|\r)'
    content = re.sub(pattern, r'\1<subsection>\2\3', content)
    
    # Giờ chia thành các dòng để xử lý
    lines = content.splitlines()

    sections = []
    current_section = []
    previous_chapter_number = None
    seen_chapters = set()
    current_chapter_number = None
    current_section_id = None
    current_subsection_id = None
    current_volume_number = None
    seen_subsections = set()  # Thêm để tránh lặp lại
    current_chapter_title = None
    current_chapter_for_segment = 0  # Số chương hiện tại để đánh ID segment
    has_final_chapter = False  # Biến để theo dõi nếu đã gặp chương kết
    
    # Biến để theo dõi số chương lớn nhất cho mỗi quyển
    max_chapter_by_volume = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Kiểm tra xem line có phải là đánh dấu subsection đặc biệt không
        subsection_marker_match = re.match(r'^<subsection>(\d+\.\d+)$', line)
        if subsection_marker_match:
            subsection_number = subsection_marker_match.group(1)
            # Kiểm tra xem subsection này đã được xử lý chưa
            if subsection_number in seen_subsections:
                i += 1
                continue
            seen_subsections.add(subsection_number)
            
            if current_section:
                # Lưu section hiện tại nếu có nội dung
                if len(current_section) > 1:  # Có ít nhất tiêu đề và nội dung
                    sections.append((current_section_id or "none", current_section, current_chapter_title or "", current_chapter_for_segment))
                current_section = []
            
            # Cập nhật thông tin subsection
            current_section_id = f"subsection_{subsection_number}"
            current_subsection_id = subsection_number
            
            # Thêm marker số hiệu subsection (như "1.1") vào tiêu đề
            current_section.append(subsection_number)
            
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
                        current_subsection_id = None
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
                # Lấy số chương lớn nhất trong quyển hiện tại
                volume_key = current_volume_number or 0
                max_chapter_in_volume = max_chapter_by_volume.get(volume_key, 0)
                
                # Đặt ID có cả volume và final_chapter
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_{max_chapter_in_volume + 1}"
                else:
                    current_section_id = f"Chapter_{max_chapter_in_volume + 1}"
                current_chapter_for_segment = max_chapter_in_volume + 1
                has_final_chapter = True
            elif special_id == "epilogue":
                # Lấy số chương lớn nhất trong quyển hiện tại
                volume_key = current_volume_number or 0
                max_chapter_in_volume = max_chapter_by_volume.get(volume_key, 0)
                
                # Đặt ID có cả volume và epilogue, đặt epilogue sau final_chapter
                if has_final_chapter:
                    epilogue_chapter_num = max_chapter_in_volume + 2
                else:
                    epilogue_chapter_num = max_chapter_in_volume + 1
                    
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_Chapter_{epilogue_chapter_num}"
                else:
                    current_section_id = f"Chapter_{epilogue_chapter_num}"
                current_chapter_for_segment = epilogue_chapter_num
            else:
                # Các phần đặc biệt khác
                if current_volume_number:
                    current_section_id = f"Volume_{current_volume_number}_{special_id}"
                else:
                    current_section_id = special_id
            
            current_chapter_number = None
            current_subsection_id = None
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
            
            current_section_id = f"Volume_{volume_number}"
            current_volume_number = volume_number
            current_chapter_number = None
            current_subsection_id = None
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
            current_subsection_id = None
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
                next_subsection_id, _ = detect_subsection(next_line)
                
                if (next_special_id or next_volume_number or next_chapter_number or next_subsection_id) and current_section:
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

def split_and_output(file_path, max_chars, max_chapter, output_file, mode, output_format):
    """Tách file thành các chương/phần và xuất ra file."""
    sections = split_content(file_path, max_chapter)

    if output_format == "txt":
        if mode == "3":  # Chế độ tách theo đoạn được đánh dấu sẵn và đánh số segment liên tục
            output_to_txt_with_continuous_segments(sections, output_file)
        else:
            output_to_txt(sections, output_file, mode, max_chars)
    else:  # YAML format
        if mode == "3":  # Chế độ tách theo đoạn được đánh dấu sẵn và đánh số segment liên tục
            output_to_yaml_with_continuous_segments(sections, output_file)
        else:
            output_to_yaml(sections, output_file, mode, max_chars)

def output_to_txt_with_continuous_segments(sections, output_file):
    """Xuất dữ liệu ra file TXT với segment đánh số liên tục."""
    with open(output_file, 'w', encoding='utf-8') as out_file:
        # Biến để theo dõi segment liên tục toàn bộ file
        global_segment_counter = 1
        
        # Nhóm các section theo chương
        chapters = {}
        for section_id, section_lines, chapter_title, chapter_number in sections:
            if chapter_number not in chapters:
                chapters[chapter_number] = []
            chapters[chapter_number].append((section_id, section_lines, chapter_title))
        
        # Xử lý từng chương
        for chapter_number in sorted(chapters.keys()):
            chapter_sections = chapters[chapter_number]
            
            # Xác định ID chương
            if chapter_number == 0:  # Prologue
                chapter_id = "Chapter_0"
            elif chapter_number == -1:  # Epilogue cũ (nên không xuất hiện nữa)
                # Tìm số chương lớn nhất
                max_chapter = max([ch for ch in chapters.keys() if isinstance(ch, int) and ch > 0], default=0)
                chapter_id = f"Chapter_{max_chapter + 1}"
            else:
                chapter_id = f"Chapter_{chapter_number}"
            
            # Xử lý từng section trong chương
            for section_id, section_lines, chapter_title in chapter_sections:
                # Bỏ qua tiêu đề (line đầu tiên)
                content_lines = section_lines[1:]
                
                # Loại bỏ các dòng marker subsection (khi xuất)
                filtered_content = []
                for line in content_lines:
                    # Bỏ qua các dòng subsection marker
                    if re.match(r'^\d+\.\d+$', line.strip()):
                        continue
                    filtered_content.append(line)
                
                # Nếu không có nội dung sau khi lọc, bỏ qua segment này
                if not filtered_content:
                    continue
                
                # Ghi ra file
                out_file.write(f"{chapter_id}_Segment_{global_segment_counter}\n")
                out_file.write(f"{chapter_title}\n")
                for content_line in filtered_content:
                    out_file.write(f"{content_line}\n")
                out_file.write("\n")
                
                global_segment_counter += 1

def output_to_yaml_with_continuous_segments(sections, output_file):
    """Xuất dữ liệu ra file YAML với segment đánh số liên tục."""
    all_segments = []
    
    # Biến để theo dõi segment liên tục toàn bộ file
    global_segment_counter = 1
    
    # Nhóm các section theo volume và chapter
    volumes = {}
    for section_id, section_lines, chapter_title, chapter_number in sections:
        # Trích xuất thông tin volume từ section_id nếu có
        volume_match = re.search(r'Volume_(\d+)', section_id)
        volume_number = int(volume_match.group(1)) if volume_match else None
        
        if volume_number not in volumes:
            volumes[volume_number] = {}
        
        if chapter_number not in volumes[volume_number]:
            volumes[volume_number][chapter_number] = []
        
        volumes[volume_number][chapter_number].append((section_id, section_lines, chapter_title))
    
    # Xử lý từng volume
    for volume_number in sorted(volumes.keys()):
        volume_chapters = volumes[volume_number]
        
        # Xử lý từng chương trong volume
        for chapter_number in sorted(volume_chapters.keys()):
            chapter_sections = volume_chapters[chapter_number]
            
            # Xác định ID chương
            if chapter_number == 0:  # Prologue
                if volume_number is not None:
                    chapter_id = f"Volume_{volume_number}_Chapter_0"
                else:
                    chapter_id = "Chapter_0"
            elif chapter_number == -1:  # Epilogue cũ (nên không xuất hiện nữa)
                # Tìm số chương lớn nhất trong volume hiện tại
                max_chapter = max([ch for ch in volume_chapters.keys() if isinstance(ch, int) and ch > 0], default=0)
                if volume_number is not None:
                    chapter_id = f"Volume_{volume_number}_Chapter_{max_chapter + 1}"
                else:
                    chapter_id = f"Chapter_{max_chapter + 1}"
            else:
                # Tạo ID chương với thông tin volume nếu có
                if volume_number is not None:
                    chapter_id = f"Volume_{volume_number}_Chapter_{chapter_number}"
                else:
                    chapter_id = f"Chapter_{chapter_number}"
            
            # Xử lý từng section trong chương
            for section_id, section_lines, chapter_title in chapter_sections:
                # Bỏ qua tiêu đề (line đầu tiên)
                content_lines = section_lines[1:]
                
                # Loại bỏ các dòng marker subsection (khi xuất)
                filtered_content = []
                for line in content_lines:
                    # Bỏ qua các dòng subsection marker
                    if re.match(r'^\d+\.\d+$', line.strip()):
                        continue
                    filtered_content.append(line)
                
                # Nếu không có nội dung sau khi lọc, bỏ qua segment này
                if not filtered_content:
                    continue
                    
                # Nối các dòng nội dung lại
                content = "\n".join(filtered_content)

                all_segments.append({
                    "id": f"{chapter_id}_Segment_{global_segment_counter}",
                    "title": chapter_title,
                    "content": content
                })
                global_segment_counter += 1

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
        if mode == "2":  # Chế độ tách theo chương/phần
            for section_id, section_lines, _, _ in sections:
                title = section_lines[0]
                out_file.write(f"{section_id}\n")
                out_file.write(f"{title}\n")
                for content_line in section_lines[1:]:
                    out_file.write(f"{content_line}\n")
                out_file.write("\n")
        else:  # Chế độ tách theo part
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
                            out_file.write(f"{part_line}\n")
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
                        out_file.write(f"{part_line}\n")
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
        
        # Chế độ tách theo chương/phần
        if mode == "2":
            for section_id, section_lines, _, chapter_number in volume_sections:
                title = section_lines[0]
                content = "\n".join(section_lines[1:])

                # Đảm bảo ID bao gồm thông tin volume nếu có
                if volume_number is not None:
                    if section_id.lower().startswith("chapter_"):
                        # Trích xuất số chapter từ ID
                        chapter_match = re.search(r'Chapter_(\d+)', section_id)
                        if chapter_match:
                            chapter_num = chapter_match.group(1)
                            section_id = f"Volume_{volume_number}_Chapter_{chapter_num}"
                    elif not section_id.startswith(f"Volume_{volume_number}"):
                        section_id = f"Volume_{volume_number}_{section_id}"
                
                all_segments.append({
                    "id": section_id,
                    "title": title,
                    "content": content
                })
        
        # Chế độ tách theo segment
        else:
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
                            "content": "\n".join(current_segment)
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
                        "content": "\n".join(current_segment)
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
    
    print("\nChọn định dạng đầu ra:")
    print("1 - TXT")
    print("2 - YAML")
    format_choice = input("Nhập lựa chọn (1 hoặc 2): ").strip() or "1"
    output_format = "txt" if format_choice == "1" else "yaml"
    
    user_output = input("Nhập tên file đầu ra (để trống sẽ tự tạo): ").strip()
    
    # Hỏi đường dẫn thư mục đầu ra
    output_dir = input("Nhập đường dẫn thư mục lưu file (mặc định là thư mục hiện tại): ").strip() or "."
    output_file = get_output_filename(input_file, user_output, output_format, output_dir)
    
    max_chapter = int(input("Nhập số chương tối đa [1000]: ").strip() or 1000)

    print("\nChọn chế độ tách:")
    print("1 - Tách theo part/segment dựa trên số ký tự")
    print("2 - Tách theo chương/phần")
    print("3 - Tách theo đoạn được đánh dấu sẵn và đánh số segment liên tục")
    mode = input("Nhập lựa chọn (1, 2 hoặc 3) [1]: ").strip() or "1"

    max_chars = None
    if mode == "1":
        max_chars = int(input(f"Nhập số ký tự tối đa cho mỗi {'segment' if output_format == 'yaml' else 'part'} [2000]: ").strip() or 2000)

    # Xác nhận
    print(f"\nXác nhận:")
    print(f"- Input: {input_file}")
    print(f"- Output: {output_file}")
    print(f"- Thư mục đầu ra: {output_dir}")
    print(f"- Định dạng: {output_format.upper()}")
    if mode == "1":
        print(f"- Chế độ: Tách theo part/segment dựa trên số ký tự")
        print(f"- Số ký tự tối đa/{'segment' if output_format == 'yaml' else 'part'}: {max_chars}")
    elif mode == "2":
        print(f"- Chế độ: Tách theo chương/phần")
    else:
        print(f"- Chế độ: Tách theo đoạn được đánh dấu sẵn và đánh số segment liên tục")
    
    confirm = input("\nTiếp tục? (y/n): ").strip().lower() or "y"

    if confirm != 'y':
        print("Hủy thao tác!")
        return

    # Thực hiện tách file
    split_and_output(input_file, max_chars, max_chapter, output_file, mode, output_format)

    print(f"\nHoàn thành! File đã tách lưu tại: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main() 