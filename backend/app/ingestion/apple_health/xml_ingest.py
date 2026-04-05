import os
import sys
import hashlib
import argparse
from datetime import datetime
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert

# Allow module to be executed from backend root via `python -m app.ingestion.apple_health.xml_ingest`
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal, engine
from app.db.models import SourceFile, ImportRun, RawMeasurement
from app.core.config import settings

def calculate_file_hash(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def parse_date(date_str: str) -> datetime:
    """Robustly parses Apple Health dates and safely strips timezone."""
    if not date_str:
        raise ValueError("Empty date string")
        
    cleaned = date_str.strip()
    
    try:
        # Apple Health standard format: "2024-03-22 17:34:25 -0400"
        dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S %z")
        return dt.replace(tzinfo=None)
    except ValueError:
        try:
            # Fallback: No timezone
            return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Fallback: ISO format
                return datetime.fromisoformat(cleaned.replace('Z', '+00:00')).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Failed to parse date: {date_str}")

def ingest_apple_health_xml(db: Session, xml_filepath: str):
    print(f"[INFO] Starting fast-batch ingestion of Apple Health XML from {xml_filepath}")
    
    start_time = datetime.utcnow()
    
    if not os.path.exists(xml_filepath):
        print(f"[ERROR] File not found at {xml_filepath}")
        return

    # Apply SQLite performance Pragmas directly bounding to the open connection context via the session engine
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.execute(text("PRAGMA temp_store=MEMORY;"))

    # 1. Register Source File
    file_hash = calculate_file_hash(xml_filepath)
    filename = os.path.basename(xml_filepath)
    
    source_file = db.query(SourceFile).filter(SourceFile.file_hash == file_hash).first()
    if not source_file:
        source_file = SourceFile(
            filename=filename,
            file_hash=file_hash,
            file_type='xml',
            stored_path=os.path.abspath(xml_filepath),
            source_category='apple_health',
            created_at=start_time
        )
        db.add(source_file)
        db.commit()
        db.refresh(source_file)
        print(f"[INFO] Created new SourceFile tracking record (id: {source_file.id})")
    else:
        print(f"[INFO] Reprocessing existing file (id: {source_file.id})")

    # 2. Create Import Run Tracking
    import_run = ImportRun(
        source_file_id=source_file.id,
        import_type='apple_health_xml',
        start_time=start_time,
        status='running',
        records_seen=0,
        records_added=0,
        records_skipped=0
    )
    db.add(import_run)
    db.commit()
    db.refresh(import_run)
    print(f"[INFO] Created ImportRun (id: {import_run.id})")

    # Re-expanding architecture to cover ALL targeted metrics 
    ALLOWED_TYPES = {
        "HKQuantityTypeIdentifierBodyMass",
        "HKQuantityTypeIdentifierBodyMassIndex",
        "HKQuantityTypeIdentifierHeartRate",
        "HKQuantityTypeIdentifierRestingHeartRate",
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "HKQuantityTypeIdentifierRespiratoryRate",
        "HKQuantityTypeIdentifierOxygenSaturation",
        "HKQuantityTypeIdentifierBodyTemperature",
        "HKQuantityTypeIdentifierStepCount",
        "HKQuantityTypeIdentifierDistanceWalkingRunning",
        "HKQuantityTypeIdentifierActiveEnergyBurned",
        "HKQuantityTypeIdentifierBasalEnergyBurned",
        "HKQuantityTypeIdentifierAppleExerciseTime",
        "HKQuantityTypeIdentifierWalkingHeartRateAverage",
        "HKQuantityTypeIdentifierVO2Max",
        "HKCategoryTypeIdentifierSleepAnalysis",
        "HKQuantityTypeIdentifierBodyFatPercentage",
        "HKQuantityTypeIdentifierLeanBodyMass"
    }

    # Intelligent Payload scoping defaults tracking high yield troubleshooting targets exclusively
    SELECTED_PAYLOAD_METRICS = {
        "HKCategoryTypeIdentifierSleepAnalysis",
        "HKQuantityTypeIdentifierRestingHeartRate",
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "HKQuantityTypeIdentifierVO2Max",
        "HKClinicalRecord"
    }

    BATCH_SIZE = 2000
    batch_buffer = []

    def flush_batch():
        if not batch_buffer:
            return
            
        # Bulk Insert leveraging SQLite deterministic `INSERT OR IGNORE` fallback avoiding session corruption
        stmt = insert(RawMeasurement).values(batch_buffer)
        stmt = stmt.on_conflict_do_nothing(index_elements=['dedupe_hash'])
        
        result = db.execute(stmt)
        
        records_pushed = result.rowcount
        records_skipped_locally = len(batch_buffer) - records_pushed
        
        import_run.records_added += records_pushed
        import_run.records_skipped += records_skipped_locally
        
        db.commit()
        batch_buffer.clear()
        
        print(f"[INFO] Processed batch. Total seen: {import_run.records_seen}, added: {import_run.records_added}, skipped: {import_run.records_skipped}")

    try:
        context = ET.iterparse(xml_filepath, events=("end",))
        
        for event, elem in context:
            if elem.tag == 'Record':
                import_run.records_seen += 1
                metric_type = elem.get('type')
                
                if metric_type in ALLOWED_TYPES:
                    source_name = elem.get('sourceName', 'Unknown')
                    source_version = elem.get('sourceVersion')
                    device = elem.get('device')
                    start_date_str = elem.get('startDate')
                    end_date_str = elem.get('endDate')
                    value_str = elem.get('value')
                    unit = elem.get('unit')
                    
                    if not all([start_date_str, end_date_str, value_str]):
                        import_run.records_skipped += 1
                        elem.clear()
                        continue
                        
                    try:
                        start_date = parse_date(start_date_str)
                        end_date = parse_date(end_date_str)
                    except ValueError as ve:
                        print(f"[WARN] Skipping record due to parsing error: {ve}")
                        import_run.records_skipped += 1
                        elem.clear()
                        continue
                    
                    # Refinement path separating explicit numeric versus categorical string values robustly natively
                    parsed_value = None
                    value_text = None
                    
                    try:
                        parsed_value = float(value_str)
                        hash_val_str = str(parsed_value)
                    except ValueError:
                        # Ensures categorical records map independently uncorrupted tracking alongside standard units unharmed
                        value_text = value_str
                        hash_val_str = value_text.lower().strip()
                        
                    raw_hash_string = f"{metric_type}{start_date.isoformat()}{end_date.isoformat()}{hash_val_str}{source_name.lower().strip()}"
                    dedupe_hash = hashlib.sha256(raw_hash_string.encode('utf-8')).hexdigest()
                    
                    # Implementation of dynamic payload persistence policy architecture
                    raw_payload = None
                    policy = getattr(settings, 'PAYLOAD_STORAGE_POLICY', 'selected_metrics').lower()
                    
                    if policy == 'all':
                        raw_payload = ET.tostring(elem, encoding='unicode')
                    elif policy == 'selected_metrics' and metric_type in SELECTED_PAYLOAD_METRICS:
                        raw_payload = ET.tostring(elem, encoding='unicode')
                    
                    batch_buffer.append(dict(
                        source_file_id=source_file.id,
                        import_run_id=import_run.id,
                        metric_type=metric_type,
                        source_name=source_name,
                        source_version=source_version,
                        device=device,
                        start_date=start_date,
                        end_date=end_date,
                        value=parsed_value,
                        value_text=value_text,
                        unit=unit,
                        dedupe_hash=dedupe_hash,
                        raw_payload=raw_payload,
                        created_at=datetime.utcnow()
                    ))
                        
                    if len(batch_buffer) >= BATCH_SIZE:
                        flush_batch()

                elem.clear()
                
        # Commit tail metrics safely maintaining buffer integrity
        flush_batch()
            
        import_run.status = 'success'
        import_run.end_time = datetime.utcnow()
        db.commit()
        print(f"[INFO] Ingestion successful! Added: {import_run.records_added}, Skipped: {import_run.records_skipped}, Total Seen: {import_run.records_seen}")

    except Exception as e:
        db.rollback()
        import_run.status = 'failed'
        import_run.error_message = str(e)
        import_run.end_time = datetime.utcnow()
        db.commit()
        print(f"[ERROR] System experienced failure structure during ingestion execution: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Apple Health XML")
    parser.add_argument("xml_filepath", type=str, help="Path to the Apple Health export.xml file")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        ingest_apple_health_xml(db, args.xml_filepath)
    finally:
        db.close()
