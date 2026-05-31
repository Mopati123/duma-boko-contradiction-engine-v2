#!/usr/bin/env python3
"""
Shadow Promotion Assessment Engine v1.

Builds a deterministic JSON-only assessment of whether promotion from shadow
operations should be considered. This lane does not recommend promotion, enable
production, authorize release, approve evidence, or mark readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_TREND = Path(
    "outputs/shadow_operations_trend_analysis/shadow_operations_trend_summary.json"
)
DEFAULT_TELEMETRY = Path(
    "outputs/shadow_operations_telemetry/shadow_operations_telemetry_summary.json"
)
DEFAULT_SHADOW_OPERATIONS = Path(
    "outputs/shadow_operations_program/shadow_operations_program_summary.json"
)
DEFAULT_PROJECT_COMPLETION = Path(
    "outputs/project_completion_certificate/project_completion_certificate_summary.json"
)
DEFAULT_APPROVAL_GATE = Path(
    "outputs/final_release_approval_gate/final_release_approval_gate_summary.json"
)
DEFAULT_EXTERNAL_SIGNING = Path(
    "outputs/external_signing_evidence_template/external_signing_evidence_template_summary.json"
)
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/shadow_promotion_assessment")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_promotion_assessment_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_promotion_assessment_summary.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "shadow_promotion_assessment_report.json"

PROMOTION_BLOCK_REASONS = [
    "external_manual_approval_missing",
    "external_signature_missing",
    "longitudinal_observation_window_incomplete",
    "live_production_not_enabled",
    "production_authorization_absent",
]

REQUIRED_REPORT_SECTIONS = (
    "assessment_basis",
    "runtime_health",
    "trend_analysis",
    "governance_constraints",
    "promotion_blockers",
    "non_promotion_decision",
    "future_requirements",
    "final_status",
)

ALLOWED_STATUSES = {
    "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY",
    "BLOCKED_MISSING_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_INVALID_SHADOW_OPERATIONS_PROGRAM",
    "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE",
    "BLOCKED_MISSING_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE",
    "BLOCKED_MISSING_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_INVALID_EXTERNAL_SIGNING_TEMPLATE",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "SHADOW_PROMOTION_ASSESSMENT_INVALID",
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
class ShadowPromotionAssessmentRecord:
    shadow_promotion_assessment_id: str
    shadow_promotion_status: str
    release_tag: str
    shadow_trend_root: str
    shadow_telemetry_root: str
    shadow_operations_root: str
    project_completion_root: str
    approval_gate_root: str
    external_signing_template_root: str
    real_tag_evidence_root: str
    shadow_promotion_assessment_report_hash: str
    shadow_promotion_assessment_root: str
    shadow_promotion_assessment_ready: bool
    promotion_recommended: bool
    promotion_blocked: bool
    promotion_block_reason_count: int
    promotion_block_reasons: List[str]
    shadow_health_score: float
    shadow_stability_score: float
    drift_rate: float
    failure_rate: float
    refusal_rate: float
    reconciliation_rate: float
    trend_window: str
    promotion_readiness_score: float
    promotion_threshold: float
    promotion_score_passed: bool
    governance_approval_passed: bool
    external_signature_passed: bool
    longitudinal_window_passed: bool
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


def _one(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) == 1.0


def _determine_status(
    trend: Dict[str, Any],
    telemetry: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    project_completion: Dict[str, Any],
    approval_gate: Dict[str, Any],
    external_signing: Dict[str, Any],
    real_tag: Dict[str, Any],
) -> str:
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
    if not _zero(trend.get("promotion_readiness_score")):
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TREND_ANALYSIS"
    for key in (
        "health_velocity",
        "health_acceleration",
        "stability_velocity",
        "stability_acceleration",
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

    if not telemetry:
        return "BLOCKED_MISSING_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("shadow_telemetry_status") != "SHADOW_OPERATIONS_TELEMETRY_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("shadow_telemetry_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if telemetry.get("total_shadow_cycles") != 11112:
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
    if float(telemetry.get("shadow_health_score") or 0.0) != 100.0:
        return "BLOCKED_INVALID_SHADOW_OPERATIONS_TELEMETRY"
    if float(telemetry.get("shadow_stability_score") or 0.0) != 100.0:
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

    if not project_completion:
        return "BLOCKED_MISSING_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_completion_status") != "PROJECT_COMPLETION_CERTIFICATE_CANDIDATE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("project_phase") != "GOVERNANCE_RUNTIME_V1_COMPLETE":
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("engineering_complete") is not True:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("external_governance_pending") is not True:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("manual_approval_present") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if project_completion.get("release_authorized") is not False:
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _closed_release_flags(project_completion):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"
    if not _is_nonzero_hash(project_completion.get("project_completion_certificate_root")):
        return "BLOCKED_INVALID_PROJECT_COMPLETION_CERTIFICATE"

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
    if approval_gate.get("production_ready") is not False:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if _as_count(approval_gate.get("approved_evidence")) != 0:
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"
    if not _is_nonzero_hash(approval_gate.get("approval_gate_root")):
        return "BLOCKED_INVALID_FINAL_RELEASE_APPROVAL_GATE"

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

    return "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE"


def _build_report(
    status: str,
    release_tag: str,
    trend: Dict[str, Any],
    telemetry: Dict[str, Any],
    shadow_operations: Dict[str, Any],
    project_completion: Dict[str, Any],
    approval_gate: Dict[str, Any],
    external_signing: Dict[str, Any],
    real_tag: Dict[str, Any],
) -> Dict[str, Any]:
    ready = status == "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE"
    return {
        "assessment_basis": {
            "shadow_promotion_status": status,
            "shadow_promotion_assessment_ready": ready,
            "release_tag": release_tag,
            "shadow_trend_root": str(trend.get("shadow_trend_root") or ""),
            "shadow_telemetry_root": str(telemetry.get("shadow_telemetry_root") or ""),
            "shadow_operations_root": str(shadow_operations.get("shadow_operations_root") or ""),
            "project_completion_root": str(
                project_completion.get("project_completion_certificate_root") or ""
            ),
            "approval_gate_root": str(approval_gate.get("approval_gate_root") or ""),
            "external_signing_template_root": str(
                external_signing.get("external_signing_template_root") or ""
            ),
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
        },
        "runtime_health": {
            "shadow_health_score": float(telemetry.get("shadow_health_score") or 0.0),
            "shadow_stability_score": float(telemetry.get("shadow_stability_score") or 0.0),
            "drift_rate": float(telemetry.get("cumulative_drift_rate") or 0.0),
            "failure_rate": float(telemetry.get("cumulative_failure_rate") or 0.0),
            "refusal_rate": float(telemetry.get("cumulative_refusal_rate") or 0.0),
            "reconciliation_rate": float(
                telemetry.get("cumulative_reconciliation_rate") or 0.0
            ),
            "total_shadow_cycles": int(telemetry.get("total_shadow_cycles") or 0),
        },
        "trend_analysis": {
            "trend_window": str(trend.get("trend_window") or "BOOTSTRAP_BASELINE"),
            "health_velocity": float(trend.get("health_velocity") or 0.0),
            "stability_velocity": float(trend.get("stability_velocity") or 0.0),
            "drift_velocity": float(trend.get("drift_velocity") or 0.0),
            "refusal_velocity": float(trend.get("refusal_velocity") or 0.0),
            "failure_velocity": float(trend.get("failure_velocity") or 0.0),
            "promotion_readiness_score": 0.0,
            "promotion_recommended": False,
        },
        "governance_constraints": {
            "manual_approval_present": False,
            "release_authorized": False,
            "external_signature_present": False,
            "notes_signed_with_real_key": False,
            "real_tag_verified": bool(real_tag.get("real_tag_evidence_status") == "REAL_TAG_EVIDENCE_VERIFIED"),
            "production_ready": False,
            "live_production_enabled": False,
        },
        "promotion_blockers": {
            "promotion_blocked": True,
            "promotion_block_reason_count": len(PROMOTION_BLOCK_REASONS),
            "promotion_block_reasons": PROMOTION_BLOCK_REASONS,
        },
        "non_promotion_decision": {
            "promotion_recommended": False,
            "promotion_readiness_score": 0.0,
            "promotion_threshold": 95.0,
            "promotion_score_passed": False,
            "governance_approval_passed": False,
            "external_signature_passed": False,
            "longitudinal_window_passed": False,
            "decision": "promotion_not_recommended",
        },
        "future_requirements": [
            "obtain_external_manual_approval",
            "obtain_external_signature_evidence",
            "collect_longitudinal_shadow_observation_windows",
            "maintain_zero_drift_failure_and_refusal_regressions",
            "perform_explicit_production_authorization_lane_before_any_promotion",
        ],
        "final_status": {
            "shadow_promotion_status": status,
            "shadow_promotion_assessment_ready": ready,
            "promotion_recommended": False,
            "promotion_blocked": True,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "external_signature_present": False,
            "notes_signed_with_real_key": False,
            "live_production_enabled": False,
            "public_ready": False,
            "institutional_ready": False,
            "approved_evidence": 0,
        },
    }


def validate_report(report: Dict[str, Any]) -> None:
    if tuple(report.keys()) != REQUIRED_REPORT_SECTIONS:
        raise ValueError("shadow_promotion_assessment_report must contain exactly the required sections")


def validate_record(record: ShadowPromotionAssessmentRecord) -> None:
    data = record.to_dict()
    required = {
        "shadow_promotion_assessment_id",
        "shadow_promotion_status",
        "release_tag",
        "shadow_trend_root",
        "shadow_telemetry_root",
        "shadow_operations_root",
        "project_completion_root",
        "approval_gate_root",
        "external_signing_template_root",
        "real_tag_evidence_root",
        "shadow_promotion_assessment_report_hash",
        "shadow_promotion_assessment_root",
        "shadow_promotion_assessment_ready",
        "promotion_recommended",
        "promotion_blocked",
        "promotion_block_reason_count",
        "promotion_block_reasons",
        "shadow_health_score",
        "shadow_stability_score",
        "drift_rate",
        "failure_rate",
        "refusal_rate",
        "reconciliation_rate",
        "trend_window",
        "promotion_readiness_score",
        "promotion_threshold",
        "promotion_score_passed",
        "governance_approval_passed",
        "external_signature_passed",
        "longitudinal_window_passed",
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
        raise ValueError(f"ShadowPromotionAssessmentRecord missing fields: {sorted(missing)}")
    if data["shadow_promotion_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported shadow_promotion_status: {data['shadow_promotion_status']}")
    if data["promotion_block_reasons"] != PROMOTION_BLOCK_REASONS:
        raise ValueError("promotion_block_reasons changed unexpectedly")
    if data["promotion_block_reason_count"] != len(PROMOTION_BLOCK_REASONS):
        raise ValueError("promotion_block_reason_count must be 5")
    if data["promotion_blocked"] is not True:
        raise ValueError("promotion_blocked must remain true")
    if data["promotion_threshold"] != 95.0:
        raise ValueError("promotion_threshold must be 95.0")
    if data["trend_window"] != "BOOTSTRAP_BASELINE":
        raise ValueError("trend_window must be BOOTSTRAP_BASELINE")
    if data["shadow_promotion_status"] == "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE":
        for key in (
            "shadow_trend_root",
            "shadow_telemetry_root",
            "shadow_operations_root",
            "project_completion_root",
            "approval_gate_root",
            "external_signing_template_root",
            "real_tag_evidence_root",
            "shadow_promotion_assessment_report_hash",
            "shadow_promotion_assessment_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["shadow_promotion_assessment_ready"] is not True:
            raise ValueError("shadow_promotion_assessment_ready must be true for candidate output")
        if data["shadow_health_score"] != 100.0 or data["shadow_stability_score"] != 100.0:
            raise ValueError("shadow health and stability scores must be 100.0")
        if data["reconciliation_rate"] != 1.0:
            raise ValueError("reconciliation_rate must be 1.0")
    for key in (
        "drift_rate",
        "failure_rate",
        "refusal_rate",
        "promotion_readiness_score",
    ):
        if data[key] != 0.0:
            raise ValueError(f"{key} must be 0.0")
    for key in (
        "promotion_score_passed",
        "governance_approval_passed",
        "external_signature_passed",
        "longitudinal_window_passed",
    ):
        if data[key] is not False:
            raise ValueError(f"{key} must remain false")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_shadow_promotion_assessment(
    trend_path: Path = DEFAULT_TREND,
    telemetry_path: Path = DEFAULT_TELEMETRY,
    shadow_operations_path: Path = DEFAULT_SHADOW_OPERATIONS,
    project_completion_path: Path = DEFAULT_PROJECT_COMPLETION,
    approval_gate_path: Path = DEFAULT_APPROVAL_GATE,
    external_signing_path: Path = DEFAULT_EXTERNAL_SIGNING,
    real_tag_path: Path = DEFAULT_REAL_TAG,
) -> Dict[str, Any]:
    trend = _load_json(trend_path)
    telemetry = _load_json(telemetry_path)
    shadow_operations = _load_json(shadow_operations_path)
    project_completion = _load_json(project_completion_path)
    approval_gate = _load_json(approval_gate_path)
    external_signing = _load_json(external_signing_path)
    real_tag = _load_json(real_tag_path)
    status = _determine_status(
        trend,
        telemetry,
        shadow_operations,
        project_completion,
        approval_gate,
        external_signing,
        real_tag,
    )
    ready = status == "SHADOW_PROMOTION_ASSESSMENT_CANDIDATE"
    release_tag = str(
        trend.get("release_tag")
        or telemetry.get("release_tag")
        or shadow_operations.get("release_tag")
        or project_completion.get("release_tag")
        or real_tag.get("tag_name")
        or ""
    )
    report = _build_report(
        status,
        release_tag,
        trend,
        telemetry,
        shadow_operations,
        project_completion,
        approval_gate,
        external_signing,
        real_tag,
    )
    validate_report(report)
    report_hash = _hash_json(report)
    trend_root = str(trend.get("shadow_trend_root") or "")
    telemetry_root = str(telemetry.get("shadow_telemetry_root") or "")
    shadow_operations_root = str(shadow_operations.get("shadow_operations_root") or "")
    project_completion_root = str(project_completion.get("project_completion_certificate_root") or "")
    approval_gate_root = str(approval_gate.get("approval_gate_root") or "")
    external_signing_root = str(external_signing.get("external_signing_template_root") or "")
    real_tag_root = str(real_tag.get("real_tag_evidence_root") or "")
    root = _hash_json(
        {
            "shadow_promotion_status": status,
            "release_tag": release_tag,
            "shadow_promotion_assessment_report_hash": report_hash,
            "shadow_trend_root": trend_root,
            "shadow_telemetry_root": telemetry_root,
            "shadow_operations_root": shadow_operations_root,
            "project_completion_root": project_completion_root,
            "approval_gate_root": approval_gate_root,
            "external_signing_template_root": external_signing_root,
            "real_tag_evidence_root": real_tag_root,
            "promotion_recommended": False,
            "promotion_blocked": True,
            "promotion_block_reasons": PROMOTION_BLOCK_REASONS,
            "promotion_readiness_score": 0.0,
            "promotion_threshold": 95.0,
            "production_ready": False,
            "release_authorized": False,
            "manual_approval_present": False,
            "external_signature_present": False,
            "live_production_enabled": False,
        }
    )
    record = ShadowPromotionAssessmentRecord(
        shadow_promotion_assessment_id=f"SHADOW_PROMOTION_ASSESSMENT_{root[:16]}",
        shadow_promotion_status=status,
        release_tag=release_tag,
        shadow_trend_root=trend_root,
        shadow_telemetry_root=telemetry_root,
        shadow_operations_root=shadow_operations_root,
        project_completion_root=project_completion_root,
        approval_gate_root=approval_gate_root,
        external_signing_template_root=external_signing_root,
        real_tag_evidence_root=real_tag_root,
        shadow_promotion_assessment_report_hash=report_hash,
        shadow_promotion_assessment_root=root,
        shadow_promotion_assessment_ready=ready,
        promotion_recommended=False,
        promotion_blocked=True,
        promotion_block_reason_count=len(PROMOTION_BLOCK_REASONS),
        promotion_block_reasons=PROMOTION_BLOCK_REASONS,
        shadow_health_score=float(telemetry.get("shadow_health_score") or 0.0),
        shadow_stability_score=float(telemetry.get("shadow_stability_score") or 0.0),
        drift_rate=float(telemetry.get("cumulative_drift_rate") or 0.0),
        failure_rate=float(telemetry.get("cumulative_failure_rate") or 0.0),
        refusal_rate=float(telemetry.get("cumulative_refusal_rate") or 0.0),
        reconciliation_rate=float(telemetry.get("cumulative_reconciliation_rate") or 0.0),
        trend_window=str(trend.get("trend_window") or "BOOTSTRAP_BASELINE"),
        promotion_readiness_score=0.0,
        promotion_threshold=95.0,
        promotion_score_passed=False,
        governance_approval_passed=False,
        external_signature_passed=False,
        longitudinal_window_passed=False,
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
            "Shadow promotion assessment candidate only. Promotion remains blocked "
            "without external approval, external signing, and longitudinal evidence."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "shadow_promotion_assessment_record_count": 1,
        "shadow_promotion_assessment_candidate_count": 1 if ready else 0,
        "shadow_promotion_assessment_blocked_count": 0 if ready else 1,
        "shadow_promotion_status": status,
        "shadow_promotion_assessment_ready": ready,
        "release_tag": release_tag,
        "shadow_trend_root": trend_root,
        "shadow_telemetry_root": telemetry_root,
        "shadow_operations_root": shadow_operations_root,
        "project_completion_root": project_completion_root,
        "approval_gate_root": approval_gate_root,
        "external_signing_template_root": external_signing_root,
        "real_tag_evidence_root": real_tag_root,
        "shadow_promotion_assessment_report_hash": report_hash,
        "shadow_promotion_assessment_root": root,
        "promotion_recommended": False,
        "promotion_blocked": True,
        "promotion_block_reason_count": len(PROMOTION_BLOCK_REASONS),
        "promotion_block_reasons": PROMOTION_BLOCK_REASONS,
        "shadow_health_score": float(telemetry.get("shadow_health_score") or 0.0),
        "shadow_stability_score": float(telemetry.get("shadow_stability_score") or 0.0),
        "drift_rate": float(telemetry.get("cumulative_drift_rate") or 0.0),
        "failure_rate": float(telemetry.get("cumulative_failure_rate") or 0.0),
        "refusal_rate": float(telemetry.get("cumulative_refusal_rate") or 0.0),
        "reconciliation_rate": float(telemetry.get("cumulative_reconciliation_rate") or 0.0),
        "trend_window": str(trend.get("trend_window") or "BOOTSTRAP_BASELINE"),
        "promotion_readiness_score": 0.0,
        "promotion_threshold": 95.0,
        "promotion_score_passed": False,
        "governance_approval_passed": False,
        "external_signature_passed": False,
        "longitudinal_window_passed": False,
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
    _write_json(REPORT_OUTPUT, report)
    return {"payload": payload, "summary": summary, "report": report}
