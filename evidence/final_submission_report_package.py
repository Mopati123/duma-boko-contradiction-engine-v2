#!/usr/bin/env python3
"""
Final Submission Report Package Engine v1.

Builds deterministic Markdown submission reports from the frozen Governance
Runtime v1 evidence chain. This lane does not approve evidence, authorize
release, enable production, or mark public/institutional readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_PROJECT_COMPLETION = Path(
    "outputs/project_completion_certificate/project_completion_certificate_summary.json"
)
DEFAULT_FREEZE = Path(
    "outputs/governance_runtime_v1_freeze/governance_runtime_v1_freeze_summary.json"
)
DEFAULT_FINAL_REPORT = Path(
    "outputs/final_governance_runtime_report/final_governance_runtime_report_summary.json"
)
DEFAULT_INSTITUTIONAL = Path(
    "outputs/institutional_readiness_report/institutional_readiness_report_summary.json"
)
DEFAULT_OPERATIONAL = Path(
    "outputs/operational_history_report/operational_history_report_summary.json"
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
DEFAULT_STRESS = Path("outputs/shadow_runtime_stress_suite/shadow_runtime_stress_summary.json")
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/final_submission_report_package")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_submission_report_package_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_submission_report_package_summary.json"

REPORT_FILES = (
    "01_executive_summary.md",
    "02_governance_runtime_architecture.md",
    "03_verification_and_stress_validation.md",
    "04_operational_history_report.md",
    "05_institutional_readiness_report.md",
    "06_shadow_operations_report.md",
    "07_promotion_assessment_report.md",
    "08_freeze_certificate.md",
    "09_appendix_evidence_roots.md",
    "final_submission_report.md",
)

RELEASE_TAG = "v1.0.0-rc1-governance-runtime"
TITLE = "Governance Runtime v1"
TITLE_SUBTITLE = (
    "Engineering Complete \u2014 Observation Active \u2014 Promotion Refused Pending Governance"
)
TITLE_RELEASE = f"Release Candidate: {RELEASE_TAG}"
NON_AUTHORIZATION_STATEMENT = (
    "This system is engineering-complete and release-candidate-ready.\n"
    "It is not production-authorized.\n"
    "It is not institutionally approved.\n"
    "It intentionally refuses promotion until external manual approval, external "
    "signature, longitudinal observation, and explicit production authorization "
    "are completed."
)
FREEZE_PHASE = "ENGINEERING_COMPLETE_OBSERVATION_ACTIVE_PROMOTION_REFUSED_PENDING_GOVERNANCE"

PROMOTION_BLOCK_REASONS = [
    "external_manual_approval_missing",
    "external_signature_missing",
    "longitudinal_observation_window_incomplete",
    "live_production_not_enabled",
    "production_authorization_absent",
]

REMAINING_GOVERNANCE_ACTIONS = [
    "longitudinal_shadow_observation",
    "external_manual_approval",
    "external_signature",
    "production_authorization_decision",
    "monthly_governance_reporting",
]

ALLOWED_STATUSES = {
    "FINAL_SUBMISSION_REPORT_PACKAGE_CANDIDATE",
    "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_MISSING_GOVERNANCE_RUNTIME_V1_FREEZE",
    "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE",
    "BLOCKED_MISSING_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_INVALID_FINAL_GOVERNANCE_RUNTIME_REPORT",
    "BLOCKED_MISSING_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_INVALID_INSTITUTIONAL_READINESS_REPORT",
    "BLOCKED_MISSING_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_MISSING_SHADOW_PROMOTION_ASSESSMENT",
    "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT",
    "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS",
    "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_FINAL_HARDENING_AUDIT",
    "BLOCKED_INVALID_FINAL_HARDENING_AUDIT",
    "FINAL_SUBMISSION_REPORT_PACKAGE_INVALID",
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
class FinalSubmissionReportPackageRecord:
    submission_package_id: str
    submission_package_status: str
    release_tag: str
    project_completion_root: str
    governance_runtime_v1_freeze_root: str
    final_governance_runtime_report_root: str
    institutional_readiness_report_root: str
    operational_history_report_root: str
    shadow_operations_root: str
    shadow_telemetry_root: str
    shadow_trend_root: str
    shadow_promotion_assessment_root: str
    shadow_stress_root: str
    real_tag_evidence_root: str
    final_hardening_root: str
    final_submission_report_package_hash: str
    final_submission_report_package_root: str
    submission_package_ready: bool
    generated_report_files: List[str]
    engineering_complete: bool
    observation_active: bool
    promotion_refused: bool
    promotion_recommended: bool
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


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


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


def _one(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) == 1.0


def _determine_status(
    project_completion: Dict[str, Any],
    freeze: Dict[str, Any],
    final_report: Dict[str, Any],
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    telemetry: Dict[str, Any],
    trend: Dict[str, Any],
    promotion: Dict[str, Any],
    stress: Dict[str, Any],
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

    if not freeze:
        return "BLOCKED_MISSING_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("freeze_status") != "GOVERNANCE_RUNTIME_V1_FREEZE_CANDIDATE":
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("freeze_phase") != FREEZE_PHASE:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    for key in (
        "engineering_complete",
        "observation_active",
        "promotion_refused",
        "external_governance_pending",
    ):
        if freeze.get(key) is not True:
            return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("promotion_recommended") is not False:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("release_authorized") is not False:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if freeze.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if not _closed_release_flags(freeze):
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"
    if not _is_nonzero_hash(freeze.get("governance_runtime_v1_freeze_root")):
        return "BLOCKED_INVALID_GOVERNANCE_RUNTIME_V1_FREEZE"

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
    if operational.get("drift_detected") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("reconciliation_passed") is not True:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if operational.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _closed_release_flags(operational):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"
    if not _is_nonzero_hash(operational.get("operational_history_report_root")):
        return "BLOCKED_INVALID_OPERATIONAL_HISTORY_REPORT"

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
    if not _one(telemetry.get("cumulative_reconciliation_rate")):
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
    if trend.get("promotion_recommended") is not False:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    if not _zero(trend.get("promotion_readiness_score")):
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
    if promotion.get("promotion_block_reasons") != PROMOTION_BLOCK_REASONS:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("release_authorized") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("external_signature_present") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if promotion.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if not _closed_release_flags(promotion):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"
    if not _is_nonzero_hash(promotion.get("shadow_promotion_assessment_root")):
        return "BLOCKED_INVALID_SHADOW_PROMOTION_ASSESSMENT"

    if not stress:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_status") != "SHADOW_RUNTIME_STRESS_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_targets") != [100, 1000, 10000]:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("total_shadow_cycles") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_success_count") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_refusal_count") != 0 or stress.get("stress_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("reconciliation_passed") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("live_production_enabled") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _closed_release_flags(stress):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _is_nonzero_hash(stress.get("shadow_stress_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"

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
    if final_hardening.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if final_hardening.get("generated_outputs_committed") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _closed_release_flags(final_hardening):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"
    if not _is_nonzero_hash(final_hardening.get("final_hardening_root")):
        return "BLOCKED_INVALID_FINAL_HARDENING_AUDIT"

    return "FINAL_SUBMISSION_REPORT_PACKAGE_CANDIDATE"


def _front_matter() -> str:
    return "\n".join(
        [
            f"# {TITLE}",
            f"## {TITLE_SUBTITLE}",
            f"### {TITLE_RELEASE}",
            "",
            NON_AUTHORIZATION_STATEMENT,
        ]
    )


def _kv_lines(items: Dict[str, Any]) -> List[str]:
    return [f"- {key}: {value}" for key, value in items.items()]


def _section(title: str, lines: List[str]) -> str:
    return "\n".join([f"# {title}", "", *lines, ""])


def _build_markdown_files(
    status: str,
    release_tag: str,
    project_completion: Dict[str, Any],
    freeze: Dict[str, Any],
    final_report: Dict[str, Any],
    institutional: Dict[str, Any],
    operational: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    telemetry: Dict[str, Any],
    trend: Dict[str, Any],
    promotion: Dict[str, Any],
    stress: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> Dict[str, str]:
    files: Dict[str, str] = {}
    files["01_executive_summary.md"] = _section(
        "01 Executive Summary",
        [
            _front_matter(),
            "",
            "- submission_package_status: " + status,
            "- engineering_complete: True",
            "- observation_active: True",
            "- promotion_refused: True",
            "- production_ready: False",
            "- release_authorized: False",
            "- public_ready: False",
            "- institutional_ready: False",
        ],
    )
    files["02_governance_runtime_architecture.md"] = _section(
        "02 Governance Runtime Architecture",
        _kv_lines(
            {
                "project_phase": project_completion.get("project_phase"),
                "freeze_phase": freeze.get("freeze_phase"),
                "final_report_status": final_report.get("final_report_status"),
                "project_completion_root": project_completion.get(
                    "project_completion_certificate_root"
                ),
                "governance_runtime_v1_freeze_root": freeze.get(
                    "governance_runtime_v1_freeze_root"
                ),
            }
        ),
    )
    files["03_verification_and_stress_validation.md"] = _section(
        "03 Verification And Stress Validation",
        _kv_lines(
            {
                "release_tag": release_tag,
                "tag_verified": final_report.get("tag_verified"),
                "real_tag_evidence_status": real_tag.get("real_tag_evidence_status"),
                "stress_targets": stress.get("stress_targets"),
                "total_shadow_cycles": stress.get("total_shadow_cycles"),
                "stress_success_count": stress.get("stress_success_count"),
                "drift_detected": stress.get("drift_detected"),
            }
        ),
    )
    files["04_operational_history_report.md"] = _section(
        "04 Operational History Report",
        _kv_lines(
            {
                "operational_history_status": operational.get("operational_history_status"),
                "total_shadow_cycles": operational.get("total_shadow_cycles"),
                "total_success_count": operational.get("total_success_count"),
                "total_failure_count": operational.get("total_failure_count"),
                "total_refusal_count": operational.get("total_refusal_count"),
                "reconciliation_passed": operational.get("reconciliation_passed"),
                "operational_history_report_root": operational.get(
                    "operational_history_report_root"
                ),
            }
        ),
    )
    files["05_institutional_readiness_report.md"] = _section(
        "05 Institutional Readiness Report",
        _kv_lines(
            {
                "institutional_report_status": institutional.get("institutional_report_status"),
                "institutional_report_ready": institutional.get("institutional_report_ready"),
                "architecture_ready": institutional.get("architecture_ready"),
                "governance_ready": institutional.get("governance_ready"),
                "institutional_ready": institutional.get("institutional_ready"),
                "production_ready": institutional.get("production_ready"),
                "institutional_readiness_report_root": institutional.get(
                    "institutional_readiness_report_root"
                ),
            }
        ),
    )
    files["06_shadow_operations_report.md"] = _section(
        "06 Shadow Operations Report",
        _kv_lines(
            {
                "shadow_operations_status": shadow_operations.get("shadow_operations_status"),
                "shadow_telemetry_status": telemetry.get("shadow_telemetry_status"),
                "shadow_trend_status": trend.get("shadow_trend_status"),
                "baseline_shadow_cycles": shadow_operations.get("baseline_shadow_cycles"),
                "total_shadow_cycles": telemetry.get("total_shadow_cycles"),
                "shadow_health_score": telemetry.get("shadow_health_score"),
                "shadow_stability_score": telemetry.get("shadow_stability_score"),
                "promotion_recommended": trend.get("promotion_recommended"),
            }
        ),
    )
    files["07_promotion_assessment_report.md"] = _section(
        "07 Promotion Assessment Report",
        _kv_lines(
            {
                "shadow_promotion_status": promotion.get("shadow_promotion_status"),
                "promotion_recommended": promotion.get("promotion_recommended"),
                "promotion_blocked": promotion.get("promotion_blocked"),
                "promotion_block_reasons": promotion.get("promotion_block_reasons"),
                "promotion_readiness_score": promotion.get("promotion_readiness_score"),
                "promotion_threshold": promotion.get("promotion_threshold"),
                "shadow_promotion_assessment_root": promotion.get(
                    "shadow_promotion_assessment_root"
                ),
            }
        ),
    )
    files["08_freeze_certificate.md"] = _section(
        "08 Freeze Certificate",
        [
            str(freeze.get("freeze_phase")),
            "",
            str(
                "Governance Runtime v1 is frozen as an engineering-complete, "
                "observation-active, promotion-refused candidate pending governance."
            ),
            "",
            *_kv_lines(
                {
                    "freeze_status": freeze.get("freeze_status"),
                    "engineering_complete": freeze.get("engineering_complete"),
                    "observation_active": freeze.get("observation_active"),
                    "promotion_refused": freeze.get("promotion_refused"),
                    "external_governance_pending": freeze.get("external_governance_pending"),
                    "governance_runtime_v1_freeze_root": freeze.get(
                        "governance_runtime_v1_freeze_root"
                    ),
                }
            ),
        ],
    )
    files["09_appendix_evidence_roots.md"] = _section(
        "09 Appendix Evidence Roots",
        _kv_lines(
            {
                "project_completion_root": project_completion.get(
                    "project_completion_certificate_root"
                ),
                "governance_runtime_v1_freeze_root": freeze.get(
                    "governance_runtime_v1_freeze_root"
                ),
                "final_governance_runtime_report_root": final_report.get(
                    "final_governance_runtime_report_root"
                ),
                "institutional_readiness_report_root": institutional.get(
                    "institutional_readiness_report_root"
                ),
                "operational_history_report_root": operational.get(
                    "operational_history_report_root"
                ),
                "shadow_operations_root": shadow_operations.get("shadow_operations_root"),
                "shadow_telemetry_root": telemetry.get("shadow_telemetry_root"),
                "shadow_trend_root": trend.get("shadow_trend_root"),
                "shadow_promotion_assessment_root": promotion.get(
                    "shadow_promotion_assessment_root"
                ),
                "shadow_stress_root": stress.get("shadow_stress_root"),
                "real_tag_evidence_root": real_tag.get("real_tag_evidence_root"),
                "final_hardening_root": final_hardening.get("final_hardening_root"),
            }
        ),
    )
    files["final_submission_report.md"] = (
        _front_matter()
        + "\n\n"
        + "\n\n".join(
            files[name].rstrip() for name in REPORT_FILES if name != "final_submission_report.md"
        )
        + "\n"
    )
    return files


def _hash_markdown_package(files: Dict[str, str]) -> str:
    manifest = {name: _sha256_text(files[name].rstrip() + "\n") for name in REPORT_FILES}
    return _hash_json(manifest)


def validate_record(record: FinalSubmissionReportPackageRecord) -> None:
    data = record.to_dict()
    required = {
        "submission_package_id",
        "submission_package_status",
        "release_tag",
        "project_completion_root",
        "governance_runtime_v1_freeze_root",
        "final_governance_runtime_report_root",
        "institutional_readiness_report_root",
        "operational_history_report_root",
        "shadow_operations_root",
        "shadow_telemetry_root",
        "shadow_trend_root",
        "shadow_promotion_assessment_root",
        "shadow_stress_root",
        "real_tag_evidence_root",
        "final_hardening_root",
        "final_submission_report_package_hash",
        "final_submission_report_package_root",
        "submission_package_ready",
        "generated_report_files",
        "engineering_complete",
        "observation_active",
        "promotion_refused",
        "promotion_recommended",
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
        raise ValueError(f"FinalSubmissionReportPackageRecord missing fields: {sorted(missing)}")
    if data["submission_package_status"] not in ALLOWED_STATUSES:
        raise ValueError(
            f"Unsupported submission_package_status: {data['submission_package_status']}"
        )
    if data["release_tag"] != RELEASE_TAG:
        raise ValueError("release_tag changed unexpectedly")
    if data["generated_report_files"] != list(REPORT_FILES):
        raise ValueError("generated_report_files changed unexpectedly")
    if data["engineering_complete"] is not True:
        raise ValueError("engineering_complete must remain true")
    if data["promotion_refused"] is not True:
        raise ValueError("promotion_refused must remain true")
    if data["submission_package_status"] == "FINAL_SUBMISSION_REPORT_PACKAGE_CANDIDATE":
        if data["submission_package_ready"] is not True:
            raise ValueError("submission_package_ready must be true for candidate output")
        if data["observation_active"] is not True:
            raise ValueError("observation_active must be true for candidate output")
        for key in (
            "project_completion_root",
            "governance_runtime_v1_freeze_root",
            "final_governance_runtime_report_root",
            "institutional_readiness_report_root",
            "operational_history_report_root",
            "shadow_operations_root",
            "shadow_telemetry_root",
            "shadow_trend_root",
            "shadow_promotion_assessment_root",
            "shadow_stress_root",
            "real_tag_evidence_root",
            "final_hardening_root",
            "final_submission_report_package_hash",
            "final_submission_report_package_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def validate_markdown_files(files: Dict[str, str]) -> None:
    if tuple(files.keys()) != REPORT_FILES:
        raise ValueError("final submission report files changed unexpectedly")
    final_report = files["final_submission_report.md"]
    required_lines = [TITLE, TITLE_SUBTITLE, TITLE_RELEASE]
    for line in required_lines:
        if line not in final_report:
            raise ValueError(f"final_submission_report.md missing title line: {line}")
    for line in NON_AUTHORIZATION_STATEMENT.splitlines():
        if line not in final_report:
            raise ValueError("final_submission_report.md missing non-authorization statement")


def build_final_submission_report_package(
    project_completion_path: Path = DEFAULT_PROJECT_COMPLETION,
    freeze_path: Path = DEFAULT_FREEZE,
    final_report_path: Path = DEFAULT_FINAL_REPORT,
    institutional_path: Path = DEFAULT_INSTITUTIONAL,
    operational_path: Path = DEFAULT_OPERATIONAL,
    shadow_operations_path: Path = DEFAULT_SHADOW_OPERATIONS,
    telemetry_path: Path = DEFAULT_TELEMETRY,
    trend_path: Path = DEFAULT_TREND,
    promotion_path: Path = DEFAULT_PROMOTION,
    stress_path: Path = DEFAULT_STRESS,
    real_tag_path: Path = DEFAULT_REAL_TAG,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
) -> Dict[str, Any]:
    project_completion = _load_json(project_completion_path)
    freeze = _load_json(freeze_path)
    final_report = _load_json(final_report_path)
    institutional = _load_json(institutional_path)
    operational = _load_json(operational_path)
    shadow_operations = _load_json(shadow_operations_path)
    telemetry = _load_json(telemetry_path)
    trend = _load_json(trend_path)
    promotion = _load_json(promotion_path)
    stress = _load_json(stress_path)
    real_tag = _load_json(real_tag_path)
    final_hardening = _load_json(final_hardening_path)
    status = _determine_status(
        project_completion,
        freeze,
        final_report,
        institutional,
        operational,
        shadow_operations,
        telemetry,
        trend,
        promotion,
        stress,
        real_tag,
        final_hardening,
    )
    ready = status == "FINAL_SUBMISSION_REPORT_PACKAGE_CANDIDATE"
    release_tag = str(
        project_completion.get("release_tag")
        or freeze.get("release_tag")
        or final_report.get("release_candidate_tag")
        or real_tag.get("tag_name")
        or RELEASE_TAG
    )
    files = _build_markdown_files(
        status,
        release_tag,
        project_completion,
        freeze,
        final_report,
        institutional,
        operational,
        shadow_operations,
        telemetry,
        trend,
        promotion,
        stress,
        real_tag,
        final_hardening,
    )
    validate_markdown_files(files)
    package_hash = _hash_markdown_package(files)
    project_completion_root = str(project_completion.get("project_completion_certificate_root") or "")
    freeze_root = str(freeze.get("governance_runtime_v1_freeze_root") or "")
    final_report_root = str(final_report.get("final_governance_runtime_report_root") or "")
    institutional_root = str(institutional.get("institutional_readiness_report_root") or "")
    operational_root = str(operational.get("operational_history_report_root") or "")
    shadow_operations_root = str(shadow_operations.get("shadow_operations_root") or "")
    telemetry_root = str(telemetry.get("shadow_telemetry_root") or "")
    trend_root = str(trend.get("shadow_trend_root") or "")
    promotion_root = str(promotion.get("shadow_promotion_assessment_root") or "")
    stress_root = str(stress.get("shadow_stress_root") or "")
    real_tag_root = str(real_tag.get("real_tag_evidence_root") or "")
    final_hardening_root = str(final_hardening.get("final_hardening_root") or "")
    root = _hash_json(
        {
            "submission_package_status": status,
            "release_tag": release_tag,
            "final_submission_report_package_hash": package_hash,
            "project_completion_root": project_completion_root,
            "governance_runtime_v1_freeze_root": freeze_root,
            "final_governance_runtime_report_root": final_report_root,
            "institutional_readiness_report_root": institutional_root,
            "operational_history_report_root": operational_root,
            "shadow_operations_root": shadow_operations_root,
            "shadow_telemetry_root": telemetry_root,
            "shadow_trend_root": trend_root,
            "shadow_promotion_assessment_root": promotion_root,
            "shadow_stress_root": stress_root,
            "real_tag_evidence_root": real_tag_root,
            "final_hardening_root": final_hardening_root,
            "engineering_complete": True,
            "observation_active": ready,
            "promotion_refused": True,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    record = FinalSubmissionReportPackageRecord(
        submission_package_id=f"FINAL_SUBMISSION_REPORT_PACKAGE_{root[:16]}",
        submission_package_status=status,
        release_tag=release_tag,
        project_completion_root=project_completion_root,
        governance_runtime_v1_freeze_root=freeze_root,
        final_governance_runtime_report_root=final_report_root,
        institutional_readiness_report_root=institutional_root,
        operational_history_report_root=operational_root,
        shadow_operations_root=shadow_operations_root,
        shadow_telemetry_root=telemetry_root,
        shadow_trend_root=trend_root,
        shadow_promotion_assessment_root=promotion_root,
        shadow_stress_root=stress_root,
        real_tag_evidence_root=real_tag_root,
        final_hardening_root=final_hardening_root,
        final_submission_report_package_hash=package_hash,
        final_submission_report_package_root=root,
        submission_package_ready=ready,
        generated_report_files=list(REPORT_FILES),
        engineering_complete=True,
        observation_active=ready,
        promotion_refused=True,
        promotion_recommended=False,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        approved_evidence=0,
        notes=(
            "Final submission package candidate only. Generated Markdown reports "
            "summarize frozen Governance Runtime v1 evidence without authorizing "
            "production or institutional readiness."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "final_submission_report_package_record_count": 1,
        "final_submission_report_package_candidate_count": 1 if ready else 0,
        "final_submission_report_package_blocked_count": 0 if ready else 1,
        "submission_package_status": status,
        "submission_package_ready": ready,
        "release_tag": release_tag,
        "project_completion_root": project_completion_root,
        "governance_runtime_v1_freeze_root": freeze_root,
        "final_governance_runtime_report_root": final_report_root,
        "institutional_readiness_report_root": institutional_root,
        "operational_history_report_root": operational_root,
        "shadow_operations_root": shadow_operations_root,
        "shadow_telemetry_root": telemetry_root,
        "shadow_trend_root": trend_root,
        "shadow_promotion_assessment_root": promotion_root,
        "shadow_stress_root": stress_root,
        "real_tag_evidence_root": real_tag_root,
        "final_hardening_root": final_hardening_root,
        "final_submission_report_package_hash": package_hash,
        "final_submission_report_package_root": root,
        "generated_report_file_count": len(REPORT_FILES),
        "generated_report_files": list(REPORT_FILES),
        "engineering_complete": True,
        "observation_active": ready,
        "promotion_refused": True,
        "promotion_recommended": False,
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
    for name in REPORT_FILES:
        _write_text(DEFAULT_OUTPUT_DIR / name, files[name])
    return {"payload": payload, "summary": summary, "reports": files}
