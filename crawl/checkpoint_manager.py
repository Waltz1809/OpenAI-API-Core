#!/usr/bin/env python3
"""
Checkpoint Manager
==================

Quản lý checkpoint để resume crawl từ vị trí cũ
Lưu trữ: last_url, chapter_count, timestamp
"""

import os
import json
from datetime import datetime


class CheckpointManager:
    """Quản lý checkpoint cho resume crawl"""
    
    def __init__(self, checkpoint_dir="checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self.ensure_checkpoint_dir()
    
    def ensure_checkpoint_dir(self):
        """Đảm bảo thư mục checkpoint tồn tại"""
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def get_checkpoint_file(self, series_name):
        """Lấy path file checkpoint cho series"""
        safe_name = "".join(c for c in series_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        return os.path.join(self.checkpoint_dir, f"{safe_name}_checkpoint.json")
    
    def save_checkpoint(self, series_name, chapter_count, current_url, title=None):
        """
        Lưu checkpoint
        
        Args:
            series_name: Tên series
            chapter_count: Số chapter đã crawl
            current_url: URL hiện tại
            title: Title chapter hiện tại (optional)
        """
        try:
            checkpoint_file = self.get_checkpoint_file(series_name)
            
            checkpoint_data = {
                'series_name': series_name,
                'chapter_count': chapter_count,
                'last_url': current_url,
                'last_title': title,
                'timestamp': datetime.now().isoformat(),
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"⚠️  Lỗi save checkpoint: {e}")
            return False
    
    def load_checkpoint(self, series_name):
        """
        Load checkpoint
        
        Args:
            series_name: Tên series
            
        Returns:
            dict hoặc None nếu không có checkpoint
        """
        try:
            checkpoint_file = self.get_checkpoint_file(series_name)
            
            if not os.path.exists(checkpoint_file):
                return None
            
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            return checkpoint_data
            
        except Exception as e:
            print(f"⚠️  Lỗi load checkpoint: {e}")
            return None
    
    def has_checkpoint(self, series_name):
        """Kiểm tra có checkpoint không"""
        checkpoint_file = self.get_checkpoint_file(series_name)
        return os.path.exists(checkpoint_file)
    
    def delete_checkpoint(self, series_name):
        """Xóa checkpoint (khi crawl hoàn thành)"""
        try:
            checkpoint_file = self.get_checkpoint_file(series_name)
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
                return True
            return False
        except Exception as e:
            print(f"⚠️  Lỗi delete checkpoint: {e}")
            return False
    
    def list_checkpoints(self):
        """List tất cả checkpoint hiện có"""
        checkpoints = []
        try:
            if os.path.exists(self.checkpoint_dir):
                for file in os.listdir(self.checkpoint_dir):
                    if file.endswith('_checkpoint.json'):
                        file_path = os.path.join(self.checkpoint_dir, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                checkpoints.append(data)
                        except:
                            continue
        except Exception as e:
            print(f"⚠️  Lỗi list checkpoints: {e}")
        
        return checkpoints 