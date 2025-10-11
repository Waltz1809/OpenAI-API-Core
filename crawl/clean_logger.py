#!/usr/bin/env python3
"""
Clean Logging System for Crawler
================================

Simplified, readable logging cho crawl process
"""

import time
from datetime import datetime


class CleanLogger:
    """Clean, minimal logging cho crawler"""
    
    def __init__(self, series_name, total_chapters=None):
        self.series_name = series_name
        self.total_chapters = total_chapters
        self.start_time = time.time()
        self.stats = {
            'crawled': 0,
            'failed': 0,
            'skipped': 0,
            'retries': 0
        }
        
        # Print header
        print(f"\n🚀 Starting crawl: {series_name}")
        if total_chapters:
            print(f"📚 Target: {total_chapters} chapters")
        print("─" * 50)
    
    def log_chapter(self, chapter_num, title, status, details=None):
        """Log single chapter progress"""
        
        # Progress indicator
        if self.total_chapters:
            progress = f"[{chapter_num:3d}/{self.total_chapters}]"
        else:
            progress = f"[{chapter_num:3d}]"
        
        # Status icon
        icons = {
            'success': '✅',
            'failed': '❌', 
            'retry': '🔄',
            'skipped': '⏭️',
            'missing': '❓'
        }
        icon = icons.get(status, '❓')
        
        # Clean title (max 50 chars)
        clean_title = title[:47] + "..." if len(title) > 50 else title
        
        # Main log line
        print(f"{icon} {progress} {clean_title}")
        
        # Details if needed
        if details and status in ['failed', 'retry']:
            print(f"    └─ {details}")
        
        # Update stats
        if status == 'success':
            self.stats['crawled'] += 1
        elif status == 'failed':
            self.stats['failed'] += 1
        elif status == 'skipped':
            self.stats['skipped'] += 1
        elif status == 'retry':
            self.stats['retries'] += 1
    
    def log_validation(self, chapter_num, qidian_title, site_title, match_score):
        """Log chapter validation results"""
        if match_score >= 0.9:
            print(f"    ✅ Match: {match_score:.1%}")
        elif match_score >= 0.7:
            print(f"    ⚠️  Partial: {match_score:.1%}")
        else:
            print(f"    ❌ Mismatch: {match_score:.1%}")
            print(f"       Qidian: {qidian_title[:30]}...")
            print(f"       Site:   {site_title[:30]}...")
    
    def log_summary(self):
        """Print final summary"""
        elapsed = time.time() - self.start_time
        total = sum(self.stats.values()) - self.stats['retries']  # Don't double count retries
        
        print("─" * 50)
        print(f"📊 Crawl Summary: {self.series_name}")
        print(f"   ✅ Success: {self.stats['crawled']}")
        print(f"   ❌ Failed:  {self.stats['failed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']}")
        print(f"   🔄 Retries: {self.stats['retries']}")
        print(f"   ⏱️  Time:    {elapsed:.1f}s")
        
        if total > 0:
            success_rate = (self.stats['crawled'] / total) * 100
            print(f"   📈 Success Rate: {success_rate:.1f}%")
        
        print("─" * 50)
    
    def log_missing_chapters(self, missing_list):
        """Log missing chapters"""
        if missing_list:
            print(f"\n⚠️  Missing chapters: {len(missing_list)}")
            for chapter_num in missing_list[:10]:  # Show first 10
                print(f"    - Chapter {chapter_num}")
            if len(missing_list) > 10:
                print(f"    ... and {len(missing_list) - 10} more")


class PiaotiaLogger(CleanLogger):
    """Specialized logger cho Piaotia với JSON validation"""
    
    def __init__(self, series_name, qidian_json_path, piaotia_json_path):
        super().__init__(series_name)
        
        # Load JSON files
        self.qidian_data = self._load_qidian_json(qidian_json_path)
        self.piaotia_data = self._load_piaotia_json(piaotia_json_path)
        
        # Analyze differences
        self._analyze_differences()
    
    def _load_qidian_json(self, path):
        """Load Qidian ground truth"""
        try:
            import json
            import os

            # Ensure absolute path
            if not os.path.isabs(path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(script_dir))
                path = os.path.join(project_root, path)

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert to dict {chapter_num: title}
            result = {}
            for i, item in enumerate(data, 1):
                result[i] = item.get('title', '')
            
            return result
        except Exception as e:
            print(f"⚠️  Lỗi load Qidian JSON: {e}")
            return {}
    
    def _load_piaotia_json(self, path):
        """Load Piaotia chapter mapping"""
        try:
            import json
            import os

            # Ensure absolute path
            if not os.path.isabs(path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(script_dir))
                path = os.path.join(project_root, path)

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert to dict {chapter_num: {"title": ..., "url": ...}}
            result = {}
            for item in data:
                title = item.get('title', '')
                url = item.get('url', '')
                
                # Extract chapter number
                match = re.match(r'^第(\d+)章', title)
                if match:
                    chapter_num = int(match.group(1))
                    result[chapter_num] = {
                        'title': title,
                        'url': url
                    }
            
            return result
        except Exception as e:
            print(f"⚠️  Lỗi load Piaotia JSON: {e}")
            return {}
    
    def _analyze_differences(self):
        """Analyze differences between Qidian and Piaotia"""
        qidian_chapters = set(self.qidian_data.keys())
        piaotia_chapters = set(self.piaotia_data.keys())
        
        missing_in_piaotia = qidian_chapters - piaotia_chapters
        extra_in_piaotia = piaotia_chapters - qidian_chapters
        
        print(f"📊 Chapter Analysis:")
        print(f"   📖 Qidian: {len(qidian_chapters)} chapters")
        print(f"   🌐 Piaotia: {len(piaotia_chapters)} chapters")
        
        if missing_in_piaotia:
            print(f"   ❌ Missing in Piaotia: {len(missing_in_piaotia)} chapters")
            missing_list = sorted(list(missing_in_piaotia))
            print(f"      Missing: {missing_list[:10]}{'...' if len(missing_list) > 10 else ''}")
        
        if extra_in_piaotia:
            print(f"   ➕ Extra in Piaotia: {len(extra_in_piaotia)} chapters")
    
    def get_piaotia_url(self, chapter_num):
        """Get Piaotia URL for specific chapter"""
        return self.piaotia_data.get(chapter_num, {}).get('url')
    
    def validate_chapter(self, chapter_num, crawled_title):
        """Validate crawled chapter với ground truth"""
        qidian_title = self.qidian_data.get(chapter_num, '')
        piaotia_title = self.piaotia_data.get(chapter_num, {}).get('title', '')
        
        # Simple title comparison
        if qidian_title == crawled_title:
            return 1.0  # Perfect match
        elif qidian_title == piaotia_title == crawled_title:
            return 1.0  # All match
        elif qidian_title and crawled_title:
            # Basic similarity check
            common_chars = set(qidian_title) & set(crawled_title)
            similarity = len(common_chars) / max(len(qidian_title), len(crawled_title))
            return similarity
        else:
            return 0.0


class SimpleLogger(CleanLogger):
    """Simple logger không cần validation"""

    def __init__(self, series_name):
        super().__init__(series_name)
