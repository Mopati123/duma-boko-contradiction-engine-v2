#!/usr/bin/env python3
"""
Operational History Report Engine v1.

Builds a deterministic JSON-only operational history report from the proven
shadow runtime and stress evidence. This lane does not approve evidence, enable
production, authorize release, publish, or mark readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_STRESS = Path("outputs/shadow_runtime_stress_suite/shadow_runtime_stress_summary.json")
DEFAULT_RUNTIME = Path("outputs/shadow_runtime_evidence/shadow_runtime_evidence_summary.json")
DEFAULT_SHADOW_EXECUTION = Path(
    "outputs/shadow_deployment_execution_dry_run/"
    "shadow_deployment_execution_summary.json"
)
DEFAULT_REAL_TAG = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_FINAL_HARDENING = Path(
    "outputs/final_hardening_audit/final_hardening_audit_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/operational_history_report")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "operational_history_report_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "operational_history_report_summary.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "operational_history_report.json"

ALLOWED_STATUSES = {
    "OPERATIONAL_HISTORY_REPORT_CANDIDATE",
    "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS",
    "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS",
    "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE",
    "BLOCKED_MISSING_SHADOW_EXECUTION",
    "BLOCKED_INVALID_SHADOW_EXECUTION",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_FINAL_HARDENING",
    "BLOCKED_INVALID_FINAL_HARDENING",
    "OPERATIONAL_HISTORY_REPORT_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "production_ready",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "release_authorized",
    "manual_approval_present",
    "live_production_enabled",
    "secrets_in_evidence",
    "approved_evidence",
)


@dataclass
class OperationalHistoryReportRecord:
    operational_history_id: str
    operational_history_status: str
    release_tag: str
    stress_root: str
    runtime_root: str
    shadow_execution_root: str
    real_tag_evidence_root: str
    final_hardening_root: str
    operational_history_report_hash: str
    operational_history_report_root: str
    operational_history_ready: bool
    total_shadow_cycles: int
    stress_cycles: int
    baseline_cycles: int
    total_success_count: int
    total_failure_count: int
    total_refusal_count: int
    reconciliation_passed: bool
    drift_detected: bool
    live_production_enabled: bool
    production_ready: bool
    release_authorized: bool
    manual_approval_present: bool
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
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    shadow_execution: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
) -> str:
    if not stress:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_status") != "SHADOW_RUNTIME_STRESS_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("shadow_stress_ready") is not True:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("total_shadow_cycles") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_success_count") != 11100:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("stress_refusal_count") != 0 or stress.get("stress_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if stress.get("reconciliation_passed") is not True or stress.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"
    if not _closed_release_flags(stress) or not _is_nonzero_hash(stress.get("shadow_stress_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_STRESS"

    if not runtime:
        return "BLOCKED_MISSING_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_runtime_status") != "SHADOW_RUNTIME_EVIDENCE_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_cycle_count") != 12 or runtime.get("shadow_success_count") != 12:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("shadow_refusal_count") != 0 or runtime.get("shadow_failure_count") != 0:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if runtime.get("reconciliation_passed") is not True or runtime.get("drift_detected") is not False:
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"
    if not _closed_release_flags(runtime) or not _is_nonzero_hash(runtime.get("shadow_runtime_root")):
        return "BLOCKED_INVALID_SHADOW_RUNTIME_EVIDENCE"

    if not shadow_execution:
        return "BLOCKED_MISSING_SHADOW_EXECUTION"
    if shadow_execution.get("shadow_execution_status") != "SHADOW_DEPLOYMENT_EXECUTION_DRY_RUN_CANDIDATE":
        return "BLOCKED_INVALID_SHADOW_EXECUTION"
    if shadow_execution.get("shadow_execution_performed") is not True:
        return "BLOCKED_INVALID_SHADOW_EXECUTION"
    if not _closed_release_flags(shadow_execution) or not _is_nonzero_hash(shadow_execution.get("shadow_execution_root")):
        return "BLOCKED_INVALID_SHADOW_EXECUTION"

    if not real_tag:
        return "BLOCKED_MISSING_REAL_TAG_EVIDENCE"
    if real_tag.get("real_tag_evidence_status") != "REAL_TAG_EVIDENCE_VERIFIED":
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_exists_locally") is not True or real_tag.get("tag_pushed_to_origin") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _closed_release_flags(real_tag) or not _is_nonzero_hash(real_tag.get("real_tag_evidence_root")):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"

    if not final_hardening:
        return "BLOCKED_MISSING_FINAL_HARDENING"
    if final_hardening.get("final_hardening_status") != "FINAL_HARDENING_AUDIT_CANDIDATE":
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if final_hardening.get("final_hardening_ready") is not True:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if final_hardening.get("secrets_detected") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if final_hardening.get("generated_outputs_committed") is not False:
        return "BLOCKED_INVALID_FINAL_HARDENING"
    if not _closed_release_flags(final_hardening) or not _is_nonzero_hash(final_hardening.get("final_hardening_root")):
        return "BLOCKED_INVALID_FINAL_HARDENING"

    return "OPERATIONAL_HISTORY_REPORT_CANDIDATE"


def _build_report(
    release_tag: str,
    stress: Dict[str, Any],
    runtime: Dict[str, Any],
    shadow_execution: Dict[str, Any],
    real_tag: Dict[str, Any],
    final_hardening: Dict[str, Any],
    status: str,
) -> Dict[str, Any]:
    stress_cycles = int(stress.get("total_shadow_cycles") or 0)
    baseline_cycles = int(runtime.get("shadow_cycle_count") or 0)
    return {
        "operational_history_report_version": "operational_history_report_v1",
        "operational_history_status": status,
        "release_tag": release_tag,
        "cycle_totals": {
            "baseline_cycles": baseline_cycles,
            "stress_cycles": stress_cycles,
            "total_shadow_cycles": baseline_cycles + stress_cycles,
            "total_success_count": int(runtime.get("shadow_success_count") or 0)
            + int(stress.get("stress_success_count") or 0),
            "total_failure_count": int(runtime.get("shadow_failure_count") or 0)
            + int(stress.get("stress_failure_count") or 0),
            "total_refusal_count": int(runtime.get("shadow_refusal_count") or 0)
            + int(stress.get("stress_refusal_count") or 0),
        },
        "reconciliation": {
            "reconciliation_passed": status == "OPERATIONAL_HISTORY_REPORT_CANDIDATE",
            "drift_detected": False,
        },
        "source_roots": {
            "final_hardening_root": str(final_hardening.get("final_hardening_root") or ""),
            "real_tag_evidence_root": str(real_tag.get("real_tag_evidence_root") or ""),
            "shadow_execution_root": str(shadow_execution.get("shadow_execution_root") or ""),
            "shadow_runtime_root": str(runtime.get("shadow_runtime_root") or ""),
            "shadow_stress_root": str(stress.get("shadow_stress_root") or ""),
        },
        "closed_flags": {
            "approved_evidence": 0,
            "live_production_enabled": False,
            "manual_approval_present": False,
            "production_ready": False,
            "public_ready": False,
            "institutional_ready": False,
            "release_authorized": False,
            "report_ready": False,
            "secrets_in_evidence": False,
        },
    }


def validate_record(record: OperationalHistoryReportRecord) -> None:
    data = record.to_dict()
    required = {
        "operational_history_id",
        "operational_history_status",
        "release_tag",
        "stress_root",
        "runtime_root",
        "shadow_execution_root",
        "real_tag_evidence_root",
        "final_hardening_root",
        "operational_history_report_hash",
        "operational_history_report_root",
        "operational_history_ready",
        "total_shadow_cycles",
        "stress_cycles",
        "baseline_cycles",
        "total_success_count",
        "total_failure_count",
        "total_refusal_count",
        "reconciliation_passed",
        "drift_detected",
        "live_production_enabled",
        "production_ready",
        "release_authorized",
        "manual_approval_present",
        "secrets_in_evidence",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"OperationalHistoryReportRecord missing fields: {sorted(missing)}")
    if data["operational_history_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported operational_history_status: {data['operational_history_status']}")
    if data["operational_history_status"] == "OPERATIONAL_HISTORY_REPORT_CANDIDATE":
        for key in (
            "stress_root",
            "runtime_root",
            "shadow_execution_root",
            "real_tag_evidence_root",
            "final_hardening_root",
            "operational_history_report_hash",
            "operational_history_report_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["operational_history_ready"] is not True:
            raise ValueError("operational_history_ready must be true")
        if data["total_shadow_cycles"] != 11112:
            raise ValueError("total_shadow_cycles must be 11112")
        if data["total_success_count"] != 11112:
            raise ValueError("total_success_count must be 11112")
        if data["total_failure_count"] != 0 or data["total_refusal_count"] != 0:
            raise ValueError("failure/refusal totals must be zero")
        if data["reconciliation_passed"] is not True:
            raise ValueError("reconciliation_passed must be true")
    if data["drift_detected"] is not False:
        raise ValueError("drift_detected must remain false")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_operational_history_report(
    stress_path: Path = DEFAULT_STRESS,
    runtime_path: Path = DEFAULT_RUNTIME,
    shadow_execution_path: Path = DEFAULT_SHADOW_EXECUTION,
    real_tag_path: Path = DEFAULT_REAL_TAG,
    final_hardening_path: Path = DEFAULT_FINAL_HARDENING,
) -> Dict[str, Any]:
    stress = _load_json(stress_path)
    runtime = _load_json(runtime_path)
    shadow_execution = _load_json(shadow_execution_path)
    real_tag = _load_json(real_tag_path)
    final_hardening = _load_json(final_hardening_path)
    status = _determine_status(stress, runtime, shadow_execution, real_tag, final_hardening)
    ready = status == "OPERATIONAL_HISTORY_REPORT_CANDIDATE"
    release_tag = str(stress.get("release_tag") or runtime.get("release_tag") or real_tag.get("tag_name") or "")
    report = _build_report(release_tag, stress, runtime, shadow_execution, real_tag, final_hardening, status)
    report_hash = _hash_json(report)
    stress_cycles = int(stress.get("total_shadow_cycles") or 0)
    baseline_cycles = int(runtime.get("shadow_cycle_count") or 0)
    total_success = int(runtime.get("shadow_success_count") or 0) + int(stress.get("stress_success_count") or 0)
    total_failure = int(runtime.get("shadow_failure_count") or 0) + int(stress.get("stress_failure_count") or 0)
    total_refusal = int(runtime.get("shadow_refusal_count") or 0) + int(stress.get("stress_refusal_count") or 0)
    root = _hash_json(
        {
            "operational_history_status": status,
            "release_tag": release_tag,
            "operational_history_report_hash": report_hash,
            "stress_root": str(stress.get("shadow_stress_root") or ""),
            "runtime_root": str(runtime.get("shadow_runtime_root") or ""),
            "total_shadow_cycles": baseline_cycles + stress_cycles,
            "total_success_count": total_success,
            "reconciliation_passed": ready,
            "production_ready": False,
        }
    )
    record = OperationalHistoryReportRecord(
        operational_history_id=f"OPERATIONAL_HISTORY_REPORT_{root[:16]}",
        operational_history_status=status,
        release_tag=release_tag,
        stress_root=str(stress.get("shadow_stress_root") or ""),
        runtime_root=str(runtime.get("shadow_runtime_root") or ""),
        shadow_execution_root=str(shadow_execution.get("shadow_execution_root") or ""),
        real_tag_evidence_root=str(real_tag.get("real_tag_evidence_root") or ""),
        final_hardening_root=str(final_hardening.get("final_hardening_root") or ""),
        operational_history_report_hash=report_hash,
        operational_history_report_root=root,
        operational_history_ready=ready,
        total_shadow_cycles=baseline_cycles + stress_cycles,
        stress_cycles=stress_cycles,
        baseline_cycles=baseline_cycles,
        total_success_count=total_success,
        total_failure_count=total_failure,
        total_refusal_count=total_refusal,
        reconciliation_passed=ready,
        drift_detected=False,
        live_production_enabled=False,
        production_ready=False,
        release_authorized=False,
        manual_approval_present=False,
        secrets_in_evidence=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes="Operational history report candidate only. No readiness or production flags were promoted.",
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "operational_history_record_count": 1,
        "operational_history_candidate_count": 1 if ready else 0,
        "operational_history_blocked_count": 0 if ready else 1,
        "operational_history_status": status,
        "operational_history_ready": ready,
        "release_tag": release_tag,
        "stress_root": record.stress_root,
        "runtime_root": record.runtime_root,
        "shadow_execution_root": record.shadow_execution_root,
        "real_tag_evidence_root": record.real_tag_evidence_root,
        "final_hardening_root": record.final_hardening_root,
        "operational_history_report_hash": report_hash,
        "operational_history_report_root": root,
        "total_shadow_cycles": record.total_shadow_cycles,
        "stress_cycles": stress_cycles,
        "baseline_cycles": baseline_cycles,
        "total_success_count": total_success,
        "total_failure_count": total_failure,
        "total_refusal_count": total_refusal,
        "drift_detected": False,
        "reconciliation_passed": ready,
        "live_production_enabled": False,
        "production_ready": False,
        "release_authorized": False,
        "manual_approval_present": False,
        "secrets_in_evidence": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(REPORT_OUTPUT, report)
    return {"payload": payload, "summary": summary, "report": report}
