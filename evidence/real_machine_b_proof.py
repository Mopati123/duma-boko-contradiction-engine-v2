#!/usr/bin/env python3
"""
Real Machine-B Proof Engine v1.

Builds a deterministic real Machine-B proof candidate from the cross-machine
proof and production freeze outputs.

This lane distinguishes logical placeholder Machine-B proof from real external
Machine-B proof readiness. It does not claim real Machine-B execution has
occurred unless an external Machine-B artifact is provided later.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_CROSS_MACHINE_STATUS = Path("outputs/cross_machine_proof/cross_machine_proof_status.json")
DEFAULT_PRODUCTION_FREEZE_STATUS = Path("outputs/production_freeze/production_freeze_status.json")

DEFAULT_OUTPUT_DIR = Path("outputs/real_machine_b_proof")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_machine_b_proof_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_machine_b_proof_summary.json"
CONTRACT_OUTPUT = DEFAULT_OUTPUT_DIR / "machine_b_contract_request.json"

FORBIDDEN_TRUE_FLAGS = (
    "real_machine_b_verified",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_STATUSES = {
    "REAL_MACHINE_B_READY",
    "BLOCKED_MISSING_CROSS_MACHINE",
    "BLOCKED_INVALID_CROSS_MACHINE",
    "BLOCKED_MISSING_PRODUCTION_FREEZE",
    "BLOCKED_INVALID_PRODUCTION_FREEZE",
    "REAL_MACHINE_B_INVALID",
}


@dataclass
class RealMachineBProofRecord:
    machine_b_id: str
    machine_b_status: str
    cross_machine_root: str
    production_freeze_root: str
    replay_root: str
    contract_match_required: bool
    merkle_match_required: bool
    replay_match_required: bool
    machine_b_contract_request_hash: str
    machine_b_expected_root: str
    real_machine_b_verified: bool
    production_ready: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_external_machine: bool
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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _determine_status(cross_machine: Dict[str, Any], production_freeze: Dict[str, Any]) -> str:
    if not cross_machine:
        return "BLOCKED_MISSING_CROSS_MACHINE"
    if cross_machine.get("cross_machine_status") != "CROSS_MACHINE_CANDIDATE":
        return "BLOCKED_INVALID_CROSS_MACHINE"
    if cross_machine.get("cross_machine_verified") is not True:
        return "BLOCKED_INVALID_CROSS_MACHINE"

    if not production_freeze:
        return "BLOCKED_MISSING_PRODUCTION_FREEZE"
    if production_freeze.get("freeze_status") != "PRODUCTION_FREEZE_CANDIDATE":
        return "BLOCKED_INVALID_PRODUCTION_FREEZE"

    if production_freeze.get("cross_machine_root") != cross_machine.get("cross_machine_root"):
        return "BLOCKED_INVALID_PRODUCTION_FREEZE"

    return "REAL_MACHINE_B_READY"


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "machine_b_id",
        "machine_b_status",
        "cross_machine_root",
        "production_freeze_root",
        "replay_root",
        "contract_match_required",
        "merkle_match_required",
        "replay_match_required",
        "machine_b_contract_request_hash",
        "machine_b_expected_root",
        "real_machine_b_verified",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_external_machine",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"RealMachineBProofRecord missing fields: {sorted(missing)}")

    if data["machine_b_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported machine_b_status: {data['machine_b_status']}")

    if data["machine_b_status"] == "REAL_MACHINE_B_READY":
        for key in (
            "cross_machine_root",
            "production_freeze_root",
            "replay_root",
            "machine_b_contract_request_hash",
            "machine_b_expected_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for REAL_MACHINE_B_READY")

        for key in ("contract_match_required", "merkle_match_required", "replay_match_required"):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for REAL_MACHINE_B_READY")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_external_machine"] is not True:
        raise ValueError("requires_external_machine must remain true")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_real_machine_b_proof(
    cross_machine_status_path: Path = DEFAULT_CROSS_MACHINE_STATUS,
    production_freeze_status_path: Path = DEFAULT_PRODUCTION_FREEZE_STATUS,
) -> Dict[str, Any]:
    cross_machine = _first_record(cross_machine_status_path)
    production_freeze = _first_record(production_freeze_status_path)

    status = _determine_status(cross_machine, production_freeze)

    cross_machine_root = str(cross_machine.get("cross_machine_root") or "")
    production_freeze_root = str(production_freeze.get("production_freeze_root") or "")
    replay_root = str(cross_machine.get("replay_root") or "")

    contract_request = {
        "contract_version": "real_machine_b_contract_request_v1",
        "required_execution": "independent_machine_b_run",
        "cross_machine_root": cross_machine_root,
        "production_freeze_root": production_freeze_root,
        "replay_root": replay_root,
        "required_matches": {
            "contract_match": True,
            "merkle_match": True,
            "replay_match": True,
        },
        "forbidden_claims": {
            "real_machine_b_verified": False,
            "production_ready": False,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
    }

    machine_b_contract_request_hash = _hash_json(contract_request)

    machine_b_expected_root = _hash_json(
        {
            "machine_b_contract_request_hash": machine_b_contract_request_hash,
            "cross_machine_root": cross_machine_root,
            "production_freeze_root": production_freeze_root,
            "replay_root": replay_root,
        }
    )

    record = RealMachineBProofRecord(
        machine_b_id=f"REAL_MACHINE_B_{machine_b_expected_root[:16]}",
        machine_b_status=status,
        cross_machine_root=cross_machine_root,
        production_freeze_root=production_freeze_root,
        replay_root=replay_root,
        contract_match_required=True,
        merkle_match_required=True,
        replay_match_required=True,
        machine_b_contract_request_hash=machine_b_contract_request_hash,
        machine_b_expected_root=machine_b_expected_root,
        real_machine_b_verified=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_external_machine=True,
        requires_manual_review=True,
        notes=(
            "Real Machine-B proof readiness candidate only. No independent Machine-B "
            "execution has been claimed. This artifact defines the external proof "
            "contract that a second machine must satisfy."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "machine_b_record_count": 1,
        "machine_b_ready_count": 1 if status == "REAL_MACHINE_B_READY" else 0,
        "machine_b_blocked_missing_cross_machine_count": (
            1 if status == "BLOCKED_MISSING_CROSS_MACHINE" else 0
        ),
        "machine_b_blocked_invalid_cross_machine_count": (
            1 if status == "BLOCKED_INVALID_CROSS_MACHINE" else 0
        ),
        "machine_b_blocked_missing_production_freeze_count": (
            1 if status == "BLOCKED_MISSING_PRODUCTION_FREEZE" else 0
        ),
        "machine_b_blocked_invalid_production_freeze_count": (
            1 if status == "BLOCKED_INVALID_PRODUCTION_FREEZE" else 0
        ),
        "machine_b_invalid_count": 1 if status == "REAL_MACHINE_B_INVALID" else 0,
        "machine_b_status": status,
        "machine_b_contract_request_hash": machine_b_contract_request_hash,
        "machine_b_expected_root": machine_b_expected_root,
        "real_machine_b_verified": False,
        "requires_external_machine": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CONTRACT_OUTPUT, contract_request)

    return {
        "payload": payload,
        "summary": summary,
        "contract_request": contract_request,
    }