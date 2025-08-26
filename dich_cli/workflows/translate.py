#!/usr/bin/env python3
"""
Translation Workflow - Dịch content và title trong cùng 1 lần chạy
"""

import os
import threading
import queue
import time
from typing import Dict, List, Tuple

from core.ai_factory import AIClientFactory
from core.yaml_processor import YamlProcessor
from core.logger import Logger


class TranslateWorkflow:
    """Workflow để dịch cả content và title."""
    
    def __init__(self, config: Dict, secret: Dict):
        self.config = config
        self.secret = secret
        self.processor = YamlProcessor()
        
        # Setup API client cho translate
        self.client = AIClientFactory.create_client(config['translate_api'], secret)
        
        # Setup API client cho title (riêng)
        self.title_client = None
        if config['title_translation']['enabled']:
            self.title_client = AIClientFactory.create_client(config['title_api'], secret)
        
        # Load prompts
        self.content_prompt = self._load_prompt(config['paths']['prompt_file'])
        self.title_prompt = self._load_prompt(config['paths']['title_prompt_file'])
        
        # Setup paths
        self.input_file = config['active_task']['source_yaml_file']
        self.base_name = self.processor.get_base_name(self.input_file)
        
        # Get SDK code from factory
        self.sdk_code = AIClientFactory.get_sdk_code(config['translate_api'])
        
        # Output files
        self.output_file = self.processor.create_output_filename(
            self.input_file, 
            config['paths']['output_trans'],
            self.sdk_code
        )
        
        # Logger
        self.logger = Logger(
            config['paths']['log_trans'],
            self.base_name,
            self.sdk_code
        )
        
        print(f"🔧 SDK: {self.sdk_code.upper()}")
        print(f"🤖 Content Model: {self.client.get_model_name()}")
        
        # Hiển thị multi-key info
        content_provider = self.config['translate_api']['provider']
        if AIClientFactory.has_multiple_keys(content_provider):
            key_status = AIClientFactory.get_key_rotator_status()
            content_keys = key_status.get(content_provider, {}).get('key_count', 1)
            print(f"🔑 Content Keys: {content_keys} keys (round-robin)")
        
        if self.title_client:
            title_sdk = AIClientFactory.get_sdk_code(config['title_api'])
            print(f"🏷️ Title Model: {self.title_client.get_model_name()} ({title_sdk.upper()})")
            
            # Hiển thị title multi-key info
            title_provider = self.config['title_api']['provider']
            if AIClientFactory.has_multiple_keys(title_provider):
                key_status = AIClientFactory.get_key_rotator_status()
                title_keys = key_status.get(title_provider, {}).get('key_count', 1)
                print(f"🔑 Title Keys: {title_keys} keys (round-robin)")
        print(f"📝 Output: {self.output_file}")
        print(f"📋 Log: {self.logger.get_log_path()}")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"Prompt file không tồn tại: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy workflow chính."""
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
            
            print(f"📊 Tổng cộng {len(segments)} segments cần xử lý")
            
            # 2. Dịch content trước
            print("\n📝 Đang dịch content...")
            translated_segments = self._translate_content(segments)
            
            # 3. Dịch titles sau (nếu enabled)
            translated_titles = {}
            if self.config['title_translation']['enabled'] and self.title_client:
                print("\n🏷️ Đang dịch titles...")
                translated_titles = self._translate_titles(segments)
                print(f"✅ Đã dịch {len(translated_titles)} titles")
            
            # 4. Merge titles vào segments
            if translated_titles:
                print("\n🔄 Đang merge titles...")
                self._merge_titles(translated_segments, translated_titles)
            
            # 5. Save temp file trước
            temp_output_file = os.path.join(
                os.path.dirname(self.output_file), 
                f"temp_{os.path.basename(self.output_file)}"
            )
            print(f"\n💾 Đang save temp file: {os.path.basename(temp_output_file)}...")
            self.processor.save_yaml(translated_segments, temp_output_file)
            print(f"✅ Kết quả dịch thô lưu tại: {temp_output_file}")
            
            # 6. Clean từ temp file -> final file
            print(f"\n🧹 Đang clean từ temp file...")
            self._clean_yaml_file(temp_output_file, self.output_file)
            print(f"✅ Clean hoàn thành! File cuối cùng: {self.output_file}")
            
            # 7. Xóa temp file
            if os.path.exists(temp_output_file):
                os.remove(temp_output_file)
                print(f"🗑️ Đã xóa temp file: {os.path.basename(temp_output_file)}")
            
            # 8. Log summary
            successful = len(translated_segments)
            failed = len(segments) - successful
            self.logger.log_summary(
                len(segments), successful, failed, self.client.get_model_name()
            )
            
            print(f"\n🎉 HOÀN THÀNH!")
            print(f"✅ Thành công: {successful}/{len(segments)} segments")
            print(f"📁 Output: {self.output_file}")
            print(f"📋 Log: {self.logger.get_log_path()}")
            
        except Exception as e:
            print(f"❌ Lỗi trong translate workflow: {e}")
            raise
    
    def _translate_titles(self, segments: List[Dict]) -> Dict[str, str]:
        """Dịch titles của các chapters unique bằng title client riêng."""
        # Lấy chapters unique
        unique_chapters = self.processor.get_unique_chapters(segments)
        
        if not unique_chapters:
            return {}
        
        translated_titles = {}
        title_delay = self.config['title_api'].get('delay', 3)
        
        for chapter_id, original_title in unique_chapters.items():
            try:
                print(f"🏷️ Dịch title: {chapter_id}")
                
                if self.title_client is None:
                    print(f"❌ Title client không được khởi tạo")
                    translated_titles[chapter_id] = original_title
                    continue
                
                content, token_info = self.title_client.generate_content(
                    self.title_prompt,
                    original_title
                )
                
                # Clean title result
                translated_title = content.strip().replace('"', '').replace('\\n', '\n')
                translated_titles[chapter_id] = translated_title
                
                self.logger.log_segment(
                    f"Title_{chapter_id}", "THÀNH CÔNG", 
                    token_info=token_info
                )
                
                # Delay cho title để tránh quota issues
                time.sleep(title_delay)
                
            except Exception as e:
                print(f"❌ Lỗi dịch title {chapter_id}: {e}")
                self.logger.log_segment(
                    f"Title_{chapter_id}", "THẤT BẠI", str(e)
                )
                # Giữ nguyên title gốc
                translated_titles[chapter_id] = original_title
        
        return translated_titles
    
    def _translate_content(self, segments: List[Dict]) -> List[Dict]:
        """Dịch content của segments bằng threading."""
        q = queue.Queue()
        result_dict = {}
        lock = threading.Lock()
        
        # Đưa segments vào queue
        for idx, segment in enumerate(segments):
            q.put((idx, segment))
            result_dict[idx] = None
        
        # Threading config
        concurrent_requests = self.config['translate_api']['concurrent_requests']
        num_threads = min(concurrent_requests, len(segments))
        threads = []
        
        print(f"🔧 Sử dụng {num_threads} threads đồng thời...")
        
        # Tạo và chạy threads
        for _ in range(num_threads):
            t = threading.Thread(
                target=self._content_worker,
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
    
    def _content_worker(self, q: queue.Queue, result_dict: Dict, 
                       lock: threading.Lock, total_segments: int):
        """Worker thread để dịch content."""
        while not q.empty():
            try:
                idx, segment = q.get(block=False)
                segment_id = segment['id']
                
                with lock:
                    processed = len([v for v in result_dict.values() if v is not None])
                    print(f"[{processed + 1}/{total_segments}] 📝 {segment_id}")
                
                try:
                    # Dịch content
                    user_prompt = f"Dịch đoạn văn sau từ tiếng Trung sang tiếng Việt:\n\n{segment['content']}"
                    
                    content, token_info = self.client.generate_content(
                        self.content_prompt,
                        user_prompt
                    )
                    
                    # Tạo segment mới
                    translated_segment = {
                        'id': segment['id'],
                        'title': segment['title'],  # Sẽ được merge sau
                        'content': content
                    }
                    
                    with lock:
                        result_dict[idx] = translated_segment
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
                
                # Delay để tránh rate limit
                time.sleep(self.config['translate_api'].get('delay', 1))
                
            except queue.Empty:
                break
    
    def _merge_titles(self, segments: List[Dict], translated_titles: Dict[str, str]):
        """Merge translated titles vào segments."""
        for segment in segments:
            segment_id = segment.get('id', '')
            
            # Tìm chapter ID từ segment ID
            chapter_match = self.processor.chapter_pattern.search(segment_id)
            if chapter_match:
                chapter_id = chapter_match.group(0)
                
                if chapter_id in translated_titles:
                    segment['title'] = translated_titles[chapter_id]
    
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
