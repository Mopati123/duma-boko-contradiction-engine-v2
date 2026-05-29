#!/usr/bin/env python3
"""
Final Report Collapse Engine v1.

Builds deterministic final-report collapse preflight records from canonical graph
mutation candidates. This lane proves whether the system has enough canonical
replacement evidence to proceed toward final report generation.

It does not generate the report, does not mutate the graph, does not approve
evidence, and does not mark public/institutional/report readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_MUTATION_STATUS = Path(
    "outputs/canonical_graph_mutation/canonical_graph_mutation_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/final_report_collapse_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_report_collapse_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_report_collapse_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "collapse_applied",
    "report_generated",
)

ALLOWED_COLLAPSE_STATUSES = {
    "report_collapse_candidate",
    "report_collapse_blocked_missing_mutation",
    "report_collapse_blocked_unapplied_mutation",
    "report_collapse_blocked_invalid_url",
    "report_collapse_invalid",
}


@dataclass
class FinalReportCollapseRecord:
    collapse_id: str
    evidence_id: str
    case_id: str
    collapse_status: str
    mutation_hash: str
    replacement_url: str
    replacement_content_hash: str
    legacy_empty_url_replaced: bool
    collapse_applied: bool
    report_generated: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonempty_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith(("http://", "https://"))


def _load_mutation_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "collapse_id",
        "evidence_id",
        "case_id",
        "collapse_status",
        "mutation_hash",
        "replacement_url",
        "replacement_content_hash",
        "legacy_empty_url_replaced",
        "collapse_applied",
        "report_generated",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"FinalReportCollapseRecord missing fields: {sorted(missing)}")

    if data["collapse_status"] not in ALLOWED_COLLAPSE_STATUSES:
        raise ValueError(f"Unsupported collapse_status: {data['collapse_status']}")

    if data["collapse_status"] == "report_collapse_candidate":
        if not _is_nonempty_url(data["replacement_url"]):
            raise ValueError("replacement_url must be a non-empty http(s) URL")
        if not data["replacement_content_hash"]:
            raise ValueError("replacement_content_hash must be non-empty")
        if data["legacy_empty_url_replaced"] is not True:
            raise ValueError("legacy_empty_url_replaced must be true for collapse candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_record_from_mutation(mutation: Dict[str, Any]) -> FinalReportCollapseRecord:
    replacement = mutation.get("replacement_evidence_object") or {}

    evidence_id = str(mutation.get("evidence_id") or replacement.get("evidence_id") or "UNKNOWN")
    case_id = str(mutation.get("case_id") or replacement.get("case_id") or "UNKNOWN")
    mutation_hash = str(mutation.get("mutation_hash") or "")
    replacement_url = str(mutation.get("canonical_url") or replacement.get("url") or "")
    replacement_content_hash = str(mutation.get("content_hash") or replacement.get("content_hash") or "")

    if mutation.get("mutation_status") != "mutation_candidate":
        status = "report_collapse_blocked_missing_mutation"
        legacy_empty_url_replaced = False
    elif not _is_nonempty_url(replacement_url):
        status = "report_collapse_blocked_invalid_url"
        legacy_empty_url_replaced = False
    else:
        status = "report_collapse_candidate"
        legacy_empty_url_replaced = True

    material = json.dumps(
        {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "collapse_status": status,
            "mutation_hash": mutation_hash,
            "replacement_url": replacement_url,
            "replacement_content_hash": replacement_content_hash,
            "legacy_empty_url_replaced": legacy_empty_url_replaced,
            "collapse_applied": False,
            "report_generated": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    collapse_hash = _sha256_text(material)

    record = FinalReportCollapseRecord(
        collapse_id=f"REPORT_COLLAPSE_{evidence_id}_{collapse_hash[:16]}",
        evidence_id=evidence_id,
        case_id=case_id,
        collapse_status=status,
        mutation_hash=mutation_hash,
        replacement_url=replacement_url,
        replacement_content_hash=replacement_content_hash,
        legacy_empty_url_replaced=legacy_empty_url_replaced,
        collapse_applied=False,
        report_generated=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Final report collapse preflight candidate only. No graph mutation, "
            "final report generation, evidence approval, public release, institutional "
            "release, or readiness flag mutation occurred."
        ),
    )

    validate_record(record)
    return record


def build_final_report_collapse(
    evidence_id: Optional[str] = None,
    mutation_status_path: Path = DEFAULT_MUTATION_STATUS,
) -> Dict[str, Any]:
    mutation_records = _load_mutation_records(mutation_status_path)

    if evidence_id:
        mutation_records = [
            record for record in mutation_records
            if record.get("evidence_id") == evidence_id
        ]

    records: List[FinalReportCollapseRecord] = []

    if not mutation_records:
        material = json.dumps(
            {
                "evidence_id": evidence_id or "ALL",
                "collapse_status": "report_collapse_blocked_missing_mutation",
                "collapse_applied": False,
                "report_generated": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        collapse_hash = _sha256_text(material)

        record = FinalReportCollapseRecord(
            collapse_id=f"REPORT_COLLAPSE_{evidence_id or 'ALL'}_{collapse_hash[:16]}",
            evidence_id=evidence_id or "ALL",
            case_id="UNKNOWN",
            collapse_status="report_collapse_blocked_missing_mutation",
            mutation_hash="",
            replacement_url="",
            replacement_content_hash="",
            legacy_empty_url_replaced=False,
            collapse_applied=False,
            report_generated=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="Canonical graph mutation proof is missing; report collapse cannot proceed.",
        )
        validate_record(record)
        records.append(record)
    else:
        for mutation in mutation_records:
            records.append(_build_record_from_mutation(mutation))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    collapse_root = (
        _sha256_text(
            "|".join(
                _sha256_text(
                    json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                )
                for record in records
            )
        )
        if records
        else "0" * 64
    )

    summary = {
        "collapse_record_count": len(records),
        "report_collapse_candidate_count": sum(
            1 for record in records if record.collapse_status == "report_collapse_candidate"
        ),
        "report_collapse_blocked_missing_mutation_count": sum(
            1 for record in records
            if record.collapse_status == "report_collapse_blocked_missing_mutation"
        ),
        "report_collapse_blocked_unapplied_mutation_count": sum(
            1 for record in records
            if record.collapse_status == "report_collapse_blocked_unapplied_mutation"
        ),
        "report_collapse_blocked_invalid_url_count": sum(
            1 for record in records if record.collapse_status == "report_collapse_blocked_invalid_url"
        ),
        "report_collapse_invalid_count": sum(
            1 for record in records if record.collapse_status == "report_collapse_invalid"
        ),
        "legacy_empty_url_replaced_count": sum(
            1 for record in records if record.legacy_empty_url_replaced
        ),
        "collapse_root": collapse_root,
        "collapse_applied": False,
        "report_generated": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}