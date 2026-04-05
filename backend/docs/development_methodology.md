# Development Methodology

### Guiding Principles

1. **Deterministic Logic First, AI Second**
   - The AI must *never* process raw `.xlsx`, `.pdf`, or `.xml` assets natively.
   - Applications must aggressively force parsed arrays into structured Data Models (`LabResult`, `RawMeasurement`) leveraging canonical rules arrays first.
   - The LLM solely reads clean string digests formatted explicitly for summarization parameters.

2. **Domain Isolation**
   - No DB queries exist natively in `app/main.py`.
   - `app/application/*` endpoints are defined explicitly as non-destructive orchestrators linking `ingestion`, `db`, and `ai` layers harmoniously.
   - If an extraction fails, it fails gracefully at the Ingestion level explicitly mapping error matrices before it breaks DB insertion queries.

3. **Database Rules Engine**
   - Deduplication loops rely entirely on SHA256 hashed tuples natively tracked via `ImportRun` & `SourceFile` mappings natively shielding against redundant terminal executions.

4. **Future App Transferability (Finance AI)**
   - To duplicate this application for Finance: `ingestion/` maps to `csv_banks`, `domain/` groups categorization constraints, and `application/` triggers `build_finance_snapshot`. The identical Application interface guarantees zero structural loss.
