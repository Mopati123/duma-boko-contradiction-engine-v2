#!/usr/bin/env python3
"""
Project Completion Certificate Engine v1.

Builds a deterministic JSON-only certificate that Governance Runtime v1 is
engineering-complete and release-candidate-ready. This lane does not authorize
release, approve evidence, sign externally, publish, or mark production ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_FINAL_REPORT = Path(
    "outputs/final_governance_runtime_report/final_governance_runtime_report_summary.json"
)
DEFAULT_INSTITUTIONAL = Path(
    "outputs/institutional_readiness_report/institutional_readiness_report_summary.json"
)
DEFAULT_OPERATIONAL = Path(
    "outputs/operational_history_report/operational_history_report_summary.json"
)
DEFAULT_STRESS = Path("outputs/shadow_runtime_stress_suite/shadow_runtime_stress_summary.json")
DEFAULT_RUNTIME = Path("outputs/shadow_runtime_evidence/shadow_runtime_evidence_summary.json")
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/project_completion_certificate")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "project_completion_certificate_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "project_completion_certificate_summary.json"
CERTIFICATE_OUTPUT = DEFAULT_OUTPUT_DIR / "project_completion_certificate.json"

FINAL_STATUS_STATEMENT = (
    "The governance runtime v1 project is engineering-complete and release-candidate-ready. "
    "Production authorization remains blocked until external manual approval, external signing, "
    "and deliberate deployment authorization are completed."
)

REQUIRED_CERTIFICATE_SECTIONS = (
    "completed_capabilities",
    "verified_roots",
    "release_tag",
    "stress_metrics",
    "operational_history_metrics",
    "remaining_manual_actions",
    "final_status_statement",
)

ALLOWED_STATUSES = {
    "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE",
    "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_MISSING_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS",
    "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS",
    "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "PROJECT_COMPLETION_CERTIFICATE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "release_authorized",
    "manual_approval_present",
    "notes_signed_with_real_key",
    "external_signature_present",
    "approved_evidence",
    "live_production_enabled",
    "production_mutation_allowed",
    "secrets_in_evidence",
    "secrets_detected",
)


@dataclass
class ProjectCompletionCertificateRecord:
    project_completion_id: str
    project_completion_status: str
    project_phase: str
    release_tag: str
    final_governance_runtime_report_root: str
    institutional_readiness_report_root: str
    operational_history_report_root: str
    shadow_stress_root: str
    shadow_runtime_root: str
    real_tag_evidence_root: str
    approval_gate_root: str
    final_hardening_root: str
    project_completion_certificate_hash: str
    project_completion_certificate_root: str
    engineering_complete: bool
    release_candidate_complete: bool
    shadow_validation_complete: bool
    stress_validation_complete: bool
    final_reporting_complete: bool
    external_governance_pending: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
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
    final_report: Dict[str, Any],
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    real_tag: Dict[str, Any],
    approval_gate: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> str:
    if not final_report:
        return "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("final_report_status") != "FINAL_GOVERNANCE_RUNTIME_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("final_report_ready") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("tag_verified") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("external_signing_pending") is not True:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _closed_release_flags(final_report):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _is_nonzero_hash(final_report.get("final_governance_runtime_report_root")):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"

    if not institutional:
        return "BLOCKED_MISSING_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("institutional_report_status") != "INSTITUTIONAL_READINESS_REPORT_CANDIDATE":
        return "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT"
    if institutional.get("institutional_report_ready") is not True:
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
    if not _closed_release_flags(stress):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _is_nonzero_hash(stress.get("shadow_stress_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"

    if not runtime:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_runtime_status") != "SHADOW_RUNTIME_EVIDENCE_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_runtime_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_cycle_count") != 12 or runtime.get("shadow_success_count") != 12:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_refusal_count") != 0 or runtime.get("shadow_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("reconciliation_passed") is not True or runtime.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _closed_release_flags(runtime):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _is_nonzero_hash(runtime.get("shadow_runtime_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"

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
    if not _closed_release_flags(real_tag):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _is_nonzero_hash(real_tag.get("real_tag_evidence_root")):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"

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

    return "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE"


def _build_certificate(
    status: str,
    release_tag: str,
    final_report: Dict[str, Any],
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    real_tag: Dict[str, Any],
    approval_gate: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE"
    return {
        "completed_capabilities": {
            "engineering_complete": ready,
            "release_candidate_complete": ready,
            "shadow_validation_complete": ready,
            "stress_validation_complete": ready,
            "final_reporting_complete": ready,
            "governance_runtime_v1_complete": ready,
        },
        "verified_roots": {
            "final_governance_runtime_report_root": str(
                final_report.get("final_governance_runtime_report_root") or ""
            ),
            "institutional_readiness_report_root": str(
                institutional.get("institutional_readiness_report_root") or ""
            ),
            "operational_history_report_root": str(
                operational.get("operational_history_report_root") or ""
            ),
            "shadow_stress_root": str(stress.get("shadow_stress_root") or ""),
            "shadow_runtime_root": str(runtime.get("shadow_runtime_root") or ""),
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "final_hardening_root": str(final_hardening.get("final_hardening_root") or ""),
        },
        "release_tag": release_tag,
        "stress_metrics": {
            "stress_targets": stress.get("stress_targets") or [],
            "total_shadow_cycles": int(stress.get("total_shadow_cycles") or 0),
            "stress_success_count": int(stress.get("stress_success_count") or 0),
            "stress_refusal_count": int(stress.get("stress_refusal_count") or 0),
            "stress_failure_count": int(stress.get("stress_failure_count") or 0),
            "reconciliation_passed": stress.get("reconciliation_passed") is True,
            "drift_detected": False,
        },
        "operational_history_metrics": {
            "total_shadow_cycles": int(operational.get("total_shadow_cycles") or 0),
            "baseline_cycles": int(operational.get("baseline_cycles") or 0),
            "stress_cycles": int(operational.get("stress_cycles") or 0),
            "total_success_count": int(operational.get("total_success_count") or 0),
            "total_refusal_count": int(operational.get("total_refusal_count") or 0),
            "total_failure_count": int(operational.get("total_failure_count") or 0),
            "reconciliation_passed": operational.get("reconciliation_passed") is True,
            "drift_detected": False,
        },
        "remaining_manual_actions": [
            "create_external_manual_approval_artifact",
            "sign_release_notes_with_external_key",
            "record_external_signature_evidence",
            "authorize_release_deliberately",
            "authorize_production_deployment_deliberately",
        ],
        "final_status_statement": FINAL_STATUS_STATEMENT,
    }


def validate_certificate(certificate: Dict[str, Any]) -> None:
    if tuple(certificate.keys()) != REQUIRED_CERTIFICATE_SECTIONS:
        raise ValueError("project_completion_certificate must contain exactly the required sections")
    if certificate.get("final_status_statement") != FINAL_STATUS_STATEMENT:
        raise ValueError("final_status_statement must match the required text")


def validate_record(record: ProjectCompletionCertificateRecord) -> None:
    data = record.to_dict()
    required = {
        "project_completion_id",
        "project_completion_status",
        "project_phase",
        "release_tag",
        "final_governance_runtime_report_root",
        "institutional_readiness_report_root",
        "operational_history_report_root",
        "shadow_stress_root",
        "shadow_runtime_root",
        "real_tag_evidence_root",
        "approval_gate_root",
        "final_hardening_root",
        "project_completion_certificate_hash",
        "project_completion_certificate_root",
        "engineering_complete",
        "release_candidate_complete",
        "shadow_validation_complete",
        "stress_validation_complete",
        "final_reporting_complete",
        "external_governance_pending",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "approved_evidence",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ProjectCompletionCertificateRecord missing fields: {sorted(missing)}")
    if data["project_completion_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported project_completion_status: {data['project_completion_status']}")
    if data["project_phase"] != "GOVERNANCE_RUNTIME_V1_COMPLETE":
        raise ValueError("project_phase must be GOVERNANCE_RUNTIME_V1_COMPLETE")
    if data["project_completion_status"] == "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE":
        for key in (
            "final_governance_runtime_report_root",
            "institutional_readiness_report_root",
            "operational_history_report_root",
            "shadow_stress_root",
            "shadow_runtime_root",
            "real_tag_evidence_root",
            "approval_gate_root",
            "final_hardening_root",
            "project_completion_certificate_hash",
            "project_completion_certificate_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        for key in (
            "engineering_complete",
            "release_candidate_complete",
            "shadow_validation_complete",
            "stress_validation_complete",
            "final_reporting_complete",
            "external_governance_pending",
        ):
            if data[key] is not True:
                raise ValueError(f"{key} must be true for candidate output")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_project_completion_certificate(
    final_report_path: Path = DEFAULT_FINAL_REPORT,
    institutional_path: Path = DEFAULT_INSTITUTIONAL,
    operational_path: Path = DEFAULT_OPERATIONAL,
    stress_path: Path = DEFAULT_STRESS,
    runtime_path: Path = DEFAULT_RUNTIME,
    real_tag_path: Path = DEFAULT_REAL_TAG,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
) -> Dict[str, Any]:
    final_report = _load_json(final_report_path)
    institutional = _load_json(institutional_path)
    operational = _load_json(operational_path)
    stress = _load_json(stress_path)
    runtime = _load_json(runtime_path)
    real_tag = _load_json(real_tag_path)
    approval_gate = _load_json(approval_gate_path)
    final_hardening = _load_json(final_hardening_path)
    status = _determine_status(
        final_report,
        institutional,
        operational,
        stress,
        runtime,
        real_tag,
        approval_gate,
        final_hardening,
    )
    ready = status == "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE"
    release_tag = str(
        final_report.get("release_candidate_tag")
        or institutional.get("release_tag")
        or operational.get("release_tag")
        or real_tag.get("tag_name")
        or ""
    )
    certificate = _build_certificate(
        status,
        release_tag,
        final_report,
        institutional,
        operational,
        stress,
        runtime,
        real_tag,
        approval_gate,
        final_hardening,
    )
    validate_certificate(certificate)
    certificate_hash = _hash_json(certificate)
    root = _hash_json(
        {
            "project_completion_status": status,
            "project_phase": "GOVERNANCE_RUNTIME_V1_COMPLETE",
            "release_tag": release_tag,
            "project_completion_certificate_hash": certificate_hash,
            "final_governance_runtime_report_root": str(
                final_report.get("final_governance_runtime_report_root") or ""
            ),
            "institutional_readiness_report_root": str(
                institutional.get("institutional_readiness_report_root") or ""
            ),
            "operational_history_report_root": str(
                operational.get("operational_history_report_root") or ""
            ),
            "shadow_stress_root": str(stress.get("shadow_stress_root") or ""),
            "shadow_runtime_root": str(runtime.get("shadow_runtime_root") or ""),
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "final_hardening_root": str(final_hardening.get("final_hardening_root") or ""),
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
        }
    )
    record = ProjectCompletionCertificateRecord(
        project_completion_id=f"PROJECT_COMPLETION_CERTIFICATE_{root[:16]}",
        project_completion_status=status,
        project_phase="GOVERNANCE_RUNTIME_V1_COMPLETE",
        release_tag=release_tag,
        final_governance_runtime_report_root=str(
            final_report.get("final_governance_runtime_report_root") or ""
        ),
        institutional_readiness_report_root=str(
            institutional.get("institutional_readiness_report_root") or ""
        ),
        operational_history_report_root=str(operational.get("operational_history_report_root") or ""),
        shadow_stress_root=str(stress.get("shadow_stress_root") or ""),
        shadow_runtime_root=str(runtime.get("shadow_runtime_root") or ""),
        real_tag_evidence_root=str(real_tag.get("real_tag_evidence_root") or ""),
        approval_gate_root=str(approval_gate.get("approval_gate_root") or ""),
        final_hardening_root=str(final_hardening.get("final_hardening_root") or ""),
        project_completion_certificate_hash=certificate_hash,
        project_completion_certificate_root=root,
        engineering_complete=ready,
        release_candidate_complete=ready,
        shadow_validation_complete=ready,
        stress_validation_complete=ready,
        final_reporting_complete=ready,
        external_governance_pending=True,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        approved_evidence=0,
        notes=(
            "Project completion certificate candidate only. Governance Runtime v1 is "
            "engineering-complete, while external governance and production authorization remain pending."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "project_completion_record_count": 1,
        "project_completion_candidate_count": 1 if ready else 0,
        "project_completion_blocked_count": 0 if ready else 1,
        "project_completion_status": status,
        "project_phase": "GOVERNANCE_RUNTIME_V1_COMPLETE",
        "release_tag": release_tag,
        "final_governance_runtime_report_root": record.final_governance_runtime_report_root,
        "institutional_readiness_report_root": record.institutional_readiness_report_root,
        "operational_history_report_root": record.operational_history_report_root,
        "shadow_stress_root": record.shadow_stress_root,
        "shadow_runtime_root": record.shadow_runtime_root,
        "real_tag_evidence_root": record.real_tag_evidence_root,
        "approval_gate_root": record.approval_gate_root,
        "final_hardening_root": record.final_hardening_root,
        "project_completion_certificate_hash": certificate_hash,
        "project_completion_certificate_root": root,
        "engineering_complete": ready,
        "release_candidate_complete": ready,
        "shadow_validation_complete": ready,
        "stress_validation_complete": ready,
        "final_reporting_complete": ready,
        "external_governance_pending": True,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "approved_evidence": 0,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CERTIFICATE_OUTPUT, certificate)
    return {"payload": payload, "summary": summary, "certificate": certificate}
