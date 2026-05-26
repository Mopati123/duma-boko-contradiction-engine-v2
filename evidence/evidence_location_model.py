"""
evidence_location_model.py - Location-aware exact evidence validation.
"""

from typing import Any, Dict, Iterable, List


LOCATION_TYPES = {
    "video_timestamp",
    "article_reference",
    "document_reference",
}

LOCATION_FIELDS = (
    "evidence_location_type",
    "excerpt_text",
    "publication_date",
    "paragraph_reference",
    "quote_location",
    "page_reference",
    "section_reference",
)

PLACEHOLDER_VALUES = {
    "",
    "pending_manual_review",
    "pending final manual extraction",
    "pending source collection",
    "tbd",
    "todo",
    "n/a",
    "unknown",
}

BASE_REQUIRED_FIELDS = (
    "evidence_id",
    "case_id",
    "source_url",
    "verification_status",
)


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def is_placeholder_value(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_VALUES


def has_exact_value(value: Any) -> bool:
    return isinstance(value, str) and not is_placeholder_value(value)


def _first_present_field(data: Dict[str, Any], fields: Iterable[str]) -> bool:
    return any(has_exact_value(data.get(field_name)) for field_name in fields)


def _require_known_location_type(data: Dict[str, Any]) -> str:
    location_type = data.get("evidence_location_type")
    if not isinstance(location_type, str) or not location_type.strip():
        raise ValueError("evidence_location_type is required")
    if location_type not in LOCATION_TYPES:
        raise ValueError(f"evidence_location_type is unsupported: {location_type}")
    return location_type


def missing_location_required_fields(
    record: Any,
    require_location_type: bool = True,
) -> List[str]:
    data = _as_dict(record)
    missing: List[str] = []

    for field_name in BASE_REQUIRED_FIELDS:
        if not has_exact_value(data.get(field_name)):
            missing.append(field_name)

    location_type = data.get("evidence_location_type", "")
    if not isinstance(location_type, str) or not location_type.strip():
        if require_location_type:
            missing.append("evidence_location_type")
        return missing
    if location_type not in LOCATION_TYPES:
        missing.append("evidence_location_type")
        return missing

    if location_type == "video_timestamp":
        for field_name in (
            "transcript_text",
            "quote_text",
            "timestamp_start",
            "timestamp_end",
        ):
            if not has_exact_value(data.get(field_name)):
                missing.append(field_name)
    elif location_type == "article_reference":
        if not has_exact_value(data.get("quote_text")):
            missing.append("quote_text")
        if not _first_present_field(data, ("excerpt_text", "transcript_text")):
            missing.append("excerpt_text_or_transcript_text")
        if not _first_present_field(data, ("paragraph_reference", "quote_location")):
            missing.append("paragraph_reference_or_quote_location")
    elif location_type == "document_reference":
        if not has_exact_value(data.get("quote_text")):
            missing.append("quote_text")
        if not _first_present_field(data, ("excerpt_text", "transcript_text")):
            missing.append("excerpt_text_or_transcript_text")
        if not _first_present_field(
            data,
            ("page_reference", "section_reference", "paragraph_reference"),
        ):
            missing.append(
                "page_reference_or_section_reference_or_paragraph_reference"
            )

    return missing


def validate_no_fake_timestamps_for_text_source(record: Any) -> None:
    data = _as_dict(record)
    location_type = data.get("evidence_location_type")
    if location_type in {"article_reference", "document_reference"}:
        if has_exact_value(data.get("timestamp_start")) or has_exact_value(
            data.get("timestamp_end")
        ):
            raise ValueError(
                "article/document evidence must not use video timestamp fields"
            )


def validate_no_placeholder_final_evidence(record: Any) -> None:
    data = _as_dict(record)
    for field_name in (
        "transcript_text",
        "excerpt_text",
        "quote_text",
        "timestamp_start",
        "timestamp_end",
        "paragraph_reference",
        "quote_location",
        "page_reference",
        "section_reference",
    ):
        value = data.get(field_name)
        if isinstance(value, str) and value.strip() and is_placeholder_value(value):
            raise ValueError(
                f"{field_name} contains placeholder text and cannot be final evidence"
            )


def validate_evidence_location_for_promotion(record: Any) -> None:
    data = _as_dict(record)
    _require_known_location_type(data)
    validate_no_fake_timestamps_for_text_source(data)
    validate_no_placeholder_final_evidence(data)

    missing = missing_location_required_fields(data, require_location_type=True)
    if missing:
        raise ValueError("missing required evidence location fields: " + ", ".join(missing))
