# Target Architecture

This application strictly segments data mapping from AI logic to guarantee deterministic local-first analysis before LLMs synthesize context.

### The Stack
- **Database:** Local SQLite (`C:\health_ai_data\db\health.db`)
- **Models:** Canonical SQLAlchemy schema (`LabResult`, `RawMeasurement`).
- **Entry point:** `app.main` (CLI orchestrator mapping to Use Cases).

### Layer Constraints (ACTIVE)
1. **Application (`app/application/`):** Orchestrates logic execution natively without mutating properties itself.
   - `generate_daily_summary.py`: Wires together the DB context, the text generation domain, and the AI.
   - `ingest_lab_file.py`: Wraps both `excel_ingest.process_excel_file` and `pdf_ingest.process_pdf_file`.
   - `ingest_apple_export.py`: Wraps `xml_ingest.ingest_apple_health_xml`.
2. **Domain (`app/domain/`):** Pure deterministic computations.
   - `daily_assessment.build_health_snapshot`: Derives structured deltas using `lab_repository.get_trend_for_test`.
   - `normalization.resolve_canonical_test`: Matches raw lab names perfectly avoiding hallucinations.
3. **Ingestion (`app/ingestion/`):**
   - Parses complex PDF Layouts into chronological structs explicitly in `pdf_ingest.py`.
   - Generates SQLite `dedupe_hash` via `common.file_hashing.py` immediately mapping raw data matrices without duplication.
4. **AI Layer (`app/ai/`):**
   - Pure string context transformation. Isolated completely so prompt drifts do not impact schema processing paths.
