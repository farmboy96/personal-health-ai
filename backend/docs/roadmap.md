# Roadmap

### Phase 1: Structural Cleanup (NOW)
- **Status:** COMPLETED.
- **Goal:** Move bare prototype scripts into official Domain Driven architecture.
- **Key Milestones:** Re-mapping database imports, defining App boundaries (CLI vs Domain vs Ingestion).

### Phase 2: Schema Expansion & True Rollups (LATER)
- **Status:** PENDING.
- **Goal:** Expand schema parameters allowing complex aggregate analysis models natively.
- **Key Milestones:** 
  1. Add `person_profile`, `supplements`, `health_events` tables routing complex metadata into context.
  2. Implement Apple Health 7-day and 30-day baseline computations inside `app.application.rebuild_daily_snapshot`.
  3. Expand `daily_assessment.py` to evaluate chronological delta comparisons beyond static boundaries inherently linking event context (e.g. TRT, Blood Donations, Fasting).
  4. Migrate Presentation interfaces to FastAPI powering React Web UI responses natively bypassing CLI constraints over JSON protocols.
