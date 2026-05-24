"""
manual_review.py - Conservative manual review records for real evidence.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.real_evidence_replacement import (
    DEFAULT_REAL_STATUS_OUTPUT,
    replace_real_evidence,
)


DEFAULT_MANUAL_REVIEW_OUTPUT_DIR = Path("outputs/manual_review")
DEFAULT_MANUAL_REVIEW_RECORDS_OUTPUT = (
    DEFAULT_MANUAL_REVIEW_OUTPUT_DIR / "manual_review_records.json"
)
DEFAULT_MANUAL_REVIEW_SUMMARY_OUTPUT = (
    DEFAULT_MANUAL_REVIEW_OUTPUT_DIR / "manual_review_summary.json"
)

REVIEW_STATUSES = {
    "pending_review",
    "reviewed_with_concerns",
    "reviewed_rejected",
    "reviewed_candidate",
}

PUBLICATION_RECOMMENDATIONS = {
    "do_not_publish",
    "needs_more_evidence",
    "candidate_for_hardening",
}

PROHIBITED_READINESS_TEXT = {
    "institution_ready",
    "institution-ready",
    "ready for institutional release",
    "ready for public release",
}

DRY_RUN_REVIEW_NOTES = (
    "Dry-run review record only. Real transcript, timestamp, quote, and context "
    "require human verification."
)


@dataclass
class ManualReviewRecord:
    review_id: str
    evidence_id: str
    case_id: str
    url: str
    reviewer: str
    review_status: str
    transcript_review: str
    timestamp_review: str
    quote_review: str
    context_review: str
    speaker_review: str
    publication_recommendation: str
    manual_review_required: bool
    public_ready: bool
    report_ready: bool
    review_notes: str

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
        raise ValueError(f"ManualReviewRecord.{field_name} must be a non-empty string")


def _reject_readiness_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in PROHIBITED_READINESS_TEXT:
        if claim in text:
            raise ValueError(
                f"ManualReviewRecord contains prohibited readiness claim: {claim}"
            )


def validate_manual_review_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "review_id",
        "evidence_id",
        "case_id",
        "url",
        "reviewer",
        "review_status",
        "transcript_review",
        "timestamp_review",
        "quote_review",
        "context_review",
        "speaker_review",
        "publication_recommendation",
        "review_notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["review_status"] not in REVIEW_STATUSES:
        raise ValueError(
            f"ManualReviewRecord.review_status is unsupported: {data['review_status']}"
        )

    if data["publication_recommendation"] not in PUBLICATION_RECOMMENDATIONS:
        raise ValueError(
            "ManualReviewRecord.publication_recommendation is unsupported: "
            f"{data['publication_recommendation']}"
        )

    if data["publication_recommendation"] == "public_ready":
        raise ValueError(
            "ManualReviewRecord.publication_recommendation cannot be public_ready"
        )

    if data.get("manual_review_required") is not True:
        raise ValueError("ManualReviewRecord.manual_review_required must be true")
    if data.get("public_ready") is not False:
        raise ValueError("ManualReviewRecord.public_ready must be false")
    if data.get("report_ready") is not False:
        raise ValueError("ManualReviewRecord.report_ready must be false")

    if data["review_status"] in {"reviewed_rejected", "reviewed_with_concerns"}:
        if "reason" not in data["review_notes"].lower():
            raise ValueError(
                f"ManualReviewRecord.{data['review_status']} requires a reason "
                "in review_notes"
            )

    _reject_readiness_claims(data)


def _status_to_review_record(status: Dict[str, Any]) -> ManualReviewRecord:
    evidence_id = str(status.get("evidence_id", ""))
    record = ManualReviewRecord(
        review_id=f"REVIEW_{evidence_id}",
        evidence_id=evidence_id,
        case_id=str(status.get("case_id", "")),
        url=str(status.get("url", "")),
        reviewer="manual-review-v1-dry-run",
        review_status="pending_review",
        transcript_review=(
            f"Transcript status: {status.get('transcript_status', 'unavailable')}. "
            "Human verification required."
        ),
        timestamp_review=(
            f"Timestamp status: {status.get('timestamp_status', 'unavailable')}. "
            "Human verification required."
        ),
        quote_review=(
            f"Quote status: {status.get('quote_status', 'unavailable')}. "
            "Human verification required."
        ),
        context_review="Context requires human verification.",
        speaker_review="Speaker identity and confidence require human verification.",
        publication_recommendation="needs_more_evidence",
        manual_review_required=True,
        public_ready=False,
        report_ready=False,
        review_notes=DRY_RUN_REVIEW_NOTES,
    )
    validate_manual_review_record(record)
    return record


def load_real_evidence_statuses(
    input_path: Path = DEFAULT_REAL_STATUS_OUTPUT,
) -> List[Dict[str, Any]]:
    if not input_path.exists():
        replace_real_evidence(dry_run=True)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    statuses = data.get("statuses")
    if not isinstance(statuses, list):
        raise ValueError("Real evidence status artifact must contain statuses")
    return [_as_dict(status) for status in statuses]


def write_manual_review_outputs(
    records: List[ManualReviewRecord],
    output_dir: Path = DEFAULT_MANUAL_REVIEW_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_manual_review_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "manual_review_records.json"
    summary_path = output_dir / "manual_review_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "total_evidence_records_reviewed": len(records),
        "pending_review": sum(
            1 for record in records if record.review_status == "pending_review"
        ),
        "reviewed_with_concerns": sum(
            1 for record in records if record.review_status == "reviewed_with_concerns"
        ),
        "reviewed_rejected": sum(
            1 for record in records if record.review_status == "reviewed_rejected"
        ),
        "reviewed_candidate": sum(
            1 for record in records if record.review_status == "reviewed_candidate"
        ),
        "public_ready": sum(1 for record in records if record.public_ready),
        "report_ready": sum(1 for record in records if record.report_ready),
        "manual_review_required": sum(
            1 for record in records if record.manual_review_required
        ),
        "records_output": str(records_path),
        "summary_output": str(summary_path),
    }

    save_json(
        {
            "metadata": {
                "generated_at_utc": utc_now_iso(),
                "mode": "dry-run",
                "manual_review_required": True,
                "public_ready": False,
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


def manual_review_dry_run(
    output_dir: Path = DEFAULT_MANUAL_REVIEW_OUTPUT_DIR,
) -> Dict[str, Any]:
    statuses = load_real_evidence_statuses()
    records = [_status_to_review_record(status) for status in statuses]
    outputs = write_manual_review_outputs(records, output_dir)

    return {
        "total_evidence_records_reviewed": len(records),
        "pending_review": sum(
            1 for record in records if record.review_status == "pending_review"
        ),
        "reviewed_with_concerns": sum(
            1 for record in records if record.review_status == "reviewed_with_concerns"
        ),
        "reviewed_rejected": sum(
            1 for record in records if record.review_status == "reviewed_rejected"
        ),
        "reviewed_candidate": sum(
            1 for record in records if record.review_status == "reviewed_candidate"
        ),
        "public_ready": sum(1 for record in records if record.public_ready),
        "report_ready": sum(1 for record in records if record.report_ready),
        "records": records,
        **outputs,
    }
