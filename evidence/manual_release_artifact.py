#!/usr/bin/env python3
"""
Manual Release Artifact Template Engine v1.

Builds a deterministic manual approval artifact template. This lane does not
create real manual approval, real Git tags, real signatures, private keys,
secrets, release authorization, or production readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_RELEASE_EXECUTION = Path(
    "outputs/release_execution_checklist/release_execution_checklist_summary.json"
)
DEFAULT_RELEASE_TAG = Path("outputs/release_tag_and_signed_notes/release_tag_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/manual_release_artifact")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_release_artifact_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_release_artifact_summary.json"
TEMPLATE_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_approval_template.json"

PLACEHOLDER = "PENDING_MANUAL_ENTRY"

ALLOWED_STATUSES = {
    "MANUAL_RELEASE_ARTIFACT_TEMPLATE_CANDIDATE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_MISSING_RELEASE_EXECUTION_CHECKLIST",
    "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST",
    "BLOCKED_MISSING_RELEASE_TAG",
    "BLOCKED_INVALID_RELEASE_TAG",
    "MANUAL_RELEASE_ARTIFACT_TEMPLATE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "manual_approval_present",
    "release_authorized",
    "production_ready",
    "real_git_tag_created",
    "real_signature_present",
    "secrets_detected",
    "generated_outputs_committed",
    "git_tag_created",
    "notes_signed_with_real_key",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ManualReleaseArtifactRecord:
    manual_release_artifact_id: str
    manual_release_artifact_status: str
    release_tag: str
    release_candidate_root: str
    final_hardening_root: str
    approval_gate_root: str
    release_execution_root: str
    manual_approval_template_hash: str
    manual_release_artifact_root: str
    manual_approval_template_ready: bool
    manual_approval_present: bool
    release_authorized: bool
    production_ready: bool
    real_git_tag_created: bool
    real_signature_present: bool
    secrets_detected: bool
    generated_outputs_committed: bool
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
    final_hardening: Dict[str, Any],
    approval_gate: Dict[str, Any],
    release_execution: Dict[str, Any],
    release_tag: Dict[str, Any],
) -> str:
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
    if approval_gate.get("git_tag_created") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

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
    if release_execution.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_RELEASE_EXECUTION_CHECKLIST"
    if not _closed_release_flags(release_execution):
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
    if not _closed_release_flags(release_tag):
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _is_nonzero_hash(release_tag.get("release_candidate_root")):
        return "BLOCKED_INVALID_RELEASE_TAG"

    return "MANUAL_RELEASE_ARTIFACT_TEMPLATE_CANDIDATE"


def _manual_approval_template(release_tag: str, release_candidate_root: str) -> Dict[str, Any]:
    return {
        "manual_approval_template_version": "manual_release_artifact_v1",
        "template_only": True,
        "placeholder_values_are_not_approval": True,
        "manual_approval_present": False,
        "release_authorized": False,
        "production_ready": False,
        "required_fields": {
            "approver_name": PLACEHOLDER,
            "approver_role": PLACEHOLDER,
            "approval_timestamp_utc": PLACEHOLDER,
            "approved_release_tag": release_tag or PLACEHOLDER,
            "approved_release_candidate_root": release_candidate_root or PLACEHOLDER,
            "approval_statement": PLACEHOLDER,
            "external_signature_reference": PLACEHOLDER,
            "approval_artifact_hash": PLACEHOLDER,
        },
        "validation_requirements": {
            "approver_name_non_placeholder": True,
            "approver_role_non_placeholder": True,
            "approval_timestamp_utc_non_placeholder": True,
            "approved_release_tag_matches_candidate": True,
            "approved_release_candidate_root_matches_candidate": True,
            "approval_statement_non_placeholder": True,
            "external_signature_reference_non_placeholder": True,
            "approval_artifact_hash_non_placeholder_sha256": True,
            "private_keys_or_secrets_absent": True,
        },
        "forbidden_in_template_lane": {
            "real_git_tag_created": True,
            "real_signature_present": True,
            "manual_approval_present": True,
            "release_authorized": True,
            "production_ready": True,
        },
    }


def validate_record(record: ManualReleaseArtifactRecord) -> None:
    data = record.to_dict()

    required = {
        "manual_release_artifact_id",
        "manual_release_artifact_status",
        "release_tag",
        "release_candidate_root",
        "final_hardening_root",
        "approval_gate_root",
        "release_execution_root",
        "manual_approval_template_hash",
        "manual_release_artifact_root",
        "manual_approval_template_ready",
        "manual_approval_present",
        "release_authorized",
        "production_ready",
        "real_git_tag_created",
        "real_signature_present",
        "secrets_detected",
        "generated_outputs_committed",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ManualReleaseArtifactRecord missing fields: {sorted(missing)}")

    if data["manual_release_artifact_status"] not in ALLOWED_STATUSES:
        raise ValueError(
            "Unsupported manual_release_artifact_status: "
            f"{data['manual_release_artifact_status']}"
        )

    if data["manual_release_artifact_status"] == "MANUAL_RELEASE_ARTIFACT_TEMPLATE_CANDIDATE":
        for key in (
            "release_candidate_root",
            "final_hardening_root",
            "approval_gate_root",
            "release_execution_root",
            "manual_approval_template_hash",
            "manual_release_artifact_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")

        if data["manual_approval_template_ready"] is not True:
            raise ValueError("manual_approval_template_ready must be true for candidate output")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_manual_release_artifact(
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    release_execution_path: Path = DEFAULT_RELEASE_EXECUTION,
    release_tag_path: Path = DEFAULT_RELEASE_TAG,
) -> Dict[str, Any]:
    final_hardening = _load_json(final_hardening_path)
    approval_gate = _load_json(approval_gate_path)
    release_execution = _load_json(release_execution_path)
    release_tag_summary = _load_json(release_tag_path)

    status = _determine_status(
        final_hardening,
        approval_gate,
        release_execution,
        release_tag_summary,
    )

    release_tag = str(release_tag_summary.get("release_tag") or "v1.0.0-rc1-governance-runtime")
    release_candidate_root = str(release_tag_summary.get("release_candidate_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")
    release_execution_root = str(release_execution.get("release_execution_root") or "")

    template = _manual_approval_template(release_tag, release_candidate_root)
    template_hash = _hash_json(template)
    artifact_root = _hash_json(
        {
            "manual_release_artifact_status": status,
            "release_tag": release_tag,
            "release_candidate_root": release_candidate_root,
            "final_hardening_root": final_hardening_root,
            "approval_gate_root": approval_gate_root,
            "release_execution_root": release_execution_root,
            "manual_approval_template_hash": template_hash,
            "manual_approval_present": False,
            "release_authorized": False,
            "production_ready": False,
            "real_git_tag_created": False,
            "real_signature_present": False,
        }
    )
    ready = status == "MANUAL_RELEASE_ARTIFACT_TEMPLATE_CANDIDATE"

    record = ManualReleaseArtifactRecord(
        manual_release_artifact_id=f"MANUAL_RELEASE_ARTIFACT_{artifact_root[:16]}",
        manual_release_artifact_status=status,
        release_tag=release_tag,
        release_candidate_root=release_candidate_root,
        final_hardening_root=final_hardening_root,
        approval_gate_root=approval_gate_root,
        release_execution_root=release_execution_root,
        manual_approval_template_hash=template_hash,
        manual_release_artifact_root=artifact_root,
        manual_approval_template_ready=ready,
        manual_approval_present=False,
        release_authorized=False,
        production_ready=False,
        real_git_tag_created=False,
        real_signature_present=False,
        secrets_detected=False,
        generated_outputs_committed=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Manual release artifact template candidate only. Placeholder values do not "
            "constitute approval, release authorization, signing, tagging, or production readiness."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}
    summary = {
        "manual_release_artifact_record_count": 1,
        "manual_release_artifact_candidate_count": 1 if ready else 0,
        "manual_release_artifact_blocked_count": 0 if ready else 1,
        "manual_release_artifact_invalid_count": 0,
        "manual_release_artifact_status": status,
        "manual_approval_template_ready": ready,
        "release_tag": release_tag,
        "release_candidate_root": release_candidate_root,
        "final_hardening_root": final_hardening_root,
        "approval_gate_root": approval_gate_root,
        "release_execution_root": release_execution_root,
        "manual_approval_template_hash": template_hash,
        "manual_release_artifact_root": artifact_root,
        "manual_approval_present": False,
        "release_authorized": False,
        "production_ready": False,
        "real_git_tag_created": False,
        "real_signature_present": False,
        "secrets_detected": False,
        "generated_outputs_committed": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(TEMPLATE_OUTPUT, template)

    return {
        "payload": payload,
        "summary": summary,
        "manual_approval_template": template,
    }
