#!/usr/bin/env python3
"""
Draft Word report preview.

Builds a boss-facing DOCX preview from current temporal evidence artifacts. This
is not a final contradiction report: it does not fetch URLs, call LLMs, create
embeddings, evaluate predicate incompatibility, score contradictions, approve
evidence, mark production readiness, or create final reports.
"""

from pathlib import Path
from typing import Any, Dict, List, Sequence
from xml.sax.saxutils import escape
import hashlib
import json
import zipfile


DEFAULT_CONTEXT = Path("inputs/report_metadata/duma_boko_final_word_report_context.json")
DEFAULT_BEFORE_CANDIDATES = Path(
    "outputs/before_temporal_claim_normalization/before_temporal_claim_candidates.json"
)
DEFAULT_AFTER_CANDIDATES = Path(
    "outputs/temporal_claim_normalization/temporal_claim_candidates.json"
)
DEFAULT_PAIRS = Path("outputs/temporal_same_object_pairing/temporal_comparison_pairs.json")
DEFAULT_PAIRING_SUMMARY = Path(
    "outputs/temporal_same_object_pairing/temporal_same_object_pairing_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/final_word_report_preview")
DOCX_OUTPUT = DEFAULT_OUTPUT_DIR / "DUMA_BOKO_PROMISE_DELIVERY_EVIDENCE_REPORT_DRAFT.docx"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_word_report_preview_summary.json"

SCHEMA_VERSION = "final_word_report_preview_v1"
PREVIEW_STATUS = "FINAL_WORD_REPORT_PREVIEW_CANDIDATE"
FINAL_STATUS = "TEMPORAL_COMPARISON_CANDIDATE"
REPORT_DATE = "2026-06-12"

REQUIRED_SECTIONS = (
    "Cover Page",
    "Subject Identity",
    "Executive Summary",
    "Human Verdict",
    "BEFORE Evidence",
    "AFTER Evidence",
    "Same-Object / Same-Domain Pairing",
    "Promise-Delivery Comparison",
    "Contradiction Geometry",
    "Guardrails",
    "Audit Lineage",
    "Human Review Notes",
    "Machine Audit Appendix",
)
SUBJECT_IDENTITY_FIELDS = (
    "Name",
    "Political Party",
    "Party Abbreviation",
    "Position Title",
    "Role at BEFORE Time",
    "Current Government Position",
    "Jurisdiction",
    "Primary Evidence ID",
    "Original Promise",
    "Human-reviewed Quote",
    "Key Phrase",
)
HUMAN_VERDICT_EXPLANATION = (
    "The system has established admissible BEFORE and AFTER temporal evidence "
    "paths and neutral same-domain comparison pairs. It has not yet completed "
    "predicate incompatibility detection. Therefore no contradiction is declared."
)


class FinalWordReportPreviewRefusal(ValueError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _hash_json(payload: Any) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FinalWordReportPreviewRefusal(f"Required input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _require_nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinalWordReportPreviewRefusal(f"{label} must be a non-empty string.")
    return value.strip()


def _load_context(path: Path) -> Dict[str, Any]:
    context = _load_json(path)
    if context.get("metadata_id") != "DUMA_BOKO_FINAL_WORD_REPORT_CONTEXT_V1":
        raise FinalWordReportPreviewRefusal("Report identity context metadata_id is unsupported.")
    subject = context.get("subject_identity")
    promise = context.get("primary_promise")
    if not isinstance(subject, dict) or not isinstance(promise, dict):
        raise FinalWordReportPreviewRefusal("Report identity context is missing subject/promise blocks.")
    required = {
        "Name": subject.get("name"),
        "Political Party": subject.get("political_party"),
        "Party Abbreviation": subject.get("political_party_abbreviation"),
        "Position Title": subject.get("position_title"),
        "Role at BEFORE Time": subject.get("role_at_before_time"),
        "Current Government Position": subject.get("current_government_position"),
        "Jurisdiction": subject.get("location_or_jurisdiction"),
        "Primary Evidence ID": promise.get("evidence_id"),
        "Original Promise": promise.get("original_promise"),
        "Human-reviewed Quote": promise.get("human_reviewed_quote_text"),
        "Key Phrase": promise.get("key_phrase"),
    }
    for label in SUBJECT_IDENTITY_FIELDS:
        _require_nonempty(required.get(label), label)
    if promise.get("human_review_required") is not True or promise.get("production_ready") is not False:
        raise FinalWordReportPreviewRefusal("Primary promise guardrails must remain closed.")
    return context


def _load_before_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("schema_version") != "before_temporal_claim_normalization_v1":
        raise FinalWordReportPreviewRefusal("BEFORE temporal candidate schema_version is unsupported.")
    candidates = payload.get("before_temporal_claim_candidates")
    if not isinstance(candidates, list):
        raise FinalWordReportPreviewRefusal("BEFORE temporal candidates must be a list.")
    for candidate in candidates:
        if candidate.get("temporal_position") != "BEFORE":
            raise FinalWordReportPreviewRefusal("BEFORE temporal candidate position must remain BEFORE.")
        for field_name in ("temporal_claim_id", "claim_text", "claim_time", "packet_root", "source_claim_root", "temporal_claim_root"):
            _require_nonempty(candidate.get(field_name), f"BEFORE.{field_name}")
    return candidates


def _load_after_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("schema_version") != "manual_after_temporal_claim_normalization_v1":
        raise FinalWordReportPreviewRefusal("AFTER temporal candidate schema_version is unsupported.")
    candidates = payload.get("temporal_claim_candidates")
    if not isinstance(candidates, list):
        raise FinalWordReportPreviewRefusal("AFTER temporal candidates must be a list.")
    for candidate in candidates:
        if candidate.get("temporal_position") != "AFTER":
            raise FinalWordReportPreviewRefusal("AFTER temporal candidate position must remain AFTER.")
        for field_name in ("temporal_claim_id", "claim_text", "claim_time", "packet_root", "source_claim_root", "temporal_claim_root"):
            _require_nonempty(candidate.get(field_name), f"AFTER.{field_name}")
    return candidates


def _load_pairs(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("schema_version") != "temporal_same_object_pairing_v1":
        raise FinalWordReportPreviewRefusal("Temporal comparison pair schema_version is unsupported.")
    pairs = payload.get("temporal_comparison_pairs")
    if not isinstance(pairs, list):
        raise FinalWordReportPreviewRefusal("Temporal comparison pairs must be a list.")
    for pair in pairs:
        for field_name in (
            "temporal_comparison_pair_id",
            "before_temporal_claim_id",
            "after_temporal_claim_id",
            "before_claim_text",
            "after_claim_text",
            "pair_root",
        ):
            _require_nonempty(pair.get(field_name), f"Pair.{field_name}")
        if pair.get("neutral_pairing_only") is not True:
            raise FinalWordReportPreviewRefusal("Temporal comparison pair must remain neutral.")
    return pairs


def _load_pairing_summary(path: Path, before_count: int, after_count: int, pair_count: int) -> Dict[str, Any]:
    summary = _load_json(path)
    if summary.get("temporal_same_object_pairing_status") not in (
        "TEMPORAL_SAME_OBJECT_PAIRING_CANDIDATE",
        "TEMPORAL_SAME_OBJECT_PAIRING_PARTIAL",
        "TEMPORAL_SAME_OBJECT_PAIRING_NO_MATCH",
    ):
        raise FinalWordReportPreviewRefusal("Temporal same-object pairing status is unsupported.")
    expected = {
        "before_temporal_claim_count": before_count,
        "after_temporal_claim_count": after_count,
        "temporal_comparison_pair_count": pair_count,
    }
    for field_name, value in expected.items():
        if summary.get(field_name) != value:
            raise FinalWordReportPreviewRefusal(f"Pairing summary {field_name} does not match artifacts.")
    if summary.get("neutral_pairing_only") is not True or summary.get("contradictions_created") != 0:
        raise FinalWordReportPreviewRefusal("Pairing summary must remain neutral and non-contradictory.")
    for counter_name in (
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "final_reports_created",
        "approved_evidence",
    ):
        if summary.get(counter_name) != 0:
            raise FinalWordReportPreviewRefusal(f"Pairing guardrail {counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise FinalWordReportPreviewRefusal("Pairing summary governance flags must remain closed.")
    return summary


def _xml_text(text: Any) -> str:
    return escape(str(text), {"\"": "&quot;"})


def _paragraph(text: str, bold: bool = False, size: int = 22) -> str:
    text_value = _xml_text(text)
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:p><w:r><w:rPr>"
        f"{bold_xml}<w:sz w:val=\"{size}\"/>"
        "</w:rPr><w:t xml:space=\"preserve\">"
        f"{text_value}</w:t></w:r></w:p>"
    )


def _heading(text: str, level: int = 1) -> str:
    size = 32 if level == 1 else 26
    return _paragraph(text, bold=True, size=size)


def _bullet(text: str) -> str:
    return _paragraph(f"- {text}", size=20)


def _page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _claim_line(candidate: Dict[str, Any]) -> str:
    return (
        f"{candidate['temporal_claim_id']} | {candidate.get('claim_time', '')} | "
        f"{candidate.get('claim_type', '')} | {candidate['claim_text']}"
    )


def _pair_line(pair: Dict[str, Any]) -> str:
    tokens = ", ".join(pair.get("matched_domain_tokens") or [])
    return (
        f"{pair['temporal_comparison_pair_id']} | tokens: {tokens} | "
        f"BEFORE {pair['before_temporal_claim_id']} -> AFTER {pair['after_temporal_claim_id']}"
    )


def _subject_identity_rows(context: Dict[str, Any]) -> Dict[str, str]:
    subject = context["subject_identity"]
    promise = context["primary_promise"]
    return {
        "Name": subject["name"],
        "Political Party": subject["political_party"],
        "Party Abbreviation": subject["political_party_abbreviation"],
        "Position Title": subject["position_title"],
        "Role at BEFORE Time": subject["role_at_before_time"],
        "Current Government Position": subject["current_government_position"],
        "Jurisdiction": subject["location_or_jurisdiction"],
        "Primary Evidence ID": promise["evidence_id"],
        "Original Promise": promise["original_promise"],
        "Human-reviewed Quote": promise["human_reviewed_quote_text"],
        "Key Phrase": promise["key_phrase"],
    }


def _document_elements(
    context: Dict[str, Any],
    before_candidates: List[Dict[str, Any]],
    after_candidates: List[Dict[str, Any]],
    pairs: List[Dict[str, Any]],
    pairing_summary: Dict[str, Any],
) -> List[str]:
    elements: List[str] = [
        _heading("DUMA BOKO PROMISE-DELIVERY EVIDENCE REPORT", 1),
        _paragraph("DRAFT PREVIEW", bold=True, size=30),
        _paragraph("HUMAN REVIEW REQUIRED", bold=True, size=26),
        _paragraph("PRODUCTION READY: FALSE", bold=True, size=24),
        _paragraph("NO FINAL CONTRADICTION DECLARED", bold=True, size=24),
        _paragraph(f"Report Date: {REPORT_DATE}", size=20),
        _paragraph(f"Final Status: {FINAL_STATUS}", size=20),
        _page_break(),
    ]
    for section in REQUIRED_SECTIONS[1:]:
        elements.append(_heading(section, 1))
        if section == "Subject Identity":
            for label, value in _subject_identity_rows(context).items():
                elements.append(_bullet(f"{label}: {value}"))
        elif section == "Executive Summary":
            elements.append(_paragraph(HUMAN_VERDICT_EXPLANATION))
            elements.append(_bullet(f"BEFORE temporal claim count: {len(before_candidates)}"))
            elements.append(_bullet(f"AFTER temporal claim count: {len(after_candidates)}"))
            elements.append(_bullet(f"Neutral same-domain comparison pair count: {len(pairs)}"))
        elif section == "Human Verdict":
            elements.append(_paragraph(f"Required verdict: {FINAL_STATUS}", bold=True))
            elements.append(_paragraph(HUMAN_VERDICT_EXPLANATION))
        elif section == "BEFORE Evidence":
            for candidate in before_candidates:
                elements.append(_bullet(_claim_line(candidate)))
                elements.append(_bullet(f"Root: {candidate['temporal_claim_root']}"))
        elif section == "AFTER Evidence":
            for candidate in after_candidates:
                elements.append(_bullet(_claim_line(candidate)))
                elements.append(_bullet(f"Root: {candidate['temporal_claim_root']}"))
        elif section == "Same-Object / Same-Domain Pairing":
            for pair in pairs:
                elements.append(_bullet(_pair_line(pair)))
                elements.append(_bullet(f"Pair Root: {pair['pair_root']}"))
            elements.append(_bullet(f"Unpaired BEFORE count: {pairing_summary.get('unpaired_before_claim_count', 0)}"))
            elements.append(_bullet(f"Unpaired AFTER count: {pairing_summary.get('unpaired_after_claim_count', 0)}"))
        elif section == "Promise-Delivery Comparison":
            promise = context["primary_promise"]
            elements.append(_bullet(f"Original Promise: {promise['original_promise']}"))
            elements.append(_bullet(f"Human-reviewed Quote: {promise['human_reviewed_quote_text']}"))
            elements.append(_bullet("Comparison status: neutral temporal comparison candidate only."))
        elif section == "Contradiction Geometry":
            elements.append(_bullet("Predicate incompatibility detection: NOT COMPLETED"))
            elements.append(_bullet("Contradiction scoring: NOT PERFORMED"))
            elements.append(_bullet("Contradiction declared: false"))
        elif section == "Guardrails":
            for line in (
                "urls_fetched: 0",
                "live_web_access_performed: 0",
                "llm_calls: 0",
                "embeddings_created: 0",
                "claims_rewritten: 0",
                "claims_normalized_semantically: 0",
                "contradictions_created: 0",
                "final_reports_created: 0",
                "approved_evidence: 0",
                "production_ready: false",
                "human_review_required: true",
            ):
                elements.append(_bullet(line))
        elif section == "Audit Lineage":
            elements.append(_bullet(f"Pairing root: {pairing_summary.get('temporal_same_object_pairing_root', '')}"))
            elements.append(_bullet(f"Pairing method: {pairing_summary.get('pairing_method', '')}"))
            elements.append(_bullet(f"Allowed domain tokens: {', '.join(pairing_summary.get('allowed_domain_tokens', []))}"))
        elif section == "Human Review Notes":
            elements.append(_paragraph("This draft is for human review and format preview only. It is not public-ready, institutional-ready, or production-ready."))
        elif section == "Machine Audit Appendix":
            elements.append(_bullet(f"Schema version: {SCHEMA_VERSION}"))
            elements.append(_bullet(f"Context hash: {_hash_json(context)}"))
            elements.append(_bullet(f"BEFORE candidate roots: {', '.join(candidate['temporal_claim_root'] for candidate in before_candidates)}"))
            elements.append(_bullet(f"AFTER candidate roots: {', '.join(candidate['temporal_claim_root'] for candidate in after_candidates)}"))
        elements.append(_paragraph(""))
    return elements


def _document_xml(elements: Sequence[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(elements)
        + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        "</w:body></w:document>"
    )


def _write_docx(path: Path, elements: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": _document_xml(elements),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:title>Duma Boko Promise-Delivery Evidence Report Draft Preview</dc:title>"
            "<dc:creator>Duma Boko Contradiction Engine v2</dc:creator>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{REPORT_DATE}T00:00:00Z</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{REPORT_DATE}T00:00:00Z</dcterms:modified>"
            "</cp:coreProperties>"
        ),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Duma Boko Contradiction Engine v2</Application>"
            "</Properties>"
        ),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        for file_name in sorted(files):
            docx.writestr(file_name, files[file_name])


def build_final_word_report_preview(
    context_path: Path = DEFAULT_CONTEXT,
    before_candidates_path: Path = DEFAULT_BEFORE_CANDIDATES,
    after_candidates_path: Path = DEFAULT_AFTER_CANDIDATES,
    pairs_path: Path = DEFAULT_PAIRS,
    pairing_summary_path: Path = DEFAULT_PAIRING_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    context = _load_context(context_path)
    before_candidates = _load_before_candidates(before_candidates_path)
    after_candidates = _load_after_candidates(after_candidates_path)
    pairs = _load_pairs(pairs_path)
    pairing_summary = _load_pairing_summary(
        pairing_summary_path,
        len(before_candidates),
        len(after_candidates),
        len(pairs),
    )

    docx_path = output_dir / DOCX_OUTPUT.name
    summary_path = output_dir / SUMMARY_OUTPUT.name
    elements = _document_elements(context, before_candidates, after_candidates, pairs, pairing_summary)
    _write_docx(docx_path, elements)
    docx_hash = _sha256_bytes(docx_path.read_bytes())
    summary = {
        "final_word_report_preview_status": PREVIEW_STATUS,
        "schema_version": SCHEMA_VERSION,
        "report_type": context["report_type"],
        "docx_preview_path": str(docx_path),
        "summary_path": str(summary_path),
        "docx_created": docx_path.exists(),
        "docx_sha256": docx_hash,
        "required_sections": list(REQUIRED_SECTIONS),
        "subject_identity_fields": list(SUBJECT_IDENTITY_FIELDS),
        "required_subject_identity_fields_present": True,
        "before_temporal_claim_count": len(before_candidates),
        "after_temporal_claim_count": len(after_candidates),
        "temporal_pair_count": len(pairs),
        "unpaired_before_claim_count": pairing_summary.get("unpaired_before_claim_count", 0),
        "unpaired_after_claim_count": pairing_summary.get("unpaired_after_claim_count", 0),
        "final_status": FINAL_STATUS,
        "human_verdict_explanation": HUMAN_VERDICT_EXPLANATION,
        "contradiction_declared": False,
        "predicate_incompatibility_detection_completed": False,
        "contradiction_scoring_completed": False,
        "human_review_required": True,
        "preview_reports_created": 1,
        "final_reports_created": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "embeddings_created": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "evidence_approved": 0,
        "approved_evidence": 0,
        "production_ready": False,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
        "final_word_report_preview_root": "",
    }
    summary["final_word_report_preview_root"] = _hash_json(summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(summary_path, summary)

    for counter_name in (
        "final_reports_created",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "evidence_approved",
        "approved_evidence",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if summary["contradiction_declared"] is not False or summary["human_review_required"] is not True:
        raise ValueError("Preview verdict guardrails must remain closed.")
    if not _closed_flags(summary):
        raise ValueError("Final Word report preview governance flags must remain closed.")

    return {
        "summary": summary,
        "docx_path": docx_path,
    }


__all__ = ["build_final_word_report_preview"]
