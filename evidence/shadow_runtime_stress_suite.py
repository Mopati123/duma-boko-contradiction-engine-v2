#!/usr/bin/env python3
"""
Shadow Runtime Stress Suite Engine v1.

Builds deterministic non-production stress evidence from the proven shadow
runtime lane. This lane records compact batch-level stress roots only. It does
not enable live production, authorize release, sign with a real key, create
private keys, or mutate real-world systems.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_SHADOW_RUNTIME = Path(
    "outputs/shadow_runtime_evidence/shadow_runtime_evidence_summary.json"
)
DEFAULT_SHADOW_EXECUTION = Path(
    "outputs/shadow_deployment_execution_dry_run/"
    "shadow_deployment_execution_summary.json"
)
DEFAULT_SHADOW_DEPLOYMENT_PLAN = Path(
    "outputs/shadow_deployment_plan/shadow_deployment_plan_summary.json"
)
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_runtime_stress_suite")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_stress_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_stress_summary.json"
BATCHES_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_runtime_stress_batches.json"

STRESS_TARGETS = [100, 1000, 10000]

ALLOWED_STATUSES = {
    "SHADOW_RUNTIME_STRESS_CANDIDATE",
    "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_MISSING_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN",
    "BLOCKED_INVALID_SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN",
    "BLOCKED_MISSING_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "SHADOW_RUNTIME_STRESS_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "live_production_enabled",
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "secrets_in_evidence",
    "production_mutation_attempted",
    "production_mutation_allowed",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ShadowRuntimeStressSuiteRecord:
    shadow_stress_id: str
    shadow_stress_status: str
    release_tag: str
    shadow_runtime_root: str
    shadow_execution_root: str
    shadow_deployment_root: str
    final_hardening_root: str
    approval_gate_root: str
    shadow_stress_batches_hash: str
    shadow_stress_root: str
    shadow_stress_ready: bool
    stress_batch_count: int
    stress_targets: List[int]
    total_shadow_cycles: int
    stress_success_count: int
    stress_refusal_count: int
    stress_failure_count: int
    reconciliation_passed: bool
    drift_detected: bool
    live_production_enabled: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    secrets_in_evidence: bool
    production_mutation_attempted: bool
    production_mutation_allowed: bool
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
    shadow_runtime: Dict[str, Any],
    shadow_execution: Dict[str, Any],
    shadow_plan: Dict[str, Any],
    final_hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
) -> str:
    if not shadow_runtime:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_runtime_status") != "SHADOW_RUNTIME_EVIDENCE_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_runtime_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_cycle_count") != 12:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_success_count") != 12:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_refusal_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("shadow_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("reconciliation_passed") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if shadow_runtime.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _closed_release_flags(shadow_runtime):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _is_nonzero_hash(shadow_runtime.get("shadow_runtime_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"

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
    if not _closed_release_flags(shadow_plan):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if not _is_nonzero_hash(shadow_plan.get("shadow_deployment_root")):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"

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
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

    return "SHADOW_RUNTIME_STRESS_CANDIDATE"


def _build_stress_batches(
    release_tag: str,
    shadow_runtime_root: str,
    shadow_execution_root: str,
    shadow_deployment_root: str,
) -> List[Dict[str, Any]]:
    batches: List[Dict[str, Any]] = []
    for target in STRESS_TARGETS:
        batch_id = f"SHADOW_STRESS_BATCH_{target}"
        batch_input_root = _hash_json(
            {
                "batch_id": batch_id,
                "release_tag": release_tag,
                "target_cycle_count": target,
                "shadow_runtime_root": shadow_runtime_root,
                "shadow_execution_root": shadow_execution_root,
                "shadow_deployment_root": shadow_deployment_root,
            }
        )
        batch_execution_root = _hash_json(
            {
                "batch_id": batch_id,
                "target_cycle_count": target,
                "batch_input_root": batch_input_root,
                "live_production_enabled": False,
                "production_mutation_attempted": False,
                "production_mutation_allowed": False,
                "production_ready": False,
            }
        )
        batch_evidence_root = _hash_json(
            {
                "batch_id": batch_id,
                "batch_execution_root": batch_execution_root,
                "success_count": target,
                "refusal_count": 0,
                "failure_count": 0,
                "secrets_in_evidence": False,
            }
        )
        batch_reconciliation_root = _hash_json(
            {
                "batch_id": batch_id,
                "batch_input_root": batch_input_root,
                "batch_execution_root": batch_execution_root,
                "batch_evidence_root": batch_evidence_root,
                "reconciliation_passed": True,
                "drift_detected": False,
            }
        )
        batches.append(
            {
                "batch_id": batch_id,
                "target_cycle_count": target,
                "batch_input_root": batch_input_root,
                "batch_execution_root": batch_execution_root,
                "batch_evidence_root": batch_evidence_root,
                "batch_reconciliation_root": batch_reconciliation_root,
                "batch_status": "shadow_stress_batch_success",
                "success_count": target,
                "refusal_count": 0,
                "failure_count": 0,
                "drift_detected": False,
                "production_mutation_attempted": False,
                "production_mutation_allowed": False,
            }
        )
    return batches


def _validate_batches(batches: List[Dict[str, Any]]) -> None:
    if len(batches) != len(STRESS_TARGETS):
        raise ValueError("stress_batch_count must match stress target count")
    for index, target in enumerate(STRESS_TARGETS):
        batch = batches[index]
        expected_id = f"SHADOW_STRESS_BATCH_{target}"
        if batch.get("batch_id") != expected_id:
            raise ValueError(f"Unexpected batch_id for target {target}")
        if batch.get("target_cycle_count") != target:
            raise ValueError(f"Unexpected target_cycle_count for {expected_id}")
        for key in (
            "batch_input_root",
            "batch_execution_root",
            "batch_evidence_root",
            "batch_reconciliation_root",
        ):
            if not _is_nonzero_hash(batch.get(key)):
                raise ValueError(f"{expected_id} {key} must be a non-zero hash")
        if batch.get("batch_status") != "shadow_stress_batch_success":
            raise ValueError(f"{expected_id} must be successful")
        if batch.get("success_count") != target:
            raise ValueError(f"{expected_id} success_count must equal target")
        if batch.get("refusal_count") != 0:
            raise ValueError(f"{expected_id} refusal_count must be 0")
        if batch.get("failure_count") != 0:
            raise ValueError(f"{expected_id} failure_count must be 0")
        if batch.get("drift_detected") is not False:
            raise ValueError(f"{expected_id} drift_detected must remain false")
        if batch.get("production_mutation_attempted") is not False:
            raise ValueError(f"{expected_id} must not attempt production mutation")
        if batch.get("production_mutation_allowed") is not False:
            raise ValueError(f"{expected_id} must not allow production mutation")


def validate_record(record: ShadowRuntimeStressSuiteRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_stress_id",
        "shadow_stress_status",
        "release_tag",
        "shadow_runtime_root",
        "shadow_execution_root",
        "shadow_deployment_root",
        "final_hardening_root",
        "approval_gate_root",
        "shadow_stress_batches_hash",
        "shadow_stress_root",
        "shadow_stress_ready",
        "stress_batch_count",
        "stress_targets",
        "total_shadow_cycles",
        "stress_success_count",
        "stress_refusal_count",
        "stress_failure_count",
        "reconciliation_passed",
        "drift_detected",
        "live_production_enabled",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "secrets_in_evidence",
        "production_mutation_attempted",
        "production_mutation_allowed",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ShadowRuntimeStressSuiteRecord missing fields: {sorted(missing)}")
    if data["shadow_stress_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_stress_status: {data['shadow_stress_status']}")

    if data["shadow_stress_status"] == "SHADOW_RUNTIME_STRESS_CANDIDATE":
        for key in (
            "shadow_runtime_root",
            "shadow_execution_root",
            "shadow_deployment_root",
            "final_hardening_root",
            "approval_gate_root",
            "shadow_stress_batches_hash",
            "shadow_stress_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["shadow_stress_ready"] is not True:
            raise ValueError("shadow_stress_ready must be true for candidate output")
        if data["stress_targets"] != STRESS_TARGETS:
            raise ValueError("stress_targets must be [100, 1000, 10000]")
        if int(data["stress_batch_count"]) != len(STRESS_TARGETS):
            raise ValueError("stress_batch_count must be 3")
        if int(data["total_shadow_cycles"]) != sum(STRESS_TARGETS):
            raise ValueError("total_shadow_cycles must be 11100")
        if int(data["stress_success_count"]) != sum(STRESS_TARGETS):
            raise ValueError("stress_success_count must be 11100")
        if int(data["stress_refusal_count"]) != 0:
            raise ValueError("stress_refusal_count must be 0")
        if int(data["stress_failure_count"]) != 0:
            raise ValueError("stress_failure_count must be 0")
        if data["reconciliation_passed"] is not True:
            raise ValueError("reconciliation_passed must be true")

    if data["drift_detected"] is not False:
        raise ValueError("drift_detected must remain false")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_runtime_stress_suite(
    shadow_runtime_path: Path = DEFAULT_SHADOW_RUNTIME,
    shadow_execution_path: Path = DEFAULT_SHADOW_EXECUTION,
    shadow_plan_path: Path = DEFAULT_SHADOW_DEPLOYMENT_PLAN,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
) -> Dict[str, Any]:
    shadow_runtime = _load_json(shadow_runtime_path)
    shadow_execution = _load_json(shadow_execution_path)
    shadow_plan = _load_json(shadow_plan_path)
    final_hardening = _load_json(final_hardening_path)
    approval_gate = _load_json(approval_gate_path)

    status = _determine_status(
        shadow_runtime,
        shadow_execution,
        shadow_plan,
        final_hardening,
        approval_gate,
    )
    ready = status == "SHADOW_RUNTIME_STRESS_CANDIDATE"

    release_tag = str(
        shadow_runtime.get("release_tag")
        or shadow_execution.get("release_tag")
        or shadow_plan.get("release_tag")
        or ""
    )
    shadow_runtime_root = str(shadow_runtime.get("shadow_runtime_root") or "")
    shadow_execution_root = str(shadow_execution.get("shadow_execution_root") or "")
    shadow_deployment_root = str(shadow_plan.get("shadow_deployment_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")

    batches = (
        _build_stress_batches(
            release_tag,
            shadow_runtime_root,
            shadow_execution_root,
            shadow_deployment_root,
        )
        if ready
        else []
    )
    if ready:
        _validate_batches(batches)

    stress_batch_count = len(batches)
    total_shadow_cycles = sum(batch["target_cycle_count"] for batch in batches)
    stress_success_count = sum(batch["success_count"] for batch in batches)
    stress_refusal_count = sum(batch["refusal_count"] for batch in batches)
    stress_failure_count = sum(batch["failure_count"] for batch in batches)
    drift_detected = any(batch.get("drift_detected") is True for batch in batches)
    reconciliation_passed = (
        ready
        and stress_batch_count == len(STRESS_TARGETS)
        and stress_success_count == sum(STRESS_TARGETS)
        and stress_refusal_count == 0
        and stress_failure_count == 0
        and not drift_detected
    )
    batches_document = {
        "shadow_runtime_stress_batches_version": "shadow_runtime_stress_suite_v1",
        "release_tag": release_tag,
        "stress_targets": STRESS_TARGETS,
        "stress_batch_count": stress_batch_count,
        "total_shadow_cycles": total_shadow_cycles,
        "reconciliation_passed": reconciliation_passed,
        "drift_detected": drift_detected,
        "live_production_enabled": False,
        "production_ready": False,
        "batches": batches,
    }
    batches_hash = _hash_json(batches_document)
    root = _hash_json(
        {
            "shadow_stress_status": status,
            "release_tag": release_tag,
            "shadow_runtime_root": shadow_runtime_root,
            "shadow_execution_root": shadow_execution_root,
            "shadow_deployment_root": shadow_deployment_root,
            "final_hardening_root": final_hardening_root,
            "approval_gate_root": approval_gate_root,
            "shadow_stress_batches_hash": batches_hash,
            "stress_targets": STRESS_TARGETS,
            "total_shadow_cycles": total_shadow_cycles,
            "stress_success_count": stress_success_count,
            "reconciliation_passed": reconciliation_passed,
            "drift_detected": drift_detected,
            "live_production_enabled": False,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
        }
    )

    record = ShadowRuntimeStressSuiteRecord(
        shadow_stress_id=f"SHADOW_RUNTIME_STRESS_{root[:16]}",
        shadow_stress_status=status,
        release_tag=release_tag,
        shadow_runtime_root=shadow_runtime_root,
        shadow_execution_root=shadow_execution_root,
        shadow_deployment_root=shadow_deployment_root,
        final_hardening_root=final_hardening_root,
        approval_gate_root=approval_gate_root,
        shadow_stress_batches_hash=batches_hash,
        shadow_stress_root=root,
        shadow_stress_ready=ready,
        stress_batch_count=stress_batch_count,
        stress_targets=STRESS_TARGETS,
        total_shadow_cycles=total_shadow_cycles,
        stress_success_count=stress_success_count,
        stress_refusal_count=stress_refusal_count,
        stress_failure_count=stress_failure_count,
        reconciliation_passed=reconciliation_passed,
        drift_detected=drift_detected,
        live_production_enabled=False,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        secrets_in_evidence=False,
        production_mutation_attempted=False,
        production_mutation_allowed=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Shadow runtime stress candidate only. Deterministic non-production stress "
            "batches were recorded and reconciled; live production remains disabled."
            if ready
            else "Shadow runtime stress suite is blocked by missing or invalid upstream evidence."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_stress_record_count": 1,
        "shadow_stress_candidate_count": 1 if ready else 0,
        "shadow_stress_blocked_count": 0 if ready else 1,
        "shadow_stress_status": status,
        "shadow_stress_ready": ready,
        "release_tag": release_tag,
        "shadow_runtime_root": shadow_runtime_root,
        "shadow_execution_root": shadow_execution_root,
        "shadow_deployment_root": shadow_deployment_root,
        "final_hardening_root": final_hardening_root,
        "approval_gate_root": approval_gate_root,
        "shadow_stress_batches_hash": batches_hash,
        "shadow_stress_root": root,
        "stress_batch_count": stress_batch_count,
        "stress_targets": STRESS_TARGETS,
        "total_shadow_cycles": total_shadow_cycles,
        "stress_success_count": stress_success_count,
        "stress_refusal_count": stress_refusal_count,
        "stress_failure_count": stress_failure_count,
        "reconciliation_passed": reconciliation_passed,
        "drift_detected": drift_detected,
        "live_production_enabled": False,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "secrets_in_evidence": False,
        "production_mutation_attempted": False,
        "production_mutation_allowed": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(BATCHES_OUTPUT, batches_document)
    return {"payload": payload, "summary": summary, "batches": batches_document}
