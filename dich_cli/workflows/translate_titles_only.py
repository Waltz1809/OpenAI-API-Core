#!/usr/bin/env python3
"""
Translate Titles Only Workflow - Dịch titles riêng và patch vào file gốc từ config
Workflow này:
1. Đọc titles từ file được chỉ định (config hoặc nhập vào)
2. Dịch titles
3. Patch vào file source_yaml_file từ config (tạo backup trước)
"""

import os
import time
from typing import Dict, List

from core.ai_factory import AIClientFactory
from core.yaml_processor import YamlProcessor
from core.logger import Logger
from core.path_helper import get_path_helper


class TranslateTitlesOnlyWorkflow:
    """
    Workflow để dịch title riêng và patch vào file gốc từ config.
    - Đọc titles: từ file được chỉ định (config/user input)
    - Patch vào: luôn là source_yaml_file từ config (có backup)
    """
    
    def __init__(self, config: Dict, secret: Dict):
        self.config = config
        self.secret = secret
        self.processor = YamlProcessor()
        
        # Setup API client cho title
        self.title_client = AIClientFactory.create_client(config['title_api'], secret)
        
        # Load title prompt
        self.title_prompt = self._load_prompt(config['paths']['title_prompt_file'])
        
        # Get SDK code
        self.sdk_code = AIClientFactory.get_sdk_code(config['title_api'])
        
        # Temp file for tracking progress
        base_name = self.processor.get_base_name(config['active_task']['source_yaml_file'])
        self.temp_file = self.processor.create_temp_filename(
            f"{base_name}_titles",
            config['paths']['temp_output'],
            self.sdk_code
        )
        
        print(f"🔧 SDK: {self.sdk_code.upper()}")
        print(f"🏷️ Title Model: {self.title_client.get_model_name()}")
        print(f"💾 Temp: {self.temp_file}")
        
        # Hiển thị multi-key info
        title_provider = self.config['title_api']['provider']
        if AIClientFactory.has_multiple_keys(title_provider):
            key_status = AIClientFactory.get_key_rotator_status()
            title_keys = key_status.get(title_provider, {}).get('key_count', 1)
            print(f"🔑 Title Keys: {title_keys} keys (round-robin)")
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt từ file."""
        ph = get_path_helper()
        resolved_path = ph.resolve(prompt_file)
        
        if not ph.exists(resolved_path):
            raise FileNotFoundError(f"Prompt file không tồn tại: {prompt_file}")
        
        with open(resolved_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def run(self):
        """Chạy workflow chính."""
        try:
            # Lấy file path từ user để load titles gốc
            source_file = self._get_file_path()
            
            if not source_file or not os.path.exists(source_file):
                print(f"❌ File không tồn tại: {source_file}")
                return
            
            print(f"\n📖 Đang load file YAML: {source_file}")
            segments = self.processor.load_yaml(source_file)
            print(f"📊 Tổng cộng {len(segments)} segments")
            
            # Lấy unique chapters
            unique_chapters = self.processor.get_unique_chapters(segments)
            
            if not unique_chapters:
                print("❌ Không tìm thấy chapter nào để dịch title!")
                return
            
            print(f"🏷️ Tìm thấy {len(unique_chapters)} chapter titles cần dịch")
            
            # Tạo logger
            base_name = self.processor.get_base_name(source_file)
            logger = Logger(
                os.path.dirname(source_file),
                f"{base_name}_titles",
                self.sdk_code
            )
            
            # Xóa temp file cũ nếu có
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
            
            # Dịch titles (ghi incremental vào temp)
            print("\n🏷️ Đang dịch titles...")
            translated_titles = self._translate_titles(unique_chapters, logger)
            print(f"✅ Đã dịch {len(translated_titles)} titles")
            
            # Merge titles vào segments
            print("\n🔄 Đang merge titles...")
            self._merge_titles(segments, translated_titles)
            
            # Ghi segments với titles mới vào temp file
            print(f"💾 Đang save temp file...")
            self.processor.save_yaml(segments, self.temp_file)
            
            # Lấy target file để patch (luôn là source_yaml_file từ config)
            target_file = self.config['active_task']['source_yaml_file']
            
            # Tạo backup trước khi patch
            backup_file = self._create_backup(target_file)
            print(f"💾 Đã tạo backup: {backup_file}")
            
            # Patch vào file gốc từ config
            print(f"\n🔧 Đang patch titles vào file gốc: {target_file}...")
            self.processor.save_yaml(segments, target_file)
            
            # Xóa temp file
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
            
            # Log summary
            successful = len([v for v in translated_titles.values() if v])
            failed = len(unique_chapters) - successful
            logger.log_summary(
                len(unique_chapters), successful, failed, 
                self.title_client.get_model_name()
            )
            
            print(f"\n🎉 HOÀN THÀNH!")
            print(f"✅ Thành công: {successful}/{len(unique_chapters)} titles")
            print(f"📖 Source đọc: {source_file}")
            print(f"📁 File đã được patch: {target_file}")
            print(f"💾 Backup: {backup_file}")
            print(f"📋 Log: {logger.get_log_path()}")
            
        except Exception as e:
            print(f"❌ Lỗi trong translate titles workflow: {e}")
            raise
    
    def _get_file_path(self) -> str:
        """Lấy file path từ user input để đọc titles gốc."""
        ph = get_path_helper()
        
        print("\n" + "="*60)
        print("  DỊCH TITLES - Nhập file để đọc titles gốc")
        print("="*60)
        print("Ví dụ: data/yaml/output/WebNovel/master/master_70.yaml")
        print("Hoặc nhấn Enter để dùng file trong config")
        print("Lưu ý: Titles sẽ được patch vào source_yaml_file từ config")
        print(f"Project root: {ph.project_root}")
        print("="*60)
        
        user_input = input("\nĐường dẫn file: ").strip()
        
        if not user_input:
            # Dùng file từ config (đã là relative path)
            return self.config['active_task']['source_yaml_file']
        
        # PathHelper tự động xử lý relative/absolute
        return user_input
    
    def _create_backup(self, input_file: str) -> str:
        """Tạo backup file trước khi patch."""
        import shutil
        from datetime import datetime
        
        base_dir = os.path.dirname(input_file)
        base_name = self.processor.get_base_name(input_file)
        
        now = datetime.now()
        date_part = now.strftime("%d%m%y")
        time_part = now.strftime("%H%M")
        
        backup_filename = f"{date_part}_{time_part}_backup_{base_name}.yaml"
        backup_path = os.path.join(base_dir, backup_filename)
        
        # Copy file gốc sang backup
        shutil.copy2(input_file, backup_path)
        
        return backup_path
    
    def _translate_titles(self, unique_chapters: Dict[str, str], logger: Logger) -> Dict[str, str]:
        """Dịch titles của các chapters unique."""
        translated_titles = {}
        title_delay = self.config['title_api'].get('delay', 3)
        
        total = len(unique_chapters)
        current = 0
        
        for chapter_id, original_title in unique_chapters.items():
            current += 1
            try:
                print(f"[{current}/{total}] 🏷️ {chapter_id}: {original_title[:50]}...")
                
                content, token_info = self.title_client.generate_content(
                    self.title_prompt,
                    original_title
                )
                
                # Clean title result
                translated_title = content.strip().replace('"', '').replace('\\n', '\n')
                translated_titles[chapter_id] = translated_title
                
                print(f"           ✅ {translated_title}")
                
                logger.log_segment(
                    f"Title_{chapter_id}", "THÀNH CÔNG", 
                    token_info=token_info
                )
                
                # Delay để tránh quota issues
                if current < total:  # Không delay ở lần cuối
                    time.sleep(title_delay)
                
            except Exception as e:
                print(f"           ❌ Lỗi: {e}")
                logger.log_segment(
                    f"Title_{chapter_id}", "THẤT BẠI", str(e)
                )
                # Giữ nguyên title gốc
                translated_titles[chapter_id] = original_title
        
        return translated_titles
    
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

