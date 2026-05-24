"""
release_readiness.py - Conservative public/institutional release checks.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.final_report_hardening import (
    DEFAULT_FINAL_REPORT_HARDENING_RECORD,
    harden_final_report_dry_run,
    validate_final_report_hardening_record,
)


DEFAULT_RELEASE_READINESS_DIR = Path("outputs/release_readiness")
DEFAULT_RELEASE_READINESS_RECORD = (
    DEFAULT_RELEASE_READINESS_DIR / "release_readiness_record.json"
)
DEFAULT_RELEASE_READINESS_SUMMARY = (
    DEFAULT_RELEASE_READINESS_DIR / "release_readiness_summary.json"
)

RELEASE_STATUSES = {
    "blocked_review_draft_only",
    "blocked_manual_review_required",
    "blocked_real_evidence_required",
    "blocked_ci_policy_required",
    "release_candidate_pending_approval",
}

BLOCKED_RELEASE_STATUSES = {
    "blocked_review_draft_only",
    "blocked_manual_review_required",
    "blocked_real_evidence_required",
    "blocked_ci_policy_required",
}

FORBIDDEN_RELEASE_CLAIMS = (
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "institution ready",
    "validated public evidence",
    "final forensic report",
)

DRY_RUN_BLOCKER_REASONS = [
    "real evidence approval required",
    "manual review approval required",
    "public release approval absent",
    "institutional release approval absent",
    "GitHub Actions unavailable due to billing/account lock",
    "local CI is valid for development but release policy must be formalized",
]

DRY_RUN_RELEASE_NOTES = (
    "Release readiness dry-run only. The hardened review draft remains blocked "
    "from public and institutional release until real evidence, manual review, "
    "source, timestamp, quote, context, and CI policy approval are complete."
)


@dataclass
class ReleaseReadinessRecord:
    readiness_id: str
    report_id: str
    release_status: str
    release_blocked: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    evidence_approval_status: str
    manual_review_status: str
    source_verification_status: str
    timestamp_verification_status: str
    quote_verification_status: str
    context_verification_status: str
    ci_policy_status: str
    blocker_reasons: List[str]
    release_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"ReleaseReadinessRecord.{field_name} must be a non-empty string"
        )


def _require_blocker_reasons(data: Dict[str, Any]) -> List[str]:
    reasons = data.get("blocker_reasons")
    if not isinstance(reasons, list):
        raise ValueError("ReleaseReadinessRecord.blocker_reasons must be a list")
    if data.get("release_blocked") is True and not reasons:
        raise ValueError(
            "ReleaseReadinessRecord.blocker_reasons must be non-empty when "
            "release_blocked is true"
        )
    for reason in reasons:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "ReleaseReadinessRecord.blocker_reasons must contain non-empty strings"
            )
    return reasons


def _reject_affirmative_release_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_RELEASE_CLAIMS:
        if claim in text:
            raise ValueError(
                "ReleaseReadinessRecord contains prohibited release claim: "
                f"{claim}"
            )


def validate_release_readiness_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "readiness_id",
        "report_id",
        "release_status",
        "evidence_approval_status",
        "manual_review_status",
        "source_verification_status",
        "timestamp_verification_status",
        "quote_verification_status",
        "context_verification_status",
        "ci_policy_status",
        "release_notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["release_status"] not in RELEASE_STATUSES:
        raise ValueError(
            f"ReleaseReadinessRecord.release_status is unsupported: "
            f"{data['release_status']}"
        )

    if data.get("release_blocked") is not True:
        raise ValueError("ReleaseReadinessRecord.release_blocked must be true")
    if data.get("public_ready") is not False:
        raise ValueError("ReleaseReadinessRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError("ReleaseReadinessRecord.institutional_ready must be false")
    if data.get("report_ready") is not False:
        raise ValueError("ReleaseReadinessRecord.report_ready must be false")

    reasons = _require_blocker_reasons(data)
    if data["release_status"] in BLOCKED_RELEASE_STATUSES and not reasons:
        raise ValueError(
            "ReleaseReadinessRecord blocked statuses require blocker reasons"
        )

    _reject_affirmative_release_claims(data)


def _load_hardening_record(
    input_path: Path = DEFAULT_FINAL_REPORT_HARDENING_RECORD,
) -> Dict[str, Any]:
    if not input_path.exists():
        harden_final_report_dry_run()

    artifact = json.loads(input_path.read_text(encoding="utf-8"))
    record = artifact.get("record")
    if not isinstance(record, dict):
        raise ValueError("Final report hardening artifact must contain record")
    validate_final_report_hardening_record(record)
    return record


def build_release_readiness_record_dry_run(
    hardening_input_path: Path = DEFAULT_FINAL_REPORT_HARDENING_RECORD,
) -> ReleaseReadinessRecord:
    hardening_record = _load_hardening_record(hardening_input_path)
    record = ReleaseReadinessRecord(
        readiness_id="RELEASE_READINESS_V1_DRY_RUN",
        report_id=str(hardening_record["report_id"]),
        release_status="blocked_manual_review_required",
        release_blocked=True,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        evidence_approval_status="manual_review_required",
        manual_review_status="pending_review",
        source_verification_status="source_present_but_not_release_approved",
        timestamp_verification_status="fixture_verified_not_public_evidence",
        quote_verification_status="fixture_verified_not_public_evidence",
        context_verification_status="manual_context_review_required",
        ci_policy_status="github_actions_unavailable_local_ci_used",
        blocker_reasons=list(DRY_RUN_BLOCKER_REASONS),
        release_notes=DRY_RUN_RELEASE_NOTES,
    )
    validate_release_readiness_record(record)
    return record


def write_release_readiness_outputs(
    record: ReleaseReadinessRecord,
    output_dir: Path = DEFAULT_RELEASE_READINESS_DIR,
) -> Dict[str, str]:
    validate_release_readiness_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "release_readiness_record.json"
    summary_path = output_dir / "release_readiness_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "readiness_id": record.readiness_id,
        "report_id": record.report_id,
        "release_status": record.release_status,
        "release_blocked": record.release_blocked,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "blocker_count": len(record.blocker_reasons),
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }

    save_json(
        {
            "metadata": {
                "generated_at_utc": utc_now_iso(),
                "mode": "dry-run",
                "release_blocked": True,
                "public_ready": False,
                "institutional_ready": False,
                "report_ready": False,
            },
            "record": record.to_dict(),
        },
        str(record_path),
    )
    save_json(summary, str(summary_path))
    return {
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }


def check_release_readiness_dry_run(
    output_dir: Path = DEFAULT_RELEASE_READINESS_DIR,
) -> Dict[str, Any]:
    record = build_release_readiness_record_dry_run()
    outputs = write_release_readiness_outputs(record, output_dir)
    return {
        "readiness_id": record.readiness_id,
        "report_id": record.report_id,
        "release_status": record.release_status,
        "release_blocked": record.release_blocked,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "blocker_count": len(record.blocker_reasons),
        "record": record,
        **outputs,
    }
