"""
source_content_verification.py - Candidate-only verification of extracted content.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

from evidence.selected_recovery_source import load_selected_recovery_sources
from evidence.source_content_extraction import (
    DEFAULT_SOURCE_CONTENT_EXTRACTION_STATUS_OUTPUT,
    KEYWORDS_BY_EVIDENCE_ID,
    SourceContentExtractionRecord,
    validate_source_content_extraction_record,
)


DEFAULT_SOURCE_CONTENT_VERIFICATION_OUTPUT_DIR = Path(
    "outputs/source_content_verification"
)
DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT = (
    DEFAULT_SOURCE_CONTENT_VERIFICATION_OUTPUT_DIR
    / "source_content_verification_status.json"
)
DEFAULT_SOURCE_CONTENT_VERIFICATION_SUMMARY_OUTPUT = (
    DEFAULT_SOURCE_CONTENT_VERIFICATION_OUTPUT_DIR
    / "source_content_verification_summary.json"
)

VERIFICATION_STATUSES = {
    "not_checked",
    "verified_candidate_for_content_review",
    "blocked_pending_fallback",
    "extraction_unavailable",
    "rejected",
    "error",
}

CONTENT_REVIEW_STATUSES = {
    "not_checked",
    "keyword_match",
    "insufficient_content",
    "blocked_source",
    "requires_fallback_source",
    "error",
}

FORBIDDEN_VERIFICATION_CLAIMS = (
    "verified_for_approval_review",
    "approved_evidence: true",
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "approved evidence",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "final forensic report",
)


@dataclass
class SourceContentVerificationRecord:
    original_evidence_id: str
    selected_recovery_candidate_id: str
    source_url: str
    extraction_status: str
    verification_status: str
    content_review_status: str
    extracted_text_candidate: str
    extracted_quote_candidate: str
    verification_notes: str
    verified_for_content_review: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool

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
            f"SourceContentVerificationRecord.{field_name} must be a non-empty string"
        )


def _reject_forbidden_claims(data: Dict[str, Any]) -> None:
    if "verified_for_approval_review" in data:
        raise ValueError(
            "SourceContentVerificationRecord must not contain "
            "verified_for_approval_review"
        )

    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_VERIFICATION_CLAIMS:
        if claim in text:
            raise ValueError(
                "SourceContentVerificationRecord contains prohibited "
                f"approval/readiness claim: {claim}"
            )


def _contains_keyword(original_evidence_id: str, text: str) -> bool:
    normalized = text.lower()
    return any(
        keyword.lower() in normalized
        for keyword in KEYWORDS_BY_EVIDENCE_ID.get(original_evidence_id, ())
    )


def validate_source_content_verification_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "original_evidence_id",
        "selected_recovery_candidate_id",
        "source_url",
        "extraction_status",
        "verification_status",
        "content_review_status",
        "verification_notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(
            "SourceContentVerificationRecord.verification_status is unsupported: "
            f"{data['verification_status']}"
        )
    if data["content_review_status"] not in CONTENT_REVIEW_STATUSES:
        raise ValueError(
            "SourceContentVerificationRecord.content_review_status is unsupported: "
            f"{data['content_review_status']}"
        )

    if data.get("requires_manual_review") is not True:
        raise ValueError(
            "SourceContentVerificationRecord.requires_manual_review must be true"
        )
    if data.get("approved_evidence") is not False:
        raise ValueError(
            "SourceContentVerificationRecord.approved_evidence must be false"
        )
    if data.get("public_ready") is not False:
        raise ValueError("SourceContentVerificationRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "SourceContentVerificationRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("SourceContentVerificationRecord.report_ready must be false")

    if (
        data.get("verified_for_content_review") is True
        and data["verification_status"] != "verified_candidate_for_content_review"
    ):
        raise ValueError(
            "SourceContentVerificationRecord.verified_for_content_review requires "
            "verification_status=verified_candidate_for_content_review"
        )

    _reject_forbidden_claims(data)


def _record_from_extraction_dict(data: Dict[str, Any]) -> SourceContentExtractionRecord:
    return SourceContentExtractionRecord(
        original_evidence_id=str(data.get("original_evidence_id", "")),
        selected_recovery_candidate_id=str(
            data.get("selected_recovery_candidate_id", "")
        ),
        source_url=str(data.get("source_url", "")),
        extraction_status=str(data.get("extraction_status", "")),
        content_source_status=str(data.get("content_source_status", "")),
        extracted_text_candidate=str(data.get("extracted_text_candidate", "")),
        extracted_quote_candidate=str(data.get("extracted_quote_candidate", "")),
        extraction_method=str(data.get("extraction_method", "")),
        requires_manual_review=bool(data.get("requires_manual_review", False)),
        approved_evidence=bool(data.get("approved_evidence", False)),
        public_ready=bool(data.get("public_ready", False)),
        institutional_ready=bool(data.get("institutional_ready", False)),
        report_ready=bool(data.get("report_ready", False)),
        notes=str(data.get("notes", "")),
    )


def build_verification_record(
    extraction_record: SourceContentExtractionRecord,
    verification_status: str,
    content_review_status: str,
    verification_notes: str,
    verified_for_content_review: bool = False,
) -> SourceContentVerificationRecord:
    validate_source_content_extraction_record(extraction_record)
    record = SourceContentVerificationRecord(
        original_evidence_id=extraction_record.original_evidence_id,
        selected_recovery_candidate_id=(
            extraction_record.selected_recovery_candidate_id
        ),
        source_url=extraction_record.source_url,
        extraction_status=extraction_record.extraction_status,
        verification_status=verification_status,
        content_review_status=content_review_status,
        extracted_text_candidate=extraction_record.extracted_text_candidate,
        extracted_quote_candidate=extraction_record.extracted_quote_candidate,
        verification_notes=verification_notes,
        verified_for_content_review=verified_for_content_review,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
    )
    validate_source_content_verification_record(record)
    return record


def build_missing_artifact_records(
    evidence_id: Optional[str] = None,
) -> List[SourceContentVerificationRecord]:
    selected_sources = load_selected_recovery_sources(evidence_id=evidence_id)
    records: List[SourceContentVerificationRecord] = []
    for selected_source in selected_sources:
        extraction_record = SourceContentExtractionRecord(
            original_evidence_id=selected_source.original_evidence_id,
            selected_recovery_candidate_id=(
                selected_source.selected_recovery_candidate_id
            ),
            source_url=selected_source.selected_source_url,
            extraction_status="not_checked",
            content_source_status="not_checked",
            extracted_text_candidate="",
            extracted_quote_candidate="",
            extraction_method="no_artifact",
            requires_manual_review=True,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            notes="No source content extraction artifact found.",
        )
        records.append(
            build_verification_record(
                extraction_record,
                verification_status="not_checked",
                content_review_status="insufficient_content",
                verification_notes=(
                    "No source content extraction artifact found; human review or "
                    "a fresh extraction dry-run is required."
                ),
            )
        )
    return records


def verify_extraction_record(
    extraction_record: SourceContentExtractionRecord,
) -> SourceContentVerificationRecord:
    validate_source_content_extraction_record(extraction_record)

    if extraction_record.extraction_status == "extracted_candidate":
        candidate_text = (
            f"{extraction_record.extracted_text_candidate} "
            f"{extraction_record.extracted_quote_candidate}"
        )
        if _contains_keyword(extraction_record.original_evidence_id, candidate_text):
            return build_verification_record(
                extraction_record,
                verification_status="verified_candidate_for_content_review",
                content_review_status="keyword_match",
                verification_notes=(
                    "Extracted candidate contains configured source-content keywords. "
                    "Human manual review is still required before template use."
                ),
                verified_for_content_review=True,
            )
        return build_verification_record(
            extraction_record,
            verification_status="extraction_unavailable",
            content_review_status="insufficient_content",
            verification_notes=(
                "Extracted candidate did not contain configured source-content "
                "keywords; fallback or human review is required."
            ),
        )

    if extraction_record.extraction_status == "blocked":
        return build_verification_record(
            extraction_record,
            verification_status="blocked_pending_fallback",
            content_review_status="requires_fallback_source",
            verification_notes=(
                "Selected source was blocked during extraction; fallback source "
                "review is required."
            ),
        )

    if extraction_record.extraction_status == "not_checked":
        return build_verification_record(
            extraction_record,
            verification_status="not_checked",
            content_review_status="not_checked",
            verification_notes=(
                "Extraction has not checked source content; human review or a fresh "
                "extraction dry-run is required."
            ),
        )

    if extraction_record.extraction_status == "extraction_unavailable":
        return build_verification_record(
            extraction_record,
            verification_status="extraction_unavailable",
            content_review_status="insufficient_content",
            verification_notes=(
                "Extraction did not produce a usable candidate; fallback or human "
                "review is required."
            ),
        )

    if extraction_record.extraction_status == "error":
        return build_verification_record(
            extraction_record,
            verification_status="error",
            content_review_status="error",
            verification_notes=(
                "Extraction reported an error; fallback or human review is required."
            ),
        )

    return build_verification_record(
        extraction_record,
        verification_status="rejected",
        content_review_status="insufficient_content",
        verification_notes="Extraction status is unsupported for content review.",
    )


def load_extraction_records(
    status_path: Path = DEFAULT_SOURCE_CONTENT_EXTRACTION_STATUS_OUTPUT,
    evidence_id: Optional[str] = None,
) -> List[SourceContentExtractionRecord]:
    if not status_path.exists():
        return []

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        raise ValueError("source_content_extraction_status.json must contain records")

    records: List[SourceContentExtractionRecord] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, dict):
            raise ValueError("Source content extraction records must be objects")
        record = _record_from_extraction_dict(raw_record)
        validate_source_content_extraction_record(record)
        if evidence_id is None or record.original_evidence_id == evidence_id:
            records.append(record)

    return records


def summarize_verification_records(
    records: List[SourceContentVerificationRecord],
    artifact_found: bool,
) -> Dict[str, Any]:
    for record in records:
        validate_source_content_verification_record(record)

    return {
        "generated_at_utc": utc_now_iso(),
        "artifact_found": artifact_found,
        "total_records": len(records),
        "verified_candidate_for_content_review_count": sum(
            1
            for record in records
            if record.verification_status == "verified_candidate_for_content_review"
        ),
        "verified_for_content_review_count": sum(
            1 for record in records if record.verified_for_content_review
        ),
        "blocked_pending_fallback_count": sum(
            1
            for record in records
            if record.verification_status == "blocked_pending_fallback"
        ),
        "extraction_unavailable_count": sum(
            1
            for record in records
            if record.verification_status == "extraction_unavailable"
        ),
        "not_checked_count": sum(
            1 for record in records if record.verification_status == "not_checked"
        ),
        "error_count": sum(
            1 for record in records if record.verification_status == "error"
        ),
        "requires_manual_review_count": sum(
            1 for record in records if record.requires_manual_review
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }


def write_verification_outputs(
    records: List[SourceContentVerificationRecord],
    artifact_found: bool,
    output_dir: Path = DEFAULT_SOURCE_CONTENT_VERIFICATION_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_source_content_verification_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "source_content_verification_status.json"
    summary_path = output_dir / "source_content_verification_summary.json"
    summary = summarize_verification_records(records, artifact_found=artifact_found)
    summary["status_output"] = str(status_path)
    summary["summary_output"] = str(summary_path)

    status_payload = {
        "metadata": {
            "generated_at_utc": summary["generated_at_utc"],
            "artifact_found": artifact_found,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "records": [record.to_dict() for record in records],
    }

    status_path.write_text(json.dumps(status_payload, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"status_output": str(status_path), "summary_output": str(summary_path)}


def verify_source_content(
    evidence_id: Optional[str] = None,
    no_network: bool = False,
    extraction_status_path: Path = DEFAULT_SOURCE_CONTENT_EXTRACTION_STATUS_OUTPUT,
    output_dir: Path = DEFAULT_SOURCE_CONTENT_VERIFICATION_OUTPUT_DIR,
) -> Dict[str, Any]:
    # no_network is explicit in the CLI contract; verification never fetches.
    del no_network
    extraction_records = load_extraction_records(
        status_path=extraction_status_path,
        evidence_id=evidence_id,
    )
    artifact_found = extraction_status_path.exists()
    if extraction_records:
        verification_records = [
            verify_extraction_record(record) for record in extraction_records
        ]
    else:
        verification_records = build_missing_artifact_records(evidence_id=evidence_id)

    outputs = write_verification_outputs(
        verification_records,
        artifact_found=artifact_found,
        output_dir=output_dir,
    )
    summary = summarize_verification_records(
        verification_records,
        artifact_found=artifact_found,
    )
    summary.update(outputs)
    return summary
