"""
PubMed E-utilities client — all study fields are parsed only from retrieved XML.

https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

from __future__ import annotations

import logging
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
REQUEST_PAUSE_SEC = 0.35


def _sleep_between_calls() -> None:
    time.sleep(REQUEST_PAUSE_SEC)


def _local_tag(elem: ET.Element) -> str:
    return elem.tag.split("}", 1)[-1] if elem.tag else ""


def _gather_abstract_texts(node: ET.Element | None) -> str:
    if node is None:
        return ""
    texts: list[str] = []
    for child in node:
        tname = _local_tag(child)
        if tname == "AbstractText":
            label = child.attrib.get("Label", "")
            txt = (child.text or "").strip()
            inner = "".join(child.itertext()).strip()
            chunk = inner or txt
            if label:
                texts.append(f"{label}: {chunk}")
            elif chunk:
                texts.append(chunk)
        elif child.text:
            texts.append(child.text.strip())
    if texts:
        return "\n".join(texts).strip()
    # fallback whole abstract node text
    parts = []
    if node.text:
        parts.append(node.text.strip())
    for child in node:
        parts.extend(child.itertext())
    return "\n".join(parts).strip()


def _collect_authors(auth_list_node: ET.Element | None) -> list[str]:
    out: list[str] = []
    if auth_list_node is None:
        return out
    for au in auth_list_node:
        if _local_tag(au) != "Author":
            continue
        ln = fm = initials = ""
        # Standard Author
        for child in au:
            tag = _local_tag(child)
            if tag == "LastName":
                ln = (child.text or "").strip()
            elif tag == "ForeName":
                fm = (child.text or "").strip()
            elif tag == "Initials":
                initials = (child.text or "").strip()
            elif tag == "CollectiveName":
                ln = (child.text or "").strip()
        if ln:
            rest = fm or initials
            out.append(f"{ln} {rest}".strip())
    return out[:25]


def _extract_year(pub_date_elem: ET.Element | None) -> str:
    if pub_date_elem is None:
        return ""
    year_node = None
    for child in pub_date_elem:
        if _local_tag(child) == "Year":
            year_node = child
            break
        if _local_tag(child) == "MedlineDate":
            txt = (child.text or "").strip().split()[0][:4]
            return txt if txt.isdigit() else ""
    return (year_node.text or "").strip() if year_node is not None else ""


def _journal_title(journal_elem: ET.Element | None) -> str:
    if journal_elem is None:
        return ""
    for child in journal_elem:
        if _local_tag(child) == "Title":
            return (child.text or "").strip()
    return ""


def _publication_types(article: ET.Element) -> list[str]:
    out: list[str] = []
    for child in article.iter():
        if _local_tag(child) == "PublicationType":
            txt = (child.text or "").strip()
            if txt:
                out.append(txt)
    return sorted(set(out))


def _first_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for ch in parent:
        if _local_tag(ch) == name:
            return ch
    return None


def _parse_pubmed_article(pubmed_article: ET.Element) -> dict[str, Any] | None:
    """Extract one article dict from a PubmedArticle XML element."""
    citation = _first_child(pubmed_article, "MedlineCitation")
    article = _first_child(citation, "Article") if citation is not None else None
    if citation is None or article is None:
        return None

    pmid_el = _first_child(citation, "PMID")
    pmid = (pmid_el.text or "").strip() if pmid_el is not None else ""

    title_el = _first_child(article, "ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""

    journal_el = _first_child(article, "Journal")
    journal = _journal_title(journal_el)

    jour_issue = _first_child(journal_el, "JournalIssue") if journal_el is not None else None
    pub_date = _first_child(jour_issue, "PubDate") if jour_issue is not None else None
    year = _extract_year(pub_date)

    auth_list = _first_child(article, "AuthorList")
    authors = _collect_authors(auth_list)

    abstract_el = _first_child(article, "Abstract")
    abstract = _gather_abstract_texts(abstract_el)

    pt = _publication_types(article)

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "abstract": abstract,
        "publication_types": pt,
    }


def search_pubmed(
    query: str,
    max_results: int = 15,
    recent_only: bool = True,
) -> list[str]:
    """
    Return PMIDs from esearch.fcgi — results only from PubMed servers.
    """
    base_term = query.strip()
    if recent_only:
        # Last 10 calendar years inclusive (publication date)
        from datetime import datetime, timedelta

        end_d = datetime.utcnow().date()
        start_d = end_d - timedelta(days=365 * 10)
        dp = (
            f'("{start_d.year}/{start_d.month:02d}/{start_d.day:02d}"[PDAT] : '
            f'"{end_d.year}/{end_d.month:02d}/{end_d.day:02d}"[PDAT])'
        )
        term = f"({base_term}) AND {dp}"
    else:
        term = base_term

    params = {
        "db": "pubmed",
        "term": term,
        "retmax": max(max_results, 1),
        "sort": "relevance",
        "retmode": "xml",
    }
    url = BASE + "esearch.fcgi?" + urllib.parse.urlencode(params)
    try:
        _sleep_between_calls()
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        pmids: list[str] = []
        for id_elem in root.iter():
            if _local_tag(id_elem) == "Id":
                txt = (id_elem.text or "").strip()
                if txt.isdigit():
                    pmids.append(txt)
            if len(pmids) >= max_results:
                break
        # esearch wraps multiple Id tags
        pmids = pmids[:max_results]
        return pmids
    except Exception as e:
        logger.exception("PubMed esearch failed: %s", e)
        return []


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    """efetch abstracts — parsed fields only from XML."""
    if not pmids:
        return []
    out: list[dict[str, Any]] = []
    # Chunk to reasonable batch size for URL length / stability
    chunk_size = 120
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        ids = ",".join(chunk)
        params = {
            "db": "pubmed",
            "id": ids,
            "rettype": "abstract",
            "retmode": "xml",
        }
        url = BASE + "efetch.fcgi?" + urllib.parse.urlencode(params)
        try:
            _sleep_between_calls()
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            logger.exception("PubMed efetch failed for chunk starting %s: %s", chunk[0], e)
            continue

        for pubmed_article in root.iter():
            if _local_tag(pubmed_article) != "PubmedArticle":
                continue
            parsed = _parse_pubmed_article(pubmed_article)
            if parsed and parsed.get("pmid"):
                out.append(parsed)

    # Dedupe preserving order
    seen: set[str] = set()
    uniq: list[dict] = []
    for row in out:
        pid = str(row["pmid"])
        if pid in seen:
            continue
        seen.add(pid)
        uniq.append(row)
    return uniq
