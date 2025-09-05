#!/usr/bin/env python3
"""
Text Splitter Module - Main Entry Point
Splits text files into segments for processing by translation pipeline.
"""

import pathlib
import argparse
from typing import List, Dict, Any

from core import ConfigManager, LogManager, TextProcessor, FileManager, CacheManager


class TextSplitter:
    """Main Text Splitter class that orchestrates the splitting process."""
    
    def __init__(self, config_path: str = None):
        """Initialize the splitter with configuration."""
        # Initialize managers
        self.config_manager = ConfigManager(config_path)
        self.project_root = FileManager.find_project_root()
        self.file_manager = FileManager(self.project_root)
        
        # Setup logging
        logging_config = self.config_manager.get_logging()
        paths_config = self.config_manager.get_paths()
        
        self.log_manager = LogManager(
            project_root=self.project_root,
            log_path=paths_config['logs'],
            enable_logging=logging_config.get('enable_logging', True)
        )
        
        self.text_processor = TextProcessor()
        self.cache_manager = CacheManager(self.project_root)
    
    def process_file(self, file_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Process a single file and return list of segments."""
        try:
            # Read file content
            original_content = self.file_manager.read_file(file_path)
            
            # Extract title and content without title
            title, content = self.text_processor.extract_title_and_content(original_content)
            chapter_name = self.text_processor.get_chapter_name(file_path.name)
            
            # Split content into segments (content now excludes the title)
            processing_config = self.config_manager.get_processing()
            segment_length = processing_config['segment_length']
            
            segments = self.text_processor.split_text(content, segment_length)
            
            # Create segment objects
            segment_objects = []
            for i, segment_content in enumerate(segments, 1):
                segment_obj = {
                    'id': f"{chapter_name}_segment_{i}",
                    'title': title,
                    'content': segment_content.strip()
                }
                segment_objects.append(segment_obj)
            
            self.log_manager.log(f"Processed {file_path.name}: {len(segment_objects)} segments created")
            return segment_objects
            
        except Exception as e:
            self.log_manager.log(f"Error processing file {file_path}: {e}")
            return []
    
    def clean_cache(self, dry_run: bool = False):
        """Clean Python cache files and directories."""
        self.log_manager.log("Starting cache cleanup...")
        
        # Get cache info before cleaning
        cache_size_before = self.cache_manager.get_cache_size()
        pycache_dirs = self.cache_manager.find_pycache_directories()
        pyc_files = self.cache_manager.find_pyc_files()
        
        self.log_manager.log(f"Found {len(pycache_dirs)} __pycache__ directories")
        self.log_manager.log(f"Found {len(pyc_files)} standalone .pyc files")
        self.log_manager.log(f"Total cache size: {self.cache_manager.format_size(cache_size_before)}")
        
        if dry_run:
            self.log_manager.log("DRY RUN: No files will be deleted")
            for pycache_dir in pycache_dirs:
                self.log_manager.log(f"Would remove: {pycache_dir}")
            for pyc_file in pyc_files:
                self.log_manager.log(f"Would remove: {pyc_file}")
            return
        
        # Perform cleanup
        results = self.cache_manager.clean_pycache(dry_run=False)
        
        # Log results
        self.log_manager.log(f"Removed {results['pycache_dirs_removed']}/{results['pycache_dirs_found']} __pycache__ directories")
        self.log_manager.log(f"Removed {results['pyc_files_removed']}/{results['pyc_files_found']} .pyc files")
        
        if results['errors']:
            self.log_manager.log(f"Encountered {len(results['errors'])} errors:")
            for error in results['errors']:
                self.log_manager.log(f"  - {error}")
        
        # Get cache size after cleaning
        cache_size_after = self.cache_manager.get_cache_size()
        freed_space = cache_size_before - cache_size_after
        
        if freed_space > 0:
            self.log_manager.log(f"Freed {self.cache_manager.format_size(freed_space)} of disk space")
        
        self.log_manager.log("Cache cleanup completed")
    
    def run(self):
        """Main execution function."""
        self.log_manager.log("Starting Text Splitter...")
        
        # Get configuration
        paths_config = self.config_manager.get_paths()
        processing_config = self.config_manager.get_processing()
        logging_config = self.config_manager.get_logging()
        
        # Get all input files
        input_files = self.file_manager.get_input_files(
            paths_config['input'], 
            processing_config['file_types']
        )
        self.log_manager.log(f"Found {len(input_files)} files to process")
        
        if not input_files:
            self.log_manager.log("No files found matching the specified criteria")
            return
        
        # Filter out already processed files if skip_processed is enabled
        if logging_config.get('skip_processed', True):
            unprocessed_files = [
                f for f in input_files 
                if not self.log_manager.is_file_processed(f, logging_config.get('skip_processed', True))
            ]
            skipped_count = len(input_files) - len(unprocessed_files)
            if skipped_count > 0:
                self.log_manager.log(f"Skipping {skipped_count} already processed files")
            input_files = unprocessed_files
        
        if not input_files:
            self.log_manager.log("All files have already been processed. Nothing to do.")
            return
        
        # Process each file
        total_segments = 0
        processed_files = 0
        failed_files = 0
        
        for file_path in input_files:
            self.log_manager.log(f"Processing: {file_path.name}")
            
            # Process file
            segments = self.process_file(file_path)
            
            if segments:
                # Create output path
                output_path = self.file_manager.create_output_structure(
                    file_path, 
                    paths_config['input'], 
                    paths_config['output']
                )
                
                # Save segments
                try:
                    self.file_manager.save_segments(segments, output_path)
                    self.log_manager.log(f"Saved {len(segments)} segments to {output_path.name}")
                    
                    # Mark as processed
                    self.log_manager.mark_file_processed(file_path)
                    
                    total_segments += len(segments)
                    processed_files += 1
                except Exception as e:
                    self.log_manager.log(f"Failed to save segments for {file_path.name}: {e}")
                    failed_files += 1
            else:
                self.log_manager.log(f"No segments generated for {file_path.name}")
                failed_files += 1
        
        # Save processed files log
        self.log_manager.save_session()
        
        self.log_manager.log(f"Completed! Processed {processed_files} files, generated {total_segments} segments")
        if failed_files > 0:
            self.log_manager.log(f"Failed to process {failed_files} files")
        
        self.log_manager.log("Text Splitter finished successfully")
        
        # Optional: Clean cache after successful run
        cache_size = self.cache_manager.get_cache_size()
        if cache_size > 0:
            self.log_manager.log(f"Python cache size: {self.cache_manager.format_size(cache_size)}")
            self.log_manager.log("Tip: Use --clean-cache to clean Python cache files")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Text Splitter - Split text files into segments')
    parser.add_argument('--clean-cache', action='store_true', 
                       help='Clean Python cache files (__pycache__ and .pyc)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be cleaned without actually deleting (use with --clean-cache)')
    
    args = parser.parse_args()
    
    try:
        splitter = TextSplitter()
        
        if args.clean_cache:
            splitter.clean_cache(dry_run=args.dry_run)
        else:
            splitter.run()
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
