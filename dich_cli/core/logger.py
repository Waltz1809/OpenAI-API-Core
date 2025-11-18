#!/usr/bin/env python3
"""
Logger module với naming convention: ddmmyy_giờ_SDK_tên.log
"""

import os
from datetime import datetime
from typing import Optional
from .path_helper import get_path_helper


class Logger:
    """Logger với smart naming convention và token tracking."""
    
    def __init__(self, log_dir: str, base_name: str, sdk_type: str, mode: str = "translate",
                 timestamp_folder: Optional[str] = None):
        """
        Args:
            log_dir: Thư mục chứa log files (relative to project root)
            base_name: Tên base từ input file
            sdk_type: "gmn" (Gemini) hoặc "oai" (OpenAI)
            mode: "translate", "retry", "context"
            timestamp_folder: Optional subfolder name (cho batch mode)
        """
        ph = get_path_helper()
        
        # Nếu có timestamp_folder, thêm vào log_dir
        if timestamp_folder:
            log_dir = os.path.join(log_dir, timestamp_folder)
        
        self.log_dir = ph.ensure_dir(log_dir)
        self.base_name = base_name
        self.sdk_type = sdk_type
        self.mode = mode
        
        # Tạo tên file theo format: ddmmyy_giờ_SDK_tên.log
        now = datetime.now()
        date_part = now.strftime("%d%m%y")
        time_part = now.strftime("%H%M")
        
        # Tránh duplicate suffix nếu base_name đã chứa mode
        if mode != "translate" and not base_name.endswith(f"_{mode}"):
            suffix = f"_{mode}"
        else:
            suffix = ""

        # Nếu có timestamp_folder (batch mode), không thêm timestamp vào tên file
        if timestamp_folder:
            filename = f"{sdk_type}_{base_name}{suffix}.log"
        else:
            filename = f"{date_part}_{time_part}_{sdk_type}_{base_name}{suffix}.log"

        self.log_file = os.path.join(log_dir, filename)
        
        # Token tracking - Simplified (loại bỏ cache tokens không sử dụng)
        self.total_tokens = {
            "input": 0, 
            "output": 0, 
            "thinking": 0,
            "total": 0
        }
        self.request_count = 0
        self.content_request_count = 0  # Chỉ đếm content segments (không tính Title_Chapter)
        
        # Khởi tạo log file
        self._write_header()
    
    def _write_header(self):
        """Ghi header cho log file."""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"--- BẮT ĐẦU {self.mode.upper()} WORKFLOW {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            f.write(f"SDK: {self.sdk_type.upper()}\n")
            f.write(f"Base name: {self.base_name}\n\n")
    
    def log_segment(self, segment_id: str, status: str, error: Optional[str] = None, 
                   token_info: Optional[dict] = None):
        """
        Ghi log cho một segment.
        
        Args:
            segment_id: ID của segment
            status: "THÀNH CÔNG" hoặc "THẤT BẠI"
            error: Thông tin lỗi (nếu có)
            token_info: {"input": int, "output": int, "thinking": int}
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {segment_id}: {status}"
        
        # Thêm token info nếu có - Simplified format
        if token_info:
            input_tokens = token_info.get('input', 0)
            output_tokens = token_info.get('output', 0)
            thinking_tokens = token_info.get('thinking', 0)
            
            # Log format: input = prompt tokens, output = completion
            log_message += f" | Tokens: In={input_tokens}, Out={output_tokens}"
            
            # Cập nhật tổng token
            self.total_tokens["input"] += input_tokens
            self.total_tokens["output"] += output_tokens
            self.total_tokens["thinking"] += thinking_tokens
            
            # Tính total tokens = input + output + thinking
            request_total = input_tokens + output_tokens + thinking_tokens
            self.total_tokens["total"] += request_total
            
            self.request_count += 1
            
            # Chỉ đếm content segments (không tính Title_Chapter)
            if not segment_id.startswith("Title_"):
                self.content_request_count += 1
        
        if error:
            log_message += f" - Lỗi: {error}"
        
        # Ghi vào file và console
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
        print(log_message)
    
    def log_summary(self, total_segments: int, successful: int, failed: int, 
                   model_name: str, cost_info: Optional[dict] = None):
        """Ghi tổng kết vào log."""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n--- TỔNG KẾT ---\n")
            f.write(f"Model: {model_name}\n")
            f.write(f"Tổng segments: {total_segments}\n")
            f.write(f"Thành công: {self.content_request_count}\n")
            f.write(f"Thất bại: {total_segments - self.content_request_count}\n")
            
            if self.request_count > 0:
                f.write(f"\n--- TOKEN USAGE ---\n")
                f.write(f"Số request thành công: {self.request_count}\n")
                f.write(f"Input tokens (prompt): {self.total_tokens['input']:,}\n")
                f.write(f"Output tokens (completion): {self.total_tokens['output']:,}\n")
                if self.total_tokens['thinking'] > 0:
                    f.write(f"Reasoning tokens: {self.total_tokens['thinking']:,}\n")
                f.write(f"Total tokens: {self.total_tokens['total']:,}\n")
                
                avg_input = self.total_tokens['input'] / self.request_count
                avg_output = self.total_tokens['output'] / self.request_count
                f.write(f"Trung bình Input/request: {avg_input:.1f}\n")
                f.write(f"Trung bình Output/request: {avg_output:.1f}\n")
            
            if cost_info:
                f.write(f"\n--- CHI PHÍ DỰ KIẾN ---\n")
                f.write(f"Tổng chi phí: ${cost_info['total']:.6f} {cost_info['currency']}\n")
            
            f.write(f"\n--- KẾT THÚC {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    def get_log_path(self) -> str:
        """Trả về đường dẫn file log."""
        return self.log_file
    
    def get_token_stats(self) -> dict:
        """Trả về thống kê token."""
        total = sum(self.total_tokens.values())
        return {
            **self.total_tokens,
            "total": total,
            "request_count": self.request_count
        }
