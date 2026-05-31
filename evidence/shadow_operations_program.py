#!/usr/bin/env python3
"""
Shadow Operations Program Engine v1.

Builds a deterministic JSON-only longitudinal shadow operations program from
the completed Governance Runtime v1 evidence chain. This lane does not enable
live production, authorize release, approve evidence, or mark readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_PROJECT_COMPLETION = Path(
    "outputs/project_completion_certificate/project_completion_certificate_summary.json"
)
DEFAULT_FINAL_REPORT = Path(
    "outputs/final_governance_runtime_report/final_governance_runtime_report_summary.json"
)
DEFAULT_OPERATIONAL = Path(
    "outputs/operational_history_report/operational_history_report_summary.json"
)
DEFAULT_STRESS = Path("outputs/shadow_runtime_stress_suite/shadow_runtime_stress_summary.json")
DEFAULT_RUNTIME = Path("outputs/shadow_runtime_evidence/shadow_runtime_evidence_summary.json")
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_operations_program")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_operations_program_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_operations_program_summary.json"
PROGRAM_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_operations_program.json"

REQUIRED_PROGRAM_SECTIONS = (
    "program_objective",
    "operational_scope",
    "daily_shadow_cycle_plan",
    "weekly_reconciliation_plan",
    "drift_detection_plan",
    "refusal_collection_plan",
    "evidence_retention_plan",
    "promotion_criteria",
    "non_promotion_conditions",
    "remaining_manual_governance_actions",
)

ALLOWED_STATUSES = {
    "SHADOW_OPERATIONS_PROGRAM_CANDIDATE",
    "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS",
    "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS",
    "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "SHADOW_OPERATIONS_PROGRAM_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "live_production_enabled",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "notes_signed_with_real_key",
    "external_signature_present",
    "approved_evidence",
    "production_mutation_allowed",
    "secrets_in_evidence",
    "secrets_detected",
)


@dataclass
class ShadowOperationsProgramRecord:
    shadow_operations_id: str
    shadow_operations_status: str
    program_phase: str
    release_tag: str
    project_completion_root: str
    final_governance_runtime_report_root: str
    operational_history_report_root: str
    shadow_stress_root: str
    shadow_runtime_root: str
    approval_gate_root: str
    shadow_operations_program_hash: str
    shadow_operations_root: str
    shadow_operations_ready: bool
    baseline_shadow_cycles: int
    stress_cycles: int
    runtime_cycles: int
    stress_validation_complete: bool
    engineering_complete: bool
    final_reporting_complete: bool
    external_governance_pending: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    live_production_enabled: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    approved_evidence: int
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
    project_completion: Dict[str, Any],
    final_report: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    approval_gate: Dict[str, Any],
) -> str:
    if not project_completion:
        return "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_completion_status") != "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_phase") != "GOVERNANCE_RUNTIME_V1_COMPLETE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    for key in (
        "engineering_complete",
        "release_candidate_complete",
        "shadow_validation_complete",
        "stress_validation_complete",
        "final_reporting_complete",
        "external_governance_pending",
    ):
        if project_completion.get(key) is not True:
            return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("release_authorized") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _closed_release_flags(project_completion):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _is_nonzero_hash(project_completion.get("project_completion_certificate_root")):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"

    if not final_report:
        return "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("final_report_status") != "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("final_report_ready") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("tag_verified") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("external_signing_pending") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _closed_release_flags(final_report):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _is_nonzero_hash(final_report.get("final_governance_runtime_report_root")):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"

    if not operational:
        return "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT"
    if operational.get("operational_history_status") != "OPERATIONAL_HISTORY_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("operational_history_ready") is not True:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_shadow_cycles") != 11112:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_success_count") != 11112:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_failure_count") != 0 or operational.get("total_refusal_count") != 0:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("reconciliation_passed") is not True or operational.get("drift_detected") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _closed_release_flags(operational):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _is_nonzero_hash(operational.get("operational_history_report_root")):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"

    if not stress:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_status") != "SHADOW_RUNTIME_STRESS_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_targets") != [100, 1000, 10000]:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("total_shadow_cycles") != 11100 or stress.get("stress_success_count") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_refusal_count") != 0 or stress.get("stress_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("reconciliation_passed") is not True or stress.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("production_mutation_allowed") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _closed_release_flags(stress):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _is_nonzero_hash(stress.get("shadow_stress_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"

    if not runtime:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_runtime_status") != "SHADOW_RUNTIME_EVIDENCE_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_runtime_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_cycle_count") != 12 or runtime.get("shadow_success_count") != 12:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_refusal_count") != 0 or runtime.get("shadow_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("reconciliation_passed") is not True or runtime.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _closed_release_flags(runtime):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _is_nonzero_hash(runtime.get("shadow_runtime_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"

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

    return "SHADOW_OPERATIONS_PROGRAM_CANDIDATE"


def _build_program(
    status: str,
    release_tag: str,
    project_completion: Dict[str, Any],
    final_report: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    approval_gate: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "SHADOW_OPERATIONS_PROGRAM_CANDIDATE"
    return {
        "program_objective": {
            "program_phase": "LONGITUDINAL_SHADOW_OPERATIONS",
            "objective": (
                "Collect deterministic longitudinal shadow-operation evidence while "
                "production, release authorization, and public readiness remain closed."
            ),
            "shadow_operations_ready": ready,
        },
        "operational_scope": {
            "release_tag": release_tag,
            "engineering_complete": project_completion.get("engineering_complete") is True,
            "baseline_shadow_cycles": int(operational.get("total_shadow_cycles") or 0),
            "stress_cycles": int(stress.get("total_shadow_cycles") or 0),
            "runtime_cycles": int(runtime.get("shadow_cycle_count") or 0),
            "live_production_enabled": False,
            "production_ready": False,
        },
        "daily_shadow_cycle_plan": {
            "cycle_frequency": "daily",
            "minimum_shadow_cycles_per_day": 12,
            "source_roots_required": [
                "project_completion_certificate_root",
                "final_governance_runtime_report_root",
                "operational_history_report_root",
            ],
            "production_mutation_allowed": False,
        },
        "weekly_reconciliation_plan": {
            "reconciliation_frequency": "weekly",
            "required_result": "reconciliation_passed",
            "drift_detected_required_value": False,
            "failure_count_required_value": 0,
        },
        "drift_detection_plan": {
            "drift_signal_collection": True,
            "drift_detected_required_value": False,
            "drift_response": "block_promotion_and_emit_refusal_evidence",
        },
        "refusal_collection_plan": {
            "collect_refusals": True,
            "classify_refusal_reason": True,
            "production_refusal_required_without_manual_approval": True,
        },
        "evidence_retention_plan": {
            "retain_summary_roots": True,
            "retain_shadow_operation_summaries": True,
            "store_generated_outputs_outside_git": True,
            "secrets_in_evidence": False,
        },
        "promotion_criteria": [
            "external_manual_approval_artifact_present",
            "external_signature_evidence_present",
            "release_authorization_deliberately_recorded",
            "no_shadow_drift_detected",
            "no_live_production_mutation_without_authorization",
        ],
        "non_promotion_conditions": [
            "manual_approval_present_false",
            "external_signature_missing",
            "release_authorized_false",
            "production_ready_false",
            "drift_detected_true",
            "production_mutation_allowed_true",
            "secrets_detected_true",
        ],
        "remaining_manual_governance_actions": [
            "create_external_manual_approval_artifact",
            "sign_release_notes_with_external_key",
            "record_external_signature_evidence",
            "authorize_release_deliberately",
            "authorize_production_deployment_deliberately",
        ],
    }


def validate_program(program: Dict[str, Any]) -> None:
    if tuple(program.keys()) != REQUIRED_PROGRAM_SECTIONS:
        raise ValueError("shadow_operations_program must contain exactly the required sections")


def validate_record(record: ShadowOperationsProgramRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_operations_id",
        "shadow_operations_status",
        "program_phase",
        "release_tag",
        "project_completion_root",
        "final_governance_runtime_report_root",
        "operational_history_report_root",
        "shadow_stress_root",
        "shadow_runtime_root",
        "approval_gate_root",
        "shadow_operations_program_hash",
        "shadow_operations_root",
        "shadow_operations_ready",
        "baseline_shadow_cycles",
        "stress_cycles",
        "runtime_cycles",
        "stress_validation_complete",
        "engineering_complete",
        "final_reporting_complete",
        "external_governance_pending",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "live_production_enabled",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "approved_evidence",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ShadowOperationsProgramRecord missing fields: {sorted(missing)}")
    if data["shadow_operations_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_operations_status: {data['shadow_operations_status']}")
    if data["program_phase"] != "LONGITUDINAL_SHADOW_OPERATIONS":
        raise ValueError("program_phase must be LONGITUDINAL_SHADOW_OPERATIONS")
    if data["shadow_operations_status"] == "SHADOW_OPERATIONS_PROGRAM_CANDIDATE":
        for key in (
            "project_completion_root",
            "final_governance_runtime_report_root",
            "operational_history_report_root",
            "shadow_stress_root",
            "shadow_runtime_root",
            "approval_gate_root",
            "shadow_operations_program_hash",
            "shadow_operations_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["shadow_operations_ready"] is not True:
            raise ValueError("shadow_operations_ready must be true for candidate output")
        if data["baseline_shadow_cycles"] != 11112:
            raise ValueError("baseline_shadow_cycles must be 11112")
        if data["stress_cycles"] != 11100:
            raise ValueError("stress_cycles must be 11100")
        if data["runtime_cycles"] != 12:
            raise ValueError("runtime_cycles must be 12")
        for key in (
            "stress_validation_complete",
            "engineering_complete",
            "final_reporting_complete",
            "external_governance_pending",
        ):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for candidate output")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_operations_program(
    project_completion_path: Path = DEFAULT_PROJECT_COMPLETION,
    final_report_path: Path = DEFAULT_FINAL_REPORT,
    operational_path: Path = DEFAULT_OPERATIONAL,
    stress_path: Path = DEFAULT_STRESS,
    runtime_path: Path = DEFAULT_RUNTIME,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
) -> Dict[str, Any]:
    project_completion = _load_json(project_completion_path)
    final_report = _load_json(final_report_path)
    operational = _load_json(operational_path)
    stress = _load_json(stress_path)
    runtime = _load_json(runtime_path)
    approval_gate = _load_json(approval_gate_path)
    status = _determine_status(
        project_completion,
        final_report,
        operational,
        stress,
        runtime,
        approval_gate,
    )
    ready = status == "SHADOW_OPERATIONS_PROGRAM_CANDIDATE"
    release_tag = str(
        project_completion.get("release_tag")
        or final_report.get("release_candidate_tag")
        or operational.get("release_tag")
        or stress.get("release_tag")
        or ""
    )
    program = _build_program(
        status,
        release_tag,
        project_completion,
        final_report,
        operational,
        stress,
        runtime,
        approval_gate,
    )
    validate_program(program)
    program_hash = _hash_json(program)
    project_completion_root = str(project_completion.get("project_completion_certificate_root") or "")
    final_report_root = str(final_report.get("final_governance_runtime_report_root") or "")
    operational_root = str(operational.get("operational_history_report_root") or "")
    stress_root = str(stress.get("shadow_stress_root") or "")
    runtime_root = str(runtime.get("shadow_runtime_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")
    baseline_cycles = int(operational.get("total_shadow_cycles") or 0)
    stress_cycles = int(stress.get("total_shadow_cycles") or 0)
    runtime_cycles = int(runtime.get("shadow_cycle_count") or 0)
    root = _hash_json(
        {
            "shadow_operations_status": status,
            "program_phase": "LONGITUDINAL_SHADOW_OPERATIONS",
            "release_tag": release_tag,
            "shadow_operations_program_hash": program_hash,
            "project_completion_root": project_completion_root,
            "final_governance_runtime_report_root": final_report_root,
            "operational_history_report_root": operational_root,
            "shadow_stress_root": stress_root,
            "shadow_runtime_root": runtime_root,
            "approval_gate_root": approval_gate_root,
            "baseline_shadow_cycles": baseline_cycles,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "live_production_enabled": False,
        }
    )
    record = ShadowOperationsProgramRecord(
        shadow_operations_id=f"SHADOW_OPERATIONS_PROGRAM_{root[:16]}",
        shadow_operations_status=status,
        program_phase="LONGITUDINAL_SHADOW_OPERATIONS",
        release_tag=release_tag,
        project_completion_root=project_completion_root,
        final_governance_runtime_report_root=final_report_root,
        operational_history_report_root=operational_root,
        shadow_stress_root=stress_root,
        shadow_runtime_root=runtime_root,
        approval_gate_root=approval_gate_root,
        shadow_operations_program_hash=program_hash,
        shadow_operations_root=root,
        shadow_operations_ready=ready,
        baseline_shadow_cycles=baseline_cycles,
        stress_cycles=stress_cycles,
        runtime_cycles=runtime_cycles,
        stress_validation_complete=ready,
        engineering_complete=project_completion.get("engineering_complete") is True and ready,
        final_reporting_complete=project_completion.get("final_reporting_complete") is True and ready,
        external_governance_pending=True,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        live_production_enabled=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        approved_evidence=0,
        notes=(
            "Shadow Operations Program candidate only. Longitudinal shadow operations "
            "are planned without enabling live production or promoting readiness."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_operations_record_count": 1,
        "shadow_operations_candidate_count": 1 if ready else 0,
        "shadow_operations_blocked_count": 0 if ready else 1,
        "shadow_operations_status": status,
        "shadow_operations_ready": ready,
        "program_phase": "LONGITUDINAL_SHADOW_OPERATIONS",
        "release_tag": release_tag,
        "project_completion_root": project_completion_root,
        "final_governance_runtime_report_root": final_report_root,
        "operational_history_report_root": operational_root,
        "shadow_stress_root": stress_root,
        "shadow_runtime_root": runtime_root,
        "approval_gate_root": approval_gate_root,
        "shadow_operations_program_hash": program_hash,
        "shadow_operations_root": root,
        "baseline_shadow_cycles": baseline_cycles,
        "stress_cycles": stress_cycles,
        "runtime_cycles": runtime_cycles,
        "stress_validation_complete": ready,
        "engineering_complete": record.engineering_complete,
        "final_reporting_complete": record.final_reporting_complete,
        "external_governance_pending": True,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "live_production_enabled": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "approved_evidence": 0,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PROGRAM_OUTPUT, program)
    return {"payload": payload, "summary": summary, "program": program}
