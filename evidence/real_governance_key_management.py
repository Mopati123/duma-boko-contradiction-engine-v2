#!/usr/bin/env python3
"""
Real Governance Key Management Engine v1.

Builds a deterministic governance key-management candidate. This lane does not
create real private keys and does not expose secrets. It defines the authority,
rotation, revocation, and custody envelope required before production release.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_REAL_WORLD_SCALE = Path(
    "outputs/real_world_evidence_scale_execution/real_world_evidence_scale_summary.json"
)
DEFAULT_PRODUCTION_READINESS = Path(
    "outputs/production_readiness_assessment/production_readiness_summary.json"
)
DEFAULT_SIGNATURE_AUTHORITY = Path(
    "outputs/signature_authority/signature_authority_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/real_governance_key_management")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_governance_key_management_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_governance_key_management_summary.json"
POLICY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_key_policy.json"

ALLOWED_STATUSES = {
    "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE",
    "BLOCKED_MISSING_REAL_WORLD_SCALE",
    "BLOCKED_INVALID_REAL_WORLD_SCALE",
    "BLOCKED_MISSING_PRODUCTION_READINESS",
    "BLOCKED_INVALID_PRODUCTION_READINESS",
    "BLOCKED_MISSING_SIGNATURE_AUTHORITY",
    "BLOCKED_INVALID_SIGNATURE_AUTHORITY",
    "GOVERNANCE_KEY_MANAGEMENT_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "keys_activated",
    "private_keys_generated",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class GovernanceKeyManagementRecord:
    key_management_id: str
    key_management_status: str
    authority_hash: str
    certificate_authority_root: str
    real_world_scale_root: str
    production_readiness_root: str
    key_policy_hash: str
    custody_policy_hash: str
    rotation_policy_hash: str
    revocation_policy_hash: str
    key_management_root: str
    keys_activated: bool
    private_keys_generated: bool
    secrets_in_evidence: bool
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


def _load_first_record(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records[0] if records and isinstance(records[0], dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _determine_status(
    real_world_scale: Dict[str, Any],
    production_readiness: Dict[str, Any],
    signature_authority: Dict[str, Any],
) -> str:
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

    if not signature_authority:
        return "BLOCKED_MISSING_SIGNATURE_AUTHORITY"
    if signature_authority.get("authority_status") != "SIGNATURE_AUTHORITY_CANDIDATE":
        return "BLOCKED_INVALID_SIGNATURE_AUTHORITY"
    if not _is_nonzero_hash(signature_authority.get("authority_hash")):
        return "BLOCKED_INVALID_SIGNATURE_AUTHORITY"

    return "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE"


def validate_record(record: GovernanceKeyManagementRecord) -> None:
    data = record.to_dict()

    required = {
        "key_management_id",
        "key_management_status",
        "authority_hash",
        "certificate_authority_root",
        "real_world_scale_root",
        "production_readiness_root",
        "key_policy_hash",
        "custody_policy_hash",
        "rotation_policy_hash",
        "revocation_policy_hash",
        "key_management_root",
        "keys_activated",
        "private_keys_generated",
        "secrets_in_evidence",
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
        raise ValueError(f"GovernanceKeyManagementRecord missing fields: {sorted(missing)}")

    if data["key_management_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported key_management_status: {data['key_management_status']}")

    if data["key_management_status"] == "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE":
        for key in (
            "authority_hash",
            "certificate_authority_root",
            "real_world_scale_root",
            "production_readiness_root",
            "key_policy_hash",
            "custody_policy_hash",
            "rotation_policy_hash",
            "revocation_policy_hash",
            "key_management_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["secrets_in_evidence"] is not False:
        raise ValueError("secrets_in_evidence must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_real_governance_key_management(
    real_world_scale_path: Path = DEFAULT_REAL_WORLD_SCALE,
    production_readiness_path: Path = DEFAULT_PRODUCTION_READINESS,
    signature_authority_path: Path = DEFAULT_SIGNATURE_AUTHORITY,
) -> Dict[str, Any]:
    real_world_scale = _load_json(real_world_scale_path)
    production_readiness = _load_json(production_readiness_path)
    signature_authority = _load_first_record(signature_authority_path)

    status = _determine_status(real_world_scale, production_readiness, signature_authority)

    authority_hash = str(signature_authority.get("authority_hash") or "")
    certificate_authority_root = str(signature_authority.get("certificate_authority_root") or "")
    real_world_scale_root = str(real_world_scale.get("real_world_scale_root") or "")
    production_readiness_root = str(production_readiness.get("readiness_root") or "")

    key_policy = {
        "policy_version": "real_governance_key_management_v1",
        "private_keys_in_repo": False,
        "private_keys_in_evidence": False,
        "allowed_key_roles": [
            "release_signing",
            "evidence_anchor_signing",
            "governance_authority_signing",
            "recovery_authority_signing",
        ],
        "minimum_controls": [
            "offline_backup_required",
            "rotation_required",
            "revocation_required",
            "manual_review_required",
            "no_secrets_in_logs",
            "no_secrets_in_artifacts",
        ],
    }

    custody_policy = {
        "policy_version": "custody_policy_v1",
        "custody_model": "external_secret_store_or_offline_custody",
        "repo_may_store": ["public_key_fingerprint", "key_id", "policy_hash"],
        "repo_must_not_store": ["private_key", "seed_phrase", "password", "api_secret"],
    }

    rotation_policy = {
        "policy_version": "rotation_policy_v1",
        "rotation_required": True,
        "rotation_triggers": [
            "scheduled_rotation",
            "role_change",
            "suspected_compromise",
            "release_epoch_change",
        ],
    }

    revocation_policy = {
        "policy_version": "revocation_policy_v1",
        "revocation_required": True,
        "revocation_outputs": [
            "revocation_record",
            "revocation_root",
            "replacement_authority_record",
        ],
    }

    key_policy_hash = _hash_json(key_policy)
    custody_policy_hash = _hash_json(custody_policy)
    rotation_policy_hash = _hash_json(rotation_policy)
    revocation_policy_hash = _hash_json(revocation_policy)

    key_management_root = _hash_json(
        {
            "status": status,
            "authority_hash": authority_hash,
            "certificate_authority_root": certificate_authority_root,
            "real_world_scale_root": real_world_scale_root,
            "production_readiness_root": production_readiness_root,
            "key_policy_hash": key_policy_hash,
            "custody_policy_hash": custody_policy_hash,
            "rotation_policy_hash": rotation_policy_hash,
            "revocation_policy_hash": revocation_policy_hash,
        }
    )

    record = GovernanceKeyManagementRecord(
        key_management_id=f"GOVERNANCE_KEY_MANAGEMENT_{key_management_root[:16]}",
        key_management_status=status,
        authority_hash=authority_hash,
        certificate_authority_root=certificate_authority_root,
        real_world_scale_root=real_world_scale_root,
        production_readiness_root=production_readiness_root,
        key_policy_hash=key_policy_hash,
        custody_policy_hash=custody_policy_hash,
        rotation_policy_hash=rotation_policy_hash,
        revocation_policy_hash=revocation_policy_hash,
        key_management_root=key_management_root,
        keys_activated=False,
        private_keys_generated=False,
        secrets_in_evidence=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Governance key-management candidate only. No private keys were generated, "
            "activated, logged, committed, or embedded in evidence. This artifact defines "
            "the governance key policy envelope required before production release."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "key_management_record_count": 1,
        "key_management_candidate_count": (
            1 if status == "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE" else 0
        ),
        "key_management_blocked_count": (
            0 if status == "GOVERNANCE_KEY_MANAGEMENT_CANDIDATE" else 1
        ),
        "key_management_invalid_count": (
            1 if status == "GOVERNANCE_KEY_MANAGEMENT_INVALID" else 0
        ),
        "key_management_status": status,
        "authority_hash": authority_hash,
        "certificate_authority_root": certificate_authority_root,
        "key_policy_hash": key_policy_hash,
        "custody_policy_hash": custody_policy_hash,
        "rotation_policy_hash": rotation_policy_hash,
        "revocation_policy_hash": revocation_policy_hash,
        "key_management_root": key_management_root,
        "keys_activated": False,
        "private_keys_generated": False,
        "secrets_in_evidence": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    policy = {
        "key_policy": key_policy,
        "custody_policy": custody_policy,
        "rotation_policy": rotation_policy,
        "revocation_policy": revocation_policy,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(POLICY_OUTPUT, policy)

    return {
        "payload": payload,
        "summary": summary,
        "policy": policy,
    }