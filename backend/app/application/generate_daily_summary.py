from sqlalchemy import desc, or_

from app.ai.health_interpreter import generate_ai_insights
from app.db.database import SessionLocal
from app.db.models import GeneticVariant
from app.domain.assessment.apple_health_rollup import compute_rollups, format_rollup_block
from app.domain.assessment.daily_assessment import build_health_snapshot, build_summary_text


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

        genetics_rows = (
            db.query(GeneticVariant)
            .filter(
                or_(GeneticVariant.repute == "Bad", GeneticVariant.magnitude >= 2.5)
            )
            .order_by(desc(GeneticVariant.magnitude))
            .limit(20)
            .all()
        )
        genetic_lines = []
        for r in genetics_rows:
            mag_disp = r.magnitude if r.magnitude is not None else "?"
            genes = r.genes or ""
            summ = (r.summary or "").replace("\n", " ").strip()
            genetic_lines.append(
                f"{r.rsid}({r.genotype}) mag={mag_disp} [{genes}]: {summ}"
            )
        genetic_context = "\n".join(genetic_lines) if genetic_lines else None

        rollups = compute_rollups(db)
        physiology_block = format_rollup_block(rollups)
        physiology_context = physiology_block.strip() or None

        ai_output = generate_ai_insights(
            summary,
            genetic_context=genetic_context,
            physiology_context=physiology_context,
        )

        return {
            "snapshot_data": snapshot,
            "summary_text": summary,
            "physiology_rollups": physiology_block,
            "ai_insights": ai_output,
        }
    finally:
        db.close()
