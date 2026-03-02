# Quality Assurance Checklist

## Functional Testing
- [ ] **Project Creation**: Can create a new project and save settings (e.g., API Key).
- [ ] **File Upload**:
    - [ ] Upload Tender Document (PDF) successfully.
    - [ ] Upload multiple Bid Documents (PDFs) successfully.
    - [ ] Verify files are saved in the correct local directory.
- [ ] **Document Processing**:
    - [ ] PDF to Markdown conversion works.
    - [ ] OCR correctly extracts text from images within the PDF.
    - [ ] Combined text is stored in the database.
- [ ] **AI Integration**:
    - [ ] Zhipu AI API Key validation works.
    - [ ] "Extract Criteria" returns valid JSON structure.
    - [ ] "Score Bids" returns scores and reasoning for each bid.
- [ ] **Results Display**:
    - [ ] Scores are displayed correctly in the table.
    - [ ] Detailed reasoning is accessible.

## Performance & Stability
- [ ] **Concurrency**:
    - [ ] Task Queue correctly limits concurrent OCR tasks to 2 (or configured limit).
    - [ ] Task Queue correctly limits concurrent LLM calls to 5 (or configured limit).
    - [ ] UI remains responsive while background tasks are running.
- [ ] **Large Files**:
    - [ ] System handles large PDFs (>50 pages) without OOM (Chunking works).
    - [ ] Uploading 5+ files concurrently queues them correctly.
- [ ] **Error Handling**:
    - [ ] Invalid API Key shows a clear error message.
    - [ ] Task failures (e.g., corrupt PDF) are reported to UI without crashing the queue.
    - [ ] Users can cancel a running task.

## UI/UX
- [ ] **Real-time Feedback**:
    - [ ] Progress bars update smoothly (per page/step).
    - [ ] Detailed activity logs are visible and scrolling.
    - [ ] Status indicators (Queued, Processing, Completed, Failed) are clear.
- [ ] "Start Evaluation" button is disabled until documents are ready.
- [ ] Responsive design (basic desktop support).
