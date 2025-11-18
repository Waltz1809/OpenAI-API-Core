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
from core.path_helper import get_path_helper


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
        
        # Batch processing setup
        self.batch_mode = config.get('batch_processing', {}).get('enabled', False)
        self.timestamp_folder_name = None  # Sẽ được tạo khi run batch mode
        
        # Temp file for incremental writes (được tạo lại mỗi batch)
        self.temp_file = None
        
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
        
        # Mode info
        if self.batch_mode:
            batch_config = config['batch_processing']
            mode = batch_config.get('mode', 'chapter')
            size = batch_config.get('chapters_per_batch', 100)
            print(f"📦 Batch Mode: {mode.upper()} ({size} chapters/batch)")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        ph = get_path_helper()
        resolved_path = ph.resolve(prompt_file)
        
        if not ph.exists(resolved_path):
            raise FileNotFoundError(f"Prompt file không tồn tại: {prompt_file}")
        
        with open(resolved_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy workflow chính - dispatch to batch or single file mode."""
        try:
            # Load và filter YAML
            print("\n📖 Đang load file YAML...")
            segments = self.processor.load_yaml(self.input_file)
            
            # Filter theo filtering config
            original_count = len(segments)
            segments = self.processor.filter_segments(
                segments, self.config['filtering']
            )
            
            if len(segments) != original_count:
                print(f"📊 Đã filter: {original_count} -> {len(segments)} segments")
            
            print(f"📊 Tổng cộng {len(segments)} segments cần xử lý")
            
            # Dispatch theo mode
            if self.batch_mode:
                self._run_batch_mode(segments)
            else:
                self._run_single_file_mode(segments)
                
        except Exception as e:
            print(f"❌ Lỗi trong translate workflow: {e}")
            raise
    
    def _run_single_file_mode(self, segments: List[Dict]):
        """Chạy workflow mode single file (logic cũ)."""
        # Setup output và temp files
        output_file = self.processor.create_output_filename(
            self.input_file, 
            self.config['paths']['output_trans'],
            self.sdk_code
        )
        
        self.temp_file = self.processor.create_temp_filename(
            self.base_name,
            self.config['paths']['temp_output'],
            self.sdk_code
        )
        
        # Setup logger (single file mode - không có timestamp folder)
        logger = Logger(
            self.config['paths']['log_trans'],
            self.base_name,
            self.sdk_code
        )
        
        print(f"📝 Output: {output_file}")
        print(f"💾 Temp: {self.temp_file}")
        print(f"📋 Log: {logger.get_log_path()}")
        
        # Xóa temp file cũ nếu có
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
            print(f"🗑️ Đã xóa temp file cũ")
        
        # Dịch content
        print("\n📝 Đang dịch content...")
        self._translate_content(segments, logger)
        print(f"✅ Đã dịch xong, đang load từ temp file...")
        
        # Load temp file và sort
        translated_segments = self.processor.load_yaml(self.temp_file)
        print(f"📊 Đang sắp xếp lại theo thứ tự gốc...")
        translated_segments = self.processor.sort_by_original_order(
            translated_segments, segments
        )
        
        # Dịch titles (nếu enabled)
        translated_titles = {}
        if self.config['title_translation']['enabled'] and self.title_client:
            print("\n🏷️ Đang dịch titles...")
            translated_titles = self._translate_titles(segments, logger)
            print(f"✅ Đã dịch {len(translated_titles)} titles")
        
        # Merge titles
        if translated_titles:
            print("\n🔄 Đang merge titles...")
            self._merge_titles(translated_segments, translated_titles)
        
        # Clean
        print(f"\n🧹 Đang clean và save final file...")
        if self.config['cleaner']['enabled']:
            for segment in translated_segments:
                if 'content' in segment and segment['content']:
                    segment['content'] = self.processor.clean_content(segment['content'])
        
        # Extract titles từ content
        print(f"🏷️ Đang extract titles từ content đã dịch...")
        extracted_count = self._extract_titles_from_content(translated_segments)
        if extracted_count > 0:
            print(f"✅ Đã extract {extracted_count} titles từ content")
        
        # Save final file
        self.processor.save_yaml(translated_segments, output_file)
        print(f"✅ Đã save final file: {output_file}")
        
        # Xóa temp file
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
            print(f"🗑️ Đã xóa temp file")
        
        # Log summary
        successful = logger.content_request_count
        failed = len(segments) - successful
        logger.log_summary(
            len(segments), successful, failed, self.client.get_model_name()
        )
        
        print(f"\n🎉 HOÀN THÀNH!")
        print(f"✅ Thành công: {successful}/{len(segments)} segments")
        print(f"📁 Output: {output_file}")
        print(f"📋 Log: {logger.get_log_path()}")
    
    def _run_batch_mode(self, segments: List[Dict]):
        """Chạy workflow mode batch processing."""
        from datetime import datetime
        
        # Tạo timestamp folder
        now = datetime.now()
        date_part = now.strftime("%d%m%y")
        time_part = now.strftime("%H%M")
        timestamp_folder_name = f"{date_part}_{time_part}_{self.sdk_code}_{self.base_name}"
        
        # Tạo output folder
        output_folder = os.path.join(
            self.config['paths']['output_trans'], 
            timestamp_folder_name
        )
        os.makedirs(output_folder, exist_ok=True)
        
        # Tạo log folder
        log_folder_path = os.path.join(
            self.config['paths']['log_trans'],
            timestamp_folder_name
        )
        os.makedirs(log_folder_path, exist_ok=True)
        
        print(f"\n📁 Session Folder: {timestamp_folder_name}")
        print(f"📂 Output: {output_folder}")
        print(f"📋 Logs: {log_folder_path}")
        
        # Split segments thành batches
        batch_config = self.config['batch_processing']
        if batch_config.get('mode') == 'volume':
            batches = self.processor.split_segments_by_volume(segments)
        else:
            chapters_per_batch = batch_config.get('chapters_per_batch', 100)
            batches = self.processor.split_segments_by_chapter_range(
                segments, chapters_per_batch
            )
        
        print(f"📊 Chia thành {len(batches)} batches: {list(batches.keys())}")
        
        # Process từng batch
        total_successful = 0
        total_failed = 0
        batch_files = []
        
        for i, (batch_name, batch_segments) in enumerate(batches.items(), 1):
            print(f"\n{'='*70}")
            print(f"🚀 BATCH {i}/{len(batches)}: {batch_name}")
            print(f"   Segments: {len(batch_segments)}")
            print(f"{'='*70}")
            
            # Process batch
            success_count, batch_file = self._process_batch(
                batch_name, batch_segments, output_folder, timestamp_folder_name
            )
            
            total_successful += success_count
            total_failed += len(batch_segments) - success_count
            batch_files.append(batch_file)
            
            print(f"✅ Batch {batch_name} hoàn thành!")
        
        # Summary tổng kết
        print(f"\n{'='*70}")
        print(f"🎉 HOÀN THÀNH TẤT CẢ {len(batches)} BATCHES!")
        print(f"{'='*70}")
        print(f"✅ Thành công: {total_successful} segments")
        print(f"❌ Thất bại: {total_failed} segments")
        print(f"\n📁 Output files ({len(batch_files)}):")
        for file in batch_files:
            print(f"   {file}")
        print(f"\n📋 Log folder: {log_folder_path}")
    
    def _process_batch(self, batch_name: str, batch_segments: List[Dict], 
                      output_folder: str, timestamp_folder_name: str) -> tuple:
        """
        Process một batch: dịch, clean, save.
        
        Returns:
            (success_count, output_file_path)
        """
        # Setup temp file cho batch này
        self.temp_file = self.processor.create_temp_filename(
            f"{batch_name}_{self.base_name}",
            self.config['paths']['temp_output'],
            self.sdk_code
        )
        
        # Setup logger cho batch (với timestamp folder)
        logger = Logger(
            self.config['paths']['log_trans'],
            f"{batch_name}_{self.base_name}",
            self.sdk_code,
            timestamp_folder=timestamp_folder_name
        )
        
        # Xóa temp file cũ
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
        
        # Dịch content
        print(f"📝 Đang dịch content...")
        self._translate_content(batch_segments, logger)
        
        # Load và sort
        translated_segments = self.processor.load_yaml(self.temp_file)
        translated_segments = self.processor.sort_by_original_order(
            translated_segments, batch_segments
        )
        
        # Dịch titles (nếu enabled)
        translated_titles = {}
        if self.config['title_translation']['enabled'] and self.title_client:
            print(f"🏷️ Đang dịch titles...")
            translated_titles = self._translate_titles(batch_segments, logger)
            if translated_titles:
                print(f"✅ Đã dịch {len(translated_titles)} titles")
        
        # Merge titles
        if translated_titles:
            self._merge_titles(translated_segments, translated_titles)
        
        # Clean
        if self.config['cleaner']['enabled']:
            for segment in translated_segments:
                if 'content' in segment and segment['content']:
                    segment['content'] = self.processor.clean_content(segment['content'])
        
        # Extract titles từ content
        extracted_count = self._extract_titles_from_content(translated_segments)
        if extracted_count > 0:
            print(f"✅ Đã extract {extracted_count} titles từ content")
        
        # Save batch file (naming: gmn_Ch001-100_real_game.yaml)
        batch_filename = f"{self.sdk_code}_{batch_name}_{self.base_name}.yaml"
        batch_output_path = os.path.join(output_folder, batch_filename)
        self.processor.save_yaml(translated_segments, batch_output_path)
        print(f"💾 Saved: {batch_filename}")
        
        # Xóa temp file
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
        
        # Log summary cho batch
        successful = logger.content_request_count
        logger.log_summary(
            len(batch_segments), successful, 
            len(batch_segments) - successful, 
            self.client.get_model_name()
        )
        
        return successful, batch_output_path
    
    def _translate_titles(self, segments: List[Dict], logger: Logger) -> Dict[str, str]:
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
                
                logger.log_segment(
                    f"Title_{chapter_id}", "THÀNH CÔNG", 
                    token_info=token_info
                )
                
                # Delay cho title để tránh quota issues
                time.sleep(title_delay)
                
            except Exception as e:
                print(f"❌ Lỗi dịch title {chapter_id}: {e}")
                logger.log_segment(
                    f"Title_{chapter_id}", "THẤT BẠI", str(e)
                )
                # Giữ nguyên title gốc
                translated_titles[chapter_id] = original_title
        
        return translated_titles
    
    def _translate_content(self, segments: List[Dict], logger: Logger):
        """Dịch content của segments bằng threading và ghi incremental vào temp file."""
        q = queue.Queue()
        lock = threading.Lock()
        processed_count = {'value': 0}
        
        # Đưa segments vào queue
        for segment in segments:
            q.put(segment)
        
        # Threading config
        concurrent_requests = self.config['translate_api']['concurrent_requests']
        num_threads = min(concurrent_requests, len(segments))
        threads = []
        
        print(f"🔧 Sử dụng {num_threads} threads đồng thời...")
        
        # Tạo và chạy threads
        for _ in range(num_threads):
            t = threading.Thread(
                target=self._content_worker,
                args=(q, lock, len(segments), processed_count, logger)
            )
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Đợi hoàn thành
        for t in threads:
            t.join()
    
    def _content_worker(self, q: queue.Queue, lock: threading.Lock, 
                       total_segments: int, processed_count: Dict, logger: Logger):
        """Worker thread để dịch content và ghi vào temp file."""
        while not q.empty():
            try:
                segment = q.get(block=False)
                segment_id = segment['id']
                
                with lock:
                    processed_count['value'] += 1
                    current = processed_count['value']
                    print(f"[{current}/{total_segments}] 📝 {segment_id}")
                
                try:
                    # Dịch content
                    user_prompt = f"\n\n{segment['content']}"
                    
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
                    
                    # Ghi vào temp file ngay (thread-safe)
                    with lock:
                        self.processor.append_segment_to_temp(translated_segment, self.temp_file)
                        logger.log_segment(
                            segment_id, "THÀNH CÔNG", token_info=token_info
                        )
                
                except Exception as e:
                    with lock:
                        # Giữ segment gốc nếu lỗi
                        self.processor.append_segment_to_temp(segment, self.temp_file)
                        logger.log_segment(
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
    
    def _extract_titles_from_content(self, segments: List[Dict]) -> int:
        """
        Extract title từ dòng đầu của content đã dịch và update field title.
        Đây là bước cleanup tự động sau khi dịch xong.
        
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
    
