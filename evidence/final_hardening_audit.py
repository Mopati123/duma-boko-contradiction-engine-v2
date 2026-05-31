#!/usr/bin/env python3
"""
Final Hardening Audit Engine v1.

Builds a deterministic final hardening audit before manual release. This lane
confirms the release chain remains structurally ready while production stays
blocked until external manual approval, real tag creation, external signing,
tag push, archival, and shadow deployment happen outside this engine.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import subprocess


DEFAULT_RELEASE_EXECUTION = Path(
    "outputs/release_execution_checklist/release_execution_checklist_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_RELEASE_TAG = Path("outputs/release_tag_and_signed_notes/release_tag_summary.json")
DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/final_hardening_audit")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_hardening_audit_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_hardening_audit_summary.json"
CHECKLIST_OUTPUT = DEFAULT_OUTPUT_DIR / "final_hardening_checklist.json"

REMAINING_MANUAL_ACTIONS = [
    "create_external_manual_approval_artifact",
    "create_real_git_tag",
    "sign_release_notes_with_external_key",
    "push_release_tag",
    "archive_release_artifacts_outside_git",
    "begin_shadow_deployment",
]

ALLOWED_STATUSES = {
    "FINAL_HARDENING_AUDIT_CANDIDATE",
    "BLOCKED_MISSING_RELEASE_EXECUTION_CHECKLIST",
    "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_MISSING_RELEASE_TAG",
    "BLOCKED_INVALID_RELEASE_TAG",
    "BLOCKED_MISSING_RECOVERY_RUNBOOK",
    "BLOCKED_INVALID_RECOVERY_RUNBOOK",
    "BLOCKED_MISSING_OPERATOR_RUNBOOK",
    "BLOCKED_INVALID_OPERATOR_RUNBOOK",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "BLOCKED_SECRETS_DETECTED",
    "BLOCKED_GENERATED_OUTPUTS_COMMITTED",
    "FINAL_HARDENING_AUDIT_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "manual_approval_present",
    "release_authorized",
    "production_ready",
    "secrets_detected",
    "generated_outputs_committed",
    "git_tag_created",
    "notes_signed_with_real_key",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

RELEASE_OUTPUT_DIRS = (
    "outputs/release_tag_and_signed_notes/",
    "outputs/release_execution_checklist/",
    "outputs/final_release_approval_gate/",
    "outputs/final_hardening_audit/",
)


@dataclass
class FinalHardeningAuditRecord:
    final_hardening_id: str
    final_hardening_status: str
    release_tag: str
    release_execution_root: str
    approval_gate_root: str
    release_candidate_root: str
    recovery_runbook_root: str
    operator_runbook_root: str
    deployment_package_root: str
    key_management_root: str
    final_hardening_checklist_hash: str
    final_hardening_root: str
    final_hardening_ready: bool
    release_candidate_ready: bool
    approval_gate_ready: bool
    manual_approval_present: bool
    release_authorized: bool
    production_ready: bool
    secrets_detected: bool
    generated_outputs_committed: bool
    git_tag_created: bool
    notes_signed_with_real_key: bool
    approved_evidence: int
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    remaining_manual_actions: List[str]
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


def _has_closed_release_flags(payload: Dict[str, Any]) -> bool:
    return (
        payload.get("production_ready") is False
        and payload.get("public_ready") is False
        and payload.get("institutional_ready") is False
        and payload.get("report_ready") is False
        and _as_count(payload.get("approved_evidence")) == 0
    )


def _secrets_detected(
    release_execution: Dict[str, Any],
    approval_gate: Dict[str, Any],
    key_management: Dict[str, Any],
) -> bool:
    return any(
        item.get("secrets_in_evidence") is not False
        for item in (release_execution, approval_gate, key_management)
        if item
    ) or key_management.get("private_keys_generated") is True


def _generated_outputs_committed() -> bool:
    tracked_outputs = _load_tracked_files()
    return any(
        path.startswith(prefix)
        for path in tracked_outputs
        for prefix in RELEASE_OUTPUT_DIRS
    )


def _load_tracked_files() -> List[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _determine_status(
    release_execution: Dict[str, Any],
    approval_gate: Dict[str, Any],
    release_tag: Dict[str, Any],
    recovery: Dict[str, Any],
    operator: Dict[str, Any],
    deployment: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
    if not release_execution:
        return "BLOCKED_MISSING_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("release_execution_status") != "RELEASE_EXECUTION_CHECKLIST_CANDIDATE":
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("release_execution_ready") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("git_tag_created") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if not _has_closed_release_flags(release_execution):
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if not _is_nonzero_hash(release_execution.get("release_execution_root")):
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"

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
    if approval_gate.get("git_tag_created") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _has_closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

    if not release_tag:
        return "BLOCKED_MISSING_RELEASE_TAG"
    if release_tag.get("release_status") != "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE":
        return "BLOCKED_INVALID_RELEASE_TAG"
    if release_tag.get("release_candidate_ready") is not True:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if release_tag.get("git_tag_created") is not False:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if release_tag.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _has_closed_release_flags(release_tag):
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _is_nonzero_hash(release_tag.get("release_candidate_root")):
        return "BLOCKED_INVALID_RELEASE_TAG"

    if not recovery:
        return "BLOCKED_MISSING_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_status") != "RECOVERY_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_ready") is not True:
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _has_closed_release_flags(recovery):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _is_nonzero_hash(recovery.get("recovery_runbook_root")):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"

    if not operator:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _has_closed_release_flags(operator):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _is_nonzero_hash(operator.get("operator_runbook_root")):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not deployment:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _has_closed_release_flags(deployment):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _is_nonzero_hash(deployment.get("deployment_package_root")):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("private_keys_generated") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _has_closed_release_flags(key_management):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _is_nonzero_hash(key_management.get("key_management_root")):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    if _secrets_detected(release_execution, approval_gate, key_management):
        return "BLOCKED_SECRETS_DETECTED"

    if _generated_outputs_committed():
        return "BLOCKED_GENERATED_OUTPUTS_COMMITTED"

    return "FINAL_HARDENING_AUDIT_CANDIDATE"


def _final_hardening_checklist(release_tag: str) -> Dict[str, Any]:
    return {
        "final_hardening_checklist_version": "final_hardening_audit_v1",
        "release_tag": release_tag,
        "remaining_manual_actions": REMAINING_MANUAL_ACTIONS,
        "hardening_assertions": {
            "manual_approval_present": False,
            "release_authorized": False,
            "production_ready": False,
            "secrets_detected": False,
            "generated_outputs_committed": False,
            "approved_evidence": 0,
        },
        "secret_scan_model": {
            "policy_mentions_are_not_secrets": True,
            "actual_secret_material_allowed": False,
            "private_key_material_allowed": False,
            "private_signing_allowed": False,
        },
        "generated_output_policy": {
            "new_generated_outputs_committed": False,
            "release_lane_outputs_ignored": True,
            "historical_tracked_fixtures_preserved": True,
        },
    }


def validate_record(record: FinalHardeningAuditRecord) -> None:
    data = record.to_dict()

    required = {
        "final_hardening_id",
        "final_hardening_status",
        "release_tag",
        "release_execution_root",
        "approval_gate_root",
        "release_candidate_root",
        "recovery_runbook_root",
        "operator_runbook_root",
        "deployment_package_root",
        "key_management_root",
        "final_hardening_checklist_hash",
        "final_hardening_root",
        "final_hardening_ready",
        "release_candidate_ready",
        "approval_gate_ready",
        "manual_approval_present",
        "release_authorized",
        "production_ready",
        "secrets_detected",
        "generated_outputs_committed",
        "git_tag_created",
        "notes_signed_with_real_key",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "remaining_manual_actions",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"FinalHardeningAuditRecord missing fields: {sorted(missing)}")

    if data["final_hardening_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported final_hardening_status: {data['final_hardening_status']}")

    if data["final_hardening_status"] == "FINAL_HARDENING_AUDIT_CANDIDATE":
        for key in (
            "release_execution_root",
            "approval_gate_root",
            "release_candidate_root",
            "recovery_runbook_root",
            "operator_runbook_root",
            "deployment_package_root",
            "key_management_root",
            "final_hardening_checklist_hash",
            "final_hardening_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["final_hardening_ready"] is not True:
            raise ValueError("final_hardening_ready must be true for candidate output")
        if data["release_candidate_ready"] is not True:
            raise ValueError("release_candidate_ready must be true for candidate output")
        if data["approval_gate_ready"] is not True:
            raise ValueError("approval_gate_ready must be true for candidate output")

    if data["remaining_manual_actions"] != REMAINING_MANUAL_ACTIONS:
        raise ValueError("remaining_manual_actions do not match required final manual actions")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_final_hardening_audit(
    release_execution_path: Path = DEFAULT_RELEASE_EXECUTION,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    release_tag_path: Path = DEFAULT_RELEASE_TAG,
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    release_execution = _load_json(release_execution_path)
    approval_gate = _load_json(approval_gate_path)
    release_tag_summary = _load_json(release_tag_path)
    recovery = _load_json(recovery_path)
    operator = _load_json(operator_path)
    deployment = _load_json(deployment_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(
        release_execution,
        approval_gate,
        release_tag_summary,
        recovery,
        operator,
        deployment,
        key_management,
    )

    release_tag = str(release_tag_summary.get("release_tag") or "v1.0.0-rc1-governance-runtime")
    release_execution_root = str(release_execution.get("release_execution_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")
    release_candidate_root = str(release_tag_summary.get("release_candidate_root") or "")
    recovery_root = str(recovery.get("recovery_runbook_root") or "")
    operator_root = str(operator.get("operator_runbook_root") or "")
    deployment_root = str(deployment.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    secrets_detected = _secrets_detected(release_execution, approval_gate, key_management)
    generated_outputs_committed = _generated_outputs_committed()
    checklist = _final_hardening_checklist(release_tag)
    checklist_hash = _hash_json(checklist)
    final_hardening_root = _hash_json(
        {
            "final_hardening_status": status,
            "release_tag": release_tag,
            "release_execution_root": release_execution_root,
            "approval_gate_root": approval_gate_root,
            "release_candidate_root": release_candidate_root,
            "recovery_runbook_root": recovery_root,
            "operator_runbook_root": operator_root,
            "deployment_package_root": deployment_root,
            "key_management_root": key_management_root,
            "final_hardening_checklist_hash": checklist_hash,
            "remaining_manual_actions": REMAINING_MANUAL_ACTIONS,
            "manual_approval_present": False,
            "release_authorized": False,
            "production_ready": False,
            "secrets_detected": secrets_detected,
            "generated_outputs_committed": generated_outputs_committed,
        }
    )
    ready = status == "FINAL_HARDENING_AUDIT_CANDIDATE"

    record = FinalHardeningAuditRecord(
        final_hardening_id=f"FINAL_HARDENING_AUDIT_{final_hardening_root[:16]}",
        final_hardening_status=status,
        release_tag=release_tag,
        release_execution_root=release_execution_root,
        approval_gate_root=approval_gate_root,
        release_candidate_root=release_candidate_root,
        recovery_runbook_root=recovery_root,
        operator_runbook_root=operator_root,
        deployment_package_root=deployment_root,
        key_management_root=key_management_root,
        final_hardening_checklist_hash=checklist_hash,
        final_hardening_root=final_hardening_root,
        final_hardening_ready=ready,
        release_candidate_ready=release_tag_summary.get("release_candidate_ready") is True,
        approval_gate_ready=approval_gate.get("approval_gate_ready") is True,
        manual_approval_present=False,
        release_authorized=False,
        production_ready=False,
        secrets_detected=secrets_detected,
        generated_outputs_committed=generated_outputs_committed,
        git_tag_created=False,
        notes_signed_with_real_key=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        remaining_manual_actions=REMAINING_MANUAL_ACTIONS,
        notes=(
            "Final hardening audit candidate only. Manual approval, real tag creation, "
            "external signing, tag push, artifact archival, and shadow deployment remain."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}
    summary = {
        "final_hardening_record_count": 1,
        "final_hardening_candidate_count": 1 if ready else 0,
        "final_hardening_blocked_count": 0 if ready else 1,
        "final_hardening_invalid_count": 0,
        "final_hardening_status": status,
        "final_hardening_ready": ready,
        "release_tag": release_tag,
        "release_execution_root": release_execution_root,
        "approval_gate_root": approval_gate_root,
        "release_candidate_root": release_candidate_root,
        "recovery_runbook_root": recovery_root,
        "operator_runbook_root": operator_root,
        "deployment_package_root": deployment_root,
        "key_management_root": key_management_root,
        "final_hardening_checklist_hash": checklist_hash,
        "final_hardening_root": final_hardening_root,
        "release_candidate_ready": release_tag_summary.get("release_candidate_ready") is True,
        "approval_gate_ready": approval_gate.get("approval_gate_ready") is True,
        "manual_approval_present": False,
        "release_authorized": False,
        "production_ready": False,
        "secrets_detected": secrets_detected,
        "generated_outputs_committed": generated_outputs_committed,
        "remaining_manual_actions": REMAINING_MANUAL_ACTIONS,
        "git_tag_created": False,
        "notes_signed_with_real_key": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CHECKLIST_OUTPUT, checklist)

    return {
        "payload": payload,
        "summary": summary,
        "final_hardening_checklist": checklist,
    }
