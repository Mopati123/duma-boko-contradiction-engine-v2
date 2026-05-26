"""
template_update_from_content_review.py - Candidate-only template update lane.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import shutil

from evidence.real_evidence_inputs import validate_real_evidence_input_record
from evidence.source_recovery import load_source_recovery_candidates


DEFAULT_TEMPLATE_UPDATE_OUTPUT_DIR = Path("outputs/template_update_from_content_review")
DEFAULT_TEMPLATE_UPDATE_STATUS_OUTPUT = (
    DEFAULT_TEMPLATE_UPDATE_OUTPUT_DIR / "template_update_from_content_review_status.json"
)
DEFAULT_TEMPLATE_UPDATE_SUMMARY_OUTPUT = (
    DEFAULT_TEMPLATE_UPDATE_OUTPUT_DIR / "template_update_from_content_review_summary.json"
)
DEFAULT_REAL_EVIDENCE_INPUT_DIR = Path("data/real_evidence_inputs")
DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT = Path(
    "outputs/source_content_verification/source_content_verification_status.json"
)
DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT = Path(
    "outputs/health_fallback_source/health_fallback_source_status.json"
)
DEFAULT_CANONICAL_CASE_MODELS_OUTPUT = Path(
    "outputs/canonical_case_models/canonical_case_models.json"
)

REVIEWER = "content-review-template-update-v1"
JOBS_EVIDENCE_ID = "VID_JOBS_001"
HEALTH_EVIDENCE_ID = "VID_HEALTH_001"
JOBS_CANDIDATE_ID = "RECOVERY_VID_JOBS_001_UDC_HOME"
HEALTH_BLOCKED_CANDIDATE_ID = "RECOVERY_VID_HEALTH_001_REUTERS"
HEALTH_FALLBACK_CANDIDATE_ID = "RECOVERY_VID_HEALTH_001_AL_JAZEERA"

TEMPLATE_FIELDS = (
    "evidence_id",
    "case_id",
    "source_url",
    "transcript_text",
    "timestamp_start",
    "timestamp_end",
    "quote_text",
    "speaker",
    "context_summary",
    "case_relevance_note",
    "reviewer",
    "reviewer_notes",
    "verification_status",
)

FORBIDDEN_TEMPLATE_UPDATE_FIELDS = (
    "verified_for_approval_review",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

STATIC_UPDATE_FIELDS = {
    JOBS_EVIDENCE_ID: {
        "source_url": "https://www.udc.org.bw/",
        "speaker": "Duma Boko",
        "context_summary": (
            "Candidate-reviewed official-party source for jobs promise. "
            "Manual review required."
        ),
        "case_relevance_note": (
            "Supports employment/jobs promise review. Candidate-only, not approved "
            "evidence."
        ),
        "reviewer_notes": (
            "Updated from content-review candidate RECOVERY_VID_JOBS_001_UDC_HOME. "
            "Original unavailable YouTube source preserved for audit: "
            "https://www.youtube.com/watch?v=e0MLzB5nGDc. Candidate-only entry "
            "requires manual verification before approval."
        ),
    },
    HEALTH_EVIDENCE_ID: {
        "source_url": (
            "https://www.aljazeera.com/news/2025/8/26/"
            "botswana-declares-public-health-emergency-over-medicine-shortage"
        ),
        "speaker": "Duma Boko",
        "context_summary": (
            "Candidate-reviewed fallback source for health emergency / medicine "
            "shortage. Reuters preferred source remains blocked."
        ),
        "case_relevance_note": (
            "Supports health/medicine shortage review. Candidate-only, not approved "
            "evidence."
        ),
        "reviewer_notes": (
            "Updated from fallback content-review candidate "
            "RECOVERY_VID_HEALTH_001_AL_JAZEERA. Reuters preferred source remains "
            "blocked: https://www.reuters.com/business/healthcare-pharmaceuticals/"
            "botswana-declares-public-health-emergency-clinics-run-out-medicine-"
            "2025-08-25/. Original YouTube source preserved for audit: "
            "https://www.youtube.com/watch?v=ZsxLObyHUYE. Candidate-only entry "
            "requires manual verification before approval."
        ),
    },
}


@dataclass
class TemplateUpdateRecord:
    evidence_id: str
    case_id: str
    template_path: str
    update_status: str
    original_source_url: str
    proposed_source_url: str
    verification_status: str
    changed_fields: List[str]
    would_write_template: bool
    backup_path: str
    diagnostic_notes: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    proposed_template: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _contains_key(value: Any, target_key: str) -> bool:
    if isinstance(value, dict):
        return target_key in value or any(
            _contains_key(item, target_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target_key) for item in value)
    return False


def _load_optional_records(path: Path, record_key: str = "records") -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get(record_key, [])
        if not records and record_key != "case_models":
            records = payload.get("case_models", [])
    elif isinstance(payload, list):
        records = payload
    else:
        return []
    return [record for record in records if isinstance(record, dict)]


def _records_by_evidence_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(record.get("original_evidence_id") or record.get("evidence_id")): record
        for record in records
        if record.get("original_evidence_id") or record.get("evidence_id")
    }


def _case_models_by_case_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(record.get("case_id")): record
        for record in records
        if record.get("case_id")
    }


def load_template_records(
    evidence_id: str = "",
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
) -> List[Tuple[Path, Dict[str, str]]]:
    if evidence_id and evidence_id not in {JOBS_EVIDENCE_ID, HEALTH_EVIDENCE_ID}:
        raise ValueError(f"Unsupported evidence_id for template update: {evidence_id}")

    paths = [
        template_dir / f"{JOBS_EVIDENCE_ID}.template.json",
        template_dir / f"{HEALTH_EVIDENCE_ID}.template.json",
    ]
    if evidence_id:
        paths = [template_dir / f"{evidence_id}.template.json"]

    templates: List[Tuple[Path, Dict[str, str]]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Template must be a JSON object: {path}")
        record = {field: str(data.get(field, "")) for field in TEMPLATE_FIELDS}
        validate_real_evidence_input_record(record)
        templates.append((path, record))
    return templates


def _candidate_failure_status(evidence_id: str, candidate_id: str) -> str:
    for candidate in load_source_recovery_candidates():
        if (
            candidate.original_evidence_id == evidence_id
            and candidate.recovery_candidate_id == candidate_id
        ):
            return candidate.original_failure_status
    return "unknown"


def _diagnostic_notes(
    evidence_id: str,
    source_verification_records: Dict[str, Dict[str, Any]],
    health_fallback_records: Dict[str, Dict[str, Any]],
    canonical_case_models: Dict[str, Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if evidence_id == JOBS_EVIDENCE_ID:
        source_record = source_verification_records.get(evidence_id, {})
        parts.append(f"candidate_id={JOBS_CANDIDATE_ID}")
        parts.append(
            "content_status="
            + str(source_record.get("verification_status", "pending_manual_review"))
        )
        parts.append(
            "original_failure_status="
            + _candidate_failure_status(evidence_id, JOBS_CANDIDATE_ID)
        )
        case_model = canonical_case_models.get("CASE_002", {})
    else:
        fallback_record = health_fallback_records.get(evidence_id, {})
        parts.append(f"blocked_preferred_candidate_id={HEALTH_BLOCKED_CANDIDATE_ID}")
        parts.append(f"fallback_candidate_id={HEALTH_FALLBACK_CANDIDATE_ID}")
        parts.append(
            "fallback_status="
            + str(fallback_record.get("verification_status", "pending_manual_review"))
        )
        parts.append(
            "original_failure_status="
            + _candidate_failure_status(evidence_id, HEALTH_BLOCKED_CANDIDATE_ID)
        )
        case_model = canonical_case_models.get("CASE_006", {})

    if case_model:
        original_promise = case_model.get("original_promise", {})
        if isinstance(original_promise, dict):
            parts.append(
                "canonical_category="
                + str(original_promise.get("promise_category", "pending_manual_review"))
            )
    else:
        parts.append("canonical_case_model=missing_optional_diagnostic")
    return "; ".join(parts)


def build_template_update(
    template_record: Dict[str, str],
    source_verification_records: Optional[Dict[str, Dict[str, Any]]] = None,
    health_fallback_records: Optional[Dict[str, Dict[str, Any]]] = None,
    canonical_case_models: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, str]:
    evidence_id = template_record.get("evidence_id", "")
    if evidence_id not in STATIC_UPDATE_FIELDS:
        raise ValueError(f"Unsupported evidence_id for template update: {evidence_id}")

    updated = dict(template_record)
    for field_name, value in STATIC_UPDATE_FIELDS[evidence_id].items():
        if field_name in updated:
            updated[field_name] = value
    updated["reviewer"] = REVIEWER
    updated["verification_status"] = "entered_pending_review"

    for field_name in ("transcript_text", "timestamp_start", "timestamp_end", "quote_text"):
        updated[field_name] = template_record.get(field_name, "")

    validate_template_update_record(updated)
    return updated


def validate_template_update_record(record: Any) -> None:
    if hasattr(record, "to_dict"):
        data = record.to_dict()
    elif isinstance(record, dict):
        data = record
    else:
        raise ValueError(f"Expected object or dict, got {type(record).__name__}")

    if _contains_key(data, "verified_for_approval_review"):
        raise ValueError("Template update must not contain verified_for_approval_review")
    for field_name in FORBIDDEN_TEMPLATE_UPDATE_FIELDS:
        if data.get(field_name) is True:
            raise ValueError(f"Template update must not set {field_name}=true")

    for value in _string_values(data):
        if value.strip() == "verified_for_approval_review":
            raise ValueError("Template update must not set verified_for_approval_review")

    if not isinstance(data.get("evidence_id"), str) or not data["evidence_id"].strip():
        raise ValueError("Template update evidence_id must be a non-empty string")
    if not isinstance(data.get("source_url"), str) or not data["source_url"].strip():
        raise ValueError("Template update source_url must be a non-empty string")
    if data.get("verification_status") != "entered_pending_review":
        raise ValueError(
            "Template update verification_status must be entered_pending_review"
        )

    validate_real_evidence_input_record(data)
    json.dumps(data)


def ordered_template(record: Dict[str, str]) -> Dict[str, str]:
    return {field: str(record.get(field, "")) for field in TEMPLATE_FIELDS}


def write_template(path: Path, proposed_record: Dict[str, str]) -> str:
    validate_template_update_record(proposed_record)
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    path.write_text(
        json.dumps(ordered_template(proposed_record), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(backup_path)


def write_outputs(
    records: List[TemplateUpdateRecord],
    mode: str,
    output_dir: Path = DEFAULT_TEMPLATE_UPDATE_OUTPUT_DIR,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "template_update_from_content_review_status.json"
    summary_path = output_dir / "template_update_from_content_review_summary.json"
    summary = summarize_template_updates(records, mode)
    summary["status_output"] = str(status_path)
    summary["summary_output"] = str(summary_path)
    status = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": mode,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "records": [record.to_dict() for record in records],
    }
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"status_output": str(status_path), "summary_output": str(summary_path)}


def summarize_template_updates(
    records: List[TemplateUpdateRecord],
    mode: str,
) -> Dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "selected_template_count": len(records),
        "entered_pending_review_count": sum(
            1 for record in records if record.verification_status == "entered_pending_review"
        ),
        "write_count": sum(
            1
            for record in records
            if record.update_status == "updated_template"
        ),
        "backup_count": sum(1 for record in records if record.backup_path),
        "verified_for_approval_review": 0,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "evidence_ids": [record.evidence_id for record in records],
    }


def update_templates_from_content_review(
    evidence_id: str = "",
    write: bool = False,
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    output_dir: Path = DEFAULT_TEMPLATE_UPDATE_OUTPUT_DIR,
    source_verification_path: Path = DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT,
    health_fallback_path: Path = DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT,
    canonical_case_models_path: Path = DEFAULT_CANONICAL_CASE_MODELS_OUTPUT,
) -> Dict[str, Any]:
    source_verification_records = _records_by_evidence_id(
        _load_optional_records(source_verification_path)
    )
    health_fallback_records = _records_by_evidence_id(
        _load_optional_records(health_fallback_path)
    )
    canonical_case_models = _case_models_by_case_id(
        _load_optional_records(canonical_case_models_path, record_key="case_models")
    )
    templates = load_template_records(evidence_id=evidence_id, template_dir=template_dir)

    records: List[TemplateUpdateRecord] = []
    for path, template_record in templates:
        proposed = build_template_update(
            template_record,
            source_verification_records=source_verification_records,
            health_fallback_records=health_fallback_records,
            canonical_case_models=canonical_case_models,
        )
        changed_fields = [
            field
            for field in TEMPLATE_FIELDS
            if template_record.get(field, "") != proposed.get(field, "")
        ]
        backup_path = ""
        update_status = "would_update_template" if changed_fields else "no_changes"
        if write and changed_fields:
            backup_path = write_template(path, proposed)
            update_status = "updated_template"
        records.append(
            TemplateUpdateRecord(
                evidence_id=proposed["evidence_id"],
                case_id=proposed["case_id"],
                template_path=str(path),
                update_status=update_status,
                original_source_url=template_record["source_url"],
                proposed_source_url=proposed["source_url"],
                verification_status=proposed["verification_status"],
                changed_fields=changed_fields,
                would_write_template=bool(write and changed_fields),
                backup_path=backup_path,
                diagnostic_notes=_diagnostic_notes(
                    proposed["evidence_id"],
                    source_verification_records,
                    health_fallback_records,
                    canonical_case_models,
                ),
                approved_evidence=False,
                public_ready=False,
                institutional_ready=False,
                report_ready=False,
                proposed_template=ordered_template(proposed),
            )
        )

    mode = "write" if write else "dry-run"
    outputs = write_outputs(records, mode=mode, output_dir=output_dir)
    summary = summarize_template_updates(records, mode=mode)
    summary.update(outputs)
    summary["records"] = records
    return summary
