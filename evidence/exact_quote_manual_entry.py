"""
exact_quote_manual_entry.py - Human-supplied exact evidence entry gate.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import json
import shutil

from evidence.evidence_location_model import (
    has_exact_value,
    is_placeholder_value,
    validate_no_fake_timestamps_for_text_source,
    validate_no_placeholder_final_evidence,
)
from evidence.real_evidence_inputs import (
    DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    validate_real_evidence_input_record,
)


DEFAULT_MANUAL_ENTRY_OUTPUT_DIR = Path("outputs/exact_quote_manual_entry")
DEFAULT_MANUAL_ENTRY_STATUS_OUTPUT = (
    DEFAULT_MANUAL_ENTRY_OUTPUT_DIR / "exact_quote_manual_entry_status.json"
)
DEFAULT_MANUAL_ENTRY_SUMMARY_OUTPUT = (
    DEFAULT_MANUAL_ENTRY_OUTPUT_DIR / "exact_quote_manual_entry_summary.json"
)

JOBS_EVIDENCE_ID = "VID_JOBS_001"
HEALTH_EVIDENCE_ID = "VID_HEALTH_001"
ALLOWED_EVIDENCE_IDS = {JOBS_EVIDENCE_ID, HEALTH_EVIDENCE_ID}

CURRENT_REVIEW_STATUS = "entered_pending_review"

FORBIDDEN_FIELDS = (
    "verified_for_approval_review",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ENTRY_STATUSES = {
    "accepted",
    "rejected",
    "write_blocked",
    "applied",
}

WRITE_FIELDS_BY_LOCATION_TYPE = {
    "document_reference": (
        "quote_text",
        "excerpt_text",
        "transcript_text",
        "page_reference",
        "section_reference",
        "paragraph_reference",
    ),
    "article_reference": (
        "quote_text",
        "excerpt_text",
        "transcript_text",
        "paragraph_reference",
        "quote_location",
    ),
    "video_timestamp": (
        "quote_text",
        "transcript_text",
        "timestamp_start",
        "timestamp_end",
    ),
}


@dataclass
class ExactQuoteManualEntryRecord:
    evidence_id: str
    entry_path: str
    template_path: str
    entry_status: str
    evidence_location_type: str
    validation_errors: List[str]
    write_blockers: List[str]
    changed_fields: List[str]
    would_write_template: bool
    backup_path: str
    quote_text_filled: bool
    transcript_or_excerpt_filled: bool
    location_fields_filled: bool
    verified_for_approval_review: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    proposed_template: Dict[str, Any]

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


def _contains_key(value: Any, target_key: str) -> bool:
    if isinstance(value, dict):
        return target_key in value or any(
            _contains_key(item, target_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target_key) for item in value)
    return False


def normalize_source_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().rstrip("/")


def load_manual_entry(entry_path: Path) -> Dict[str, Any]:
    data = json.loads(entry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Manual entry must be a JSON object: {entry_path}")
    return data


def load_matching_template(
    evidence_id: str,
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
) -> Tuple[Path, Dict[str, Any]]:
    if evidence_id not in ALLOWED_EVIDENCE_IDS:
        raise ValueError(f"Unsupported manual-entry evidence_id: {evidence_id}")
    path = template_dir / f"{evidence_id}.template.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Template must be a JSON object: {path}")
    validate_real_evidence_input_record(data)
    return path, data


def _reject_forbidden_fields(data: Dict[str, Any]) -> None:
    for field_name in FORBIDDEN_FIELDS:
        if data.get(field_name) is True:
            raise ValueError(
                f"Exact quote manual entry must not set {field_name}=true"
            )
        if _contains_key(data, field_name):
            raise ValueError(
                "Exact quote manual entry must not contain forbidden field: "
                f"{field_name}"
            )


def _require_exact_field(
    data: Dict[str, Any],
    field_name: str,
    errors: List[str],
) -> None:
    if not has_exact_value(data.get(field_name)):
        errors.append(f"{field_name} is required and must not be a placeholder")


def _has_one_exact_field(data: Dict[str, Any], field_names: Tuple[str, ...]) -> bool:
    return any(has_exact_value(data.get(field_name)) for field_name in field_names)


def _attestation_errors(entry: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    attestation = entry.get("attestation")
    if not isinstance(attestation, dict):
        return ["attestation object is required"]
    if attestation.get("human_entered") is not True:
        errors.append("attestation.human_entered must be true")
    if attestation.get("no_fabrication") is not True:
        errors.append("attestation.no_fabrication must be true")
    return errors


MANUAL_ENTRY_PLACEHOLDER_FRAGMENTS = (
    "paste exact",
    "paste longer",
    "paste section",
    "paste paragraph",
    "paste document",
    "paste source",
    "paste quote",
    "paste excerpt",
    "paste transcript",
    "paste location",
    "article body, paragraph x",
    "paragraph x",
)


def _placeholder_errors(entry: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for field_name in (
        "reviewer",
        "review_date",
        "source_url",
        "quote_text",
        "excerpt_text",
        "transcript_text",
        "page_reference",
        "section_reference",
        "paragraph_reference",
        "quote_location",
        "timestamp_start",
        "timestamp_end",
    ):
        value = entry.get(field_name)
        if not isinstance(value, str) or not value.strip():
            continue

        normalized_value = value.strip().casefold()

        if is_placeholder_value(value):
            errors.append(f"{field_name} contains placeholder text")
            continue

        if any(
            placeholder_fragment in normalized_value
            for placeholder_fragment in MANUAL_ENTRY_PLACEHOLDER_FRAGMENTS
        ):
            errors.append(f"{field_name} contains manual-entry placeholder text")

    return errors


def validate_manual_entry_against_template(
    entry: Dict[str, Any],
    template: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []
    try:
        _reject_forbidden_fields(entry)
    except ValueError as exc:
        errors.append(str(exc))

    evidence_id = str(entry.get("evidence_id", ""))
    if evidence_id not in ALLOWED_EVIDENCE_IDS:
        errors.append(f"evidence_id is unsupported: {evidence_id}")
    if evidence_id != str(template.get("evidence_id", "")):
        errors.append("evidence_id does not match target template")

    entry_location_type = str(entry.get("evidence_location_type", ""))
    template_location_type = str(template.get("evidence_location_type", ""))
    if entry_location_type != template_location_type:
        errors.append("evidence_location_type does not match target template")
    if entry_location_type not in WRITE_FIELDS_BY_LOCATION_TYPE:
        errors.append(f"evidence_location_type is unsupported: {entry_location_type}")

    if normalize_source_url(entry.get("source_url")) != normalize_source_url(
        template.get("source_url")
    ):
        errors.append("source_url does not match target template")

    for field_name in ("reviewer", "review_date", "source_url", "quote_text"):
        _require_exact_field(entry, field_name, errors)

    if not _has_one_exact_field(entry, ("excerpt_text", "transcript_text")):
        errors.append("excerpt_text or transcript_text is required")

    if entry_location_type == "document_reference" and not _has_one_exact_field(
        entry,
        ("page_reference", "section_reference", "paragraph_reference"),
    ):
        errors.append(
            "page_reference, section_reference, or paragraph_reference is required"
        )
    elif entry_location_type == "article_reference" and not _has_one_exact_field(
        entry,
        ("paragraph_reference", "quote_location"),
    ):
        errors.append("paragraph_reference or quote_location is required")
    elif entry_location_type == "video_timestamp":
        for field_name in ("timestamp_start", "timestamp_end"):
            _require_exact_field(entry, field_name, errors)

    errors.extend(_attestation_errors(entry))
    errors.extend(_placeholder_errors(entry))

    proposed = build_proposed_template(entry, template, skip_validation=True)
    try:
        validate_no_fake_timestamps_for_text_source(proposed)
        validate_no_placeholder_final_evidence(proposed)
    except ValueError as exc:
        errors.append(str(exc))

    return errors


def build_proposed_template(
    entry: Dict[str, Any],
    template: Dict[str, Any],
    skip_validation: bool = False,
) -> Dict[str, Any]:
    if not skip_validation:
        errors = validate_manual_entry_against_template(entry, template)
        if errors:
            raise ValueError("; ".join(errors))
    location_type = str(template.get("evidence_location_type", ""))
    proposed = dict(template)
    for field_name in WRITE_FIELDS_BY_LOCATION_TYPE.get(location_type, ()):
        value = entry.get(field_name)
        if has_exact_value(value):
            proposed[field_name] = str(value).strip()
    proposed["verification_status"] = CURRENT_REVIEW_STATUS
    return proposed


def _changed_fields(template: Dict[str, Any], proposed: Dict[str, Any]) -> List[str]:
    return [
        field_name
        for field_name in WRITE_FIELDS_BY_LOCATION_TYPE.get(
            str(template.get("evidence_location_type", "")),
            (),
        )
        if str(template.get(field_name, "")) != str(proposed.get(field_name, ""))
    ]


def build_exact_quote_manual_entry_record(
    entry: Dict[str, Any],
    entry_path: Path,
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    require_source_checked: bool = False,
) -> ExactQuoteManualEntryRecord:
    evidence_id = str(entry.get("evidence_id", ""))
    template_path = template_dir / f"{evidence_id}.template.json"
    template: Dict[str, Any] = {}
    validation_errors: List[str] = []
    try:
        template_path, template = load_matching_template(evidence_id, template_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        validation_errors.append(str(exc))

    if template:
        validation_errors.extend(validate_manual_entry_against_template(entry, template))
        proposed = build_proposed_template(entry, template, skip_validation=True)
    else:
        proposed = {}

    write_blockers: List[str] = []
    attestation = entry.get("attestation", {})
    if (
        require_source_checked
        and isinstance(attestation, dict)
        and attestation.get("source_checked") is not True
    ):
        write_blockers.append("attestation.source_checked must be true for write")

    entry_status = "accepted"
    if validation_errors:
        entry_status = "rejected"
    elif write_blockers:
        entry_status = "write_blocked"

    changed_fields = _changed_fields(template, proposed) if template else []
    location_type = str(entry.get("evidence_location_type", ""))
    record = ExactQuoteManualEntryRecord(
        evidence_id=evidence_id,
        entry_path=str(entry_path),
        template_path=str(template_path),
        entry_status=entry_status,
        evidence_location_type=location_type,
        validation_errors=validation_errors,
        write_blockers=write_blockers,
        changed_fields=changed_fields,
        would_write_template=False,
        backup_path="",
        quote_text_filled=has_exact_value(entry.get("quote_text")),
        transcript_or_excerpt_filled=_has_one_exact_field(
            entry,
            ("excerpt_text", "transcript_text"),
        ),
        location_fields_filled=_has_one_exact_field(
            entry,
            (
                "page_reference",
                "section_reference",
                "paragraph_reference",
                "quote_location",
                "timestamp_start",
                "timestamp_end",
            ),
        ),
        verified_for_approval_review=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        proposed_template=proposed,
    )
    validate_exact_quote_manual_entry_record(record)
    return record


def validate_exact_quote_manual_entry_record(record: Any) -> None:
    data = _as_dict(record)
    for field_name in (
        "evidence_id",
        "entry_path",
        "template_path",
        "entry_status",
        "evidence_location_type",
    ):
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"ExactQuoteManualEntryRecord.{field_name} must be non-empty"
            )
    if data["entry_status"] not in ENTRY_STATUSES:
        raise ValueError(
            "ExactQuoteManualEntryRecord.entry_status is unsupported: "
            f"{data['entry_status']}"
        )
    if data.get("verified_for_approval_review") is not False:
        raise ValueError("Exact quote manual entry must not approval-verify")
    if data.get("approved_evidence") is not False:
        raise ValueError("Exact quote manual entry must not approve evidence")
    for field_name in ("public_ready", "institutional_ready", "report_ready"):
        if data.get(field_name) is not False:
            raise ValueError(f"Exact quote manual entry must not set {field_name}")
    if not isinstance(data.get("validation_errors"), list):
        raise ValueError("validation_errors must be a list")
    if not isinstance(data.get("write_blockers"), list):
        raise ValueError("write_blockers must be a list")
    if not isinstance(data.get("changed_fields"), list):
        raise ValueError("changed_fields must be a list")
    if data["entry_status"] == "rejected" and not data["validation_errors"]:
        raise ValueError("Rejected entries require validation_errors")
    if data["entry_status"] == "write_blocked" and not data["write_blockers"]:
        raise ValueError("Write-blocked entries require write_blockers")
    if data["entry_status"] == "applied" and data.get("would_write_template") is not True:
        raise ValueError("Applied entries must set would_write_template=true")
    if data["entry_status"] != "applied" and data.get("would_write_template") is not False:
        raise ValueError("Non-applied entries must not set would_write_template")
    json.dumps(data)


def _write_template(path: Path, proposed: Dict[str, Any]) -> str:
    validate_real_evidence_input_record(proposed)
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    path.write_text(
        json.dumps(proposed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(backup_path)


def summarize_exact_quote_manual_entries(
    records: List[ExactQuoteManualEntryRecord],
    mode: str,
) -> Dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "entry_count": len(records),
        "accepted_count": sum(1 for record in records if record.entry_status == "accepted"),
        "rejected_count": sum(1 for record in records if record.entry_status == "rejected"),
        "write_blocked_count": sum(
            1 for record in records if record.entry_status == "write_blocked"
        ),
        "applied_count": sum(1 for record in records if record.entry_status == "applied"),
        "write_count": sum(1 for record in records if record.backup_path),
        "backup_count": sum(1 for record in records if record.backup_path),
        "quote_text_filled_count": sum(1 for record in records if record.quote_text_filled),
        "transcript_or_excerpt_filled_count": sum(
            1 for record in records if record.transcript_or_excerpt_filled
        ),
        "location_fields_filled_count": sum(
            1 for record in records if record.location_fields_filled
        ),
        "verified_for_approval_review": 0,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "evidence_ids": [record.evidence_id for record in records],
    }


def write_exact_quote_manual_entry_outputs(
    records: List[ExactQuoteManualEntryRecord],
    mode: str,
    output_dir: Path = DEFAULT_MANUAL_ENTRY_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_exact_quote_manual_entry_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / DEFAULT_MANUAL_ENTRY_STATUS_OUTPUT.name
    summary_path = output_dir / DEFAULT_MANUAL_ENTRY_SUMMARY_OUTPUT.name
    summary = summarize_exact_quote_manual_entries(records, mode)
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


def apply_exact_quote_manual_entry(
    entry_path: Path,
    write: bool = False,
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    output_dir: Path = DEFAULT_MANUAL_ENTRY_OUTPUT_DIR,
) -> Dict[str, Any]:
    entry = load_manual_entry(entry_path)
    record = build_exact_quote_manual_entry_record(
        entry,
        entry_path,
        template_dir=template_dir,
        require_source_checked=write,
    )
    if write:
        if record.entry_status != "accepted":
            if record.entry_status == "write_blocked":
                record.entry_status = "write_blocked"
            validate_exact_quote_manual_entry_record(record)
        else:
            backup_path = _write_template(Path(record.template_path), record.proposed_template)
            record.backup_path = backup_path
            record.would_write_template = True
            record.entry_status = "applied"
            validate_exact_quote_manual_entry_record(record)
    mode = "write" if write else "dry-run"
    outputs = write_exact_quote_manual_entry_outputs([record], mode=mode, output_dir=output_dir)
    summary = summarize_exact_quote_manual_entries([record], mode)
    summary.update(outputs)
    summary["records"] = [record]
    return summary
