import os
import sys
import argparse
from datetime import datetime
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import SourceFile, ImportRun
from app.ingestion.labs.excel_ingest import process_excel_file

def calculate_file_hash(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Ingest Exact V1 Excel Lab Value Matrix Files")
    parser.add_argument("filepath", type=str, help="Absolute or relative path to your specific .xlsx file")
    args = parser.parse_args()
    
    filepath = args.filepath
    if not os.path.exists(filepath):
        print(f"[ERROR] Excel Target Matrix not located exactly at: {filepath}")
        return
        
    db = SessionLocal()
    try:
        start_time = datetime.utcnow()
        file_hash = calculate_file_hash(filepath)
        filename = os.path.basename(filepath)
        
        source_file = db.query(SourceFile).filter(SourceFile.file_hash == file_hash).first()
        if not source_file:
            source_file = SourceFile(
                filename=filename,
                file_hash=file_hash,
                file_type='xlsx',
                stored_path=os.path.abspath(filepath),
                source_category='lab_excel',
                created_at=start_time
            )
            db.add(source_file)
            db.commit()
            db.refresh(source_file)
            print(f"[INFO] Hooking New Source Tracker UUID (id: {source_file.id})")
        else:
            print(f"[INFO] Overriding and targeting preexisting Target Tracker UUID (id: {source_file.id})")

        import_run = ImportRun(
            source_file_id=source_file.id,
            import_type='lab_excel',
            start_time=start_time,
            status='running',
            records_seen=0,
            records_added=0,
            records_skipped=0
        )
        db.add(import_run)
        db.commit()
        db.refresh(import_run)
        
        print(f"[INFO] Booting Lab Matrix Excel extraction execution thread...")
        process_excel_file(db, filepath, source_file, import_run)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
