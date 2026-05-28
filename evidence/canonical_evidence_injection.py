#!/usr/bin/env python3
"""
Canonical Evidence Injection Engine v1.

Builds deterministic injection candidates from canonical evidence resolution
records. This engine prepares replacement EvidenceObject payloads that can later
be injected into the case graph before final report generation.

It does not mutate cases, does not approve evidence, does not publish, and does
not mark report readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_RESOLUTION_STATUS = Path(
    "outputs/canonical_evidence_resolution/canonical_evidence_resolution_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/canonical_evidence_injection")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_injection_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_injection_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "injection_applied",
)

ALLOWED_INJECTION_STATUSES = {
    "injection_candidate",
    "injection_blocked_missing_resolution",
    "injection_blocked_unresolved_snapshot",
    "injection_blocked_invalid_url",
    "injection_invalid",
}


@dataclass
class CanonicalEvidenceInjectionRecord:
    injection_id: str
    evidence_id: str
    case_id: str
    injection_status: str
    canonical_evidence_object: Dict[str, Any]
    canonical_url: str
    canonical_source_type: str
    canonical_lineage: str
    resolution_hash: str
    injection_hash: str
    injection_applied: bool
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


def _load_resolution_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "injection_id",
        "evidence_id",
        "case_id",
        "injection_status",
        "canonical_evidence_object",
        "canonical_url",
        "canonical_source_type",
        "canonical_lineage",
        "resolution_hash",
        "injection_hash",
        "injection_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CanonicalEvidenceInjectionRecord missing fields: {sorted(missing)}")

    if data["injection_status"] not in ALLOWED_INJECTION_STATUSES:
        raise ValueError(f"Unsupported injection_status: {data['injection_status']}")

    evidence_object = data["canonical_evidence_object"]
    if not isinstance(evidence_object, dict):
        raise ValueError("canonical_evidence_object must be an object")

    if data["injection_status"] == "injection_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")
        if not _is_nonempty_url(evidence_object.get("url")):
            raise ValueError("canonical_evidence_object.url must be a non-empty http(s) URL")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_evidence_object(resolution: Dict[str, Any]) -> Dict[str, Any]:
    evidence_id = str(resolution.get("evidence_id") or "UNKNOWN")
    case_id = str(resolution.get("case_id") or "UNKNOWN")
    canonical_url = str(resolution.get("canonical_url") or "")
    source_type = str(resolution.get("canonical_source_type") or "unknown")
    lineage = str(resolution.get("canonical_lineage") or "unknown")
    resolution_hash = str(resolution.get("resolution_hash") or "")

    return {
        "evidence_id": evidence_id,
        "case_id": case_id,
        "url": canonical_url,
        "source_type": source_type,
        "verification_status": "verified_for_approval_review",
        "canonical_lineage": lineage,
        "resolution_hash": resolution_hash,
        "content_hash": str(resolution.get("content_hash") or ""),
        "snapshot_required": bool(resolution.get("snapshot_required", True)),
        "snapshot_sealed": bool(resolution.get("snapshot_sealed", False)),
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "notes": (
            "Canonical injectable EvidenceObject candidate. It is not approved, "
            "not public-ready, not institutional-ready, and not report-ready."
        ),
    }


def _build_record_from_resolution(resolution: Dict[str, Any]) -> CanonicalEvidenceInjectionRecord:
    evidence_id = str(resolution.get("evidence_id") or "UNKNOWN")
    case_id = str(resolution.get("case_id") or "UNKNOWN")
    canonical_url = str(resolution.get("canonical_url") or "")
    canonical_source_type = str(resolution.get("canonical_source_type") or "unknown")
    canonical_lineage = str(resolution.get("canonical_lineage") or "unknown")
    resolution_hash = str(resolution.get("resolution_hash") or "")
    resolution_status = str(resolution.get("resolution_status") or "")

    if resolution_status != "resolution_candidate":
        status = "injection_blocked_missing_resolution"
    elif not _is_nonempty_url(canonical_url):
        status = "injection_blocked_invalid_url"
    else:
        status = "injection_candidate"

    evidence_object = _build_evidence_object(resolution)

    material = json.dumps(
        {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "injection_status": status,
            "canonical_evidence_object": evidence_object,
            "resolution_hash": resolution_hash,
            "injection_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    injection_hash = _sha256_text(material)

    record = CanonicalEvidenceInjectionRecord(
        injection_id=f"INJECT_{evidence_id}_{injection_hash[:16]}",
        evidence_id=evidence_id,
        case_id=case_id,
        injection_status=status,
        canonical_evidence_object=evidence_object,
        canonical_url=canonical_url,
        canonical_source_type=canonical_source_type,
        canonical_lineage=canonical_lineage,
        resolution_hash=resolution_hash,
        injection_hash=injection_hash,
        injection_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Injection candidate only. No case graph mutation, evidence approval, "
            "public release, institutional release, or final report mutation occurred."
        ),
    )

    validate_record(record)
    return record


def build_canonical_evidence_injection(
    evidence_id: Optional[str] = None,
    resolution_status_path: Path = DEFAULT_RESOLUTION_STATUS,
) -> Dict[str, Any]:
    resolution_records = _load_resolution_records(resolution_status_path)

    if evidence_id:
        resolution_records = [
            record for record in resolution_records
            if record.get("evidence_id") == evidence_id
        ]

    records: List[CanonicalEvidenceInjectionRecord] = []

    if not resolution_records:
        material = json.dumps(
            {
                "evidence_id": evidence_id or "ALL",
                "injection_status": "injection_blocked_missing_resolution",
                "injection_applied": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        injection_hash = _sha256_text(material)

        record = CanonicalEvidenceInjectionRecord(
            injection_id=f"INJECT_{evidence_id or 'ALL'}_{injection_hash[:16]}",
            evidence_id=evidence_id or "ALL",
            case_id="UNKNOWN",
            injection_status="injection_blocked_missing_resolution",
            canonical_evidence_object={},
            canonical_url="",
            canonical_source_type="unknown",
            canonical_lineage="unknown",
            resolution_hash="",
            injection_hash=injection_hash,
            injection_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="Resolution proof is missing; no injectable EvidenceObject can be produced.",
        )
        validate_record(record)
        records.append(record)
    else:
        for resolution in resolution_records:
            records.append(_build_record_from_resolution(resolution))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    injection_root = (
        _sha256_text("|".join(record.injection_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "injection_record_count": len(records),
        "injection_candidate_count": sum(
            1 for record in records if record.injection_status == "injection_candidate"
        ),
        "injection_blocked_missing_resolution_count": sum(
            1 for record in records if record.injection_status == "injection_blocked_missing_resolution"
        ),
        "injection_blocked_unresolved_snapshot_count": sum(
            1 for record in records if record.injection_status == "injection_blocked_unresolved_snapshot"
        ),
        "injection_blocked_invalid_url_count": sum(
            1 for record in records if record.injection_status == "injection_blocked_invalid_url"
        ),
        "injection_invalid_count": sum(
            1 for record in records if record.injection_status == "injection_invalid"
        ),
        "injection_root": injection_root,
        "injection_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}