#!/usr/bin/env python3
"""
Deployment Package Engine v1.

Builds a deterministic deployment-package candidate from the completed
governance, key-management, real-world scale, and production-readiness lanes.

This lane does not deploy the system. It creates the release/deployment envelope,
required commands, artifact policy, and deployment checklist.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)
DEFAULT_REAL_WORLD_SCALE = Path(
    "outputs/real_world_evidence_scale_execution/real_world_evidence_scale_summary.json"
)
DEFAULT_PRODUCTION_READINESS = Path(
    "outputs/production_readiness_assessment/production_readiness_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/deployment_package")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "deployment_package_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "deployment_package_summary.json"
MANIFEST_OUTPUT = DEFAULT_OUTPUT_DIR / "deployment_manifest.json"

ALLOWED_STATUSES = {
    "DEPLOYMENT_PACKAGE_CANDIDATE",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "BLOCKED_MISSING_REAL_WORLD_SCALE",
    "BLOCKED_INVALID_REAL_WORLD_SCALE",
    "BLOCKED_MISSING_PRODUCTION_READINESS",
    "BLOCKED_INVALID_PRODUCTION_READINESS",
    "DEPLOYMENT_PACKAGE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "deployment_applied",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class DeploymentPackageRecord:
    deployment_id: str
    deployment_status: str
    key_management_root: str
    real_world_scale_root: str
    production_readiness_root: str
    deployment_manifest_hash: str
    deployment_package_root: str
    deployment_candidate_ready: bool
    deployment_applied: bool
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
    key_management: Dict[str, Any],
    real_world_scale: Dict[str, Any],
    production_readiness: Dict[str, Any],
) -> str:
    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    if not real_world_scale:
        return "BLOCKED_MISSING_REAL_WORLD_SCALE"
    if real_world_scale.get("real_world_scale_status") != "REAL_WORLD_SCALE_EXECUTION_CANDIDATE":
        return "BLOCKED_INVALID_REAL_WORLD_SCALE"
    if real_world_scale.get("real_world_verified") is not True:
        return "BLOCKED_INVALID_REAL_WORLD_SCALE"

    if not production_readiness:
        return "BLOCKED_MISSING_PRODUCTION_READINESS"
    if production_readiness.get("readiness_status") != "PRODUCTION_READINESS_CANDIDATE":
        return "BLOCKED_INVALID_PRODUCTION_READINESS"
    if int(production_readiness.get("readiness_score", 0)) < 90:
        return "BLOCKED_INVALID_PRODUCTION_READINESS"

    return "DEPLOYMENT_PACKAGE_CANDIDATE"


def _deployment_manifest() -> Dict[str, Any]:
    return {
        "manifest_version": "deployment_package_v1",
        "runtime": {
            "language": "python",
            "supported_execution": ["local_cli", "ci_runner", "controlled_server"],
            "forbidden_execution": [
                "unreviewed_production_mutation",
                "private_key_material_in_repo",
                "unlogged_evidence_mutation",
            ],
        },
        "required_commands": [
            "python scripts/build_canonical_evidence_url_closure.py --dry-run",
            "python scripts/build_canonical_evidence_resolution.py --dry-run",
            "python scripts/build_canonical_evidence_injection.py --dry-run",
            "python scripts/build_evidence_snapshot_sealing.py --dry-run",
            "python scripts/build_canonical_graph_mutation.py --dry-run",
            "python scripts/build_final_report_collapse.py --dry-run",
            "python scripts/build_governance_signatures.py --dry-run",
            "python scripts/build_governance_anchor_bundle.py --dry-run",
            "python scripts/build_final_report_sealing.py --dry-run",
            "python scripts/build_anchor_publication.py --dry-run",
            "python scripts/build_anchor_verification.py --dry-run",
            "python scripts/build_verification_certificate.py --dry-run",
            "python scripts/build_public_anchor_engine.py --dry-run",
            "python scripts/build_signature_authority.py --dry-run",
            "python scripts/build_replay_certification.py --dry-run",
            "python scripts/build_cross_machine_proof.py --dry-run",
            "python scripts/build_production_freeze.py --dry-run",
            "python scripts/build_adversarial_falsification_suite.py --dry-run",
            "python scripts/build_real_machine_b_verification.py --dry-run",
            "python scripts/build_scale_certification_suite.py --dry-run",
            "python scripts/build_real_scale_execution.py --dry-run",
            "python scripts/build_production_readiness_assessment.py --dry-run",
            "python scripts/build_real_world_evidence_scale_execution.py --dry-run",
            "python scripts/build_real_governance_key_management.py --dry-run",
            "python scripts/build_deployment_package.py --dry-run",
        ],
        "artifact_policy": {
            "source_code_committed": True,
            "outputs_ignored": True,
            "private_keys_committed": False,
            "machine_b_packages_committed": False,
            "operator_review_required": True,
        },
        "deployment_checklist": [
            "clean_master_required",
            "origin_master_synced_required",
            "venv_or_isolated_runtime_required",
            "dependency_install_required",
            "full_dry_run_chain_required",
            "no_untracked_source_required",
            "no_secrets_in_outputs_required",
            "manual_release_review_required",
        ],
    }


def validate_record(record: DeploymentPackageRecord) -> None:
    data = record.to_dict()

    required = {
        "deployment_id",
        "deployment_status",
        "key_management_root",
        "real_world_scale_root",
        "production_readiness_root",
        "deployment_manifest_hash",
        "deployment_package_root",
        "deployment_candidate_ready",
        "deployment_applied",
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
        raise ValueError(f"DeploymentPackageRecord missing fields: {sorted(missing)}")

    if data["deployment_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported deployment_status: {data['deployment_status']}")

    if data["deployment_status"] == "DEPLOYMENT_PACKAGE_CANDIDATE":
        for key in (
            "key_management_root",
            "real_world_scale_root",
            "production_readiness_root",
            "deployment_manifest_hash",
            "deployment_package_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["deployment_candidate_ready"] is not True:
            raise ValueError("deployment_candidate_ready must be true")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_deployment_package(
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
    real_world_scale_path: Path = DEFAULT_REAL_WORLD_SCALE,
    production_readiness_path: Path = DEFAULT_PRODUCTION_READINESS,
) -> Dict[str, Any]:
    key_management = _load_json(key_management_path)
    real_world_scale = _load_json(real_world_scale_path)
    production_readiness = _load_json(production_readiness_path)

    status = _determine_status(key_management, real_world_scale, production_readiness)

    key_management_root = str(key_management.get("key_management_root") or "")
    real_world_scale_root = str(real_world_scale.get("real_world_scale_root") or "")
    production_readiness_root = str(production_readiness.get("readiness_root") or "")

    manifest = _deployment_manifest()
    deployment_manifest_hash = _hash_json(manifest)

    deployment_package_root = _hash_json(
        {
            "deployment_status": status,
            "key_management_root": key_management_root,
            "real_world_scale_root": real_world_scale_root,
            "production_readiness_root": production_readiness_root,
            "deployment_manifest_hash": deployment_manifest_hash,
        }
    )

    deployment_candidate_ready = status == "DEPLOYMENT_PACKAGE_CANDIDATE"

    record = DeploymentPackageRecord(
        deployment_id=f"DEPLOYMENT_PACKAGE_{deployment_package_root[:16]}",
        deployment_status=status,
        key_management_root=key_management_root,
        real_world_scale_root=real_world_scale_root,
        production_readiness_root=production_readiness_root,
        deployment_manifest_hash=deployment_manifest_hash,
        deployment_package_root=deployment_package_root,
        deployment_candidate_ready=deployment_candidate_ready,
        deployment_applied=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Deployment package candidate only. The manifest defines required dry-run "
            "commands, artifact policy, and deployment checklist. No deployment was "
            "performed and production_ready remains false."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "deployment_package_record_count": 1,
        "deployment_package_candidate_count": (
            1 if status == "DEPLOYMENT_PACKAGE_CANDIDATE" else 0
        ),
        "deployment_package_blocked_count": (
            0 if status == "DEPLOYMENT_PACKAGE_CANDIDATE" else 1
        ),
        "deployment_package_invalid_count": (
            1 if status == "DEPLOYMENT_PACKAGE_INVALID" else 0
        ),
        "deployment_status": status,
        "deployment_candidate_ready": deployment_candidate_ready,
        "key_management_root": key_management_root,
        "real_world_scale_root": real_world_scale_root,
        "production_readiness_root": production_readiness_root,
        "deployment_manifest_hash": deployment_manifest_hash,
        "deployment_package_root": deployment_package_root,
        "deployment_applied": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(MANIFEST_OUTPUT, manifest)

    return {
        "payload": payload,
        "summary": summary,
        "deployment_manifest": manifest,
    }