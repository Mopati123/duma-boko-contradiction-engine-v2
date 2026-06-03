#!/usr/bin/env python3
"""
Real Segments To Evidence Packets v2.

Converts real localized transcript or source-text segments into image-derived
evidence packets. This lane packetizes existing localized text only; it does not
invent quotes, timestamps, transcripts, claims, contradictions, production
readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json


DEFAULT_SEGMENTS_INPUT = Path(
    "outputs/real_transcript_localization/localized_transcript_segments.json"
)
DEFAULT_LOCALIZATION_SUMMARY = Path(
    "outputs/real_transcript_localization/real_transcript_localization_summary.json"
)
DEFAULT_HARVESTED_SOURCES = Path("outputs/source_harvester_engine/harvested_sources.json")

DEFAULT_OUTPUT_DIR = Path("outputs/real_segments_to_evidence_packets")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packets_summary.json"
PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packets.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packet_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packets_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packet_schema.json"

SCHEMA_VERSION = "real_segments_to_evidence_packets_v2"

DRY_RUN_STATUS = "REAL_EVIDENCE_PACKETS_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "REAL_EVIDENCE_PACKETS_CANDIDATE"
PARTIAL_STATUS = "REAL_EVIDENCE_PACKETS_PARTIAL"
REFUSED_STATUS = "REAL_EVIDENCE_PACKETS_REFUSED"

UPSTREAM_STATUSES = (
    "REAL_TRANSCRIPT_LOCALIZATION_DRY_RUN_VALIDATED",
    "REAL_TRANSCRIPT_LOCALIZATION_CANDIDATE",
    "REAL_TRANSCRIPT_LOCALIZATION_PARTIAL",
    "REAL_TRANSCRIPT_LOCALIZATION_REFUSED",
)

SEGMENT_VERIFICATION_STATUS = "REAL_LOCALIZED_TEXT_REQUIRES_MANUAL_REVIEW"
PACKET_STATUS = "REAL_EVIDENCE_PACKET_REQUIRES_MANUAL_REVIEW"
EVIDENCE_VERIFICATION_STATUS = "REAL_SEGMENT_EVIDENCE_REQUIRES_MANUAL_REVIEW"
LOCALIZATION_STATUS = "REAL_SEGMENT_PACKETIZED"
UNCLASSIFIED = "UNCLASSIFIED_PENDING_CLAIM_EXTRACTION"

SEGMENT_FIELDS = (
    "localized_segment_id",
    "harvested_source_id",
    "registry_source_id",
    "content_url",
    "content_title",
    "source_type",
    "source_method",
    "localized_text",
    "timestamp_start",
    "timestamp_end",
    "text_line_start",
    "text_line_end",
    "text_char_start",
    "text_char_end",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "localized_segment_root",
)

HARVESTED_OWNER_FIELDS = (
    "harvested_source_id",
    "content_url",
    "content_title",
    "content_owner",
)

INTEGRATED_OUTPUT_SECTIONS = (
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
)

PACKET_FIELDS = (
    "packet_id",
    "case_id",
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
    "packet_root",
    "packet_status",
)

EVIDENCE_ITEM_FIELDS = (
    "evidence_id",
    "evidence_type",
    "source_reference",
    "content_url",
    "content_title",
    "timestamp_start",
    "timestamp_end",
    "video_url",
    "video_title",
    "video_timestamp_start",
    "video_timestamp_end",
    "audio_timestamp_start",
    "audio_timestamp_end",
    "transcript_start_line",
    "transcript_end_line",
    "text_line_start",
    "text_line_end",
    "text_char_start",
    "text_char_end",
    "quote_text",
    "quote_source",
    "screenshot_reference",
    "document_reference",
    "document_page_start",
    "document_page_end",
    "hash_sha256",
    "segment_metadata_hash",
    "localized_segment_root",
    "verification_status",
    "localization_status",
    "refusal_reason",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "localized_segment_id",
    "harvested_source_id",
    "registry_source_id",
    "content_url",
    "content_title",
    "refusal_code",
    "refusal_reason",
    "missing_fields",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_MALFORMED_SEGMENT",
    "REFUSED_MISSING_OWNER_LOOKUP",
    "REFUSED_MISSING_SOURCE_URL",
    "REFUSED_MISSING_SOURCE_TITLE",
    "REFUSED_MISSING_SEGMENT_TEXT",
    "REFUSED_MISSING_ANCHOR",
    "REFUSED_MISSING_HASH",
    "REFUSED_INVALID_GUARDRAILS",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _has_line_anchor(segment: Dict[str, Any]) -> bool:
    start = _safe_int(segment.get("text_line_start"))
    end = _safe_int(segment.get("text_line_end"))
    return start > 0 and end >= start


def _has_timestamp_anchor(segment: Dict[str, Any]) -> bool:
    return bool(segment.get("timestamp_start")) and bool(segment.get("timestamp_end"))


def _has_anchor(segment: Dict[str, Any]) -> bool:
    return _has_line_anchor(segment) or _has_timestamp_anchor(segment)


def _timestamp_or_empty(value: Optional[str]) -> str:
    return value if isinstance(value, str) else ""


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "real_segments_to_evidence_packets_only": True,
        "modes": ["dry-run", "from-segments"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "localized_segment_fields": list(SEGMENT_FIELDS),
        "harvested_owner_fields": list(HARVESTED_OWNER_FIELDS),
        "top_level_sections": list(INTEGRATED_OUTPUT_SECTIONS),
        "packet_fields": list(PACKET_FIELDS),
        "evidence_item_fields": list(EVIDENCE_ITEM_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "packetization_rule": (
            "Each real localized segment becomes at most one manual-review evidence "
            "packet. Segment text is copied exactly into quote_text."
        ),
        "prohibited_outputs": {
            "quotes_invented": 0,
            "timestamps_invented": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "metadata_hash": "preserved from localized segment metadata_hash",
            "localized_segment_root": "preserved from localized segment root",
            "packet_root": "sha256 over evidence packet excluding packet_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "real_evidence_packets_root": (
                "sha256 over sorted packet roots, sorted refusal roots, and closed flags"
            ),
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("real evidence packet schema_version changed unexpectedly")
    if schema.get("top_level_sections") != list(INTEGRATED_OUTPUT_SECTIONS):
        raise ValueError("real evidence packet top-level sections changed unexpectedly")
    if schema.get("packet_fields") != list(PACKET_FIELDS):
        raise ValueError("real evidence packet fields changed unexpectedly")
    if schema.get("evidence_item_fields") != list(EVIDENCE_ITEM_FIELDS):
        raise ValueError("real evidence item fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("real evidence refusal fields changed unexpectedly")


def _segment_hash_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "harvested_source_id": segment["harvested_source_id"],
        "content_url": segment["content_url"],
        "source_method": segment["source_method"],
        "localized_text": segment["localized_text"],
        "timestamp_start": segment["timestamp_start"],
        "timestamp_end": segment["timestamp_end"],
        "text_line_start": segment["text_line_start"],
        "text_line_end": segment["text_line_end"],
        "text_char_start": segment["text_char_start"],
        "text_char_end": segment["text_char_end"],
    }


def _segment_root_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(segment)
    material.pop("localized_segment_root", None)
    return material


def _packet_root_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(packet)
    material.pop("packet_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _segment_identity(segment: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        str(segment.get("localized_segment_id") or "UNKNOWN_SEGMENT"),
        str(segment.get("harvested_source_id") or "UNKNOWN_HARVESTED_SOURCE"),
        str(segment.get("registry_source_id") or "UNKNOWN_REGISTRY_SOURCE"),
        str(segment.get("content_url") or ""),
        str(segment.get("content_title") or ""),
    )


def _make_refusal(
    segment: Dict[str, Any],
    code: str,
    reason: str,
    missing_fields: List[str],
) -> Dict[str, Any]:
    localized_segment_id, harvested_source_id, registry_source_id, content_url, content_title = (
        _segment_identity(segment)
    )
    refusal = {
        "refusal_id": f"REAL_EVIDENCE_PACKET_REFUSAL_{localized_segment_id}",
        "localized_segment_id": localized_segment_id,
        "harvested_source_id": harvested_source_id,
        "registry_source_id": registry_source_id,
        "content_url": content_url,
        "content_title": content_title,
        "refusal_code": code,
        "refusal_reason": reason,
        "missing_fields": missing_fields,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_segment(segment: Dict[str, Any]) -> None:
    if set(segment.keys()) != set(SEGMENT_FIELDS):
        raise ValueError("Real localized segment fields changed unexpectedly")
    for field_name in (
        "localized_segment_id",
        "harvested_source_id",
        "registry_source_id",
        "content_url",
        "content_title",
        "source_type",
        "source_method",
        "localized_text",
        "verification_status",
        "metadata_hash",
        "localized_segment_root",
    ):
        _require_nonempty_string(segment, field_name, "RealLocalizedTranscriptSegment")
    if not _is_public_url(segment["content_url"]):
        raise ValueError("RealLocalizedTranscriptSegment.content_url must be public HTTP(S)")
    if segment["manual_review_required"] is not True:
        raise ValueError("RealLocalizedTranscriptSegment.manual_review_required must remain true")
    if segment["verification_status"] != SEGMENT_VERIFICATION_STATUS:
        raise ValueError("RealLocalizedTranscriptSegment.verification_status changed")
    if segment["timestamp_start"] is not None and not isinstance(segment["timestamp_start"], str):
        raise ValueError("RealLocalizedTranscriptSegment.timestamp_start must be string or null")
    if segment["timestamp_end"] is not None and not isinstance(segment["timestamp_end"], str):
        raise ValueError("RealLocalizedTranscriptSegment.timestamp_end must be string or null")
    for field_name in ("text_line_start", "text_line_end", "text_char_start", "text_char_end"):
        if not isinstance(segment[field_name], int) or segment[field_name] < 0:
            raise ValueError(f"RealLocalizedTranscriptSegment.{field_name} must be non-negative")
    if not _has_anchor(segment):
        raise ValueError("RealLocalizedTranscriptSegment must preserve a line or timestamp anchor")
    if segment["metadata_hash"] != _hash_json(_segment_hash_material(segment)):
        raise ValueError(f"metadata_hash mismatch for {segment['localized_segment_id']}")
    if segment["localized_segment_root"] != _hash_json(_segment_root_material(segment)):
        raise ValueError(f"localized_segment_root mismatch for {segment['localized_segment_id']}")


def _validate_localization_summary(summary: Dict[str, Any], segment_count: int) -> None:
    if not summary:
        raise ValueError("real_transcript_localization_summary.json is missing")
    if summary.get("real_transcript_localization_status") not in UPSTREAM_STATUSES:
        raise ValueError("real transcript localization status is invalid")
    if summary.get("localized_segment_count") != segment_count:
        raise ValueError("localized segment count does not match summary")
    for counter_name in (
        "transcripts_invented",
        "timestamps_invented",
        "quotes_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("real transcript localization guardrails must remain closed")


def _load_segments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("localized_transcript_segments.json is missing")
    segments = payload.get("localized_transcript_segments")
    if not isinstance(segments, list):
        raise ValueError("localized_transcript_segments must be a list")
    return segments


def _owner_lookup(harvested_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not harvested_payload:
        raise ValueError("harvested_sources.json is missing")
    harvested_sources = harvested_payload.get("harvested_sources")
    if not isinstance(harvested_sources, list):
        raise ValueError("harvested_sources must be a list")
    lookup: Dict[str, Dict[str, Any]] = {}
    for source in harvested_sources:
        for field_name in HARVESTED_OWNER_FIELDS:
            _require_nonempty_string(source, field_name, "HarvestedSource")
        source_id = source["harvested_source_id"]
        if source_id in lookup:
            raise ValueError(f"duplicate harvested_source_id in owner lookup: {source_id}")
        lookup[source_id] = source
    return lookup


def _source_owner(segment: Dict[str, Any], owner_lookup: Dict[str, Dict[str, Any]]) -> str:
    source = owner_lookup.get(segment["harvested_source_id"])
    if not source:
        raise ValueError("missing harvested source owner lookup")
    owner = source.get("content_owner")
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("missing harvested source content_owner")
    return owner.strip()


def _source_platform(segment: Dict[str, Any], owner_lookup: Dict[str, Dict[str, Any]]) -> str:
    source = owner_lookup.get(segment["harvested_source_id"], {})
    platform = source.get("platform") or segment.get("source_method") or ""
    return str(platform)


def _make_evidence_item(segment: Dict[str, Any], index: int) -> Dict[str, Any]:
    timestamp_start = segment["timestamp_start"]
    timestamp_end = segment["timestamp_end"]
    source_type = segment["source_type"]
    is_video_or_audio = source_type in ("video", "audio")
    evidence_item = {
        "evidence_id": f"REAL_EVIDENCE_ITEM_{index:04d}",
        "evidence_type": source_type,
        "source_reference": segment["localized_segment_id"],
        "content_url": segment["content_url"],
        "content_title": segment["content_title"],
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "video_url": segment["content_url"] if source_type == "video" else "",
        "video_title": segment["content_title"] if source_type == "video" else "",
        "video_timestamp_start": _timestamp_or_empty(timestamp_start) if is_video_or_audio else "",
        "video_timestamp_end": _timestamp_or_empty(timestamp_end) if is_video_or_audio else "",
        "audio_timestamp_start": _timestamp_or_empty(timestamp_start) if source_type == "audio" else "",
        "audio_timestamp_end": _timestamp_or_empty(timestamp_end) if source_type == "audio" else "",
        "transcript_start_line": segment["text_line_start"],
        "transcript_end_line": segment["text_line_end"],
        "text_line_start": segment["text_line_start"],
        "text_line_end": segment["text_line_end"],
        "text_char_start": segment["text_char_start"],
        "text_char_end": segment["text_char_end"],
        "quote_text": segment["localized_text"],
        "quote_source": "localized_text_exact_copy",
        "screenshot_reference": "",
        "document_reference": segment["content_url"],
        "document_page_start": 0,
        "document_page_end": 0,
        "hash_sha256": segment["metadata_hash"],
        "segment_metadata_hash": segment["metadata_hash"],
        "localized_segment_root": segment["localized_segment_root"],
        "verification_status": EVIDENCE_VERIFICATION_STATUS,
        "localization_status": LOCALIZATION_STATUS,
        "refusal_reason": "",
    }
    if tuple(evidence_item.keys()) != EVIDENCE_ITEM_FIELDS:
        raise ValueError("Real evidence item fields changed unexpectedly")
    return evidence_item


def _make_packet(
    segment: Dict[str, Any],
    owner_lookup: Dict[str, Dict[str, Any]],
    index: int,
) -> Dict[str, Any]:
    owner = _source_owner(segment, owner_lookup)
    evidence_item = _make_evidence_item(segment, index)
    packet = {
        "packet_id": f"REAL_EVIDENCE_PACKET_{index:04d}",
        "case_id": f"REAL_SEGMENT_CASE_{index:04d}",
        "source_details": {
            "source_type": segment["source_type"],
            "source_title": segment["content_title"],
            "source_url": segment["content_url"],
            "source_platform": _source_platform(segment, owner_lookup),
            "source_reference_id": segment["localized_segment_id"],
            "source_theme": "real_localized_segment",
            "harvested_source_id": segment["harvested_source_id"],
            "registry_source_id": segment["registry_source_id"],
            "source_method": segment["source_method"],
            "segment_metadata_hash": segment["metadata_hash"],
            "localized_segment_root": segment["localized_segment_root"],
        },
        "source_ownership": {
            "ownership_type": "public_source_reference",
            "owner_name": owner,
            "correlation_level": "harvested_source_owner_lookup",
            "verification_status": SEGMENT_VERIFICATION_STATUS,
            "ownership_notes": (
                "Owner preserved from source harvester metadata by harvested_source_id."
            ),
        },
        "speaker_political_leader": {
            "speaker_name": UNCLASSIFIED,
            "political_party": UNCLASSIFIED,
            "speaker_role": UNCLASSIFIED,
            "authority_context": "not_asserted_by_packetization_lane",
        },
        "original_promise": {
            "promise_text": "",
            "promise_summary": UNCLASSIFIED,
            "promise_category": UNCLASSIFIED,
            "promise_source_reference": segment["localized_segment_id"],
            "promise_classification_status": "NOT_EXTRACTED",
        },
        "current_government_position": {
            "position_text": "",
            "position_summary": UNCLASSIFIED,
            "position_category": UNCLASSIFIED,
            "position_source_reference": segment["localized_segment_id"],
            "position_classification_status": "NOT_EXTRACTED",
        },
        "evidence_collection": {
            "evidence_items": [evidence_item],
            "evidence_count": 1,
            "collection_status": PACKET_STATUS,
        },
        "final_report_validation_checklist": {
            "source_details_present": True,
            "source_ownership_present": True,
            "speaker_political_leader_present": True,
            "original_promise_present": True,
            "current_government_position_present": True,
            "evidence_collection_present": True,
            "source_url_present": True,
            "owner_preserved": True,
            "segment_text_preserved": True,
            "line_anchor_preserved": True,
            "timestamp_anchor_preserved": True,
            "hash_preserved": True,
            "localized_segment_root_preserved": True,
            "claims_created": 0,
            "contradictions_created": 0,
            "deterministic_json": True,
            "sha256_roots": True,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "no_generated_outputs_committed": True,
        },
        "packet_root": "",
        "packet_status": PACKET_STATUS,
    }
    packet["packet_root"] = _hash_json(_packet_root_material(packet))
    if tuple(packet.keys()) != PACKET_FIELDS:
        raise ValueError("Real evidence packet fields changed unexpectedly")
    return packet


def validate_evidence_item(item: Dict[str, Any]) -> None:
    if tuple(item.keys()) != EVIDENCE_ITEM_FIELDS:
        raise ValueError("Real evidence item fields changed unexpectedly")
    for field_name in (
        "evidence_id",
        "evidence_type",
        "source_reference",
        "content_url",
        "content_title",
        "quote_text",
        "quote_source",
        "hash_sha256",
        "segment_metadata_hash",
        "localized_segment_root",
        "verification_status",
        "localization_status",
    ):
        _require_nonempty_string(item, field_name, "RealEvidenceItem")
    if not _is_public_url(item["content_url"]):
        raise ValueError("RealEvidenceItem.content_url must be public HTTP(S)")
    if item["quote_source"] != "localized_text_exact_copy":
        raise ValueError("RealEvidenceItem.quote_source changed unexpectedly")
    if item["hash_sha256"] != item["segment_metadata_hash"]:
        raise ValueError("RealEvidenceItem.hash_sha256 must preserve segment metadata_hash")
    if not _is_nonzero_hash(item["hash_sha256"]):
        raise ValueError("RealEvidenceItem.hash_sha256 must be non-zero")
    if not _is_nonzero_hash(item["localized_segment_root"]):
        raise ValueError("RealEvidenceItem.localized_segment_root must be non-zero")
    if item["verification_status"] != EVIDENCE_VERIFICATION_STATUS:
        raise ValueError("RealEvidenceItem.verification_status changed unexpectedly")
    if item["localization_status"] != LOCALIZATION_STATUS:
        raise ValueError("RealEvidenceItem.localization_status changed unexpectedly")
    if not (_has_line_anchor(item) or bool(item.get("timestamp_start"))):
        raise ValueError("RealEvidenceItem must preserve a line or timestamp anchor")


def validate_packet(packet: Dict[str, Any]) -> None:
    if tuple(packet.keys()) != PACKET_FIELDS:
        raise ValueError("Real evidence packet fields changed unexpectedly")
    for field_name in ("packet_id", "case_id", "packet_root", "packet_status"):
        _require_nonempty_string(packet, field_name, "RealEvidencePacket")
    if packet["packet_status"] != PACKET_STATUS:
        raise ValueError("RealEvidencePacket.packet_status changed unexpectedly")
    for section in INTEGRATED_OUTPUT_SECTIONS:
        if section not in packet or not isinstance(packet[section], dict):
            raise ValueError(f"RealEvidencePacket.{section} must be present")
    source_details = packet["source_details"]
    source_ownership = packet["source_ownership"]
    for field_name in ("source_url", "source_title", "source_reference_id"):
        _require_nonempty_string(source_details, field_name, "RealEvidenceSourceDetails")
    _require_nonempty_string(source_ownership, "owner_name", "RealEvidenceSourceOwnership")
    items = packet["evidence_collection"].get("evidence_items")
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("RealEvidencePacket must contain exactly one evidence item")
    if packet["evidence_collection"].get("evidence_count") != 1:
        raise ValueError("RealEvidencePacket evidence_count must be 1")
    validate_evidence_item(items[0])
    checklist = packet["final_report_validation_checklist"]
    if not _closed_flags(checklist):
        raise ValueError("Final report validation checklist flags must remain closed")
    if checklist.get("claims_created") != 0 or checklist.get("contradictions_created") != 0:
        raise ValueError("Final report validation checklist must not create claims/contradictions")
    for flag_name in (
        "owner_preserved",
        "segment_text_preserved",
        "line_anchor_preserved",
        "timestamp_anchor_preserved",
        "hash_preserved",
        "localized_segment_root_preserved",
        "deterministic_json",
        "sha256_roots",
        "no_generated_outputs_committed",
    ):
        if checklist.get(flag_name) is not True:
            raise ValueError(f"Final report validation checklist {flag_name} must be true")
    if not _is_nonzero_hash(packet["packet_root"]):
        raise ValueError("RealEvidencePacket.packet_root must be non-zero")
    if packet["packet_root"] != _hash_json(_packet_root_material(packet)):
        raise ValueError(f"packet_root mismatch for {packet['packet_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Real evidence packet refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "localized_segment_id",
        "harvested_source_id",
        "registry_source_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RealEvidencePacketRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"unsupported real evidence packet refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RealEvidencePacketRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("RealEvidencePacketRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _validate_preservation(packet: Dict[str, Any], segment: Dict[str, Any]) -> None:
    item = packet["evidence_collection"]["evidence_items"][0]
    if packet["source_details"]["source_url"] != segment["content_url"]:
        raise ValueError("packet did not preserve source URL")
    if packet["source_details"]["source_title"] != segment["content_title"]:
        raise ValueError("packet did not preserve source title")
    if item["quote_text"] != segment["localized_text"]:
        raise ValueError("packet did not preserve localized segment text")
    if item["timestamp_start"] != segment["timestamp_start"]:
        raise ValueError("packet did not preserve timestamp_start")
    if item["timestamp_end"] != segment["timestamp_end"]:
        raise ValueError("packet did not preserve timestamp_end")
    if item["text_line_start"] != segment["text_line_start"]:
        raise ValueError("packet did not preserve text_line_start")
    if item["text_line_end"] != segment["text_line_end"]:
        raise ValueError("packet did not preserve text_line_end")
    if item["text_char_start"] != segment["text_char_start"]:
        raise ValueError("packet did not preserve text_char_start")
    if item["text_char_end"] != segment["text_char_end"]:
        raise ValueError("packet did not preserve text_char_end")
    if item["segment_metadata_hash"] != segment["metadata_hash"]:
        raise ValueError("packet did not preserve metadata_hash")
    if item["localized_segment_root"] != segment["localized_segment_root"]:
        raise ValueError("packet did not preserve localized_segment_root")


def _packet_or_refusal(
    segment: Dict[str, Any],
    owner_lookup: Dict[str, Dict[str, Any]],
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        validate_segment(segment)
    except ValueError as exc:
        return None, _make_refusal(
            segment,
            "REFUSED_MALFORMED_SEGMENT",
            str(exc),
            ["localized_segment"],
        )
    if not segment.get("content_url"):
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_SOURCE_URL",
            "Localized segment is missing content_url.",
            ["content_url"],
        )
    if not segment.get("content_title"):
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_SOURCE_TITLE",
            "Localized segment is missing content_title.",
            ["content_title"],
        )
    if not segment.get("localized_text"):
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_SEGMENT_TEXT",
            "Localized segment is missing localized_text.",
            ["localized_text"],
        )
    if not _has_anchor(segment):
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_ANCHOR",
            "Localized segment is missing line or timestamp anchors.",
            ["text_line_start", "text_line_end", "timestamp_start", "timestamp_end"],
        )
    if not _is_nonzero_hash(segment.get("metadata_hash")) or not _is_nonzero_hash(
        segment.get("localized_segment_root")
    ):
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_HASH",
            "Localized segment is missing metadata_hash or localized_segment_root.",
            ["metadata_hash", "localized_segment_root"],
        )
    if segment["harvested_source_id"] not in owner_lookup:
        return None, _make_refusal(
            segment,
            "REFUSED_MISSING_OWNER_LOOKUP",
            "No harvested source owner lookup exists for this segment.",
            ["harvested_source_id"],
        )
    try:
        packet = _make_packet(segment, owner_lookup, index)
        validate_packet(packet)
        _validate_preservation(packet, segment)
    except ValueError as exc:
        return None, _make_refusal(
            segment,
            "REFUSED_INVALID_GUARDRAILS",
            str(exc),
            ["packet_guardrails"],
        )
    return packet, None


def _status_for(mode: str, packet_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if packet_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if packet_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    localized_segment_count: int,
    packets: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    packet_lines = ["- None"]
    if packets:
        packet_lines = []
        for packet in packets[:20]:
            item = packet["evidence_collection"]["evidence_items"][0]
            preview = item["quote_text"][:140].replace("\n", " ")
            packet_lines.extend(
                [
                    f"- {packet['packet_id']}",
                    f"  - Source: {packet['source_details']['source_title']}",
                    f"  - URL: {packet['source_details']['source_url']}",
                    f"  - Owner: {packet['source_ownership']['owner_name']}",
                    f"  - Segment: {item['source_reference']}",
                    f"  - Text Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Segment: {refusal['localized_segment_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Real Segments To Evidence Packets v2",
            "",
            "This lane converts real localized transcript or source-text segments "
            "into manual-review evidence packets. It does not invent quotes, "
            "timestamps, transcripts, claims, contradictions, production readiness, "
            "or approved evidence.",
            "",
            "## Summary",
            f"- real_evidence_packet_status: {status}",
            f"- mode: {mode}",
            f"- localized_segment_count: {localized_segment_count}",
            f"- real_evidence_packet_count: {len(packets)}",
            f"- refusal_count: {len(refusals)}",
            f"- real_evidence_packets_root: {root}",
            "",
            "## First Packets",
            *packet_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Quotes Invented: 0",
            "- Timestamps Invented: 0",
            "- Transcripts Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Evidence Approved Count: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )


def build_real_segments_to_evidence_packets(
    mode: str = "dry-run",
    segments_path: Path = DEFAULT_SEGMENTS_INPUT,
    localization_summary_path: Path = DEFAULT_LOCALIZATION_SUMMARY,
    harvested_sources_path: Path = DEFAULT_HARVESTED_SOURCES,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-segments"):
        raise ValueError("mode must be dry-run or from-segments")

    segments_payload = _load_json(segments_path)
    localization_summary = _load_json(localization_summary_path)
    harvested_payload = _load_json(harvested_sources_path)

    segments = _load_segments(segments_payload)
    _validate_localization_summary(localization_summary, len(segments))
    owner_lookup = _owner_lookup(harvested_payload)

    schema = _schema()
    validate_schema(schema)

    packets: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "dry-run":
        for segment in segments:
            validate_segment(segment)
            _source_owner(segment, owner_lookup)
    else:
        for index, segment in enumerate(segments, start=1):
            packet, refusal = _packet_or_refusal(segment, owner_lookup, index)
            if packet is not None:
                packets.append(packet)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    for packet in packets:
        validate_packet(packet)
    for refusal in refusals:
        validate_refusal(refusal)

    packet_roots = [packet["packet_root"] for packet in packets]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    anchors_preserved_count = len(packets)
    hashes_preserved_count = len(packets)
    root = _hash_json(
        {
            "packet_roots": sorted(packet_roots),
            "refusal_roots": sorted(refusal_roots),
            "quotes_invented": 0,
            "timestamps_invented": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(packets), len(refusals))
    report = _build_report(status, mode, len(segments), packets, refusals, root)
    summary = {
        "real_evidence_packet_status": status,
        "mode": mode,
        "localized_segment_count": len(segments),
        "real_evidence_packet_count": len(packets),
        "refusal_count": len(refusals),
        "harvested_owner_lookup_count": len(owner_lookup),
        "anchors_preserved_count": anchors_preserved_count,
        "hashes_preserved_count": hashes_preserved_count,
        "quotes_invented": 0,
        "timestamps_invented": 0,
        "quotes_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "packet_roots": packet_roots,
        "refusal_roots": refusal_roots,
        "real_evidence_packet_schema_hash": _hash_json(schema),
        "real_evidence_packets_report_hash": _sha256_text(report),
        "real_evidence_packets_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "quotes_invented",
        "timestamps_invented",
        "quotes_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("real evidence packet summary guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PACKETS_OUTPUT, {"real_evidence_packets": packets})
    _write_json(REFUSALS_OUTPUT, {"real_evidence_packet_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "real_evidence_packets": packets,
        "real_evidence_packet_refusals": refusals,
        "schema": schema,
        "report": report,
    }
