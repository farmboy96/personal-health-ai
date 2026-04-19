import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import LabResult
from app.domain.labs.normalization import resolve_canonical_test
from app.ingestion.labs.parser_utils import extract_numeric_value

def main():
    session = SessionLocal()
    try:
        rows = session.query(LabResult).filter(LabResult.canonical_test_code.is_(None)).all()
        print(f"Found {len(rows)} rows with canonical_test_code=NULL")
        
        updated = 0
        still_unmatched = {}
        numeric_filled = 0
        
        for row in rows:
            resolved = resolve_canonical_test(session, row.source_test_name, source_scope="ANY")
            if resolved:
                row.canonical_test_code = resolved["canonical_test_code"]
                row.canonical_test_name = resolved["canonical_test_name"]
                row.test_category = resolved["test_category"]
                row.panel_name = resolved["panel_name"]
                updated += 1
            else:
                still_unmatched[row.source_test_name] = still_unmatched.get(row.source_test_name, 0) + 1
            
            # Also backfill result_value_numeric from result_value_text if missing
            # (PDF ingestion doesn't set numeric; daily_assessment filters on numeric NOT NULL)
            if row.result_value_numeric is None and row.result_value_text:
                num = extract_numeric_value(row.result_value_text)
                if num is not None:
                    row.result_value_numeric = num
                    numeric_filled += 1
        
        session.commit()
        print(f"Updated {updated} rows with canonical codes")
        print(f"Filled {numeric_filled} result_value_numeric values from text")
        print(f"Still unmatched: {sum(still_unmatched.values())} rows across {len(still_unmatched)} distinct names")
        if still_unmatched:
            print("\nTop 20 remaining unmatched names:")
            for name, count in sorted(still_unmatched.items(), key=lambda x: -x[1])[:20]:
                print(f"  {count:3d}  {name}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
