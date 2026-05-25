"""
selected_recovery_source.py - Controlled source selections for content review.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from evidence.source_recovery import (
    ALLOWED_ORIGINAL_EVIDENCE_IDS,
    SourceRecoveryCandidateRecord,
    load_source_recovery_candidates,
    validate_source_recovery_candidate_record,
)


DEFAULT_SELECTED_RECOVERY_SOURCE_PATH = Path(
    "data/source_recovery/selected_recovery_sources.json"
)

SELECTION_STATUSES = {
    "selected_for_content_review",
    "rejected",
    "pending_selection",
}


@dataclass
class SelectedRecoverySourceRecord:
    original_evidence_id: str
    selected_recovery_candidate_id: str
    selected_source_url: str
    selected_source_type: str
    selection_reason: str
    selection_status: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"SelectedRecoverySourceRecord.{field_name} must be a non-empty string"
        )


def _candidate_lookup(
    candidates: Optional[List[SourceRecoveryCandidateRecord]] = None,
) -> Dict[str, SourceRecoveryCandidateRecord]:
    selected_candidates = candidates
    if selected_candidates is None:
        selected_candidates = load_source_recovery_candidates()

    lookup: Dict[str, SourceRecoveryCandidateRecord] = {}
    for candidate in selected_candidates:
        validate_source_recovery_candidate_record(candidate)
        lookup[candidate.recovery_candidate_id] = candidate
    return lookup


def validate_selected_recovery_source_record(
    record: Any,
    candidates: Optional[List[SourceRecoveryCandidateRecord]] = None,
) -> None:
    data = _as_dict(record)

    for field_name in (
        "original_evidence_id",
        "selected_recovery_candidate_id",
        "selected_source_url",
        "selected_source_type",
        "selection_reason",
        "selection_status",
        "notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["original_evidence_id"] not in ALLOWED_ORIGINAL_EVIDENCE_IDS:
        raise ValueError(
            "SelectedRecoverySourceRecord.original_evidence_id is unsupported: "
            f"{data['original_evidence_id']}"
        )

    if data["selection_status"] not in SELECTION_STATUSES:
        raise ValueError(
            "SelectedRecoverySourceRecord.selection_status is unsupported: "
            f"{data['selection_status']}"
        )

    if data.get("approved_evidence") is not False:
        raise ValueError("SelectedRecoverySourceRecord.approved_evidence must be false")
    if data.get("public_ready") is not False:
        raise ValueError("SelectedRecoverySourceRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "SelectedRecoverySourceRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("SelectedRecoverySourceRecord.report_ready must be false")

    lookup = _candidate_lookup(candidates)
    candidate_id = data["selected_recovery_candidate_id"]
    if candidate_id not in lookup:
        raise ValueError(
            "SelectedRecoverySourceRecord.selected_recovery_candidate_id is unknown: "
            f"{candidate_id}"
        )

    candidate = lookup[candidate_id]
    if data["original_evidence_id"] != candidate.original_evidence_id:
        raise ValueError(
            "SelectedRecoverySourceRecord.original_evidence_id does not match "
            f"candidate {candidate_id}"
        )
    if data["selected_source_url"] != candidate.recovery_source_url:
        raise ValueError(
            "SelectedRecoverySourceRecord.selected_source_url does not match "
            f"candidate {candidate_id}"
        )
    if data["selected_source_type"] != candidate.recovery_source_type:
        raise ValueError(
            "SelectedRecoverySourceRecord.selected_source_type does not match "
            f"candidate {candidate_id}"
        )


def _record_from_dict(data: Dict[str, Any]) -> SelectedRecoverySourceRecord:
    return SelectedRecoverySourceRecord(
        original_evidence_id=str(data.get("original_evidence_id", "")),
        selected_recovery_candidate_id=str(
            data.get("selected_recovery_candidate_id", "")
        ),
        selected_source_url=str(data.get("selected_source_url", "")),
        selected_source_type=str(data.get("selected_source_type", "")),
        selection_reason=str(data.get("selection_reason", "")),
        selection_status=str(data.get("selection_status", "pending_selection")),
        approved_evidence=bool(data.get("approved_evidence", False)),
        public_ready=bool(data.get("public_ready", False)),
        institutional_ready=bool(data.get("institutional_ready", False)),
        report_ready=bool(data.get("report_ready", False)),
        notes=str(data.get("notes", "")),
    )


def validate_selected_recovery_source_set(
    records: List[SelectedRecoverySourceRecord],
    candidates: Optional[List[SourceRecoveryCandidateRecord]] = None,
) -> None:
    lookup_candidates = candidates
    if lookup_candidates is None:
        lookup_candidates = load_source_recovery_candidates()

    selected_by_original_id: Dict[str, str] = {}
    for record in records:
        validate_selected_recovery_source_record(record, lookup_candidates)
        if record.selection_status == "selected_for_content_review":
            if record.original_evidence_id in selected_by_original_id:
                raise ValueError(
                    "Duplicate selected recovery source for original evidence ID: "
                    f"{record.original_evidence_id}"
                )
            selected_by_original_id[record.original_evidence_id] = (
                record.selected_recovery_candidate_id
            )

    missing_original_ids = sorted(
        ALLOWED_ORIGINAL_EVIDENCE_IDS - set(selected_by_original_id)
    )
    if missing_original_ids:
        raise ValueError(
            "Missing selected recovery source for original evidence ID(s): "
            + ", ".join(missing_original_ids)
        )


def load_selected_recovery_sources(
    path: Path = DEFAULT_SELECTED_RECOVERY_SOURCE_PATH,
    evidence_id: Optional[str] = None,
    candidates: Optional[List[SourceRecoveryCandidateRecord]] = None,
) -> List[SelectedRecoverySourceRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_records = data.get("selected_sources")
    else:
        raw_records = data

    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("selected_recovery_sources.json must contain selected_sources")

    records: List[SelectedRecoverySourceRecord] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, dict):
            raise ValueError("Selected recovery source records must be objects")
        records.append(_record_from_dict(raw_record))

    validate_selected_recovery_source_set(records, candidates)

    if evidence_id is not None and evidence_id not in ALLOWED_ORIGINAL_EVIDENCE_IDS:
        raise ValueError(f"Unsupported evidence_id for selected recovery source: {evidence_id}")

    if evidence_id is None:
        return records
    return [record for record in records if record.original_evidence_id == evidence_id]


def group_selected_recovery_sources(
    records: List[SelectedRecoverySourceRecord],
) -> Dict[str, List[SelectedRecoverySourceRecord]]:
    grouped: Dict[str, List[SelectedRecoverySourceRecord]] = {}
    for record in records:
        validate_selected_recovery_source_record(record)
        grouped.setdefault(record.original_evidence_id, []).append(record)
    return grouped


def summarize_selected_recovery_sources(
    records: List[SelectedRecoverySourceRecord],
) -> Dict[str, Any]:
    for record in records:
        validate_selected_recovery_source_record(record)

    return {
        "selected_count": sum(
            1 for record in records if record.selection_status == "selected_for_content_review"
        ),
        "pending_selection_count": sum(
            1 for record in records if record.selection_status == "pending_selection"
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }
