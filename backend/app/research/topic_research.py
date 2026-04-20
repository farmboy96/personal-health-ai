"""
Research pipeline: PubMed retrieval → grading → cited narrative synthesis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.client import get_openai_client
from app.research.pubmed_client import fetch_abstracts, search_pubmed
from app.research.study_grader import grade_studies

logger = logging.getLogger(__name__)


def _composite_score(s: dict) -> float:
    r = float(s.get("relevance_grade") or 0)
    i = float(s.get("importance_grade") or 0)
    return r * 2.0 + i


def research_topic(topic_config: dict, patient_context: str) -> dict[str, Any]:
    """
    topic_config: title, research_question, pubmed_queries, max_per_query
    Returns title, research_question, studies (graded, top kept), narrative.
    """
    title = topic_config["title"]
    rq = topic_config["research_question"]
    queries = topic_config["pubmed_queries"]
    max_per = int(topic_config.get("max_per_query", 10))

    seen_pmids: set[str] = set()
    ordered_pmids: list[str] = []

    for q in queries:
        ids = search_pubmed(q, max_results=max_per, recent_only=True)
        for pid in ids:
            if pid not in seen_pmids:
                seen_pmids.add(pid)
                ordered_pmids.append(pid)

    studies_raw = fetch_abstracts(ordered_pmids)
    # Preserve search order for duplicates removed in fetch
    by_pmid = {str(s["pmid"]): s for s in studies_raw}
    merged = [by_pmid[p] for p in ordered_pmids if p in by_pmid]

    graded = grade_studies(merged, rq, patient_context)

    filtered = [s for s in graded if int(s.get("relevance_grade") or 0) >= 3]
    filtered.sort(key=_composite_score, reverse=True)
    kept = filtered[:5]

    narrative = _synthesize_narrative(
        title=title,
        research_question=rq,
        patient_context=patient_context,
        studies=kept,
    )

    return {
        "title": title,
        "research_question": rq,
        "studies": kept,
        "narrative": narrative,
        "abstracts_fetched": len(merged),
    }


def _synthesize_narrative(
    *,
    title: str,
    research_question: str,
    patient_context: str,
    studies: list[dict],
) -> str:
    if not studies:
        return (
            "No studies met the relevance threshold after PubMed retrieval and grading. "
            "Consider broadening search terms or reviewing database connectivity."
        )

    client = get_openai_client()
    blocks = []
    for s in studies:
        blocks.append(
            json.dumps(
                {
                    "pmid": s.get("pmid"),
                    "title": s.get("title"),
                    "journal": s.get("journal"),
                    "year": s.get("year"),
                    "publication_types": s.get("publication_types"),
                    "abstract": s.get("abstract"),
                    "grading": {
                        "relevance_grade": s.get("relevance_grade"),
                        "importance_grade": s.get("importance_grade"),
                        "confidence": s.get("confidence"),
                        "summary": s.get("summary"),
                        "applicability_note": s.get("applicability_note"),
                    },
                },
                ensure_ascii=False,
            )
        )
    studies_blob = "\n---\n".join(blocks)
    allowed_pmids = ", ".join(str(s.get("pmid")) for s in studies)

    prompt = f"""You are writing a narrative literature synthesis for a treating physician.

Topic title: {title}
Research question: {research_question}

Patient context (facts must not be invented beyond this text):
{patient_context}

Studies (JSON lines — these are the ONLY studies you may cite):
{studies_blob}

Write:
1) Two to three paragraphs synthesizing what the evidence in these studies suggests regarding the research question.
2) A short paragraph: where consensus appears to exist vs where it does not, based only on these studies.
3) A "Recommendation for discussion" paragraph: what the patient should discuss with their doctor given this evidence.

Rules — CRITICAL:
- You may only cite studies provided above. Every factual claim about study findings must be traceable to one of these studies.
- Cite inline using exactly this form when referencing a study: [PMID: <digits>] and ONLY use PMIDs from this list: {allowed_pmids}
- Do not cite any PMID not provided. Do not invent PMIDs.
- Do not mention papers, trials, or results not in the JSON above.

Use professional clinical tone."""

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You write accurate, cited clinical summaries without hallucinating citations.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()
