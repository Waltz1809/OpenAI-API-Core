#!/usr/bin/env python3
"""
Simple Text Splitter
- Maintains directory tree structure
- Splits MD files into YAML segments
- Clean, minimal implementation with logging
"""

import os
import sys
import yaml
from pathlib import Path
import re
import logging
import datetime
from typing import List, Dict

# -------------------------
# Paths & Config
# -------------------------
CWD = Path.cwd()
CONFIG_PATH = Path(__file__).resolve().parent  / "config.yml"
if not CONFIG_PATH.exists():
    print(f"ERROR: config.yml not found next to main.py ({CONFIG_PATH})")
    print("Create config.yml (see example in the script header), then re-run.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

OUTPUT_DIR = (CWD / config.get("OUTPUT_DIR", "./output")).resolve()
if not OUTPUT_DIR:
    print("WARNING: OUTPUT_DIR is empty in config.yml. Using './output'.")

INPUT_DIR = (CWD / config.get("INPUT_DIR", ".")).resolve()
if not INPUT_DIR:
    print("WARNING: INPUT_DIR is empty in config.yml. Using current working directory.")

SEGMENT_LENGTH = int(config.get("SEGMENT_LENGTH", 30000))
if not SEGMENT_LENGTH:
    print("WARNING: SEGMENT_LENGTH is empty in config.yml. Using 30000.")

LOG_LEVEL = config.get("logging", {}).get("LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in {'DEBUG','INFO','WARNING','ERROR','CRITICAL'}:
    print("WARNING: Invalid LOG_LEVEL in config.yml. Using 'INFO'.")
    LOG_LEVEL = "INFO"

ENABLE_LOGGING = config.get("logging", {}).get("enable_logging", True)

LOG_DIR = (CWD / config.get("logging", {}).get("logs_dir", ".")).resolve()
if not LOG_DIR:
    print("WARNING: logs_dir is empty in config.yml. Using current working directory.")


def setup_logging(config: Dict, CWD: Path) -> logging.Logger:
    """Setup logging configuration."""
    logger = logging.getLogger('splitter')
    logger.handlers.clear()  # Clear existing handlers
    
    # Set log level
    logger.setLevel(LOG_LEVEL)
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if enabled in config)
    if ENABLE_LOGGING:        
        # Create log filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = LOG_DIR / f'splitter_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Log file created: {log_file}")
    
    return logger


def extract_title(content: str) -> tuple[str, str]:
    """Extract title from first ## header."""
    lines = content.split('\n')
    title = "Untitled"
    content_start = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('## ') and len(line) > 3:
            title = line[3:].strip()
            content_start = i + 1
            break
        elif line.startswith('# ') and len(line) > 2:
            title = line[2:].strip()
            content_start = i + 1
            break
    
    # Skip empty lines after title
    while content_start < len(lines) and not lines[content_start].strip():
        content_start += 1
    
    remaining_content = '\n'.join(lines[content_start:])
    return title, remaining_content


def generate_segment_id(filename: str, segment_num: int) -> str:
    """Generate segment ID from filename."""
    base_name = Path(filename).stem
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', base_name.lower())
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    return f"{clean_name}_segment_{segment_num}"


def split_text(text: str, max_length: int) -> List[str]:
    """Split text into segments."""
    if len(text) <= max_length:
        return [text] if text.strip() else []
    
    segments = []
    start = 0
    
    while start < len(text):
        end = start + max_length
        
        if end >= len(text):
            segment = text[start:].strip()
            if segment:
                segments.append(segment)
            break
        
        # Find good break point
        break_point = end
        
        # Try paragraph break
        for i in range(min(500, end - start)):
            pos = end - i - 1
            if pos > start and pos + 1 < len(text) and text[pos:pos+2] == '\n\n':
                break_point = pos + 2
                break
        
        # Try sentence break
        if break_point == end:
            for i in range(min(300, end - start)):
                pos = end - i - 1
                if pos > start and text[pos] in '.!?' and pos + 1 < len(text) and text[pos + 1] in ' \n':
                    break_point = pos + 1
                    break
        
        # Try any newline
        if break_point == end:
            for i in range(min(200, end - start)):
                pos = end - i - 1
                if pos > start and text[pos] == '\n':
                    break_point = pos + 1
                    break
        
        segment = text[start:break_point].strip()
        if segment:
            segments.append(segment)
        start = break_point
    
    return segments


def process_file(file_path: Path, logger: logging.Logger) -> List[Dict]:
    """Process a single MD file."""
    try:
        logger.debug(f"📖 Reading file: {file_path}")
        
        # Read file as raw text
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            logger.warning(f"📄 File is empty: {file_path.name}")
            return []
        
        # Log file statistics
        file_size = len(content)
        line_count = content.count('\n') + 1
        logger.debug(f"📊 File stats: {file_size:,} chars, {line_count:,} lines")
        
        # Extract title and content
        title, text = extract_title(content)
        logger.info(f"📑 Title extracted: '{title}' from {file_path.name}")
        
        # Split into segments
        text_segments = split_text(text, SEGMENT_LENGTH)
        
        # Create segment objects and log details
        segments = []
        segment_ids = []
        for i, segment_text in enumerate(text_segments, 1):
            segment_id = generate_segment_id(file_path.name, i)
            segment_ids.append(segment_id)
            segments.append({
                'id': segment_id,
                'title': title,
                'content': segment_text
            })
            
            # Log each segment details
            segment_size = len(segment_text)
            logger.debug(f"  ✂️  Segment {i}: '{segment_id}' ({segment_size:,} chars)")
        
        # Log comprehensive file processing summary
        logger.info(f"✅ PROCESSED: {file_path.name}")
        logger.info(f"   📋 Title: '{title}'")
        logger.info(f"   📊 Original size: {file_size:,} characters, {line_count:,} lines")
        logger.info(f"   ✂️  Segments created: {len(segments)}")
        logger.info(f"   🆔 Segment IDs: {', '.join(segment_ids)}")
        
        # Calculate processing statistics
        total_segments_size = sum(len(s['content']) for s in segments)
        avg_segment_size = total_segments_size // len(segments) if segments else 0
        logger.info(f"   📈 Total segments size: {total_segments_size:,} chars")
        logger.info(f"   📊 Average segment size: {avg_segment_size:,} chars")
        
        return segments
        
    except Exception as e:
        logger.error(f"❌ ERROR processing {file_path.name}: {e}")
        return []


def save_yaml(segments: List[Dict], output_path: Path, logger: logging.Logger):
    """Save segments to YAML file."""
    try:
        os.makedirs(output_path.parent, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write YAML with |- block style
            for i, segment in enumerate(segments):
                if i > 0:
                    f.write("\n")
                
                f.write(f"- id: {segment['id']}\n")
                f.write(f"  title: '{segment['title']}'\n")
                f.write("  content: |-\n")
                
                # Write content with indentation
                for line in segment['content'].split('\n'):
                    f.write(f"    {line}\n")
        
        # Log save details
        file_size = output_path.stat().st_size
        logger.info(f"💾 SAVED: {output_path}")
        logger.info(f"   📁 Directory: {output_path.parent}")
        logger.info(f"   📊 File size: {file_size:,} bytes")
        logger.info(f"   ✂️  Contains {len(segments)} segments")
        
    except Exception as e:
        logger.error(f"❌ ERROR saving {output_path}: {e}")


def main():
    """Main function with comprehensive logging and statistics."""
    
    # Setup logging
    logger = setup_logging(config, CWD)
    
    # Fancy startup banner
    logger.info("=" * 80)
    logger.info("🚀 SIMPLE TEXT SPLITTER - ADVANCED LOGGING MODE")
    logger.info("=" * 80)
    logger.info(f"⏰ Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔧 Python version: {os.sys.version.split()[0]}")
    logger.info(f"📂 Working directory: {CWD}")
    logger.info("=" * 80)
    
    # Log configuration details
    logger.info("⚙️  CONFIGURATION:")
    logger.info(f"   📁 Input directory:  {INPUT_DIR}")
    logger.info(f"   📁 Output directory: {OUTPUT_DIR}")
    logger.info(f"   ✂️  Segment length:   {SEGMENT_LENGTH:,} characters")
    logger.info(f"   📊 Log level:        {LOG_LEVEL}")
    logger.info("-" * 80)
    
    
    # Discovery phase
    logger.info("� DISCOVERY PHASE:")
    md_files = list(INPUT_DIR.rglob('*.md'))
    logger.info(f"   📚 Found {len(md_files)} markdown files")
    
    # Organize files by directory for better logging
    dirs_map = {}
    total_input_size = 0
    
    for md_file in md_files:
        rel_path = md_file.relative_to(INPUT_DIR)
        dir_name = str(rel_path.parent) if rel_path.parent != Path('.') else 'root'
        
        if dir_name not in dirs_map:
            dirs_map[dir_name] = []
        dirs_map[dir_name].append(md_file)
        
        # Calculate total input size
        try:
            total_input_size += md_file.stat().st_size
        except:
            pass
    
    logger.info(f"   � Total input size: {total_input_size:,} bytes ({total_input_size/1024/1024:.2f} MB)")
    logger.info(f"   📁 Directories found: {len(dirs_map)}")
    
    # Log directory structure
    for dir_name, files in sorted(dirs_map.items()):
        logger.info(f"      📂 {dir_name}: {len(files)} files")
    
    logger.info("-" * 80)
    
    # Processing phase
    logger.info("⚡ PROCESSING PHASE:")
    processed_files = 0
    total_segments = 0
    failed_files = []
    file_stats = []
    
    start_time = datetime.datetime.now()
    
    for i, md_file in enumerate(md_files, 1):
        logger.info(f"📖 [{i:4d}/{len(md_files)}] Processing: {md_file.name}")
        logger.debug(f"    Full path: {md_file}")
        
        # Process file
        segments = process_file(md_file, logger)
        
        if segments:
            # Calculate output path (preserve directory structure)
            rel_path = md_file.relative_to(INPUT_DIR)
            output_file = OUTPUT_DIR / rel_path.with_suffix('.yml')
            
            # Save segments
            save_yaml(segments, output_file, logger)
            
            processed_files += 1
            total_segments += len(segments)
            
            # Track file statistics
            file_stats.append({
                'name': md_file.name,
                'path': str(rel_path),
                'title': segments[0]['title'] if segments else 'Unknown',
                'segments': len(segments),
                'segment_ids': [s['id'] for s in segments]
            })
            
            logger.info(f"   ✅ SUCCESS: {len(segments)} segments created")
        else:
            failed_files.append(md_file.name)
            logger.warning(f"   ⚠️  SKIPPED: No segments created")
        
        logger.info("-" * 40)
    
    # Final statistics
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    
    logger.info("=" * 80)
    logger.info("📊 FINAL STATISTICS")
    logger.info("=" * 80)
    logger.info(f"⏰ Processing duration: {duration}")
    logger.info(f"📚 Files discovered: {len(md_files)}")
    logger.info(f"✅ Files processed: {processed_files}")
    logger.info(f"❌ Files failed: {len(failed_files)}")
    logger.info(f"✂️  Total segments: {total_segments}")
    
    if processed_files > 0:
        avg_segments = total_segments / processed_files
        logger.info(f"📊 Average segments per file: {avg_segments:.2f}")
        
        files_per_second = processed_files / duration.total_seconds() if duration.total_seconds() > 0 else 0
        logger.info(f"⚡ Processing speed: {files_per_second:.2f} files/second")
    
    logger.info("-" * 80)
    
    # Detailed file breakdown
    if file_stats:
        logger.info("📋 DETAILED FILE BREAKDOWN:")
        logger.info("-" * 80)
        
        for i, stats in enumerate(file_stats, 1):
            logger.info(f"📄 [{i:3d}] FILE: {stats['name']}")
            logger.info(f"     📁 Path: {stats['path']}")
            logger.info(f"     📑 Title: '{stats['title']}'")
            logger.info(f"     ✂️  Segments: {stats['segments']}")
            logger.info(f"     � IDs: {', '.join(stats['segment_ids'])}")
            if i < len(file_stats):
                logger.info("-" * 40)
    
    # Failed files section
    if failed_files:
        logger.info("❌ FAILED FILES:")
        logger.info("-" * 80)
        for failed_file in failed_files:
            logger.info(f"   💥 {failed_file}")
    
    # Summary
    logger.info("=" * 80)
    logger.info("🎉 PROCESSING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"⏰ Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"✅ Success rate: {(processed_files/len(md_files)*100):.1f}%")
    logger.info(f"📊 Total output files: {processed_files}")
    logger.info(f"✂️  Total segments created: {total_segments}")
    logger.info("=" * 80)
    
    # Also print concise summary to console for immediate feedback
    print(f"🎉 Complete! Processed {processed_files}/{len(md_files)} files, Created {total_segments} segments")
    if failed_files:
        print(f"⚠️  {len(failed_files)} files failed - check log for details")


if __name__ == "__main__":
    main()
