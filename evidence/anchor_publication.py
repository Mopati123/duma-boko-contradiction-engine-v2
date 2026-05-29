#!/usr/bin/env python3
"""
Anchor Publication Engine v1.

Builds deterministic anchor-publication candidates from final report sealing
outputs and governance anchor bundle outputs.

This lane does not publish to any external network. It creates a publication
candidate, receipt candidate, and verification candidate while keeping all
release/readiness flags false.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_FINAL_REPORT_SEALING_STATUS = Path(
    "outputs/final_report_sealing/final_report_sealing_status.json"
)
DEFAULT_ANCHOR_BUNDLE_STATUS = Path(
    "outputs/governance_anchor_bundle/governance_anchor_bundle_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/anchor_publication")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "anchor_publication_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "anchor_publication_summary.json"
RECEIPT_OUTPUT = DEFAULT_OUTPUT_DIR / "publication_receipt.json"
VERIFICATION_OUTPUT = DEFAULT_OUTPUT_DIR / "publication_verification.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "publication_applied",
    "publication_published",
)

ALLOWED_PUBLICATION_STATUSES = {
    "publication_candidate",
    "publication_blocked_missing_seal",
    "publication_blocked_missing_anchor_bundle",
    "publication_blocked_invalid_seal",
    "publication_blocked_invalid_anchor_bundle",
    "publication_invalid",
}


@dataclass
class AnchorPublicationRecord:
    publication_id: str
    publication_status: str
    final_report_seal_root: str
    anchor_bundle_root: str
    anchor_material_hash: str
    institutional_packet_hash: str
    publication_material_hash: str
    publication_root: str
    receipt_hash: str
    verification_hash: str
    publication_applied: bool
    publication_published: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _load_records(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    if not isinstance(payload, dict):
        return []

    records = payload.get("records", [])
    return records if isinstance(records, list) else []


def validate_record(record: object) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "publication_id",
        "publication_status",
        "final_report_seal_root",
        "anchor_bundle_root",
        "anchor_material_hash",
        "institutional_packet_hash",
        "publication_material_hash",
        "publication_root",
        "receipt_hash",
        "verification_hash",
        "publication_applied",
        "publication_published",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"AnchorPublicationRecord missing fields: {sorted(missing)}")

    if data["publication_status"] not in ALLOWED_PUBLICATION_STATUSES:
        raise ValueError(f"Unsupported publication_status: {data['publication_status']}")

    if data["publication_status"] == "publication_candidate":
        if not _is_nonzero_hash(data["final_report_seal_root"]):
            raise ValueError("final_report_seal_root must be a non-zero hash")
        if not _is_nonzero_hash(data["anchor_bundle_root"]):
            raise ValueError("anchor_bundle_root must be a non-zero hash")
        if not _is_nonzero_hash(data["publication_root"]):
            raise ValueError("publication_root must be a non-zero hash")
        if not _is_nonzero_hash(data["receipt_hash"]):
            raise ValueError("receipt_hash must be a non-zero hash")
        if not _is_nonzero_hash(data["verification_hash"]):
            raise ValueError("verification_hash must be a non-zero hash")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _select_first_record(records: List[Dict[str, object]]) -> Dict[str, object]:
    return records[0] if records else {}


def build_anchor_publication(
    final_report_sealing_status_path: Path = DEFAULT_FINAL_REPORT_SEALING_STATUS,
    anchor_bundle_status_path: Path = DEFAULT_ANCHOR_BUNDLE_STATUS,
) -> Dict[str, object]:
    seal_record = _select_first_record(_load_records(final_report_sealing_status_path))
    anchor_record = _select_first_record(_load_records(anchor_bundle_status_path))

    if not seal_record:
        status = "publication_blocked_missing_seal"
    elif not anchor_record:
        status = "publication_blocked_missing_anchor_bundle"
    elif seal_record.get("seal_status") != "final_report_seal_candidate":
        status = "publication_blocked_invalid_seal"
    elif anchor_record.get("bundle_status") != "anchor_bundle_candidate":
        status = "publication_blocked_invalid_anchor_bundle"
    else:
        status = "publication_candidate"

    final_report_seal_root = str(seal_record.get("final_report_seal_root") or "")
    institutional_packet_hash = str(seal_record.get("institutional_packet_hash") or "")
    anchor_bundle_root = str(anchor_record.get("anchor_bundle_root") or "")
    anchor_material_hash = str(anchor_record.get("anchor_material_hash") or "")

    publication_material = {
        "publication_version": "anchor_publication_v1",
        "publication_status": status,
        "final_report_seal_root": final_report_seal_root,
        "institutional_packet_hash": institutional_packet_hash,
        "anchor_bundle_root": anchor_bundle_root,
        "anchor_material_hash": anchor_material_hash,
        "publication_applied": False,
        "publication_published": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    publication_material_hash = _sha256_text(
        json.dumps(publication_material, sort_keys=True, separators=(",", ":"))
    )

    publication_root = _sha256_text(
        json.dumps(
            {
                "publication_material_hash": publication_material_hash,
                "final_report_seal_root": final_report_seal_root,
                "anchor_bundle_root": anchor_bundle_root,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    receipt = {
        "receipt_version": "publication_receipt_v1",
        "publication_status": status,
        "publication_root": publication_root,
        "final_report_seal_root": final_report_seal_root,
        "anchor_bundle_root": anchor_bundle_root,
        "publication_published": False,
    }

    receipt_hash = _sha256_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")))

    verification = {
        "verification_version": "publication_verification_v1",
        "publication_root": publication_root,
        "receipt_hash": receipt_hash,
        "publication_published": False,
        "verification_passed": status == "publication_candidate",
    }

    verification_hash = _sha256_text(
        json.dumps(verification, sort_keys=True, separators=(",", ":"))
    )

    record = AnchorPublicationRecord(
        publication_id=f"ANCHOR_PUBLICATION_{publication_root[:16]}",
        publication_status=status,
        final_report_seal_root=final_report_seal_root,
        anchor_bundle_root=anchor_bundle_root,
        anchor_material_hash=anchor_material_hash,
        institutional_packet_hash=institutional_packet_hash,
        publication_material_hash=publication_material_hash,
        publication_root=publication_root,
        receipt_hash=receipt_hash,
        verification_hash=verification_hash,
        publication_applied=False,
        publication_published=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Anchor publication candidate only. No external publication, evidence approval, "
            "public release, institutional release, report generation, or readiness flag "
            "mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "publication_record_count": 1,
        "publication_candidate_count": 1 if status == "publication_candidate" else 0,
        "publication_blocked_missing_seal_count": (
            1 if status == "publication_blocked_missing_seal" else 0
        ),
        "publication_blocked_missing_anchor_bundle_count": (
            1 if status == "publication_blocked_missing_anchor_bundle" else 0
        ),
        "publication_blocked_invalid_seal_count": (
            1 if status == "publication_blocked_invalid_seal" else 0
        ),
        "publication_blocked_invalid_anchor_bundle_count": (
            1 if status == "publication_blocked_invalid_anchor_bundle" else 0
        ),
        "publication_invalid_count": 0,
        "publication_root": publication_root,
        "receipt_hash": receipt_hash,
        "verification_hash": verification_hash,
        "publication_applied": False,
        "publication_published": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(RECEIPT_OUTPUT, receipt)
    _write_json(VERIFICATION_OUTPUT, verification)

    return {
        "payload": payload,
        "summary": summary,
        "receipt": receipt,
        "verification": verification,
    }