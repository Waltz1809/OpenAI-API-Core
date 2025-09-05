"""
File management and I/O operations.
"""

import pathlib
import yaml
from typing import List, Dict, Any


class FileManager:
    """Handles file operations and directory management."""
    
    def __init__(self, project_root: pathlib.Path):
        """Initialize file manager with project root."""
        self.project_root = project_root
    
    @staticmethod
    def find_project_root() -> pathlib.Path:
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
    
    def get_input_files(self, input_path: str, file_types: List[str]) -> List[pathlib.Path]:
        """Get all files from input directory matching specified types."""
        input_dir = self.project_root / input_path
        if not input_dir.exists():
            raise Exception(f"Input directory does not exist: {input_dir}")
        
        files = []
        for file_type in file_types:
            files.extend(input_dir.rglob(f"*{file_type}"))
        
        return sorted(files)
    
    def create_output_structure(self, input_file: pathlib.Path, input_path: str, output_path: str) -> pathlib.Path:
        """Create output directory structure mirroring input structure."""
        input_base = self.project_root / input_path
        output_base = self.project_root / output_path
        
        # Get relative path from input base
        relative_path = input_file.relative_to(input_base)
        
        # Create output path
        output_file = output_base / relative_path.parent / f"{relative_path.stem}.yml"
        
        # Create directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return output_file
    
    def read_file(self, file_path: pathlib.Path) -> str:
        """Read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Failed to read file {file_path}: {e}")
    
    def save_segments(self, segments: List[Dict[str, Any]], output_path: pathlib.Path) -> bool:
        """Save segments to YAML file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(segments, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            raise Exception(f"Error saving segments to {output_path}: {e}")
