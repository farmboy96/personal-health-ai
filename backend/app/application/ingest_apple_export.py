from app.db.database import SessionLocal
from app.ingestion.apple_health.xml_ingest import ingest_apple_health_xml

def execute_ingest_apple_export(xml_filepath: str):
    """
    Application service wrapper executing deterministic Apple Health iteration loops.
    """
    db = SessionLocal()
    try:
        ingest_apple_health_xml(db, xml_filepath)
    finally:
        db.close()
