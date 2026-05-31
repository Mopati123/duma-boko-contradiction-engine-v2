#!/usr/bin/env python3
"""
Shadow Deployment Execution Dry-Run Engine v1.

Records a controlled non-production shadow deployment dry-run from verified
release and shadow deployment evidence. This lane does not enable live
production, authorize release, sign with a real key, create private keys, or
mutate real-world systems.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_SHADOW_DEPLOYMENT_PLAN = Path(
    "outputs/shadow_deployment_plan/shadow_deployment_plan_summary.json"
)
DEFAULT_REAL_TAG_EVIDENCE = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_EXTERNAL_SIGNING_TEMPLATE = Path(
    "outputs/external_signing_evidence_template/"
    "external_signing_evidence_template_summary.json"
)
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_deployment_execution_dry_run")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_deployment_execution_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_deployment_execution_summary.json"
EVIDENCE_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_execution_evidence.json"

ALLOWED_STATUSES = {
    "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE",
    "BLOCKED_MISSING_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "live_production_enabled",
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "external_signature_present",
    "notes_signed_with_real_key",
    "secrets_in_evidence",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ShadowDeploymentExecutionDryRunRecord:
    shadow_execution_id: str
    shadow_execution_status: str
    release_tag: str
    shadow_deployment_root: str
    real_tag_evidence_root: str
    external_signing_template_root: str
    final_hardening_root: str
    approval_gate_root: str
    shadow_execution_evidence_hash: str
    shadow_execution_root: str
    shadow_execution_ready: bool
    shadow_execution_performed: bool
    dry_run_commands_checked: bool
    tag_evidence_verified: bool
    shadow_plan_verified: bool
    approval_gate_verified: bool
    hardening_verified: bool
    external_signing_pending: bool
    production_refused_without_manual_approval: bool
    live_production_enabled: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    external_signature_present: bool
    notes_signed_with_real_key: bool
    secrets_in_evidence: bool
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
    shadow_plan: Dict[str, Any],
    real_tag: Dict[str, Any],
    external_signing: Dict[str, Any],
    final_hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
) -> str:
    if not shadow_plan:
        return "BLOCKED_MISSING_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("shadow_deployment_status") != "SHADOW_DEPLOYMENT_PLAN_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("shadow_deployment_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("manual_approval_required") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("external_signature_required") is not True:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if shadow_plan.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if not _closed_release_flags(shadow_plan):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"
    if not _is_nonzero_hash(shadow_plan.get("shadow_deployment_root")):
        return "BLOCKED_INVALID_SHADOW_DEPLOYMENT_PLAN"

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

    if not external_signing:
        return "BLOCKED_MISSING_EXTERNAL_SIGNING_TEMPLATE"
    if (
        external_signing.get("external_signing_template_status")
        != "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE"
    ):
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"
    if external_signing.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"
    if external_signing.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"
    if external_signing.get("release_authorized") is not False:
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"
    if not _closed_release_flags(external_signing):
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"
    if not _is_nonzero_hash(external_signing.get("external_signing_template_root")):
        return "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE"

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
    if final_hardening.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("generated_outputs_committed") is not False:
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
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

    return "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE"


def _shadow_execution_evidence(
    release_tag: str,
    shadow_deployment_root: str,
    real_tag_evidence_root: str,
    external_signing_template_root: str,
    final_hardening_root: str,
    approval_gate_root: str,
) -> Dict[str, Any]:
    return {
        "shadow_execution_evidence_version": "shadow_deployment_execution_dry_run_v1",
        "release_tag": release_tag,
        "dry_run_only": True,
        "shadow_execution_performed": True,
        "dry_run_commands_checked": True,
        "tag_evidence_verified": True,
        "shadow_plan_verified": True,
        "approval_gate_verified": True,
        "hardening_verified": True,
        "external_signing_pending": True,
        "production_refused_without_manual_approval": True,
        "live_production_enabled": False,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "external_signature_present": False,
        "notes_signed_with_real_key": False,
        "secrets_in_evidence": False,
        "mutating_actions_performed": {
            "external_signature_created": False,
            "live_production_enabled": False,
            "private_keys_created": False,
            "real_world_systems_mutated": False,
            "release_authorized": False,
        },
        "verified_inputs": {
            "approval_gate_root": approval_gate_root,
            "external_signing_template_root": external_signing_template_root,
            "final_hardening_root": final_hardening_root,
            "real_tag_evidence_root": real_tag_evidence_root,
            "shadow_deployment_root": shadow_deployment_root,
        },
    }


def validate_record(record: ShadowDeploymentExecutionDryRunRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_execution_id",
        "shadow_execution_status",
        "release_tag",
        "shadow_deployment_root",
        "real_tag_evidence_root",
        "external_signing_template_root",
        "final_hardening_root",
        "approval_gate_root",
        "shadow_execution_evidence_hash",
        "shadow_execution_root",
        "shadow_execution_ready",
        "shadow_execution_performed",
        "dry_run_commands_checked",
        "tag_evidence_verified",
        "shadow_plan_verified",
        "approval_gate_verified",
        "hardening_verified",
        "external_signing_pending",
        "production_refused_without_manual_approval",
        "live_production_enabled",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "external_signature_present",
        "notes_signed_with_real_key",
        "secrets_in_evidence",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(
            f"ShadowDeploymentExecutionDryRunRecord missing fields: {sorted(missing)}"
        )
    if data["shadow_execution_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_execution_status: {data['shadow_execution_status']}")

    if data["shadow_execution_status"] == "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE":
        for key in (
            "shadow_deployment_root",
            "real_tag_evidence_root",
            "external_signing_template_root",
            "final_hardening_root",
            "approval_gate_root",
            "shadow_execution_evidence_hash",
            "shadow_execution_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        for key in (
            "shadow_execution_ready",
            "shadow_execution_performed",
            "dry_run_commands_checked",
            "tag_evidence_verified",
            "shadow_plan_verified",
            "approval_gate_verified",
            "hardening_verified",
            "external_signing_pending",
            "production_refused_without_manual_approval",
        ):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for candidate output")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_deployment_execution_dry_run(
    shadow_plan_path: Path = DEFAULT_SHADOW_DEPLOYMENT_PLAN,
    real_tag_path: Path = DEFAULT_REAL_TAG_EVIDENCE,
    external_signing_path: Path = DEFAULT_EXTERNAL_SIGNING_TEMPLATE,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
) -> Dict[str, Any]:
    shadow_plan = _load_json(shadow_plan_path)
    real_tag = _load_json(real_tag_path)
    external_signing = _load_json(external_signing_path)
    final_hardening = _load_json(final_hardening_path)
    approval_gate = _load_json(approval_gate_path)

    status = _determine_status(
        shadow_plan,
        real_tag,
        external_signing,
        final_hardening,
        approval_gate,
    )
    ready = status == "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE"

    release_tag = str(shadow_plan.get("release_tag") or real_tag.get("tag_name") or "")
    shadow_deployment_root = str(shadow_plan.get("shadow_deployment_root") or "")
    real_tag_evidence_root = str(real_tag.get("real_tag_evidence_root") or "")
    external_signing_template_root = str(
        external_signing.get("external_signing_template_root") or ""
    )
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")

    evidence = _shadow_execution_evidence(
        release_tag,
        shadow_deployment_root,
        real_tag_evidence_root,
        external_signing_template_root,
        final_hardening_root,
        approval_gate_root,
    )
    evidence_hash = _hash_json(evidence)
    root = _hash_json(
        {
            "shadow_execution_status": status,
            "release_tag": release_tag,
            "shadow_deployment_root": shadow_deployment_root,
            "real_tag_evidence_root": real_tag_evidence_root,
            "external_signing_template_root": external_signing_template_root,
            "final_hardening_root": final_hardening_root,
            "approval_gate_root": approval_gate_root,
            "shadow_execution_evidence_hash": evidence_hash,
            "shadow_execution_performed": ready,
            "live_production_enabled": False,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "notes_signed_with_real_key": False,
        }
    )

    record = ShadowDeploymentExecutionDryRunRecord(
        shadow_execution_id=f"SHADOW_EXECUTION_DRY_RUN_{root[:16]}",
        shadow_execution_status=status,
        release_tag=release_tag,
        shadow_deployment_root=shadow_deployment_root,
        real_tag_evidence_root=real_tag_evidence_root,
        external_signing_template_root=external_signing_template_root,
        final_hardening_root=final_hardening_root,
        approval_gate_root=approval_gate_root,
        shadow_execution_evidence_hash=evidence_hash,
        shadow_execution_root=root,
        shadow_execution_ready=ready,
        shadow_execution_performed=ready,
        dry_run_commands_checked=ready,
        tag_evidence_verified=ready,
        shadow_plan_verified=ready,
        approval_gate_verified=ready,
        hardening_verified=ready,
        external_signing_pending=ready,
        production_refused_without_manual_approval=ready,
        live_production_enabled=False,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        external_signature_present=False,
        notes_signed_with_real_key=False,
        secrets_in_evidence=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Shadow deployment execution dry-run candidate only. Non-production dry-run "
            "evidence was recorded; live production remains disabled."
            if ready
            else "Shadow deployment execution dry-run is blocked by missing or invalid upstream evidence."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_execution_record_count": 1,
        "shadow_execution_candidate_count": 1 if ready else 0,
        "shadow_execution_blocked_count": 0 if ready else 1,
        "shadow_execution_status": status,
        "shadow_execution_ready": ready,
        "shadow_execution_performed": ready,
        "release_tag": release_tag,
        "shadow_deployment_root": shadow_deployment_root,
        "real_tag_evidence_root": real_tag_evidence_root,
        "external_signing_template_root": external_signing_template_root,
        "final_hardening_root": final_hardening_root,
        "approval_gate_root": approval_gate_root,
        "shadow_execution_evidence_hash": evidence_hash,
        "shadow_execution_root": root,
        "dry_run_commands_checked": ready,
        "tag_evidence_verified": ready,
        "shadow_plan_verified": ready,
        "approval_gate_verified": ready,
        "hardening_verified": ready,
        "external_signing_pending": ready,
        "production_refused_without_manual_approval": ready,
        "live_production_enabled": False,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "external_signature_present": False,
        "notes_signed_with_real_key": False,
        "secrets_in_evidence": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(EVIDENCE_OUTPUT, evidence)
    return {"payload": payload, "summary": summary, "evidence": evidence}
