import re
import json
import os
from datetime import datetime
from typing import List, Dict, Tuple

class LogAnalyzer:
    """Class để phân tích file log và tìm ra các segment thất bại."""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.failed_segments = []
        self.successful_segments = []
        
    def parse_log(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Phân tích file log để tìm ra các segment thất bại và thành công.
        
        Returns:
            Tuple[failed_segments, successful_segments]
        """
        failed = []
        successful = []
        
        if not os.path.exists(self.log_file_path):
            print(f"File log không tồn tại: {self.log_file_path}")
            return failed, successful
            
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # Pattern để match log entry
                # [2025-05-25 01:18:18] Chapter_5_Segment_37: THẤT BẠI - Lỗi: 'NoneType' object has no attribute 'content'
                pattern = r'\[([^\]]+)\]\s+([^:]+):\s+(THÀNH CÔNG|THẤT BẠI)(?:\s+-\s+Lỗi:\s+(.+))?'
                match = re.match(pattern, line)
                
                if match:
                    timestamp_str = match.group(1)
                    segment_id = match.group(2).strip()
                    status = match.group(3)
                    error_msg = match.group(4) if match.group(4) else None
                    
                    entry = {
                        'timestamp': timestamp_str,
                        'segment_id': segment_id,
                        'status': status,
                        'error': error_msg,
                        'line_number': line_num
                    }
                    
                    if status == "THẤT BẠI":
                        failed.append(entry)
                    else:
                        successful.append(entry)
        
        self.failed_segments = failed
        self.successful_segments = successful
        return failed, successful
    
    def get_failed_segment_ids(self) -> List[str]:
        """Lấy danh sách ID của các segment thất bại."""
        return [seg['segment_id'] for seg in self.failed_segments]
    
    def save_failed_list(self, output_file: str):
        """Lưu danh sách segment thất bại ra file JSON."""
        data = {
            'log_file': self.log_file_path,
            'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_failed': len(self.failed_segments),
            'total_successful': len(self.successful_segments),
            'failed_segments': self.failed_segments
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Đã lưu danh sách segment thất bại vào: {output_file}")
    
    def print_summary(self):
        """In tóm tắt kết quả phân tích."""
        print(f"\n--- KẾT QUẢ PHÂN TÍCH LOG ---")
        print(f"File log: {self.log_file_path}")
        print(f"Tổng số segment thành công: {len(self.successful_segments)}")
        print(f"Tổng số segment thất bại: {len(self.failed_segments)}")
        
        if self.failed_segments:
            print(f"\nCác segment thất bại:")
            for i, seg in enumerate(self.failed_segments, 1):
                print(f"{i:3d}. {seg['segment_id']} - {seg['error']}")
    
    def get_error_statistics(self) -> Dict[str, int]:
        """Thống kê các loại lỗi."""
        error_stats = {}
        for seg in self.failed_segments:
            error = seg.get('error', 'Unknown error')
            error_stats[error] = error_stats.get(error, 0) + 1
        return error_stats
    
    def print_error_statistics(self):
        """In thống kê các loại lỗi."""
        error_stats = self.get_error_statistics()
        if error_stats:
            print(f"\n--- THỐNG KÊ LOẠI LỖI ---")
            for error, count in sorted(error_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"{count:3d} lần: {error}")

def main():
    """Hàm main để chạy log analyzer."""
    print("--- CHƯƠNG TRÌNH PHÂN TÍCH LOG DỊCH ---\n")
    
    # Nhập đường dẫn file log
    log_file = input("Nhập đường dẫn file log cần phân tích: ").strip()
    
    if not os.path.exists(log_file):
        print(f"File log không tồn tại: {log_file}")
        return
    
    # Tạo analyzer
    analyzer = LogAnalyzer(log_file)
    
    # Phân tích log
    failed, successful = analyzer.parse_log()
    
    # In tóm tắt
    analyzer.print_summary()
    analyzer.print_error_statistics()
    
    # Hỏi có muốn lưu danh sách segment thất bại không
    if failed:
        save_failed = input(f"\nBạn có muốn lưu danh sách {len(failed)} segment thất bại ra file JSON? (y/n): ").strip().lower()
        
        if save_failed == 'y':
            # Tạo tên file output dựa trên file log
            log_basename = os.path.splitext(os.path.basename(log_file))[0]
            output_dir = os.path.dirname(log_file)
            output_file = os.path.join(output_dir, f"{log_basename}_failed_segments.json")
            
            analyzer.save_failed_list(output_file)
            print(f"\nBạn có thể sử dụng file này làm input cho chương trình retry: {output_file}")
    else:
        print("\nKhông có segment nào thất bại. Tuyệt vời!")

if __name__ == "__main__":
    main() 