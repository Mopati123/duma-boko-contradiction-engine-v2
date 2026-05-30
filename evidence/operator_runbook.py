#!/usr/bin/env python3
"""
Operator Runbook Engine v1.

Creates the deterministic operator runbook candidate for running the governed
evidence engine safely. This lane does not execute production operations.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/operator_runbook")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "operator_runbook_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "operator_runbook_summary.json"
RUNBOOK_OUTPUT = DEFAULT_OUTPUT_DIR / "operator_runbook.json"

ALLOWED_STATUSES = {
    "OPERATOR_RUNBOOK_CANDIDATE",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "OPERATOR_RUNBOOK_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "operator_runbook_approved",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class OperatorRunbookRecord:
    operator_runbook_id: str
    operator_runbook_status: str
    deployment_package_root: str
    key_management_root: str
    runbook_hash: str
    operator_runbook_root: str
    operator_runbook_ready: bool
    operator_runbook_approved: bool
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
    deployment_package: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
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

    return "OPERATOR_RUNBOOK_CANDIDATE"


def _operator_runbook() -> Dict[str, Any]:
    return {
        "runbook_version": "operator_runbook_v1",
        "operator_principles": [
            "never_run_from_dirty_working_tree",
            "never_commit_generated_outputs",
            "never_commit_private_keys_or_secrets",
            "always_run_dry_run_chain_before_release",
            "treat_refusal_as_success_when_constraints_fail",
            "manual_review_required_before_public_claims",
        ],
        "preflight_checks": [
            "git status",
            "git log --oneline -5",
            "python -m py_compile evidence/*.py scripts/*.py",
        ],
        "standard_execution_sequence": [
            "build_canonical_evidence_url_closure",
            "build_canonical_evidence_resolution",
            "build_canonical_evidence_injection",
            "build_evidence_snapshot_sealing",
            "build_canonical_graph_mutation",
            "build_final_report_collapse",
            "build_governance_signatures",
            "build_governance_anchor_bundle",
            "build_final_report_sealing",
            "build_anchor_publication",
            "build_anchor_verification",
            "build_verification_certificate",
            "build_public_anchor_engine",
            "build_signature_authority",
            "build_replay_certification",
            "build_cross_machine_proof",
            "build_production_freeze",
            "build_adversarial_falsification_suite",
            "build_real_machine_b_verification",
            "build_scale_certification_suite",
            "build_real_scale_execution",
            "build_production_readiness_assessment",
            "build_real_world_evidence_scale_execution",
            "build_real_governance_key_management",
            "build_deployment_package",
            "build_operator_runbook",
        ],
        "operator_stop_conditions": [
            "unexpected_acceptance_of_adversarial_input",
            "hash_root_drift",
            "dirty_working_tree_before_release",
            "missing_machine_b_package_for_machine_b_verification",
            "secrets_detected_in_outputs",
            "untracked_source_files",
        ],
        "manual_review_items": [
            "verify source branch",
            "verify latest origin/master",
            "verify generated summaries",
            "verify no private secrets",
            "verify release blockers",
        ],
    }


def validate_record(record: OperatorRunbookRecord) -> None:
    data = record.to_dict()

    required = {
        "operator_runbook_id",
        "operator_runbook_status",
        "deployment_package_root",
        "key_management_root",
        "runbook_hash",
        "operator_runbook_root",
        "operator_runbook_ready",
        "operator_runbook_approved",
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
        raise ValueError(f"OperatorRunbookRecord missing fields: {sorted(missing)}")

    if data["operator_runbook_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported operator_runbook_status: {data['operator_runbook_status']}")

    if data["operator_runbook_status"] == "OPERATOR_RUNBOOK_CANDIDATE":
        for key in (
            "deployment_package_root",
            "key_management_root",
            "runbook_hash",
            "operator_runbook_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["operator_runbook_ready"] is not True:
            raise ValueError("operator_runbook_ready must be true")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_operator_runbook(
    deployment_package_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    deployment_package = _load_json(deployment_package_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(deployment_package, key_management)

    deployment_package_root = str(deployment_package.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    runbook = _operator_runbook()
    runbook_hash = _hash_json(runbook)

    operator_runbook_root = _hash_json(
        {
            "operator_runbook_status": status,
            "deployment_package_root": deployment_package_root,
            "key_management_root": key_management_root,
            "runbook_hash": runbook_hash,
        }
    )

    ready = status == "OPERATOR_RUNBOOK_CANDIDATE"

    record = OperatorRunbookRecord(
        operator_runbook_id=f"OPERATOR_RUNBOOK_{operator_runbook_root[:16]}",
        operator_runbook_status=status,
        deployment_package_root=deployment_package_root,
        key_management_root=key_management_root,
        runbook_hash=runbook_hash,
        operator_runbook_root=operator_runbook_root,
        operator_runbook_ready=ready,
        operator_runbook_approved=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Operator runbook candidate only. Defines safe execution, stop conditions, "
            "manual review items, and standard dry-run sequence. It does not approve "
            "production operation."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "operator_runbook_record_count": 1,
        "operator_runbook_candidate_count": 1 if ready else 0,
        "operator_runbook_blocked_count": 0 if ready else 1,
        "operator_runbook_invalid_count": 0,
        "operator_runbook_status": status,
        "operator_runbook_ready": ready,
        "deployment_package_root": deployment_package_root,
        "key_management_root": key_management_root,
        "runbook_hash": runbook_hash,
        "operator_runbook_root": operator_runbook_root,
        "operator_runbook_approved": False,
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