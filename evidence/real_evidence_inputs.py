"""
real_evidence_inputs.py - Human-entry templates for real evidence population.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.evidence_location_model import (
    LOCATION_FIELDS,
    validate_evidence_location_for_promotion,
)


DEFAULT_REAL_EVIDENCE_INPUT_DIR = Path("data/real_evidence_inputs")
DEFAULT_REAL_EVIDENCE_INPUT_OUTPUT_DIR = Path("outputs/real_evidence_inputs")
DEFAULT_REAL_EVIDENCE_INPUT_STATUS_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_INPUT_OUTPUT_DIR / "real_evidence_input_status.json"
)
DEFAULT_REAL_EVIDENCE_INPUT_SUMMARY_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_INPUT_OUTPUT_DIR / "real_evidence_input_summary.json"
)

VERIFICATION_STATUSES = {
    "pending_human_entry",
    "entered_pending_review",
    "rejected_do_not_use",
    "verified_for_approval_review",
}

HUMAN_ENTRY_FIELDS = (
    "transcript_text",
    "timestamp_start",
    "timestamp_end",
    "quote_text",
    "speaker",
    "context_summary",
    "case_relevance_note",
    "reviewer",
    "reviewer_notes",
)

FORBIDDEN_READINESS_CLAIMS = (
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
class RealEvidenceInputRecord:
    evidence_id: str
    case_id: str
    source_url: str
    transcript_text: str
    timestamp_start: str
    timestamp_end: str
    quote_text: str
    speaker: str
    context_summary: str
    case_relevance_note: str
    reviewer: str
    reviewer_notes: str
    verification_status: str
    evidence_location_type: str = ""
    excerpt_text: str = ""
    publication_date: str = ""
    paragraph_reference: str = ""
    quote_location: str = ""
    page_reference: str = ""
    section_reference: str = ""

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


def _require_string_field(data: Dict[str, Any], field_name: str) -> None:
    if field_name not in data or not isinstance(data[field_name], str):
        raise ValueError(f"RealEvidenceInputRecord.{field_name} must be a string")


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    _require_string_field(data, field_name)
    if not data[field_name].strip():
        raise ValueError(
            f"RealEvidenceInputRecord.{field_name} must be a non-empty string"
        )


def _reject_readiness_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_READINESS_CLAIMS:
        if claim in text:
            raise ValueError(
                "RealEvidenceInputRecord contains prohibited readiness claim: "
                f"{claim}"
            )


def validate_real_evidence_input_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "evidence_id",
        "case_id",
        "source_url",
        *HUMAN_ENTRY_FIELDS,
        "verification_status",
    ):
        _require_string_field(data, field_name)
    for field_name in LOCATION_FIELDS:
        if field_name in data and not isinstance(data[field_name], str):
            raise ValueError(f"RealEvidenceInputRecord.{field_name} must be a string")

    for field_name in ("evidence_id", "case_id", "source_url", "verification_status"):
        _require_nonempty_string(data, field_name)

    if data["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(
            "RealEvidenceInputRecord.verification_status is unsupported: "
            f"{data['verification_status']}"
        )

    if data["verification_status"] == "verified_for_approval_review":
        for field_name in (
            "speaker",
            "context_summary",
            "case_relevance_note",
            "reviewer",
            "reviewer_notes",
        ):
            _require_nonempty_string(data, field_name)
        validate_evidence_location_for_promotion(data)

    _reject_readiness_claims(data)


def _record_from_dict(data: Dict[str, Any]) -> RealEvidenceInputRecord:
    return RealEvidenceInputRecord(
        evidence_id=str(data.get("evidence_id", "")),
        case_id=str(data.get("case_id", "")),
        source_url=str(data.get("source_url", "")),
        transcript_text=str(data.get("transcript_text", "")),
        timestamp_start=str(data.get("timestamp_start", "")),
        timestamp_end=str(data.get("timestamp_end", "")),
        quote_text=str(data.get("quote_text", "")),
        speaker=str(data.get("speaker", "")),
        context_summary=str(data.get("context_summary", "")),
        case_relevance_note=str(data.get("case_relevance_note", "")),
        reviewer=str(data.get("reviewer", "")),
        reviewer_notes=str(data.get("reviewer_notes", "")),
        verification_status=str(data.get("verification_status", "")),
        evidence_location_type=str(data.get("evidence_location_type", "")),
        excerpt_text=str(data.get("excerpt_text", "")),
        publication_date=str(data.get("publication_date", "")),
        paragraph_reference=str(data.get("paragraph_reference", "")),
        quote_location=str(data.get("quote_location", "")),
        page_reference=str(data.get("page_reference", "")),
        section_reference=str(data.get("section_reference", "")),
    )


def load_real_evidence_input_records(
    input_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
) -> List[RealEvidenceInputRecord]:
    paths = sorted(input_dir.glob("*.template.json"))
    if not paths:
        raise ValueError(f"No real evidence input templates found in {input_dir}")

    records: List[RealEvidenceInputRecord] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Real evidence input template must be an object: {path}")
        record = _record_from_dict(data)
        validate_real_evidence_input_record(record)
        records.append(record)
    return records


def write_real_evidence_input_outputs(
    records: List[RealEvidenceInputRecord],
    output_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_real_evidence_input_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "real_evidence_input_status.json"
    summary_path = output_dir / "real_evidence_input_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "total_input_records": len(records),
        "pending_human_entry": sum(
            1 for record in records if record.verification_status == "pending_human_entry"
        ),
        "entered_pending_review": sum(
            1 for record in records if record.verification_status == "entered_pending_review"
        ),
        "rejected_do_not_use": sum(
            1 for record in records if record.verification_status == "rejected_do_not_use"
        ),
        "verified_for_approval_review": sum(
            1
            for record in records
            if record.verification_status == "verified_for_approval_review"
        ),
        "records_ready_for_approval_review": sum(
            1
            for record in records
            if record.verification_status == "verified_for_approval_review"
        ),
        "status_output": str(status_path),
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
        str(status_path),
    )
    save_json(summary, str(summary_path))
    return {
        "status_output": str(status_path),
        "summary_output": str(summary_path),
    }


def validate_real_evidence_inputs_dry_run(
    input_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    output_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_OUTPUT_DIR,
) -> Dict[str, Any]:
    records = load_real_evidence_input_records(input_dir)
    outputs = write_real_evidence_input_outputs(records, output_dir)
    return {
        "total_input_records": len(records),
        "pending_human_entry": sum(
            1 for record in records if record.verification_status == "pending_human_entry"
        ),
        "entered_pending_review": sum(
            1 for record in records if record.verification_status == "entered_pending_review"
        ),
        "rejected_do_not_use": sum(
            1 for record in records if record.verification_status == "rejected_do_not_use"
        ),
        "verified_for_approval_review": sum(
            1
            for record in records
            if record.verification_status == "verified_for_approval_review"
        ),
        "records_ready_for_approval_review": sum(
            1
            for record in records
            if record.verification_status == "verified_for_approval_review"
        ),
        "records": records,
        **outputs,
    }
