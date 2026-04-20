from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc

from app.ai.client import get_openai_client
from app.application._docx_helpers import (
    add_text_with_bullets,
    apply_table_layout,
    configure_document_typography,
    ensure_bullet_styles,
    set_cell_text,
    shade_cell,
    truncate,
)
from app.db.database import SessionLocal
from app.db.models import ClinicalReport, GeneticRecommendation, GeneticVariant

logger = logging.getLogger(__name__)

HEDGING_TERMS = ["consider", "may want to", "it might be beneficial"]


def _default_output_dir() -> Path:
    d = Path(__file__).resolve().parents[2] / "data" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_pmids(text: str) -> list[str]:
    return re.findall(r"(?:\[?\s*PMID:\s*)(\d+)\]?", text or "")


def _dehedge_text(text: str) -> str:
    t = text or ""
    t = re.sub(r"\b[Cc]onsider\b", "Do", t)
    t = re.sub(r"\b[Mm]ay want to\b", "should", t)
    t = re.sub(r"\bit might be beneficial\b", "it is useful", t, flags=re.I)
    return t


def _normalize_genotype(gt: str) -> tuple[str, str]:
    cleaned = (gt or "").replace("(", "").replace(")", "").replace(" ", "")
    parts = cleaned.split(";")
    if len(parts) != 2:
        return "", ""
    return parts[0].upper(), parts[1].upper()


def _match_pattern(genotype: str, pattern: str) -> bool:
    a1, a2 = _normalize_genotype(genotype)
    if not a1:
        return False
    p = (pattern or "any").strip().lower()
    if p == "any":
        return True
    if p == "homozygous_minor":
        return a1 == a2
    if p.startswith("*/"):
        target = p.split("/", 1)[1].upper()
        return a1 == target or a2 == target
    if "/" in p:
        x, y = p.split("/", 1)
        x = x.upper()
        y = y.upper()
        return sorted([a1, a2]) == sorted([x, y])
    return False


def _load_report_row(db, clinical_report_id: int | None) -> ClinicalReport:
    if clinical_report_id is not None:
        row = db.query(ClinicalReport).filter(ClinicalReport.id == clinical_report_id).first()
    else:
        row = db.query(ClinicalReport).order_by(desc(ClinicalReport.created_at)).first()
    if not row:
        raise ValueError("No ClinicalReport found")
    return row


def _match_recommendations(db, variants: list[GeneticVariant]) -> list[dict[str, Any]]:
    var_by_rsid: dict[str, list[GeneticVariant]] = {}
    for v in variants:
        var_by_rsid.setdefault(v.rsid, []).append(v)

    recs = db.query(GeneticRecommendation).all()
    matched: list[dict[str, Any]] = []
    for r in recs:
        vrows = var_by_rsid.get(r.rsid, [])
        for v in vrows:
            if _match_pattern(v.genotype or "", r.genotype_pattern or "any"):
                d = {
                    "rsid": r.rsid,
                    "gene": r.gene,
                    "category": r.category,
                    "recommendation_text": r.recommendation_text,
                    "rationale": r.rationale,
                    "action_level": r.action_level,
                    "priority": r.priority,
                    "source_notes": r.source_notes,
                    "genotype": v.genotype,
                }
                matched.append(d)
                break

    # de-dupe exact text
    uniq = {}
    for m in matched:
        k = (m["rsid"], m["category"], m["recommendation_text"])
        if k not in uniq:
            uniq[k] = m
    out = list(uniq.values())
    out.sort(key=lambda x: (x["priority"], x["category"], x["recommendation_text"]))
    return out


def _extract_normalized_numbers(text: str) -> set[str]:
    raw = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", text or "")
    out: set[str] = set()
    for tok in raw:
        out.add(tok.replace(",", ""))
    return out


def _numbers_from_context(snapshot: dict[str, Any]) -> set[str]:
    blob = json.dumps(snapshot, default=str)
    return _extract_normalized_numbers(blob)


def _ai_section1(patient_context_snapshot: dict[str, Any]) -> str:
    ctx = json.dumps(patient_context_snapshot, indent=2, default=str)
    prompt = f"""Write Section 1: \"How you're doing right now\" for Robert Grogan.

Use only this data:
{ctx}

Output 3-5 short paragraphs. Requirements:
- Name specific numbers and trajectories that are positive or improving.
- Tie each number to an observed behavior where plausible.
- Do not invent numbers.
- Tone: direct, informed, zero fluff.
"""
    client = get_openai_client()
    rsp = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You write precise patient-facing health analysis from provided numbers only."},
            {"role": "user", "content": prompt},
        ],
    )
    return (rsp.choices[0].message.content or "").strip()


def _ai_top_5_actions(
    *,
    patient_context_snapshot: dict[str, Any],
    matched_recommendations: list[dict[str, Any]],
    topic_narratives: dict[str, str],
) -> str:
    context_json = json.dumps(patient_context_snapshot, indent=2, default=str)
    recs_json = json.dumps(
        [
            {
                "category": r.get("category"),
                "action_level": r.get("action_level"),
                "priority": r.get("priority"),
                "recommendation_text": r.get("recommendation_text"),
                "rationale": r.get("rationale"),
                "rsid": r.get("rsid"),
                "gene": r.get("gene"),
            }
            for r in matched_recommendations
        ],
        ensure_ascii=False,
    )
    topics_json = json.dumps(topic_narratives, ensure_ascii=False)

    prompt = """
From the patient context, matched genetic recommendations, and topic narratives below, select the 5 highest-leverage actions for the patient to focus on over the next 30 days. Criteria:

1. Rank by expected impact on the patient's most concerning biomarker trends (rising LDL, elevated homocysteine, elevated estradiol)
2. Favor actions the patient can execute alone (diet swaps, routine changes) over discuss-with-doctor items
3. Each action must be phrased in plain English at an 8th grade reading level
4. Each action is 1 sentence describing the change, followed by 1-2 sentences explaining why it matters in terms the patient can feel (not medical jargon)
5. Order by priority, highest leverage first
6. No PMID citations in this section — keep it clean; citations live in the detail sections

Write in direct voice: "Switch X to Y" not "consider switching X to Y." The reader is motivated and capable; give him the action plainly.

Output exactly 5 top-level bullets, each beginning with "- ".
"""
    full_prompt = (
        f"{prompt}\n\n"
        f"Patient context snapshot JSON:\n{context_json}\n\n"
        f"Matched recommendations JSON:\n{recs_json}\n\n"
        f"Topic narratives JSON:\n{topics_json}\n"
    )
    client = get_openai_client()
    rsp = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You create direct patient action plans. No hedging. No citations in this section.",
            },
            {"role": "user", "content": full_prompt},
        ],
    )
    return _dehedge_text((rsp.choices[0].message.content or "").strip())


def _prioritize_august_handoff(questions_grouped: dict[str, list[str]], max_items: int = 5) -> list[str]:
    # Flatten then rank by key clinical importance themes
    all_items: list[str] = []
    for _, items in questions_grouped.items():
        all_items.extend(items)

    def score(item: str) -> tuple[int, int]:
        t = item.lower()
        s = 0
        if "psa" in t or "mri" in t or "prostate" in t:
            s += 6
        if "ldl" in t or "apob" in t or "lipid" in t:
            s += 5
        if "homocysteine" in t or "methyl" in t or "folate" in t or "b12" in t:
            s += 5
        if "ferritin" in t or "iron" in t:
            s += 3
        if "thyroid" in t or "tsh" in t or "tpo" in t:
            s += 2
        if "vitamin d" in t:
            s += 1
        # shorter, actionable phrasing preferred
        return (-s, len(item))

    dedup = sorted(set(all_items), key=score)
    return dedup[:max_items]


def _topic_translation_ai(
    *,
    topic_title: str,
    physician_narrative: str,
    patient_context: str,
    allowed_studies: list[dict[str, Any]],
) -> str:
    allowed_pmids = [str(s.get("pmid")) for s in allowed_studies if s.get("pmid")]
    studies_blob = json.dumps(
        [
            {
                "pmid": s.get("pmid"),
                "title": s.get("title"),
                "journal": s.get("journal"),
                "year": s.get("year"),
                "abstract": s.get("abstract"),
                "summary": s.get("summary"),
                "applicability_note": s.get("applicability_note"),
            }
            for s in allowed_studies
        ],
        ensure_ascii=False,
    )
    prompt = f"""
You are translating a physician-facing clinical literature synthesis into a patient-facing action guide for a specific reader. The reader is a 54-year-old man, a 3-stripe brown belt in Brazilian jiu-jitsu, who does weighted-vest rucking on weekends, practices 16:8 intermittent fasting plus occasional multi-day fasts, and works from home at a computer. He reads Peter Attia, Andrew Huberman, and Rhonda Patrick. He can handle real information.

Your voice: direct, evidence-citing, action-oriented. No hedging for its own sake. Do not use phrases like "consider," "may want to," or "it might be beneficial." Prefer imperatives: "swap X for Y," "add X," "stop doing Y." When evidence is strong, say so plainly. When it's weak, say so plainly — do not pretend certainty you don't have.

You may only cite PMIDs provided in the context. Do not invent studies, authors, effect sizes, or dates. If you reference a number from a study, it must appear verbatim in the provided abstracts.

Structure each topic as four sections with these exact headings:

What's working — specific things in the patient's data or behavior that are moving numbers in the right direction. Be specific — name the number and name the behavior.

What to adjust — diet, sleep, training, behavior changes the patient can make alone. Name specific swaps. Cite PMIDs when the adjustment is evidence-backed.

What to discuss with Dr. Lamkin — supplement additions or dose changes, new labs to order, medication considerations. These are the handoff items.

What to watch for — specific numbers or symptoms that should trigger contacting Dr. Lamkin earlier than the scheduled visit.

Length: each section 2-5 bullet points. Do not pad.

Topic: {topic_title}
Patient context:
{patient_context}

Physician narrative:
{physician_narrative}

Allowed studies JSON:
{studies_blob}

Allowed PMIDs only: {", ".join(allowed_pmids)}
"""
    client = get_openai_client()
    rsp = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You produce direct patient action guides with strict PMID discipline and no invented claims.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    text = (rsp.choices[0].message.content or "").strip()
    # hard guard against hallucinated PMIDs
    bad = [p for p in _extract_pmids(text) if p not in set(allowed_pmids)]
    if bad:
        for p in bad:
            text = text.replace(f"[PMID: {p}]", "[PMID: removed]")
            text = text.replace(f"PMID: {p}", "PMID: removed")
    return _dehedge_text(text)


def _extract_discuss_items_from_topic(text: str) -> list[str]:
    out: list[str] = []
    lines = (text or "").splitlines()
    in_section = False
    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        if t.lower().startswith("what to discuss with dr. lamkin"):
            in_section = True
            continue
        if in_section and t.lower().startswith("what to watch for"):
            break
        if in_section and t.startswith("- "):
            out.append(t[2:].strip())
    return out


def _category_display(cat: str) -> str:
    m = {
        "diet": "Diet",
        "exercise": "Exercise",
        "supplement": "Supplements",
        "sleep": "Sleep & Lifestyle",
        "behavior": "Sleep & Lifestyle",
        "monitoring": "Monitoring",
    }
    return m.get(cat, cat.title())


def generate_patient_report(clinical_report_id: int | None = None, output_dir: str | None = None) -> dict:
    db = SessionLocal()
    try:
        report_row = _load_report_row(db, clinical_report_id)
        snapshot = json.loads(report_row.patient_context_snapshot or "{}")
        narratives = json.loads(report_row.narrative_sections or "{}")
        retrieved = json.loads(report_row.retrieved_studies or "[]")
        variants = db.query(GeneticVariant).all()
        matched = _match_recommendations(db, variants)
    finally:
        db.close()

    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"patient_report_{ts}.docx"

    patient_context = json.dumps(snapshot, default=str, indent=2)
    section1 = _dehedge_text(_ai_section1(snapshot))

    # translate each topic
    topic_translations: dict[str, str] = {}
    cited_pmids: set[str] = set()
    by_topic_studies: dict[str, list[dict[str, Any]]] = {}
    for s in retrieved:
        by_topic_studies.setdefault(str(s.get("topic_key") or ""), []).append(s)

    for topic_key, physician_text in narratives.items():
        topic_title = topic_key
        if topic_key in {
            "mthfr_homocysteine_trt",
            "ldl_trajectory_trt_apoa2",
            "prostate_surveillance_trt_high_prs",
        }:
            from app.research.topic_catalog import TOPICS

            topic_title = TOPICS[topic_key]["title"]
        allowed = by_topic_studies.get(topic_key, [])
        translated = _topic_translation_ai(
            topic_title=topic_title,
            physician_narrative=physician_text,
            patient_context=patient_context,
            allowed_studies=allowed,
        )
        topic_translations[topic_key] = translated
        cited_pmids.update(_extract_pmids(translated))

    # questions to bring
    discuss_items: set[tuple[str, str]] = set()
    for r in matched:
        if r["action_level"] == "discuss_with_doctor":
            discuss_items.add((_category_display(r["category"]), r["recommendation_text"]))
    for tk, txt in topic_translations.items():
        for item in _extract_discuss_items_from_topic(txt):
            category = "Topic: " + tk
            discuss_items.add((category, item))

    grouped: dict[str, list[str]] = {}
    for cat, item in discuss_items:
        grouped.setdefault(cat, []).append(item)
    for k in grouped:
        grouped[k] = sorted(set(grouped[k]))

    # evidence appendix mapping
    retrieved_by_pmid = {str(s.get("pmid")): s for s in retrieved if s.get("pmid")}
    cited_sorted = sorted([p for p in cited_pmids if p in retrieved_by_pmid], key=lambda x: int(x))

    top5_text = _ai_top_5_actions(
        patient_context_snapshot=snapshot,
        matched_recommendations=matched,
        topic_narratives=topic_translations,
    )
    august_box = _prioritize_august_handoff(grouped, max_items=5)

    # Build docx
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Inches

    doc = Document()
    configure_document_typography(doc)
    ensure_bullet_styles(doc)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("Your Personal Health Report")
    r.bold = True
    r.font.size = Pt(20)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("Action-oriented translation of your labs, genetics, and current research - prepared for Robert Grogan")
    dt = doc.add_paragraph()
    dt.alignment = WD_ALIGN_PARAGRAPH.CENTER
    dt.add_run(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    doc.add_paragraph(
        "This is the companion to the physician report you are bringing to Dr. Lamkin. "
        "It is organized around what you can do now, what you should bring to your next visit, "
        "and what evidence supports each move. Every cited study is real and verifiable by PMID."
    )

    doc.add_heading("Your Top 5 Actions This Month", level=1)
    add_text_with_bullets(doc, top5_text)

    doc.add_heading("Bring to Dr. Lamkin in August", level=2)
    box = doc.add_table(rows=1, cols=1)
    apply_table_layout(box, [6.5])
    box_cell = box.rows[0].cells[0]
    box_cell.text = ""
    for item in august_box:
        box_cell.add_paragraph(f"- {item}", style="List Bullet")

    doc.add_heading("How you're doing right now", level=1)
    for p in section1.split("\n\n"):
        if p.strip():
            doc.add_paragraph(p.strip())

    doc.add_heading("Your genetic playbook", level=1)
    order = ["Diet", "Exercise", "Supplements", "Sleep & Lifestyle", "Monitoring", "Behavior"]
    grouped_recs: dict[str, list[dict[str, Any]]] = {}
    for rec in matched:
        grouped_recs.setdefault(_category_display(rec["category"]), []).append(rec)
    for cat in order:
        entries = grouped_recs.get(cat, [])
        if not entries:
            continue
        doc.add_heading(cat, level=2)
        for e in entries:
            p = doc.add_paragraph()
            rr = p.add_run(e["recommendation_text"])
            rr.bold = True
            doc.add_paragraph(e["rationale"])
            tag = "[self-directed]" if e["action_level"] == "self_directed" else "[discuss with Dr. Lamkin]"
            tag_p = doc.add_paragraph(tag)
            for run in tag_p.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = None

    for tk, txt in topic_translations.items():
        from app.research.topic_catalog import TOPICS

        title = TOPICS.get(tk, {}).get("title", tk)
        doc.add_heading(title, level=1)
        add_text_with_bullets(doc, txt)

    doc.add_heading("Questions to bring to Dr. Lamkin", level=1)
    for cat in sorted(grouped.keys()):
        doc.add_heading(cat, level=2)
        for item in grouped[cat]:
            doc.add_paragraph(f"- {item}", style="List Bullet")

    doc.add_heading("The evidence behind this", level=1)
    # small appendix table for readability
    tbl = doc.add_table(rows=1, cols=4)
    apply_table_layout(tbl, [0.8, 2.4, 1.0, 2.3])
    headers = ["PMID", "Title", "Journal/Year", "Summary"]
    for i, h in enumerate(headers):
        set_cell_text(tbl.rows[0].cells[i], h, bold=True, size_pt=9)
        shade_cell(tbl.rows[0].cells[i], "D9D9D9")
    for pid in cited_sorted:
        s = retrieved_by_pmid[pid]
        row = tbl.add_row().cells
        vals = [
            pid,
            truncate(s.get("title") or "", 120),
            truncate(f"{s.get('journal','')} ({s.get('year','')})", 70),
            truncate((s.get("summary") or s.get("abstract") or "").replace("\n", " "), 220),
        ]
        for i, v in enumerate(vals):
            set_cell_text(row[i], v, size_pt=9)
            row[i].width = Inches([0.8, 2.4, 1.0, 2.3][i])

    doc.save(str(out_path))

    # update clinical report
    db = SessionLocal()
    try:
        row2 = db.query(ClinicalReport).filter(ClinicalReport.id == report_row.id).first()
        row2.patient_docx_path = str(out_path.resolve())
        db.commit()
    finally:
        db.close()

    # integrity checks summary
    narrative_blob = "\n".join(topic_translations.values())
    hedging_hits = [t for t in HEDGING_TERMS if t in narrative_blob.lower()]
    number_pool = _numbers_from_context(snapshot)
    section1_numbers = _extract_normalized_numbers(section1)
    number_integrity_ok = all(n in number_pool for n in section1_numbers)
    pmid_integrity_ok = all(pid in retrieved_by_pmid for pid in _extract_pmids(narrative_blob))

    # attach debug text fields for requested output extraction
    return {
        "patient_docx_path": str(out_path.resolve()),
        "recommendations_matched": len(matched),
        "topics_translated": len(topic_translations),
        "total_cited_pmids": len(cited_sorted),
        "section1_text": section1,
        "topic_sections": topic_translations,
        "recommendation_samples": random.sample(matched, k=min(3, len(matched))),
        "questions_section": grouped,
        "top5_actions_text": top5_text,
        "august_handoff_items": august_box,
        "hedging_hits": hedging_hits,
        "pmid_integrity_ok": pmid_integrity_ok,
        "number_integrity_ok": number_integrity_ok,
    }
