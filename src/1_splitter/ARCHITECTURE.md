# Modular Text Splitter Architecture

## 📁 Directory Structure

```
src/1_splitter/
├── main.py              # Main entry point (streamlined)
├── main_old.py          # Original monolithic version (backup)
├── config.yml           # Configuration file
├── README.md            # Documentation
└── core/                # Core modules
    ├── __init__.py      # Package initialization
    ├── config.py        # Configuration management
    ├── logging.py       # Logging and tracking
    ├── text_processor.py # Text processing and splitting
    └── file_manager.py  # File I/O operations
```

## 🔧 Module Breakdown

### **Main Entry Point (`main.py`)**
- **Size**: ~150 lines (down from 500+)
- **Purpose**: Orchestrates the splitting process
- **Dependencies**: Uses all core modules
- **Responsibility**: High-level workflow coordination

### **Core Modules (`core/`)**

#### **1. ConfigManager (`config.py`)**
- **Purpose**: Configuration loading and validation
- **Features**:
  - YAML file parsing
  - Comprehensive validation
  - Type checking
  - Getter methods for each config section

#### **2. LogManager (`logging.py`)**
- **Purpose**: Logging and file tracking
- **Features**:
  - Session logging with timestamps
  - File processing history
  - Change detection via MD5 hashing
  - Progress tracking

#### **3. TextProcessor (`text_processor.py`)**
- **Purpose**: Text processing and splitting
- **Features**:
  - Title extraction from `##` headers
  - Smart text segmentation
  - Chapter name parsing
  - Content cleaning

#### **4. FileManager (`file_manager.py`)**
- **Purpose**: File I/O operations
- **Features**:
  - Project root detection
  - Directory structure creation
  - File reading/writing
  - YAML output generation

## ✨ Benefits of Modular Design

### **1. Maintainability**
- ✅ **Single Responsibility**: Each module has one clear purpose
- ✅ **Separation of Concerns**: Logic is properly separated
- ✅ **Easy Testing**: Individual modules can be tested independently

### **2. Readability**
- ✅ **Smaller Files**: Each file is focused and manageable
- ✅ **Clear Interfaces**: Well-defined module boundaries
- ✅ **Self-Documenting**: Module names clearly indicate purpose

### **3. Extensibility**
- ✅ **Easy to Extend**: Add new features to specific modules
- ✅ **Pluggable**: Modules can be replaced or enhanced independently
- ✅ **Reusable**: Core modules can be used in other projects

### **4. Debugging**
- ✅ **Isolated Issues**: Problems are contained within modules
- ✅ **Clear Stack Traces**: Easier to identify problem locations
- ✅ **Modular Testing**: Test individual components separately

## 🔄 Data Flow

```
main.py
    ↓
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
```

## 🚀 Usage

The interface remains exactly the same:

```bash
cd src/1_splitter
python main.py
```

But now the code is:
- **More maintainable** with clear module boundaries
- **Easier to test** with isolated components  
- **Better organized** with logical separation
- **More extensible** for future enhancements

## 🔧 Future Enhancements

The modular structure makes it easy to add:
- **New text processors** for different file formats
- **Alternative storage backends** (JSON, XML, database)
- **Advanced logging** with different log levels
- **Configuration hot-reloading**
- **Plugin system** for custom processors
