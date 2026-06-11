#!/usr/bin/env python3
"""
Temporal Evidence Packet Generation v2.

Converts localized temporal content segments into flat manual-review evidence
packets. This lane preserves existing localized text only; it does not invent
quotes, create timestamps, claims, contradictions, production readiness, or
approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json


DEFAULT_SEGMENTS_INPUT = Path(
    "outputs/temporal_content_localization/localized_temporal_segments.json"
)
DEFAULT_LOCALIZATION_SUMMARY = Path(
    "outputs/temporal_content_localization/temporal_content_localization_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_evidence_packet_generation")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_evidence_packet_summary.json"
PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_evidence_packets.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_evidence_packet_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_evidence_packet_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_evidence_packet_schema.json"

SCHEMA_VERSION = "temporal_evidence_packet_generation_v2"
UPSTREAM_SCHEMA_VERSION = "temporal_content_localization_v2"

DRY_RUN_STATUS = "TEMPORAL_EVIDENCE_PACKET_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_EVIDENCE_PACKET_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_EVIDENCE_PACKET_PARTIAL"
REFUSED_STATUS = "TEMPORAL_EVIDENCE_PACKET_REFUSED"

UPSTREAM_STATUSES = (
    "TEMPORAL_CONTENT_LOCALIZATION_DRY_RUN_VALIDATED",
    "TEMPORAL_CONTENT_LOCALIZATION_CANDIDATE",
    "TEMPORAL_CONTENT_LOCALIZATION_PARTIAL",
    "TEMPORAL_CONTENT_LOCALIZATION_REFUSED",
)
TIME_DIRECTIONS = ("BEFORE", "AFTER")
SOURCE_TYPES = (
    "MANIFESTO",
    "RALLY_VIDEO",
    "INTERVIEW",
    "OFFICIAL_STATEMENT",
    "GOVERNMENT_UPDATE",
    "MINISTRY_UPDATE",
    "BUDGET_DOCUMENT",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
    "PARTY_WEBSITE",
    "SOCIAL_MEDIA_POST",
)

SEGMENT_FIELDS = (
    "localized_segment_id",
    "harvested_temporal_source_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "segment_index",
    "segment_text",
    "segment_sha256",
    "publisher",
    "published_date",
    "topic",
    "manual_review_required",
    "localization_root",
)
PACKET_FIELDS = (
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "harvested_temporal_source_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "publisher",
    "published_date",
    "topic",
    "evidence_text",
    "segment_sha256",
    "localization_root",
    "manual_review_required",
    "packet_hash",
    "packet_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "localized_segment_id",
    "harvested_temporal_source_id",
    "source_id",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_SEGMENT",
    "REFUSED_DUPLICATE_LOCALIZED_SEGMENT_ID",
    "REFUSED_SEGMENT_HASH_MISMATCH",
    "REFUSED_LOCALIZATION_ROOT_MISMATCH",
    "REFUSED_MISSING_LINEAGE",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
    "REFUSED_PACKET_HASH_MISMATCH",
    "REFUSED_PACKET_ROOT_MISMATCH",
)


class TemporalEvidencePacketRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Any) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TemporalEvidencePacketRefusal(code, f"{field_name} must be a non-empty string.")


def _segment_root_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {field: segment[field] for field in SEGMENT_FIELDS if field != "localization_root"}


def _packet_hash_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: packet[field]
        for field in PACKET_FIELDS
        if field not in ("packet_hash", "packet_root")
    }


def _packet_root_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {field: packet[field] for field in PACKET_FIELDS if field != "packet_root"}


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_segment(segment: Dict[str, Any]) -> None:
    if not isinstance(segment, dict) or set(segment.keys()) != set(SEGMENT_FIELDS):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            "Localized temporal segment fields do not match upstream schema.",
        )
    for field_name in SEGMENT_FIELDS:
        if field_name in ("segment_index", "manual_review_required"):
            continue
        _require_nonempty_string(segment, field_name, "REFUSED_MALFORMED_SEGMENT")
    if segment["time_direction"] not in TIME_DIRECTIONS:
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            f"Unsupported time_direction: {segment['time_direction']}.",
        )
    if segment["source_type"] not in SOURCE_TYPES:
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            f"Unsupported source_type: {segment['source_type']}.",
        )
    if not _is_public_url(segment["url"]):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            "Localized temporal segment URL must be public HTTP(S).",
        )
    if not isinstance(segment["segment_index"], int) or segment["segment_index"] < 1:
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            "Localized temporal segment segment_index must be positive.",
        )
    if segment["manual_review_required"] is not True:
        raise TemporalEvidencePacketRefusal(
            "REFUSED_MALFORMED_SEGMENT",
            "Localized temporal segment manual_review_required must remain true.",
        )
    if segment["segment_sha256"] != _sha256_text(segment["segment_text"]):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_SEGMENT_HASH_MISMATCH",
            f"segment_sha256 mismatch for {segment['localized_segment_id']}.",
        )
    if segment["localization_root"] != _hash_json(_segment_root_material(segment)):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_LOCALIZATION_ROOT_MISMATCH",
            f"localization_root mismatch for {segment['localized_segment_id']}.",
        )


def _load_segments(segments_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(segments_path)
    if not isinstance(payload, dict):
        raise ValueError("localized_temporal_segments payload must be a JSON object.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("localized_temporal_segments schema_version is unsupported.")
    segments = payload.get("localized_temporal_segments")
    if not isinstance(segments, list):
        raise ValueError("localized_temporal_segments must contain a list.")
    seen_ids = set()
    for segment in segments:
        _validate_segment(segment)
        segment_id = segment["localized_segment_id"]
        if segment_id in seen_ids:
            raise TemporalEvidencePacketRefusal(
                "REFUSED_DUPLICATE_LOCALIZED_SEGMENT_ID",
                f"Duplicate localized_segment_id: {segment_id}.",
            )
        seen_ids.add(segment_id)
    return segments


def _validate_localization_summary(summary_path: Path, segment_count: int) -> Dict[str, Any]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        raise ValueError("temporal_content_localization_summary.json is missing.")
    if summary.get("temporal_content_localization_status") not in UPSTREAM_STATUSES:
        raise ValueError("Temporal content localization status is invalid.")
    if summary.get("localized_temporal_segment_count") != segment_count:
        raise ValueError("Localized temporal segment count does not match summary.")
    for counter_name in (
        "content_summarized",
        "meaning_inferred",
        "quotes_created",
        "timestamps_created",
        "claims_created",
        "contradictions_created",
        "embeddings_created",
        "sentiment_classifications_created",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise TemporalEvidencePacketRefusal(
                "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
                f"Upstream guardrail {counter_name} is not closed.",
            )
    if summary.get("source_lineage_preserved") is not True:
        raise TemporalEvidencePacketRefusal(
            "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
            "Temporal content localization source lineage was not preserved.",
        )
    if not _closed_flags(summary):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
            "Temporal content localization governance flags must remain closed.",
        )
    return summary


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "temporal_evidence_packet_generation_only": True,
        "modes": ["dry-run", "from-segments"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "localized_temporal_segment_fields": list(SEGMENT_FIELDS),
        "temporal_evidence_packet_fields": list(PACKET_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "packetization_rule": (
            "Each valid localized temporal segment becomes exactly one flat "
            "manual-review temporal evidence packet."
        ),
        "root_rules": {
            "segment_sha256": "preserved from localized temporal segment",
            "localization_root": "preserved from localized temporal segment",
            "packet_hash": "sha256 over packet excluding packet_hash and packet_root",
            "packet_root": "sha256 over packet excluding packet_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
        },
        "guardrails": {
            "approved_evidence": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "embeddings_created": 0,
            "final_reports_created": 0,
            "live_web_access_performed": 0,
            "llm_calls": 0,
            "production_ready": False,
            "quotes_created": 0,
            "timestamps_created": 0,
            "urls_fetched": 0,
        },
    }


def _segment_identity(segment: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(segment.get("localized_segment_id") or "UNKNOWN_LOCALIZED_SEGMENT"),
        str(segment.get("harvested_temporal_source_id") or "UNKNOWN_HARVESTED_TEMPORAL_SOURCE"),
        str(segment.get("source_id") or "UNKNOWN_SOURCE_ID"),
    )


def _make_refusal(segment: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    localized_segment_id, harvested_temporal_source_id, source_id = _segment_identity(segment)
    refusal = {
        "refusal_id": f"TEMPORAL_EVIDENCE_PACKET_REFUSAL_{localized_segment_id}",
        "localized_segment_id": localized_segment_id,
        "harvested_temporal_source_id": harvested_temporal_source_id,
        "source_id": source_id,
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal evidence packet refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TemporalEvidencePacketRefusal.{field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalEvidencePacketRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _make_packet(segment: Dict[str, Any], index: int) -> Dict[str, Any]:
    packet = {
        "temporal_evidence_packet_id": f"TEMPORAL_EVIDENCE_PACKET_{index:06d}",
        "localized_segment_id": segment["localized_segment_id"],
        "harvested_temporal_source_id": segment["harvested_temporal_source_id"],
        "source_id": segment["source_id"],
        "time_direction": segment["time_direction"],
        "source_type": segment["source_type"],
        "url": segment["url"],
        "publisher": segment["publisher"],
        "published_date": segment["published_date"],
        "topic": segment["topic"],
        "evidence_text": segment["segment_text"],
        "segment_sha256": segment["segment_sha256"],
        "localization_root": segment["localization_root"],
        "manual_review_required": True,
        "packet_hash": "",
        "packet_root": "",
    }
    packet["packet_hash"] = _hash_json(_packet_hash_material(packet))
    packet["packet_root"] = _hash_json(_packet_root_material(packet))
    return packet


def validate_packet(packet: Dict[str, Any]) -> None:
    if set(packet.keys()) != set(PACKET_FIELDS):
        raise ValueError("Temporal evidence packet fields changed unexpectedly.")
    for field_name in PACKET_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = packet.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TemporalEvidencePacket.{field_name} must be non-empty.")
    if packet["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalEvidencePacket.time_direction unsupported.")
    if packet["source_type"] not in SOURCE_TYPES:
        raise ValueError("TemporalEvidencePacket.source_type unsupported.")
    if not _is_public_url(packet["url"]):
        raise ValueError("TemporalEvidencePacket.url must be public HTTP(S).")
    if packet["manual_review_required"] is not True:
        raise ValueError("TemporalEvidencePacket.manual_review_required must remain true.")
    if packet["packet_hash"] != _hash_json(_packet_hash_material(packet)):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_PACKET_HASH_MISMATCH",
            f"packet_hash mismatch for {packet['temporal_evidence_packet_id']}.",
        )
    if packet["packet_root"] != _hash_json(_packet_root_material(packet)):
        raise TemporalEvidencePacketRefusal(
            "REFUSED_PACKET_ROOT_MISMATCH",
            f"packet_root mismatch for {packet['temporal_evidence_packet_id']}.",
        )


def _validate_packet_preservation(packet: Dict[str, Any], segment: Dict[str, Any]) -> None:
    for field_name in (
        "localized_segment_id",
        "harvested_temporal_source_id",
        "source_id",
        "time_direction",
        "source_type",
        "url",
        "publisher",
        "published_date",
        "topic",
        "segment_sha256",
        "localization_root",
    ):
        if packet[field_name] != segment[field_name]:
            raise ValueError(f"Temporal evidence packet did not preserve {field_name}.")
    if packet["evidence_text"] != segment["segment_text"]:
        raise ValueError("Temporal evidence packet did not preserve segment_text exactly.")
    if packet["segment_sha256"] != _sha256_text(packet["evidence_text"]):
        raise ValueError("Temporal evidence packet segment_sha256 does not match evidence_text.")


def _packet_or_refusal(segment: Dict[str, Any], index: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_segment(segment)
        for field_name in (
            "localized_segment_id",
            "harvested_temporal_source_id",
            "source_id",
            "url",
            "publisher",
            "published_date",
            "topic",
            "segment_text",
            "segment_sha256",
            "localization_root",
        ):
            _require_nonempty_string(segment, field_name, "REFUSED_MISSING_LINEAGE")
        packet = _make_packet(segment, index)
        validate_packet(packet)
        _validate_packet_preservation(packet, segment)
        return packet, None
    except TemporalEvidencePacketRefusal as exc:
        refusal = _make_refusal(segment, exc.code, exc.reason)
        validate_refusal(refusal)
        return None, refusal
    except ValueError as exc:
        refusal = _make_refusal(segment, "REFUSED_MALFORMED_SEGMENT", str(exc))
        validate_refusal(refusal)
        return None, refusal


def _status_for(mode: str, packet_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if packet_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if packet_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_evidence_packet_root",
        "temporal_evidence_packet_schema_hash",
        "temporal_evidence_packet_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    segment_count: int,
    packets: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    packet_lines = ["- None"]
    if packets:
        packet_lines = []
        for packet in packets[:20]:
            preview = packet["evidence_text"][:160].replace("\n", " ")
            packet_lines.extend(
                [
                    f"- {packet['temporal_evidence_packet_id']}",
                    f"  - Segment: {packet['localized_segment_id']}",
                    f"  - Source: {packet['source_id']}",
                    f"  - Preview: {preview}",
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
            "# Temporal Evidence Packet Generation v2",
            "",
            "This lane packetizes localized temporal segments only. It does not "
            "packetize localization refusals, invent quotes, create timestamps, "
            "claims, contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- temporal_evidence_packet_status: {status}",
            f"- mode: {mode}",
            f"- localized_temporal_segment_count: {segment_count}",
            f"- temporal_evidence_packet_count: {len(packets)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_evidence_packet_root: {root}",
            "",
            "## First Temporal Evidence Packets",
            *packet_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Embeddings Created: 0",
            "- URLs Fetched: 0",
            "- Live Web Access Performed: 0",
            "- LLM Calls: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_evidence_packet_generation(
    mode: str = "dry-run",
    segments_path: Path = DEFAULT_SEGMENTS_INPUT,
    localization_summary_path: Path = DEFAULT_LOCALIZATION_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-segments"):
        raise ValueError("mode must be 'dry-run' or 'from-segments'.")

    segments = _load_segments(segments_path)
    _validate_localization_summary(localization_summary_path, len(segments))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    packets: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "from-segments":
        for segment in segments:
            packet, refusal = _packet_or_refusal(segment, len(packets) + 1)
            if packet is not None:
                packets.append(packet)
            if refusal is not None:
                refusals.append(refusal)

    packet_roots = [packet["packet_root"] for packet in packets]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    status = _status_for(mode, len(packets), len(refusals))
    summary = {
        "temporal_evidence_packet_status": status,
        "mode": mode,
        "localized_temporal_segment_count": len(segments),
        "temporal_evidence_packet_count": len(packets),
        "refusal_count": len(refusals),
        "before_packet_count": sum(1 for packet in packets if packet["time_direction"] == "BEFORE"),
        "after_packet_count": sum(1 for packet in packets if packet["time_direction"] == "AFTER"),
        "source_type_packet_counts": {
            source_type: sum(1 for packet in packets if packet["source_type"] == source_type)
            for source_type in SOURCE_TYPES
        },
        "localized_segment_ids": [segment["localized_segment_id"] for segment in segments],
        "packet_roots": packet_roots,
        "refusal_roots": refusal_roots,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "lineage_preserved": True,
        "segment_sha256_preserved": True,
        "localization_root_preserved": True,
        "evidence_text_exact_copy": True,
        "temporal_evidence_packet_schema_hash": schema_hash,
        "temporal_evidence_packet_report_hash": "",
        "temporal_evidence_packet_root": "",
        "quotes_created": 0,
        "quotes_invented": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "embeddings_created": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "final_reports_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_evidence_packet_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(segments),
        packets,
        refusals,
        summary["temporal_evidence_packet_root"],
    )
    summary["temporal_evidence_packet_report_hash"] = _sha256_text(report)
    summary["temporal_evidence_packet_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(segments),
        packets,
        refusals,
        summary["temporal_evidence_packet_root"],
    )
    if mode == "dry-run" and (packets or refusals):
        raise ValueError("Dry-run must validate localized temporal segments only.")
    for counter_name in (
        "quotes_created",
        "quotes_invented",
        "timestamps_created",
        "claims_created",
        "contradictions_created",
        "embeddings_created",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Temporal evidence packet guardrails must remain closed.")

    packet_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_evidence_packets": packets,
    }
    refusal_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_evidence_packet_refusals": refusals,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / PACKETS_OUTPUT.name, packet_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusal_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "temporal_evidence_packets": packets,
        "temporal_evidence_packet_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_temporal_evidence_packet_generation"]
