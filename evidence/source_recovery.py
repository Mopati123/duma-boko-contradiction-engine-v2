"""
source_recovery.py - Candidate-only registry for evidence source recovery.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json


DEFAULT_SOURCE_RECOVERY_PATH = Path(
    "data/source_recovery/source_recovery_candidates.json"
)

ALLOWED_ORIGINAL_EVIDENCE_IDS = {
    "VID_JOBS_001",
    "VID_HEALTH_001",
}

VERIFICATION_STATUSES = {
    "candidate_unverified",
    "rejected",
    "verified_for_manual_review",
}

READINESS_FIELDS = {
    "approved",
    "approved_candidate",
    "approval_candidate",
    "approved_evidence_candidate",
    "public_ready",
    "institutional_ready",
    "report_ready",
}

FORBIDDEN_RECOVERY_CLAIMS = (
    "approved evidence",
    "approved_evidence_candidate",
    "approval_candidate: true",
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
class SourceRecoveryCandidateRecord:
    original_evidence_id: str
    original_source_url: str
    original_failure_status: str
    recovery_candidate_id: str
    recovery_source_url: str
    recovery_source_type: str
    recovery_source_rank: int
    recovery_reason: str
    verification_status: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
            f"SourceRecoveryCandidateRecord.{field_name} must be a non-empty string"
        )


def _reject_approval_or_readiness(data: Dict[str, Any]) -> None:
    for field_name in READINESS_FIELDS:
        if field_name in data:
            raise ValueError(
                "SourceRecoveryCandidateRecord must not contain approval/readiness "
                f"field: {field_name}"
            )

    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_RECOVERY_CLAIMS:
        if claim in text:
            raise ValueError(
                "SourceRecoveryCandidateRecord contains prohibited approval/readiness "
                f"claim: {claim}"
            )


def validate_source_recovery_candidate_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "original_evidence_id",
        "original_source_url",
        "original_failure_status",
        "recovery_candidate_id",
        "recovery_source_url",
        "recovery_source_type",
        "recovery_reason",
        "verification_status",
        "notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["original_evidence_id"] not in ALLOWED_ORIGINAL_EVIDENCE_IDS:
        raise ValueError(
            "SourceRecoveryCandidateRecord.original_evidence_id is unsupported: "
            f"{data['original_evidence_id']}"
        )

    if data["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(
            "SourceRecoveryCandidateRecord.verification_status is unsupported: "
            f"{data['verification_status']}"
        )

    rank = data.get("recovery_source_rank")
    if not isinstance(rank, int) or rank < 1:
        raise ValueError(
            "SourceRecoveryCandidateRecord.recovery_source_rank must be a positive "
            "integer"
        )

    _reject_approval_or_readiness(data)


def _record_from_dict(data: Dict[str, Any]) -> SourceRecoveryCandidateRecord:
    return SourceRecoveryCandidateRecord(
        original_evidence_id=str(data.get("original_evidence_id", "")),
        original_source_url=str(data.get("original_source_url", "")),
        original_failure_status=str(data.get("original_failure_status", "")),
        recovery_candidate_id=str(data.get("recovery_candidate_id", "")),
        recovery_source_url=str(data.get("recovery_source_url", "")),
        recovery_source_type=str(data.get("recovery_source_type", "")),
        recovery_source_rank=data.get("recovery_source_rank", 0),
        recovery_reason=str(data.get("recovery_reason", "")),
        verification_status=str(data.get("verification_status", "candidate_unverified")),
        notes=str(data.get("notes", "")),
    )


def load_source_recovery_candidates(
    path: Path = DEFAULT_SOURCE_RECOVERY_PATH,
    evidence_id: Optional[str] = None,
) -> List[SourceRecoveryCandidateRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_records = data.get("candidates")
    else:
        raw_records = data

    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("source_recovery_candidates.json must contain candidates")

    seen_candidate_ids = set()
    records: List[SourceRecoveryCandidateRecord] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, dict):
            raise ValueError("Source recovery candidate records must be objects")
        record = _record_from_dict(raw_record)
        validate_source_recovery_candidate_record(record)
        if record.recovery_candidate_id in seen_candidate_ids:
            raise ValueError(
                "Duplicate source recovery candidate ID: "
                f"{record.recovery_candidate_id}"
            )
        seen_candidate_ids.add(record.recovery_candidate_id)
        if evidence_id is None or record.original_evidence_id == evidence_id:
            records.append(record)

    if evidence_id is not None and evidence_id not in ALLOWED_ORIGINAL_EVIDENCE_IDS:
        raise ValueError(f"Unsupported evidence_id for source recovery: {evidence_id}")

    return records


def group_source_recovery_candidates(
    records: List[SourceRecoveryCandidateRecord],
) -> Dict[str, List[SourceRecoveryCandidateRecord]]:
    grouped: Dict[str, List[SourceRecoveryCandidateRecord]] = {}
    for record in records:
        validate_source_recovery_candidate_record(record)
        grouped.setdefault(record.original_evidence_id, []).append(record)
    return grouped


def summarize_source_recovery_candidates(
    records: List[SourceRecoveryCandidateRecord],
) -> Dict[str, Any]:
    for record in records:
        validate_source_recovery_candidate_record(record)

    return {
        "total_candidates": len(records),
        "jobs_candidates": sum(
            1 for record in records if record.original_evidence_id == "VID_JOBS_001"
        ),
        "health_candidates": sum(
            1 for record in records if record.original_evidence_id == "VID_HEALTH_001"
        ),
        "approved_candidates": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }
