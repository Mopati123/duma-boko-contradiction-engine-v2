#!/usr/bin/env python3
"""
Anchor Verification Engine v1.

Verifies deterministic anchor publication artifacts against governance anchor
bundle outputs.

This lane does not publish externally, approve evidence, or mark public,
institutional, or report readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_PUBLICATION_STATUS = Path(
    "outputs/anchor_publication/anchor_publication_status.json"
)
DEFAULT_PUBLICATION_RECEIPT = Path(
    "outputs/anchor_publication/publication_receipt.json"
)
DEFAULT_PUBLICATION_VERIFICATION = Path(
    "outputs/anchor_publication/publication_verification.json"
)
DEFAULT_ANCHOR_BUNDLE_STATUS = Path(
    "outputs/governance_anchor_bundle/governance_anchor_bundle_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/anchor_verification_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "anchor_verification_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "anchor_verification_summary.json"
RECEIPT_OUTPUT = DEFAULT_OUTPUT_DIR / "anchor_verification_receipt.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "verification_applied",
)

ALLOWED_VERIFICATION_STATUSES = {
    "VERIFIED",
    "FAILED",
    "BLOCKED_MISSING_PUBLICATION",
    "BLOCKED_MISSING_ANCHOR_BUNDLE",
}


@dataclass
class AnchorVerificationRecord:
    verification_id: str
    verification_status: str
    publication_root: str
    anchor_bundle_root: str
    receipt_hash: str
    verification_hash: str
    verification_root: str
    publication_verified: bool
    anchor_verified: bool
    receipt_verified: bool
    integrity_verified: bool
    verification_applied: bool
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


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "verification_id",
        "verification_status",
        "publication_root",
        "anchor_bundle_root",
        "receipt_hash",
        "verification_hash",
        "verification_root",
        "publication_verified",
        "anchor_verified",
        "receipt_verified",
        "integrity_verified",
        "verification_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"AnchorVerificationRecord missing fields: {sorted(missing)}")

    if data["verification_status"] not in ALLOWED_VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {data['verification_status']}")

    if data["verification_status"] == "VERIFIED":
        for key in (
            "publication_root",
            "anchor_bundle_root",
            "receipt_hash",
            "verification_hash",
            "verification_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for VERIFIED")

        for key in (
            "publication_verified",
            "anchor_verified",
            "receipt_verified",
            "integrity_verified",
        ):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for VERIFIED")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_anchor_verification(
    expected_publication_root: Optional[str] = None,
    expected_receipt_hash: Optional[str] = None,
    publication_status_path: Path = DEFAULT_PUBLICATION_STATUS,
    publication_receipt_path: Path = DEFAULT_PUBLICATION_RECEIPT,
    publication_verification_path: Path = DEFAULT_PUBLICATION_VERIFICATION,
    anchor_bundle_status_path: Path = DEFAULT_ANCHOR_BUNDLE_STATUS,
) -> Dict[str, Any]:
    publication_record = _first_record(publication_status_path)
    anchor_record = _first_record(anchor_bundle_status_path)

    receipt = _load_json(publication_receipt_path) if publication_receipt_path.exists() else {}
    verification = (
        _load_json(publication_verification_path)
        if publication_verification_path.exists()
        else {}
    )

    if not publication_record:
        status = "BLOCKED_MISSING_PUBLICATION"
    elif not anchor_record:
        status = "BLOCKED_MISSING_ANCHOR_BUNDLE"
    else:
        publication_root = str(publication_record.get("publication_root") or "")
        anchor_bundle_root = str(publication_record.get("anchor_bundle_root") or "")
        receipt_hash = str(publication_record.get("receipt_hash") or "")
        verification_hash = str(publication_record.get("verification_hash") or "")

        publication_verified = (
            publication_record.get("publication_status") == "publication_candidate"
            and _is_nonzero_hash(publication_root)
            and (
                expected_publication_root is None
                or expected_publication_root == publication_root
            )
        )

        anchor_verified = (
            anchor_record.get("bundle_status") == "anchor_bundle_candidate"
            and anchor_record.get("anchor_bundle_root") == anchor_bundle_root
            and _is_nonzero_hash(anchor_bundle_root)
        )

        recomputed_receipt_hash = _hash_json(receipt) if isinstance(receipt, dict) else ""
        receipt_verified = (
            _is_nonzero_hash(receipt_hash)
            and recomputed_receipt_hash == receipt_hash
            and (
                expected_receipt_hash is None
                or expected_receipt_hash == receipt_hash
            )
        )

        recomputed_verification_hash = (
            _hash_json(verification) if isinstance(verification, dict) else ""
        )
        verification_verified = (
            _is_nonzero_hash(verification_hash)
            and recomputed_verification_hash == verification_hash
        )

        integrity_verified = (
            publication_verified
            and anchor_verified
            and receipt_verified
            and verification_verified
        )

        status = "VERIFIED" if integrity_verified else "FAILED"

    publication_root = str(publication_record.get("publication_root") or "")
    anchor_bundle_root = str(publication_record.get("anchor_bundle_root") or "")
    receipt_hash = str(publication_record.get("receipt_hash") or "")
    verification_hash = str(publication_record.get("verification_hash") or "")

    publication_verified = status == "VERIFIED" or (
        bool(publication_record)
        and publication_record.get("publication_status") == "publication_candidate"
        and _is_nonzero_hash(publication_root)
        and (expected_publication_root is None or expected_publication_root == publication_root)
    )

    anchor_verified = status == "VERIFIED" or (
        bool(anchor_record)
        and anchor_record.get("bundle_status") == "anchor_bundle_candidate"
        and anchor_record.get("anchor_bundle_root") == anchor_bundle_root
        and _is_nonzero_hash(anchor_bundle_root)
    )

    recomputed_receipt_hash = _hash_json(receipt) if isinstance(receipt, dict) else ""
    receipt_verified = status == "VERIFIED" or (
        _is_nonzero_hash(receipt_hash)
        and recomputed_receipt_hash == receipt_hash
        and (expected_receipt_hash is None or expected_receipt_hash == receipt_hash)
    )

    recomputed_verification_hash = _hash_json(verification) if isinstance(verification, dict) else ""
    verification_verified = status == "VERIFIED" or (
        _is_nonzero_hash(verification_hash)
        and recomputed_verification_hash == verification_hash
    )

    integrity_verified = (
        publication_verified
        and anchor_verified
        and receipt_verified
        and verification_verified
        and status == "VERIFIED"
    )

    verification_material = {
        "verification_version": "anchor_verification_v1",
        "verification_status": status,
        "publication_root": publication_root,
        "anchor_bundle_root": anchor_bundle_root,
        "receipt_hash": receipt_hash,
        "verification_hash": verification_hash,
        "publication_verified": publication_verified,
        "anchor_verified": anchor_verified,
        "receipt_verified": receipt_verified,
        "integrity_verified": integrity_verified,
        "verification_applied": False,
    }

    verification_root = _hash_json(verification_material)

    record = AnchorVerificationRecord(
        verification_id=f"ANCHOR_VERIFICATION_{verification_root[:16]}",
        verification_status=status,
        publication_root=publication_root,
        anchor_bundle_root=anchor_bundle_root,
        receipt_hash=receipt_hash,
        verification_hash=verification_hash,
        verification_root=verification_root,
        publication_verified=publication_verified,
        anchor_verified=anchor_verified,
        receipt_verified=receipt_verified,
        integrity_verified=integrity_verified,
        verification_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Anchor verification candidate only. No approval, public release, "
            "institutional release, report readiness, or external publication occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "verification_record_count": 1,
        "verification_candidate_count": 1 if status == "VERIFIED" else 0,
        "verification_blocked_missing_publication_count": (
            1 if status == "BLOCKED_MISSING_PUBLICATION" else 0
        ),
        "verification_blocked_missing_anchor_bundle_count": (
            1 if status == "BLOCKED_MISSING_ANCHOR_BUNDLE" else 0
        ),
        "verification_blocked_invalid_publication_count": (
            1 if status == "FAILED" and not publication_verified else 0
        ),
        "verification_blocked_invalid_anchor_bundle_count": (
            1 if status == "FAILED" and not anchor_verified else 0
        ),
        "verification_invalid_count": 1 if status == "FAILED" else 0,
        "publication_verified": publication_verified,
        "anchor_verified": anchor_verified,
        "receipt_verified": receipt_verified,
        "integrity_verified": integrity_verified,
        "verification_root": verification_root,
        "verification_applied": False,
        "verification_status": status,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    receipt_payload = {
        "receipt_version": "anchor_verification_receipt_v1",
        "verification_root": verification_root,
        "verification_status": status,
        "publication_root": publication_root,
        "anchor_bundle_root": anchor_bundle_root,
        "receipt_hash": receipt_hash,
        "verification_hash": verification_hash,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(RECEIPT_OUTPUT, receipt_payload)

    return {
        "payload": payload,
        "summary": summary,
        "receipt": receipt_payload,
    }