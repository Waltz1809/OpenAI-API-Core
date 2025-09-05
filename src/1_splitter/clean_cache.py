#!/usr/bin/env python3
"""
Cache Cleaner Script
Standalone utility to clean Python cache files from the project.
"""

import sys
import pathlib

# Add current directory to path so we can import core modules
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from core import CacheManager, FileManager


def main():
    """Main entry point for cache cleaner."""
    try:
        # Find project root and setup cache manager
        project_root = FileManager.find_project_root()
        cache_manager = CacheManager(project_root)
        
        print("🧹 Python Cache Cleaner")
        print("=" * 40)
        
        # Get cache information
        pycache_dirs = cache_manager.find_pycache_directories()
        pyc_files = cache_manager.find_pyc_files()
        cache_size = cache_manager.get_cache_size()
        
        print(f"📁 Project root: {project_root}")
        print(f"🗂️  __pycache__ directories found: {len(pycache_dirs)}")
        print(f"📄 .pyc files found: {len(pyc_files)}")
        print(f"💾 Total cache size: {cache_manager.format_size(cache_size)}")
        print()
        
        if len(pycache_dirs) == 0 and len(pyc_files) == 0:
            print("✨ No cache files found! Project is already clean.")
            return 0
        
        # Show what will be cleaned
        if len(pycache_dirs) > 0:
            print("📂 __pycache__ directories to remove:")
            for pycache_dir in pycache_dirs:
                rel_path = pycache_dir.relative_to(project_root)
                print(f"  - {rel_path}")
        
        if len(pyc_files) > 0:
            print(f"📄 Standalone .pyc files to remove: {len(pyc_files)} files")
        
        print()
        
        # Ask for confirmation
        response = input("🤔 Do you want to proceed with cleaning? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("❌ Cache cleaning cancelled.")
            return 0
        
        print("\n🚀 Starting cleanup...")
        
        # Perform cleanup
        results = cache_manager.clean_pycache(dry_run=False)
        
        print(f"✅ Removed {results['pycache_dirs_removed']}/{results['pycache_dirs_found']} __pycache__ directories")
        print(f"✅ Removed {results['pyc_files_removed']}/{results['pyc_files_found']} .pyc files")
        
        if results['errors']:
            print(f"⚠️  Encountered {len(results['errors'])} errors:")
            for error in results['errors']:
                print(f"   - {error}")
        
        # Calculate space freed
        new_cache_size = cache_manager.get_cache_size()
        freed_space = cache_size - new_cache_size
        
        if freed_space > 0:
            print(f"💾 Freed {cache_manager.format_size(freed_space)} of disk space")
        
        print("\n🎉 Cache cleanup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
