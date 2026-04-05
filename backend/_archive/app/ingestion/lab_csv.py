from sqlalchemy.orm import Session
from app.db.models import SourceFile, ImportRun, LabTestMaster, LabResult

def ingest_lab_csv(db: Session, csv_filepath: str):
    \"\"\"
    Stub for parsing historical lab data from a CSV spreadsheet.
    Workflow:
    1. Read CSV using pandas.
    2. Map column headers (e.g., 'Cholesterol') to an existing or new LabTestMaster record.
    3. Unpivot (melt) the data so each metric reading is a single row.
    4. Insert into LabResult, creating a SourceFile reference.
    \"\"\"
    print(f"Ingesting Lab CSV from {csv_filepath} (Not Implemented)")
    pass
