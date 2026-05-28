#!/usr/bin/env python3
"""
Canonical Evidence Resolution Engine v1.

Converts canonical URL closure records into deterministic resolution candidates.

This lane does not fetch network content, approve evidence, publish evidence, or
mark report readiness. It proves which evidence URLs are ready for future
snapshot sealing and which remain blocked.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_URL_CLOSURE_STATUS = Path(
    "outputs/canonical_evidence_url_closure/canonical_evidence_url_closure_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/canonical_evidence_resolution")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_resolution_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_resolution_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "resolution_applied",
    "snapshot_sealed",
)

ALLOWED_RESOLUTION_STATUSES = {
    "resolution_candidate",
    "resolution_blocked_missing_url_closure",
    "resolution_blocked_invalid_url",
    "resolution_invalid",
}


@dataclass
class CanonicalEvidenceResolutionRecord:
    resolution_id: str
    evidence_id: str
    case_id: str
    resolution_status: str
    canonical_url: str
    canonical_source_type: str
    canonical_lineage: str
    url_closure_provenance_hash: str
    resolution_hash: str
    content_hash: str
    snapshot_required: bool
    snapshot_sealed: bool
    resolution_applied: bool
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


def _load_url_closure_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "resolution_id",
        "evidence_id",
        "case_id",
        "resolution_status",
        "canonical_url",
        "canonical_source_type",
        "canonical_lineage",
        "url_closure_provenance_hash",
        "resolution_hash",
        "content_hash",
        "snapshot_required",
        "snapshot_sealed",
        "resolution_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CanonicalEvidenceResolutionRecord missing fields: {sorted(missing)}")

    if data["resolution_status"] not in ALLOWED_RESOLUTION_STATUSES:
        raise ValueError(f"Unsupported resolution_status: {data['resolution_status']}")

    if data["resolution_status"] == "resolution_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")

    if data["snapshot_required"] is not True:
        raise ValueError("snapshot_required must remain true")


def _build_record_from_closure(closure: Dict[str, Any]) -> CanonicalEvidenceResolutionRecord:
    evidence_id = str(closure.get("evidence_id") or "UNKNOWN")
    case_id = str(closure.get("case_id") or "UNKNOWN")
    canonical_url = str(closure.get("canonical_url") or "")
    canonical_source_type = str(closure.get("canonical_source_type") or "unknown")
    canonical_lineage = str(closure.get("canonical_lineage") or "unknown")
    closure_hash = str(closure.get("provenance_hash") or "")

    if not _is_nonempty_url(canonical_url):
        status = "resolution_blocked_invalid_url"
    else:
        status = "resolution_candidate"

    material = json.dumps(
        {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "resolution_status": status,
            "canonical_url": canonical_url,
            "canonical_source_type": canonical_source_type,
            "canonical_lineage": canonical_lineage,
            "url_closure_provenance_hash": closure_hash,
            "content_hash": "",
            "snapshot_required": True,
            "snapshot_sealed": False,
            "resolution_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    resolution_hash = _sha256_text(material)

    record = CanonicalEvidenceResolutionRecord(
        resolution_id=f"RESOLVE_{evidence_id}_{resolution_hash[:16]}",
        evidence_id=evidence_id,
        case_id=case_id,
        resolution_status=status,
        canonical_url=canonical_url,
        canonical_source_type=canonical_source_type,
        canonical_lineage=canonical_lineage,
        url_closure_provenance_hash=closure_hash,
        resolution_hash=resolution_hash,
        content_hash="",
        snapshot_required=True,
        snapshot_sealed=False,
        resolution_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Resolution candidate only. Network content has not been fetched, "
            "content_hash is intentionally empty until snapshot sealing, and no "
            "approval/readiness/report mutation occurred."
        ),
    )

    validate_record(record)
    return record


def build_canonical_evidence_resolution(
    evidence_id: Optional[str] = None,
    url_closure_status_path: Path = DEFAULT_URL_CLOSURE_STATUS,
) -> Dict[str, Any]:
    closure_records = _load_url_closure_records(url_closure_status_path)

    if evidence_id:
        closure_records = [
            record for record in closure_records
            if record.get("evidence_id") == evidence_id
        ]

    records: List[CanonicalEvidenceResolutionRecord] = []

    if not closure_records:
        material = json.dumps(
            {
                "evidence_id": evidence_id or "ALL",
                "resolution_status": "resolution_blocked_missing_url_closure",
                "snapshot_required": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        resolution_hash = _sha256_text(material)

        record = CanonicalEvidenceResolutionRecord(
            resolution_id=f"RESOLVE_{evidence_id or 'ALL'}_{resolution_hash[:16]}",
            evidence_id=evidence_id or "ALL",
            case_id="UNKNOWN",
            resolution_status="resolution_blocked_missing_url_closure",
            canonical_url="",
            canonical_source_type="unknown",
            canonical_lineage="unknown",
            url_closure_provenance_hash="",
            resolution_hash=resolution_hash,
            content_hash="",
            snapshot_required=True,
            snapshot_sealed=False,
            resolution_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="URL closure proof is missing; evidence cannot advance to snapshot sealing.",
        )
        validate_record(record)
        records.append(record)
    else:
        for closure in closure_records:
            records.append(_build_record_from_closure(closure))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    resolution_root = (
        _sha256_text("|".join(record.resolution_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "resolution_record_count": len(records),
        "resolution_candidate_count": sum(
            1 for record in records if record.resolution_status == "resolution_candidate"
        ),
        "resolution_blocked_missing_url_closure_count": sum(
            1 for record in records if record.resolution_status == "resolution_blocked_missing_url_closure"
        ),
        "resolution_blocked_invalid_url_count": sum(
            1 for record in records if record.resolution_status == "resolution_blocked_invalid_url"
        ),
        "resolution_invalid_count": sum(
            1 for record in records if record.resolution_status == "resolution_invalid"
        ),
        "snapshot_required_count": sum(1 for record in records if record.snapshot_required),
        "snapshot_sealed_count": sum(1 for record in records if record.snapshot_sealed),
        "resolution_root": resolution_root,
        "resolution_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}