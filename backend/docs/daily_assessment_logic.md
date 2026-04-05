# Daily Assessment Logic

### The Objective
Transform large fragmented datasets into intelligent situational context daily without hallucination risk.

### Pipeline Stage 1: Deterministic Filtering (Implemented)
- Orchestrated via `app/domain/assessment/daily_assessment.py`.
- **Logic**: Executes static queries (`get_trend_for_test` in `app/db/repositories/lab_repository.py`) pulling only specifically named panels.
- Matches `latest` against `previous` to natively calculate absolute mathematical constraints (deltas).
- Compiles the string snapshot organically.

### Pipeline Stage 2: AI Logic Translation (Implemented)
- Executed silently via `app/ai/health_interpreter.py`.
- Ingests cleanly organized output from Stage 1 into the `gpt-5` matrix.
- Enforces strict analytical parameters (No fluff, Practical Actions, Highlight Trends).

### Pipeline Stage 3: Rollup Expansion (Phase 2 Target)
- Future requirement inside `app/application/rebuild_daily_snapshot.py` to synthesize fast-moving Apple Health metrics dynamically directly alongside slow-moving labs.
