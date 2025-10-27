#!/usr/bin/env python3
"""
Retry Workflow - Dịch lại các segments thất bại
"""

import os
import json
import threading
import queue
import time
from typing import Dict, List, Optional
from datetime import datetime

from core.ai_factory import AIClientFactory
from core.yaml_processor import YamlProcessor
from core.logger import Logger


class RetryWorkflow:
    """Workflow để retry các segments thất bại."""
    
    def __init__(self, config: Dict, secret: Dict):
        self.config = config
        self.secret = secret
        self.processor = YamlProcessor()
        
        # Setup API client cho retry
        self.client = AIClientFactory.create_client(config['retry_api'], secret)
        
        # Load prompt
        self.prompt = self._load_prompt(config['paths']['prompt_file'])
        
        # Setup paths
        self.input_file = config['active_task']['source_yaml_file']
        self.base_name = self.processor.get_base_name(self.input_file)
        
        # Get SDK code from factory - sử dụng method tồn tại
        provider = config['retry_api'].get('provider', 'openai').lower()
        sdk_mapping = {'openai': 'oai', 'gemini': 'gmn', 'vertex': 'vtx'}
        self.sdk_code = sdk_mapping.get(provider, 'oai')
        
        # Logger
        self.logger = Logger(
            config['paths']['log_trans'],
            self.base_name,
            self.sdk_code,
            "retry"
        )
        
        print(f"🔧 Retry SDK: {self.sdk_code.upper()}")
        print(f"🤖 Retry Model: {self.client.get_model_name()}")
        print(f"📋 Log: {self.logger.get_log_path()}")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"Prompt file không tồn tại: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy retry workflow."""
        try:
            # 1. Tìm hoặc lấy file log để phân tích
            log_file = self._get_log_file()
            if not log_file:
                print("❌ Không tìm thấy file log nào để phân tích!")
                return
            
            print(f"📋 Phân tích log: {log_file}")
            
            # 2. Phân tích log để tìm failed segments
            failed_segments = self._analyze_log(log_file)
            if not failed_segments:
                print("✅ Không có segment nào thất bại!")
                return
            
            print(f"⚠️ Tìm thấy {len(failed_segments)} segment thất bại")
            
            # 3. Tìm hoặc lấy file output để patch
            output_file = self._get_output_file(log_file)
            if not output_file:
                print("❌ Không tìm thấy file output tương ứng!")
                return
            
            print(f"🎯 Sẽ patch file: {output_file}")
            
            # 4. Load segments gốc để lấy content
            print("📖 Load segments gốc...")
            original_segments = self.processor.load_yaml(self.input_file)
            
            # 5. Retry dịch các segments thất bại
            print(f"🔄 Bắt đầu retry {len(failed_segments)} segments...")
            fixed_segments = self._retry_segments(failed_segments, original_segments)
            
            if not fixed_segments:
                print("❌ Không có segment nào được sửa thành công!")
                return
            
            # 6. Patch file output
            print(f"🔧 Patch {len(fixed_segments)} segments vào file...")
            self._patch_output_file(output_file, fixed_segments)
            
            # 7. Log summary
            self.logger.log_summary(
                len(failed_segments), len(fixed_segments), 
                len(failed_segments) - len(fixed_segments),
                self.client.get_model_name()
            )
            
            print(f"\n🎉 RETRY HOÀN THÀNH!")
            print(f"✅ Đã sửa: {len(fixed_segments)}/{len(failed_segments)} segments")
            print(f"📁 File đã patch: {output_file}")
            print(f"📋 Log: {self.logger.get_log_path()}")
            
        except Exception as e:
            print(f"❌ Lỗi trong retry workflow: {e}")
            raise
    
    def _get_log_file(self) -> Optional[str]:
        """
        Lấy file log để phân tích.
        - Nếu config có 'retry_log_file' và khác "LATEST", dùng path đó
        - Ngược lại, tìm file log mới nhất
        """
        # Kiểm tra xem có chỉ định file log cụ thể không
        retry_log_file = self.config.get('retry_log_file', 'LATEST')
        
        if retry_log_file and retry_log_file.upper() != 'LATEST':
            # Sử dụng file log được chỉ định
            if os.path.isabs(retry_log_file):
                log_path = retry_log_file
            else:
                # Relative path từ project root
                log_path = os.path.abspath(retry_log_file)
            
            if not os.path.exists(log_path):
                print(f"❌ File log được chỉ định không tồn tại: {log_path}")
                return None
            
            print(f"📌 Sử dụng file log được chỉ định: {os.path.basename(log_path)}")
            return log_path
        
        # Mặc định: tìm file log mới nhất
        return self._find_latest_log()
    
    def _find_latest_log(self) -> Optional[str]:
        """Tìm file log mới nhất (KHÔNG BAO GỒM chính file retry log hiện tại)."""
        log_dir = self.config['paths']['log_trans']
        
        if not os.path.exists(log_dir):
            return None
        
        # Tìm TẤT CẢ files log
        all_log_files = [
            os.path.join(log_dir, f) 
            for f in os.listdir(log_dir) 
            if f.endswith('.log')
        ]
        
        if not all_log_files:
            return None
        
        # Loại bỏ chính file log hiện tại của retry workflow
        current_retry_log = self.logger.get_log_path()
        log_files = [
            f for f in all_log_files 
            if os.path.abspath(f) != os.path.abspath(current_retry_log)
        ]
        
        if not log_files:
            print("❌ Chỉ tìm thấy file retry log hiện tại, không có log gốc nào để phân tích!")
            return None
        
        # Trả về file mới nhất (không phải retry log hiện tại)
        latest_log = max(log_files, key=os.path.getmtime)
        print(f"🔍 Phát hiện log mới nhất: {os.path.basename(latest_log)}")
        return latest_log
    
    def _analyze_log(self, log_file: str) -> List[str]:
        """Phân tích log để tìm failed segments."""
        failed_segments = []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ': THẤT BẠI' in line:
                    # Extract segment ID từ log line
                    # Format: [timestamp] segment_id: THẤT BẠI - Lỗi: ...
                    parts = line.split('] ', 1)
                    if len(parts) > 1:
                        segment_part = parts[1].split(': THẤT BẠI')[0]
                        # Bỏ qua title logs
                        if not segment_part.startswith('Title_'):
                            failed_segments.append(segment_part)
        
        return failed_segments
    
    def _get_output_file(self, log_file: str) -> Optional[str]:
        """
        Lấy file output để patch.
        - Nếu config có 'retry_output_file' và khác "LATEST", dùng path đó
        - Ngược lại, tìm file output mới nhất
        """
        # Kiểm tra xem có chỉ định file output cụ thể không
        retry_output_file = self.config.get('retry_output_file', 'LATEST')
        
        if retry_output_file and retry_output_file.upper() != 'LATEST':
            # Sử dụng file output được chỉ định
            if os.path.isabs(retry_output_file):
                output_path = retry_output_file
            else:
                # Relative path từ project root
                output_path = os.path.abspath(retry_output_file)
            
            if not os.path.exists(output_path):
                print(f"❌ File output được chỉ định không tồn tại: {output_path}")
                return None
            
            print(f"📌 Sử dụng file output được chỉ định: {os.path.basename(output_path)}")
            return output_path
        
        # Mặc định: tìm file output mới nhất
        return self._find_output_file(log_file)
    
    def _find_output_file(self, log_file: str) -> Optional[str]:
        """Tìm file output mới nhất trong output dir."""
        # Đọc header của log để tìm output path
        with open(log_file, 'r', encoding='utf-8') as f:
            for _ in range(10):  # Chỉ đọc vài dòng đầu
                line = f.readline()
                if not line:
                    break
                # Tìm pattern output file trong log
                if 'Output:' in line or 'output' in line.lower():
                    # Có thể cần logic phức tạp hơn để extract path
                    pass
        
        # Fallback: Tìm file YAML mới nhất trong output dir
        output_dir = self.config['paths']['output_trans']
        if not os.path.exists(output_dir):
            return None
        
        yaml_files = [
            os.path.join(output_dir, f) 
            for f in os.listdir(output_dir) 
            if f.endswith('.yaml')
        ]
        
        if not yaml_files:
            return None
        
        latest_output = max(yaml_files, key=os.path.getmtime)
        print(f"🔍 Phát hiện output mới nhất: {os.path.basename(latest_output)}")
        return latest_output
    
    def _retry_segments(self, failed_segment_ids: List[str], 
                       original_segments: List[Dict]) -> List[Dict]:
        """Retry dịch các segments thất bại."""
        # Tìm segments gốc tương ứng
        segments_to_retry = []
        for segment_id in failed_segment_ids:
            for segment in original_segments:
                if segment['id'] == segment_id:
                    segments_to_retry.append(segment)
                    break
        
        if not segments_to_retry:
            return []
        
        # Threading setup
        q = queue.Queue()
        result_dict = {}
        lock = threading.Lock()
        
        for idx, segment in enumerate(segments_to_retry):
            q.put((idx, segment))
            result_dict[idx] = None
        
        # Retry với threading
        concurrent_requests = self.config['retry_api']['concurrent_requests']
        num_threads = min(concurrent_requests, len(segments_to_retry))
        threads = []
        
        for _ in range(num_threads):
            t = threading.Thread(
                target=self._retry_worker,
                args=(q, result_dict, lock, len(segments_to_retry))
            )
            t.daemon = True
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # Thu thập kết quả thành công
        results = []
        for idx in sorted(result_dict.keys()):
            if result_dict[idx] is not None:
                results.append(result_dict[idx])
        
        return results
    
    def _retry_worker(self, q: queue.Queue, result_dict: Dict,
                     lock: threading.Lock, total_segments: int):
        """Worker thread cho retry."""
        max_retries = self.config['retry_api'].get('max_retries', 3)
        
        while not q.empty():
            try:
                idx, segment = q.get(block=False)
                segment_id = segment['id']
                
                with lock:
                    processed = len([v for v in result_dict.values() if v is not None])
                    print(f"[{processed + 1}/{total_segments}] 🔄 Retry {segment_id}")
                
                # Retry với số lần tối đa
                success = False
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            print(f"    🔄 Thử lại lần {attempt + 1}/{max_retries}")
                        
                        user_prompt = f"\n\n{segment['content']}"
                        
                        content, token_info = self.client.generate_content(
                            self.prompt,
                            user_prompt
                        )
                        
                        # Thành công
                        translated_segment = {
                            'id': segment['id'],
                            'title': segment['title'],
                            'content': content
                        }
                        
                        with lock:
                            result_dict[idx] = translated_segment
                            self.logger.log_segment(
                                segment_id, f"THÀNH CÔNG (retry {attempt + 1})",
                                token_info=token_info
                            )
                        
                        success = True
                        break
                        
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                
                if not success:
                    with lock:
                        result_dict[idx] = None
                        self.logger.log_segment(
                            segment_id, f"THẤT BẠI sau {max_retries} lần thử", last_error
                        )
                
                q.task_done()
                
                # Delay để tránh rate limit (đọc từ config)
                time.sleep(self.config['retry_api'].get('delay', 1))
                
            except queue.Empty:
                break
    
    def _patch_output_file(self, output_file: str, fixed_segments: List[Dict]):
        """Patch fixed segments vào output file."""
        # Load file gốc
        original_data = self.processor.load_yaml(output_file)
        
        # Tạo map để patch nhanh
        fixes_map = {segment['id']: segment for segment in fixed_segments}
        
        # Patch content
        patched_count = 0
        for segment in original_data:
            if segment['id'] in fixes_map:
                fixed_segment = fixes_map[segment['id']]
                segment['title'] = fixed_segment['title']
                segment['content'] = fixed_segment['content']
                patched_count += 1
        
        # Clean nếu enabled
        if self.config['cleaner']['enabled']:
            for segment in original_data:
                if segment['id'] in fixes_map:
                    segment['content'] = self.processor.clean_content(segment['content'])
        
        # Save lại file
        self.processor.save_yaml(original_data, output_file)
        
        print(f"✅ Đã patch {patched_count} segments vào file")
