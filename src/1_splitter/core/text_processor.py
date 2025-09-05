"""
Text processing and splitting functionality.
"""

import re
from typing import List, Tuple


class TextProcessor:
    """Handles text processing, title extraction, and content splitting."""
    
    @staticmethod
    def extract_title_and_content(content: str) -> Tuple[str, str]:
        """Extract title from first ## header and return title and content without the title."""
        lines = content.strip().split('\n')
        title = "Untitled"
        content_start_index = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for the first ## header (markdown h2)
            if line.startswith('## ') and len(line) > 3:
                # Extract title without the ## prefix
                title = line[3:].strip()
                # Remove any additional markdown formatting
                title = re.sub(r'\*\*([^*]+)\*\*', r'\1', title)  # Remove bold
                title = re.sub(r'\*([^*]+)\*', r'\1', title)  # Remove italic
                title = title.strip()
                
                # Find where content should start (skip empty lines after title)
                content_start_index = i + 1
                while (content_start_index < len(lines) and 
                       not lines[content_start_index].strip()):
                    content_start_index += 1
                break
        
        # Return title and content without the title line
        remaining_content = '\n'.join(lines[content_start_index:]).strip()
        return title, remaining_content
    
    @staticmethod
    def get_chapter_name(filename: str) -> str:
        """Extract chapter name from filename."""
        # Remove extension and extract chapter info
        import os
        base_name = os.path.splitext(filename)[0]
        # Look for chapter pattern
        chapter_match = re.search(r'chapter[_\s]*(\d+(?:\.\d+)?)', base_name, re.IGNORECASE)
        if chapter_match:
            return f"chapter_{chapter_match.group(1)}"
        else:
            # Fallback to cleaned filename
            return re.sub(r'[^a-zA-Z0-9_]', '_', base_name.lower())
    
    @staticmethod
    def split_text(text: str, max_length: int) -> List[str]:
        """Split text into segments without overlap."""
        if len(text) <= max_length:
            return [text]
        
        segments = []
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + max_length
            
            if end >= len(text):
                # Last segment
                segments.append(text[start:])
                break
            
            # Try to find a good break point (sentence, paragraph, or word boundary)
            break_point = end
            
            # Look for sentence break (. ! ?) within last 200 characters
            for i in range(min(200, end - start)):
                pos = end - i - 1
                if pos > start and text[pos] in '.!?':
                    # Check if next character is space or newline
                    if pos + 1 < len(text) and text[pos + 1] in ' \n\t':
                        break_point = pos + 1
                        break
            
            # If no sentence break found, look for paragraph break
            if break_point == end:
                for i in range(min(200, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == '\n' and pos + 1 < len(text) and text[pos + 1] == '\n':
                        break_point = pos + 2
                        break
            
            # If still no good break, look for any newline
            if break_point == end:
                for i in range(min(100, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == '\n':
                        break_point = pos + 1
                        break
            
            # If still no break, look for word boundary
            if break_point == end:
                for i in range(min(50, end - start)):
                    pos = end - i - 1
                    if pos > start and text[pos] == ' ':
                        break_point = pos + 1
                        break
            
            segments.append(text[start:break_point])
            
            # Move to next segment without overlap
            start = break_point
        
        return segments
