import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.genetics.promethease_ingest import ingest_promethease


def main():
    if len(sys.argv) < 2:
        print("Usage: ingest_promethease.py <path_to_zip_or_html>")
        sys.exit(1)
    ingest_promethease(sys.argv[1])


if __name__ == "__main__":
    main()
