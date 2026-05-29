#!/usr/bin/env python3
"""
Public Anchor Engine v1.

Builds deterministic public-anchor candidates from verification certificate
outputs.

This lane does not publish externally. It creates a public anchor candidate,
receipt, and public proof manifest while keeping all release/readiness flags
false.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_CERTIFICATE_STATUS = Path(
    "outputs/verification_certificate/verification_certificate_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/public_anchor_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "public_anchor_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "public_anchor_summary.json"
RECEIPT_OUTPUT = DEFAULT_OUTPUT_DIR / "public_anchor_receipt.json"
MANIFEST_OUTPUT = DEFAULT_OUTPUT_DIR / "public_anchor_manifest.json"

FORBIDDEN_TRUE_FLAGS = (
    "publicly_anchored",
    "public_anchor_applied",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_PUBLIC_ANCHOR_STATUSES = {
    "PUBLIC_ANCHOR_CANDIDATE",
    "BLOCKED_MISSING_CERTIFICATE",
    "BLOCKED_UNCERTIFIABLE_CERTIFICATE",
    "PUBLIC_ANCHOR_INVALID",
}


@dataclass
class PublicAnchorRecord:
    public_anchor_id: str
    public_anchor_status: str
    certificate_hash: str
    certificate_signature_hash: str
    verification_root: str
    publication_root: str
    anchor_bundle_root: str
    public_anchor_material_hash: str
    public_anchor_root: str
    public_anchor_receipt_hash: str
    publicly_anchored: bool
    public_anchor_applied: bool
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
        "public_anchor_id",
        "public_anchor_status",
        "certificate_hash",
        "certificate_signature_hash",
        "verification_root",
        "publication_root",
        "anchor_bundle_root",
        "public_anchor_material_hash",
        "public_anchor_root",
        "public_anchor_receipt_hash",
        "publicly_anchored",
        "public_anchor_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"PublicAnchorRecord missing fields: {sorted(missing)}")

    if data["public_anchor_status"] not in ALLOWED_PUBLIC_ANCHOR_STATUSES:
        raise ValueError(f"Unsupported public_anchor_status: {data['public_anchor_status']}")

    if data["public_anchor_status"] == "PUBLIC_ANCHOR_CANDIDATE":
        for key in (
            "certificate_hash",
            "certificate_signature_hash",
            "verification_root",
            "publication_root",
            "anchor_bundle_root",
            "public_anchor_material_hash",
            "public_anchor_root",
            "public_anchor_receipt_hash",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for PUBLIC_ANCHOR_CANDIDATE")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_public_anchor(
    certificate_status_path: Path = DEFAULT_CERTIFICATE_STATUS,
) -> Dict[str, Any]:
    certificate_record = _first_record(certificate_status_path)

    if not certificate_record:
        status = "BLOCKED_MISSING_CERTIFICATE"
    elif certificate_record.get("certificate_status") != "CERTIFIABLE":
        status = "BLOCKED_UNCERTIFIABLE_CERTIFICATE"
    else:
        status = "PUBLIC_ANCHOR_CANDIDATE"

    certificate_hash = str(certificate_record.get("certificate_hash") or "")
    certificate_signature_hash = str(certificate_record.get("certificate_signature_hash") or "")
    verification_root = str(certificate_record.get("verification_root") or "")
    publication_root = str(certificate_record.get("publication_root") or "")
    anchor_bundle_root = str(certificate_record.get("anchor_bundle_root") or "")

    public_anchor_material = {
        "anchor_version": "public_anchor_v1",
        "public_anchor_status": status,
        "certificate_hash": certificate_hash,
        "certificate_signature_hash": certificate_signature_hash,
        "verification_root": verification_root,
        "publication_root": publication_root,
        "anchor_bundle_root": anchor_bundle_root,
        "publicly_anchored": False,
        "public_anchor_applied": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    public_anchor_material_hash = _hash_json(public_anchor_material)

    public_anchor_root = _hash_json(
        {
            "public_anchor_material_hash": public_anchor_material_hash,
            "certificate_hash": certificate_hash,
            "verification_root": verification_root,
            "publication_root": publication_root,
        }
    )

    receipt = {
        "receipt_version": "public_anchor_receipt_v1",
        "public_anchor_status": status,
        "public_anchor_root": public_anchor_root,
        "certificate_hash": certificate_hash,
        "verification_root": verification_root,
        "publication_root": publication_root,
        "publicly_anchored": False,
    }

    public_anchor_receipt_hash = _hash_json(receipt)

    manifest = {
        "manifest_version": "public_anchor_manifest_v1",
        "public_anchor_root": public_anchor_root,
        "public_anchor_receipt_hash": public_anchor_receipt_hash,
        "certificate_hash": certificate_hash,
        "certificate_signature_hash": certificate_signature_hash,
        "verification_root": verification_root,
        "publication_root": publication_root,
        "anchor_bundle_root": anchor_bundle_root,
        "publicly_anchored": False,
    }

    record = PublicAnchorRecord(
        public_anchor_id=f"PUBLIC_ANCHOR_{public_anchor_root[:16]}",
        public_anchor_status=status,
        certificate_hash=certificate_hash,
        certificate_signature_hash=certificate_signature_hash,
        verification_root=verification_root,
        publication_root=publication_root,
        anchor_bundle_root=anchor_bundle_root,
        public_anchor_material_hash=public_anchor_material_hash,
        public_anchor_root=public_anchor_root,
        public_anchor_receipt_hash=public_anchor_receipt_hash,
        publicly_anchored=False,
        public_anchor_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Public anchor candidate only. No external anchoring, certification, "
            "approval, public release, institutional release, or report readiness "
            "mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "public_anchor_record_count": 1,
        "public_anchor_candidate_count": 1 if status == "PUBLIC_ANCHOR_CANDIDATE" else 0,
        "public_anchor_blocked_missing_certificate_count": (
            1 if status == "BLOCKED_MISSING_CERTIFICATE" else 0
        ),
        "public_anchor_blocked_uncertifiable_certificate_count": (
            1 if status == "BLOCKED_UNCERTIFIABLE_CERTIFICATE" else 0
        ),
        "public_anchor_invalid_count": 1 if status == "PUBLIC_ANCHOR_INVALID" else 0,
        "public_anchor_status": status,
        "public_anchor_material_hash": public_anchor_material_hash,
        "public_anchor_root": public_anchor_root,
        "public_anchor_receipt_hash": public_anchor_receipt_hash,
        "publicly_anchored": False,
        "public_anchor_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(RECEIPT_OUTPUT, receipt)
    _write_json(MANIFEST_OUTPUT, manifest)

    return {
        "payload": payload,
        "summary": summary,
        "receipt": receipt,
        "manifest": manifest,
    }