#!/usr/bin/env python3
"""
Real Machine-B Verification Engine v1.

Verifies an externally produced Machine-B proof package that has been copied
back onto Machine A.

This lane does not mark production ready, public ready, institutional ready, or
report ready. It creates a deterministic verification candidate proving that the
Machine-B proof package matches the expected roots and match flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_MACHINE_B_DIR = Path("machine_b_result")
DEFAULT_OUTPUT_DIR = Path("outputs/real_machine_b_verification")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_machine_b_verification_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_machine_b_verification_summary.json"

EXPECTED_MACHINE_B_ROOT = "dd51fa0de9a510217c74448810a7caf28afcd482bce1846e400eb11c75ab15a6"
EXPECTED_CROSS_MACHINE_ROOT = "abcc3d944faf183ab6f38687c290455e4baba9703f04fcca1d7217bd1dc7a95f"
EXPECTED_MACHINE_B_CONTRACT_HASH = "2db9d369fd80419e52db0a9a753071c7e050c7572bd6f277ade0b99347f94fae"

ALLOWED_STATUSES = {
    "REAL_MACHINE_B_VERIFIED_CANDIDATE",
    "BLOCKED_MISSING_MACHINE_B_PACKAGE",
    "BLOCKED_INVALID_MACHINE_B_ROOT",
    "BLOCKED_INVALID_CROSS_MACHINE_ROOT",
    "BLOCKED_INVALID_MATCH_FLAGS",
    "REAL_MACHINE_B_VERIFICATION_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class RealMachineBVerificationRecord:
    verification_id: str
    verification_status: str
    machine_b_expected_root: str
    expected_machine_b_root: str
    machine_b_contract_request_hash: str
    expected_machine_b_contract_hash: str
    cross_machine_root: str
    expected_cross_machine_root: str
    contract_match: bool
    merkle_match: bool
    replay_match: bool
    cross_machine_verified: bool
    real_machine_b_verified: bool
    verification_root: str
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


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _exists_required_package(machine_b_dir: Path) -> bool:
    required = (
        "real_machine_b_proof_summary.json",
        "cross_machine_proof_summary.json",
        "production_freeze_summary.json",
        "machine_b_contract_request.json",
        "real_machine_b_proof_status.json",
    )
    return all((machine_b_dir / name).exists() for name in required)


def _determine_status(
    machine_b_summary: Dict[str, Any],
    cross_machine_summary: Dict[str, Any],
) -> str:
    if not machine_b_summary or not cross_machine_summary:
        return "BLOCKED_MISSING_MACHINE_B_PACKAGE"

    if machine_b_summary.get("machine_b_expected_root") != EXPECTED_MACHINE_B_ROOT:
        return "BLOCKED_INVALID_MACHINE_B_ROOT"

    if (
        machine_b_summary.get("machine_b_contract_request_hash")
        != EXPECTED_MACHINE_B_CONTRACT_HASH
    ):
        return "BLOCKED_INVALID_MACHINE_B_ROOT"

    if cross_machine_summary.get("cross_machine_root") != EXPECTED_CROSS_MACHINE_ROOT:
        return "BLOCKED_INVALID_CROSS_MACHINE_ROOT"

    required_flags = (
        cross_machine_summary.get("contract_match") is True,
        cross_machine_summary.get("merkle_match") is True,
        cross_machine_summary.get("replay_match") is True,
        cross_machine_summary.get("cross_machine_verified") is True,
    )

    if not all(required_flags):
        return "BLOCKED_INVALID_MATCH_FLAGS"

    if machine_b_summary.get("machine_b_status") != "REAL_MACHINE_B_READY":
        return "BLOCKED_INVALID_MACHINE_B_ROOT"

    if machine_b_summary.get("machine_b_ready_count") != 1:
        return "BLOCKED_INVALID_MACHINE_B_ROOT"

    return "REAL_MACHINE_B_VERIFIED_CANDIDATE"


def validate_record(record: RealMachineBVerificationRecord) -> None:
    data = record.to_dict()

    required = {
        "verification_id",
        "verification_status",
        "machine_b_expected_root",
        "expected_machine_b_root",
        "machine_b_contract_request_hash",
        "expected_machine_b_contract_hash",
        "cross_machine_root",
        "expected_cross_machine_root",
        "contract_match",
        "merkle_match",
        "replay_match",
        "cross_machine_verified",
        "real_machine_b_verified",
        "verification_root",
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
        raise ValueError(f"RealMachineBVerificationRecord missing fields: {sorted(missing)}")

    if data["verification_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported verification_status: {data['verification_status']}")

    if data["verification_status"] == "REAL_MACHINE_B_VERIFIED_CANDIDATE":
        if data["real_machine_b_verified"] is not True:
            raise ValueError("real_machine_b_verified must be true for verified candidate")

        for flag in (
            "contract_match",
            "merkle_match",
            "replay_match",
            "cross_machine_verified",
        ):
            if data[flag] is not True:
                raise ValueError(f"{flag} must be true for verified candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_real_machine_b_verification(
    machine_b_dir: Path = DEFAULT_MACHINE_B_DIR,
) -> Dict[str, Any]:
    if not _exists_required_package(machine_b_dir):
        machine_b_summary = {}
        cross_machine_summary = {}
    else:
        machine_b_summary = _load_json(machine_b_dir / "real_machine_b_proof_summary.json")
        cross_machine_summary = _load_json(machine_b_dir / "cross_machine_proof_summary.json")

    status = _determine_status(machine_b_summary, cross_machine_summary)

    machine_b_expected_root = str(machine_b_summary.get("machine_b_expected_root") or "")
    machine_b_contract_request_hash = str(
        machine_b_summary.get("machine_b_contract_request_hash") or ""
    )
    cross_machine_root = str(cross_machine_summary.get("cross_machine_root") or "")

    contract_match = cross_machine_summary.get("contract_match") is True
    merkle_match = cross_machine_summary.get("merkle_match") is True
    replay_match = cross_machine_summary.get("replay_match") is True
    cross_machine_verified = cross_machine_summary.get("cross_machine_verified") is True

    real_machine_b_verified = status == "REAL_MACHINE_B_VERIFIED_CANDIDATE"

    verification_root = _hash_json(
        {
            "verification_status": status,
            "machine_b_expected_root": machine_b_expected_root,
            "expected_machine_b_root": EXPECTED_MACHINE_B_ROOT,
            "machine_b_contract_request_hash": machine_b_contract_request_hash,
            "expected_machine_b_contract_hash": EXPECTED_MACHINE_B_CONTRACT_HASH,
            "cross_machine_root": cross_machine_root,
            "expected_cross_machine_root": EXPECTED_CROSS_MACHINE_ROOT,
            "contract_match": contract_match,
            "merkle_match": merkle_match,
            "replay_match": replay_match,
            "cross_machine_verified": cross_machine_verified,
            "real_machine_b_verified": real_machine_b_verified,
        }
    )

    record = RealMachineBVerificationRecord(
        verification_id=f"REAL_MACHINE_B_VERIFICATION_{verification_root[:16]}",
        verification_status=status,
        machine_b_expected_root=machine_b_expected_root,
        expected_machine_b_root=EXPECTED_MACHINE_B_ROOT,
        machine_b_contract_request_hash=machine_b_contract_request_hash,
        expected_machine_b_contract_hash=EXPECTED_MACHINE_B_CONTRACT_HASH,
        cross_machine_root=cross_machine_root,
        expected_cross_machine_root=EXPECTED_CROSS_MACHINE_ROOT,
        contract_match=contract_match,
        merkle_match=merkle_match,
        replay_match=replay_match,
        cross_machine_verified=cross_machine_verified,
        real_machine_b_verified=real_machine_b_verified,
        verification_root=verification_root,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Real Machine-B verification candidate. Machine-B proof package has "
            "been received on Machine A and matched against expected deterministic roots."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "machine_b_verification_record_count": 1,
        "machine_b_verified_candidate_count": (
            1 if status == "REAL_MACHINE_B_VERIFIED_CANDIDATE" else 0
        ),
        "machine_b_verification_blocked_missing_package_count": (
            1 if status == "BLOCKED_MISSING_MACHINE_B_PACKAGE" else 0
        ),
        "machine_b_verification_blocked_invalid_machine_b_root_count": (
            1 if status == "BLOCKED_INVALID_MACHINE_B_ROOT" else 0
        ),
        "machine_b_verification_blocked_invalid_cross_machine_root_count": (
            1 if status == "BLOCKED_INVALID_CROSS_MACHINE_ROOT" else 0
        ),
        "machine_b_verification_blocked_invalid_match_flags_count": (
            1 if status == "BLOCKED_INVALID_MATCH_FLAGS" else 0
        ),
        "machine_b_verification_invalid_count": (
            1 if status == "REAL_MACHINE_B_VERIFICATION_INVALID" else 0
        ),
        "machine_b_verification_status": status,
        "machine_b_expected_root": machine_b_expected_root,
        "expected_machine_b_root": EXPECTED_MACHINE_B_ROOT,
        "cross_machine_root": cross_machine_root,
        "expected_cross_machine_root": EXPECTED_CROSS_MACHINE_ROOT,
        "contract_match": contract_match,
        "merkle_match": merkle_match,
        "replay_match": replay_match,
        "cross_machine_verified": cross_machine_verified,
        "real_machine_b_verified": real_machine_b_verified,
        "verification_root": verification_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {
        "payload": payload,
        "summary": summary,
    }