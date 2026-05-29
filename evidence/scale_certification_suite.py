#!/usr/bin/env python3
"""
Scale Certification Suite v1.

Builds deterministic scale-certification candidates from the verified Machine-B
proof and production-freeze baseline.

This lane does not generate real 10/100/1000/10000 evidence cases yet. It
creates the lawful scale plan and deterministic certification envelope proving
that scale-up must preserve the same governance laws, roots, refusal semantics,
and readiness constraints.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_MACHINE_B_VERIFICATION = Path(
    "outputs/real_machine_b_verification/real_machine_b_verification_summary.json"
)
DEFAULT_PRODUCTION_FREEZE = Path(
    "outputs/production_freeze/production_freeze_summary.json"
)
DEFAULT_REPLAY = Path(
    "outputs/replay_certification/replay_certification_summary.json"
)
DEFAULT_CROSS_MACHINE = Path(
    "outputs/cross_machine_proof/cross_machine_proof_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/scale_certification_suite")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "scale_certification_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "scale_certification_summary.json"
PLAN_OUTPUT = DEFAULT_OUTPUT_DIR / "scale_plan.json"

SCALE_TARGETS = (10, 100, 1000, 10000)

ALLOWED_STATUSES = {
    "SCALE_CERTIFICATION_CANDIDATE",
    "BLOCKED_MISSING_MACHINE_B_VERIFICATION",
    "BLOCKED_INVALID_MACHINE_B_VERIFICATION",
    "BLOCKED_MISSING_PRODUCTION_FREEZE",
    "BLOCKED_INVALID_PRODUCTION_FREEZE",
    "BLOCKED_MISSING_REPLAY",
    "BLOCKED_INVALID_REPLAY",
    "BLOCKED_MISSING_CROSS_MACHINE",
    "BLOCKED_INVALID_CROSS_MACHINE",
    "SCALE_CERTIFICATION_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "scale_certified",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ScaleCertificationRecord:
    scale_id: str
    scale_status: str
    scale_target: int
    machine_b_verification_root: str
    production_freeze_root: str
    replay_root: str
    cross_machine_root: str
    scale_input_hash: str
    scale_law_hash: str
    scale_certification_root: str
    deterministic_ready: bool
    refusal_required: bool
    scale_certified: bool
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _determine_status(
    machine_b: Dict[str, Any],
    production_freeze: Dict[str, Any],
    replay: Dict[str, Any],
    cross_machine: Dict[str, Any],
) -> str:
    if not machine_b:
        return "BLOCKED_MISSING_MACHINE_B_VERIFICATION"
    if machine_b.get("machine_b_verification_status") != "REAL_MACHINE_B_VERIFIED_CANDIDATE":
        return "BLOCKED_INVALID_MACHINE_B_VERIFICATION"
    if machine_b.get("real_machine_b_verified") is not True:
        return "BLOCKED_INVALID_MACHINE_B_VERIFICATION"

    if not production_freeze:
        return "BLOCKED_MISSING_PRODUCTION_FREEZE"
    if production_freeze.get("freeze_status") != "PRODUCTION_FREEZE_CANDIDATE":
        return "BLOCKED_INVALID_PRODUCTION_FREEZE"

    if not replay:
        return "BLOCKED_MISSING_REPLAY"
    if replay.get("replay_status") != "REPLAY_CERTIFICATION_CANDIDATE":
        return "BLOCKED_INVALID_REPLAY"
    if replay.get("replay_verified") is not True:
        return "BLOCKED_INVALID_REPLAY"

    if not cross_machine:
        return "BLOCKED_MISSING_CROSS_MACHINE"
    if cross_machine.get("cross_machine_status") != "CROSS_MACHINE_CANDIDATE":
        return "BLOCKED_INVALID_CROSS_MACHINE"
    if cross_machine.get("cross_machine_verified") is not True:
        return "BLOCKED_INVALID_CROSS_MACHINE"

    expected_cross = machine_b.get("cross_machine_root")
    if expected_cross != cross_machine.get("cross_machine_root"):
        return "BLOCKED_INVALID_MACHINE_B_VERIFICATION"

    expected_freeze = production_freeze.get("production_freeze_root")
    if not _is_nonzero_hash(expected_freeze):
        return "BLOCKED_INVALID_PRODUCTION_FREEZE"

    return "SCALE_CERTIFICATION_CANDIDATE"


def validate_record(record: ScaleCertificationRecord) -> None:
    data = record.to_dict()

    required = {
        "scale_id",
        "scale_status",
        "scale_target",
        "machine_b_verification_root",
        "production_freeze_root",
        "replay_root",
        "cross_machine_root",
        "scale_input_hash",
        "scale_law_hash",
        "scale_certification_root",
        "deterministic_ready",
        "refusal_required",
        "scale_certified",
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
        raise ValueError(f"ScaleCertificationRecord missing fields: {sorted(missing)}")

    if data["scale_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported scale_status: {data['scale_status']}")

    if data["scale_target"] not in SCALE_TARGETS:
        raise ValueError(f"Unsupported scale_target: {data['scale_target']}")

    if data["scale_status"] == "SCALE_CERTIFICATION_CANDIDATE":
        for key in (
            "machine_b_verification_root",
            "production_freeze_root",
            "replay_root",
            "cross_machine_root",
            "scale_input_hash",
            "scale_law_hash",
            "scale_certification_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for scale candidate")

        if data["deterministic_ready"] is not True:
            raise ValueError("deterministic_ready must be true for scale candidate")

        if data["refusal_required"] is not True:
            raise ValueError("refusal_required must be true for scale candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_scale_certification_suite(
    machine_b_verification_path: Path = DEFAULT_MACHINE_B_VERIFICATION,
    production_freeze_path: Path = DEFAULT_PRODUCTION_FREEZE,
    replay_path: Path = DEFAULT_REPLAY,
    cross_machine_path: Path = DEFAULT_CROSS_MACHINE,
) -> Dict[str, Any]:
    machine_b = _load_json(machine_b_verification_path)
    production_freeze = _load_json(production_freeze_path)
    replay = _load_json(replay_path)
    cross_machine = _load_json(cross_machine_path)

    status = _determine_status(machine_b, production_freeze, replay, cross_machine)

    machine_b_verification_root = str(machine_b.get("verification_root") or "")
    production_freeze_root = str(production_freeze.get("production_freeze_root") or "")
    replay_root = str(replay.get("replay_root") or "")
    cross_machine_root = str(cross_machine.get("cross_machine_root") or "")

    scale_law = {
        "law_version": "scale_certification_law_v1",
        "scale_targets": list(SCALE_TARGETS),
        "must_preserve": [
            "deterministic_roots",
            "replay_root_lineage",
            "cross_machine_root_lineage",
            "production_freeze_baseline",
            "refusal_first_semantics",
            "no_readiness_mutation",
            "no_approval_mutation",
            "manual_review_required",
        ],
    }

    scale_law_hash = _hash_json(scale_law)

    records: List[ScaleCertificationRecord] = []

    for target in SCALE_TARGETS:
        scale_input = {
            "target_evidence_count": target,
            "machine_b_verification_root": machine_b_verification_root,
            "production_freeze_root": production_freeze_root,
            "replay_root": replay_root,
            "cross_machine_root": cross_machine_root,
            "scale_law_hash": scale_law_hash,
        }

        scale_input_hash = _hash_json(scale_input)

        scale_certification_root = _hash_json(
            {
                "scale_status": status,
                "scale_target": target,
                "scale_input_hash": scale_input_hash,
                "scale_law_hash": scale_law_hash,
                "deterministic_ready": status == "SCALE_CERTIFICATION_CANDIDATE",
                "refusal_required": True,
            }
        )

        record = ScaleCertificationRecord(
            scale_id=f"SCALE_CERTIFICATION_{target}_{scale_certification_root[:16]}",
            scale_status=status,
            scale_target=target,
            machine_b_verification_root=machine_b_verification_root,
            production_freeze_root=production_freeze_root,
            replay_root=replay_root,
            cross_machine_root=cross_machine_root,
            scale_input_hash=scale_input_hash,
            scale_law_hash=scale_law_hash,
            scale_certification_root=scale_certification_root,
            deterministic_ready=status == "SCALE_CERTIFICATION_CANDIDATE",
            refusal_required=True,
            scale_certified=False,
            production_ready=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Scale certification candidate only. This creates deterministic scale "
                "law envelopes for future 10/100/1000/10000 evidence-case execution. "
                "It does not certify real scaled evidence volume yet."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    suite_root = _hash_json(
        {
            "suite_version": "scale_certification_suite_v1",
            "scale_law_hash": scale_law_hash,
            "scale_roots": [record.scale_certification_root for record in records],
        }
    )

    candidate_count = sum(
        1 for record in records if record.scale_status == "SCALE_CERTIFICATION_CANDIDATE"
    )

    summary = {
        "scale_record_count": len(records),
        "scale_candidate_count": candidate_count,
        "scale_blocked_count": len(records) - candidate_count,
        "scale_invalid_count": sum(
            1 for record in records if record.scale_status == "SCALE_CERTIFICATION_INVALID"
        ),
        "scale_targets": list(SCALE_TARGETS),
        "scale_law_hash": scale_law_hash,
        "scale_suite_root": suite_root,
        "machine_b_verification_root": machine_b_verification_root,
        "production_freeze_root": production_freeze_root,
        "replay_root": replay_root,
        "cross_machine_root": cross_machine_root,
        "deterministic_ready": candidate_count == len(records),
        "scale_certified": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PLAN_OUTPUT, scale_law)

    return {
        "payload": payload,
        "summary": summary,
        "scale_law": scale_law,
    }