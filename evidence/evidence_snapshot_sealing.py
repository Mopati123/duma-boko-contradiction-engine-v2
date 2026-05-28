#!/usr/bin/env python3
"""
Evidence Snapshot Sealing Engine v1.

Builds deterministic snapshot-seal candidates from canonical injectable
EvidenceObject records.

This lane does not fetch live network content. It creates seal candidates using
deterministic canonical material already present in the injected evidence object.
A future networked acquisition lane can replace the snapshot payload with real
fetched content while preserving the same seal contract.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_INJECTION_STATUS = Path(
    "outputs/canonical_evidence_injection/canonical_evidence_injection_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/evidence_snapshot_sealing")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_snapshot_sealing_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_snapshot_sealing_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "seal_applied",
)

ALLOWED_SEAL_STATUSES = {
    "snapshot_seal_candidate",
    "snapshot_blocked_missing_injection",
    "snapshot_blocked_invalid_evidence_object",
    "snapshot_invalid",
}


@dataclass
class EvidenceSnapshotSealRecord:
    seal_id: str
    evidence_id: str
    case_id: str
    seal_status: str
    canonical_url: str
    canonical_source_type: str
    injection_hash: str
    snapshot_material_hash: str
    content_hash: str
    snapshot_sealed: bool
    seal_applied: bool
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


def _load_injection_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "seal_id",
        "evidence_id",
        "case_id",
        "seal_status",
        "canonical_url",
        "canonical_source_type",
        "injection_hash",
        "snapshot_material_hash",
        "content_hash",
        "snapshot_sealed",
        "seal_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"EvidenceSnapshotSealRecord missing fields: {sorted(missing)}")

    if data["seal_status"] not in ALLOWED_SEAL_STATUSES:
        raise ValueError(f"Unsupported seal_status: {data['seal_status']}")

    if data["seal_status"] == "snapshot_seal_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")
        if not data["content_hash"]:
            raise ValueError("content_hash must be non-empty for snapshot_seal_candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_record_from_injection(injection: Dict[str, Any]) -> EvidenceSnapshotSealRecord:
    evidence_object = injection.get("canonical_evidence_object") or {}
    evidence_id = str(injection.get("evidence_id") or evidence_object.get("evidence_id") or "UNKNOWN")
    case_id = str(injection.get("case_id") or evidence_object.get("case_id") or "UNKNOWN")
    canonical_url = str(injection.get("canonical_url") or evidence_object.get("url") or "")
    canonical_source_type = str(
        injection.get("canonical_source_type")
        or evidence_object.get("source_type")
        or "unknown"
    )
    injection_hash = str(injection.get("injection_hash") or "")

    if (
        injection.get("injection_status") != "injection_candidate"
        or not isinstance(evidence_object, dict)
        or not _is_nonempty_url(evidence_object.get("url"))
    ):
        status = "snapshot_blocked_invalid_evidence_object"
        snapshot_material_hash = ""
        content_hash = ""
        snapshot_sealed = False
    else:
        status = "snapshot_seal_candidate"
        snapshot_material = {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "url": canonical_url,
            "source_type": canonical_source_type,
            "verification_status": evidence_object.get("verification_status"),
            "canonical_lineage": evidence_object.get("canonical_lineage"),
            "resolution_hash": evidence_object.get("resolution_hash"),
            "injection_hash": injection_hash,
        }

        snapshot_material_text = json.dumps(
            snapshot_material,
            sort_keys=True,
            separators=(",", ":"),
        )

        snapshot_material_hash = _sha256_text(snapshot_material_text)
        content_hash = _sha256_text(
            json.dumps(
                {
                    "snapshot_type": "deterministic_canonical_metadata_snapshot",
                    "snapshot_material_hash": snapshot_material_hash,
                    "snapshot_material": snapshot_material,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        snapshot_sealed = True

    seal_material = json.dumps(
        {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "seal_status": status,
            "canonical_url": canonical_url,
            "canonical_source_type": canonical_source_type,
            "injection_hash": injection_hash,
            "snapshot_material_hash": snapshot_material_hash,
            "content_hash": content_hash,
            "snapshot_sealed": snapshot_sealed,
            "seal_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    seal_hash = _sha256_text(seal_material)

    record = EvidenceSnapshotSealRecord(
        seal_id=f"SNAPSHOT_SEAL_{evidence_id}_{seal_hash[:16]}",
        evidence_id=evidence_id,
        case_id=case_id,
        seal_status=status,
        canonical_url=canonical_url,
        canonical_source_type=canonical_source_type,
        injection_hash=injection_hash,
        snapshot_material_hash=snapshot_material_hash,
        content_hash=content_hash,
        snapshot_sealed=snapshot_sealed,
        seal_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Snapshot seal candidate generated from deterministic canonical metadata. "
            "No live network fetch, approval, public release, institutional release, "
            "or final report mutation occurred."
        ),
    )

    validate_record(record)
    return record


def build_evidence_snapshot_sealing(
    evidence_id: Optional[str] = None,
    injection_status_path: Path = DEFAULT_INJECTION_STATUS,
) -> Dict[str, Any]:
    injection_records = _load_injection_records(injection_status_path)

    if evidence_id:
        injection_records = [
            record for record in injection_records
            if record.get("evidence_id") == evidence_id
        ]

    records: List[EvidenceSnapshotSealRecord] = []

    if not injection_records:
        material = json.dumps(
            {
                "evidence_id": evidence_id or "ALL",
                "seal_status": "snapshot_blocked_missing_injection",
                "snapshot_sealed": False,
                "seal_applied": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        seal_hash = _sha256_text(material)

        record = EvidenceSnapshotSealRecord(
            seal_id=f"SNAPSHOT_SEAL_{evidence_id or 'ALL'}_{seal_hash[:16]}",
            evidence_id=evidence_id or "ALL",
            case_id="UNKNOWN",
            seal_status="snapshot_blocked_missing_injection",
            canonical_url="",
            canonical_source_type="unknown",
            injection_hash="",
            snapshot_material_hash="",
            content_hash="",
            snapshot_sealed=False,
            seal_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="Injection proof is missing; snapshot cannot be sealed.",
        )
        validate_record(record)
        records.append(record)
    else:
        for injection in injection_records:
            records.append(_build_record_from_injection(injection))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    snapshot_root = (
        _sha256_text("|".join(record.content_hash for record in records if record.content_hash))
        if any(record.content_hash for record in records)
        else "0" * 64
    )

    summary = {
        "snapshot_record_count": len(records),
        "snapshot_seal_candidate_count": sum(
            1 for record in records if record.seal_status == "snapshot_seal_candidate"
        ),
        "snapshot_blocked_missing_injection_count": sum(
            1 for record in records if record.seal_status == "snapshot_blocked_missing_injection"
        ),
        "snapshot_blocked_invalid_evidence_object_count": sum(
            1 for record in records if record.seal_status == "snapshot_blocked_invalid_evidence_object"
        ),
        "snapshot_invalid_count": sum(
            1 for record in records if record.seal_status == "snapshot_invalid"
        ),
        "snapshot_sealed_count": sum(1 for record in records if record.snapshot_sealed),
        "snapshot_root": snapshot_root,
        "seal_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}