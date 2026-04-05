import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import LabResult
from app.services.labs.normalization.test_name_normalizer import resolve_canonical_test

session = SessionLocal()

rows = session.query(LabResult).filter(LabResult.canonical_test_code.is_(None)).all()

updated = 0
for row in rows:
    resolved = resolve_canonical_test(session, row.source_test_name, source_scope="ANY")
    if resolved:
        row.canonical_test_code = resolved["canonical_test_code"]
        row.canonical_test_name = resolved["canonical_test_name"]
        row.test_category = resolved["test_category"]
        row.panel_name = resolved["panel_name"]
        updated += 1

session.commit()
session.close()

print(f"Updated {updated} existing lab rows.")