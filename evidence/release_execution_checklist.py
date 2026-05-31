#!/usr/bin/env python3
"""
Release Execution Checklist Engine v1.

Builds a deterministic, manual-only release execution checklist from the
completed release-candidate architecture. This lane does not create Git tags,
does not sign notes, does not use private keys, and does not authorize
production.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_RELEASE_TAG = Path("outputs/release_tag_and_signed_notes/release_tag_summary.json")
DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/release_execution_checklist")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "release_execution_checklist_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "release_execution_checklist_summary.json"
MANUAL_STEPS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_release_steps.json"

ALLOWED_STATUSES = {
    "RELEASE_EXECUTION_CHECKLIST_CANDIDATE",
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
    "RELEASE_EXECUTION_CHECKLIST_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
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
class ReleaseExecutionChecklistRecord:
    release_execution_id: str
    release_execution_status: str
    release_tag: str
    release_candidate_root: str
    recovery_runbook_root: str
    operator_runbook_root: str
    deployment_package_root: str
    key_management_root: str
    manual_release_steps_hash: str
    release_execution_root: str
    release_execution_ready: bool
    manual_review_required: bool
    real_git_tag_required: bool
    external_signature_required: bool
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


def _candidate_status(
    release_tag: Dict[str, Any],
    recovery: Dict[str, Any],
    operator: Dict[str, Any],
    deployment: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
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

    return "RELEASE_EXECUTION_CHECKLIST_CANDIDATE"


def _manual_release_steps(release_tag: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = [
        {
            "step_number": 1,
            "step_id": "confirm_clean_master",
            "instruction": "Confirm local master is checked out and the working tree is clean.",
            "command_hint": "git checkout master && git status",
            "external_manual_action_required": False,
            "stores_secret": False,
        },
        {
            "step_number": 2,
            "step_id": "confirm_origin_master_synced",
            "instruction": "Confirm local master and origin/master point to the same commit.",
            "command_hint": "git fetch origin && git status && git rev-parse master origin/master",
            "external_manual_action_required": False,
            "stores_secret": False,
        },
        {
            "step_number": 3,
            "step_id": "run_full_dry_run_chain",
            "instruction": "Run the full release dry-run chain from a clean tree.",
            "command_hint": "run documented dry-run builders through release tag and signed notes",
            "external_manual_action_required": False,
            "stores_secret": False,
        },
        {
            "step_number": 4,
            "step_id": "inspect_release_candidate_summary",
            "instruction": "Inspect release candidate summary and confirm candidate readiness only.",
            "command_hint": "python -m json.tool outputs/release_tag_and_signed_notes/release_tag_summary.json",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
        {
            "step_number": 5,
            "step_id": "create_real_git_tag_manually",
            "instruction": f"Create real Git tag {release_tag} manually after external approval.",
            "command_hint": f"git tag -a {release_tag} -m <approved release message>",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
        {
            "step_number": 6,
            "step_id": "sign_release_notes_with_external_key_manually",
            "instruction": "Sign release notes manually with an external key outside the repository.",
            "command_hint": "use external signing workflow; do not commit private key material",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
        {
            "step_number": 7,
            "step_id": "push_tag_manually",
            "instruction": "Push the manually created release tag after signature verification.",
            "command_hint": f"git push origin {release_tag}",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
        {
            "step_number": 8,
            "step_id": "archive_release_artifacts_outside_git",
            "instruction": "Archive release artifacts outside Git in the approved artifact store.",
            "command_hint": "use external artifact archive; do not commit generated artifacts",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
        {
            "step_number": 9,
            "step_id": "record_final_release_evidence_without_secrets",
            "instruction": "Record final release evidence without secrets or private key material.",
            "command_hint": "record public hashes, tag, signer identity reference, and approval metadata only",
            "external_manual_action_required": True,
            "stores_secret": False,
        },
    ]

    return {
        "manual_release_steps_version": "release_execution_checklist_v1",
        "release_tag": release_tag,
        "step_count": len(steps),
        "steps": steps,
        "secret_policy": {
            "private_keys_in_repo": False,
            "secrets_in_evidence": False,
            "external_signature_required": True,
        },
        "production_authorization": {
            "self_authorized": False,
            "production_ready": False,
            "manual_external_approval_required": True,
        },
    }


def validate_record(record: ReleaseExecutionChecklistRecord) -> None:
    data = record.to_dict()

    required = {
        "release_execution_id",
        "release_execution_status",
        "release_tag",
        "release_candidate_root",
        "recovery_runbook_root",
        "operator_runbook_root",
        "deployment_package_root",
        "key_management_root",
        "manual_release_steps_hash",
        "release_execution_root",
        "release_execution_ready",
        "manual_review_required",
        "real_git_tag_required",
        "external_signature_required",
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
        raise ValueError(f"ReleaseExecutionChecklistRecord missing fields: {sorted(missing)}")

    if data["release_execution_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported release_execution_status: {data['release_execution_status']}")

    if data["release_execution_status"] == "RELEASE_EXECUTION_CHECKLIST_CANDIDATE":
        for key in (
            "release_candidate_root",
            "recovery_runbook_root",
            "operator_runbook_root",
            "deployment_package_root",
            "key_management_root",
            "manual_release_steps_hash",
            "release_execution_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["release_execution_ready"] is not True:
            raise ValueError("release_execution_ready must be true for candidate output")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    for flag in ("manual_review_required", "real_git_tag_required", "external_signature_required"):
        if data.get(flag) is not True:
            raise ValueError(f"{flag} must remain true")


def build_release_execution_checklist(
    release_tag_path: Path = DEFAULT_RELEASE_TAG,
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    release_tag_summary = _load_json(release_tag_path)
    recovery = _load_json(recovery_path)
    operator = _load_json(operator_path)
    deployment = _load_json(deployment_path)
    key_management = _load_json(key_management_path)

    status = _candidate_status(
        release_tag_summary,
        recovery,
        operator,
        deployment,
        key_management,
    )

    release_tag = str(release_tag_summary.get("release_tag") or "v1.0.0-rc1-governance-runtime")
    release_candidate_root = str(release_tag_summary.get("release_candidate_root") or "")
    recovery_root = str(recovery.get("recovery_runbook_root") or "")
    operator_root = str(operator.get("operator_runbook_root") or "")
    deployment_root = str(deployment.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    manual_steps = _manual_release_steps(release_tag)
    manual_steps_hash = _hash_json(manual_steps)
    release_execution_root = _hash_json(
        {
            "release_execution_status": status,
            "release_tag": release_tag,
            "release_candidate_root": release_candidate_root,
            "recovery_runbook_root": recovery_root,
            "operator_runbook_root": operator_root,
            "deployment_package_root": deployment_root,
            "key_management_root": key_management_root,
            "manual_release_steps_hash": manual_steps_hash,
        }
    )
    ready = status == "RELEASE_EXECUTION_CHECKLIST_CANDIDATE"

    record = ReleaseExecutionChecklistRecord(
        release_execution_id=f"RELEASE_EXECUTION_CHECKLIST_{release_execution_root[:16]}",
        release_execution_status=status,
        release_tag=release_tag,
        release_candidate_root=release_candidate_root,
        recovery_runbook_root=recovery_root,
        operator_runbook_root=operator_root,
        deployment_package_root=deployment_root,
        key_management_root=key_management_root,
        manual_release_steps_hash=manual_steps_hash,
        release_execution_root=release_execution_root,
        release_execution_ready=ready,
        manual_review_required=True,
        real_git_tag_required=True,
        external_signature_required=True,
        git_tag_created=False,
        notes_signed_with_real_key=False,
        secrets_in_evidence=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Release execution checklist candidate only. Real Git tag creation, external "
            "release-note signing, tag push, and artifact archive remain manual external steps."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}
    summary = {
        "release_execution_record_count": 1,
        "release_execution_candidate_count": 1 if ready else 0,
        "release_execution_blocked_count": 0 if ready else 1,
        "release_execution_invalid_count": 0,
        "release_execution_status": status,
        "release_execution_ready": ready,
        "release_tag": release_tag,
        "release_candidate_root": release_candidate_root,
        "recovery_runbook_root": recovery_root,
        "operator_runbook_root": operator_root,
        "deployment_package_root": deployment_root,
        "key_management_root": key_management_root,
        "manual_release_steps_hash": manual_steps_hash,
        "release_execution_root": release_execution_root,
        "manual_review_required": True,
        "real_git_tag_required": True,
        "external_signature_required": True,
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
    _write_json(MANUAL_STEPS_OUTPUT, manual_steps)

    return {
        "payload": payload,
        "summary": summary,
        "manual_release_steps": manual_steps,
    }
