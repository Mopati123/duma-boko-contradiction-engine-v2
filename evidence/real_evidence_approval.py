"""
real_evidence_approval.py - Conservative real evidence approval candidates.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.manual_review import (
    DEFAULT_MANUAL_REVIEW_RECORDS_OUTPUT,
    manual_review_dry_run,
    validate_manual_review_record,
)


DEFAULT_REAL_EVIDENCE_APPROVAL_DIR = Path("outputs/real_evidence_approval")
DEFAULT_REAL_EVIDENCE_APPROVAL_RECORDS_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_APPROVAL_DIR / "real_evidence_approval_records.json"
)
DEFAULT_REAL_EVIDENCE_APPROVAL_SUMMARY_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_APPROVAL_DIR / "real_evidence_approval_summary.json"
)

APPROVAL_STATUSES = {
    "blocked_missing_real_evidence",
    "blocked_manual_review_required",
    "blocked_context_review_required",
    "approved_evidence_candidate",
    "rejected_evidence",
}

BLOCKED_APPROVAL_STATUSES = {
    "blocked_missing_real_evidence",
    "blocked_manual_review_required",
    "blocked_context_review_required",
}

APPROVAL_CANDIDATE_REQUIREMENTS = {
    "transcript_status": "real_transcript_verified",
    "timestamp_status": "real_timestamp_verified",
    "quote_status": "real_quote_verified",
    "context_status": "context_verified",
    "case_relevance_status": "case_relevance_verified",
}

DRY_RUN_BLOCKER_REASONS = [
    "real transcript approval required",
    "real timestamp approval required",
    "real quote approval required",
    "context approval required",
    "reviewer approval required",
]

FORBIDDEN_APPROVAL_CLAIMS = (
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


@dataclass
class RealEvidenceApprovalRecord:
    approval_id: str
    evidence_id: str
    case_id: str
    source_url: str
    transcript_status: str
    timestamp_status: str
    quote_status: str
    context_status: str
    case_relevance_status: str
    reviewer: str
    approval_status: str
    approval_candidate: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    approval_notes: str
    blocker_reasons: List[str]

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
            f"RealEvidenceApprovalRecord.{field_name} must be a non-empty string"
        )


def _require_blocker_reasons(data: Dict[str, Any]) -> List[str]:
    reasons = data.get("blocker_reasons")
    if not isinstance(reasons, list):
        raise ValueError("RealEvidenceApprovalRecord.blocker_reasons must be a list")
    for reason in reasons:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "RealEvidenceApprovalRecord.blocker_reasons must contain "
                "non-empty strings"
            )
    return reasons


def _reject_approval_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_APPROVAL_CLAIMS:
        if claim in text:
            raise ValueError(
                "RealEvidenceApprovalRecord contains prohibited readiness claim: "
                f"{claim}"
            )


def validate_real_evidence_approval_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "approval_id",
        "evidence_id",
        "case_id",
        "source_url",
        "transcript_status",
        "timestamp_status",
        "quote_status",
        "context_status",
        "case_relevance_status",
        "reviewer",
        "approval_status",
        "approval_notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["approval_status"] not in APPROVAL_STATUSES:
        raise ValueError(
            "RealEvidenceApprovalRecord.approval_status is unsupported: "
            f"{data['approval_status']}"
        )

    if data.get("public_ready") is not False:
        raise ValueError("RealEvidenceApprovalRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "RealEvidenceApprovalRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("RealEvidenceApprovalRecord.report_ready must be false")

    reasons = _require_blocker_reasons(data)
    if data["approval_status"] in BLOCKED_APPROVAL_STATUSES and not reasons:
        raise ValueError(
            "RealEvidenceApprovalRecord blocked statuses require blocker_reasons"
        )
    if data["approval_status"] == "rejected_evidence" and not reasons:
        raise ValueError(
            "RealEvidenceApprovalRecord.rejected_evidence requires blocker_reasons"
        )

    if data.get("approval_candidate") is True:
        for field_name, expected in APPROVAL_CANDIDATE_REQUIREMENTS.items():
            if data.get(field_name) != expected:
                raise ValueError(
                    "RealEvidenceApprovalRecord.approval_candidate requires "
                    f"{field_name}={expected}"
                )
        if data["approval_status"] != "approved_evidence_candidate":
            raise ValueError(
                "RealEvidenceApprovalRecord.approval_candidate requires "
                "approval_status=approved_evidence_candidate"
            )
    elif data.get("approval_candidate") is not False:
        raise ValueError(
            "RealEvidenceApprovalRecord.approval_candidate must be a boolean"
        )

    if data["approval_status"] == "approved_evidence_candidate":
        for field_name, expected in APPROVAL_CANDIDATE_REQUIREMENTS.items():
            if data.get(field_name) != expected:
                raise ValueError(
                    "RealEvidenceApprovalRecord.approved_evidence_candidate "
                    f"requires {field_name}={expected}"
                )

    _reject_approval_claims(data)


def _load_manual_review_records(
    input_path: Path = DEFAULT_MANUAL_REVIEW_RECORDS_OUTPUT,
) -> List[Dict[str, Any]]:
    if not input_path.exists():
        manual_review_dry_run()

    artifact = json.loads(input_path.read_text(encoding="utf-8"))
    records = artifact.get("records")
    if not isinstance(records, list):
        raise ValueError("Manual review artifact must contain records")

    loaded = [_as_dict(record) for record in records]
    for record in loaded:
        validate_manual_review_record(record)
    return loaded


def _manual_review_to_approval_record(
    review_record: Dict[str, Any],
) -> RealEvidenceApprovalRecord:
    evidence_id = str(review_record.get("evidence_id", ""))
    record = RealEvidenceApprovalRecord(
        approval_id=f"APPROVAL_{evidence_id}",
        evidence_id=evidence_id,
        case_id=str(review_record.get("case_id", "")),
        source_url=str(review_record.get("url", "")),
        transcript_status="real_transcript_approval_required",
        timestamp_status="real_timestamp_approval_required",
        quote_status="real_quote_approval_required",
        context_status="context_approval_required",
        case_relevance_status="case_relevance_review_required",
        reviewer="real-evidence-approval-v1-dry-run",
        approval_status="blocked_manual_review_required",
        approval_candidate=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        approval_notes=(
            "Dry-run approval record only. Real transcript, timestamp, quote, "
            "context, case relevance, and reviewer approval are required before "
            "candidate approval."
        ),
        blocker_reasons=list(DRY_RUN_BLOCKER_REASONS),
    )
    validate_real_evidence_approval_record(record)
    return record


def build_real_evidence_approval_records_dry_run() -> List[RealEvidenceApprovalRecord]:
    review_records = _load_manual_review_records()
    records = [_manual_review_to_approval_record(record) for record in review_records]
    return records


def write_real_evidence_approval_outputs(
    records: List[RealEvidenceApprovalRecord],
    output_dir: Path = DEFAULT_REAL_EVIDENCE_APPROVAL_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_real_evidence_approval_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "real_evidence_approval_records.json"
    summary_path = output_dir / "real_evidence_approval_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "total_evidence_items_evaluated": len(records),
        "approved_evidence_candidate": sum(
            1 for record in records if record.approval_status == "approved_evidence_candidate"
        ),
        "blocked_missing_real_evidence": sum(
            1 for record in records if record.approval_status == "blocked_missing_real_evidence"
        ),
        "blocked_manual_review_required": sum(
            1 for record in records if record.approval_status == "blocked_manual_review_required"
        ),
        "blocked_context_review_required": sum(
            1 for record in records if record.approval_status == "blocked_context_review_required"
        ),
        "rejected_evidence": sum(
            1 for record in records if record.approval_status == "rejected_evidence"
        ),
        "public_ready": sum(1 for record in records if record.public_ready),
        "institutional_ready": sum(
            1 for record in records if record.institutional_ready
        ),
        "report_ready": sum(1 for record in records if record.report_ready),
        "records_output": str(records_path),
        "summary_output": str(summary_path),
    }

    save_json(
        {
            "metadata": {
                "generated_at_utc": utc_now_iso(),
                "mode": "dry-run",
                "public_ready": False,
                "institutional_ready": False,
                "report_ready": False,
            },
            "records": [record.to_dict() for record in records],
        },
        str(records_path),
    )
    save_json(summary, str(summary_path))
    return {
        "records_output": str(records_path),
        "summary_output": str(summary_path),
    }


def approve_real_evidence_dry_run(
    output_dir: Path = DEFAULT_REAL_EVIDENCE_APPROVAL_DIR,
) -> Dict[str, Any]:
    records = build_real_evidence_approval_records_dry_run()
    outputs = write_real_evidence_approval_outputs(records, output_dir)

    return {
        "total_evidence_items_evaluated": len(records),
        "approved_evidence_candidate": sum(
            1 for record in records if record.approval_status == "approved_evidence_candidate"
        ),
        "blocked_missing_real_evidence": sum(
            1 for record in records if record.approval_status == "blocked_missing_real_evidence"
        ),
        "blocked_manual_review_required": sum(
            1 for record in records if record.approval_status == "blocked_manual_review_required"
        ),
        "blocked_context_review_required": sum(
            1 for record in records if record.approval_status == "blocked_context_review_required"
        ),
        "rejected_evidence": sum(
            1 for record in records if record.approval_status == "rejected_evidence"
        ),
        "public_ready": sum(1 for record in records if record.public_ready),
        "institutional_ready": sum(
            1 for record in records if record.institutional_ready
        ),
        "report_ready": sum(1 for record in records if record.report_ready),
        "records": records,
        **outputs,
    }
