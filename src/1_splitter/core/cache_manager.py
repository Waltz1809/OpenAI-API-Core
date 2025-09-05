"""
Cache management utilities for the Text Splitter.
"""

import pathlib
import shutil
from typing import List


class CacheManager:
    """Handles Python cache cleaning and maintenance."""
    
    def __init__(self, project_root: pathlib.Path):
        """Initialize cache manager with project root."""
        self.project_root = project_root
    
    def find_pycache_directories(self) -> List[pathlib.Path]:
        """Find all __pycache__ directories in the project."""
        pycache_dirs = []
        
        # Search for __pycache__ directories recursively
        for pycache_dir in self.project_root.rglob("__pycache__"):
            if pycache_dir.is_dir():
                pycache_dirs.append(pycache_dir)
        
        return sorted(pycache_dirs)
    
    def find_pyc_files(self) -> List[pathlib.Path]:
        """Find all .pyc files in the project."""
        pyc_files = []
        
        # Search for .pyc files recursively
        for pyc_file in self.project_root.rglob("*.pyc"):
            if pyc_file.is_file():
                pyc_files.append(pyc_file)
        
        return sorted(pyc_files)
    
    def clean_pycache(self, dry_run: bool = False) -> dict:
        """Clean all Python cache files and directories."""
        pycache_dirs = self.find_pycache_directories()
        pyc_files = self.find_pyc_files()
        
        results = {
            'pycache_dirs_found': len(pycache_dirs),
            'pyc_files_found': len(pyc_files),
            'pycache_dirs_removed': 0,
            'pyc_files_removed': 0,
            'errors': []
        }
        
        if dry_run:
            return results
        
        # Remove __pycache__ directories
        for pycache_dir in pycache_dirs:
            try:
                shutil.rmtree(pycache_dir)
                results['pycache_dirs_removed'] += 1
            except Exception as e:
                results['errors'].append(f"Failed to remove {pycache_dir}: {e}")
        
        # Remove standalone .pyc files
        for pyc_file in pyc_files:
            try:
                pyc_file.unlink()
                results['pyc_files_removed'] += 1
            except Exception as e:
                results['errors'].append(f"Failed to remove {pyc_file}: {e}")
        
        return results
    
    def get_cache_size(self) -> int:
        """Get total size of cache files in bytes."""
        total_size = 0
        
        # Size of __pycache__ directories
        for pycache_dir in self.find_pycache_directories():
            for file_path in pycache_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except (OSError, FileNotFoundError):
                        pass
        
        # Size of standalone .pyc files
        for pyc_file in self.find_pyc_files():
            try:
                total_size += pyc_file.stat().st_size
            except (OSError, FileNotFoundError):
                pass
        
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
