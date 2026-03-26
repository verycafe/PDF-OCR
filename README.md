# PDF-OCR

A local web-based tool for PDF processing and OCR with intelligent table recognition, with DOCX/DOC support via server-side PDF conversion.

## Features

### Core Capabilities
- **DOCX/DOC Support**: Converts Word documents to PDF server-side, then reuses the existing PDF/OCR pipeline
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

**Download**:
- Docker image: preloaded during `docker build`
- Local source run: automatic on first use

### PPStructureV3
**Purpose**: Document structure analysis and table recognition

**Models Used**:
- `PP-DocBlockLayout` - Document block layout detection
- `PP-DocLayout_plus-L` - Advanced document layout analysis
- `PP-LCNet_x1_0_table_cls` - Table classification
- `PP-Chart2Table` - Chart to table conversion
- `PP-FormulaNet_plus-L` - Formula recognition (disabled by default)

**Total Size**: ~1GB

**Download**:
- Docker image: preloaded during `docker build`
- Local source run: automatic on first use (may take several minutes)

**Cache Location**:
- `~/.cache/huggingface/hub/models--PaddlePaddle--*`
- `~/.paddlex/official_models/`
- Docker image cache path: `/app/.paddlex/official_models/`

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

## Docker Deployment

Optional: create a `.env` file from the example before deployment:
```bash
cp .env.example .env
```

## GitHub Container Publishing

The repository now includes a GitHub Actions workflow at
[`/.github/workflows/docker-publish.yml`](/Users/tvwoo/Projects/PDF-OCR/.github/workflows/docker-publish.yml).

When code is pushed to `main`, GitHub Actions will build and publish the Docker image to:
```bash
ghcr.io/verycafe/pdf-ocr
```

Before the image is published, the workflow now:
- builds the Dockerized app
- starts the container locally in CI
- runs `python3 scripts/smoke-test.py`
- only publishes the GHCR image after the smoke test passes

Common tags:
```bash
ghcr.io/verycafe/pdf-ocr:latest
ghcr.io/verycafe/pdf-ocr:main
ghcr.io/verycafe/pdf-ocr:sha-<commit>
```

If the first workflow run fails with a package permission error, check the GitHub repository setting:
- `Settings -> Actions -> General -> Workflow permissions`
- ensure it is allowed to write packages / use read and write permissions

The repository can now be built from source into a single Docker image that:
- builds the Vite frontend inside the image
- serves the built frontend from Flask
- runs the backend OCR service and DOCX/DOC conversion in the same container
- preloads OCR / PPStructure models during image build so runtime startup does not need a first-use model download

Build the image:
```bash
bash scripts/docker-build.sh
```

Build and start the service:
```bash
bash scripts/docker-up.sh
```

Then open: http://localhost:5001

Start the existing image without rebuilding:
```bash
bash scripts/docker-start.sh
```

Stop the service:
```bash
bash scripts/docker-down.sh
```

View recent logs:
```bash
bash scripts/docker-logs.sh
```

Follow live logs:
```bash
bash scripts/docker-logs.sh -f app
```

Restart the running service without rebuilding:
```bash
bash scripts/docker-restart.sh
```

Show container status and HTTP health:
```bash
bash scripts/docker-status.sh
```

Open a shell inside the app container:
```bash
bash scripts/docker-shell.sh
```

Run the deployment smoke test locally:
```bash
python3 scripts/smoke-test.py
```

## First Run

When running from source outside Docker, the system will still download required models on first OCR use (~1.2GB total):
- PaddleOCR models: ~200MB
- PPStructureV3 models: ~1GB

For Docker deployments, those models are now downloaded during image build and baked into the image.

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
