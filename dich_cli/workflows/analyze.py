#!/usr/bin/env python3
"""
Analyze Workflow - Phân tích ngữ cảnh của content
"""

import os
import threading
import queue
import time
from typing import Dict, List

from core.ai_factory import AIClientFactory
from core.yaml_processor import YamlProcessor
from core.logger import Logger
from core.path_helper import get_path_helper


class AnalyzeWorkflow:
    """Workflow để phân tích ngữ cảnh."""
    
    def __init__(self, config: Dict, secret: Dict):
        self.config = config
        self.secret = secret
        self.processor = YamlProcessor()
        
        # Setup API client cho context analysis
        self.client = AIClientFactory.create_client(config['context_api'], secret)
        
        # Load prompt
        self.prompt = self._load_prompt(config['paths']['context_prompt_file'])
        
        # Setup paths
        self.input_file = config['active_task']['source_yaml_file']
        self.base_name = self.processor.get_base_name(self.input_file)
        
        # Get SDK code from factory
        self.sdk_code = AIClientFactory.get_sdk_code(config['context_api'])
        
        # Output files (context_dir chứa cả output và log)
        context_subdir = config['paths']['context_dir']

        self.output_file = self.processor.create_output_filename(
            self.input_file,
            context_subdir,
            self.sdk_code,
            "context"
        )
        
        # Temp file for incremental writes
        self.temp_file = self.processor.create_temp_filename(
            f"{self.base_name}_context",
            config['paths']['temp_output'],
            self.sdk_code
        )

        # Logger (cũng save trong context_subdir)
        self.logger = Logger(
            context_subdir,
            self.base_name,
            self.sdk_code,
            "context"
        )
        
        print(f"🔧 Context SDK: {self.sdk_code.upper()}")
        print(f"🤖 Context Model: {self.client.get_model_name()}")
        print(f"📝 Output: {self.output_file}")
        print(f"💾 Temp: {self.temp_file}")
        print(f"📋 Log: {self.logger.get_log_path()}")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        ph = get_path_helper()
        resolved_path = ph.resolve(prompt_file)
        
        if not ph.exists(resolved_path):
            raise FileNotFoundError(f"Context prompt file không tồn tại: {prompt_file}")

        with open(resolved_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy context analysis workflow."""
        try:
            # 1. Load và filter YAML
            print("\n📖 Đang load file YAML...")
            segments = self.processor.load_yaml(self.input_file)
            
            # Filter theo filtering config mới
            original_count = len(segments)
            segments = self.processor.filter_segments(
                segments, self.config['filtering']
            )
            
            if len(segments) != original_count:
                print(f"📊 Đã filter: {original_count} -> {len(segments)} segments")
            
            print(f"📊 Tổng cộng {len(segments)} segments cần phân tích")
            
            # 2. Xóa temp file cũ nếu có
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
                print(f"🗑️ Đã xóa temp file cũ")
            
            # 3. Phân tích ngữ cảnh (ghi incremental vào temp file)
            print("\n🔍 Đang phân tích ngữ cảnh...")
            self._analyze_segments(segments)
            print(f"✅ Đã phân tích xong, đang load từ temp file...")
            
            # 4. Load temp file và sort theo thứ tự gốc
            analyzed_segments = self.processor.load_yaml(self.temp_file)
            print(f"📊 Đang sắp xếp lại theo thứ tự gốc...")
            analyzed_segments = self.processor.sort_by_original_order(
                analyzed_segments, segments
            )
            
            # 5. Clean và save final file
            print(f"\n🧹 Đang clean và save final file...")
            if self.config['cleaner']['enabled']:
                for segment in analyzed_segments:
                    if 'content' in segment and segment['content']:
                        segment['content'] = self.processor.clean_content(segment['content'])
            
            # 5.1. Extract titles từ content (nếu context có dịch title)
            print(f"🏷️ Đang extract titles từ content...")
            extracted_count = self._extract_titles_from_content(analyzed_segments)
            if extracted_count > 0:
                print(f"✅ Đã extract {extracted_count} titles từ content")
            
            self.processor.save_yaml(analyzed_segments, self.output_file)
            print(f"✅ Đã save final file: {self.output_file}")
            
            # 6. Xóa temp file
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
                print(f"🗑️ Đã xóa temp file")
            
            # 6. Log summary - đếm từ logger stats
            successful = self.logger.request_count  # Số request thành công (có token_info)
            failed = len(segments) - successful
            self.logger.log_summary(
                len(segments), successful, failed, self.client.get_model_name()
            )
            
            # 7. Log failed segments (để có thể retry sau)
            if failed > 0:
                print(f"⚠️ Có {failed} segments thất bại")
                analyzed_ids = {seg['id'] for seg in analyzed_segments if 'id' in seg}
                original_ids = {seg['id'] for seg in segments if 'id' in seg}
                failed_ids = original_ids - analyzed_ids
                
                if failed_ids:
                    self.logger.log_message(
                        f"Failed segments: {', '.join(sorted(failed_ids))}",
                        "ERROR"
                    )
            
            print(f"\n🎉 PHÂN TÍCH HOÀN THÀNH!")
            print(f"✅ Thành công: {successful}/{len(segments)} segments")
            if failed > 0:
                print(f"⚠️ Thất bại: {failed} segments (xem log để retry)")
            print(f"📁 Output: {self.output_file}")
            print(f"📋 Log: {self.logger.get_log_path()}")
            
        except Exception as e:
            print(f"❌ Lỗi trong analyze workflow: {e}")
            raise
    
    def _analyze_segments(self, segments: List[Dict]):
        """Phân tích ngữ cảnh của segments bằng threading và ghi incremental vào temp file."""
        q = queue.Queue()
        lock = threading.Lock()
        processed_count = {'value': 0}
        
        # Đưa segments vào queue
        for segment in segments:
            q.put(segment)
        
        # Threading config
        concurrent_requests = self.config['context_api']['concurrent_requests']
        num_threads = min(concurrent_requests, len(segments))
        threads = []
        
        print(f"🔧 Sử dụng {num_threads} threads đồng thời...")
        
        # Tạo và chạy threads
        for _ in range(num_threads):
            t = threading.Thread(
                target=self._analysis_worker,
                args=(q, lock, len(segments), processed_count)
            )
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Đợi hoàn thành
        for t in threads:
            t.join()
    
    def _analysis_worker(self, q: queue.Queue, lock: threading.Lock, 
                        total_segments: int, processed_count: Dict):
        """Worker thread để phân tích context và ghi vào temp file."""
        while not q.empty():
            try:
                segment = q.get(block=False)
                segment_id = segment['id']
                
                with lock:
                    processed_count['value'] += 1
                    current = processed_count['value']
                    print(f"[{current}/{total_segments}] 🔍 {segment_id}")
                
                try:
                    # Phân tích context
                    user_prompt = f"Phân tích ngữ cảnh của đoạn văn sau:\n\n{segment['content']}"
                    
                    analysis, token_info = self.client.generate_content(
                        self.prompt,
                        user_prompt
                    )
                    
                    # Tạo segment mới với analysis
                    analyzed_segment = {
                        'id': segment['id'],
                        'title': segment['title'],
                        'content': analysis  # Replace content với analysis
                    }
                    
                    # Ghi vào temp file ngay (thread-safe)
                    with lock:
                        self.processor.append_segment_to_temp(analyzed_segment, self.temp_file)
                        self.logger.log_segment(
                            segment_id, "THÀNH CÔNG", token_info=token_info
                        )
                
                except Exception as e:
                    with lock:
                        # Giữ segment gốc nếu lỗi
                        self.processor.append_segment_to_temp(segment, self.temp_file)
                        self.logger.log_segment(
                            segment_id, "THẤT BẠI", str(e)
                        )
                
                q.task_done()
                
                # Delay để tránh rate limit
                time.sleep(self.config['context_api'].get('delay', 1))
                
            except queue.Empty:
                break
    
    def _extract_titles_from_content(self, segments: List[Dict]) -> int:
        """
        Extract title từ dòng đầu của content và update field title.
        Dùng cho context analysis nếu có dịch title trong content.
        
        Returns:
            int: Số segments đã extract title
        """
        extracted = 0
        
        for segment in segments:
            if 'content' not in segment or not segment['content']:
                continue
            
            content = segment['content']
            lines = content.split('\n')
            
            # Bỏ qua các dòng rỗng ở đầu
            first_line_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    first_line_idx = i
                    break
            
            if first_line_idx >= len(lines):
                continue
            
            first_line = lines[first_line_idx].strip()
            
            # Loại bỏ dấu ' ở đầu nếu có (từ splitter)
            if first_line.startswith("'"):
                first_line = first_line[1:].strip()
            
            # Update title nếu có nội dung
            if first_line:
                segment['title'] = first_line
                extracted += 1
        
        return extracted
