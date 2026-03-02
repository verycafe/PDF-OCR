# Development Tasks

## Phase 1: Project Setup & Backend Foundation
- [ ] Initialize Python virtual environment and install dependencies (`flask`, `flask-cors`, `zhipuai`, `peewee` or `sqlalchemy`). <!-- id: 0 -->
- [ ] Set up Flask project structure (app factory, blueprints, config). <!-- id: 1 -->
- [ ] Initialize SQLite database and define ORM models (`Project`, `Document`, `EvaluationResult`). <!-- id: 2 -->
- [ ] Create API endpoints for Project creation and listing. <!-- id: 3 -->

## Phase 2: Document Processing Pipeline
- [ ] Install and configure `pymupdf4llm` and `paddleocr`. <!-- id: 4 -->
- [ ] Implement file upload API (`POST /api/upload`) with file storage logic. <!-- id: 5 -->
- [ ] Implement robust background task queue system:
    - [ ] Create `TaskQueue` manager using `threading` and `queue.Queue`. <!-- id: 26 -->
    - [ ] Implement worker pools: separate pools for CPU-bound (OCR, max_workers=2) and I/O-bound (LLM, max_workers=5) tasks. <!-- id: 27 -->
    - [ ] Add task prioritization logic (Tender > Bid). <!-- id: 28 -->
    - [ ] Implement task cancellation mechanism. <!-- id: 29 -->
- [ ] Develop PDF processing logic:
    - [ ] Implement chunking strategy for large PDFs to optimize memory usage. <!-- id: 30 -->
    - [ ] Implement hash-based caching for OCR results. <!-- id: 31 -->
    - [ ] Convert PDF to Markdown. <!-- id: 7 -->
    - [ ] Extract images and run OCR with per-page progress updates. <!-- id: 8 -->
    - [ ] Merge text and save to database. <!-- id: 9 -->
- [ ] Implement advanced SSE feedback mechanism:
    - [ ] Define event schema (QUEUED, PROCESSING_OCR, PROCESSING_LLM, COMPLETED, FAILED). <!-- id: 32 -->
    - [ ] Integrate progress reporting into OCR and LLM loops. <!-- id: 33 -->
    - [ ] Implement log streaming for detailed activity view. <!-- id: 34 -->

## Phase 3: AI Integration (Zhipu AI)
- [ ] Implement Zhipu AI client wrapper with user-provided API Key support. <!-- id: 11 -->
- [ ] Develop Prompt Engineering module:
    - [ ] Define prompts for "Criteria Extraction". <!-- id: 12 -->
    - [ ] Define prompts for "Bid Scoring". <!-- id: 13 -->
- [ ] Implement API endpoints to trigger Extraction and Scoring tasks. <!-- id: 14 -->
- [ ] Store AI results (criteria JSON and scoring results) in the database. <!-- id: 15 -->

## Phase 4: Frontend Development
- [ ] Initialize React project with Vite and Tailwind CSS. <!-- id: 16 -->
- [ ] Create reusable UI components (UploadZone, ProgressBar, DataTable). <!-- id: 17 -->
- [ ] Build "Project Setup" page (API Key input, Project Name). <!-- id: 18 -->
- [ ] Build "Document Upload" page with real-time status updates. <!-- id: 19 -->
- [ ] Build "Evaluation Dashboard" to trigger AI tasks and view results. <!-- id: 20 -->
- [ ] Implement SSE consumption for real-time updates. <!-- id: 21 -->

## Phase 5: Integration & Testing
- [ ] Perform end-to-end testing with sample PDFs. <!-- id: 22 -->
- [ ] Optimize OCR performance (adjust threading/batching if needed). <!-- id: 23 -->
- [ ] Refine prompt templates based on test results. <!-- id: 24 -->
- [ ] Finalize UI/UX polish. <!-- id: 25 -->
