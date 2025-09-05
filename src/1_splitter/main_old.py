#!/usr/bin/env python3
"""
Text Splitter Module
Splits text files into segments for processing by translation pipeline.
"""

import os
import yaml
import pathlib
from typing import List, Dict, Any, Set, Tuple
import re
import json
import hashlib
from datetime import datetime


class TextSplitter:
    """Handles splitting of text files into manageable segments."""
    
    def __init__(self, config_path: str = None):
        """Initialize the splitter with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yml")
        
        self.config = self._load_config(config_path)
        self.project_root = self._get_project_root()
        self.processed_files = set()
        self.log_file = None
        
        # Validate required config sections
        self._validate_config()
        
        logging_config = self.config.get('logging')
        if logging_config and logging_config.get('enable_logging', True):
            self._setup_logging()
            self._load_processed_files()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")
    
    def _validate_config(self):
        """Validate that all required configuration sections and parameters exist."""
        # Check main sections
        required_sections = ['paths', 'processing', 'logging']
        for section in required_sections:
            if section not in self.config:
                raise Exception(f"Required config section '{section}' is missing")
        
        # Check paths section
        paths_config = self.config['paths']
        required_paths = ['input', 'output', 'logs']
        for path in required_paths:
            if not paths_config.get(path):
                raise Exception(f"Required config parameter 'paths.{path}' is missing")
        
        # Check processing section
        processing_config = self.config['processing']
        required_processing = ['file_types', 'segment_length']
        for param in required_processing:
            if not processing_config.get(param):
                raise Exception(f"Required config parameter 'processing.{param}' is missing")
        
        # Validate file_types is a list
        if not isinstance(processing_config['file_types'], list):
            raise Exception("'processing.file_types' must be a list")
        
        # Validate segment_length is a number
        if not isinstance(processing_config['segment_length'], int) or processing_config['segment_length'] <= 0:
            raise Exception("'processing.segment_length' must be a positive integer")
        
        # Check logging section
        logging_config = self.config['logging']
        required_logging = ['enable_logging', 'skip_processed']
        for param in required_logging:
            if param not in logging_config:
                raise Exception(f"Required config parameter 'logging.{param}' is missing")
    
    def _get_project_root(self) -> pathlib.Path:
        """Get the project root directory - always set to OpenAI-API-Core repo folder."""
        current_dir = pathlib.Path(__file__).resolve().parent
        
        # Go up until we find the OpenAI-API-Core directory
        while current_dir != current_dir.parent:
            if current_dir.name == "OpenAI-API-Core":
                print(f"Found OpenAI-API-Core directory: {current_dir}")
                # Change working directory to the repo root
                import os
                os.chdir(current_dir)
                print(f"Changed working directory to: {current_dir}")
                return current_dir
            current_dir = current_dir.parent
        
        # If we can't find OpenAI-API-Core, raise an error
        raise Exception(f"Could not find OpenAI-API-Core directory. Started from: {pathlib.Path(__file__).resolve().parent}")
    
    
    def _setup_logging(self):
        """Setup logging directory and files."""
        if not self.config.get('logging', {}).get('enable_logging', True):
            return
        
        # Get log path from config, no hardcoded fallback
        log_path = self.config.get('paths', {}).get('logs')
        if not log_path:
            raise Exception("Log path must be specified in config under 'paths.logs'")
            
        log_dir = self.project_root / log_path
        log_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Setting up logging in: {log_dir}")
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"splitter_log_{timestamp}.txt"
        self.processed_log_file = log_dir / "processed_files.json"
        
        # Initialize log file
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"Text Splitter Log - Started at {datetime.now()}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Project Root: {self.project_root}\n")
            f.write(f"Config: {self.config}\n")
            f.write("=" * 50 + "\n\n")
    
    def _load_processed_files(self):
        """Load list of previously processed files."""
        logging_config = self.config.get('logging')
        if not logging_config:
            raise Exception("'logging' section is required in config")
        
        if not logging_config.get('enable_logging', True) or not logging_config.get('skip_processed', True):
            return
            
        try:
            if hasattr(self, 'processed_log_file') and self.processed_log_file.exists():
                with open(self.processed_log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                self._log(f"Loaded {len(self.processed_files)} previously processed files")
        except Exception as e:
            self._log(f"Warning: Could not load processed files log: {e}")
            self.processed_files = set()
    
    def _save_processed_files(self):
        """Save list of processed files."""
        logging_config = self.config.get('logging')
        if not logging_config:
            raise Exception("'logging' section is required in config")
            
        if not logging_config.get('enable_logging', True):
            return
            
        try:
            if hasattr(self, 'processed_log_file'):
                data = {
                    'processed_files': list(self.processed_files),
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.processed_log_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(f"Warning: Could not save processed files log: {e}")
    
    def _get_file_hash(self, file_path: pathlib.Path) -> str:
        """Get hash of file for tracking changes."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return str(file_path.stat().st_mtime)
    
    def _get_file_key(self, file_path: pathlib.Path) -> str:
        """Get unique key for file tracking."""
        file_hash = self._get_file_hash(file_path)
        return f"{file_path.name}:{file_hash}"
    
    def _is_file_processed(self, file_path: pathlib.Path) -> bool:
        """Check if file has already been processed."""
        logging_config = self.config.get('logging')
        if not logging_config:
            raise Exception("'logging' section is required in config")
            
        if not logging_config.get('skip_processed', True):
            return False
        
        file_key = self._get_file_key(file_path)
        return file_key in self.processed_files
    
    def _mark_file_processed(self, file_path: pathlib.Path):
        """Mark file as processed."""
        logging_config = self.config.get('logging')
        if not logging_config:
            raise Exception("'logging' section is required in config")
            
        if logging_config.get('enable_logging', True):
            file_key = self._get_file_key(file_path)
            self.processed_files.add(file_key)
    
    def _log(self, message: str):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        print(log_message)
        
        logging_config = self.config.get('logging')
        if logging_config and logging_config.get('enable_logging', True) and self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + "\n")
            except Exception as e:
                print(f"Warning: Could not write to log file: {e}")
    
    def extract_title_and_content(self, content: str) -> Tuple[str, str]:
        """Extract title from first ## header and return title and content without the title."""
        lines = content.strip().split('\n')
        title = "Untitled"
        content_start_index = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for the first ## header (markdown h2)
            if line.startswith('## ') and len(line) > 3:
                # Extract title without the ## prefix
                title = line[3:].strip()
                # Remove any additional markdown formatting
                title = re.sub(r'\*\*([^*]+)\*\*', r'\1', title)  # Remove bold
                title = re.sub(r'\*([^*]+)\*', r'\1', title)  # Remove italic
                title = title.strip()
                
                # Find where content should start (skip empty lines after title)
                content_start_index = i + 1
                while (content_start_index < len(lines) and 
                       not lines[content_start_index].strip()):
                    content_start_index += 1
                break
        
        # Return title and content without the title line
        remaining_content = '\n'.join(lines[content_start_index:]).strip()
        return title, remaining_content
    
    def get_chapter_name(self, filename: str) -> str:
        """Extract chapter name from filename."""
        # Remove extension and extract chapter info
        base_name = os.path.splitext(filename)[0]
        # Look for chapter pattern
        chapter_match = re.search(r'chapter[_\s]*(\d+(?:\.\d+)?)', base_name, re.IGNORECASE)
        if chapter_match:
            return f"chapter_{chapter_match.group(1)}"
        else:
            # Fallback to cleaned filename
            return re.sub(r'[^a-zA-Z0-9_]', '_', base_name.lower())
    
    def split_text(self, text: str, max_length: int) -> List[str]:
        """Split text into segments without overlap."""
        if len(text) <= max_length:
            return [text]
        
        segments = []
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + max_length
            
            if end >= len(text):
                # Last segment
                segments.append(text[start:])
                break
            
            # Try to find a good break point (sentence, paragraph, or word boundary)
            break_point = end
            
            # Look for sentence break (. ! ?) within last 200 characters
            for i in range(min(200, end - start)):
                pos = end - i - 1
                if pos > start and text[pos] in '.!?':
                    # Check if next character is space or newline
                    if pos + 1 < len(text) and text[pos + 1] in ' \n\t':
                        break_point = pos + 1
                        break
            
            # If no sentence break found, look for paragraph break
            if break_point == end:
                for i in range(min(200, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == '\n' and pos + 1 < len(text) and text[pos + 1] == '\n':
                        break_point = pos + 2
                        break
            
            # If still no good break, look for any newline
            if break_point == end:
                for i in range(min(100, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == '\n':
                        break_point = pos + 1
                        break
            
            # If still no break, look for word boundary
            if break_point == end:
                for i in range(min(50, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == ' ':
                        break_point = pos + 1
                        break
            
            segments.append(text[start:break_point])
            
            # Move to next segment without overlap
            start = break_point
        
        return segments
    
    def process_file(self, file_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Process a single file and return list of segments."""
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Extract title and content without title
            title, content = self.extract_title_and_content(original_content)
            chapter_name = self.get_chapter_name(file_path.name)
            
            # Split content into segments (content now excludes the title)
            processing_config = self.config.get('processing')
            if not processing_config:
                raise Exception("'processing' section is required in config")
            
            segment_length = processing_config.get('segment_length')
            if not segment_length:
                raise Exception("'processing.segment_length' is required in config")
                
            segments = self.split_text(content, segment_length)
            
            # Create segment objects
            segment_objects = []
            for i, segment_content in enumerate(segments, 1):
                segment_obj = {
                    'id': f"{chapter_name}_segment_{i}",
                    'title': title,
                    'content': segment_content.strip()
                }
                segment_objects.append(segment_obj)
            
            self._log(f"Processed {file_path.name}: {len(segment_objects)} segments created")
            return segment_objects
            
        except Exception as e:
            self._log(f"Error processing file {file_path}: {e}")
            return []
    
    def get_input_files(self) -> List[pathlib.Path]:
        """Get all files from input directory matching specified types."""
        paths_config = self.config.get('paths')
        if not paths_config:
            raise Exception("'paths' section is required in config")
            
        input_path = paths_config.get('input')
        if not input_path:
            raise Exception("'paths.input' is required in config")
            
        input_dir = self.project_root / input_path
        if not input_dir.exists():
            raise Exception(f"Input directory does not exist: {input_dir}")
        
        processing_config = self.config.get('processing')
        if not processing_config:
            raise Exception("'processing' section is required in config")
            
        file_types = processing_config.get('file_types')
        if not file_types:
            raise Exception("'processing.file_types' is required in config")
        
        files = []
        for file_type in file_types:
            files.extend(input_dir.rglob(f"*{file_type}"))
        
        return sorted(files)
    
    def create_output_structure(self, input_file: pathlib.Path) -> pathlib.Path:
        """Create output directory structure mirroring input structure."""
        paths_config = self.config.get('paths')
        if not paths_config:
            raise Exception("'paths' section is required in config")
            
        input_path = paths_config.get('input')
        output_path = paths_config.get('output')
        if not input_path or not output_path:
            raise Exception("'paths.input' and 'paths.output' are required in config")
            
        input_base = self.project_root / input_path
        output_base = self.project_root / output_path
        
        # Get relative path from input base
        relative_path = input_file.relative_to(input_base)
        
        # Create output path
        output_file = output_base / relative_path.parent / f"{relative_path.stem}.yml"
        
        # Create directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return output_file
    
    def save_segments(self, segments: List[Dict[str, Any]], output_path: pathlib.Path):
        """Save segments to YAML file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(segments, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._log(f"Saved {len(segments)} segments to {output_path.name}")
        except Exception as e:
            self._log(f"Error saving segments to {output_path}: {e}")
    
    def run(self):
        """Main execution function."""
        self._log("Starting Text Splitter...")
        
        # Get all input files
        input_files = self.get_input_files()
        self._log(f"Found {len(input_files)} files to process")
        
        if not input_files:
            self._log("No files found matching the specified criteria")
            return
        
        # Filter out already processed files if skip_processed is enabled
        logging_config = self.config.get('logging')
        if logging_config and logging_config.get('skip_processed', True):
            unprocessed_files = [f for f in input_files if not self._is_file_processed(f)]
            skipped_count = len(input_files) - len(unprocessed_files)
            if skipped_count > 0:
                self._log(f"Skipping {skipped_count} already processed files")
            input_files = unprocessed_files
        
        if not input_files:
            self._log("All files have already been processed. Nothing to do.")
            return
        
        # Process each file
        total_segments = 0
        processed_files = 0
        failed_files = 0
        
        for file_path in input_files:
            self._log(f"Processing: {file_path.name}")
            
            # Process file
            segments = self.process_file(file_path)
            
            if segments:
                # Create output path
                output_path = self.create_output_structure(file_path)
                
                # Save segments
                self.save_segments(segments, output_path)
                
                # Mark as processed
                self._mark_file_processed(file_path)
                
                total_segments += len(segments)
                processed_files += 1
            else:
                self._log(f"No segments generated for {file_path.name}")
                failed_files += 1
        
        # Save processed files log
        self._save_processed_files()
        
        self._log(f"Completed! Processed {processed_files} files, generated {total_segments} segments")
        if failed_files > 0:
            self._log(f"Failed to process {failed_files} files")
        
        self._log("Text Splitter finished successfully")


def main():
    """Main entry point."""
    try:
        splitter = TextSplitter()
        splitter.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
