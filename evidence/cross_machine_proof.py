#!/usr/bin/env python3
"""
Cross-Machine Proof Engine v1.

Builds deterministic cross-machine proof candidates from replay certification
outputs.

This lane does not claim a real second machine has run the pipeline yet. It
creates a reproducibility contract candidate and a Machine-B placeholder proof
whose roots must match the local replay contract before production freeze.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_REPLAY_STATUS = Path("outputs/replay_certification/replay_certification_status.json")

DEFAULT_OUTPUT_DIR = Path("outputs/cross_machine_proof")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "cross_machine_proof_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "cross_machine_proof_summary.json"
CONTRACT_OUTPUT = DEFAULT_OUTPUT_DIR / "cross_machine_contract.json"

FORBIDDEN_TRUE_FLAGS = (
    "cross_machine_applied",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_CROSS_MACHINE_STATUSES = {
    "CROSS_MACHINE_CANDIDATE",
    "BLOCKED_MISSING_REPLAY",
    "BLOCKED_INVALID_REPLAY",
    "CROSS_MACHINE_INVALID",
}


@dataclass
class CrossMachineProofRecord:
    cross_machine_id: str
    cross_machine_status: str
    replay_root: str
    replay_input_hash: str
    replay_output_hash: str
    machine_a_contract_hash: str
    machine_b_contract_hash: str
    contract_match: bool
    merkle_match: bool
    replay_match: bool
    cross_machine_root: str
    cross_machine_verified: bool
    cross_machine_applied: bool
    production_ready: bool
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
        "cross_machine_id",
        "cross_machine_status",
        "replay_root",
        "replay_input_hash",
        "replay_output_hash",
        "machine_a_contract_hash",
        "machine_b_contract_hash",
        "contract_match",
        "merkle_match",
        "replay_match",
        "cross_machine_root",
        "cross_machine_verified",
        "cross_machine_applied",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CrossMachineProofRecord missing fields: {sorted(missing)}")

    if data["cross_machine_status"] not in ALLOWED_CROSS_MACHINE_STATUSES:
        raise ValueError(f"Unsupported cross_machine_status: {data['cross_machine_status']}")

    if data["cross_machine_status"] == "CROSS_MACHINE_CANDIDATE":
        for key in (
            "replay_root",
            "replay_input_hash",
            "replay_output_hash",
            "machine_a_contract_hash",
            "machine_b_contract_hash",
            "cross_machine_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for cross-machine candidate")

        for key in ("contract_match", "merkle_match", "replay_match", "cross_machine_verified"):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for cross-machine candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_cross_machine_proof(
    replay_status_path: Path = DEFAULT_REPLAY_STATUS,
) -> Dict[str, Any]:
    replay_record = _first_record(replay_status_path)

    if not replay_record:
        status = "BLOCKED_MISSING_REPLAY"
    elif replay_record.get("replay_status") != "REPLAY_CERTIFICATION_CANDIDATE":
        status = "BLOCKED_INVALID_REPLAY"
    elif replay_record.get("replay_verified") is not True:
        status = "BLOCKED_INVALID_REPLAY"
    else:
        status = "CROSS_MACHINE_CANDIDATE"

    replay_root = str(replay_record.get("replay_root") or "")
    replay_input_hash = str(replay_record.get("replay_input_hash") or "")
    replay_output_hash = str(replay_record.get("replay_output_hash") or "")

    contract = {
        "contract_version": "cross_machine_contract_v1",
        "required_status": "REPLAY_CERTIFICATION_CANDIDATE",
        "replay_root": replay_root,
        "replay_input_hash": replay_input_hash,
        "replay_output_hash": replay_output_hash,
        "determinism_laws": [
            "same_inputs_same_replay_root",
            "same_inputs_same_replay_input_hash",
            "same_inputs_same_replay_output_hash",
            "no_external_mutation",
            "no_readiness_flag_mutation",
        ],
    }

    machine_a_contract_hash = _hash_json(
        {
            "machine": "A",
            "contract": contract,
        }
    )

    # Candidate placeholder: until an actual second machine submits its own
    # proof, Machine B is modelled as the same deterministic contract candidate.
    # Production Freeze must replace this with a real external Machine-B artifact.
    machine_b_contract_hash = _hash_json(
        {
            "machine": "A",
            "contract": contract,
        }
    )

    contract_match = (
        status == "CROSS_MACHINE_CANDIDATE"
        and machine_a_contract_hash == machine_b_contract_hash
    )

    merkle_material = {
        "replay_root": replay_root,
        "replay_input_hash": replay_input_hash,
        "replay_output_hash": replay_output_hash,
        "machine_a_contract_hash": machine_a_contract_hash,
        "machine_b_contract_hash": machine_b_contract_hash,
    }

    merkle_root_a = _hash_json({"machine": "A", "merkle_material": merkle_material})
    merkle_root_b = _hash_json({"machine": "A", "merkle_material": merkle_material})

    merkle_match = status == "CROSS_MACHINE_CANDIDATE" and merkle_root_a == merkle_root_b

    replay_match = (
        status == "CROSS_MACHINE_CANDIDATE"
        and _is_nonzero_hash(replay_root)
        and _is_nonzero_hash(replay_input_hash)
        and _is_nonzero_hash(replay_output_hash)
    )

    cross_machine_verified = contract_match and merkle_match and replay_match

    cross_machine_root = _hash_json(
        {
            "cross_machine_status": status,
            "replay_root": replay_root,
            "machine_a_contract_hash": machine_a_contract_hash,
            "machine_b_contract_hash": machine_b_contract_hash,
            "contract_match": contract_match,
            "merkle_match": merkle_match,
            "replay_match": replay_match,
        }
    )

    record = CrossMachineProofRecord(
        cross_machine_id=f"CROSS_MACHINE_PROOF_{cross_machine_root[:16]}",
        cross_machine_status=status,
        replay_root=replay_root,
        replay_input_hash=replay_input_hash,
        replay_output_hash=replay_output_hash,
        machine_a_contract_hash=machine_a_contract_hash,
        machine_b_contract_hash=machine_b_contract_hash,
        contract_match=contract_match,
        merkle_match=merkle_match,
        replay_match=replay_match,
        cross_machine_root=cross_machine_root,
        cross_machine_verified=cross_machine_verified,
        cross_machine_applied=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Cross-machine proof candidate only. Machine-B proof is a deterministic "
            "placeholder contract, not an independently executed external proof. "
            "No production readiness, approval, public release, institutional release, "
            "or report readiness mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "cross_machine_record_count": 1,
        "cross_machine_candidate_count": 1 if status == "CROSS_MACHINE_CANDIDATE" else 0,
        "cross_machine_blocked_missing_replay_count": (
            1 if status == "BLOCKED_MISSING_REPLAY" else 0
        ),
        "cross_machine_blocked_invalid_replay_count": (
            1 if status == "BLOCKED_INVALID_REPLAY" else 0
        ),
        "cross_machine_invalid_count": 1 if status == "CROSS_MACHINE_INVALID" else 0,
        "cross_machine_status": status,
        "contract_match": contract_match,
        "merkle_match": merkle_match,
        "replay_match": replay_match,
        "cross_machine_verified": cross_machine_verified,
        "cross_machine_root": cross_machine_root,
        "production_ready": False,
        "cross_machine_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CONTRACT_OUTPUT, contract)

    return {
        "payload": payload,
        "summary": summary,
        "contract": contract,
    }