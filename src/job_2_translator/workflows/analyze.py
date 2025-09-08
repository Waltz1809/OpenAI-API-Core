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


class AnalyzeWorkflow:
    """Workflow để phân tích ngữ cảnh."""

    def __init__(self, config: Dict, secret: Dict, input_file: str | None = None, output_base_override: str | None = None):
        self.config = config
        self.secret = secret
        self.processor = YamlProcessor()
        # Setup API client cho context analysis (reuses translate_api settings)
        self.client = AIClientFactory.create_client(config['translate_api'], secret)

        # Load prompt
        self.prompt = self._load_prompt(config['paths']['context_prompt_file'])

        # Validate & set input
        if not input_file:
            raise ValueError("AnalyzeWorkflow now requires explicit input_file (legacy source_yaml_file removed).")
        self.input_file = input_file
        self.base_name = self.processor.get_base_name(self.input_file)

        # Get SDK code from factory (based on translate_api now)
        self.sdk_code = AIClientFactory.get_sdk_code(config['translate_api'])

        # Output base directory override (to maintain parallel directory structure)
        context_subdir = output_base_override or config['paths']['context_dir']

        self.output_file = self.processor.create_output_filename(
            self.input_file,
            context_subdir,
            self.sdk_code,
            "context"
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
        print(f"📋 Log: {self.logger.get_log_path()}")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"Context prompt file không tồn tại: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy context analysis workflow."""
        try:
            # 1. Load và filter YAML
            print("\n📖 Đang load file YAML...")
            segments = self.processor.load_yaml(self.input_file)
            
            print(f"📊 Tổng cộng {len(segments)} segments cần phân tích")
            
            # 2. Phân tích ngữ cảnh
            print("\n🔍 Đang phân tích ngữ cảnh...")
            analyzed_segments = self._analyze_segments(segments)
            
            # 3. Save temp file trước
            temp_output_file = os.path.join(
                os.path.dirname(self.output_file), 
                f"temp_{os.path.basename(self.output_file)}"
            )
            print(f"\n💾 Đang save temp file: {os.path.basename(temp_output_file)}...")
            self.processor.save_yaml(analyzed_segments, temp_output_file)
            print(f"✅ Kết quả phân tích thô lưu tại: {temp_output_file}")
            
            # 4. Clean từ temp file -> final file
            print(f"\n🧹 Đang clean từ temp file...")
            self._clean_yaml_file(temp_output_file, self.output_file)
            print(f"✅ Clean hoàn thành! File cuối cùng: {self.output_file}")
            
            # 5. Xóa temp file
            if os.path.exists(temp_output_file):
                os.remove(temp_output_file)
                print(f"🗑️ Đã xóa temp file: {os.path.basename(temp_output_file)}")
            
            # 6. Log summary - đếm từ logger stats
            successful = self.logger.request_count  # Số request thành công (có token_info)
            failed = len(segments) - successful
            self.logger.log_summary(
                len(segments), successful, failed, self.client.get_model_name()
            )
            
            print(f"\n🎉 PHÂN TÍCH HOÀN THÀNH!")
            print(f"✅ Thành công: {successful}/{len(segments)} segments")
            print(f"📁 Output: {self.output_file}")
            print(f"📋 Log: {self.logger.get_log_path()}")
            
        except Exception as e:
            print(f"❌ Lỗi trong analyze workflow: {e}")
            raise
    
    def _analyze_segments(self, segments: List[Dict]) -> List[Dict]:
        """Phân tích ngữ cảnh của segments bằng threading."""
        q = queue.Queue()
        result_dict = {}
        lock = threading.Lock()
        
        # Đưa segments vào queue
        for idx, segment in enumerate(segments):
            q.put((idx, segment))
            result_dict[idx] = None

        # Threading config
        concurrent_requests = self.config['translate_api'].get('concurrent_requests', 1)
        num_threads = min(concurrent_requests, len(segments))
        threads = []

        print(f"🔧 Sử dụng {num_threads} threads đồng thời...")

        # Tạo và chạy threads
        for _ in range(num_threads):
            t = threading.Thread(
                target=self._analysis_worker,
                args=(q, result_dict, lock, len(segments))
            )
            t.daemon = True
            t.start()
            threads.append(t)

        # Đợi hoàn thành
        for t in threads:
            t.join()

        # Thu thập kết quả
        results = []
        for idx in sorted(result_dict.keys()):
            if result_dict[idx] is not None:
                results.append(result_dict[idx])

        return results
    
    def _analysis_worker(self, q: queue.Queue, result_dict: Dict, 
                        lock: threading.Lock, total_segments: int):
        """Worker thread để phân tích context."""
        while not q.empty():
            try:
                idx, segment = q.get(block=False)
                segment_id = segment['id']
                
                with lock:
                    processed = len([v for v in result_dict.values() if v is not None])
                    print(f"[{processed + 1}/{total_segments}] 🔍 {segment_id}")
                
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
                    
                    with lock:
                        result_dict[idx] = analyzed_segment
                        self.logger.log_segment(
                            segment_id, "THÀNH CÔNG", token_info=token_info
                        )
                
                except Exception as e:
                    with lock:
                        # Giữ segment gốc nếu lỗi
                        result_dict[idx] = segment
                        self.logger.log_segment(
                            segment_id, "THẤT BẠI", str(e)
                        )
                
                q.task_done()
                
                # Delay để tránh rate limit (reuse translate_api.delay)
                time.sleep(self.config['translate_api'].get('delay', 1))
                
            except queue.Empty:
                break
    
    def _clean_yaml_file(self, input_file: str, output_file: str):
        """Clean YAML file theo pattern của file cũ: temp -> final."""
        if not self.config['cleaner']['enabled']:
            # Nếu không clean, chỉ rename
            os.rename(input_file, output_file)
            return
        
        # Đọc temp file
        temp_data = self.processor.load_yaml(input_file)
        
        # Clean từng segment
        for segment in temp_data:
            if 'content' in segment and segment['content']:
                segment['content'] = self.processor.clean_content(segment['content'])
        
        # Ghi ra final file
        self.processor.save_yaml(temp_data, output_file)
    
    def _clean_segments(self, segments: List[Dict]):
        """Clean content của segments - deprecated, dùng _clean_yaml_file."""
        if not self.config['cleaner']['enabled']:
            return
        
        for segment in segments:
            if 'content' in segment:
                segment['content'] = self.processor.clean_content(segment['content'])
