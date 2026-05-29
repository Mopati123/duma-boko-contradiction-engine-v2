#!/usr/bin/env python3
"""
Replay Certification Engine v1.

Builds deterministic replay certification candidates from the authority,
public anchor, certificate, and verification layers.

This lane does not certify, publish, approve evidence, or mark public,
institutional, or report readiness. It proves deterministic replay agreement
over already-emitted chain roots.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_AUTHORITY_STATUS = Path("outputs/signature_authority/signature_authority_status.json")
DEFAULT_PUBLIC_ANCHOR_STATUS = Path("outputs/public_anchor_engine/public_anchor_status.json")
DEFAULT_CERTIFICATE_STATUS = Path("outputs/verification_certificate/verification_certificate_status.json")
DEFAULT_VERIFICATION_STATUS = Path("outputs/anchor_verification_engine/anchor_verification_status.json")

DEFAULT_OUTPUT_DIR = Path("outputs/replay_certification")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "replay_certification_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "replay_certification_summary.json"
REPLAY_RECEIPT_OUTPUT = DEFAULT_OUTPUT_DIR / "replay_certification_receipt.json"

FORBIDDEN_TRUE_FLAGS = (
    "certified",
    "replay_applied",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_REPLAY_STATUSES = {
    "REPLAY_CERTIFICATION_CANDIDATE",
    "BLOCKED_MISSING_AUTHORITY",
    "BLOCKED_MISSING_PUBLIC_ANCHOR",
    "BLOCKED_MISSING_CERTIFICATE",
    "BLOCKED_MISSING_VERIFICATION",
    "BLOCKED_INVALID_AUTHORITY",
    "BLOCKED_INVALID_PUBLIC_ANCHOR",
    "BLOCKED_INVALID_CERTIFICATE",
    "BLOCKED_INVALID_VERIFICATION",
    "REPLAY_CERTIFICATION_INVALID",
}


@dataclass
class ReplayCertificationRecord:
    replay_id: str
    replay_status: str
    authority_hash: str
    authority_signature_hash: str
    certificate_authority_root: str
    public_anchor_root: str
    certificate_hash: str
    verification_root: str
    replay_input_hash: str
    replay_output_hash: str
    replay_root: str
    replay_verified: bool
    certified: bool
    replay_applied: bool
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


def _determine_status(
    authority_record: Dict[str, Any],
    public_anchor_record: Dict[str, Any],
    certificate_record: Dict[str, Any],
    verification_record: Dict[str, Any],
) -> str:
    if not authority_record:
        return "BLOCKED_MISSING_AUTHORITY"
    if not public_anchor_record:
        return "BLOCKED_MISSING_PUBLIC_ANCHOR"
    if not certificate_record:
        return "BLOCKED_MISSING_CERTIFICATE"
    if not verification_record:
        return "BLOCKED_MISSING_VERIFICATION"

    if authority_record.get("authority_status") != "SIGNATURE_AUTHORITY_CANDIDATE":
        return "BLOCKED_INVALID_AUTHORITY"
    if public_anchor_record.get("public_anchor_status") != "PUBLIC_ANCHOR_CANDIDATE":
        return "BLOCKED_INVALID_PUBLIC_ANCHOR"
    if certificate_record.get("certificate_status") != "CERTIFIABLE":
        return "BLOCKED_INVALID_CERTIFICATE"
    if verification_record.get("verification_status") != "VERIFIED":
        return "BLOCKED_INVALID_VERIFICATION"

    expected_pairs = (
        (
            authority_record.get("public_anchor_root"),
            public_anchor_record.get("public_anchor_root"),
            "BLOCKED_INVALID_AUTHORITY",
        ),
        (
            authority_record.get("certificate_hash"),
            certificate_record.get("certificate_hash"),
            "BLOCKED_INVALID_AUTHORITY",
        ),
        (
            public_anchor_record.get("certificate_hash"),
            certificate_record.get("certificate_hash"),
            "BLOCKED_INVALID_PUBLIC_ANCHOR",
        ),
        (
            certificate_record.get("verification_root"),
            verification_record.get("verification_root"),
            "BLOCKED_INVALID_CERTIFICATE",
        ),
    )

    for left, right, failure in expected_pairs:
        if left != right or not _is_nonzero_hash(left):
            return failure

    return "REPLAY_CERTIFICATION_CANDIDATE"


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "replay_id",
        "replay_status",
        "authority_hash",
        "authority_signature_hash",
        "certificate_authority_root",
        "public_anchor_root",
        "certificate_hash",
        "verification_root",
        "replay_input_hash",
        "replay_output_hash",
        "replay_root",
        "replay_verified",
        "certified",
        "replay_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ReplayCertificationRecord missing fields: {sorted(missing)}")

    if data["replay_status"] not in ALLOWED_REPLAY_STATUSES:
        raise ValueError(f"Unsupported replay_status: {data['replay_status']}")

    if data["replay_status"] == "REPLAY_CERTIFICATION_CANDIDATE":
        for key in (
            "authority_hash",
            "authority_signature_hash",
            "certificate_authority_root",
            "public_anchor_root",
            "certificate_hash",
            "verification_root",
            "replay_input_hash",
            "replay_output_hash",
            "replay_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for replay candidate")

        if data["replay_verified"] is not True:
            raise ValueError("replay_verified must be true for replay candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_replay_certification(
    authority_status_path: Path = DEFAULT_AUTHORITY_STATUS,
    public_anchor_status_path: Path = DEFAULT_PUBLIC_ANCHOR_STATUS,
    certificate_status_path: Path = DEFAULT_CERTIFICATE_STATUS,
    verification_status_path: Path = DEFAULT_VERIFICATION_STATUS,
) -> Dict[str, Any]:
    authority_record = _first_record(authority_status_path)
    public_anchor_record = _first_record(public_anchor_status_path)
    certificate_record = _first_record(certificate_status_path)
    verification_record = _first_record(verification_status_path)

    status = _determine_status(
        authority_record,
        public_anchor_record,
        certificate_record,
        verification_record,
    )

    authority_hash = str(authority_record.get("authority_hash") or "")
    authority_signature_hash = str(authority_record.get("authority_signature_hash") or "")
    certificate_authority_root = str(authority_record.get("certificate_authority_root") or "")
    public_anchor_root = str(public_anchor_record.get("public_anchor_root") or "")
    certificate_hash = str(certificate_record.get("certificate_hash") or "")
    verification_root = str(verification_record.get("verification_root") or "")

    replay_input = {
        "authority_hash": authority_hash,
        "authority_signature_hash": authority_signature_hash,
        "certificate_authority_root": certificate_authority_root,
        "public_anchor_root": public_anchor_root,
        "certificate_hash": certificate_hash,
        "verification_root": verification_root,
    }

    replay_input_hash = _hash_json(replay_input)

    replay_output = {
        "replay_status": status,
        "replay_input_hash": replay_input_hash,
        "authority_status": authority_record.get("authority_status"),
        "public_anchor_status": public_anchor_record.get("public_anchor_status"),
        "certificate_status": certificate_record.get("certificate_status"),
        "verification_status": verification_record.get("verification_status"),
        "certified": False,
        "replay_applied": False,
    }

    replay_output_hash = _hash_json(replay_output)
    replay_verified = status == "REPLAY_CERTIFICATION_CANDIDATE"

    replay_root = _hash_json(
        {
            "replay_input_hash": replay_input_hash,
            "replay_output_hash": replay_output_hash,
            "replay_verified": replay_verified,
        }
    )

    record = ReplayCertificationRecord(
        replay_id=f"REPLAY_CERTIFICATION_{replay_root[:16]}",
        replay_status=status,
        authority_hash=authority_hash,
        authority_signature_hash=authority_signature_hash,
        certificate_authority_root=certificate_authority_root,
        public_anchor_root=public_anchor_root,
        certificate_hash=certificate_hash,
        verification_root=verification_root,
        replay_input_hash=replay_input_hash,
        replay_output_hash=replay_output_hash,
        replay_root=replay_root,
        replay_verified=replay_verified,
        certified=False,
        replay_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Replay certification candidate only. No certification, approval, "
            "public release, institutional release, or report readiness mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "replay_record_count": 1,
        "replay_candidate_count": 1 if status == "REPLAY_CERTIFICATION_CANDIDATE" else 0,
        "replay_blocked_missing_authority_count": (
            1 if status == "BLOCKED_MISSING_AUTHORITY" else 0
        ),
        "replay_blocked_missing_public_anchor_count": (
            1 if status == "BLOCKED_MISSING_PUBLIC_ANCHOR" else 0
        ),
        "replay_blocked_missing_certificate_count": (
            1 if status == "BLOCKED_MISSING_CERTIFICATE" else 0
        ),
        "replay_blocked_missing_verification_count": (
            1 if status == "BLOCKED_MISSING_VERIFICATION" else 0
        ),
        "replay_blocked_invalid_authority_count": (
            1 if status == "BLOCKED_INVALID_AUTHORITY" else 0
        ),
        "replay_blocked_invalid_public_anchor_count": (
            1 if status == "BLOCKED_INVALID_PUBLIC_ANCHOR" else 0
        ),
        "replay_blocked_invalid_certificate_count": (
            1 if status == "BLOCKED_INVALID_CERTIFICATE" else 0
        ),
        "replay_blocked_invalid_verification_count": (
            1 if status == "BLOCKED_INVALID_VERIFICATION" else 0
        ),
        "replay_invalid_count": 1 if status == "REPLAY_CERTIFICATION_INVALID" else 0,
        "replay_status": status,
        "replay_verified": replay_verified,
        "replay_input_hash": replay_input_hash,
        "replay_output_hash": replay_output_hash,
        "replay_root": replay_root,
        "certified": False,
        "replay_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    replay_receipt = {
        "receipt_version": "replay_certification_receipt_v1",
        "replay_status": status,
        "replay_verified": replay_verified,
        "replay_input_hash": replay_input_hash,
        "replay_output_hash": replay_output_hash,
        "replay_root": replay_root,
        "certified": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(REPLAY_RECEIPT_OUTPUT, replay_receipt)

    return {
        "payload": payload,
        "summary": summary,
        "replay_receipt": replay_receipt,
    }