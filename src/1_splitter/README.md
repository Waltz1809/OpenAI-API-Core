# Text Splitter Module

A robust text processing module that intelligently splits large text files into manageable segments for translation pipelines. Features smart boundary detection, progress tracking, and resumable processing.

## 🚀 Features

### Core Functionality
- **Smart Text Splitting**: Breaks text at natural boundaries (sentences, paragraphs, words)
- **Configurable Segments**: Customizable segment length and file type filtering
- **Structure Preservation**: Maintains input directory hierarchy in output
- **YAML Output**: Structured output with unique IDs, titles, and content

### Advanced Features
- **Progress Tracking**: Comprehensive logging with timestamps
- **Resume Capability**: Skip already processed files automatically
- **Change Detection**: Only reprocess files when content changes
- **Error Handling**: Robust error logging and recovery

## 📁 Configuration

The module uses a structured configuration file (`config.yml`) organized into logical sections:

### Paths Configuration
```yaml
paths:
  input: "0_markdown_exports"      # Source directory for input files
  output: "output/split_segments"  # Destination for processed segments
  logs: "logs/splitter"           # Directory for log files
```

### Processing Configuration
```yaml
processing:
  file_types:                     # Supported file extensions
    - ".md"
    - ".txt"
  segment_length: 2000           # Maximum characters per segment
```

### Logging & Tracking Configuration
```yaml
logging:
  enable_logging: true           # Enable comprehensive logging
  skip_processed: true           # Skip unchanged files on restart
```

## 🎯 Usage

### Basic Usage
```bash
cd src/1_splitter
python main.py
```

### What Happens
1. Scans input directory for supported file types
2. Checks processing history (if tracking enabled)
3. Processes only new or changed files
4. Splits text into segments with smart boundaries
5. Saves structured YAML output
6. Updates processing log

## 📄 Output Format

Each input file generates one YAML file containing all its segments:

```yaml
- id: chapter_1_segment_1
  title: "Participants in a Chance Meeting by the Storefront"
  content: |
    ## Chapter 01: Participants in a Chance Meeting by the Storefront
    
    Your life exists
    In order to meet
    What then, does a meeting mean...

- id: chapter_1_segment_2
  title: "Participants in a Chance Meeting by the Storefront" 
  content: |
    Point Allocation (Life)
    
    The morning sun cast long shadows...
```

## 🔧 Technical Details

### ID Generation
- **Format**: `chapter_x_segment_y`
- **Chapter Extraction**: Intelligent parsing from filename patterns
- **Segment Numbering**: Sequential numbering within each file

### Title Extraction
- Extracted from first meaningful line of content
- Automatically removes Markdown formatting (`##`, `**`, `*`)
- Falls back to "Untitled" if no title found

### Smart Text Splitting
The splitter uses a hierarchical approach to find optimal break points:
1. **Sentence Boundaries**: Looks for `.`, `!`, `?` followed by space/newline
2. **Paragraph Breaks**: Finds double newlines (`\n\n`)
3. **Line Breaks**: Falls back to single newlines
4. **Word Boundaries**: Last resort splitting at spaces

### Directory Structure
Input structure is perfectly mirrored in output:
```
Input:  0_markdown_exports/Volume_1A/Chapter_01.md
Output: output/split_segments/Volume_1A/Chapter_01.yml
```

## 📊 Logging & Tracking

### Session Logs
- **Location**: `logs/splitter/splitter_log_YYYYMMDD_HHMMSS.txt`
- **Content**: Timestamped processing events, errors, statistics
- **Format**: Human-readable with structured timestamps

### Processing History
- **Location**: `logs/splitter/processed_files.json`
- **Purpose**: Tracks completed files with content hashes
- **Benefit**: Enables resumable processing and change detection

### Log Output Example
```
[2025-09-05 14:30:15] Starting Text Splitter...
[2025-09-05 14:30:15] Found 45 files to process
[2025-09-05 14:30:15] Skipping 12 already processed files
[2025-09-05 14:30:16] Processing: Chapter_01.md
[2025-09-05 14:30:16] Processed Chapter_01.md: 3 segments created
[2025-09-05 14:30:16] Saved 3 segments to Chapter_01.yml
```

## ⚙️ Customization

### Adding File Types
```yaml
processing:
  file_types:
    - ".md"
    - ".txt"
    - ".rtf"    # Add new types here
    - ".docx"
```

### Adjusting Segment Size
```yaml
processing:
  segment_length: 3000  # Increase for larger segments
```

### Disabling Tracking
```yaml
logging:
  enable_logging: false  # Disable all logging
  skip_processed: false  # Process all files every time
```

## 🛠️ Error Handling

The module includes comprehensive error handling:
- **File Access Errors**: Logged with specific file information
- **Encoding Issues**: Handles various text encodings gracefully
- **Configuration Errors**: Clear error messages for invalid config
- **Directory Creation**: Automatically creates missing output directories

## 📈 Performance

- **Efficient Processing**: Only processes changed files
- **Memory Optimized**: Streams large files without loading entirely
- **Fast Scanning**: Quick file system traversal with glob patterns
- **Parallel Ready**: Architecture supports future parallel processing
