#!/usr/bin/env python3
"""
Final Release Approval Gate Engine v1.

Builds a deterministic final approval gate from the completed release execution
checklist and release-candidate artifacts. This lane records that external
manual approval is required and absent. It does not create Git tags, sign
release notes, store secrets, authorize release, or mark production ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_RELEASE_EXECUTION = Path(
    "outputs/release_execution_checklist/release_execution_checklist_summary.json"
)
DEFAULT_RELEASE_TAG = Path("outputs/release_tag_and_signed_notes/release_tag_summary.json")
DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/final_release_approval_gate")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_release_approval_gate_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_release_approval_gate_summary.json"
REQUIREMENTS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_approval_requirements.json"

ALLOWED_STATUSES = {
    "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE",
    "BLOCKED_MISSING_RELEASE_EXECUTION_CHECKLIST",
    "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST",
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
    "FINAL_RELEASE_APPROVAL_GATE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "manual_approval_present",
    "release_authorized",
    "git_tag_created",
    "notes_signed_with_real_key",
    "secrets_in_evidence",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class FinalReleaseApprovalGateRecord:
    approval_gate_id: str
    approval_gate_status: str
    release_tag: str
    release_execution_root: str
    release_candidate_root: str
    recovery_runbook_root: str
    operator_runbook_root: str
    deployment_package_root: str
    key_management_root: str
    manual_approval_requirements_hash: str
    approval_gate_root: str
    approval_gate_ready: bool
    external_manual_approval_required: bool
    manual_approval_present: bool
    release_authorized: bool
    git_tag_created: bool
    notes_signed_with_real_key: bool
    secrets_in_evidence: bool
    production_ready: bool
    approved_evidence: bool
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


def _determine_status(
    release_execution: Dict[str, Any],
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
    if release_execution.get("manual_review_required") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("real_git_tag_required") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("external_signature_required") is not True:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("git_tag_created") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if release_execution.get("production_ready") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if not _is_nonzero_hash(release_execution.get("release_execution_root")):
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"

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
    if release_tag.get("production_ready") is not False:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _is_nonzero_hash(release_tag.get("release_candidate_root")):
        return "BLOCKED_INVALID_RELEASE_TAG"

    if not recovery:
        return "BLOCKED_MISSING_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_status") != "RECOVERY_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_ready") is not True:
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if not _is_nonzero_hash(recovery.get("recovery_runbook_root")):
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"

    if not operator:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if not _is_nonzero_hash(operator.get("operator_runbook_root")):
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not deployment:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if not _is_nonzero_hash(deployment.get("deployment_package_root")):
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if not _is_nonzero_hash(key_management.get("key_management_root")):
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    return "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE"


def _manual_approval_requirements(release_tag: str) -> Dict[str, Any]:
    requirements: List[Dict[str, Any]] = [
        {
            "requirement_id": "approver_identity_reference",
            "description": "A stable external reference to the human or authority approving release.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "approval_timestamp",
            "description": "The external approval timestamp recorded outside generated evidence.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "release_tag_confirmation",
            "description": f"Confirmation that the approved release tag is {release_tag}.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "external_signature_reference",
            "description": "A public reference or fingerprint for the externally signed release notes.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "tag_push_confirmation",
            "description": "Confirmation that the real Git tag was pushed after approval.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "artifact_archive_reference",
            "description": "External archive reference for release artifacts stored outside Git.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
        {
            "requirement_id": "no_secret_attestation",
            "description": "Attestation that no private keys or secrets are present in release evidence.",
            "required_before_authorization": True,
            "stores_secret": False,
        },
    ]

    return {
        "manual_approval_requirements_version": "final_release_approval_gate_v1",
        "release_tag": release_tag,
        "manual_approval_present": False,
        "release_authorized": False,
        "production_ready": False,
        "requirement_count": len(requirements),
        "requirements": requirements,
        "authorization_policy": {
            "self_authorization_allowed": False,
            "external_manual_approval_required": True,
            "real_git_tag_required": True,
            "external_signature_required": True,
            "production_ready_without_approval_allowed": False,
        },
        "secret_policy": {
            "private_keys_in_repo": False,
            "secrets_in_evidence": False,
            "secret_material_allowed_in_approval_artifact": False,
        },
    }


def validate_record(record: FinalReleaseApprovalGateRecord) -> None:
    data = record.to_dict()

    required = {
        "approval_gate_id",
        "approval_gate_status",
        "release_tag",
        "release_execution_root",
        "release_candidate_root",
        "recovery_runbook_root",
        "operator_runbook_root",
        "deployment_package_root",
        "key_management_root",
        "manual_approval_requirements_hash",
        "approval_gate_root",
        "approval_gate_ready",
        "external_manual_approval_required",
        "manual_approval_present",
        "release_authorized",
        "git_tag_created",
        "notes_signed_with_real_key",
        "secrets_in_evidence",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"FinalReleaseApprovalGateRecord missing fields: {sorted(missing)}")

    if data["approval_gate_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported approval_gate_status: {data['approval_gate_status']}")

    if data["approval_gate_status"] == "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE":
        for key in (
            "release_execution_root",
            "release_candidate_root",
            "recovery_runbook_root",
            "operator_runbook_root",
            "deployment_package_root",
            "key_management_root",
            "manual_approval_requirements_hash",
            "approval_gate_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["approval_gate_ready"] is not True:
            raise ValueError("approval_gate_ready must be true for candidate output")

    if data["external_manual_approval_required"] is not True:
        raise ValueError("external_manual_approval_required must remain true")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")


def build_final_release_approval_gate(
    release_execution_path: Path = DEFAULT_RELEASE_EXECUTION,
    release_tag_path: Path = DEFAULT_RELEASE_TAG,
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    release_execution = _load_json(release_execution_path)
    release_tag_summary = _load_json(release_tag_path)
    recovery = _load_json(recovery_path)
    operator = _load_json(operator_path)
    deployment = _load_json(deployment_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(
        release_execution,
        release_tag_summary,
        recovery,
        operator,
        deployment,
        key_management,
    )

    release_tag = str(release_tag_summary.get("release_tag") or "v1.0.0-rc1-governance-runtime")
    release_execution_root = str(release_execution.get("release_execution_root") or "")
    release_candidate_root = str(release_tag_summary.get("release_candidate_root") or "")
    recovery_root = str(recovery.get("recovery_runbook_root") or "")
    operator_root = str(operator.get("operator_runbook_root") or "")
    deployment_root = str(deployment.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    requirements = _manual_approval_requirements(release_tag)
    requirements_hash = _hash_json(requirements)
    approval_gate_root = _hash_json(
        {
            "approval_gate_status": status,
            "release_tag": release_tag,
            "release_execution_root": release_execution_root,
            "release_candidate_root": release_candidate_root,
            "recovery_runbook_root": recovery_root,
            "operator_runbook_root": operator_root,
            "deployment_package_root": deployment_root,
            "key_management_root": key_management_root,
            "manual_approval_requirements_hash": requirements_hash,
            "manual_approval_present": False,
            "release_authorized": False,
            "production_ready": False,
        }
    )
    ready = status == "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE"

    record = FinalReleaseApprovalGateRecord(
        approval_gate_id=f"FINAL_RELEASE_APPROVAL_GATE_{approval_gate_root[:16]}",
        approval_gate_status=status,
        release_tag=release_tag,
        release_execution_root=release_execution_root,
        release_candidate_root=release_candidate_root,
        recovery_runbook_root=recovery_root,
        operator_runbook_root=operator_root,
        deployment_package_root=deployment_root,
        key_management_root=key_management_root,
        manual_approval_requirements_hash=requirements_hash,
        approval_gate_root=approval_gate_root,
        approval_gate_ready=ready,
        external_manual_approval_required=True,
        manual_approval_present=False,
        release_authorized=False,
        git_tag_created=False,
        notes_signed_with_real_key=False,
        secrets_in_evidence=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Final release approval gate candidate only. The release path is structurally "
            "ready for external manual approval, but no real approval artifact is present."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}
    summary = {
        "approval_gate_record_count": 1,
        "approval_gate_candidate_count": 1 if ready else 0,
        "approval_gate_blocked_count": 0 if ready else 1,
        "approval_gate_invalid_count": 0,
        "approval_gate_status": status,
        "approval_gate_ready": ready,
        "release_tag": release_tag,
        "release_execution_root": release_execution_root,
        "release_candidate_root": release_candidate_root,
        "recovery_runbook_root": recovery_root,
        "operator_runbook_root": operator_root,
        "deployment_package_root": deployment_root,
        "key_management_root": key_management_root,
        "manual_approval_requirements_hash": requirements_hash,
        "approval_gate_root": approval_gate_root,
        "external_manual_approval_required": True,
        "manual_approval_present": False,
        "release_authorized": False,
        "git_tag_created": False,
        "notes_signed_with_real_key": False,
        "secrets_in_evidence": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(REQUIREMENTS_OUTPUT, requirements)

    return {
        "payload": payload,
        "summary": summary,
        "manual_approval_requirements": requirements,
    }
