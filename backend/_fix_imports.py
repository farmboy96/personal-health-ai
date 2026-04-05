import os

base = r'c:/Users/Owner/OneDrive/Family/Personal-Health-AI/backend'

replacements = {
    'app.db.repositories.lab_repository': 'app.db.repositories.lab_repository',
    'app.domain.labs.normalization': 'app.domain.labs.normalization',
    'app.ingestion.common.file_hashing': 'app.ingestion.common.file_hashing',
    'app.ingestion.labs.parser_utils': 'app.ingestion.labs.parser_utils',
    'app.ingestion.labs.excel_ingest': 'app.ingestion.labs.excel_ingest',
    'app.ingestion.labs.pdf_ingest': 'app.ingestion.labs.pdf_ingest',
    'app.ingestion.apple_health.xml_ingest': 'app.ingestion.apple_health.xml_ingest.xml_ingest'
}

for root, _, files in os.walk(base):
    if '\\.venv' in root or '/.venv' in root or '\\_archive' in root or '/_archive' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            modified = False
            for old, new in replacements.items():
                if old in content:
                    content = content.replace(old, new)
                    modified = True
                    
            if modified:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated imports in {filepath}")
