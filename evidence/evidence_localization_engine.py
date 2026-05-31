#!/usr/bin/env python3
"""
Evidence Localization Engine v2.

Builds deterministic localized sample evidence packets from the v2 Evidence
Packet Engine outputs. The localization values are schema/demo anchors only;
they are not approved evidence and do not mark production, public, or
institutional readiness.
"""

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_PACKET_OUTPUT = Path("outputs/evidence_packet_engine/evidence_packets.json")
DEFAULT_PACKET_SUMMARY = Path(
    "outputs/evidence_packet_engine/evidence_packet_engine_summary.json"
)
DEFAULT_PACKET_SCHEMA = Path("outputs/evidence_packet_engine/evidence_packet_schema.json")

DEFAULT_OUTPUT_DIR = Path("outputs/evidence_localization_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_localization_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_localization_summary.json"
LOCALIZED_PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "localized_evidence_packets.json"
INTEGRATED_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "integrated_output_schema.json"

ENGINE_STATUS = "EVIDENCE_LOCALIZATION_ENGINE_CANDIDATE"
SCHEMA_VERSION = "evidence_localization_engine_v2"
UPSTREAM_SCHEMA_VERSION = "evidence_packet_engine_v2"
LOCALIZATION_STATUS = "sample_localized"

INTEGRATED_OUTPUT_SECTIONS = (
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
)

LOCALIZED_PACKET_FIELDS = (
    "packet_id",
    "case_id",
    "packet_root",
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
    "localized_packet_root",
    "localization_status",
)

LOCALIZED_EVIDENCE_ITEM_FIELDS = (
    "evidence_id",
    "evidence_type",
    "source_reference",
    "video_url",
    "video_title",
    "video_timestamp_start",
    "video_timestamp_end",
    "audio_timestamp_start",
    "audio_timestamp_end",
    "transcript_start_line",
    "transcript_end_line",
    "screenshot_reference",
    "document_reference",
    "document_page_start",
    "document_page_end",
    "quote_text",
    "hash_sha256",
    "verification_status",
    "localization_status",
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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _has_video_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("video_timestamp_start")) and bool(item.get("video_timestamp_end"))


def _has_audio_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("audio_timestamp_start")) and bool(item.get("audio_timestamp_end"))


def _has_transcript_anchor(item: Dict[str, Any]) -> bool:
    return int(item.get("transcript_start_line") or 0) > 0 and int(
        item.get("transcript_end_line") or 0
    ) >= int(item.get("transcript_start_line") or 0)


def _has_screenshot_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("screenshot_reference"))


def _has_document_anchor(item: Dict[str, Any]) -> bool:
    return int(item.get("document_page_start") or 0) > 0 and int(
        item.get("document_page_end") or 0
    ) >= int(item.get("document_page_start") or 0)


def _has_any_anchor(item: Dict[str, Any]) -> bool:
    return any(
        (
            _has_video_anchor(item),
            _has_audio_anchor(item),
            _has_transcript_anchor(item),
            _has_screenshot_anchor(item),
            _has_document_anchor(item),
        )
    )


def _integrated_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "top_level_sections": list(INTEGRATED_OUTPUT_SECTIONS),
        "localized_packet_fields": list(LOCALIZED_PACKET_FIELDS),
        "localized_evidence_item_fields": list(LOCALIZED_EVIDENCE_ITEM_FIELDS),
        "localization_anchor_rule": (
            "Each localized evidence item must include at least one video, audio, "
            "transcript, screenshot, or document-page anchor."
        ),
        "root_rules": {
            "localized_packet_root": (
                "sha256 over localized packet content excluding localized_packet_root"
            ),
            "localization_engine_root": "sha256 over sorted localized packet roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_integrated_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("integrated_output_schema schema_version changed unexpectedly")
    if schema.get("top_level_sections") != list(INTEGRATED_OUTPUT_SECTIONS):
        raise ValueError("integrated_output_schema top_level_sections changed unexpectedly")
    if schema.get("localized_packet_fields") != list(LOCALIZED_PACKET_FIELDS):
        raise ValueError("integrated_output_schema localized_packet_fields changed unexpectedly")
    if schema.get("localized_evidence_item_fields") != list(LOCALIZED_EVIDENCE_ITEM_FIELDS):
        raise ValueError(
            "integrated_output_schema localized_evidence_item_fields changed unexpectedly"
        )


def _validate_upstream(
    packets_payload: Dict[str, Any],
    packet_summary: Dict[str, Any],
    packet_schema: Dict[str, Any],
) -> str:
    if not packets_payload:
        return "BLOCKED_MISSING_EVIDENCE_PACKETS"
    if not packet_summary:
        return "BLOCKED_MISSING_EVIDENCE_PACKET_SUMMARY"
    if not packet_schema:
        return "BLOCKED_MISSING_EVIDENCE_PACKET_SCHEMA"
    if packet_summary.get("evidence_packet_status") != "EVIDENCE_PACKET_ENGINE_CANDIDATE":
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if packet_summary.get("packet_count") != 3 or packet_summary.get("valid_packet_count") != 3:
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if packet_summary.get("invalid_packet_count") != 0:
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if packet_summary.get("evidence_packet_engine_ready") is not True:
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if packet_summary.get("schema_ready") is not True:
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if not _closed_flags(packet_summary):
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SUMMARY"
    if packet_schema.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return "BLOCKED_INVALID_EVIDENCE_PACKET_SCHEMA"
    packets = packets_payload.get("packets")
    if not isinstance(packets, list) or len(packets) != 3:
        return "BLOCKED_INVALID_EVIDENCE_PACKETS"
    for packet in packets:
        for field_name in ("packet_id", "case_id", "packet_root"):
            _require_nonempty_string(packet, field_name, "EvidencePacket")
        if not _is_nonzero_hash(packet.get("packet_root")):
            return "BLOCKED_INVALID_EVIDENCE_PACKETS"
    return ENGINE_STATUS


def _quote_for_packet(packet: Dict[str, Any]) -> str:
    promise_text = str(packet.get("original_promise", {}).get("promise_text") or "").strip()
    position_text = str(packet.get("current_position", {}).get("position_text") or "").strip()
    return promise_text or position_text


def _anchors_for_case(case_id: str) -> Dict[str, Any]:
    anchors = {
        "video_url": "",
        "video_title": "",
        "video_timestamp_start": "",
        "video_timestamp_end": "",
        "audio_timestamp_start": "",
        "audio_timestamp_end": "",
        "transcript_start_line": 0,
        "transcript_end_line": 0,
        "screenshot_reference": "",
        "document_reference": "",
        "document_page_start": 0,
        "document_page_end": 0,
    }
    if case_id == "CASE_SAMPLE_001":
        anchors.update(
            {
                "video_url": "sample://employment-promise",
                "video_title": "Sample employment promise source",
                "video_timestamp_start": "00:12:31",
                "video_timestamp_end": "00:12:48",
                "transcript_start_line": 145,
                "transcript_end_line": 151,
            }
        )
    elif case_id == "CASE_SAMPLE_002":
        anchors.update(
            {
                "video_url": "sample://policy-statement",
                "video_title": "Sample policy statement source",
                "video_timestamp_start": "00:04:10",
                "video_timestamp_end": "00:04:28",
                "transcript_start_line": 55,
                "transcript_end_line": 61,
            }
        )
    elif case_id == "CASE_SAMPLE_003":
        anchors.update(
            {
                "screenshot_reference": "screenshots/case_sample_003_policy_position.png",
                "document_reference": "sample://implementation-status",
                "document_page_start": 3,
                "document_page_end": 4,
            }
        )
    else:
        raise ValueError(f"Unsupported sample case_id for localization: {case_id}")
    return anchors


def _localized_evidence_item(packet: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    anchors = _anchors_for_case(packet["case_id"])
    localized = {
        "evidence_id": item.get("evidence_id", ""),
        "evidence_type": item.get("evidence_type", ""),
        "source_reference": item.get("source_reference", ""),
        "video_url": anchors["video_url"],
        "video_title": anchors["video_title"],
        "video_timestamp_start": anchors["video_timestamp_start"],
        "video_timestamp_end": anchors["video_timestamp_end"],
        "audio_timestamp_start": anchors["audio_timestamp_start"],
        "audio_timestamp_end": anchors["audio_timestamp_end"],
        "transcript_start_line": anchors["transcript_start_line"],
        "transcript_end_line": anchors["transcript_end_line"],
        "screenshot_reference": anchors["screenshot_reference"],
        "document_reference": anchors["document_reference"],
        "document_page_start": anchors["document_page_start"],
        "document_page_end": anchors["document_page_end"],
        "quote_text": _quote_for_packet(packet),
        "hash_sha256": item.get("hash_sha256", ""),
        "verification_status": item.get("verification_status", ""),
        "localization_status": LOCALIZATION_STATUS,
    }
    if tuple(localized.keys()) != LOCALIZED_EVIDENCE_ITEM_FIELDS:
        raise ValueError("Localized evidence item fields changed unexpectedly")
    return localized


def _localized_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    evidence_items = packet.get("evidence_collection", {}).get("evidence_items", [])
    localized_items = [_localized_evidence_item(packet, item) for item in evidence_items]
    localized = {
        "packet_id": packet["packet_id"],
        "case_id": packet["case_id"],
        "packet_root": packet["packet_root"],
        "source_details": packet["source_details"],
        "source_ownership": packet["source_ownership"],
        "speaker_political_leader": packet["speaker"],
        "original_promise": packet["original_promise"],
        "current_government_position": packet["current_position"],
        "evidence_collection": {
            "evidence_items": localized_items,
            "evidence_count": len(localized_items),
            "collection_status": packet.get("evidence_collection", {}).get(
                "collection_status", ""
            ),
            "localization_status": LOCALIZATION_STATUS,
        },
        "final_report_validation_checklist": {
            "source_details_present": True,
            "source_ownership_present": True,
            "speaker_political_leader_present": True,
            "original_promise_present": True,
            "current_government_position_present": True,
            "evidence_collection_present": True,
            "localization_anchors_present": True,
            "deterministic_json": True,
            "sha256_roots": True,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "no_generated_outputs_committed": True,
        },
        "localized_packet_root": "",
        "localization_status": LOCALIZATION_STATUS,
    }
    localized["localized_packet_root"] = _hash_localized_packet(localized)
    return localized


def _hash_localized_packet(packet: Dict[str, Any]) -> str:
    material = dict(packet)
    material.pop("localized_packet_root", None)
    return _hash_json(material)


def validate_localized_evidence_item(item: Dict[str, Any]) -> None:
    if tuple(item.keys()) != LOCALIZED_EVIDENCE_ITEM_FIELDS:
        raise ValueError("Localized evidence item fields changed unexpectedly")
    for field_name in (
        "evidence_id",
        "evidence_type",
        "source_reference",
        "quote_text",
        "hash_sha256",
        "verification_status",
        "localization_status",
    ):
        _require_nonempty_string(item, field_name, "LocalizedEvidenceItem")
    if item["localization_status"] != LOCALIZATION_STATUS:
        raise ValueError("LocalizedEvidenceItem.localization_status changed unexpectedly")
    if not _has_any_anchor(item):
        raise ValueError(f"LocalizedEvidenceItem {item['evidence_id']} has no anchor")
    if item["quote_text"].strip() and not _has_any_anchor(item):
        raise ValueError(f"LocalizedEvidenceItem {item['evidence_id']} quote has no anchor")


def validate_localized_packet(packet: Dict[str, Any]) -> None:
    if tuple(packet.keys()) != LOCALIZED_PACKET_FIELDS:
        raise ValueError("Localized packet fields changed unexpectedly")
    for field_name in ("packet_id", "case_id", "packet_root", "localized_packet_root"):
        _require_nonempty_string(packet, field_name, "LocalizedEvidencePacket")
    if not _is_nonzero_hash(packet["packet_root"]):
        raise ValueError("LocalizedEvidencePacket.packet_root must be preserved")
    if not _is_nonzero_hash(packet["localized_packet_root"]):
        raise ValueError("LocalizedEvidencePacket.localized_packet_root must be non-zero")
    for section in INTEGRATED_OUTPUT_SECTIONS:
        if section not in packet or not isinstance(packet[section], dict):
            raise ValueError(f"LocalizedEvidencePacket.{section} must be present")
    items = packet["evidence_collection"].get("evidence_items")
    if not isinstance(items, list) or not items:
        raise ValueError("Localized evidence_collection.evidence_items must be non-empty")
    for item in items:
        validate_localized_evidence_item(item)
    checklist = packet["final_report_validation_checklist"]
    if not _closed_flags(checklist):
        raise ValueError("Final report validation checklist flags must remain closed")
    if checklist.get("localization_anchors_present") is not True:
        raise ValueError("Final report validation checklist must confirm anchors")
    if packet["localized_packet_root"] != _hash_localized_packet(packet):
        raise ValueError(f"localized_packet_root mismatch for {packet['packet_id']}")


def build_evidence_localization_engine(
    packets_path: Path = DEFAULT_PACKET_OUTPUT,
    summary_path: Path = DEFAULT_PACKET_SUMMARY,
    schema_path: Path = DEFAULT_PACKET_SCHEMA,
) -> Dict[str, Any]:
    packets_payload = _load_json(packets_path)
    packet_summary = _load_json(summary_path)
    packet_schema = _load_json(schema_path)
    status = _validate_upstream(packets_payload, packet_summary, packet_schema)
    schema = _integrated_schema()
    validate_integrated_schema(schema)
    source_packets = packets_payload.get("packets", [])
    localized_packets = [_localized_packet(packet) for packet in source_packets]

    valid_count = 0
    invalid_count = 0
    localized_roots: List[str] = []
    for packet in localized_packets:
        try:
            validate_localized_packet(packet)
            valid_count += 1
        except ValueError:
            invalid_count += 1
            raise
        localized_roots.append(packet["localized_packet_root"])

    ready = status == ENGINE_STATUS and valid_count == 3 and invalid_count == 0
    engine_root = _hash_json({"localized_packet_roots": sorted(localized_roots)})
    schema_hash = _hash_json(schema)
    payload = {
        "records": [
            {
                "evidence_localization_status": status,
                "localized_packet_count": len(localized_packets),
                "valid_localized_packet_count": valid_count,
                "invalid_localized_packet_count": invalid_count,
                "integrated_output_schema_hash": schema_hash,
                "evidence_localization_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "evidence_localization_status": status,
        "localized_packet_count": len(localized_packets),
        "valid_localized_packet_count": valid_count,
        "invalid_localized_packet_count": invalid_count,
        "integrated_output_schema_ready": True,
        "image_structure_encoded": True,
        "localization_ready": ready,
        "localized_packet_roots": localized_roots,
        "integrated_output_schema_hash": schema_hash,
        "evidence_localization_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(LOCALIZED_PACKETS_OUTPUT, {"localized_packets": localized_packets})
    _write_json(INTEGRATED_SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "localized_packets": localized_packets,
        "schema": schema,
    }
