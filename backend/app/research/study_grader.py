"""
Grade PubMed abstracts with OpenAI — grades must reflect abstract content only.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.ai.client import get_openai_client

logger = logging.getLogger(__name__)


_GRADE_SCHEMA_HINT = """Return a JSON object with exactly these keys:
{
  "relevance_grade": <integer 1-5>,
  "importance_grade": <integer 1-5>,
  "confidence": <string one of "A","B","C","D">,
  "summary": "<2-3 sentences describing what the study found, only from abstract>",
  "applicability_note": "<1 sentence how this applies or not to the patient>"
}
"""


def grade_studies(
    studies: list[dict],
    research_question: str,
    patient_context: str,
) -> list[dict]:
    """
    Add relevance_grade, importance_grade, confidence, summary, applicability_note to each study.
    """
    client = get_openai_client()
    out: list[dict] = []
    for study in studies:
        enriched = dict(study)
        try:
            payload = _grade_one(client, study, research_question, patient_context)
            enriched.update(payload)
        except Exception as e:
            logger.exception("Grading failed for PMID %s: %s", study.get("pmid"), e)
            enriched.update(_fallback_grade(study))
        out.append(enriched)
    return out


def _fallback_grade(study: dict) -> dict[str, Any]:
    return {
        "relevance_grade": 1,
        "importance_grade": 1,
        "confidence": "D",
        "summary": "Unable to grade automatically — abstract or metadata insufficient.",
        "applicability_note": "Could not assess applicability.",
    }


def _grade_one(client, study: dict, research_question: str, patient_context: str) -> dict[str, Any]:
    pt = ", ".join(study.get("publication_types") or [])
    authors = "; ".join((study.get("authors") or [])[:8])
    prompt = f"""You are assisting with clinical literature review. Grade ONE study at a time.

Research question for this review:
{research_question}

Patient context (for applicability only — do not invent patient facts):
{patient_context}

Study metadata (from PubMed only):
PMID: {study.get("pmid", "")}
Title: {study.get("title", "")}
Journal: {study.get("journal", "")}
Year: {study.get("year", "")}
Publication types: {pt}
Authors (truncated): {authors}

Abstract:
---
{study.get("abstract", "")}
---

Instructions:
- Grade relevance to the research question on 1-5 (1=off-topic, 5=directly answers).
- Grade importance on 1-5 using: study design (RCT/meta-analysis > review > cohort > case-control > case report), sample size if stated in abstract, journal reputation (infer cautiously from journal name only), recency.
- Overall confidence letter A/B/C/D (A=strong evidence to act on, D=weak/anecdotal).
- summary: 2-3 sentences on WHAT THE STUDY FOUND (not your opinion).
- applicability_note: 1 sentence on how this applies or does not apply to this patient given the context.

CRITICAL: Do not invent any details not present in the abstract. If the abstract is insufficient to grade a dimension, assign the lowest grade and note the limitation in summary. Do not reference studies other than the one provided. Do not fabricate PMIDs or citations.

{_GRADE_SCHEMA_HINT}
"""

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You output only valid JSON for literature grading. Never invent study results.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return _normalize_grade_payload(data)


def _normalize_grade_payload(data: dict) -> dict[str, Any]:
    rel = int(data.get("relevance_grade", 1))
    imp = int(data.get("importance_grade", 1))
    rel = max(1, min(5, rel))
    imp = max(1, min(5, imp))
    conf = str(data.get("confidence", "D")).strip().upper()
    if conf not in {"A", "B", "C", "D"}:
        conf = "D"
    summary = str(data.get("summary", "")).strip()
    app = str(data.get("applicability_note", "")).strip()
    # Strip accidental PMID citations not from input
    summary = re.sub(r"\[?\s*PMID\s*:?\s*\d+\s*\]?", "", summary).strip()
    return {
        "relevance_grade": rel,
        "importance_grade": imp,
        "confidence": conf,
        "summary": summary,
        "applicability_note": app,
    }
