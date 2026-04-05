import os

base = r'c:/Users/Owner/OneDrive/Family/Personal-Health-AI/backend'

docs = {
    'architecture.md': """# Architecture
App Purpose: Local-first Personal Health Intelligence App mapping raw bio-data into actionable insights.
Principles:
- Deterministic parsing First (Ingestion/Domain) -> AI Interpretation Second (AI).
- Total structural separation of Application Use Cases, Domain models, and Database mappings.
- Current format: CLI-first, SQLite native.
- Future API layers planned for Phase 2 via FastAPI.
""",
    'data_model.md': """# Data Model
Current State:
- `lab_results`: Core relational matrix storing historical blood metrics.
Future Entities (Phase 2):
- `person_profile`
- `daily_metrics`
- `supplements`
- `health_events`
- `daily_assessments`
""",
    'daily_assessment_logic.md': """# Daily Assessment Logic
Inputs: Cross-sectional snapshot of recent apple health daily metrics and latest clinical labs.
Deterministic Layer: Prioritized flags, computed averages, and trends.
AI Interpretation Layer: The AI ingests the clean deterministic snapshot (NOT the raw files) and outputs contextualized feedback.
""",
    'refactor_plan.md': """# Refactor Plan
What was moved: Cleaned entire prototype root into Domain Driven Design (Application, Domain, Presentation, AI, Ingestion).
What remains messy: Some PDF extraction logic and Apple Health batch transaction states are deferred for deeper isolation later.
Next passes: Migrate Fast API structure, implement remaining Phase 2 Tables.
""",
    'development_methodology.md': """# Development Methodology
- Deterministic first, AI second. Canonical schemas hold truth.
- Domain isolated cleanly from Presentation.
- Application patterns expose explicit execution endpoints for orchestration avoiding script sprawl.
- Same pattern directly transferable to Finance AI applications next.
""",
    'roadmap.md': """# Roadmap
- NOW Phase 1: Structural cleanup.
- LATER Phase 2: Schema expansion (profile, supplements, events).
- LATER Phase 2: Apple Health Baseline 30-day rollups.
- LATER Phase 2: AI Context expansion (Male, TRT, blood donations).
- LATER Phase 2: Transition from episodic to True Daily Health AI.
- LATER Phase 2: API Layer / React.
"""
}

for name, content in docs.items():
    with open(os.path.join(base, 'docs', name), 'w', encoding='utf-8') as f:
        f.write(content)

services = {
    'app/application/ingest_lab_file.py': """from app.ingestion.labs.excel_ingest import process_excel_file
from app.db.database import SessionLocal

def execute_excel_ingest(filepath: str):
    print(f"Executing Lab Ingestion Application Service: {filepath}")
    # Minimal orchestration wrapper
    pass
""",
    'app/application/ingest_apple_export.py': """from app.ingestion.apple_health.xml_ingest import stream_apple_health_xml

def execute_apple_ingest(filepath: str):
    print(f"Executing Apple Health Application Service: {filepath}")
    pass
""",
    'app/application/generate_daily_summary.py': """from app.db.database import SessionLocal
from app.domain.assessment.daily_assessment import build_health_snapshot, build_summary_text
from app.ai.health_interpreter import generate_ai_insights

def execute_daily_summary():
    db = SessionLocal()
    snapshot = build_health_snapshot(db)
    summary = build_summary_text(snapshot)
    ai_output = generate_ai_insights(summary)
    return summary, ai_output
""",
    'app/application/rebuild_daily_snapshot.py': """
def execute_rebuild_snapshot():
    print("Scaffold: Rebuilds existing daily metrics into deterministic table (Phase 2 target).")
    pass
"""
}

domain_ai = {
    'app/domain/assessment/daily_assessment.py': """from app.db.repositories.lab_repository import get_trend_for_test

def build_health_snapshot(db):
    metrics = {}
    key_tests = ["TSH", "HEMOGLOBIN_A1C", "VITAMIN_D", "TESTOSTERONE_TOTAL", "ESTRADIOL", "FERRITIN", "HS_CRP", "HOMOCYSTEINE"]
    for test in key_tests:
        trend = get_trend_for_test(db, test)
        if not trend: continue
        latest = trend[-1]
        previous = trend[-2] if len(trend) > 1 else None
        metrics[test] = {
            "latest": latest, "previous": previous,
            "delta": (latest["value"] - previous["value"] if previous and latest["value"] is not None and previous["value"] is not None else None)
        }
    return metrics

def build_summary_text(snapshot):
    lines = []
    for test, data in snapshot.items():
        latest = data["latest"]
        delta = data["delta"]
        line = f"{test}: {latest['value']} {latest['unit']}"
        if delta is not None:
            if delta > 0: line += f" (↑ {abs(delta):.2f})"
            elif delta < 0: line += f" (↓ {abs(delta):.2f})"
            else: line += " (no change)"
        if latest["flag"]: line += f" [FLAG: {latest['flag']}]"
        lines.append(line)
    return "\\n".join(lines)
""",
    'app/ai/client.py': """import os
from openai import OpenAI

def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
""",
    'app/ai/health_interpreter.py': """from app.ai.client import get_openai_client

def generate_ai_insights(summary_text: str) -> str:
    prompt = f"You are a blunt, practical health analyst...\\nData:\\n{summary_text}"
    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You analyze health data and give concise, practical insights."},
                {"role": "user", "content": prompt}
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI Generation Failed: {e}"
"""
}

for name, content in {**services, **domain_ai}.items():
    with open(os.path.join(base, name), 'w', encoding='utf-8') as f:
        f.write(content)

print("Docs, Services, and Domain extraction completed successfully.")
