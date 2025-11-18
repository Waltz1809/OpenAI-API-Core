#!/usr/bin/env python3
"""
Path Helper - Centralized path handling cho toàn bộ project
Xử lý đường dẫn tương đối một cách đồng nhất
"""

import os
from pathlib import Path
from typing import Union


class PathHelper:
    """Helper để xử lý paths một cách đồng nhất."""
    
    _instance = None
    _project_root = None
    
    def __new__(cls):
        """Singleton pattern để đảm bảo chỉ có 1 instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize với project root."""
        if self._project_root is None:
            self._project_root = self._find_project_root()
    
    @staticmethod
    def _find_project_root() -> Path:
        """
        Tìm project root directory.
        
        Strategy:
        1. Tìm từ file hiện tại lên trên cho đến khi gặp marker
        2. Marker: thư mục chứa 'dich_cli' folder
        3. Fallback: current working directory
        
        Returns:
            Path: Project root path
        """
        # Bắt đầu từ thư mục chứa file này (dich_cli/core/)
        current = Path(__file__).parent.parent.parent  # -> project root
        
        # Kiểm tra xem có phải project root không
        if (current / 'dich_cli').exists() and (current / 'data').exists():
            return current
        
        # Fallback: tìm từ cwd lên trên
        current = Path.cwd()
        while current != current.parent:
            if (current / 'dich_cli').exists():
                return current
            current = current.parent
        
        # Last fallback: current working directory
        return Path.cwd()
    
    @property
    def project_root(self) -> Path:
        """Lấy project root path."""
        return self._project_root
    
    def resolve(self, path: Union[str, Path]) -> str:
        """
        Resolve path thành absolute path.
        
        - Nếu path đã absolute: giữ nguyên
        - Nếu path relative: join với project_root
        
        Args:
            path: Đường dẫn cần resolve
            
        Returns:
            str: Absolute path
        """
        if not path:
            return str(self._project_root)
        
        p = Path(path)
        
        # Nếu đã là absolute path, return ngay
        if p.is_absolute():
            return str(p)
        
        # Relative path -> join với project root
        return str(self._project_root / p)
    
    def ensure_dir(self, path: Union[str, Path], is_file: bool = False) -> str:
        """
        Đảm bảo thư mục tồn tại.
        
        Args:
            path: Đường dẫn cần tạo
            is_file: True nếu path là file (tạo parent dir)
                    False nếu path là directory
        
        Returns:
            str: Absolute path đã resolve
        """
        full_path = Path(self.resolve(path))
        
        if is_file:
            # Tạo parent directory
            full_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Tạo chính directory đó
            full_path.mkdir(parents=True, exist_ok=True)
        
        return str(full_path)
    
    def join(self, *paths: Union[str, Path]) -> str:
        """
        Join nhiều paths lại với nhau.
        
        Args:
            *paths: Các path segments
            
        Returns:
            str: Joined path (relative hoặc absolute)
        """
        if not paths:
            return str(self._project_root)
        
        result = Path(paths[0])
        for p in paths[1:]:
            result = result / p
        
        return str(result)
    
    def relative_to_project(self, path: Union[str, Path]) -> str:
        """
        Lấy relative path so với project root.
        
        Args:
            path: Absolute hoặc relative path
            
        Returns:
            str: Relative path từ project root
        """
        try:
            abs_path = Path(self.resolve(path))
            rel_path = abs_path.relative_to(self._project_root)
            return str(rel_path)
        except ValueError:
            # Nếu path nằm ngoài project, return absolute
            return str(abs_path)
    
    def exists(self, path: Union[str, Path]) -> bool:
        """
        Kiểm tra path có tồn tại không.
        
        Args:
            path: Đường dẫn cần kiểm tra
            
        Returns:
            bool: True nếu tồn tại
        """
        return Path(self.resolve(path)).exists()
    
    def is_file(self, path: Union[str, Path]) -> bool:
        """Kiểm tra path có phải file không."""
        return Path(self.resolve(path)).is_file()
    
    def is_dir(self, path: Union[str, Path]) -> bool:
        """Kiểm tra path có phải directory không."""
        return Path(self.resolve(path)).is_dir()
    
    def get_base_name(self, file_path: Union[str, Path]) -> str:
        """
        Lấy base name từ file path (không có extension).
        
        Args:
            file_path: Đường dẫn file
            
        Returns:
            str: Base name (e.g., "file.txt" -> "file")
        """
        return Path(file_path).stem
    
    def get_extension(self, file_path: Union[str, Path]) -> str:
        """
        Lấy extension từ file path.
        
        Args:
            file_path: Đường dẫn file
            
        Returns:
            str: Extension (e.g., ".txt")
        """
        return Path(file_path).suffix
    
    def __repr__(self):
        return f"PathHelper(project_root='{self._project_root}')"


# Global instance để dùng chung
_path_helper = PathHelper()


def get_path_helper() -> PathHelper:
    """
    Lấy global PathHelper instance.
    
    Returns:
        PathHelper: Global instance
    """
    return _path_helper

