# AI Translation Pipeline

A comprehensive pipeline for crawling, processing, translating, and uploading web novels using AI translation services (OpenAI GPT, Google Vertex AI, and Gemini).

## 📋 Features

- Web novel crawling from multiple sources
- EPUB and Wiki content conversion to Markdown
- Smart content splitting for optimal translation
- Multi-provider AI translation (OpenAI, Google Vertex AI, Gemini)
- Automatic key rotation for API keys
- Content merging and formatting
- Automated web upload

## 🔧 Setup

### Prerequisites

- Python 3.8 or higher

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Waltz1809/OpenAI-API-Core.git
cd OpenAI-API-Core
```

2. Run the setup script:
```bash
# Windows
python setup.py

# Linux/MacOS
chmod +x setup.sh
./setup.sh
```

This will:
- Install required Python dependencies
- Create necessary folder structure
- Set up logging directories

## 🚀 Usage

The pipeline consists of several modules that can be run independently or in sequence:

### 1. Content Acquisition (Job 0)

Located in `src/job_0_utils/`, includes tools for:

#### Web Crawling
```bash
python src/job_0_utils/1_crawler/bakatsuki_crawler/main.py
```
Crawls web novels from supported sources.

#### Content Conversion
```bash
# Convert EPUB to Markdown
python src/job_0_utils/2_converter/epub_to_md_convert/main.py

# Convert Wiki exports to Markdown
python src/job_0_utils/2_converter/wiki_to_md_convert/main.py
```

#### Markdown Cleaning
```bash
python src/job_0_utils/3_md_tag_clean/main.py
```
Cleans and standardizes Markdown formatting.

### 2. Content Splitting (Job 1)
```bash
python src/job_1_splitter/main.py
```
Splits content into manageable segments for translation while maintaining context.

### 3. Translation (Job 2)
```bash
python src/job_2_translator/main.py
```
Translates content using configured AI providers. Supports:
- OpenAI GPT models
- Google Vertex AI
- Google Gemini

See `MULTI_KEY_SETUP.md` for detailed API key rotation setup.

### 4. Content Merging (Job 3)
```bash
python src/job_3_merger/main.py
```
Merges translated segments back into complete chapters.

### 5. Web Upload (Job 4)
```bash
python src/job_4_uploader/main.py
```
Automates the upload process to web platforms using Playwright.

## 📁 Directory Structure

```
OpenAI-API-Core/
├─ 0_epub/ - Source EPUB files
├─ 0_wiki_export/ - Wiki export files
├─ 1_input_md/ - Converted Markdown files
├─ 2_input_segment/ - Split content segments
├─ 3_output_segment/ - Translated segments
├─ 4_output_md/ - Final merged translations
└─ src/
   ├─ job_0_utils/ - Content acquisition tools
   ├─ job_1_splitter/ - Content splitting
   ├─ job_2_translator/ - AI translation
   ├─ job_3_merger/ - Content merging
   ├─ job_4_uploader/ - Web upload automation
   └─ inventory/
      ├─ logs/ - Module-specific logs
      └─ prompts/ - Translation templates
```

## 🔍 Monitoring

Each module generates logs in `inventory/logs/<module_name>/`. Check these for:
- Processing status
- Error messages
- Translation progress
- API usage statistics

## ⚠️ Important Notes

1. Configure API rate limits in each module's config to avoid service disruption
2. Use key rotation for better resource management
3. Regular backups of input/output directories are recommended
4. Check logs regularly for any issues

## 🤝 Contributing

Me-work and GPT