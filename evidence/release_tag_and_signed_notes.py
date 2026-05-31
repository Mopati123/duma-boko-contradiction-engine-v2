#!/usr/bin/env python3
"""
Release Tag and Signed Notes Engine v1.

Creates a deterministic release-candidate tag and signed-notes envelope.
This does not create a real Git tag and does not use private signing keys.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_RECOVERY_RUNBOOK = Path("outputs/recovery_runbook/recovery_runbook_summary.json")
DEFAULT_OPERATOR_RUNBOOK = Path("outputs/operator_runbook/operator_runbook_summary.json")
DEFAULT_DEPLOYMENT_PACKAGE = Path("outputs/deployment_package/deployment_package_summary.json")
DEFAULT_KEY_MANAGEMENT = Path(
    "outputs/real_governance_key_management/real_governance_key_management_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/release_tag_and_signed_notes")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "release_tag_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "release_tag_summary.json"
NOTES_OUTPUT = DEFAULT_OUTPUT_DIR / "signed_release_notes.json"

ALLOWED_STATUSES = {
    "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE",
    "BLOCKED_MISSING_RECOVERY_RUNBOOK",
    "BLOCKED_INVALID_RECOVERY_RUNBOOK",
    "BLOCKED_MISSING_OPERATOR_RUNBOOK",
    "BLOCKED_INVALID_OPERATOR_RUNBOOK",
    "BLOCKED_MISSING_DEPLOYMENT_PACKAGE",
    "BLOCKED_INVALID_DEPLOYMENT_PACKAGE",
    "BLOCKED_MISSING_KEY_MANAGEMENT",
    "BLOCKED_INVALID_KEY_MANAGEMENT",
    "RELEASE_TAG_AND_SIGNED_NOTES_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "git_tag_created",
    "notes_signed_with_real_key",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ReleaseTagSignedNotesRecord:
    release_id: str
    release_status: str
    release_tag: str
    recovery_runbook_root: str
    operator_runbook_root: str
    deployment_package_root: str
    key_management_root: str
    release_notes_hash: str
    release_candidate_root: str
    release_candidate_ready: bool
    git_tag_created: bool
    notes_signed_with_real_key: bool
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
    recovery: Dict[str, Any],
    operator: Dict[str, Any],
    deployment: Dict[str, Any],
    key_management: Dict[str, Any],
) -> str:
    if not recovery:
        return "BLOCKED_MISSING_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_status") != "RECOVERY_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"
    if recovery.get("recovery_runbook_ready") is not True:
        return "BLOCKED_INVALID_RECOVERY_RUNBOOK"

    if not operator:
        return "BLOCKED_MISSING_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_status") != "OPERATOR_RUNBOOK_CANDIDATE":
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"
    if operator.get("operator_runbook_ready") is not True:
        return "BLOCKED_INVALID_OPERATOR_RUNBOOK"

    if not deployment:
        return "BLOCKED_MISSING_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_status") != "DEPLOYMENT_PACKAGE_CANDIDATE":
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"
    if deployment.get("deployment_candidate_ready") is not True:
        return "BLOCKED_INVALID_DEPLOYMENT_PACKAGE"

    if not key_management:
        return "BLOCKED_MISSING_KEY_MANAGEMENT"
    if key_management.get("key_management_status") != "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        return "BLOCKED_INVALID_KEY_MANAGEMENT"
    if key_management.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_KEY_MANAGEMENT"

    return "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE"


def _release_notes(
    recovery_root: str,
    operator_root: str,
    deployment_root: str,
    key_management_root: str,
) -> Dict[str, Any]:
    return {
        "release_notes_version": "signed_release_notes_v1",
        "release_tag": "v1.0.0-rc1-governance-runtime",
        "release_type": "release_candidate",
        "completed_lanes": [
            "evidence_hydration",
            "governance_anchor_bundle",
            "final_report_sealing",
            "anchor_publication",
            "anchor_verification",
            "verification_certificate",
            "public_anchor",
            "signature_authority",
            "replay_certification",
            "cross_machine_proof",
            "production_freeze",
            "adversarial_falsification",
            "real_machine_b_verification",
            "scale_certification",
            "real_scale_execution",
            "production_readiness_assessment",
            "real_world_evidence_scale_execution",
            "real_governance_key_management",
            "deployment_package",
            "operator_runbook",
            "recovery_runbook",
        ],
        "root_references": {
            "recovery_runbook_root": recovery_root,
            "operator_runbook_root": operator_root,
            "deployment_package_root": deployment_root,
            "key_management_root": key_management_root,
        },
        "signature_model": {
            "real_private_key_used": False,
            "candidate_signature_only": True,
            "requires_manual_release_signing": True,
            "no_secrets_in_evidence": True,
        },
        "release_blockers_remaining": [
            "manual_final_review",
            "real_git_tag_creation",
            "real_signature_with_external_key",
        ],
    }


def validate_record(record: ReleaseTagSignedNotesRecord) -> None:
    data = record.to_dict()

    required = {
        "release_id",
        "release_status",
        "release_tag",
        "recovery_runbook_root",
        "operator_runbook_root",
        "deployment_package_root",
        "key_management_root",
        "release_notes_hash",
        "release_candidate_root",
        "release_candidate_ready",
        "git_tag_created",
        "notes_signed_with_real_key",
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
        raise ValueError(f"ReleaseTagSignedNotesRecord missing fields: {sorted(missing)}")

    if data["release_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported release_status: {data['release_status']}")

    if data["release_status"] == "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE":
        for key in (
            "recovery_runbook_root",
            "operator_runbook_root",
            "deployment_package_root",
            "key_management_root",
            "release_notes_hash",
            "release_candidate_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["release_candidate_ready"] is not True:
            raise ValueError("release_candidate_ready must be true")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_release_tag_and_signed_notes(
    recovery_path: Path = DEFAULT_RECOVERY_RUNBOOK,
    operator_path: Path = DEFAULT_OPERATOR_RUNBOOK,
    deployment_path: Path = DEFAULT_DEPLOYMENT_PACKAGE,
    key_management_path: Path = DEFAULT_KEY_MANAGEMENT,
) -> Dict[str, Any]:
    recovery = _load_json(recovery_path)
    operator = _load_json(operator_path)
    deployment = _load_json(deployment_path)
    key_management = _load_json(key_management_path)

    status = _determine_status(recovery, operator, deployment, key_management)

    recovery_root = str(recovery.get("recovery_runbook_root") or "")
    operator_root = str(operator.get("operator_runbook_root") or "")
    deployment_root = str(deployment.get("deployment_package_root") or "")
    key_management_root = str(key_management.get("key_management_root") or "")

    notes_doc = _release_notes(
        recovery_root,
        operator_root,
        deployment_root,
        key_management_root,
    )
    release_notes_hash = _hash_json(notes_doc)

    release_candidate_root = _hash_json(
        {
            "release_status": status,
            "release_tag": notes_doc["release_tag"],
            "recovery_runbook_root": recovery_root,
            "operator_runbook_root": operator_root,
            "deployment_package_root": deployment_root,
            "key_management_root": key_management_root,
            "release_notes_hash": release_notes_hash,
        }
    )

    ready = status == "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE"

    record = ReleaseTagSignedNotesRecord(
        release_id=f"RELEASE_TAG_SIGNED_NOTES_{release_candidate_root[:16]}",
        release_status=status,
        release_tag=notes_doc["release_tag"],
        recovery_runbook_root=recovery_root,
        operator_runbook_root=operator_root,
        deployment_package_root=deployment_root,
        key_management_root=key_management_root,
        release_notes_hash=release_notes_hash,
        release_candidate_root=release_candidate_root,
        release_candidate_ready=ready,
        git_tag_created=False,
        notes_signed_with_real_key=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Release tag and signed notes candidate only. No real Git tag was created "
            "and no real private signing key was used. Manual final release signing is required."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "release_record_count": 1,
        "release_candidate_count": 1 if ready else 0,
        "release_blocked_count": 0 if ready else 1,
        "release_invalid_count": 0,
        "release_status": status,
        "release_tag": notes_doc["release_tag"],
        "release_candidate_ready": ready,
        "release_notes_hash": release_notes_hash,
        "release_candidate_root": release_candidate_root,
        "git_tag_created": False,
        "notes_signed_with_real_key": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(NOTES_OUTPUT, notes_doc)

    return {
        "payload": payload,
        "summary": summary,
        "release_notes": notes_doc,
    }