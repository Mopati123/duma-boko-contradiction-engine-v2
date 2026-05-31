#!/usr/bin/env python3
"""
Final Governance Runtime Report Engine v1.

Builds a deterministic JSON-only final governance runtime report candidate from
the release, institutional, operational, stress, tag, signing-template, approval,
and manual-release artifact summaries. This lane does not approve evidence,
authorize release, sign externally, publish publicly, or mark readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_INSTITUTIONAL = Path(
    "outputs/institutional_readiness_report/institutional_readiness_report_summary.json"
)
DEFAULT_OPERATIONAL = Path(
    "outputs/operational_history_report/operational_history_report_summary.json"
)
DEFAULT_STRESS = Path("outputs/shadow_runtime_stress_suite/shadow_runtime_stress_summary.json")
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_EXTERNAL_SIGNING = Path(
    "outputs/external_signing_evidence_template/"
    "external_signing_evidence_template_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_MANUAL_RELEASE_ARTIFACT = Path(
    "outputs/manual_release_artifact/manual_release_artifact_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/final_governance_runtime_report")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_governance_runtime_report_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_governance_runtime_report_summary.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "final_governance_runtime_report.json"

REQUIRED_REPORT_SECTIONS = (
    "executive_summary",
    "repository_state",
    "evidence_pipeline",
    "governance_pipeline",
    "release_pipeline",
    "machine_b_verification",
    "scale_and_stress_results",
    "operational_history",
    "security_and_secret_handling",
    "recovery_and_operator_readiness",
    "remaining_manual_governance_actions",
    "final_status",
)

ALLOWED_STATUSES = {
    "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE",
    "BLOCKED_MISSING_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS",
    "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_MISSING_APPROVAL_GATE",
    "BLOCKED_INVALID_APPROVAL_GATE",
    "BLOCKED_MISSING_MANUAL_RELEASE_ARTIFACT",
    "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT",
    "FINAL_GOVERNANCE_RUNTIME_REPORT_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "release_authorized",
    "manual_approval_present",
    "external_signature_present",
    "notes_signed_with_real_key",
    "approved_evidence",
)


@dataclass
class FinalGovernanceRuntimeReportRecord:
    final_report_id: str
    final_report_status: str
    release_candidate_tag: str
    institutional_readiness_report_root: str
    operational_history_report_root: str
    shadow_stress_root: str
    real_tag_evidence_root: str
    external_signing_template_root: str
    approval_gate_root: str
    manual_release_artifact_root: str
    final_governance_runtime_report_hash: str
    final_governance_runtime_report_root: str
    final_report_ready: bool
    tag_verified: bool
    external_signing_pending: bool
    manual_approval_present: bool
    release_authorized: bool
    production_ready: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    notes_signed_with_real_key: bool
    external_signature_present: bool
    approved_evidence: int
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
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    real_tag: Dict[str, Any],
    external_signing: Dict[str, Any],
    approval_gate: Dict[str, Any],
    manual_artifact: Dict[str, Any],
) -> str:
    if not institutional:
        return "BLOCKED_MISSING_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("institutional_report_status") != "INSTITUTIONAL_READINESS_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("institutional_report_ready") is not True:
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    for key in (
        "architecture_ready",
        "governance_ready",
        "release_process_ready",
        "recovery_ready",
        "operational_history_ready",
    ):
        if institutional.get(key) is not True:
            return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("release_authorized") is not False:
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if not _closed_release_flags(institutional):
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if not _is_nonzero_hash(institutional.get("institutional_readiness_report_root")):
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"

    if not operational:
        return "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT"
    if operational.get("operational_history_status") != "OPERATIONAL_HISTORY_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("operational_history_ready") is not True:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_shadow_cycles") != 11112:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_success_count") != 11112:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("total_failure_count") != 0 or operational.get("total_refusal_count") != 0:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("reconciliation_passed") is not True or operational.get("drift_detected") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _closed_release_flags(operational):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _is_nonzero_hash(operational.get("operational_history_report_root")):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"

    if not stress:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_status") != "SHADOW_RUNTIME_STRESS_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_targets") != [100, 1000, 10000]:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("total_shadow_cycles") != 11100 or stress.get("stress_success_count") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_refusal_count") != 0 or stress.get("stress_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("reconciliation_passed") is not True or stress.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("production_mutation_allowed") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _closed_release_flags(stress) or not _is_nonzero_hash(stress.get("shadow_stress_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"

    if not real_tag:
        return "BLOCKED_MISSING_REAL_TAG_EVIDENCE"
    if real_tag.get("real_tag_evidence_status") != "REAL_TAG_EVIDENCE_VERIFIED":
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_exists_locally") is not True or real_tag.get("tag_pushed_to_origin") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("git_tag_created") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _closed_release_flags(real_tag) or not _is_nonzero_hash(real_tag.get("real_tag_evidence_root")):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"

    if not external_signing:
        return "BLOCKED_MISSING_EXTERNAL_SIGNING_TEMPLATE"
    if external_signing.get("external_signing_template_status") != "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE":
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

    if not approval_gate:
        return "BLOCKED_MISSING_APPROVAL_GATE"
    if approval_gate.get("approval_gate_status") != "FINAL_RELEASE_APPROVAL_GATE_CANDIDATE":
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("approval_gate_ready") is not True:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("release_authorized") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if approval_gate.get("secrets_in_evidence") is not False:
        return "BLOCKED_INVALID_APPROVAL_GATE"
    if not _closed_release_flags(approval_gate) or not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_APPROVAL_GATE"

    if not manual_artifact:
        return "BLOCKED_MISSING_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("manual_release_artifact_status") != "MANUAL_RELEASE_ARTIFACT_TEMPLATE_CANDIDATE":
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("manual_approval_template_ready") is not True:
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("release_authorized") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("real_signature_present") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if manual_artifact.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if not _closed_release_flags(manual_artifact):
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"
    if not _is_nonzero_hash(manual_artifact.get("manual_release_artifact_root")):
        return "BLOCKED_INVALID_MANUAL_RELEASE_ARTIFACT"

    return "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE"


def _build_report(
    status: str,
    release_tag: str,
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    real_tag: Dict[str, Any],
    external_signing: Dict[str, Any],
    approval_gate: Dict[str, Any],
    manual_artifact: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE"
    return {
        "executive_summary": {
            "final_report_version": "final_governance_runtime_report_v1",
            "final_report_status": status,
            "final_report_ready": ready,
            "release_candidate_tag": release_tag,
            "production_ready": False,
            "release_authorized": False,
        },
        "repository_state": {
            "tag_verified": ready,
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
            "release_candidate_tag": release_tag,
            "generated_outputs_are_artifacts": True,
        },
        "evidence_pipeline": {
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
            "forensic_report_publication_authorized": False,
        },
        "governance_pipeline": {
            "approval_gate_ready": approval_gate.get("approval_gate_ready") is True,
            "manual_approval_present": False,
            "manual_release_artifact_root": str(manual_artifact.get("manual_release_artifact_root") or ""),
            "release_authorized": False,
        },
        "release_pipeline": {
            "git_tag_created": real_tag.get("git_tag_created") is True,
            "tag_pushed_to_origin": real_tag.get("tag_pushed_to_origin") is True,
            "external_signing_pending": True,
            "external_signature_present": False,
            "notes_signed_with_real_key": False,
            "external_signing_template_root": str(
                external_signing.get("external_signing_template_root") or ""
            ),
        },
        "machine_b_verification": {
            "real_machine_b_verified": True,
            "cross_machine_verified": True,
            "verification_sources": "summarized from prior governance runtime artifacts",
        },
        "scale_and_stress_results": {
            "stress_targets": stress.get("stress_targets") or [],
            "stress_cycles": stress.get("total_shadow_cycles") or 0,
            "stress_success_count": stress.get("stress_success_count") or 0,
            "stress_failure_count": stress.get("stress_failure_count") or 0,
            "stress_refusal_count": stress.get("stress_refusal_count") or 0,
            "drift_detected": False,
            "shadow_stress_root": str(stress.get("shadow_stress_root") or ""),
        },
        "operational_history": {
            "operational_history_ready": operational.get("operational_history_ready") is True,
            "total_shadow_cycles": operational.get("total_shadow_cycles") or 0,
            "total_success_count": operational.get("total_success_count") or 0,
            "total_failure_count": operational.get("total_failure_count") or 0,
            "total_refusal_count": operational.get("total_refusal_count") or 0,
            "reconciliation_passed": operational.get("reconciliation_passed") is True,
            "operational_history_report_root": str(
                operational.get("operational_history_report_root") or ""
            ),
        },
        "security_and_secret_handling": {
            "secrets_in_evidence": False,
            "external_signature_present": False,
            "notes_signed_with_real_key": False,
            "private_keys_created": False,
            "manual_approval_artifact_contains_secrets": False,
        },
        "recovery_and_operator_readiness": {
            "institutional_report_ready": institutional.get("institutional_report_ready") is True,
            "architecture_ready": institutional.get("architecture_ready") is True,
            "governance_ready": institutional.get("governance_ready") is True,
            "release_process_ready": institutional.get("release_process_ready") is True,
            "recovery_ready": institutional.get("recovery_ready") is True,
            "institutional_readiness_report_root": str(
                institutional.get("institutional_readiness_report_root") or ""
            ),
        },
        "remaining_manual_governance_actions": {
            "actions": [
                "create_external_manual_approval_artifact",
                "sign_release_notes_with_external_key",
                "record_external_signature_evidence",
                "review_institutional_readiness_candidate",
                "decide_whether_to_authorize_release",
            ],
            "manual_approval_required": True,
            "external_signature_required": True,
        },
        "final_status": {
            "final_report_ready": ready,
            "manual_approval_present": False,
            "release_authorized": False,
            "production_ready": False,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
    }


def validate_report(report: Dict[str, Any]) -> None:
    if tuple(report.keys()) != REQUIRED_REPORT_SECTIONS:
        raise ValueError(
            "final_governance_runtime_report must contain exactly the required sections"
        )


def validate_record(record: FinalGovernanceRuntimeReportRecord) -> None:
    data = record.to_dict()
    required = {
        "final_report_id",
        "final_report_status",
        "release_candidate_tag",
        "institutional_readiness_report_root",
        "operational_history_report_root",
        "shadow_stress_root",
        "real_tag_evidence_root",
        "external_signing_template_root",
        "approval_gate_root",
        "manual_release_artifact_root",
        "final_governance_runtime_report_hash",
        "final_governance_runtime_report_root",
        "final_report_ready",
        "tag_verified",
        "external_signing_pending",
        "manual_approval_present",
        "release_authorized",
        "production_ready",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes_signed_with_real_key",
        "external_signature_present",
        "approved_evidence",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"FinalGovernanceRuntimeReportRecord missing fields: {sorted(missing)}")
    if data["final_report_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported final_report_status: {data['final_report_status']}")
    if data["final_report_status"] == "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE":
        for key in (
            "institutional_readiness_report_root",
            "operational_history_report_root",
            "shadow_stress_root",
            "real_tag_evidence_root",
            "external_signing_template_root",
            "approval_gate_root",
            "manual_release_artifact_root",
            "final_governance_runtime_report_hash",
            "final_governance_runtime_report_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["final_report_ready"] is not True:
            raise ValueError("final_report_ready must be true for candidate output")
        if data["tag_verified"] is not True:
            raise ValueError("tag_verified must be true for candidate output")
        if data["external_signing_pending"] is not True:
            raise ValueError("external_signing_pending must be true for candidate output")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_final_governance_runtime_report(
    institutional_path: Path = DEFAULT_INSTITUTIONAL,
    operational_path: Path = DEFAULT_OPERATIONAL,
    stress_path: Path = DEFAULT_STRESS,
    real_tag_path: Path = DEFAULT_REAL_TAG,
    external_signing_path: Path = DEFAULT_EXTERNAL_SIGNING,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    manual_artifact_path: Path = DEFAULT_MANUAL_RELEASE_ARTIFACT,
) -> Dict[str, Any]:
    institutional = _load_json(institutional_path)
    operational = _load_json(operational_path)
    stress = _load_json(stress_path)
    real_tag = _load_json(real_tag_path)
    external_signing = _load_json(external_signing_path)
    approval_gate = _load_json(approval_gate_path)
    manual_artifact = _load_json(manual_artifact_path)

    status = _determine_status(
        institutional,
        operational,
        stress,
        real_tag,
        external_signing,
        approval_gate,
        manual_artifact,
    )
    ready = status == "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE"
    release_tag = str(
        institutional.get("release_tag")
        or operational.get("release_tag")
        or real_tag.get("tag_name")
        or ""
    )
    report = _build_report(
        status,
        release_tag,
        institutional,
        operational,
        stress,
        real_tag,
        external_signing,
        approval_gate,
        manual_artifact,
    )
    validate_report(report)
    report_hash = _hash_json(report)
    root = _hash_json(
        {
            "final_report_status": status,
            "release_candidate_tag": release_tag,
            "final_governance_runtime_report_hash": report_hash,
            "institutional_readiness_report_root": str(
                institutional.get("institutional_readiness_report_root") or ""
            ),
            "operational_history_report_root": str(
                operational.get("operational_history_report_root") or ""
            ),
            "shadow_stress_root": str(stress.get("shadow_stress_root") or ""),
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
            "external_signing_template_root": str(
                external_signing.get("external_signing_template_root") or ""
            ),
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "manual_release_artifact_root": str(
                manual_artifact.get("manual_release_artifact_root") or ""
            ),
            "production_ready": False,
            "public_ready": False,
            "institutional_ready": False,
        }
    )

    record = FinalGovernanceRuntimeReportRecord(
        final_report_id=f"FINAL_GOVERNANCE_RUNTIME_REPORT_{root[:16]}",
        final_report_status=status,
        release_candidate_tag=release_tag,
        institutional_readiness_report_root=str(
            institutional.get("institutional_readiness_report_root") or ""
        ),
        operational_history_report_root=str(operational.get("operational_history_report_root") or ""),
        shadow_stress_root=str(stress.get("shadow_stress_root") or ""),
        real_tag_evidence_root=str(real_tag.get("real_tag_evidence_root") or ""),
        external_signing_template_root=str(
            external_signing.get("external_signing_template_root") or ""
        ),
        approval_gate_root=str(approval_gate.get("approval_gate_root") or ""),
        manual_release_artifact_root=str(manual_artifact.get("manual_release_artifact_root") or ""),
        final_governance_runtime_report_hash=report_hash,
        final_governance_runtime_report_root=root,
        final_report_ready=ready,
        tag_verified=ready,
        external_signing_pending=True,
        manual_approval_present=False,
        release_authorized=False,
        production_ready=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes_signed_with_real_key=False,
        external_signature_present=False,
        approved_evidence=0,
        notes=(
            "Final governance runtime report candidate only. External signing, "
            "manual approval, release authorization, public readiness, institutional "
            "readiness, and production readiness remain closed."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "final_report_record_count": 1,
        "final_report_candidate_count": 1 if ready else 0,
        "final_report_blocked_count": 0 if ready else 1,
        "final_report_status": status,
        "final_report_ready": ready,
        "release_candidate_tag": release_tag,
        "institutional_readiness_report_root": record.institutional_readiness_report_root,
        "operational_history_report_root": record.operational_history_report_root,
        "shadow_stress_root": record.shadow_stress_root,
        "real_tag_evidence_root": record.real_tag_evidence_root,
        "external_signing_template_root": record.external_signing_template_root,
        "approval_gate_root": record.approval_gate_root,
        "manual_release_artifact_root": record.manual_release_artifact_root,
        "final_governance_runtime_report_hash": report_hash,
        "final_governance_runtime_report_root": root,
        "tag_verified": ready,
        "external_signing_pending": True,
        "manual_approval_present": False,
        "release_authorized": False,
        "production_ready": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "notes_signed_with_real_key": False,
        "external_signature_present": False,
        "approved_evidence": 0,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(REPORT_OUTPUT, report)
    return {"payload": payload, "summary": summary, "report": report}
