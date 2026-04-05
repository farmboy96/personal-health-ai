import os
import shutil

base = r'c:/Users/Owner/OneDrive/Family/Personal-Health-AI'

dirs = [
    'backend/app/db/repositories',
    'backend/app/domain/labs',
    'backend/app/domain/biometrics',
    'backend/app/domain/supplements',
    'backend/app/domain/events',
    'backend/app/domain/assessment',
    'backend/app/ingestion/common',
    'backend/app/ingestion/labs',
    'backend/app/ingestion/apple_health',
    'backend/app/ingestion/loaders',
    'backend/app/ai',
    'backend/app/application',
    'backend/app/presentation/cli',
    'backend/app/presentation/api',
    'backend/data/raw',
    'backend/data/processed',
    'backend/tests/unit',
    'backend/tests/integration',
    'backend/tests/fixtures',
    'backend/scripts/one_time',
    'backend/scripts/maintenance',
    'backend/docs'
]

for d in dirs:
    full_dir = os.path.join(base, d)
    os.makedirs(full_dir, exist_ok=True)
    if d.startswith('backend/app/'):
        init_file = os.path.join(full_dir, '__init__.py')
        if not os.path.exists(init_file):
            open(init_file, 'w').close()

moves = {
    'backend/app/services/labs/query_service.py': 'backend/app/db/repositories/lab_repository.py',
    'backend/app/services/labs/normalization/test_name_normalizer.py': 'backend/app/domain/labs/normalization.py',
    'backend/app/services/labs/lab_hashing.py': 'backend/app/ingestion/common/file_hashing.py',
    'backend/app/services/labs/value_parser.py': 'backend/app/ingestion/labs/parser_utils.py',
    'backend/app/services/labs/excel_lab_ingest.py': 'backend/app/ingestion/labs/excel_ingest.py',
    'backend/app/ingestion/lab_pdf.py': 'backend/app/ingestion/labs/pdf_ingest.py',
    'backend/app/ingestion/apple_health.py': 'backend/app/ingestion/apple_health/xml_ingest.py',
    'backend/init_db.py': 'backend/scripts/one_time/init_db.py'
}

for src, dst in moves.items():
    src_full = os.path.join(base, src)
    dst_full = os.path.join(base, dst)

    if not os.path.exists(src_full):
        print(f'SKIP missing source: {src}')
        continue

    if os.path.exists(dst_full):
        print(f'SKIP destination already exists: {dst}')
        continue

    os.makedirs(os.path.dirname(dst_full), exist_ok=True)
    shutil.move(src_full, dst_full)
    print(f'MOVED {src} -> {dst}')
