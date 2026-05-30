#!/usr/bin/env python3
"""
Recovery Runbook Engine v1.

Creates the deterministic recovery runbook candidate for restoring, verifying,
and safely resuming the governed evidence engine after data loss, machine loss,
artifact loss, or suspected compromise.

This lane does not perform recovery. It defines the recovery envelope and proof
requirements.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/recovery_runbook")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "recovery_runbook_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "recovery_runbook_summary.json"
RUNBOOK_OUTPUT = DEFAULT_OUTPUT_DIR / "recovery_runbook.json"

ALLOWED_STATUSES = {
    "RECOVERY_RUNBOOK_CANDIDATE",
    "BLOCKED_MISSING_OPERATOR_RUNBOOK",
    "BLOCKED_INVALID_OPERATOR_RUNBOOK",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "RECOVERY_RUNBOOK_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "recovery_runbook_approved",
    "recovery_performed",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class RecoveryRunbookRecord:
    recovery_runbook_id: str
    recovery_runbook_status: str
    operator_runbook_root: str
    deployment_package_root: str
    key_management_root: str
    recovery_runbook_hash: str
    recovery_runbook_root: str
    recovery_runbook_ready: bool
    recovery_runbook_approved: bool
    recovery_performed: bool
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
    operator_runbook: Dict[str, Any],
    deployment_package: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
    if not operator_runbook:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator_runbook.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator_runbook.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not deployment_package:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment_package.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment_package.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    return "RECOVERY_RUNBOOK_CANDIDATE"


def _recovery_runbook() -> Dict[str, Any]:
    return {
        "runbook_version": "recovery_runbook_v1",
        "recovery_principles": [
            "restore_from_git_first",
            "never_restore_unverified_generated_outputs_as_source",
            "rebuild_outputs_from_committed_source",
            "verify_roots_before_resuming_operation",
            "rotate_or_revoke_keys_after_suspected_compromise",
            "manual_review_required_before public claims".replace(" ", "_"),
        ],
        "recovery_scenarios": {
            "machine_loss": [
                "clone_origin_master",
                "create_clean_virtual_environment",
                "install_dependencies",
                "run_full_dry_run_chain",
                "compare_expected_roots",
                "confirm_clean_git_status",
            ],
            "generated_output_loss": [
                "do_not_panic",
                "do_not_commit_recovered_outputs",
                "rerun_full_dry_run_chain",
                "verify_generated_summaries",
            ],
            "machine_b_package_loss": [
                "rerun_machine_b_from_clean_clone",
                "recreate_machine_b_result_zip",
                "copy_package_to_machine_a",
                "rerun_real_machine_b_verification",
            ],
            "suspected_secret_compromise": [
                "stop_all_release_actions",
                "revoke_affected_authority",
                "rotate_governance_keys",
                "record_revocation_root",
                "rerun_replay_and_anchor_chain",
            ],
            "hash_drift": [
                "stop_pipeline",
                "capture_diff",
                "verify_source_branch_and_commit",
                "rerun_from_clean_clone",
                "treat_unexplained_drift_as_release_blocker",
            ],
        },
        "minimum_recovery_commands": [
            "git clone <repo>",
            "git checkout master",
            "git pull origin master",
            "python -m venv .venv",
            "source .venv/bin/activate",
            "pip install -r requirements.txt",
            "python scripts/build_replay_certification.py --dry-run",
            "python scripts/build_cross_machine_proof.py --dry-run",
            "python scripts/build_production_freeze.py --dry-run",
        ],
        "release_resume_conditions": [
            "working_tree_clean",
            "origin_master_synced",
            "replay_verified_true",
            "cross_machine_verified_true",
            "no_secrets_in_evidence",
            "manual_review_complete",
        ],
    }


def validate_record(record: RecoveryRunbookRecord) -> None:
    data = record.to_dict()

    required = {
        "recovery_runbook_id",
        "recovery_runbook_status",
        "operator_runbook_root",
        "deployment_package_root",
        "key_management_root",
        "recovery_runbook_hash",
        "recovery_runbook_root",
        "recovery_runbook_ready",
        "recovery_runbook_approved",
        "recovery_performed",
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
        raise ValueError(f"RecoveryRunbookRecord missing fields: {sorted(missing)}")

    if data["recovery_runbook_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported recovery_runbook_status: {data['recovery_runbook_status']}")

    if data["recovery_runbook_status"] == "RECOVERY_RUNBOOK_CANDIDATE":
        for key in (
            "operator_runbook_root",
            "deployment_package_root",
            "key_management_root",
            "recovery_runbook_hash",
            "recovery_runbook_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["recovery_runbook_ready"] is not True:
            raise ValueError("recovery_runbook_ready must be true")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_recovery_runbook(
    operator_runbook_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    deployment_package_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    operator_runbook = _load_json(operator_runbook_path)
    deployment_package = _load_json(deployment_package_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(operator_runbook, deployment_package, key_management)

    operator_runbook_root = str(operator_runbook.get("operator_runbook_root") or "")
    deployment_package_root = str(deployment_package.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    runbook = _recovery_runbook()
    recovery_runbook_hash = _hash_json(runbook)

    recovery_runbook_root = _hash_json(
        {
            "recovery_runbook_status": status,
            "operator_runbook_root": operator_runbook_root,
            "deployment_package_root": deployment_package_root,
            "key_management_root": key_management_root,
            "recovery_runbook_hash": recovery_runbook_hash,
        }
    )

    ready = status == "RECOVERY_RUNBOOK_CANDIDATE"

    record = RecoveryRunbookRecord(
        recovery_runbook_id=f"RECOVERY_RUNBOOK_{recovery_runbook_root[:16]}",
        recovery_runbook_status=status,
        operator_runbook_root=operator_runbook_root,
        deployment_package_root=deployment_package_root,
        key_management_root=key_management_root,
        recovery_runbook_hash=recovery_runbook_hash,
        recovery_runbook_root=recovery_runbook_root,
        recovery_runbook_ready=ready,
        recovery_runbook_approved=False,
        recovery_performed=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Recovery runbook candidate only. Defines deterministic recovery, "
            "rebuild, hash-drift, Machine-B package, and suspected compromise paths. "
            "No recovery was performed and production_ready remains false."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "recovery_runbook_record_count": 1,
        "recovery_runbook_candidate_count": 1 if ready else 0,
        "recovery_runbook_blocked_count": 0 if ready else 1,
        "recovery_runbook_invalid_count": 0,
        "recovery_runbook_status": status,
        "recovery_runbook_ready": ready,
        "operator_runbook_root": operator_runbook_root,
        "deployment_package_root": deployment_package_root,
        "key_management_root": key_management_root,
        "recovery_runbook_hash": recovery_runbook_hash,
        "recovery_runbook_root": recovery_runbook_root,
        "recovery_runbook_approved": False,
        "recovery_performed": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(RUNBOOK_OUTPUT, runbook)

    return {
        "payload": payload,
        "summary": summary,
        "runbook": runbook,
    }