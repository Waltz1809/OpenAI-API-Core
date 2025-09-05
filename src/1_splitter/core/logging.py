"""
Logging and progress tracking for the Text Splitter.
"""

import pathlib
import json
import hashlib
from datetime import datetime
from typing import Set


class LogManager:
    """Handles logging and file tracking."""
    
    def __init__(self, project_root: pathlib.Path, log_path: str, enable_logging: bool = True):
        """Initialize logging manager."""
        self.project_root = project_root
        self.enable_logging = enable_logging
        self.processed_files: Set[str] = set()
        self.log_file = None
        self.processed_log_file = None
        
        if enable_logging:
            self._setup_logging(log_path)
            self._load_processed_files()
    
    def _setup_logging(self, log_path: str):
        """Setup logging directory and files."""
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
            f.write("=" * 50 + "\n\n")
    
    def _load_processed_files(self):
        """Load list of previously processed files."""
        if not self.enable_logging:
            return
            
        try:
            if self.processed_log_file and self.processed_log_file.exists():
                with open(self.processed_log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                self.log(f"Loaded {len(self.processed_files)} previously processed files")
        except Exception as e:
            self.log(f"Warning: Could not load processed files log: {e}")
            self.processed_files = set()
    
    def _save_processed_files(self):
        """Save list of processed files."""
        if not self.enable_logging or not self.processed_log_file:
            return
            
        try:
            data = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.processed_log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"Warning: Could not save processed files log: {e}")
    
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
    
    def is_file_processed(self, file_path: pathlib.Path, skip_processed: bool = True) -> bool:
        """Check if file has already been processed."""
        if not skip_processed:
            return False
        
        file_key = self._get_file_key(file_path)
        return file_key in self.processed_files
    
    def mark_file_processed(self, file_path: pathlib.Path):
        """Mark file as processed."""
        if self.enable_logging:
            file_key = self._get_file_key(file_path)
            self.processed_files.add(file_key)
    
    def save_session(self):
        """Save the current session data."""
        self._save_processed_files()
    
    def log(self, message: str):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        print(log_message)
        
        if self.enable_logging and self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + "\n")
            except Exception as e:
                print(f"Warning: Could not write to log file: {e}")
