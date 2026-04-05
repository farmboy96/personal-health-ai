from app.db.database import SessionLocal
from app.domain.assessment.daily_assessment import build_health_snapshot, build_summary_text
from app.ai.health_interpreter import generate_ai_insights

def execute_daily_summary():
    """
    Core application orchestration:
    1. Loads deterministically filtered data via DB.
    2. Builds normalized text snapshot.
    3. Triggers AI assessment.
    Returns structured dict, does not print to console.
    """
    db = SessionLocal()
    try:
        snapshot = build_health_snapshot(db)
        summary = build_summary_text(snapshot)
        ai_output = generate_ai_insights(summary)
        
        return {
            "snapshot_data": snapshot,
            "summary_text": summary,
            "ai_insights": ai_output
        }
    finally:
        db.close()
