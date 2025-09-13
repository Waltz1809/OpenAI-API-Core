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
    
    def __init__(self, config: Dict, secret: Dict, input_file: str | None = None, output_base_override: str | None = None):
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
        # Explicit input file is required; legacy source_yaml_file fallback removed
        if not input_file:
            raise ValueError("TranslateWorkflow now requires explicit input_file (legacy source_yaml_file removed).")
        self.input_file = input_file
        self.base_name = self.processor.get_base_name(self.input_file)
        
        # Get SDK code from factory
        self.sdk_code = AIClientFactory.get_sdk_code(config['translate_api'])
        
        # Output files with forced directory mirroring of input tree
        base_output_dir = output_base_override or config['paths']['output_trans']
        input_root_cfg = config['active_task'].get('input_dir', '')
        if input_root_cfg and not os.path.isabs(input_root_cfg):
            # cwd is project root (set in main), so join
            input_root_abs = os.path.abspath(input_root_cfg)
        else:
            input_root_abs = input_root_cfg or ''

        rel_dir = ''
        try:
            if input_root_abs and os.path.commonpath([input_root_abs, os.path.abspath(self.input_file)]) == os.path.abspath(input_root_abs):
                rel_path = os.path.relpath(self.input_file, input_root_abs)
                rel_dir = os.path.dirname(rel_path)
        except Exception:
            rel_dir = ''  # fallback: ignore mirroring if any issue

        # Construct mirrored output directory
        if rel_dir and rel_dir not in ('.', ''):
            mirrored_output_dir = os.path.join(base_output_dir, rel_dir)
        else:
            mirrored_output_dir = base_output_dir

        self.output_file = self.processor.create_output_filename(
            self.input_file,
            mirrored_output_dir,
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
            
            print(f"📊 Tổng cộng {len(segments)} segments cần xử lý")
            
            # 2. Dịch content trước
            print("\n📝 Đang dịch content...")
            translated_segments, failed_ids = self._translate_content(segments)
            
            # 3. Retry tự động các segments thất bại (nếu có)
            if failed_ids:
                print(f"\n🔄 Tự động retry {len(failed_ids)} segments lỗi...")
                retry_limit = self.config['translate_api'].get('max_retries', 0)
                if retry_limit > 0:
                    retry_fixed = self._retry_failed_segments(failed_ids, segments, retry_limit)
                    # Patch vào translated_segments
                    if retry_fixed:
                        fixed_map = {s['id']: s for s in retry_fixed}
                        for i, seg in enumerate(translated_segments):
                            if seg['id'] in fixed_map:
                                translated_segments[i] = fixed_map[seg['id']]
                    remaining_failed = [fid for fid in failed_ids if fid not in {s['id'] for s in retry_fixed}]
                    if remaining_failed:
                        print(f"⚠️ Còn {len(remaining_failed)} segments vẫn lỗi sau retry: {remaining_failed[:5]}{'...' if len(remaining_failed)>5 else ''}")
                else:
                    print("⚠️ Retry bị tắt (max_retries=0)")

            # 4. Dịch titles sau (nếu enabled)
            translated_titles = {}
            if self.config['title_translation']['enabled'] and self.title_client:
                per_file = self.config['title_translation'].get('per_file', False)
                if per_file:
                    print("\n🏷️ Dịch title cho toàn bộ file (per_file=true)...")
                    translated_titles = self._translate_file_title_once(segments)
                    if translated_titles:
                        print("✅ Đã dịch title file 1 lần")
                    else:
                        print("⚠️ Không tìm thấy title hợp lệ để dịch (giữ nguyên)")
                else:
                    print("\n🏷️ Đang dịch titles từng chapter...")
                    translated_titles = self._translate_titles(segments)
                    print(f"✅ Đã dịch {len(translated_titles)} titles")

            # 5. Merge titles vào segments
            if translated_titles:
                # Log the translated title for this file
                translated_title = next(iter(translated_titles.values())) if translated_titles else None
                print(f"\n🔄 Đang merge titles...")
                if translated_title:
                    print(f"🏷️ Translated file title (API response): {translated_title}")
                    self.logger.log_segment("File_Title", "TITLE_TRANSLATED", translated_title)
                self._merge_titles(translated_segments, translated_titles, per_file=per_file)


                # Log the final title of each segment for debugging
                for i, seg in enumerate(translated_segments):
                    print(f"[Segment {i}] Final title: {seg.get('title')}")
            
            # 6. Save temp file trước
            temp_output_file = os.path.join(
                os.path.dirname(self.output_file), 
                f"temp_{os.path.basename(self.output_file)}"
            )
            print(f"\n💾 Đang save temp file: {os.path.basename(temp_output_file)}...")
            self.processor.save_yaml(translated_segments, temp_output_file)
            print(f"✅ Kết quả dịch thô lưu tại: {temp_output_file}")
            
            # 7. Clean từ temp file -> final file
            print(f"\n🧹 Đang clean từ temp file...")
            self._clean_yaml_file(temp_output_file, self.output_file)
            print(f"✅ Clean hoàn thành! File cuối cùng: {self.output_file}")
            
            # 8. Xóa temp file
            if os.path.exists(temp_output_file):
                os.remove(temp_output_file)
                print(f"🗑️ Đã xóa temp file: {os.path.basename(temp_output_file)}")
            
            # 9. Log summary - đếm từ logger stats
            successful = self.logger.request_count  # Số request thành công (có token_info)
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
        """Translate titles of each segment individually using the title client."""
        if not segments:
            return {}
        
        translated_titles = {}
        title_delay = self.config['title_api'].get('delay', 3)
        
        for segment in segments:
            seg_id = segment.get('id')
            original_title = segment.get('title', '').strip()
            
            if not original_title:
                # Nothing to translate → keep empty
                translated_titles[seg_id] = original_title
                continue
            
            try:
                print(f"🏷️ Dịch title cho segment {seg_id}...")
                
                if self.title_client is None:
                    print("❌ Title client không được khởi tạo")
                    translated_titles[seg_id] = original_title
                    continue
                
                content, token_info = self.title_client.generate_content(
                    self.title_prompt,
                    original_title
                )
                
                translated_title = content.strip().replace('"', '').replace('\\n', '\n')
                translated_titles[seg_id] = translated_title
                
                self.logger.log_segment(
                    f"Title_{seg_id}", "THÀNH CÔNG", token_info=token_info
                )
                
                time.sleep(title_delay)  # avoid quota issues
                
            except Exception as e:
                print(f"❌ Lỗi dịch title {seg_id}: {e}")
                self.logger.log_segment(
                    f"Title_{seg_id}", "THẤT BẠI", str(e)
                )
                # Fallback: keep original
                translated_titles[seg_id] = original_title
        
        return translated_titles


    def _translate_file_title_once(self, segments: List[Dict]) -> Dict[str, str]:
        """Translate one representative title and apply to all segments."""
        if not segments:
            return {}
        
        # Pick the first non-empty original title
        first_title = next(
            (s.get('title', '').strip() for s in segments if s.get('title', '').strip()),
            ''
        )
        print(f"[DEBUG] Extracted first_title before translation: '{first_title}'")
        self.logger.log_segment("File_Title", "EXTRACTED_FIRST_TITLE", first_title)
        
        if not first_title:
            first_title = "No Title"
            for seg in segments:
                seg['title'] = first_title
        
        translated: Dict[str, str] = {}
        try:
            content, token_info = self.title_client.generate_content(  # type: ignore
                self.title_prompt,
                first_title
            )
            unified_title = content.strip().replace('"', '').replace('\\n', '\n')
            
            # Apply to all segments (map by id)
            for seg in segments:
                seg_id = seg.get('id')
                if seg_id:
                    translated[seg_id] = unified_title
            
            # Log once
            self.logger.log_segment("File_Title", "THÀNH CÔNG", token_info=token_info)
        except Exception as e:
            self.logger.log_segment("File_Title", "THẤT BẠI", str(e))
            return {}
        
        return translated

    
    def _translate_content(self, segments: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Dịch content của segments bằng threading. Trả về (segments, failed_ids)."""
        from core.key_rotator import KeyRotator
        q = queue.Queue()
        result_dict: Dict[int, Dict | None] = {}
        lock = threading.Lock()
        self._failed_ids: List[str] = []  # reset collector

        for idx, segment in enumerate(segments):
            q.put((idx, segment))
            result_dict[idx] = None

        concurrent_requests = self.config['translate_api']['concurrent_requests']
        num_threads = min(concurrent_requests, len(segments)) or 1
        print(f"🔧 Sử dụng {num_threads} threads đồng thời...")

        # Setup key rotator and assign a client per thread
        key_rotator = KeyRotator(self.secret)
        provider = self.config['translate_api']['provider']
        thread_clients = []
        for i in range(num_threads):
            key = key_rotator.get_next_key(provider)
            thread_secret = self.secret.copy()
            if key:
                # Patch the API key for this thread
                if provider == 'gemini':
                    thread_secret['gemini_api_key'] = key.get('api_key')
                elif provider == 'openai':
                    thread_secret['openai_api_key'] = key.get('api_key')
                # Add other providers as needed
            client = AIClientFactory.create_client(self.config['translate_api'], thread_secret)
            thread_clients.append(client)

        threads: List[threading.Thread] = []
        for i in range(num_threads):
            t = threading.Thread(target=self._content_worker, args=(q, result_dict, lock, len(segments), thread_clients[i]))
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        results = [result_dict[i] for i in sorted(result_dict.keys()) if result_dict[i] is not None]
        return results, list(self._failed_ids)
    
    def _content_worker(self, q: queue.Queue, result_dict: Dict, 
                       lock: threading.Lock, total_segments: int, client):
        """Worker thread để dịch content, mỗi thread dùng client riêng."""
        delay = self.config['translate_api'].get('delay', 1)
        while True:
            try:
                idx, segment = q.get_nowait()
                segment_id = segment['id']

                with lock:
                    processed = len([v for v in result_dict.values() if v is not None])
                    print(f"[{processed + 1}/{total_segments}] 📝 {segment_id}")

                try:
                    # Dịch content
                    user_prompt = f"\n\n{segment['content']}"

                    content, token_info = client.generate_content(
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
                        result_dict[idx] = segment  # mark attempted
                        self.logger.log_segment(segment_id, "THẤT BẠI", str(e))
                        # Track failure id
                        # Use a list on self to aggregate
                        if not hasattr(self, '_failed_ids'):
                            self._failed_ids = []
                        self._failed_ids.append(segment_id)

                q.task_done()
                time.sleep(delay)
            except queue.Empty:
                break
    
    def _merge_titles(self, segments: List[Dict], translated_titles: Dict[str, str], per_file: bool = False):
        """Merge translated titles back into segments (supports per_file and per_segment)."""
        if not translated_titles:
            return
        
        if per_file:
            # All values in translated_titles are identical → take one
            unified_title = next(iter(translated_titles.values()))
            for i, segment in enumerate(segments):
                old_title = segment.get('title')
                segment['title'] = unified_title
                print(f"[Overwrite] Segment {i} title: '{old_title}' → '{unified_title}'")
        else:
            # Match by segment id
            for i, segment in enumerate(segments):
                seg_id = segment.get('id')
                if seg_id in translated_titles:
                    old_title = segment.get('title')
                    new_title = translated_titles[seg_id]
                    segment['title'] = new_title
                    print(f"[Merge] Segment {i} ({seg_id}) title: '{old_title}' → '{new_title}'")


    
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

    def _retry_failed_segments(self, failed_ids: List[str], original_segments: List[Dict], max_retries: int) -> List[Dict]:
        """Retry các segment thất bại sử dụng cùng client.

        Args:
            failed_ids: danh sách id lỗi từ lượt đầu
            original_segments: toàn bộ segments gốc
            max_retries: số lần thử tối đa cho mỗi segment
        Returns:
            List[Dict]: các segment đã dịch thành công trong retry
        """
        id_map = {s['id']: s for s in original_segments}
        fixed: List[Dict] = []
        for seg_id in failed_ids:
            if seg_id not in id_map:
                continue
            original = id_map[seg_id]
            attempt = 0
            success = False
            last_error = None
            while attempt < max_retries and not success:
                attempt += 1
                try:
                    user_prompt = f"\n\n{original['content']}"
                    content, token_info = self.client.generate_content(self.content_prompt, user_prompt)
                    translated_segment = {
                        'id': original['id'],
                        'title': original['title'],
                        'content': content
                    }
                    fixed.append(translated_segment)
                    self.logger.log_segment(seg_id, f"THÀNH CÔNG (retry {attempt})", token_info=token_info)
                    success = True
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        time.sleep(min(2 ** attempt, 30))  # simple backoff
            if not success:
                self.logger.log_segment(seg_id, f"THẤT BẠI sau {max_retries} retry", last_error)
        return fixed
