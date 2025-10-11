#!/usr/bin/env python3
"""
Base Parser Class
================

Cung cấp standard interface cho tất cả parsers với JSON-only approach
"""

import os
import json
from abc import ABC, abstractmethod


class BaseParser(ABC):
    """
    Base class cho tất cả parsers
    
    Tất cả parsers sẽ inherit từ class này và implement:
    - extract_content() - Core logic extract content từ website
    - clean_content() - Clean và format content
    """
    
    @staticmethod
    def load_chapter_mapping(json_file_path):
        """
        Load chapter mapping từ JSON file - STANDARD cho tất cả parsers
        
        Args:
            json_file_path (str): Path đến file JSON
            
        Returns:
            dict: Mapping từ index -> {title, url}
            Format: {1: {'title': 'Chapter 1', 'url': 'http://...'}}
        """
        try:
            # Tìm file JSON từ nhiều locations
            possible_paths = [
                json_file_path,
                os.path.join(os.getcwd(), json_file_path),
                os.path.join(os.path.dirname(__file__), '..', '..', '..', json_file_path),
                os.path.join(os.path.dirname(__file__), '..', '..', json_file_path),
                os.path.join(os.path.dirname(__file__), '..', json_file_path)
            ]
            
            json_path = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    json_path = abs_path
                    break
            
            if not json_path:
                print(f"❌ Không tìm thấy file JSON: {json_file_path}")
                return {}
            
            print(f"📂 Loading JSON: {json_path}")
            
            with open(json_path, 'r', encoding='utf-8') as f:
                chapters = json.load(f)
            
            # Convert list to dict mapping
            mapping = {}
            for chapter in chapters:
                index = chapter['index']
                mapping[index] = {
                    'title': chapter['title'],
                    'url': chapter['url']
                }
            
            print(f"📂 Loaded {len(mapping)} chapters từ JSON (theo index): {json_path}")
            return mapping
            
        except Exception as e:
            print(f"❌ Lỗi load chapter mapping: {e}")
            return {}
    
    @staticmethod
    def get_catalog_links_from_config(page, catalog_url, series_config):
        """
        Lấy danh sách URLs từ JSON mapping - STANDARD cho tất cả parsers
        
        Args:
            page: Playwright page object (không dùng)
            catalog_url: URL catalog (không dùng)
            series_config: Dict chứa json_mapping path
            
        Returns:
            list: Danh sách URLs theo thứ tự index
        """
        json_mapping = series_config.get('json_mapping')
        if not json_mapping:
            print("❌ Thiếu json_mapping trong series config")
            return []
        
        # Load mapping
        mapping = BaseParser.load_chapter_mapping(json_mapping)
        if not mapping:
            return []
        
        # Convert to ordered list theo index
        urls = []
        for index in sorted(mapping.keys()):
            urls.append(mapping[index]['url'])
        
        return urls
    
    @staticmethod
    def get_catalog_links(page, catalog_url):
        """
        Legacy method - không được sử dụng nữa
        Tất cả parsers sẽ dùng JSON mapping
        """
        print("⚠️  get_catalog_links() deprecated - sử dụng JSON mapping")
        return []
    
    @staticmethod
    @abstractmethod
    def extract_content(page, current_url):
        """
        Extract content từ trang web - PHẢI implement trong subclass
        
        Args:
            page: Playwright page object
            current_url: URL hiện tại
            
        Returns:
            dict: {
                'title': str,
                'volume': str, 
                'content': str,
                'next_url': str,
                'success': bool
            }
        """
        pass
    
    @staticmethod
    def clean_content(content):
        """
        Clean content - có thể override trong subclass
        
        Args:
            content (str): Raw content
            
        Returns:
            str: Cleaned content
        """
        if not content:
            return ""
        
        # Basic cleaning - remove zero-width characters
        import re
        
        # Remove zero-width characters
        content = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', content)
        
        # Normalize whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = content.strip()
        
        return content


class StandardParserMixin:
    """
    Mixin cung cấp standard methods cho parsers hiện tại
    Dùng để upgrade parsers mà không cần thay đổi nhiều code
    """
    
    @staticmethod
    def load_chapter_mapping(json_file_path):
        return BaseParser.load_chapter_mapping(json_file_path)
    
    @staticmethod
    def get_catalog_links_from_config(page, catalog_url, series_config):
        return BaseParser.get_catalog_links_from_config(page, catalog_url, series_config)
    
    @staticmethod
    def get_catalog_links(page, catalog_url):
        return BaseParser.get_catalog_links(page, catalog_url)
