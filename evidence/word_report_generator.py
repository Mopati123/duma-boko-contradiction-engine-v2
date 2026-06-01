#!/usr/bin/env python3
"""
Word Report Generator v2.

Builds deterministic Markdown reports from assembled sample cases using a
Microsoft Word-compatible section structure. The reports are generated artifacts
only; they are not approved evidence and do not mark production, public, or
institutional readiness.
"""

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_CASES = Path("outputs/case_assembly_engine/assembled_cases.json")
DEFAULT_CASE_SUMMARY = Path("outputs/case_assembly_engine/case_assembly_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/word_report_generator")
REPORTS_DIR = DEFAULT_OUTPUT_DIR / "reports"
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "word_report_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "word_report_summary.json"
MASTER_REPORT = REPORTS_DIR / "Duma_Boko_Contradiction_Engine_v2_Master_Report.md"

ENGINE_STATUS = "WORD_REPORT_GENERATOR_CANDIDATE"
REPORT_STATUS = "candidate_markdown_report"

CASE_REPORTS = {
    "CASE_SAMPLE_001": REPORTS_DIR / "CASE_SAMPLE_001_report.md",
    "CASE_SAMPLE_002": REPORTS_DIR / "CASE_SAMPLE_002_report.md",
    "CASE_SAMPLE_003": REPORTS_DIR / "CASE_SAMPLE_003_report.md",
}

REPORT_SECTIONS = (
    "DUMA BOKO CONTRADICTION ENGINE v2",
    "CASE SUMMARY",
    "SOURCE DETAILS",
    "SOURCE OWNERSHIP",
    "SPEAKER / POLITICAL LEADER",
    "ORIGINAL PROMISE",
    "CURRENT GOVERNMENT POSITION",
    "EVIDENCE COLLECTION",
    "CONTRADICTION ANALYSIS",
    "PROOF CHAIN",
    "GOVERNANCE VERIFICATION",
    "FINAL OUTPUT PACKAGE",
)

CASE_FIELDS = (
    "case_id",
    "case_title",
    "case_category",
    "case_status",
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "claims",
    "normalized_claims",
    "contradiction_edges",
    "proof_chains",
    "final_finding",
    "confidence_score",
    "severity",
    "governance_verification",
    "final_report_validation_checklist",
    "case_root",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _format_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, sort_keys=True) + "\n```"


def _has_localization(item: Dict[str, Any]) -> bool:
    has_video = bool(item.get("video_timestamp_start")) and bool(item.get("video_timestamp_end"))
    has_transcript = int(item.get("transcript_start_line") or 0) > 0 and int(
        item.get("transcript_end_line") or 0
    ) >= int(item.get("transcript_start_line") or 0)
    has_screenshot = bool(item.get("screenshot_reference"))
    has_document = int(item.get("document_page_start") or 0) > 0 and int(
        item.get("document_page_end") or 0
    ) >= int(item.get("document_page_start") or 0)
    return has_video or has_transcript or has_screenshot or has_document


def _validate_upstream(cases_payload: Dict[str, Any], case_summary: Dict[str, Any]) -> str:
    if not cases_payload:
        return "BLOCKED_MISSING_ASSEMBLED_CASES"
    if not case_summary:
        return "BLOCKED_MISSING_CASE_ASSEMBLY_SUMMARY"
    if case_summary.get("case_assembly_status") != "CASE_ASSEMBLY_ENGINE_CANDIDATE":
        return "BLOCKED_INVALID_CASE_ASSEMBLY_SUMMARY"
    if case_summary.get("assembled_case_count") != 3:
        return "BLOCKED_INVALID_CASE_ASSEMBLY_SUMMARY"
    if case_summary.get("valid_case_count") != 3:
        return "BLOCKED_INVALID_CASE_ASSEMBLY_SUMMARY"
    if case_summary.get("case_assembly_ready") is not True:
        return "BLOCKED_INVALID_CASE_ASSEMBLY_SUMMARY"
    if not _closed_flags(case_summary):
        return "BLOCKED_INVALID_CASE_ASSEMBLY_SUMMARY"
    cases = cases_payload.get("assembled_cases")
    if not isinstance(cases, list) or len(cases) != 3:
        return "BLOCKED_INVALID_ASSEMBLED_CASES"
    try:
        for case in cases:
            if set(case.keys()) != set(CASE_FIELDS):
                return "BLOCKED_INVALID_ASSEMBLED_CASES"
            for field_name in ("case_id", "case_title", "case_root"):
                _require_nonempty_string(case, field_name, "AssembledCase")
            if not _is_nonzero_hash(case["case_root"]):
                return "BLOCKED_INVALID_ASSEMBLED_CASES"
            if not _closed_flags(case["governance_verification"]):
                return "BLOCKED_INVALID_ASSEMBLED_CASES"
            if not _closed_flags(case["final_report_validation_checklist"]):
                return "BLOCKED_INVALID_ASSEMBLED_CASES"
            items = case["evidence_collection"].get("evidence_items", [])
            if not items:
                return "BLOCKED_INVALID_ASSEMBLED_CASES"
            for item in items:
                for field_name in ("hash_sha256", "source_reference", "quote_text"):
                    _require_nonempty_string(item, field_name, "LocalizedEvidenceItem")
                if not _has_localization(item):
                    return "BLOCKED_INVALID_ASSEMBLED_CASES"
    except (KeyError, TypeError, ValueError):
        return "BLOCKED_INVALID_ASSEMBLED_CASES"
    return ENGINE_STATUS


def _evidence_lines(case: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for item in case["evidence_collection"]["evidence_items"]:
        lines.extend(
            [
                f"- Evidence ID: {item['evidence_id']}",
                f"  - Evidence Type: {item['evidence_type']}",
                f"  - video timestamp: {item.get('video_timestamp_start', '')} to {item.get('video_timestamp_end', '')}",
                f"  - audio timestamp: {item.get('audio_timestamp_start', '')} to {item.get('audio_timestamp_end', '')}",
                f"  - transcript line range: {item.get('transcript_start_line', 0)} to {item.get('transcript_end_line', 0)}",
                f"  - screenshot reference: {item.get('screenshot_reference', '')}",
                f"  - document page range: {item.get('document_page_start', 0)} to {item.get('document_page_end', 0)}",
                f"  - evidence hash: {item['hash_sha256']}",
                f"  - source reference: {item['source_reference']}",
                f"  - quote text: {item['quote_text']}",
                f"  - verification status: {item['verification_status']}",
                f"  - localization status: {item['localization_status']}",
            ]
        )
    return lines


def _case_report(case: Dict[str, Any]) -> str:
    final_finding = case["final_finding"]
    lines = [
        f"# {REPORT_SECTIONS[0]}",
        "",
        f"## {REPORT_SECTIONS[1]}",
        f"- Case ID: {case['case_id']}",
        f"- Case Title: {case['case_title']}",
        f"- Case Category: {case['case_category']}",
        f"- Case Status: {case['case_status']}",
        f"- Final Relationship: {final_finding['relationship_type']}",
        f"- Contradiction Found: {final_finding['contradiction_found']}",
        f"- Confidence Score: {case['confidence_score']}",
        f"- Severity: {case['severity']}",
        "",
        f"## {REPORT_SECTIONS[2]}",
        _format_json(case["source_details"]),
        "",
        f"## {REPORT_SECTIONS[3]}",
        _format_json(case["source_ownership"]),
        "",
        f"## {REPORT_SECTIONS[4]}",
        _format_json(case["speaker_political_leader"]),
        "",
        f"## {REPORT_SECTIONS[5]}",
        _format_json(case["original_promise"]),
        "",
        f"## {REPORT_SECTIONS[6]}",
        _format_json(case["current_government_position"]),
        "",
        f"## {REPORT_SECTIONS[7]}",
    ]
    lines.extend(_evidence_lines(case))
    lines.extend(
        [
            "",
            f"## {REPORT_SECTIONS[8]}",
            f"- Primary Edge ID: {final_finding['primary_edge_id']}",
            f"- Primary Proof Chain ID: {final_finding['primary_proof_chain_id']}",
            f"- Relationship Type: {final_finding['relationship_type']}",
            f"- Contradiction Type: {final_finding['contradiction_type']}",
            f"- Contradiction Found: {final_finding['contradiction_found']}",
            f"- Reasoning Summary: {final_finding['reasoning_summary']}",
            "",
            f"## {REPORT_SECTIONS[9]}",
            _format_json(case["proof_chains"]),
            "",
            f"## {REPORT_SECTIONS[10]}",
            _format_json(case["governance_verification"]),
            "",
            f"## {REPORT_SECTIONS[11]}",
            f"- Case Root: {case['case_root']}",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )
    return "\n".join(lines)


def _master_report(cases: List[Dict[str, Any]]) -> str:
    lines = [
        f"# {REPORT_SECTIONS[0]}",
        "",
        "## MASTER REPORT SUMMARY",
        f"- Case Report Count: {len(cases)}",
        f"- Contradiction Case Count: {sum(1 for case in cases if case['final_finding']['contradiction_found'])}",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
        "## CASE INDEX",
    ]
    for case in cases:
        lines.extend(
            [
                f"- {case['case_id']}: {case['case_title']}",
                f"  - Relationship: {case['final_finding']['relationship_type']}",
                f"  - Contradiction Found: {case['final_finding']['contradiction_found']}",
                f"  - Case Root: {case['case_root']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _report_manifest(cases: List[Dict[str, Any]]) -> Dict[str, str]:
    manifest: Dict[str, str] = {}
    for case in cases:
        path = CASE_REPORTS[case["case_id"]]
        manifest[str(path)] = _sha256_text(_case_report(case))
    manifest[str(MASTER_REPORT)] = _sha256_text(_master_report(cases))
    return manifest


def build_word_report_generator(
    cases_path: Path = DEFAULT_CASES,
    case_summary_path: Path = DEFAULT_CASE_SUMMARY,
) -> Dict[str, Any]:
    cases_payload = _load_json(cases_path)
    case_summary = _load_json(case_summary_path)
    status = _validate_upstream(cases_payload, case_summary)
    cases = cases_payload.get("assembled_cases", []) if status == ENGINE_STATUS else []
    report_manifest = _report_manifest(cases)
    report_root = _hash_json({"report_hashes": report_manifest})
    case_report_count = len(cases)
    report_count = case_report_count + (1 if cases else 0)
    ready = status == ENGINE_STATUS and report_count == 4 and case_report_count == 3
    payload = {
        "records": [
            {
                "word_report_status": status,
                "report_count": report_count,
                "case_report_count": case_report_count,
                "master_report_generated": bool(cases),
                "word_report_root": report_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "word_report_status": status,
        "report_count": report_count,
        "case_report_count": case_report_count,
        "master_report_generated": bool(cases),
        "word_report_ready": ready,
        "master_report_path": str(MASTER_REPORT),
        "report_hashes": report_manifest,
        "word_report_root": report_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    for case in cases:
        _write_text(CASE_REPORTS[case["case_id"]], _case_report(case))
    if cases:
        _write_text(MASTER_REPORT, _master_report(cases))
    return {
        "payload": payload,
        "summary": summary,
        "reports": report_manifest,
    }
