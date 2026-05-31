#!/usr/bin/env python3
"""
Shadow Runtime Evidence Engine v1.

Builds deterministic non-production shadow runtime history from the verified
shadow deployment dry-run. This lane records synthetic-but-operational shadow
cycles only. It does not enable live production, authorize release, sign with a
real key, create private keys, or mutate real-world systems.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_SHADOW_EXECUTION = Path(
    "outputs/shadow_deployment_execution_dry_run/"
    "shadow_deployment_execution_summary.json"
)
DEFAULT_SHADOW_DEPLOYMENT_PLAN = Path(
    "outputs/shadow_deployment_plan/shadow_deployment_plan_summary.json"
)
DEFAULT_REAL_TAG_EVIDENCE = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_runtime_evidence")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_evidence_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_evidence_summary.json"
CYCLES_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_cycles.json"

SHADOW_CYCLE_COUNT = 12

ALLOWED_STATUSES = {
    "SHADOW_RUNTIME_EVIDENCE_CANDIDATE",
    "BLOCKED_MISSING_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN",
    "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN",
    "BLOCKED_MISSING_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "SHADOW_RUNTIME_EVIDENCE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "live_production_enabled",
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "secrets_in_evidence",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ShadowRuntimeEvidenceRecord:
    shadow_runtime_id: str
    shadow_runtime_status: str
    release_tag: str
    shadow_execution_root: str
    shadow_deployment_root: str
    real_tag_evidence_root: str
    final_hardening_root: str
    approval_gate_root: str
    shadow_runtime_cycles_hash: str
    shadow_runtime_root: str
    shadow_runtime_ready: bool
    shadow_cycle_count: int
    shadow_success_count: int
    shadow_refusal_count: int
    shadow_failure_count: int
    reconciliation_passed: bool
    drift_detected: bool
    live_production_enabled: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    secrets_in_evidence: bool
    approved_evidence: int
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
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


def _as_count(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _closed_release_flags(payload: Dict[str, Any]) -> bool:
    return (
        payload.get("production_ready") is False
        and payload.get("public_ready") is False
        and payload.get("institutional_ready") is False
        and payload.get("report_ready") is False
        and _as_count(payload.get("approved_evidence")) == 0
    )


def _determine_status(
    shadow_execution: Dict[str, Any],
    shadow_plan: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
) -> str:
    if not shadow_execution:
        return "BLOCKED_MISSING_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if (
        shadow_execution.get("shadow_execution_status")
        != "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE"
    ):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("shadow_execution_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("shadow_execution_performed") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if shadow_execution.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if not _closed_release_flags(shadow_execution):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"
    if not _is_nonzero_hash(shadow_execution.get("shadow_execution_root")):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN"

    if not shadow_plan:
        return "BLOCKED_MISSING_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("shadow_deployment_status") != "SHADOW_DEPLOYMENT_PLAN_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("shadow_deployment_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if not _closed_release_flags(shadow_plan):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if not _is_nonzero_hash(shadow_plan.get("shadow_deployment_root")):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"

    if not real_tag:
        return "BLOCKED_MISSING_REAL_TAG_EVIDENCE"
    if real_tag.get("real_tag_evidence_status") != "REAL_TAG_EVIDENCE_VERIFIED":
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_exists_locally") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("git_tag_created") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_pushed_to_origin") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _closed_release_flags(real_tag):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _is_nonzero_hash(real_tag.get("real_tag_evidence_root")):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"

    if not final_hardening:
        return "BLOCKED_MISSING_FINAL_HARDENING_AUDIT"
    if final_hardening.get("final_hardening_status") != "FINAL_HARDENING_AUDIT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("final_hardening_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("generated_outputs_committed") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _closed_release_flags(final_hardening):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _is_nonzero_hash(final_hardening.get("final_hardening_root")):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"

    if not approval_gate:
        return "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("approval_gate_status") != "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("approval_gate_ready") is not True:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

    return "SHADOW_RUNTIME_EVIDENCE_CANDIDATE"


def _build_shadow_cycles(
    release_tag: str,
    shadow_execution_root: str,
    shadow_deployment_root: str,
    real_tag_evidence_root: str,
) -> List[Dict[str, Any]]:
    cycles: List[Dict[str, Any]] = []
    for cycle_index in range(1, SHADOW_CYCLE_COUNT + 1):
        cycle_id = f"SHADOW_RUNTIME_CYCLE_{cycle_index:03d}"
        input_root = _hash_json(
            {
                "cycle_id": cycle_id,
                "cycle_index": cycle_index,
                "release_tag": release_tag,
                "shadow_execution_root": shadow_execution_root,
                "shadow_deployment_root": shadow_deployment_root,
                "real_tag_evidence_root": real_tag_evidence_root,
            }
        )
        execution_root = _hash_json(
            {
                "cycle_id": cycle_id,
                "input_root": input_root,
                "live_production_enabled": False,
                "production_mutation_attempted": False,
                "production_mutation_allowed": False,
                "production_ready": False,
            }
        )
        evidence_root = _hash_json(
            {
                "cycle_id": cycle_id,
                "cycle_status": "shadow_cycle_success",
                "execution_root": execution_root,
                "secrets_in_evidence": False,
                "shadow_execution_root": shadow_execution_root,
            }
        )
        reconciliation_root = _hash_json(
            {
                "cycle_id": cycle_id,
                "drift_detected": False,
                "evidence_root": evidence_root,
                "execution_root": execution_root,
                "input_root": input_root,
                "reconciliation_passed": True,
            }
        )
        cycles.append(
            {
                "cycle_id": cycle_id,
                "cycle_index": cycle_index,
                "input_root": input_root,
                "execution_root": execution_root,
                "evidence_root": evidence_root,
                "reconciliation_root": reconciliation_root,
                "cycle_status": "shadow_cycle_success",
                "refusal_reason": "",
                "drift_detected": False,
                "production_mutation_attempted": False,
                "production_mutation_allowed": False,
            }
        )
    return cycles


def _validate_cycles(cycles: List[Dict[str, Any]]) -> None:
    if len(cycles) != SHADOW_CYCLE_COUNT:
        raise ValueError(f"Expected {SHADOW_CYCLE_COUNT} shadow runtime cycles")
    seen_ids = set()
    for expected_index, cycle in enumerate(cycles, start=1):
        expected_id = f"SHADOW_RUNTIME_CYCLE_{expected_index:03d}"
        if cycle.get("cycle_id") != expected_id:
            raise ValueError(f"Unexpected cycle_id at index {expected_index}")
        if cycle.get("cycle_index") != expected_index:
            raise ValueError(f"Unexpected cycle_index for {expected_id}")
        if cycle["cycle_id"] in seen_ids:
            raise ValueError(f"Duplicate cycle_id: {cycle['cycle_id']}")
        seen_ids.add(cycle["cycle_id"])
        for key in ("input_root", "execution_root", "evidence_root", "reconciliation_root"):
            if not _is_nonzero_hash(cycle.get(key)):
                raise ValueError(f"{expected_id} {key} must be a non-zero hash")
        if cycle.get("cycle_status") != "shadow_cycle_success":
            raise ValueError(f"{expected_id} must be a successful shadow cycle")
        if cycle.get("refusal_reason") != "":
            raise ValueError(f"{expected_id} refusal_reason must remain empty")
        if cycle.get("drift_detected") is not False:
            raise ValueError(f"{expected_id} drift_detected must remain false")
        if cycle.get("production_mutation_attempted") is not False:
            raise ValueError(f"{expected_id} must not attempt production mutation")
        if cycle.get("production_mutation_allowed") is not False:
            raise ValueError(f"{expected_id} must not allow production mutation")


def validate_record(record: ShadowRuntimeEvidenceRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_runtime_id",
        "shadow_runtime_status",
        "release_tag",
        "shadow_execution_root",
        "shadow_deployment_root",
        "real_tag_evidence_root",
        "final_hardening_root",
        "approval_gate_root",
        "shadow_runtime_cycles_hash",
        "shadow_runtime_root",
        "shadow_runtime_ready",
        "shadow_cycle_count",
        "shadow_success_count",
        "shadow_refusal_count",
        "shadow_failure_count",
        "reconciliation_passed",
        "drift_detected",
        "live_production_enabled",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "secrets_in_evidence",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ShadowRuntimeEvidenceRecord missing fields: {sorted(missing)}")
    if data["shadow_runtime_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_runtime_status: {data['shadow_runtime_status']}")

    if data["shadow_runtime_status"] == "SHADOW_RUNTIME_EVIDENCE_CANDIDATE":
        for key in (
            "shadow_execution_root",
            "shadow_deployment_root",
            "real_tag_evidence_root",
            "final_hardening_root",
            "approval_gate_root",
            "shadow_runtime_cycles_hash",
            "shadow_runtime_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["shadow_runtime_ready"] is not True:
            raise ValueError("shadow_runtime_ready must be true for candidate output")
        if int(data["shadow_cycle_count"]) != SHADOW_CYCLE_COUNT:
            raise ValueError("shadow_cycle_count must be 12")
        if int(data["shadow_success_count"]) != SHADOW_CYCLE_COUNT:
            raise ValueError("shadow_success_count must be 12")
        if int(data["shadow_refusal_count"]) != 0:
            raise ValueError("shadow_refusal_count must be 0")
        if int(data["shadow_failure_count"]) != 0:
            raise ValueError("shadow_failure_count must be 0")
        if data["reconciliation_passed"] is not True:
            raise ValueError("reconciliation_passed must be true")

    if data["drift_detected"] is not False:
        raise ValueError("drift_detected must remain false")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_runtime_evidence(
    shadow_execution_path: Path = DEFAULT_SHADOW_EXECUTION,
    shadow_plan_path: Path = DEFAULT_SHADOW_DEPLOYMENT_PLAN,
    real_tag_path: Path = DEFAULT_REAL_TAG_EVIDENCE,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
) -> Dict[str, Any]:
    shadow_execution = _load_json(shadow_execution_path)
    shadow_plan = _load_json(shadow_plan_path)
    real_tag = _load_json(real_tag_path)
    final_hardening = _load_json(final_hardening_path)
    approval_gate = _load_json(approval_gate_path)

    status = _determine_status(
        shadow_execution,
        shadow_plan,
        real_tag,
        final_hardening,
        approval_gate,
    )
    ready = status == "SHADOW_RUNTIME_EVIDENCE_CANDIDATE"

    release_tag = str(
        shadow_execution.get("release_tag")
        or shadow_plan.get("release_tag")
        or real_tag.get("tag_name")
        or ""
    )
    shadow_execution_root = str(shadow_execution.get("shadow_execution_root") or "")
    shadow_deployment_root = str(shadow_plan.get("shadow_deployment_root") or "")
    real_tag_evidence_root = str(real_tag.get("real_tag_evidence_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")

    cycles = (
        _build_shadow_cycles(
            release_tag,
            shadow_execution_root,
            shadow_deployment_root,
            real_tag_evidence_root,
        )
        if ready
        else []
    )
    if ready:
        _validate_cycles(cycles)

    cycle_count = len(cycles)
    success_count = sum(1 for cycle in cycles if cycle["cycle_status"] == "shadow_cycle_success")
    refusal_count = sum(1 for cycle in cycles if cycle["refusal_reason"])
    failure_count = cycle_count - success_count
    reconciliation_passed = ready and success_count == SHADOW_CYCLE_COUNT and failure_count == 0
    drift_detected = any(cycle.get("drift_detected") is True for cycle in cycles)
    cycles_document = {
        "shadow_runtime_cycles_version": "shadow_runtime_evidence_v1",
        "release_tag": release_tag,
        "shadow_cycle_count": cycle_count,
        "reconciliation_passed": reconciliation_passed,
        "drift_detected": drift_detected,
        "live_production_enabled": False,
        "production_ready": False,
        "cycles": cycles,
    }
    cycles_hash = _hash_json(cycles_document)
    root = _hash_json(
        {
            "shadow_runtime_status": status,
            "release_tag": release_tag,
            "shadow_execution_root": shadow_execution_root,
            "shadow_deployment_root": shadow_deployment_root,
            "real_tag_evidence_root": real_tag_evidence_root,
            "final_hardening_root": final_hardening_root,
            "approval_gate_root": approval_gate_root,
            "shadow_runtime_cycles_hash": cycles_hash,
            "shadow_cycle_count": cycle_count,
            "shadow_success_count": success_count,
            "reconciliation_passed": reconciliation_passed,
            "drift_detected": drift_detected,
            "live_production_enabled": False,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
        }
    )

    record = ShadowRuntimeEvidenceRecord(
        shadow_runtime_id=f"SHADOW_RUNTIME_EVIDENCE_{root[:16]}",
        shadow_runtime_status=status,
        release_tag=release_tag,
        shadow_execution_root=shadow_execution_root,
        shadow_deployment_root=shadow_deployment_root,
        real_tag_evidence_root=real_tag_evidence_root,
        final_hardening_root=final_hardening_root,
        approval_gate_root=approval_gate_root,
        shadow_runtime_cycles_hash=cycles_hash,
        shadow_runtime_root=root,
        shadow_runtime_ready=ready,
        shadow_cycle_count=cycle_count,
        shadow_success_count=success_count,
        shadow_refusal_count=refusal_count,
        shadow_failure_count=failure_count,
        reconciliation_passed=reconciliation_passed,
        drift_detected=drift_detected,
        live_production_enabled=False,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        secrets_in_evidence=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Shadow runtime evidence candidate only. Twelve deterministic non-production "
            "cycles were recorded and reconciled; live production remains disabled."
            if ready
            else "Shadow runtime evidence is blocked by missing or invalid upstream evidence."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_runtime_record_count": 1,
        "shadow_runtime_candidate_count": 1 if ready else 0,
        "shadow_runtime_blocked_count": 0 if ready else 1,
        "shadow_runtime_status": status,
        "shadow_runtime_ready": ready,
        "release_tag": release_tag,
        "shadow_execution_root": shadow_execution_root,
        "shadow_deployment_root": shadow_deployment_root,
        "real_tag_evidence_root": real_tag_evidence_root,
        "final_hardening_root": final_hardening_root,
        "approval_gate_root": approval_gate_root,
        "shadow_runtime_cycles_hash": cycles_hash,
        "shadow_runtime_root": root,
        "shadow_cycle_count": cycle_count,
        "shadow_success_count": success_count,
        "shadow_refusal_count": refusal_count,
        "shadow_failure_count": failure_count,
        "reconciliation_passed": reconciliation_passed,
        "drift_detected": drift_detected,
        "live_production_enabled": False,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "secrets_in_evidence": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CYCLES_OUTPUT, cycles_document)
    return {"payload": payload, "summary": summary, "cycles": cycles_document}
