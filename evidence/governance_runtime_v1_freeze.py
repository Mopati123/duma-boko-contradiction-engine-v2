#!/usr/bin/env python3
"""
Governance Runtime v1 Freeze Certificate Engine.

Builds a deterministic JSON-only freeze certificate for the Governance Runtime
v1 lifecycle boundary. This lane does not promote, authorize release, approve
evidence, enable live production, or mark readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_PROJECT_COMPLETION = Path(
    "outputs/project_completion_certificate/project_completion_certificate_summary.json"
)
DEFAULT_FINAL_REPORT = Path(
    "outputs/final_governance_runtime_report/final_governance_runtime_report_summary.json"
)
DEFAULT_SHADOW_OPERATIONS = Path(
    "outputs/shadow_operations_program/shadow_operations_program_summary.json"
)
DEFAULT_TELEMETRY = Path(
    "outputs/shadow_operations_telemetry/shadow_operations_telemetry_summary.json"
)
DEFAULT_TREND = Path(
    "outputs/shadow_operations_trend_analysis/shadow_operations_trend_summary.json"
)
DEFAULT_PROMOTION = Path(
    "outputs/shadow_promotion_assessment/shadow_promotion_assessment_summary.json"
)
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/governance_runtime_v1_freeze")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_runtime_v1_freeze_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_runtime_v1_freeze_summary.json"
CERTIFICATE_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_runtime_v1_freeze_certificate.json"

FREEZE_PHASE = "ENGINEERING_COMPLETE_OBSERVATION_ACTIVE_PROMOTION_REFUSED_PENDING_GOVERNANCE"
FREEZE_STATEMENT = (
    "Governance Runtime v1 is engineering-complete, release-candidate-tagged, "
    "stress-validated, operationally observed, telemetry-measured, trend-assessed, "
    "and promotion-assessed. Promotion remains refused pending external manual "
    "approval, external signature, longitudinal observation, and explicit "
    "production authorization."
)

REMAINING_GOVERNANCE_ACTIONS = [
    "longitudinal_shadow_observation",
    "external_manual_approval",
    "external_signature",
    "production_authorization_decision",
    "monthly_governance_reporting",
]

REQUIRED_CERTIFICATE_SECTIONS = (
    "freeze_statement",
    "completed_engineering_capabilities",
    "completed_validation_capabilities",
    "completed_reporting_capabilities",
    "completed_observation_capabilities",
    "promotion_assessment_summary",
    "remaining_governance_actions",
    "non_promotion_rationale",
    "next_program_recommendation",
    "final_status",
)

PROMOTION_BLOCK_REASONS = [
    "external_manual_approval_missing",
    "external_signature_missing",
    "longitudinal_observation_window_incomplete",
    "live_production_not_enabled",
    "production_authorization_absent",
]

ALLOWED_STATUSES = {
    "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE",
    "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_MISSING_SHADOW_PROMOTION_ASSESSMENT",
    "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "GOVERNANCE_RUNTIME_V1_FREEZE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "release_authorized",
    "manual_approval_present",
    "external_signature_present",
    "notes_signed_with_real_key",
    "live_production_enabled",
    "promotion_recommended",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "approved_evidence",
    "production_mutation_allowed",
    "secrets_in_evidence",
    "secrets_detected",
)


@dataclass
class GovernanceRuntimeV1FreezeRecord:
    freeze_id: str
    freeze_status: str
    freeze_phase: str
    release_tag: str
    project_completion_root: str
    final_governance_runtime_report_root: str
    shadow_operations_root: str
    shadow_telemetry_root: str
    shadow_trend_root: str
    shadow_promotion_assessment_root: str
    real_tag_evidence_root: str
    final_hardening_root: str
    governance_runtime_v1_freeze_certificate_hash: str
    governance_runtime_v1_freeze_root: str
    engineering_complete: bool
    observation_active: bool
    promotion_refused: bool
    promotion_recommended: bool
    external_governance_pending: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
    external_signature_present: bool
    notes_signed_with_real_key: bool
    live_production_enabled: bool
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


def _zero(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) == 0.0


def _determine_status(
    project_completion: Dict[str, Any],
    final_report: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    telemetry: Dict[str, Any],
    trend: Dict[str, Any],
    promotion: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> str:
    if not project_completion:
        return "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_completion_status") != "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_phase") != "GOVERNANCE_RUNTIME_V1_COMPLETE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    for key in (
        "engineering_complete",
        "release_candidate_complete",
        "shadow_validation_complete",
        "stress_validation_complete",
        "final_reporting_complete",
        "external_governance_pending",
    ):
        if project_completion.get(key) is not True:
            return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("release_authorized") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _closed_release_flags(project_completion):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _is_nonzero_hash(project_completion.get("project_completion_certificate_root")):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"

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
    if final_report.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if final_report.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _closed_release_flags(final_report):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"
    if not _is_nonzero_hash(final_report.get("final_governance_runtime_report_root")):
        return "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT"

    if not shadow_operations:
        return "BLOCKED_MISSING_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("shadow_operations_status") != "SHADOW_OPERATIONS_PROGRAM_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("shadow_operations_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("program_phase") != "LONGITUDINAL_SHADOW_OPERATIONS":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("engineering_complete") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("external_governance_pending") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("baseline_shadow_cycles") != 11112:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("stress_cycles") != 11100:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("runtime_cycles") != 12:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if shadow_operations.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if not _closed_release_flags(shadow_operations):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"
    if not _is_nonzero_hash(shadow_operations.get("shadow_operations_root")):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM"

    if not telemetry:
        return "BLOCKED_MISSING_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("shadow_telemetry_status") != "SHADOW_OPERATIONS_TELEMETRY_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("shadow_telemetry_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("total_shadow_cycles") != 11112:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if float(telemetry.get("shadow_health_score") or 0.0) != 100.0:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if float(telemetry.get("shadow_stability_score") or 0.0) != 100.0:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    for key in (
        "cumulative_refusal_rate",
        "cumulative_failure_rate",
        "cumulative_drift_rate",
    ):
        if not _zero(telemetry.get(key)):
            return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if float(telemetry.get("cumulative_reconciliation_rate") or 0.0) != 1.0:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if not _closed_release_flags(telemetry):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if not _is_nonzero_hash(telemetry.get("shadow_telemetry_root")):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"

    if not trend:
        return "BLOCKED_MISSING_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("shadow_trend_status") != "SHADOW_OPERATIONS_TREND_ANALYSIS_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("shadow_trend_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("trend_window") != "BOOTSTRAP_BASELINE":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("promotion_recommended") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    for key in (
        "promotion_readiness_score",
        "health_velocity",
        "stability_velocity",
        "drift_velocity",
        "refusal_velocity",
        "failure_velocity",
    ):
        if not _zero(trend.get(key)):
            return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if trend.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if not _closed_release_flags(trend):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if not _is_nonzero_hash(trend.get("shadow_trend_root")):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"

    if not promotion:
        return "BLOCKED_MISSING_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("shadow_promotion_status") != "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("shadow_promotion_assessment_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("promotion_recommended") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("promotion_blocked") is not True:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("promotion_block_reason_count") != len(PROMOTION_BLOCK_REASONS):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("promotion_block_reasons") != PROMOTION_BLOCK_REASONS:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if not _zero(promotion.get("promotion_readiness_score")):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("promotion_score_passed") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("governance_approval_passed") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("external_signature_passed") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("longitudinal_window_passed") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if not _closed_release_flags(promotion):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if not _is_nonzero_hash(promotion.get("shadow_promotion_assessment_root")):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"

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

    if not final_hardening:
        return "BLOCKED_MISSING_FINAL_HARDENING_AUDIT"
    if final_hardening.get("final_hardening_status") != "FINAL_HARDENING_AUDIT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("final_hardening_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("release_candidate_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("approval_gate_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("release_authorized") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("production_ready") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("generated_outputs_committed") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _closed_release_flags(final_hardening):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _is_nonzero_hash(final_hardening.get("final_hardening_root")):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"

    return "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE"


def _build_certificate(
    status: str,
    release_tag: str,
    project_completion: Dict[str, Any],
    final_report: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    telemetry: Dict[str, Any],
    trend: Dict[str, Any],
    promotion: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE"
    return {
        "freeze_statement": FREEZE_STATEMENT,
        "completed_engineering_capabilities": {
            "engineering_complete": bool(project_completion.get("engineering_complete") is True),
            "release_candidate_complete": bool(
                project_completion.get("release_candidate_complete") is True
            ),
            "project_phase": str(project_completion.get("project_phase") or ""),
            "project_completion_root": str(
                project_completion.get("project_completion_certificate_root") or ""
            ),
        },
        "completed_validation_capabilities": {
            "tag_verified": bool(final_report.get("tag_verified") is True),
            "real_tag_evidence_verified": bool(
                real_tag.get("real_tag_evidence_status") == "REAL_TAG_EVIDENCE_VERIFIED"
            ),
            "stress_validation_complete": bool(
                project_completion.get("stress_validation_complete") is True
            ),
            "shadow_validation_complete": bool(
                project_completion.get("shadow_validation_complete") is True
            ),
            "final_hardening_ready": bool(final_hardening.get("final_hardening_ready") is True),
        },
        "completed_reporting_capabilities": {
            "final_reporting_complete": bool(
                project_completion.get("final_reporting_complete") is True
            ),
            "final_report_ready": bool(final_report.get("final_report_ready") is True),
            "final_governance_runtime_report_root": str(
                final_report.get("final_governance_runtime_report_root") or ""
            ),
            "final_hardening_root": str(final_hardening.get("final_hardening_root") or ""),
        },
        "completed_observation_capabilities": {
            "observation_active": ready,
            "shadow_operations_ready": bool(
                shadow_operations.get("shadow_operations_ready") is True
            ),
            "shadow_telemetry_ready": bool(telemetry.get("shadow_telemetry_ready") is True),
            "shadow_trend_ready": bool(trend.get("shadow_trend_ready") is True),
            "baseline_shadow_cycles": int(shadow_operations.get("baseline_shadow_cycles") or 0),
            "total_shadow_cycles": int(telemetry.get("total_shadow_cycles") or 0),
            "shadow_health_score": float(telemetry.get("shadow_health_score") or 0.0),
            "shadow_stability_score": float(telemetry.get("shadow_stability_score") or 0.0),
        },
        "promotion_assessment_summary": {
            "shadow_promotion_status": str(promotion.get("shadow_promotion_status") or status),
            "promotion_refused": True,
            "promotion_recommended": False,
            "promotion_blocked": True,
            "promotion_block_reasons": PROMOTION_BLOCK_REASONS,
            "shadow_promotion_assessment_root": str(
                promotion.get("shadow_promotion_assessment_root") or ""
            ),
        },
        "remaining_governance_actions": REMAINING_GOVERNANCE_ACTIONS,
        "non_promotion_rationale": {
            "external_governance_pending": True,
            "external_manual_approval_missing": True,
            "external_signature_missing": True,
            "longitudinal_observation_window_incomplete": True,
            "production_authorization_absent": True,
            "live_production_enabled": False,
        },
        "next_program_recommendation": {
            "recommended_program": "continue_longitudinal_shadow_operations",
            "monthly_governance_reporting": True,
            "promotion_consideration_allowed": False,
            "promotion_requires_explicit_future_governance_lane": True,
        },
        "final_status": {
            "freeze_status": status,
            "freeze_phase": FREEZE_PHASE,
            "engineering_complete": True,
            "observation_active": ready,
            "promotion_refused": True,
            "promotion_recommended": False,
            "external_governance_pending": True,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "external_signature_present": False,
            "live_production_enabled": False,
            "public_ready": False,
            "institutional_ready": False,
            "approved_evidence": 0,
            "release_tag": release_tag,
        },
    }


def validate_certificate(certificate: Dict[str, Any]) -> None:
    if tuple(certificate.keys()) != REQUIRED_CERTIFICATE_SECTIONS:
        raise ValueError("governance_runtime_v1_freeze_certificate must contain exactly the required sections")
    if certificate["freeze_statement"] != FREEZE_STATEMENT:
        raise ValueError("freeze_statement changed unexpectedly")
    if certificate["remaining_governance_actions"] != REMAINING_GOVERNANCE_ACTIONS:
        raise ValueError("remaining_governance_actions changed unexpectedly")


def validate_record(record: GovernanceRuntimeV1FreezeRecord) -> None:
    data = record.to_dict()
    required = {
        "freeze_id",
        "freeze_status",
        "freeze_phase",
        "release_tag",
        "project_completion_root",
        "final_governance_runtime_report_root",
        "shadow_operations_root",
        "shadow_telemetry_root",
        "shadow_trend_root",
        "shadow_promotion_assessment_root",
        "real_tag_evidence_root",
        "final_hardening_root",
        "governance_runtime_v1_freeze_certificate_hash",
        "governance_runtime_v1_freeze_root",
        "engineering_complete",
        "observation_active",
        "promotion_refused",
        "promotion_recommended",
        "external_governance_pending",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "external_signature_present",
        "notes_signed_with_real_key",
        "live_production_enabled",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "approved_evidence",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"GovernanceRuntimeV1FreezeRecord missing fields: {sorted(missing)}")
    if data["freeze_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported freeze_status: {data['freeze_status']}")
    if data["freeze_phase"] != FREEZE_PHASE:
        raise ValueError("freeze_phase changed unexpectedly")
    if data["engineering_complete"] is not True:
        raise ValueError("engineering_complete must remain true")
    if data["promotion_refused"] is not True:
        raise ValueError("promotion_refused must remain true")
    if data["external_governance_pending"] is not True:
        raise ValueError("external_governance_pending must remain true")
    if data["freeze_status"] == "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE":
        if data["observation_active"] is not True:
            raise ValueError("observation_active must be true for candidate output")
        for key in (
            "project_completion_root",
            "final_governance_runtime_report_root",
            "shadow_operations_root",
            "shadow_telemetry_root",
            "shadow_trend_root",
            "shadow_promotion_assessment_root",
            "real_tag_evidence_root",
            "final_hardening_root",
            "governance_runtime_v1_freeze_certificate_hash",
            "governance_runtime_v1_freeze_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_governance_runtime_v1_freeze(
    project_completion_path: Path = DEFAULT_PROJECT_COMPLETION,
    final_report_path: Path = DEFAULT_FINAL_REPORT,
    shadow_operations_path: Path = DEFAULT_SHADOW_OPERATIONS,
    telemetry_path: Path = DEFAULT_TELEMETRY,
    trend_path: Path = DEFAULT_TREND,
    promotion_path: Path = DEFAULT_PROMOTION,
    real_tag_path: Path = DEFAULT_REAL_TAG,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
) -> Dict[str, Any]:
    project_completion = _load_json(project_completion_path)
    final_report = _load_json(final_report_path)
    shadow_operations = _load_json(shadow_operations_path)
    telemetry = _load_json(telemetry_path)
    trend = _load_json(trend_path)
    promotion = _load_json(promotion_path)
    real_tag = _load_json(real_tag_path)
    final_hardening = _load_json(final_hardening_path)
    status = _determine_status(
        project_completion,
        final_report,
        shadow_operations,
        telemetry,
        trend,
        promotion,
        real_tag,
        final_hardening,
    )
    ready = status == "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE"
    release_tag = str(
        project_completion.get("release_tag")
        or final_report.get("release_candidate_tag")
        or shadow_operations.get("release_tag")
        or real_tag.get("tag_name")
        or ""
    )
    certificate = _build_certificate(
        status,
        release_tag,
        project_completion,
        final_report,
        shadow_operations,
        telemetry,
        trend,
        promotion,
        real_tag,
        final_hardening,
    )
    validate_certificate(certificate)
    certificate_hash = _hash_json(certificate)
    project_completion_root = str(project_completion.get("project_completion_certificate_root") or "")
    final_report_root = str(final_report.get("final_governance_runtime_report_root") or "")
    shadow_operations_root = str(shadow_operations.get("shadow_operations_root") or "")
    telemetry_root = str(telemetry.get("shadow_telemetry_root") or "")
    trend_root = str(trend.get("shadow_trend_root") or "")
    promotion_root = str(promotion.get("shadow_promotion_assessment_root") or "")
    real_tag_root = str(real_tag.get("real_tag_evidence_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    root = _hash_json(
        {
            "freeze_status": status,
            "freeze_phase": FREEZE_PHASE,
            "release_tag": release_tag,
            "governance_runtime_v1_freeze_certificate_hash": certificate_hash,
            "project_completion_root": project_completion_root,
            "final_governance_runtime_report_root": final_report_root,
            "shadow_operations_root": shadow_operations_root,
            "shadow_telemetry_root": telemetry_root,
            "shadow_trend_root": trend_root,
            "shadow_promotion_assessment_root": promotion_root,
            "real_tag_evidence_root": real_tag_root,
            "final_hardening_root": final_hardening_root,
            "engineering_complete": True,
            "observation_active": ready,
            "promotion_refused": True,
            "promotion_recommended": False,
            "external_governance_pending": True,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "external_signature_present": False,
            "live_production_enabled": False,
        }
    )
    record = GovernanceRuntimeV1FreezeRecord(
        freeze_id=f"GOVERNANCE_RUNTIME_V1_FREEZE_{root[:16]}",
        freeze_status=status,
        freeze_phase=FREEZE_PHASE,
        release_tag=release_tag,
        project_completion_root=project_completion_root,
        final_governance_runtime_report_root=final_report_root,
        shadow_operations_root=shadow_operations_root,
        shadow_telemetry_root=telemetry_root,
        shadow_trend_root=trend_root,
        shadow_promotion_assessment_root=promotion_root,
        real_tag_evidence_root=real_tag_root,
        final_hardening_root=final_hardening_root,
        governance_runtime_v1_freeze_certificate_hash=certificate_hash,
        governance_runtime_v1_freeze_root=root,
        engineering_complete=True,
        observation_active=ready,
        promotion_refused=True,
        promotion_recommended=False,
        external_governance_pending=True,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        external_signature_present=False,
        notes_signed_with_real_key=False,
        live_production_enabled=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        approved_evidence=0,
        notes=(
            "Governance Runtime v1 freeze candidate only. Engineering is complete "
            "and observation remains active, while promotion is refused pending "
            "external governance."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "governance_runtime_v1_freeze_record_count": 1,
        "governance_runtime_v1_freeze_candidate_count": 1 if ready else 0,
        "governance_runtime_v1_freeze_blocked_count": 0 if ready else 1,
        "freeze_status": status,
        "freeze_phase": FREEZE_PHASE,
        "release_tag": release_tag,
        "project_completion_root": project_completion_root,
        "final_governance_runtime_report_root": final_report_root,
        "shadow_operations_root": shadow_operations_root,
        "shadow_telemetry_root": telemetry_root,
        "shadow_trend_root": trend_root,
        "shadow_promotion_assessment_root": promotion_root,
        "real_tag_evidence_root": real_tag_root,
        "final_hardening_root": final_hardening_root,
        "governance_runtime_v1_freeze_certificate_hash": certificate_hash,
        "governance_runtime_v1_freeze_root": root,
        "engineering_complete": True,
        "observation_active": ready,
        "promotion_refused": True,
        "promotion_recommended": False,
        "external_governance_pending": True,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "external_signature_present": False,
        "notes_signed_with_real_key": False,
        "live_production_enabled": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "approved_evidence": 0,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CERTIFICATE_OUTPUT, certificate)
    return {"payload": payload, "summary": summary, "certificate": certificate}
