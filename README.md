# PDF-OCR

A local web-based tool for PDF processing and OCR with intelligent table recognition.

## Features

### Core Capabilities
- **PDF Native Table Extraction**: Automatically detects and converts PDF native tables to Markdown format
- **Image OCR**: Recognizes text in images using PaddleOCR 3.4.0
- **Image Table Recognition**: Detects and extracts tables from images using PPStructureV3
- **Page-by-Page Processing**: Analyzes PDF pages element by element (text, tables, images)
- **Markdown Output**: Generates clean Markdown files with preserved table structures

### Processing Pipeline

```
PDF Document
    ↓
┌───────────────────────────────────────┐
│  Page-by-Page Layout Analysis        │
│  (PyMuPDF)                           │
└───────────────────────────────────────┘
    ↓
┌─────────────┬─────────────┬─────────────┐
│   Text      │   Tables    │   Images    │
│   Blocks    │             │             │
└─────────────┴─────────────┴─────────────┘
    ↓              ↓              ↓
Direct         PyMuPDF        Export to
Extract        Extract        PNG files
    ↓              ↓              ↓
               Convert to     PPStructureV3
               Markdown       Layout Detection
                  ↓              ↓
                            ┌────────┬────────┐
                            │ Table? │  Text? │
                            └────────┴────────┘
                                ↓        ↓
                            Table    PaddleOCR
                            Recognition  3.4.0
                                ↓        ↓
                            Markdown  Text
                            Table    Extract
    ↓              ↓              ↓
┌─────────────────────────────────────────┐
│  Merge All Content by Page Order       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Text Cleaning & Formatting             │
│  - Remove headers/footers               │
│  - Remove watermarks                    │
│  - Merge duplicate table headers        │
└─────────────────────────────────────────┘
    ↓
Final Markdown Output
```

## Model Dependencies

### PaddleOCR 3.4.0
**Purpose**: Text recognition in images

**Models Used**:
- `PP-OCRv5_server_det` - Text detection
- `PP-OCRv5_server_rec` - Text recognition

**Size**: ~200MB

**Download**: Automatic on first use

### PPStructureV3
**Purpose**: Document structure analysis and table recognition

**Models Used**:
- `PP-DocBlockLayout` - Document block layout detection
- `PP-DocLayout_plus-L` - Advanced document layout analysis
- `PP-LCNet_x1_0_table_cls` - Table classification
- `PP-Chart2Table` - Chart to table conversion
- `PP-FormulaNet_plus-L` - Formula recognition (disabled by default)

**Total Size**: ~1GB

**Download**: Automatic on first use (may take several minutes)

**Cache Location**:
- `~/.cache/huggingface/hub/models--PaddlePaddle--*`
- `~/.paddlex/official_models/`

### PyMuPDF (fitz)
**Purpose**: PDF parsing and native table extraction

**Version**: 1.27.1

**No additional models required**

## Setup

1.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run the backend:
    ```bash
    python run.py
    ```

4.  Run the frontend (in another terminal):
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

5.  Open browser: http://localhost:5173

## First Run

On first run, the system will download required models (~1.2GB total):
- PaddleOCR models: ~200MB
- PPStructureV3 models: ~1GB

This is a one-time download. Subsequent runs will use cached models.

## System Requirements

- **Python**: 3.8+
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 2GB for models and processing
- **OS**: macOS, Linux, Windows

## Version 2.0 Updates

### Major Changes
- Migrated from pymupdf4llm to PyMuPDF for fine-grained control
- Added PDF native table extraction with structure preservation
- Upgraded to PaddleOCR 3.4.0 with new API
- Integrated PPStructureV3 for image table recognition
- Implemented page-by-page element classification

### Performance Improvements
- Text extraction no longer requires OCR (faster)
- PDF native tables preserve formatting
- Intelligent image type detection (table vs text)

### Known Limitations
- Image table recognition requires ~1GB model download
- Complex merged cells in tables may not be perfectly preserved
- Formula recognition is disabled by default (can be enabled)

## Development Status

See `tasks.md` for the current development roadmap.
