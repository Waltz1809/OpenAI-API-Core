#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Splitter - Workflow tự động để tách văn bản thành segments
Sử dụng config.json để cấu hình, chỉ cần F5 để chạy
"""

import os
import json
import hashlib
import glob
import fnmatch
from datetime import datetime
from pathlib import Path
import traceback
import sys

# Import enhanced_chapter_splitter functions
# Thêm đường dẫn tới splitter folder relative to script location
script_dir = os.path.dirname(os.path.abspath(__file__))
splitter_path = script_dir  # enhanced_chapter_splitter.py nằm cùng thư mục
sys.path.append(splitter_path)
from enhanced_chapter_splitter import split_and_output

class AutoSplitter:
    def __init__(self, config_file=None):
        """Khởi tạo AutoSplitter với config file"""
        if config_file is None:
            # Tìm config.json trong cùng thư mục với script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(script_dir, "config.json")
        
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = self._find_project_root()
        self.config = self.load_config(config_file)
        self.tracking_data = self.load_tracking()
    
    def _find_project_root(self):
        """Tìm project root directory (thư mục chứa test/, current_work/, etc.)"""
        current_dir = self.script_dir
        while current_dir != os.path.dirname(current_dir):  # Không phải root filesystem
            # Kiểm tra các marker của project root
            if all(os.path.exists(os.path.join(current_dir, marker)) 
                   for marker in ['test', 'current_work']):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        
        # Fallback: sử dụng thư mục hiện tại
        return os.getcwd()
    
    def _resolve_path(self, path):
        """Resolve path relative to project root"""
        if os.path.isabs(path):
            return path
        return os.path.join(self.project_root, path)
        
    def load_config(self, config_file):
        """Load configuration từ JSON file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✅ Loaded config from {os.path.abspath(config_file)}")
            return config
        except FileNotFoundError:
            print(f"❌ Config file {config_file} not found!")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {config_file}: {e}")
            sys.exit(1)
    
    def load_tracking(self):
        """Load tracking data từ JSON file"""
        # Lưu tracking file cùng thư mục với script thay vì project root
        tracking_filename = self.config['tracking_file']
        tracking_file = os.path.join(self.script_dir, tracking_filename)
        if os.path.exists(tracking_file):
            try:
                with open(tracking_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"📋 Loaded tracking data: {len(data)} files tracked")
                return data
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error loading tracking file: {e}")
                return {}
        else:
            print("📋 No tracking file found, starting fresh")
            return {}
    
    def save_tracking(self):
        """Lưu tracking data vào JSON file"""
        # Lưu tracking file cùng thư mục với script thay vì project root
        tracking_filename = self.config['tracking_file']
        tracking_file = os.path.join(self.script_dir, tracking_filename)
        try:
            with open(tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.tracking_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Saved tracking data to {tracking_file}")
        except Exception as e:
            print(f"❌ Error saving tracking: {e}")
    
    def get_file_hash(self, file_path):
        """Tính hash của file để detect thay đổi"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None
    
    def scan_input_files(self):
        """Scan tất cả txt files trong content type directories"""
        base_input_dir = self._resolve_path(self.config['input_base_dir'])
        if not os.path.exists(base_input_dir):
            print(f"❌ Input directory not found: {base_input_dir}")
            return []
        
        files = []
        patterns = self.config['filters']['file_patterns']
        exclude_folders = self.config['filters']['exclude_folders']
        exclude_files = self.config['filters'].get('exclude_files', [])
        min_size = self.config['filters'].get('min_file_size_bytes', 0)
        
        # Scan each content type directory
        for content_type, type_config in self.config['content_types'].items():
            input_dir = os.path.join(base_input_dir, type_config['input_subdir'])
            if not os.path.exists(input_dir):
                print(f"⚠️ Content type directory not found: {input_dir}")
                continue
                
            print(f"🔍 Scanning {content_type} in {input_dir}...")
            
            for root, dirs, filenames in os.walk(input_dir):
                # Remove excluded directories from dirs list
                dirs[:] = [d for d in dirs if d not in exclude_folders]
                
                for filename in filenames:
                    # Check if file matches patterns
                    if any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                        # Check if file is not in exclude list
                        if filename not in exclude_files:
                            file_path = os.path.join(root, filename)
                            
                            # Check file size
                            try:
                                if os.path.getsize(file_path) >= min_size:
                                    files.append(file_path)
                            except OSError:
                                continue
        
        print(f"📁 Found {len(files)} files total to check")
        return sorted(files)
    
    def detect_content_type(self, file_path):
        """Detect content type từ file path"""
        base_input_dir = self._resolve_path(self.config['input_base_dir'])
        rel_path = os.path.relpath(file_path, base_input_dir)
        
        # Check content type từ đầu path
        path_parts = rel_path.split(os.sep)
        if len(path_parts) > 0:
            first_part = path_parts[0]
            for content_type, type_config in self.config['content_types'].items():
                if first_part == type_config['input_subdir']:
                    return content_type, type_config
        
        # Fallback: default to LightNovel nếu không detect được
        return "LightNovel", self.config['content_types']['LightNovel']
    
    def get_relative_path(self, file_path):
        """Lấy relative path từ input base directory"""
        input_dir = self._resolve_path(self.config['input_base_dir'])
        return os.path.relpath(file_path, input_dir)
    
    def get_output_path(self, input_file, mode_name):
        """Tạo output path dựa trên input file, mode và content type"""
        # Detect content type
        content_type, type_config = self.detect_content_type(input_file)
        
        rel_path = self.get_relative_path(input_file)
        
        # Remove content type prefix từ relative path để get internal structure  
        path_parts = rel_path.split(os.sep)
        if len(path_parts) > 1 and path_parts[0] == type_config['input_subdir']:
            internal_path = os.path.join(*path_parts[1:])
            folder = os.path.dirname(internal_path)
        else:
            folder = os.path.dirname(rel_path)
        
        filename = os.path.splitext(os.path.basename(rel_path))[0]
        
        # Smart naming: tránh lặp lại tiền tố folder trong filename
        if folder and os.path.basename(folder) != filename:
            folder_name = os.path.basename(folder)
            
            # Kiểm tra xem filename đã chứa folder_name làm prefix chưa
            # Loại bỏ các số và dấu gạch dưới để so sánh cốt lõi
            def normalize_name(name):
                # Loại bỏ số và dấu gạch dưới ở cuối để so sánh base name
                import re
                return re.sub(r'_?\d+$', '', name.lower())
            
            normalized_folder = normalize_name(folder_name)
            normalized_filename = normalize_name(filename)
            
            # Nếu filename đã bắt đầu bằng folder name (normalized), không thêm prefix
            if normalized_filename.startswith(normalized_folder):
                smart_filename = filename
            else:
                smart_filename = f"{folder_name}_{filename}"
        else:
            smart_filename = filename
        
        # Create output filename with content type specific suffix
        if mode_name == 'segment_mode':
            suffix = type_config['segment_suffix']
        else:  # context_mode
            suffix = self.config['modes']['context_mode']['suffix']
            
        output_filename = f"{smart_filename}_{suffix}.{self.config['global_settings']['output_format']}"
        
        # Create full output path with content type structure
        base_output_dir = self._resolve_path(self.config['output_base_dir'])
        content_output_dir = os.path.join(base_output_dir, type_config['output_subdir'])
        output_dir = os.path.join(content_output_dir, folder) if folder else content_output_dir
        output_path = os.path.join(output_dir, output_filename)
        
        return output_path, content_type, type_config
    
    def needs_processing(self, input_file, output_path, mode_name):
        """Kiểm tra xem file có cần xử lý không"""
        if self.config['run_settings']['force_reprocess']:
            return True, "Force reprocess enabled"
        
        rel_path = self.get_relative_path(input_file)
        
        # Check if output file exists
        if not os.path.exists(output_path):
            return True, "Output file not found"
        
        # Check tracking data
        if rel_path not in self.tracking_data:
            return True, "Not in tracking history"
        
        file_data = self.tracking_data[rel_path]
        
        # Check if this mode was processed
        if mode_name not in file_data.get('modes', {}):
            return True, f"Mode {mode_name} not processed"
        
        # Check file hash if available
        current_hash = self.get_file_hash(input_file)
        stored_hash = file_data.get('file_hash')
        
        if current_hash and stored_hash and current_hash != stored_hash:
            return True, "File content changed"
        
        return False, "Already processed"
    
    def process_file(self, input_file, mode_name):
        """Xử lý một file với một mode cụ thể"""
        output_path, content_type, type_config = self.get_output_path(input_file, mode_name)
        
        # Check if processing is needed
        needs_proc, reason = self.needs_processing(input_file, output_path, mode_name)
        
        if not needs_proc:
            return {'status': 'skip', 'reason': reason, 'output': output_path, 'content_type': content_type}
        
        try:
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get mode config from content type
            mode_config = self.config['modes'][mode_name]
            if mode_name == 'segment_mode':
                max_chars = type_config['segment_chars']
            else:  # context_mode
                max_chars = type_config['context_chars']
            
            # Call the splitter với sorting logic mới
            print(f"    🔄 Processing với sorting logic...")
            split_and_output(
                file_path=input_file,
                max_chars=max_chars,
                max_chapter=self.config['global_settings']['max_chapter'],
                output_path=output_path,
                mode=mode_config['mode'],
                output_format=self.config['global_settings']['output_format']
            )
            
            # Update tracking
            self.update_tracking(input_file, mode_name, output_path)
            
            return {'status': 'success', 'reason': reason, 'output': output_path, 'content_type': content_type}
            
        except Exception as e:
            error_msg = f"Error processing {input_file} in {mode_name}: {str(e)}"
            self.log_error(error_msg, traceback.format_exc())
            return {'status': 'error', 'reason': str(e), 'output': output_path, 'content_type': content_type}
    
    def update_tracking(self, input_file, mode_name, output_path):
        """Cập nhật tracking data"""
        rel_path = self.get_relative_path(input_file)
        
        if rel_path not in self.tracking_data:
            self.tracking_data[rel_path] = {
                'modes': {},
                'file_hash': self.get_file_hash(input_file),
                'last_updated': datetime.now().isoformat()
            }
        
        self.tracking_data[rel_path]['modes'][mode_name] = {
            'processed_date': datetime.now().isoformat(),
            'output_file': output_path
        }
        self.tracking_data[rel_path]['file_hash'] = self.get_file_hash(input_file)
        self.tracking_data[rel_path]['last_updated'] = datetime.now().isoformat()
    
    def log_error(self, message, traceback_str=""):
        """Log error to file if enabled"""
        if not self.config['run_settings']['log_errors']:
            return
        
        # Lưu error log cùng thư mục với script thay vì project root
        error_filename = self.config['run_settings']['error_log_file']
        error_file = os.path.join(self.script_dir, error_filename)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(error_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} | ERROR | {message}\n")
                if traceback_str:
                    f.write(f"{traceback_str}\n")
                f.write("-" * 50 + "\n")
        except Exception:
            pass  # Ignore logging errors
    
    def print_summary(self, results):
        """In tổng kết kết quả"""
        total = len(results)
        success = len([r for r in results if r['status'] == 'success'])
        skipped = len([r for r in results if r['status'] == 'skip'])
        errors = len([r for r in results if r['status'] == 'error'])
        
        print(f"\n📊 SUMMARY:")
        print(f"Total operations: {total}")
        print(f"✅ Success: {success}")
        print(f"⏭️ Skipped: {skipped}")
        print(f"❌ Errors: {errors}")
        
        # Summary by content type
        content_type_stats = {}
        for result in results:
            content_type = result.get('content_type', 'Unknown')
            if content_type not in content_type_stats:
                content_type_stats[content_type] = {'success': 0, 'skip': 0, 'error': 0}
            content_type_stats[content_type][result['status']] += 1
        
        if content_type_stats:
            print(f"\n📚 By Content Type:")
            for content_type, stats in content_type_stats.items():
                total_type = sum(stats.values())
                print(f"  {content_type}: {total_type} ops (✅{stats['success']} ⏭️{stats['skip']} ❌{stats['error']})")
        
        if errors > 0:
            print(f"\n❌ Files with errors:")
            for result in results:
                if result['status'] == 'error':
                    content_type = result.get('content_type', 'Unknown')
                    print(f"  - [{content_type}] {result.get('file', 'Unknown')}: {result['reason']}")
    
    def run_dry_run(self):
        """Chạy dry run để preview"""
        print("🔍 DRY RUN MODE - Preview các file sẽ được xử lý:\n")
        print("🔄 Sorting Logic: Chapters sẽ được sắp xếp đúng thứ tự\n")
        
        # Check if we would be in auto_process_missing mode
        is_auto_missing = self.config['run_settings'].get('auto_process_missing', False)
        if is_auto_missing:
            print("ℹ️ Note: auto_process_missing = true → chỉ những operations 🆕 sẽ được thực hiện\n")
        
        files = self.scan_input_files()
        preview_data = {}
        
        for file_path in files:
            # Detect content type
            content_type, type_config = self.detect_content_type(file_path)
            rel_path = self.get_relative_path(file_path)
            
            # Group by content type
            if content_type not in preview_data:
                preview_data[content_type] = {}
            
            # Remove content type prefix từ path để get internal structure
            path_parts = rel_path.split(os.sep)
            if len(path_parts) > 1 and path_parts[0] == type_config['input_subdir']:
                internal_path = os.path.join(*path_parts[1:])
                folder = os.path.dirname(internal_path) or "root"
            else:
                folder = os.path.dirname(rel_path) or "root"
            
            if folder not in preview_data[content_type]:
                preview_data[content_type][folder] = []
            
            file_info = {'file': os.path.basename(file_path), 'modes': []}
            
            # Check each enabled mode
            for mode_name, mode_config in self.config['modes'].items():
                if not mode_config.get('enabled', False):
                    continue
                
                output_path, _, _ = self.get_output_path(file_path, mode_name)
                needs_proc, reason = self.needs_processing(file_path, output_path, mode_name)
                
                status = "🆕" if needs_proc else "✅"
                action = "sẽ tạo mới" if needs_proc else "đã tồn tại, skip"
                
                # Get suffix based on mode and content type
                if mode_name == 'segment_mode':
                    suffix = type_config['segment_suffix']
                else:
                    suffix = self.config['modes']['context_mode']['suffix']
                
                file_info['modes'].append({
                    'mode': mode_name,
                    'suffix': suffix,
                    'status': status,
                    'action': action,
                    'max_chars': type_config['segment_chars'] if mode_name == 'segment_mode' else type_config['context_chars']
                })
            
            preview_data[content_type][folder].append(file_info)
        
        # Print preview grouped by content type
        total_operations = 0
        new_operations = 0
        
        for content_type, folders in preview_data.items():
            type_config = self.config['content_types'][content_type]
            print(f"📚 {content_type} ({type_config['description']}):")
            
            for folder, files_info in folders.items():
                print(f"  📂 {folder}/")
                for file_info in files_info:
                    for mode_info in file_info['modes']:
                        # Smart naming preview
                        base_filename = os.path.splitext(file_info['file'])[0]
                        if folder != "root" and folder != base_filename:
                            smart_filename = f"{folder}_{base_filename}"
                        else:
                            smart_filename = base_filename
                        
                        output_name = f"{smart_filename}_{mode_info['suffix']}.yaml"
                        print(f"    {mode_info['status']} {file_info['file']} → {output_name} ({mode_info['action']}) [{mode_info['max_chars']} chars]")
                        total_operations += 1
                        if mode_info['status'] == "🆕":
                            new_operations += 1
                print()
            print()
        
        if is_auto_missing:
            print(f"Tổng: {new_operations}/{total_operations} operations → auto_process_missing sẽ chỉ thực hiện {new_operations} operations 🆕")
        else:
            print(f"Tổng: {new_operations}/{total_operations} operations sẽ được thực hiện")
    
    def get_missing_operations(self, files):
        """Filter ra chỉ những operations cần thiết (missing files)"""
        missing_operations = []
        
        for file_path in files:
            for mode_name, mode_config in self.config['modes'].items():
                if not mode_config.get('enabled', False):
                    continue
                
                # Check if this operation is needed
                output_path, _, _ = self.get_output_path(file_path, mode_name)
                needs_proc, reason = self.needs_processing(file_path, output_path, mode_name)
                
                if needs_proc:
                    missing_operations.append((file_path, mode_name))
        
        return missing_operations
    
    def run(self):
        """Main workflow"""
        print("🚀 AUTO SPLITTER STARTED")
        print("=" * 50)
        
        # Print config summary
        enabled_modes = [name for name, config in self.config['modes'].items() if config.get('enabled', False)]
        print(f"📋 Enabled modes: {', '.join(enabled_modes)}")
        print("🔄 Sorting Logic: Chapters sẽ được sắp xếp đúng thứ tự")
        
        # Print run mode
        if self.config['run_settings']['dry_run']:
            print("🔍 Mode: DRY RUN (Preview only)")
        elif self.config['run_settings'].get('auto_process_missing', False):
            print("🎯 Mode: AUTO PROCESS MISSING (Smart mode - chỉ xử lý files thiếu)")
        elif self.config['run_settings']['force_reprocess']:
            print("🔄 Mode: FORCE REPROCESS (Xử lý lại tất cả)")
        else:
            print("📁 Mode: NORMAL (Xử lý tất cả)")
        
        # Print content types info
        base_input = self._resolve_path(self.config['input_base_dir'])
        base_output = self._resolve_path(self.config['output_base_dir'])
        print(f"📍 Project Root: {self.project_root}")
        print(f"📁 Content Types:")
        for content_type, type_config in self.config['content_types'].items():
            input_dir = os.path.join(base_input, type_config['input_subdir'])
            output_dir = os.path.join(base_output, type_config['output_subdir'])
            print(f"  📚 {content_type}: {type_config['segment_chars']}chars → {input_dir}")
            print(f"    Output: {output_dir}")
        
        if self.config['run_settings']['dry_run']:
            self.run_dry_run()
            return
        
        # Get files to process
        files = self.scan_input_files()
        if not files:
            print("ℹ️ No files found to process")
            return
        
        # Pre-filter files for auto_process_missing mode
        if self.config['run_settings'].get('auto_process_missing', False):
            filtered_operations = self.get_missing_operations(files)
            print(f"🎯 Auto Process Missing: Found {len(filtered_operations)} missing operations to process")
        else:
            # Normal mode: process all
            filtered_operations = []
            for file_path in files:
                for mode_name, mode_config in self.config['modes'].items():
                    if mode_config.get('enabled', False):
                        filtered_operations.append((file_path, mode_name))
        
        if not filtered_operations:
            print("ℹ️ No operations needed - all files are up to date!")
            return
        
        # Process files
        results = []
        total_operations = len(filtered_operations)
        current_op = 0
        
        current_file = None
        for file_path, mode_name in filtered_operations:
            rel_path = self.get_relative_path(file_path)
            
            # Print file header only once per file
            if file_path != current_file:
                print(f"\n📄 Processing: {rel_path}")
                current_file = file_path
            
            # Detect content type for progress info
            content_type, type_config = self.detect_content_type(file_path)
            
            current_op += 1
            
            if self.config['run_settings']['show_progress']:
                progress = (current_op / total_operations) * 100
                mode_config = self.config['modes'][mode_name]
                print(f"  [{progress:5.1f}%] {content_type} - {mode_name} ({mode_config['description']})...")
            
            result = self.process_file(file_path, mode_name)
            result['file'] = rel_path
            result['mode'] = mode_name
            results.append(result)
            
            # Print result with content type info
            if result['status'] == 'success':
                print(f"    ✅ Created: {os.path.basename(result['output'])} [{result['content_type']}]")
            elif result['status'] == 'skip':
                print(f"    ⏭️ Skipped: {result['reason']} [{result['content_type']}]")
            else:
                print(f"    ❌ Error: {result['reason']} [{result['content_type']}]")
        
        # Save tracking
        self.save_tracking()
        
        # Print summary
        self.print_summary(results)
        print("\n🎉 AUTO SPLITTER COMPLETED!")

def main():
    """Entry point"""
    try:
        splitter = AutoSplitter()
        splitter.run()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 