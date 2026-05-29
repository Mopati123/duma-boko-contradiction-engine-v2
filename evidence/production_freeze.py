#!/usr/bin/env python3
"""
Production Freeze Engine v1.

Builds a deterministic production-freeze candidate from the cross-machine proof
and upstream production trust chain.

This lane does not deploy, publish, approve evidence, or mutate readiness flags.
It creates the final frozen production baseline candidate.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_CROSS_MACHINE_STATUS = Path("outputs/cross_machine_proof/cross_machine_proof_status.json")
DEFAULT_REPLAY_STATUS = Path("outputs/replay_certification/replay_certification_status.json")
DEFAULT_AUTHORITY_STATUS = Path("outputs/signature_authority/signature_authority_status.json")
DEFAULT_PUBLIC_ANCHOR_STATUS = Path("outputs/public_anchor_engine/public_anchor_status.json")
DEFAULT_CERTIFICATE_STATUS = Path("outputs/verification_certificate/verification_certificate_status.json")

DEFAULT_OUTPUT_DIR = Path("outputs/production_freeze")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "production_freeze_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "production_freeze_summary.json"
BASELINE_OUTPUT = DEFAULT_OUTPUT_DIR / "production_baseline.json"

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "freeze_applied",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_FREEZE_STATUSES = {
    "PRODUCTION_FREEZE_CANDIDATE",
    "BLOCKED_MISSING_CROSS_MACHINE",
    "BLOCKED_INVALID_CROSS_MACHINE",
    "BLOCKED_MISSING_REPLAY",
    "BLOCKED_INVALID_REPLAY",
    "BLOCKED_MISSING_AUTHORITY",
    "BLOCKED_INVALID_AUTHORITY",
    "BLOCKED_MISSING_PUBLIC_ANCHOR",
    "BLOCKED_INVALID_PUBLIC_ANCHOR",
    "BLOCKED_MISSING_CERTIFICATE",
    "BLOCKED_INVALID_CERTIFICATE",
    "PRODUCTION_FREEZE_INVALID",
}


@dataclass
class ProductionFreezeRecord:
    freeze_id: str
    freeze_status: str
    certificate_hash: str
    public_anchor_root: str
    authority_hash: str
    certificate_authority_root: str
    replay_root: str
    cross_machine_root: str
    production_baseline_hash: str
    production_freeze_root: str
    production_ready: bool
    freeze_applied: bool
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
    cross_machine: Dict[str, Any],
    replay: Dict[str, Any],
    authority: Dict[str, Any],
    public_anchor: Dict[str, Any],
    certificate: Dict[str, Any],
) -> str:
    if not cross_machine:
        return "BLOCKED_MISSING_CROSS_MACHINE"
    if cross_machine.get("cross_machine_status") != "CROSS_MACHINE_CANDIDATE":
        return "BLOCKED_INVALID_CROSS_MACHINE"
    if cross_machine.get("cross_machine_verified") is not True:
        return "BLOCKED_INVALID_CROSS_MACHINE"

    if not replay:
        return "BLOCKED_MISSING_REPLAY"
    if replay.get("replay_status") != "REPLAY_CERTIFICATION_CANDIDATE":
        return "BLOCKED_INVALID_REPLAY"
    if replay.get("replay_verified") is not True:
        return "BLOCKED_INVALID_REPLAY"

    if not authority:
        return "BLOCKED_MISSING_AUTHORITY"
    if authority.get("authority_status") != "SIGNATURE_AUTHORITY_CANDIDATE":
        return "BLOCKED_INVALID_AUTHORITY"

    if not public_anchor:
        return "BLOCKED_MISSING_PUBLIC_ANCHOR"
    if public_anchor.get("public_anchor_status") != "PUBLIC_ANCHOR_CANDIDATE":
        return "BLOCKED_INVALID_PUBLIC_ANCHOR"

    if not certificate:
        return "BLOCKED_MISSING_CERTIFICATE"
    if certificate.get("certificate_status") != "CERTIFIABLE":
        return "BLOCKED_INVALID_CERTIFICATE"

    checks = (
        (cross_machine.get("replay_root"), replay.get("replay_root"), "BLOCKED_INVALID_CROSS_MACHINE"),
        (replay.get("authority_hash"), authority.get("authority_hash"), "BLOCKED_INVALID_REPLAY"),
        (replay.get("public_anchor_root"), public_anchor.get("public_anchor_root"), "BLOCKED_INVALID_REPLAY"),
        (replay.get("certificate_hash"), certificate.get("certificate_hash"), "BLOCKED_INVALID_REPLAY"),
        (authority.get("public_anchor_root"), public_anchor.get("public_anchor_root"), "BLOCKED_INVALID_AUTHORITY"),
        (authority.get("certificate_hash"), certificate.get("certificate_hash"), "BLOCKED_INVALID_AUTHORITY"),
        (public_anchor.get("certificate_hash"), certificate.get("certificate_hash"), "BLOCKED_INVALID_PUBLIC_ANCHOR"),
    )

    for left, right, failure in checks:
        if left != right or not _is_nonzero_hash(left):
            return failure

    return "PRODUCTION_FREEZE_CANDIDATE"


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "freeze_id",
        "freeze_status",
        "certificate_hash",
        "public_anchor_root",
        "authority_hash",
        "certificate_authority_root",
        "replay_root",
        "cross_machine_root",
        "production_baseline_hash",
        "production_freeze_root",
        "production_ready",
        "freeze_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ProductionFreezeRecord missing fields: {sorted(missing)}")

    if data["freeze_status"] not in ALLOWED_FREEZE_STATUSES:
        raise ValueError(f"Unsupported freeze_status: {data['freeze_status']}")

    if data["freeze_status"] == "PRODUCTION_FREEZE_CANDIDATE":
        for key in (
            "certificate_hash",
            "public_anchor_root",
            "authority_hash",
            "certificate_authority_root",
            "replay_root",
            "cross_machine_root",
            "production_baseline_hash",
            "production_freeze_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for production freeze candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_production_freeze(
    cross_machine_status_path: Path = DEFAULT_CROSS_MACHINE_STATUS,
    replay_status_path: Path = DEFAULT_REPLAY_STATUS,
    authority_status_path: Path = DEFAULT_AUTHORITY_STATUS,
    public_anchor_status_path: Path = DEFAULT_PUBLIC_ANCHOR_STATUS,
    certificate_status_path: Path = DEFAULT_CERTIFICATE_STATUS,
) -> Dict[str, Any]:
    cross_machine = _first_record(cross_machine_status_path)
    replay = _first_record(replay_status_path)
    authority = _first_record(authority_status_path)
    public_anchor = _first_record(public_anchor_status_path)
    certificate = _first_record(certificate_status_path)

    status = _determine_status(cross_machine, replay, authority, public_anchor, certificate)

    certificate_hash = str(certificate.get("certificate_hash") or "")
    public_anchor_root = str(public_anchor.get("public_anchor_root") or "")
    authority_hash = str(authority.get("authority_hash") or "")
    certificate_authority_root = str(authority.get("certificate_authority_root") or "")
    replay_root = str(replay.get("replay_root") or "")
    cross_machine_root = str(cross_machine.get("cross_machine_root") or "")

    production_baseline = {
        "baseline_version": "production_freeze_v1",
        "freeze_status": status,
        "certificate_hash": certificate_hash,
        "public_anchor_root": public_anchor_root,
        "authority_hash": authority_hash,
        "certificate_authority_root": certificate_authority_root,
        "replay_root": replay_root,
        "cross_machine_root": cross_machine_root,
        "production_ready": False,
        "freeze_applied": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    production_baseline_hash = _hash_json(production_baseline)

    production_freeze_root = _hash_json(
        {
            "production_baseline_hash": production_baseline_hash,
            "certificate_hash": certificate_hash,
            "public_anchor_root": public_anchor_root,
            "authority_hash": authority_hash,
            "replay_root": replay_root,
            "cross_machine_root": cross_machine_root,
        }
    )

    record = ProductionFreezeRecord(
        freeze_id=f"PRODUCTION_FREEZE_{production_freeze_root[:16]}",
        freeze_status=status,
        certificate_hash=certificate_hash,
        public_anchor_root=public_anchor_root,
        authority_hash=authority_hash,
        certificate_authority_root=certificate_authority_root,
        replay_root=replay_root,
        cross_machine_root=cross_machine_root,
        production_baseline_hash=production_baseline_hash,
        production_freeze_root=production_freeze_root,
        production_ready=False,
        freeze_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Production freeze candidate only. No deployment, public release, "
            "institutional release, evidence approval, or readiness flag mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "production_freeze_record_count": 1,
        "production_freeze_candidate_count": 1 if status == "PRODUCTION_FREEZE_CANDIDATE" else 0,
        "production_freeze_blocked_count": 0 if status == "PRODUCTION_FREEZE_CANDIDATE" else 1,
        "production_freeze_invalid_count": 1 if status == "PRODUCTION_FREEZE_INVALID" else 0,
        "freeze_status": status,
        "production_baseline_hash": production_baseline_hash,
        "production_freeze_root": production_freeze_root,
        "production_ready": False,
        "freeze_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(BASELINE_OUTPUT, production_baseline)

    return {
        "payload": payload,
        "summary": summary,
        "production_baseline": production_baseline,
    }