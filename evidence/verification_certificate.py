#!/usr/bin/env python3
"""
Verification Certificate Engine v1.

Builds deterministic certification candidates from anchor verification outputs.

This lane does not certify, publish, approve evidence, or mark public,
institutional, or report readiness. It converts VERIFIED into CERTIFIABLE.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_ANCHOR_VERIFICATION_STATUS = Path(
    "outputs/anchor_verification_engine/anchor_verification_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/verification_certificate")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "verification_certificate_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "verification_certificate_summary.json"
CERTIFICATE_OUTPUT = DEFAULT_OUTPUT_DIR / "certificate.json"

FORBIDDEN_TRUE_FLAGS = (
    "certified",
    "certificate_applied",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_CERTIFICATE_STATUSES = {
    "CERTIFIABLE",
    "BLOCKED_MISSING_VERIFICATION",
    "BLOCKED_UNVERIFIED_CHAIN",
    "CERTIFICATE_INVALID",
}


@dataclass
class VerificationCertificateRecord:
    certificate_id: str
    certificate_status: str
    verification_root: str
    publication_root: str
    anchor_bundle_root: str
    receipt_hash: str
    verification_hash: str
    certificate_hash: str
    certificate_signature_hash: str
    certified: bool
    certificate_applied: bool
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
        "certificate_id",
        "certificate_status",
        "verification_root",
        "publication_root",
        "anchor_bundle_root",
        "receipt_hash",
        "verification_hash",
        "certificate_hash",
        "certificate_signature_hash",
        "certified",
        "certificate_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"VerificationCertificateRecord missing fields: {sorted(missing)}")

    if data["certificate_status"] not in ALLOWED_CERTIFICATE_STATUSES:
        raise ValueError(f"Unsupported certificate_status: {data['certificate_status']}")

    if data["certificate_status"] == "CERTIFIABLE":
        for key in (
            "verification_root",
            "publication_root",
            "anchor_bundle_root",
            "receipt_hash",
            "verification_hash",
            "certificate_hash",
            "certificate_signature_hash",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for CERTIFIABLE")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_verification_certificate(
    anchor_verification_status_path: Path = DEFAULT_ANCHOR_VERIFICATION_STATUS,
) -> Dict[str, Any]:
    verification_record = _first_record(anchor_verification_status_path)

    if not verification_record:
        status = "BLOCKED_MISSING_VERIFICATION"
    elif verification_record.get("verification_status") != "VERIFIED":
        status = "BLOCKED_UNVERIFIED_CHAIN"
    elif not all(
        verification_record.get(key) is True
        for key in (
            "publication_verified",
            "anchor_verified",
            "receipt_verified",
            "integrity_verified",
        )
    ):
        status = "BLOCKED_UNVERIFIED_CHAIN"
    else:
        status = "CERTIFIABLE"

    verification_root = str(verification_record.get("verification_root") or "")
    publication_root = str(verification_record.get("publication_root") or "")
    anchor_bundle_root = str(verification_record.get("anchor_bundle_root") or "")
    receipt_hash = str(verification_record.get("receipt_hash") or "")
    verification_hash = str(verification_record.get("verification_hash") or "")

    certificate = {
        "certificate_version": "verification_certificate_v1",
        "certificate_status": status,
        "verification_root": verification_root,
        "publication_root": publication_root,
        "anchor_bundle_root": anchor_bundle_root,
        "receipt_hash": receipt_hash,
        "verification_hash": verification_hash,
        "certified": False,
        "certificate_applied": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    certificate_hash = _hash_json(certificate)

    signature_material = {
        "signature_type": "deterministic_certificate_signature_candidate_v1",
        "certificate_hash": certificate_hash,
        "verification_root": verification_root,
        "publication_root": publication_root,
        "certified": False,
    }

    certificate_signature_hash = _hash_json(signature_material)

    record = VerificationCertificateRecord(
        certificate_id=f"VERIFICATION_CERTIFICATE_{certificate_hash[:16]}",
        certificate_status=status,
        verification_root=verification_root,
        publication_root=publication_root,
        anchor_bundle_root=anchor_bundle_root,
        receipt_hash=receipt_hash,
        verification_hash=verification_hash,
        certificate_hash=certificate_hash,
        certificate_signature_hash=certificate_signature_hash,
        certified=False,
        certificate_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Verification certificate candidate only. No certification, evidence approval, "
            "public release, institutional release, or report readiness mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "certificate_record_count": 1,
        "certificate_candidate_count": 1 if status == "CERTIFIABLE" else 0,
        "certificate_blocked_missing_verification_count": (
            1 if status == "BLOCKED_MISSING_VERIFICATION" else 0
        ),
        "certificate_blocked_unverified_chain_count": (
            1 if status == "BLOCKED_UNVERIFIED_CHAIN" else 0
        ),
        "certificate_invalid_count": 1 if status == "CERTIFICATE_INVALID" else 0,
        "certificate_status": status,
        "certificate_hash": certificate_hash,
        "certificate_signature_hash": certificate_signature_hash,
        "certified": False,
        "certificate_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CERTIFICATE_OUTPUT, certificate)

    return {
        "payload": payload,
        "summary": summary,
        "certificate": certificate,
    }