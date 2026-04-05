# Local Data Model

### Active Entities (Fully Implemented)
- **`SourceFile`**: Primary UUID index protecting against blob corruption natively by hashing origin assets before reading.
- **`ImportRun`**: Traceability container tying parsing sessions back safely.
- **`LabResult`**: The core application table mapping cross-provider blood panels into single historical points avoiding duplicate `dedupe_hash` clashes implicitly using SQLite logic natively intact.
- **`LabTestMaster` / `LabTestCatalog` / `LabTestAlias`**: Handles explicit static routing for deterministic string alignment without needing AI intervention.
- **`RawMeasurement`**: Current table used by `xml_ingest.py` tracking raw parsed XML elements.

### Phase 2 Targets (Scaffolded but not physically operational)
- **`person_profile`**: Broad meta context mapping to inject contextual biases (e.g., TRT use, gender).
- **`daily_metrics`**: Target aggregate table reducing noisy Apple Data to single integer baseline daily rollup metrics natively.
- **`supplements`**: Event tracking schema.
- **`health_events`**: Blood donation / medical event index.
- **`daily_assessments`**: Output repository persisting snapshot evaluations.
