import os
import sys
import argparse
from sqlalchemy import func, desc

# Allow module to be executed cleanly from backend root via `python -m app.analysis.query_health`
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal
from app.db.models import RawMeasurement

def run_counts(db: SessionLocal):
    results = db.query(
        RawMeasurement.metric_type, 
        func.count(RawMeasurement.id)
    ).group_by(RawMeasurement.metric_type).all()
    
    print("\n========= Rows by Metric Type =========")
    if not results:
        print("No ingestion records found in database yet.")
    for metric, count in sorted(results, key=lambda x: x[1], reverse=True):
        print(f"{metric}: {count}")
    print("=======================================\n")

def run_metric_analysis(db: SessionLocal, metric_type: str):
    # 1. Date Ranges
    date_range = db.query(
        func.min(RawMeasurement.start_date),
        func.max(RawMeasurement.start_date)
    ).filter(RawMeasurement.metric_type == metric_type).first()
    
    if not date_range or not date_range[0]:
        print(f"\n[!] No active data structure located for metric: {metric_type}\n")
        return
        
    print(f"\n========= Deep Dive Analysis: {metric_type} =========")
    print(f"Date Tracking Range: {date_range[0].strftime('%Y-%m-%d %H:%M:%S')} to {date_range[1].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 2. Distinct Sources
    sources = db.query(RawMeasurement.source_name).filter(RawMeasurement.metric_type == metric_type).distinct().all()
    source_names = [s[0] for s in sources]
    print(f"Originating Sources: {', '.join(source_names)}")
    
    # 3. Recent 20 rows inspection layer
    print("\n--- Latest 20 Inserted Records ---")
    records = db.query(RawMeasurement).filter(RawMeasurement.metric_type == metric_type).order_by(desc(RawMeasurement.start_date)).limit(20).all()
    
    print(f"{'Date Observed':<22} | {'Value & Unit':<20} | {'Source System'}")
    print("-" * 70)
    
    for r in records:
        val_display = f"{r.value} {r.unit if r.unit else ''}"
        
        # Override display formatting visually if this happens to be a recognized text Category parsing
        if 'SleepAnalysis' in metric_type and r.value == 0.0:
            val_display = f"*(Enum preserved inside payload)*"
            
        print(f"{r.start_date.strftime('%Y-%m-%d %H:%M:%S'):<22} | {val_display:<20} | {r.source_name}")
    print("=====================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Personal Health Database Metrics")
    subparsers = parser.add_subparsers(dest="command", help="Analysis Query commands", required=True)
    
    # CLI setup: 'counts'
    subparsers.add_parser("counts", help="Show total localized row counts indexed by metric type")
    
    # CLI setup: 'metric'
    metric_parser = subparsers.add_parser("metric", help="Execute deep dive slice on a specific health metric")
    metric_parser.add_argument("metric_name", type=str, help="e.g. HKQuantityTypeIdentifierBodyMass")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.command == "counts":
            run_counts(db)
        elif args.command == "metric":
            run_metric_analysis(db, args.metric_name)
    finally:
        db.close()
