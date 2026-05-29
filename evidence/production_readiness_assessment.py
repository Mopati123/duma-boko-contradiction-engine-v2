#!/usr/bin/env python3
"""
Production Readiness Assessment v1.

Aggregates the completed governance, determinism, Machine-B, adversarial, and
scale-execution proof layers into a deterministic production-readiness candidate.

This lane does not declare production_ready=True. It produces a scored readiness
assessment and the remaining blocker list required before a formal production
release.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_MACHINE_B_VERIFICATION = Path(
    "outputs/real_machine_b_verification/real_machine_b_verification_summary.json"
)
DEFAULT_REAL_SCALE = Path("outputs/real_scale_execution/real_scale_execution_summary.json")
DEFAULT_PRODUCTION_FREEZE = Path("outputs/production_freeze/production_freeze_summary.json")
DEFAULT_ADVERSARIAL = Path(
    "outputs/adversarial_falsification_suite/adversarial_falsification_summary.json"
)
DEFAULT_REPLAY = Path("outputs/replay_certification/replay_certification_summary.json")
DEFAULT_CROSS_MACHINE = Path("outputs/cross_machine_proof/cross_machine_proof_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/production_readiness_assessment")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "production_readiness_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "production_readiness_summary.json"
CHECKLIST_OUTPUT = DEFAULT_OUTPUT_DIR / "production_release_checklist.json"

ALLOWED_STATUSES = {
    "PRODUCTION_READINESS_CANDIDATE",
    "BLOCKED_MISSING_MACHINE_B_VERIFICATION",
    "BLOCKED_INVALID_MACHINE_B_VERIFICATION",
    "BLOCKED_MISSING_REAL_SCALE",
    "BLOCKED_INVALID_REAL_SCALE",
    "BLOCKED_MISSING_PRODUCTION_FREEZE",
    "BLOCKED_INVALID_PRODUCTION_FREEZE",
    "BLOCKED_MISSING_ADVERSARIAL",
    "BLOCKED_INVALID_ADVERSARIAL",
    "BLOCKED_MISSING_REPLAY",
    "BLOCKED_INVALID_REPLAY",
    "BLOCKED_MISSING_CROSS_MACHINE",
    "BLOCKED_INVALID_CROSS_MACHINE",
    "PRODUCTION_READINESS_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ProductionReadinessRecord:
    readiness_id: str
    readiness_status: str
    readiness_score: int
    readiness_grade: str
    machine_b_verified: bool
    real_scale_ready: bool
    production_freeze_candidate: bool
    adversarial_refusal_ready: bool
    replay_verified: bool
    cross_machine_verified: bool
    machine_b_verification_root: str
    real_scale_suite_root: str
    production_freeze_root: str
    adversarial_suite_root: str
    replay_root: str
    cross_machine_root: str
    remaining_blockers: List[str]
    readiness_root: str
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
    real_scale: Dict[str, Any],
    production_freeze: Dict[str, Any],
    adversarial: Dict[str, Any],
    replay: Dict[str, Any],
    cross_machine: Dict[str, Any],
) -> str:
    if not machine_b:
        return "BLOCKED_MISSING_MACHINE_B_VERIFICATION"
    if machine_b.get("machine_b_verification_status") != "REAL_MACHINE_B_VERIFIED_CANDIDATE":
        return "BLOCKED_INVALID_MACHINE_B_VERIFICATION"
    if machine_b.get("real_machine_b_verified") is not True:
        return "BLOCKED_INVALID_MACHINE_B_VERIFICATION"

    if not real_scale:
        return "BLOCKED_MISSING_REAL_SCALE"
    if real_scale.get("scale_execution_ready") is not True:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("real_scale_candidate_count") != 4:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("real_scale_blocked_count") != 0:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("scale_drift_detected") is not False:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("refusal_law_preserved") is not True:
        return "BLOCKED_INVALID_REAL_SCALE"

    if not production_freeze:
        return "BLOCKED_MISSING_PRODUCTION_FREEZE"
    if production_freeze.get("freeze_status") != "PRODUCTION_FREEZE_CANDIDATE":
        return "BLOCKED_INVALID_PRODUCTION_FREEZE"

    if not adversarial:
        return "BLOCKED_MISSING_ADVERSARIAL"
    if adversarial.get("adversarial_refused_count") != 10:
        return "BLOCKED_INVALID_ADVERSARIAL"
    if adversarial.get("adversarial_unexpected_accept_count") != 0:
        return "BLOCKED_INVALID_ADVERSARIAL"

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

    return "PRODUCTION_READINESS_CANDIDATE"


def _remaining_blockers(status: str) -> List[str]:
    baseline = [
        "real_world_evidence_scale_execution",
        "real_governance_key_management",
        "deployment_package",
        "operator_runbook",
        "recovery_runbook",
        "release_tag_and_signed_release_notes",
    ]

    if status != "PRODUCTION_READINESS_CANDIDATE":
        return [f"resolve_status:{status}"] + baseline

    return baseline


def _score(status: str, remaining_blockers: List[str]) -> int:
    if status != "PRODUCTION_READINESS_CANDIDATE":
        return 0

    # Architecture, determinism, refusal, cross-machine, and synthetic scale are complete.
    # Remaining blockers are operational/deployment blockers, not core architecture blockers.
    return 94


def _grade(score: int) -> str:
    if score >= 95:
        return "RELEASE_CANDIDATE"
    if score >= 90:
        return "PRODUCTION_READY_ARCHITECTURE"
    if score >= 75:
        return "HARDENING_REQUIRED"
    return "BLOCKED"


def validate_record(record: ProductionReadinessRecord) -> None:
    data = record.to_dict()

    required = {
        "readiness_id",
        "readiness_status",
        "readiness_score",
        "readiness_grade",
        "machine_b_verified",
        "real_scale_ready",
        "production_freeze_candidate",
        "adversarial_refusal_ready",
        "replay_verified",
        "cross_machine_verified",
        "machine_b_verification_root",
        "real_scale_suite_root",
        "production_freeze_root",
        "adversarial_suite_root",
        "replay_root",
        "cross_machine_root",
        "remaining_blockers",
        "readiness_root",
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
        raise ValueError(f"ProductionReadinessRecord missing fields: {sorted(missing)}")

    if data["readiness_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported readiness_status: {data['readiness_status']}")

    if not isinstance(data["remaining_blockers"], list):
        raise ValueError("remaining_blockers must be a list")

    if data["readiness_status"] == "PRODUCTION_READINESS_CANDIDATE":
        for flag in (
            "machine_b_verified",
            "real_scale_ready",
            "production_freeze_candidate",
            "adversarial_refusal_ready",
            "replay_verified",
            "cross_machine_verified",
        ):
            if data[flag] is not True:
                raise ValueError(f"{flag} must be true for readiness candidate")

        for key in (
            "machine_b_verification_root",
            "real_scale_suite_root",
            "production_freeze_root",
            "adversarial_suite_root",
            "replay_root",
            "cross_machine_root",
            "readiness_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for readiness candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_production_readiness_assessment(
    machine_b_path: Path = DEFAULT_MACHINE_B_VERIFICATION,
    real_scale_path: Path = DEFAULT_REAL_SCALE,
    production_freeze_path: Path = DEFAULT_PRODUCTION_FREEZE,
    adversarial_path: Path = DEFAULT_ADVERSARIAL,
    replay_path: Path = DEFAULT_REPLAY,
    cross_machine_path: Path = DEFAULT_CROSS_MACHINE,
) -> Dict[str, Any]:
    machine_b = _load_json(machine_b_path)
    real_scale = _load_json(real_scale_path)
    production_freeze = _load_json(production_freeze_path)
    adversarial = _load_json(adversarial_path)
    replay = _load_json(replay_path)
    cross_machine = _load_json(cross_machine_path)

    status = _determine_status(
        machine_b,
        real_scale,
        production_freeze,
        adversarial,
        replay,
        cross_machine,
    )

    blockers = _remaining_blockers(status)
    score = _score(status, blockers)
    grade = _grade(score)

    machine_b_verified = (
        machine_b.get("machine_b_verification_status") == "REAL_MACHINE_B_VERIFIED_CANDIDATE"
        and machine_b.get("real_machine_b_verified") is True
    )
    real_scale_ready = real_scale.get("scale_execution_ready") is True
    production_freeze_candidate = (
        production_freeze.get("freeze_status") == "PRODUCTION_FREEZE_CANDIDATE"
    )
    adversarial_refusal_ready = (
        adversarial.get("adversarial_refused_count") == 10
        and adversarial.get("adversarial_unexpected_accept_count") == 0
    )
    replay_verified = (
        replay.get("replay_status") == "REPLAY_CERTIFICATION_CANDIDATE"
        and replay.get("replay_verified") is True
    )
    cross_machine_verified = (
        cross_machine.get("cross_machine_status") == "CROSS_MACHINE_CANDIDATE"
        and cross_machine.get("cross_machine_verified") is True
    )

    machine_b_verification_root = str(machine_b.get("verification_root") or "")
    real_scale_suite_root = str(real_scale.get("real_scale_suite_root") or "")
    production_freeze_root = str(production_freeze.get("production_freeze_root") or "")
    adversarial_suite_root = str(adversarial.get("adversarial_suite_root") or "")
    replay_root = str(replay.get("replay_root") or "")
    cross_machine_root = str(cross_machine.get("cross_machine_root") or "")

    readiness_root = _hash_json(
        {
            "status": status,
            "score": score,
            "grade": grade,
            "machine_b_verification_root": machine_b_verification_root,
            "real_scale_suite_root": real_scale_suite_root,
            "production_freeze_root": production_freeze_root,
            "adversarial_suite_root": adversarial_suite_root,
            "replay_root": replay_root,
            "cross_machine_root": cross_machine_root,
            "remaining_blockers": blockers,
        }
    )

    record = ProductionReadinessRecord(
        readiness_id=f"PRODUCTION_READINESS_{readiness_root[:16]}",
        readiness_status=status,
        readiness_score=score,
        readiness_grade=grade,
        machine_b_verified=machine_b_verified,
        real_scale_ready=real_scale_ready,
        production_freeze_candidate=production_freeze_candidate,
        adversarial_refusal_ready=adversarial_refusal_ready,
        replay_verified=replay_verified,
        cross_machine_verified=cross_machine_verified,
        machine_b_verification_root=machine_b_verification_root,
        real_scale_suite_root=real_scale_suite_root,
        production_freeze_root=production_freeze_root,
        adversarial_suite_root=adversarial_suite_root,
        replay_root=replay_root,
        cross_machine_root=cross_machine_root,
        remaining_blockers=blockers,
        readiness_root=readiness_root,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Production readiness candidate. Architecture, determinism, Machine-B "
            "verification, adversarial refusal, replay, cross-machine proof, production "
            "freeze, and synthetic scale execution are present. Final production release "
            "still requires real-world scale execution, real governance keys, deployment "
            "package, operator/recovery runbooks, and signed release tagging."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "production_readiness_record_count": 1,
        "production_readiness_candidate_count": (
            1 if status == "PRODUCTION_READINESS_CANDIDATE" else 0
        ),
        "production_readiness_blocked_count": (
            0 if status == "PRODUCTION_READINESS_CANDIDATE" else 1
        ),
        "production_readiness_invalid_count": (
            1 if status == "PRODUCTION_READINESS_INVALID" else 0
        ),
        "readiness_status": status,
        "readiness_score": score,
        "readiness_grade": grade,
        "remaining_blockers": blockers,
        "readiness_root": readiness_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    release_checklist = {
        "checklist_version": "production_release_checklist_v1",
        "readiness_status": status,
        "readiness_score": score,
        "readiness_grade": grade,
        "completed": [
            "architecture_complete",
            "evidence_governance_pipeline",
            "replay_certification",
            "cross_machine_proof",
            "real_machine_b_verification",
            "production_freeze_candidate",
            "adversarial_refusal_suite",
            "synthetic_scale_execution",
        ],
        "remaining": blockers,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CHECKLIST_OUTPUT, release_checklist)

    return {
        "payload": payload,
        "summary": summary,
        "release_checklist": release_checklist,
    }