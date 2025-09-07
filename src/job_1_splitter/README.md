# Simple Text Splitter (1_splitter)

A clean, minimal text splitter with just 3 core features and logging:

## Features

1. **Same Directory Tree**: Output maintains the same folder structure as input
2. **MD to YAML Conversion**: Each `.md` file becomes a `.yml` file with segment array  
3. **Clean Implementation**: No cache management, no complex dependencies
4. **Configurable Logging**: File-based logging with timestamps and log levels

## Usage

```bash
cd src/1_splitter
python main.py
```

## Configuration

Edit `config.yml`:

```yaml
paths:
  input: "0_markdown_exports"
  output: "input"
  logs: "src/inventory/logs/splitter"
  
processing:
  segment_length: 25000

logging:
  enable_logging: true
  log_level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  max_log_size_mb: 10
```

## Logging Features

- **Dual Output**: Console + file logging
- **Timestamped Files**: `splitter_YYYYMMDD_HHMMSS.log`
- **Log Levels**: DEBUG (detailed), INFO (normal), WARNING, ERROR
- **Structured Format**: `timestamp | level | message`
- **Configurable Path**: Set log directory in config

## Example

Input: `0_markdown_exports/volume_1/Chapter_1.md`
```markdown
## Chapter 1: The Beginning

This is the content of the chapter...
```

Output: `input/volume_1/Chapter_1.yml`
```yaml
- id: chapter_1_segment_1
  title: 'Chapter 1: The Beginning'
  content: |-
    This is the content of the chapter...
```

Log: `src/inventory/logs/splitter/splitter_20250907_144825.log`
```
2025-09-07 14:48:25,767 | INFO | 🚀 Simple Text Splitter Started
2025-09-07 14:48:25,768 | INFO | Processed Chapter_1.md: 1 segments created
2025-09-07 14:48:25,769 | INFO | Saved: input/volume_1/Chapter_1.yml
```

Simple, focused, and now with proper logging!

### Core Functionality
- **Smart Text Splitting**: Breaks text at natural boundaries (sentences, paragraphs, words)
- **Markdown Title Extraction**: Extracts `##` headers as titles, excludes them from content
- **Configurable Segments**: Customizable segment length and file type filtering
- **Structure Preservation**: Maintains input directory hierarchy in output
- **YAML Output**: Structured output with unique IDs, titles, and content

### Advanced Features
- **Progress Tracking**: Comprehensive logging with timestamps
- **Resume Capability**: Skip already processed files automatically
- **Change Detection**: Only reprocess files when content changes
- **Cache Management**: Automatic Python cache cleaning utilities
- **Error Handling**: Robust error logging and recovery
- **Modular Architecture**: Clean, maintainable code structure

## 📁 Architecture

### Directory Structure
```
src/1_splitter/
├── main.py              # Main entry point (streamlined)
├── clean_cache.py       # Standalone cache cleaning utility
├── config.yml           # Configuration file
├── README.md            # This documentation
├── ARCHITECTURE.md      # Detailed architecture notes
└── core/                # Core modules
    ├── __init__.py      # Package initialization
    ├── config.py        # Configuration management
    ├── logging.py       # Logging and tracking
    ├── text_processor.py # Text processing and splitting
    ├── file_manager.py  # File I/O operations
    └── cache_manager.py # Python cache management
```

### Module Responsibilities

#### **Main Entry Point (`main.py`)**
- **Size**: ~200 lines (streamlined from 500+)
- **Purpose**: Orchestrates the splitting process
- **Features**: Command-line interface, workflow coordination

#### **Core Modules (`core/`)**

**ConfigManager (`config.py`)**
- Configuration loading and validation
- YAML file parsing with type checking
- Getter methods for each config section

**LogManager (`logging.py`)**
- Session logging with timestamps
- File processing history with MD5 hashing
- Progress tracking and change detection

**TextProcessor (`text_processor.py`)**
- Title extraction from `##` headers
- Smart text segmentation with boundary detection
- Chapter name parsing from filenames

**FileManager (`file_manager.py`)**
- Project root detection and working directory management
- Directory structure creation and file I/O
- YAML output generation

**CacheManager (`cache_manager.py`)**
- Python cache file detection and removal
- Cache size calculation and reporting
- Safe cleanup with error handling

## ⚙️ Configuration

The module uses a structured configuration file (`config.yml`):

### Paths Configuration
```yaml
paths:
  input: "0_markdown_exports/Volume_1A"  # Source directory
  output: "input"                        # Destination for segments
  logs: "src/inventory/logs/splitter"    # Log files directory
```

### Processing Configuration
```yaml
processing:
  file_types:                     # Supported file extensions
    - ".md"
    - ".txt"
  segment_length: 10000          # Maximum characters per segment
```

### Logging & Tracking Configuration
```yaml
logging:
  enable_logging: true           # Enable comprehensive logging
  skip_processed: false          # Process all files (true to skip unchanged)
```

## 🎯 Usage

### Basic Text Splitting
```bash
cd src/1_splitter
python main.py
```

### Cache Management
```bash
# Clean Python cache files during splitting
python main.py --clean-cache

# Dry run - see what would be cleaned
python main.py --clean-cache --dry-run

# Standalone cache cleaner (interactive)
python clean_cache.py
```

### What Happens During Processing
1. **Initialization**: Validates config, sets up logging, finds project root
2. **File Discovery**: Scans input directory for supported file types
3. **Change Detection**: Checks processing history, skips unchanged files
4. **Text Processing**: Extracts titles from `##` headers, splits content
5. **Output Generation**: Saves structured YAML segments
6. **Cleanup**: Updates processing log, optionally cleans cache

## 📄 Output Format

Each input file generates one YAML file containing all its segments:

```yaml
- id: chapter_1_segment_1
  title: "Afterword"  # Extracted from ## header
  content: |
    Okay. If you are here for the first time, welcome.
    If not, I'm glad we could meet again...

- id: chapter_1_segment_2
  title: "Afterword"  # Same title for all segments from same file
  content: |
    As always, I have ended up creating my usual type
    of fairy tale that you can't call science fiction...
```

## 🔧 Technical Details

### Title Processing
- **Extraction**: Finds first `##` header in markdown files
- **Cleaning**: Removes markdown formatting (`**bold**`, `*italic*`)
- **Exclusion**: Title header is NOT included in segment content
- **Fallback**: Uses "Untitled" if no header found

### Smart Text Splitting
The splitter uses a hierarchical approach for optimal break points:
1. **Sentence Boundaries**: `.`, `!`, `?` followed by space/newline
2. **Paragraph Breaks**: Double newlines (`\n\n`)
3. **Line Breaks**: Single newlines as fallback
4. **Word Boundaries**: Last resort splitting at spaces

### Cache Management
- **Detection**: Finds all `__pycache__` directories and `.pyc` files
- **Size Reporting**: Calculates total cache size in human-readable format
- **Safe Removal**: Handles errors gracefully during cleanup
- **Confirmation**: Interactive mode requires user confirmation

### Directory Structure Preservation
```
Input:  0_markdown_exports/Volume_1A/Chapter_01.md
Output: input/Volume_1A/Chapter_01.yml
```

## 📊 Logging & Tracking

### Session Logs
- **Location**: `{log_path}/splitter_log_YYYYMMDD_HHMMSS.txt`
- **Content**: Timestamped events, errors, statistics
- **Format**: Human-readable with structured timestamps

### Processing History
- **Location**: `{log_path}/processed_files.json`
- **Purpose**: Tracks completed files with content hashes
- **Benefit**: Enables resumable processing and change detection

### Log Output Example
```
[2025-09-05 14:30:15] Starting Text Splitter...
[2025-09-05 14:30:15] Found OpenAI-API-Core directory: d:\Storage\novel\OpenAI-API-Core
[2025-09-05 14:30:15] Changed working directory to: d:\Storage\novel\OpenAI-API-Core
[2025-09-05 14:30:15] Found 45 files to process
[2025-09-05 14:30:16] Processing: Chapter_01.md
[2025-09-05 14:30:16] Processed Chapter_01.md: 3 segments created
[2025-09-05 14:30:16] Saved 3 segments to Chapter_01.yml
[2025-09-05 14:30:17] Python cache size: 2.3 MB
[2025-09-05 14:30:17] Tip: Use --clean-cache to clean Python cache files
```

## 🔧 Customization

### Adding File Types
```yaml
processing:
  file_types:
    - ".md"
    - ".txt"
    - ".rtf"    # Add new types
    - ".docx"
```

### Adjusting Segment Size
```yaml
processing:
  segment_length: 15000  # Increase for larger segments
```

### Disabling Tracking
```yaml
logging:
  enable_logging: false  # Disable all logging
  skip_processed: false  # Process all files every time
```

## 🛠️ Error Handling

The module includes comprehensive error handling:
- **Configuration Validation**: Clear messages for missing/invalid config
- **File Access Errors**: Detailed logging with specific file information
- **Cache Cleanup Errors**: Safe handling of permission/access issues
- **Directory Creation**: Automatic creation of missing directories
- **Encoding Issues**: Graceful handling of various text encodings

## 🚀 Performance & Benefits

### Modular Design Benefits
- ✅ **Maintainable**: Single responsibility principle, clean interfaces
- ✅ **Testable**: Isolated modules for independent testing
- ✅ **Extensible**: Easy to add new features to specific modules
- ✅ **Reusable**: Core modules can be used in other projects

### Processing Efficiency
- ✅ **Change Detection**: Only processes modified files
- ✅ **Memory Optimized**: Streams large files without full loading
- ✅ **Fast Scanning**: Efficient file system traversal
- ✅ **Cache Management**: Automated cleanup prevents disk bloat

### Data Flow
```
ConfigManager → Load and validate configuration
     ↓
FileManager → Find project root, discover input files
     ↓
LogManager → Check processing history, setup logging
     ↓
TextProcessor → Extract titles, split content into segments
     ↓
FileManager → Save segments to YAML files
     ↓
LogManager → Update processing history, log completion
     ↓
CacheManager → Report cache size, optional cleanup
```

## 🔄 Future Enhancements

The modular structure makes it easy to add:
- **New text processors** for different file formats (PDF, DOCX, HTML)
- **Alternative storage backends** (JSON, XML, database)
- **Advanced logging** with different log levels and filters
- **Configuration hot-reloading** for dynamic settings
- **Plugin system** for custom text processing algorithms
- **Parallel processing** for faster file processing
- **Web interface** for remote operation and monitoring
