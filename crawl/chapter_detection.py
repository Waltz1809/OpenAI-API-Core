#!/usr/bin/env python3
"""
Chapter Detection Utilities
===========================

Các hàm tiện ích để nhận diện chương, interlude và phần đặc biệt
Sử dụng chung cho tất cả parser
"""

import re


def enhance_chapter_detection(title):
    """
    Logic đơn giản: 
    - Có 第X章 ở đầu → Chapter thường
    - Không có 第X章 ở đầu → Interlude
    
    Args:
        title: Tiêu đề chương
        
    Returns:
        dict: {
            'type': 'chapter|interlude',
            'number': int|None,
            'title': str,
            'is_special': bool
        }
    """
    if not title:
        return {
            'type': 'interlude',
            'number': None,
            'title': title or '',
            'is_special': True
        }
    
    title = title.strip()
    
    # Các pattern nhận diện chương có số 第X章
    numbered_patterns = [
        r'^第([零一二三四五六七八九十百千]+)章',  # 第一章
        r'^第(\d{1,3})章',  # 第1章
    ]
    
    # Kiểm tra xem có pattern 第X章 ở đầu không
    for pattern in numbered_patterns:
        match = re.search(pattern, title)
        if match:
            number_str = match.group(1)
            
            # Chuyển đổi số Hán tự sang số Ả Rập nếu cần
            try:
                if number_str.isdigit():
                    chapter_number = int(number_str)
                else:
                    # Thử chuyển đổi số Hán tự
                    try:
                        import cn2an
                        chapter_number = cn2an.cn2an(number_str, mode="smart")
                    except ImportError:
                        # Nếu không có cn2an, vẫn coi là chapter nhưng không có số
                        chapter_number = None
                        
                return {
                    'type': 'chapter',
                    'number': chapter_number,
                    'title': title,
                    'is_special': False
                }
                
            except (ValueError, Exception):
                # Nếu convert số thất bại, vẫn coi là chapter
                return {
                    'type': 'chapter',
                    'number': None,
                    'title': title,
                    'is_special': False
                }
    
    # Không có pattern 第X章 → Interlude
    return {
        'type': 'interlude',
        'number': None,
        'title': title,
        'is_special': True
    } 