#!/usr/bin/env python3
"""
Institutional Readiness Report Engine v1.

Builds a deterministic JSON-only institutional readiness report candidate from
the release governance chain. This lane can report structural readiness, but it
does not mark institutional_ready, production_ready, public_ready, or report_ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_OPERATIONAL_HISTORY = Path(
    "outputs/operational_history_report/operational_history_report_summary.json"
)
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_RELEASE_EXECUTION = Path(
    "outputs/release_execution_checklist/release_execution_checklist_summary.json"
)
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/institutional_readiness_report")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "institutional_readiness_report_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "institutional_readiness_report_summary.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "institutional_readiness_report.json"

ALLOWED_STATUSES = {
    "INSTITUTIONAL_READINESS_REPORT_CANDIDATE",
    "BLOCKED_MISSING_OPERATIONAL_HISTORY",
    "BLOCKED_INVALID_OPERATIONAL_HISTORY",
    "BLOCKED_MISSING_FINAL_HARDENING",
    "BLOCKED_INVALID_FINAL_HARDENING",
    "BLOCKED_MISSING_APPROVAL_GATE",
    "BLOCKED_INVALID_APPROVAL_GATE",
    "BLOCKED_MISSING_RELEASE_EXECUTION",
    "BLOCKED_INVALID_RELEASE_EXECUTION",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_RECOVERY_RUNBOOK",
    "BLOCKED_INVALID_RECOVERY_RUNBOOK",
    "BLOCKED_MISSING_OPERATOR_RUNBOOK",
    "BLOCKED_INVALID_OPERATOR_RUNBOOK",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "INSTITUTIONAL_READINESS_REPORT_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "institutional_ready",
    "production_ready",
    "public_ready",
    "report_ready",
    "release_authorized",
    "manual_approval_present",
    "secrets_in_evidence",
    "approved_evidence",
)


@dataclass
class InstitutionalReadinessReportRecord:
    institutional_report_id: str
    institutional_report_status: str
    release_tag: str
    operational_history_root: str
    final_hardening_root: str
    approval_gate_root: str
    release_execution_root: str
    deployment_package_root: str
    recovery_runbook_root: str
    operator_runbook_root: str
    key_management_root: str
    institutional_readiness_report_hash: str
    institutional_readiness_report_root: str
    institutional_report_ready: bool
    architecture_ready: bool
    governance_ready: bool
    release_process_ready: bool
    recovery_ready: bool
    operational_history_ready: bool
    manual_approval_present: bool
    release_authorized: bool
    institutional_ready: bool
    production_ready: bool
    public_ready: bool
    report_ready: bool
    secrets_in_evidence: bool
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
    operational: Dict[str, Any],
    hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
    release_execution: Dict[str, Any],
    deployment: Dict[str, Any],
    recovery: Dict[str, Any],
    operator: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
    if not operational:
        return "BLOCKED_MISSING_OPERATIONAL_HISTORY"
    if operational.get("operational_history_status") != "OPERATIONAL_HISTORY_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY"
    if operational.get("operational_history_ready") is not True:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY"
    if operational.get("reconciliation_passed") is not True or operational.get("drift_detected") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY"
    if not _closed_release_flags(operational) or not _is_nonzero_hash(operational.get("operational_history_report_root")):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY"

    if not hardening:
        return "BLOCKED_MISSING_FINAL_HARDENING"
    if hardening.get("final_hardening_status") != "FINAL_HARDENING_AUDIT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if hardening.get("final_hardening_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if hardening.get("manual_approval_present") is not False or hardening.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if hardening.get("secrets_detected") is not False or hardening.get("generated_outputs_committed") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if not _closed_release_flags(hardening) or not _is_nonzero_hash(hardening.get("final_hardening_root")):
        return "BLOCKED_INVALID_FINAL_HARDENING"

    if not approval_gate:
        return "BLOCKED_MISSING_APPROVAL_GATE"
    if approval_gate.get("approval_gate_status") != "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE":
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("approval_gate_ready") is not True:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("manual_approval_present") is not False or approval_gate.get("release_authorized") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate) or not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_APPROVAL_GATE"

    if not release_execution:
        return "BLOCKED_MISSING_RELEASE_EXECUTION"
    if release_execution.get("release_execution_status") != "RELEASE_EXECUTION_CHECKLIST_CANDIDATE":
        return "BLOCKED_INVALID_RELEASE_EXECUTION"
    if release_execution.get("release_execution_ready") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION"
    if release_execution.get("manual_review_required") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION"
    if release_execution.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION"
    if not _closed_release_flags(release_execution) or not _is_nonzero_hash(release_execution.get("release_execution_root")):
        return "BLOCKED_INVALID_RELEASE_EXECUTION"

    if not deployment:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _closed_release_flags(deployment) or not _is_nonzero_hash(deployment.get("deployment_package_root")):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not recovery:
        return "BLOCKED_MISSING_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_status") != "RECOVERY_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_ready") is not True:
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _closed_release_flags(recovery) or not _is_nonzero_hash(recovery.get("recovery_runbook_root")):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"

    if not operator:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _closed_release_flags(operator) or not _is_nonzero_hash(operator.get("operator_runbook_root")):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False or key_management.get("private_keys_generated") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _closed_release_flags(key_management) or not _is_nonzero_hash(key_management.get("key_management_root")):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    return "INSTITUTIONAL_READINESS_REPORT_CANDIDATE"


def _build_report(
    release_tag: str,
    status: str,
    operational: Dict[str, Any],
    hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
    release_execution: Dict[str, Any],
    deployment: Dict[str, Any],
    recovery: Dict[str, Any],
    operator: Dict[str, Any],
    key_management: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "INSTITUTIONAL_READINESS_REPORT_CANDIDATE"
    return {
        "institutional_readiness_report_version": "institutional_readiness_report_v1",
        "institutional_report_status": status,
        "release_tag": release_tag,
        "readiness_dimensions": {
            "architecture_ready": ready,
            "governance_ready": ready,
            "release_process_ready": ready,
            "recovery_ready": ready,
            "operational_history_ready": ready,
        },
        "source_roots": {
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "deployment_package_root": str(deployment.get("deployment_package_root") or ""),
            "final_hardening_root": str(hardening.get("final_hardening_root") or ""),
            "key_management_root": str(key_management.get("key_management_root") or ""),
            "operational_history_root": str(operational.get("operational_history_report_root") or ""),
            "operator_runbook_root": str(operator.get("operator_runbook_root") or ""),
            "recovery_runbook_root": str(recovery.get("recovery_runbook_root") or ""),
            "release_execution_root": str(release_execution.get("release_execution_root") or ""),
        },
        "closed_flags": {
            "approved_evidence": 0,
            "institutional_ready": False,
            "manual_approval_present": False,
            "production_ready": False,
            "public_ready": False,
            "release_authorized": False,
            "report_ready": False,
            "secrets_in_evidence": False,
        },
    }


def validate_record(record: InstitutionalReadinessReportRecord) -> None:
    data = record.to_dict()
    required = {
        "institutional_report_id",
        "institutional_report_status",
        "release_tag",
        "operational_history_root",
        "final_hardening_root",
        "approval_gate_root",
        "release_execution_root",
        "deployment_package_root",
        "recovery_runbook_root",
        "operator_runbook_root",
        "key_management_root",
        "institutional_readiness_report_hash",
        "institutional_readiness_report_root",
        "institutional_report_ready",
        "architecture_ready",
        "governance_ready",
        "release_process_ready",
        "recovery_ready",
        "operational_history_ready",
        "manual_approval_present",
        "release_authorized",
        "institutional_ready",
        "production_ready",
        "public_ready",
        "report_ready",
        "secrets_in_evidence",
        "approved_evidence",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"InstitutionalReadinessReportRecord missing fields: {sorted(missing)}")
    if data["institutional_report_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported institutional_report_status: {data['institutional_report_status']}")
    if data["institutional_report_status"] == "INSTITUTIONAL_READINESS_REPORT_CANDIDATE":
        for key in (
            "operational_history_root",
            "final_hardening_root",
            "approval_gate_root",
            "release_execution_root",
            "deployment_package_root",
            "recovery_runbook_root",
            "operator_runbook_root",
            "key_management_root",
            "institutional_readiness_report_hash",
            "institutional_readiness_report_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        for key in (
            "institutional_report_ready",
            "architecture_ready",
            "governance_ready",
            "release_process_ready",
            "recovery_ready",
            "operational_history_ready",
        ):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for candidate output")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_institutional_readiness_report(
    operational_path: Path = DEFAULT_OPERATIONAL_HISTORY,
    hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    release_execution_path: Path = DEFAULT_RELEASE_EXECUTION,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    operational = _load_json(operational_path)
    hardening = _load_json(hardening_path)
    approval_gate = _load_json(approval_gate_path)
    release_execution = _load_json(release_execution_path)
    deployment = _load_json(deployment_path)
    recovery = _load_json(recovery_path)
    operator = _load_json(operator_path)
    key_management = _load_json(key_management_path)
    status = _determine_status(
        operational,
        hardening,
        approval_gate,
        release_execution,
        deployment,
        recovery,
        operator,
        key_management,
    )
    ready = status == "INSTITUTIONAL_READINESS_REPORT_CANDIDATE"
    release_tag = str(operational.get("release_tag") or release_execution.get("release_tag") or "")
    report = _build_report(
        release_tag,
        status,
        operational,
        hardening,
        approval_gate,
        release_execution,
        deployment,
        recovery,
        operator,
        key_management,
    )
    report_hash = _hash_json(report)
    root = _hash_json(
        {
            "institutional_report_status": status,
            "release_tag": release_tag,
            "institutional_readiness_report_hash": report_hash,
            "operational_history_root": str(operational.get("operational_history_report_root") or ""),
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "institutional_ready": False,
            "production_ready": False,
        }
    )
    record = InstitutionalReadinessReportRecord(
        institutional_report_id=f"INSTITUTIONAL_READINESS_REPORT_{root[:16]}",
        institutional_report_status=status,
        release_tag=release_tag,
        operational_history_root=str(operational.get("operational_history_report_root") or ""),
        final_hardening_root=str(hardening.get("final_hardening_root") or ""),
        approval_gate_root=str(approval_gate.get("approval_gate_root") or ""),
        release_execution_root=str(release_execution.get("release_execution_root") or ""),
        deployment_package_root=str(deployment.get("deployment_package_root") or ""),
        recovery_runbook_root=str(recovery.get("recovery_runbook_root") or ""),
        operator_runbook_root=str(operator.get("operator_runbook_root") or ""),
        key_management_root=str(key_management.get("key_management_root") or ""),
        institutional_readiness_report_hash=report_hash,
        institutional_readiness_report_root=root,
        institutional_report_ready=ready,
        architecture_ready=ready,
        governance_ready=ready,
        release_process_ready=ready,
        recovery_ready=ready,
        operational_history_ready=ready,
        manual_approval_present=False,
        release_authorized=False,
        institutional_ready=False,
        production_ready=False,
        public_ready=False,
        report_ready=False,
        secrets_in_evidence=False,
        approved_evidence=0,
        notes=(
            "Institutional readiness report candidate only. Structural readiness is "
            "summarized, but institutional_ready and production_ready remain false."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "institutional_report_record_count": 1,
        "institutional_report_candidate_count": 1 if ready else 0,
        "institutional_report_blocked_count": 0 if ready else 1,
        "institutional_report_status": status,
        "institutional_report_ready": ready,
        "release_tag": release_tag,
        "operational_history_root": record.operational_history_root,
        "final_hardening_root": record.final_hardening_root,
        "approval_gate_root": record.approval_gate_root,
        "release_execution_root": record.release_execution_root,
        "deployment_package_root": record.deployment_package_root,
        "recovery_runbook_root": record.recovery_runbook_root,
        "operator_runbook_root": record.operator_runbook_root,
        "key_management_root": record.key_management_root,
        "institutional_readiness_report_hash": report_hash,
        "institutional_readiness_report_root": root,
        "architecture_ready": ready,
        "governance_ready": ready,
        "release_process_ready": ready,
        "recovery_ready": ready,
        "operational_history_ready": ready,
        "manual_approval_present": False,
        "release_authorized": False,
        "institutional_ready": False,
        "production_ready": False,
        "public_ready": False,
        "report_ready": False,
        "secrets_in_evidence": False,
        "approved_evidence": 0,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(REPORT_OUTPUT, report)
    return {"payload": payload, "summary": summary, "report": report}
