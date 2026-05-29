#!/usr/bin/env python3
"""
Signature Authority Engine v1.

Builds deterministic signature-authority candidates from public anchor outputs.

This lane does not certify, sign with real keys, publish externally, approve
evidence, or mark public/institutional/report readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_PUBLIC_ANCHOR_STATUS = Path(
    "outputs/public_anchor_engine/public_anchor_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/signature_authority")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "signature_authority_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "signature_authority_summary.json"
AUTHORITY_OUTPUT = DEFAULT_OUTPUT_DIR / "authority_certificate.json"

FORBIDDEN_TRUE_FLAGS = (
    "certified",
    "authority_applied",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_AUTHORITY_STATUSES = {
    "SIGNATURE_AUTHORITY_CANDIDATE",
    "BLOCKED_MISSING_PUBLIC_ANCHOR",
    "BLOCKED_INVALID_PUBLIC_ANCHOR",
    "SIGNATURE_AUTHORITY_INVALID",
}


@dataclass
class SignatureAuthorityRecord:
    authority_id: str
    authority_status: str
    public_anchor_root: str
    public_anchor_receipt_hash: str
    certificate_hash: str
    certificate_signature_hash: str
    authority_hash: str
    authority_signature_hash: str
    certificate_authority_root: str
    certified: bool
    authority_applied: bool
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


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    if not isinstance(payload, dict):
        return []

    records = payload.get("records", [])
    return records if isinstance(records, list) else []


def _first_record(path: Path) -> Dict[str, Any]:
    records = _load_records(path)
    return records[0] if records else {}


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "authority_id",
        "authority_status",
        "public_anchor_root",
        "public_anchor_receipt_hash",
        "certificate_hash",
        "certificate_signature_hash",
        "authority_hash",
        "authority_signature_hash",
        "certificate_authority_root",
        "certified",
        "authority_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"SignatureAuthorityRecord missing fields: {sorted(missing)}")

    if data["authority_status"] not in ALLOWED_AUTHORITY_STATUSES:
        raise ValueError(f"Unsupported authority_status: {data['authority_status']}")

    if data["authority_status"] == "SIGNATURE_AUTHORITY_CANDIDATE":
        for key in (
            "public_anchor_root",
            "public_anchor_receipt_hash",
            "certificate_hash",
            "certificate_signature_hash",
            "authority_hash",
            "authority_signature_hash",
            "certificate_authority_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(
                    f"{key} must be a non-zero hash for SIGNATURE_AUTHORITY_CANDIDATE"
                )

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_signature_authority(
    public_anchor_status_path: Path = DEFAULT_PUBLIC_ANCHOR_STATUS,
) -> Dict[str, Any]:
    public_anchor_record = _first_record(public_anchor_status_path)

    if not public_anchor_record:
        status = "BLOCKED_MISSING_PUBLIC_ANCHOR"
    elif public_anchor_record.get("public_anchor_status") != "PUBLIC_ANCHOR_CANDIDATE":
        status = "BLOCKED_INVALID_PUBLIC_ANCHOR"
    else:
        status = "SIGNATURE_AUTHORITY_CANDIDATE"

    public_anchor_root = str(public_anchor_record.get("public_anchor_root") or "")
    public_anchor_receipt_hash = str(
        public_anchor_record.get("public_anchor_receipt_hash") or ""
    )
    certificate_hash = str(public_anchor_record.get("certificate_hash") or "")
    certificate_signature_hash = str(
        public_anchor_record.get("certificate_signature_hash") or ""
    )

    authority_material = {
        "authority_version": "signature_authority_v1",
        "authority_status": status,
        "authority_kind": "deterministic_local_authority_candidate",
        "public_anchor_root": public_anchor_root,
        "public_anchor_receipt_hash": public_anchor_receipt_hash,
        "certificate_hash": certificate_hash,
        "certificate_signature_hash": certificate_signature_hash,
        "certified": False,
        "authority_applied": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    authority_hash = _hash_json(authority_material)

    signature_material = {
        "signature_version": "authority_signature_candidate_v1",
        "authority_hash": authority_hash,
        "certificate_hash": certificate_hash,
        "public_anchor_root": public_anchor_root,
        "certified": False,
    }

    authority_signature_hash = _hash_json(signature_material)

    certificate_authority_root = _hash_json(
        {
            "certificate_hash": certificate_hash,
            "certificate_signature_hash": certificate_signature_hash,
            "authority_hash": authority_hash,
            "authority_signature_hash": authority_signature_hash,
            "public_anchor_root": public_anchor_root,
        }
    )

    record = SignatureAuthorityRecord(
        authority_id=f"SIGNATURE_AUTHORITY_{certificate_authority_root[:16]}",
        authority_status=status,
        public_anchor_root=public_anchor_root,
        public_anchor_receipt_hash=public_anchor_receipt_hash,
        certificate_hash=certificate_hash,
        certificate_signature_hash=certificate_signature_hash,
        authority_hash=authority_hash,
        authority_signature_hash=authority_signature_hash,
        certificate_authority_root=certificate_authority_root,
        certified=False,
        authority_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Signature authority candidate only. No real key signing, certification, "
            "approval, public release, institutional release, or report readiness "
            "mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    authority_certificate = {
        "authority_certificate_version": "signature_authority_certificate_v1",
        "authority_id": record.authority_id,
        "authority_status": status,
        "certificate_hash": certificate_hash,
        "certificate_signature_hash": certificate_signature_hash,
        "authority_hash": authority_hash,
        "authority_signature_hash": authority_signature_hash,
        "certificate_authority_root": certificate_authority_root,
        "certified": False,
        "authority_applied": False,
    }

    summary = {
        "authority_record_count": 1,
        "authority_candidate_count": 1 if status == "SIGNATURE_AUTHORITY_CANDIDATE" else 0,
        "authority_blocked_missing_public_anchor_count": (
            1 if status == "BLOCKED_MISSING_PUBLIC_ANCHOR" else 0
        ),
        "authority_blocked_invalid_public_anchor_count": (
            1 if status == "BLOCKED_INVALID_PUBLIC_ANCHOR" else 0
        ),
        "authority_invalid_count": 1 if status == "SIGNATURE_AUTHORITY_INVALID" else 0,
        "authority_status": status,
        "authority_hash": authority_hash,
        "authority_signature_hash": authority_signature_hash,
        "certificate_authority_root": certificate_authority_root,
        "certified": False,
        "authority_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(AUTHORITY_OUTPUT, authority_certificate)

    return {
        "payload": payload,
        "summary": summary,
        "authority_certificate": authority_certificate,
    }