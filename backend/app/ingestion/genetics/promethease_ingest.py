"""
Ingest Promethease HTML exports: zlib-compressed base64 JSON blocks in decompressString('...').
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.database import SessionLocal
from app.db.models import GeneticVariant, ImportRun, SourceFile

DECOMPRESS_RE = re.compile(r"decompressString\s*\(\s*'([^']*)'\s*\)")


def _strip_html(s: str) -> str:
    if not s:
        return ""
    t = re.sub(r"<[^>]+>", " ", str(s))
    return re.sub(r"\s+", " ", t).strip()


def _genes_str(genes: Any) -> str:
    if genes is None:
        return ""
    if isinstance(genes, list):
        s = ",".join(str(x) for x in genes)
    else:
        s = str(genes)
    return s[:256]


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_html_path(input_path: str) -> Tuple[str, Optional[str]]:
    """Returns (path_to_html, temp_dir_to_cleanup_or_None)."""
    p = Path(input_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Not found: {p}")
    if p.suffix.lower() == ".zip":
        tmp = tempfile.mkdtemp(prefix="promethease_extract_")
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(tmp)
        html_candidates = list(Path(tmp).rglob("promethease.html"))
        if not html_candidates:
            raise FileNotFoundError("promethease.html not found inside zip")
        return str(html_candidates[0]), tmp
    if p.suffix.lower() == ".html":
        return str(p), None
    raise ValueError(f"Expected .zip or .html, got: {p}")


def ingest_promethease(input_path: str) -> None:
    html_path: Optional[str] = None
    cleanup_dir: Optional[str] = None
    db = SessionLocal()
    import_run: Optional[ImportRun] = None

    try:
        html_path, cleanup_dir = _resolve_html_path(input_path)
        file_hash = _file_sha256(html_path)
        filename = os.path.basename(html_path)

        start_time = datetime.utcnow()

        existing_sf = db.query(SourceFile).filter(SourceFile.file_hash == file_hash).first()
        if existing_sf:
            source_file = existing_sf
            print(f"[INFO] Reusing SourceFile id={source_file.id} (same hash)")
        else:
            source_file = SourceFile(
                filename=filename,
                file_hash=file_hash,
                file_type="html",
                stored_path=os.path.abspath(html_path),
                source_category="promethease",
                created_at=start_time,
            )
            db.add(source_file)
            db.commit()
            db.refresh(source_file)
            print(f"[INFO] Registered SourceFile id={source_file.id}")

        import_run = ImportRun(
            source_file_id=source_file.id,
            import_type="promethease_html",
            start_time=start_time,
            status="running",
            records_seen=0,
            records_added=0,
            records_skipped=0,
        )
        db.add(import_run)
        db.commit()
        db.refresh(import_run)

        with open(html_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        blocks = DECOMPRESS_RE.findall(html)
        print(f"[INFO] Found {len(blocks)} decompressString blocks")

        records_seen = 0
        skipped_filter = 0
        skipped_dup = 0
        inserted_total = 0
        pending_commits = 0

        def insert_row(row: Dict[str, Any]) -> None:
            nonlocal inserted_total, skipped_dup, pending_commits
            stmt = sqlite_insert(GeneticVariant).values(**row).on_conflict_do_nothing(
                index_elements=["rsid", "genotype"]
            )
            res = db.execute(stmt)
            if res.rowcount and res.rowcount > 0:
                inserted_total += res.rowcount
            else:
                skipped_dup += 1
            pending_commits += 1
            if pending_commits >= 500:
                db.commit()
                pending_commits = 0

        for b64 in blocks:
            try:
                raw = base64.b64decode(b64)
                dec = zlib.decompress(raw)
                data = json.loads(dec.decode("utf-8"))
            except Exception:
                skipped_filter += 1
                continue

            if not isinstance(data, list):
                continue

            for snp in data:
                records_seen += 1

                mag_raw = snp.get("magnitude")
                try:
                    mag = float(mag_raw) if mag_raw is not None else None
                except (TypeError, ValueError):
                    mag = None

                if mag is None or mag < 1.5:
                    skipped_filter += 1
                    continue

                genosummary = snp.get("genosummary") or ""
                rstext_raw = snp.get("rstext") or ""
                mischeck = (genosummary + rstext_raw).lower()
                if "miscall" in mischeck:
                    skipped_filter += 1
                    continue

                rsid = str(snp.get("rsnum") or "").strip()
                genotype = str(snp.get("geno") or "").strip()
                if not rsid or not genotype:
                    skipped_filter += 1
                    continue

                genotype = genotype[:16]
                rsid = rsid[:32]

                repute_val = snp.get("repute")
                repute_str = str(repute_val)[:16] if repute_val is not None else None

                insert_row(
                    {
                        "rsid": rsid,
                        "genotype": genotype,
                        "magnitude": mag,
                        "repute": repute_str,
                        "genes": _genes_str(snp.get("genes")),
                        "summary": _strip_html(genosummary)[:2000],
                        "detail": _strip_html(rstext_raw),
                        "source_file_id": source_file.id,
                    }
                )

        if pending_commits:
            db.commit()

        import_run.records_seen = records_seen
        import_run.records_added = inserted_total
        import_run.records_skipped = skipped_filter + skipped_dup
        import_run.status = "success"
        import_run.end_time = datetime.utcnow()
        db.commit()

        print(
            f"[DONE] blocks={len(blocks)} seen={records_seen} inserted={inserted_total} "
            f"skipped_filter={skipped_filter} skipped_conflict_or_dup={skipped_dup}"
        )

    except Exception as e:
        db.rollback()
        if import_run:
            import_run.status = "failed"
            import_run.error_message = str(e)
            import_run.end_time = datetime.utcnow()
            db.commit()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()
        if cleanup_dir and os.path.isdir(cleanup_dir):
            import shutil

            shutil.rmtree(cleanup_dir, ignore_errors=True)
