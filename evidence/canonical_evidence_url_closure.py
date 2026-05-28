#!/usr/bin/env python3
"""
Canonical Evidence URL Closure Engine v1.

Builds deterministic URL-closure records for evidence nodes that must not reach
final report generation with missing, empty, or placeholder URLs.

This is a pre-production closure gate. It does not approve evidence, publish,
mark report readiness, or mutate cases. It proves whether canonical source URLs
exist for every known high-priority evidence node.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_OUTPUT_DIR = Path("outputs/canonical_evidence_url_closure")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_url_closure_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_url_closure_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "url_closure_applied",
)

ALLOWED_URL_CLOSURE_STATUSES = {
    "url_closure_candidate",
    "url_closure_not_needed",
    "url_closure_blocked",
    "url_closure_invalid",
}

CANONICAL_URL_MAP = {
    "VID_JOBS_001": {
        "case_id": "CASE_002",
        "canonical_url": "https://www.udc.org.bw/",
        "canonical_source_type": "official_manifesto_source",
        "canonical_lineage": "recovery:selected_source:canonical_template:case_graph_normalization",
        "closure_reason": "CASE_002 report blocker requires canonical non-empty official manifesto source URL.",
    },
    "VID_HEALTH_001": {
        "case_id": "CASE_006",
        "canonical_url": "https://www.aljazeera.com/news/2025/8/26/botswana-declares-public-health-emergency-over-medicine-shortage",
        "canonical_source_type": "secondary_corroboration",
        "canonical_lineage": "recovery:fallback_source:canonical_template:case_graph_normalization",
        "closure_reason": "CASE_006 requires canonical non-empty fallback article source URL.",
    },
}


@dataclass
class CanonicalEvidenceUrlClosureRecord:
    closure_id: str
    evidence_id: str
    case_id: str
    url_closure_status: str
    canonical_url: str
    canonical_source_type: str
    canonical_lineage: str
    closure_reason: str
    provenance_hash: str
    url_closure_applied: bool
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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonempty_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith(("http://", "https://"))


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "closure_id",
        "evidence_id",
        "case_id",
        "url_closure_status",
        "canonical_url",
        "canonical_source_type",
        "canonical_lineage",
        "closure_reason",
        "provenance_hash",
        "url_closure_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CanonicalEvidenceUrlClosureRecord missing fields: {sorted(missing)}")

    if data["url_closure_status"] not in ALLOWED_URL_CLOSURE_STATUSES:
        raise ValueError(f"Unsupported url_closure_status: {data['url_closure_status']}")

    if data["url_closure_status"] == "url_closure_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_canonical_evidence_url_closure(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    ids = [evidence_id] if evidence_id else sorted(CANONICAL_URL_MAP)

    records: List[CanonicalEvidenceUrlClosureRecord] = []

    for current_evidence_id in ids:
        canonical = CANONICAL_URL_MAP.get(current_evidence_id)

        if canonical is None:
            case_id = "UNKNOWN"
            canonical_url = ""
            canonical_source_type = "unknown"
            canonical_lineage = "unknown"
            closure_reason = "No canonical URL mapping exists for this evidence ID."
            status = "url_closure_blocked"
        else:
            case_id = canonical["case_id"]
            canonical_url = canonical["canonical_url"]
            canonical_source_type = canonical["canonical_source_type"]
            canonical_lineage = canonical["canonical_lineage"]
            closure_reason = canonical["closure_reason"]
            status = "url_closure_candidate"

        material = json.dumps(
            {
                "evidence_id": current_evidence_id,
                "case_id": case_id,
                "url_closure_status": status,
                "canonical_url": canonical_url,
                "canonical_source_type": canonical_source_type,
                "canonical_lineage": canonical_lineage,
                "url_closure_applied": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        provenance_hash = _sha256_text(material)

        record = CanonicalEvidenceUrlClosureRecord(
            closure_id=f"URL_CLOSURE_{current_evidence_id}_{provenance_hash[:16]}",
            evidence_id=current_evidence_id or "UNKNOWN",
            case_id=case_id,
            url_closure_status=status,
            canonical_url=canonical_url,
            canonical_source_type=canonical_source_type,
            canonical_lineage=canonical_lineage,
            closure_reason=closure_reason,
            provenance_hash=provenance_hash,
            url_closure_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only canonical URL closure record. No case graph, template, "
                "approval, readiness, public release, or final report mutation occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    closure_root = (
        _sha256_text("|".join(record.provenance_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "url_closure_record_count": len(records),
        "url_closure_candidate_count": sum(
            1 for record in records if record.url_closure_status == "url_closure_candidate"
        ),
        "url_closure_not_needed_count": sum(
            1 for record in records if record.url_closure_status == "url_closure_not_needed"
        ),
        "url_closure_blocked_count": sum(
            1 for record in records if record.url_closure_status == "url_closure_blocked"
        ),
        "url_closure_invalid_count": sum(
            1 for record in records if record.url_closure_status == "url_closure_invalid"
        ),
        "closure_root": closure_root,
        "url_closure_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}