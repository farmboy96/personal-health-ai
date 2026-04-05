import os
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import SourceFile, ImportRun
from app.ingestion.common.file_hashing import calculate_file_hash
from app.ingestion.labs.excel_ingest import process_excel_file
from app.ingestion.labs.pdf_ingest import process_pdf_file

def execute_ingest_lab_file(filepath: str):
    """
    Official application wrapper supporting both Excel and PDF legacy loops natively.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"[ERROR] Target lab file not located exactly at: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        print(f"[INFO] Routing to PDF extractor...")
        process_pdf_file(filepath)
        return

    # Fallback to standard excel routine
    db = SessionLocal()
    try:
        start_time = datetime.utcnow()
        file_hash = calculate_file_hash(filepath)
        filename = os.path.basename(filepath)
        
        source_file = db.query(SourceFile).filter(SourceFile.file_hash == file_hash).first()
        if not source_file:
            source_file = SourceFile(filename=filename, file_hash=file_hash, file_type='xlsx', stored_path=os.path.abspath(filepath), source_category='lab_excel', created_at=start_time)
            db.add(source_file)
            db.commit()
            db.refresh(source_file)
            print(f"[INFO] Hooking New Source Tracker UUID (id: {source_file.id})")
        else:
            print(f"[INFO] Overriding and targeting preexisting Target Tracker UUID (id: {source_file.id})")

        import_run = ImportRun(source_file_id=source_file.id, import_type='lab_excel', start_time=start_time, status='running')
        db.add(import_run)
        db.commit()
        db.refresh(import_run)
        
        print(f"[INFO] Booting Lab Matrix Excel extraction execution thread...")
        process_excel_file(db, filepath, source_file, import_run)
    finally:
        db.close()
