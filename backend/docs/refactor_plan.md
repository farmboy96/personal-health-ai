# Refactor Action Plan

### What Was Moved (Phase 1 Execution)
1. **Repository Structure**: Restructured into strict `application`, `ai`, `db`, `domain`, and `ingestion` groupings.
2. **Service Extraction**: Wrote strict application orchestration endpoints (`ingest_lab_file`, `generate_daily_summary`, etc.) binding terminal endpoints away from deeply nested script folders organically.
3. **Domain Layer Mapping**: `app.services.health.health_summary` natively split logic into pure code (`app/domain/assessment/`) vs contextual OpenAI generation logic (`app/ai/`).
4. **PDF Engine Rescue**: Re-inlined `debug_extract_lab_pdf`'s heavy lifting dependencies completely into `pdf_ingest.py` effectively restoring standalone execution locally without breaking the previous archival directives.

### What Remains Messy
1. The AI generation still directly calls `Model="gpt-5"`; this isn't globally parameterized into `config.py` yet.
2. Excel Extraction matrix still relies on the static `lab_name_normalizer.py` mappings instead of pure DB mapping. 

### Intentionally Deferred
1. True implementation of `rebuild_daily_snapshot.py` and the `daily_metrics` rollup algorithms.
