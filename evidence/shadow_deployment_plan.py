#!/usr/bin/env python3
"""
Shadow Deployment Plan Engine v1.

Builds a deterministic non-production shadow deployment plan from the verified
release candidate evidence. This lane prepares dry-run commands only. It does
not enable live production, authorize release, sign with a real key, create
private keys, or mark production ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_REAL_TAG_EVIDENCE = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_MANUAL_RELEASE_EXECUTION = Path(
    "outputs/manual_release_execution_plan/manual_release_execution_plan_summary.json"
)
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_deployment_plan")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_deployment_plan_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_deployment_plan_summary.json"
PLAN_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_deployment_commands.json"

ALLOWED_STATUSES = {
    "SHADOW_DEPLOYMENT_PLAN_CANDIDATE",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_MANUAL_RELEASE_EXECUTION_PLAN",
    "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_OPERATOR_RUNBOOK",
    "BLOCKED_INVALID_OPERATOR_RUNBOOK",
    "BLOCKED_MISSING_RECOVERY_RUNBOOK",
    "BLOCKED_INVALID_RECOVERY_RUNBOOK",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "SHADOW_DEPLOYMENT_PLAN_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "live_production_enabled",
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "notes_signed_with_real_key",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ShadowDeploymentPlanRecord:
    shadow_deployment_id: str
    shadow_deployment_status: str
    release_tag: str
    real_tag_evidence_root: str
    manual_release_execution_root: str
    final_hardening_root: str
    approval_gate_root: str
    deployment_package_root: str
    operator_runbook_root: str
    recovery_runbook_root: str
    key_management_root: str
    shadow_deployment_commands_hash: str
    shadow_deployment_root: str
    shadow_deployment_ready: bool
    live_production_enabled: bool
    production_ready: bool
    manual_approval_required: bool
    external_signature_required: bool
    release_authorized: bool
    manual_approval_present: bool
    notes_signed_with_real_key: bool
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
    real_tag: Dict[str, Any],
    manual_execution: Dict[str, Any],
    final_hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
    deployment: Dict[str, Any],
    operator: Dict[str, Any],
    recovery: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
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

    if not manual_execution:
        return "BLOCKED_MISSING_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("manual_release_execution_status") != "MANUAL_RELEASE_EXECUTION_PLAN_CANDIDATE":
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("manual_release_execution_ready") is not True:
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("shadow_deployment_command_prepared") is not True:
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if manual_execution.get("release_authorized") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if not _closed_release_flags(manual_execution):
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"
    if not _is_nonzero_hash(manual_execution.get("manual_release_execution_root")):
        return "BLOCKED_INVALID_MANUAL_RELEASE_EXECUTION_PLAN"

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
    if not _closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

    if not deployment:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _closed_release_flags(deployment):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _is_nonzero_hash(deployment.get("deployment_package_root")):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not operator:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _closed_release_flags(operator):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _is_nonzero_hash(operator.get("operator_runbook_root")):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not recovery:
        return "BLOCKED_MISSING_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_status") != "RECOVERY_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_ready") is not True:
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _closed_release_flags(recovery):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _is_nonzero_hash(recovery.get("recovery_runbook_root")):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("private_keys_generated") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _closed_release_flags(key_management):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _is_nonzero_hash(key_management.get("key_management_root")):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    return "SHADOW_DEPLOYMENT_PLAN_CANDIDATE"


def _shadow_commands() -> Dict[str, Any]:
    commands = [
        "git checkout master",
        "git pull origin master",
        "git status",
        "python scripts/build_real_governance_key_management.py --dry-run",
        "python scripts/build_deployment_package.py --dry-run",
        "python scripts/build_operator_runbook.py --dry-run",
        "python scripts/build_recovery_runbook.py --dry-run",
        "python scripts/build_release_tag_and_signed_notes.py --dry-run",
        "python scripts/build_release_execution_checklist.py --dry-run",
        "python scripts/build_final_release_approval_gate.py --dry-run",
        "python scripts/build_final_hardening_audit.py --dry-run",
        "python scripts/build_manual_release_artifact.py --dry-run",
        "python scripts/build_manual_release_execution_plan.py --dry-run",
        "python scripts/build_real_tag_evidence.py --dry-run",
        "python scripts/build_external_signing_evidence_template.py --dry-run",
        "python scripts/build_shadow_deployment_plan.py --dry-run",
    ]
    return {
        "shadow_deployment_plan_version": "shadow_deployment_plan_v1",
        "commands_are_non_production_only": True,
        "live_production_enabled": False,
        "production_ready": False,
        "manual_approval_required": True,
        "external_signature_required": True,
        "commands": commands,
    }


def validate_record(record: ShadowDeploymentPlanRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_deployment_id",
        "shadow_deployment_status",
        "release_tag",
        "real_tag_evidence_root",
        "manual_release_execution_root",
        "final_hardening_root",
        "approval_gate_root",
        "deployment_package_root",
        "operator_runbook_root",
        "recovery_runbook_root",
        "key_management_root",
        "shadow_deployment_commands_hash",
        "shadow_deployment_root",
        "shadow_deployment_ready",
        "live_production_enabled",
        "production_ready",
        "manual_approval_required",
        "external_signature_required",
        "release_authorized",
        "manual_approval_present",
        "notes_signed_with_real_key",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ShadowDeploymentPlanRecord missing fields: {sorted(missing)}")
    if data["shadow_deployment_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_deployment_status: {data['shadow_deployment_status']}")
    if data["shadow_deployment_status"] == "SHADOW_DEPLOYMENT_PLAN_CANDIDATE":
        for key in (
            "real_tag_evidence_root",
            "manual_release_execution_root",
            "final_hardening_root",
            "approval_gate_root",
            "deployment_package_root",
            "operator_runbook_root",
            "recovery_runbook_root",
            "key_management_root",
            "shadow_deployment_commands_hash",
            "shadow_deployment_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["shadow_deployment_ready"] is not True:
            raise ValueError("shadow_deployment_ready must be true for candidate output")
    if data["manual_approval_required"] is not True:
        raise ValueError("manual_approval_required must remain true")
    if data["external_signature_required"] is not True:
        raise ValueError("external_signature_required must remain true")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_deployment_plan(
    real_tag_path: Path = DEFAULT_REAL_TAG_EVIDENCE,
    manual_execution_path: Path = DEFAULT_MANUAL_RELEASE_EXECUTION,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    real_tag = _load_json(real_tag_path)
    manual_execution = _load_json(manual_execution_path)
    final_hardening = _load_json(final_hardening_path)
    approval_gate = _load_json(approval_gate_path)
    deployment = _load_json(deployment_path)
    operator = _load_json(operator_path)
    recovery = _load_json(recovery_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(
        real_tag,
        manual_execution,
        final_hardening,
        approval_gate,
        deployment,
        operator,
        recovery,
        key_management,
    )

    release_tag = str(real_tag.get("tag_name") or manual_execution.get("release_tag") or "")
    real_tag_root = str(real_tag.get("real_tag_evidence_root") or "")
    manual_execution_root = str(manual_execution.get("manual_release_execution_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")
    deployment_root = str(deployment.get("deployment_package_root") or "")
    operator_root = str(operator.get("operator_runbook_root") or "")
    recovery_root = str(recovery.get("recovery_runbook_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")
    commands = _shadow_commands()
    commands_hash = _hash_json(commands)
    root = _hash_json(
        {
            "shadow_deployment_status": status,
            "release_tag": release_tag,
            "real_tag_evidence_root": real_tag_root,
            "manual_release_execution_root": manual_execution_root,
            "final_hardening_root": final_hardening_root,
            "approval_gate_root": approval_gate_root,
            "deployment_package_root": deployment_root,
            "operator_runbook_root": operator_root,
            "recovery_runbook_root": recovery_root,
            "key_management_root": key_management_root,
            "shadow_deployment_commands_hash": commands_hash,
            "live_production_enabled": False,
            "production_ready": False,
        }
    )
    ready = status == "SHADOW_DEPLOYMENT_PLAN_CANDIDATE"

    record = ShadowDeploymentPlanRecord(
        shadow_deployment_id=f"SHADOW_DEPLOYMENT_PLAN_{root[:16]}",
        shadow_deployment_status=status,
        release_tag=release_tag,
        real_tag_evidence_root=real_tag_root,
        manual_release_execution_root=manual_execution_root,
        final_hardening_root=final_hardening_root,
        approval_gate_root=approval_gate_root,
        deployment_package_root=deployment_root,
        operator_runbook_root=operator_root,
        recovery_runbook_root=recovery_root,
        key_management_root=key_management_root,
        shadow_deployment_commands_hash=commands_hash,
        shadow_deployment_root=root,
        shadow_deployment_ready=ready,
        live_production_enabled=False,
        production_ready=False,
        manual_approval_required=True,
        external_signature_required=True,
        release_authorized=False,
        manual_approval_present=False,
        notes_signed_with_real_key=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Shadow deployment plan candidate only. Commands are non-production dry runs; "
            "live production remains disabled."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_deployment_record_count": 1,
        "shadow_deployment_candidate_count": 1 if ready else 0,
        "shadow_deployment_blocked_count": 0 if ready else 1,
        "shadow_deployment_status": status,
        "shadow_deployment_ready": ready,
        "release_tag": release_tag,
        "real_tag_evidence_root": real_tag_root,
        "manual_release_execution_root": manual_execution_root,
        "final_hardening_root": final_hardening_root,
        "approval_gate_root": approval_gate_root,
        "deployment_package_root": deployment_root,
        "operator_runbook_root": operator_root,
        "recovery_runbook_root": recovery_root,
        "key_management_root": key_management_root,
        "shadow_deployment_commands_hash": commands_hash,
        "shadow_deployment_root": root,
        "live_production_enabled": False,
        "production_ready": False,
        "manual_approval_required": True,
        "external_signature_required": True,
        "release_authorized": False,
        "manual_approval_present": False,
        "notes_signed_with_real_key": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PLAN_OUTPUT, commands)
    return {"payload": payload, "summary": summary, "commands": commands}
