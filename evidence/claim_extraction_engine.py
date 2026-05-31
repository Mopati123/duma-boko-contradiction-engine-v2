#!/usr/bin/env python3
"""
Claim Extraction Engine v2.

Builds deterministic sample claims from localized evidence packets. The claims
are schema/demo claims only; they are not approved evidence and they do not mark
production, public, or institutional readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import re


DEFAULT_LOCALIZED_PACKETS = Path(
    "outputs/evidence_localization_engine/localized_evidence_packets.json"
)
DEFAULT_LOCALIZATION_SUMMARY = Path(
    "outputs/evidence_localization_engine/evidence_localization_summary.json"
)
DEFAULT_INTEGRATED_SCHEMA = Path(
    "outputs/evidence_localization_engine/integrated_output_schema.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/claim_extraction_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_extraction_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_extraction_summary.json"
CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "extracted_claims.json"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_schema.json"

ENGINE_STATUS = "CLAIM_EXTRACTION_ENGINE_CANDIDATE"
SCHEMA_VERSION = "claim_extraction_engine_v2"
UPSTREAM_SCHEMA_VERSION = "evidence_localization_engine_v2"
CLAIM_STATUS = "candidate_sample_claim"
EXTRACTION_METHOD = "deterministic_sample_mapping"

SUPPORTED_CLAIM_TYPES = (
    "PROMISE",
    "CURRENT_POSITION",
    "POLICY_ACTION",
    "IMPLEMENTATION_STATUS",
)

CLAIM_FIELDS = (
    "claim_id",
    "case_id",
    "packet_id",
    "claim_type",
    "claim_category",
    "claim_subject",
    "claim_action",
    "claim_target",
    "claim_timeframe",
    "claim_text",
    "normalized_claim_text",
    "speaker_name",
    "speaker_party",
    "source_type",
    "source_reference",
    "evidence_anchors",
    "evidence_hashes",
    "confidence_score",
    "extraction_method",
    "claim_status",
    "claim_root",
)

EVIDENCE_ANCHOR_FIELDS = (
    "video_timestamp_start",
    "video_timestamp_end",
    "transcript_start_line",
    "transcript_end_line",
    "screenshot_reference",
    "document_page_start",
    "document_page_end",
    "source_reference",
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

CLAIM_MAPPING = {
    "CASE_SAMPLE_001": {
        "claim_id": "CLAIM_SAMPLE_001",
        "claim_type": "PROMISE",
        "claim_category": "EMPLOYMENT",
        "claim_subject": "employment",
        "claim_action": "CREATE",
        "claim_target": "100000 jobs",
        "claim_timeframe": "5 years",
    },
    "CASE_SAMPLE_002": {
        "claim_id": "CLAIM_SAMPLE_002",
        "claim_type": "CURRENT_POSITION",
        "claim_category": "EMPLOYMENT",
        "claim_subject": "employment programme",
        "claim_action": "STATE_POSITION",
        "claim_target": "employment programme status",
        "claim_timeframe": "",
    },
    "CASE_SAMPLE_003": {
        "claim_id": "CLAIM_SAMPLE_003",
        "claim_type": "IMPLEMENTATION_STATUS",
        "claim_category": "POLICY_IMPLEMENTATION",
        "claim_subject": "policy implementation",
        "claim_action": "DOCUMENT_STATUS",
        "claim_target": "policy implementation evidence",
        "claim_timeframe": "",
    },
}


@dataclass
class Claim:
    claim_id: str
    case_id: str
    packet_id: str
    claim_type: str
    claim_category: str
    claim_subject: str
    claim_action: str
    claim_target: str
    claim_timeframe: str
    claim_text: str
    normalized_claim_text: str
    speaker_name: str
    speaker_party: str
    source_type: str
    source_reference: str
    evidence_anchors: Dict[str, Any]
    evidence_hashes: List[str]
    confidence_score: float
    extraction_method: str
    claim_status: str
    claim_root: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


def _normalize_claim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _has_video_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("video_timestamp_start")) and bool(
        anchors.get("video_timestamp_end")
    )


def _has_transcript_anchor(anchors: Dict[str, Any]) -> bool:
    start = int(anchors.get("transcript_start_line") or 0)
    end = int(anchors.get("transcript_end_line") or 0)
    return start > 0 and end >= start


def _has_screenshot_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("screenshot_reference"))


def _has_document_anchor(anchors: Dict[str, Any]) -> bool:
    start = int(anchors.get("document_page_start") or 0)
    end = int(anchors.get("document_page_end") or 0)
    return start > 0 and end >= start


def _has_forensic_anchor(anchors: Dict[str, Any]) -> bool:
    return any(
        (
            _has_video_anchor(anchors),
            _has_transcript_anchor(anchors),
            _has_screenshot_anchor(anchors),
            _has_document_anchor(anchors),
        )
    )


def _claim_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "supported_claim_types": list(SUPPORTED_CLAIM_TYPES),
        "claim_fields": list(CLAIM_FIELDS),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "extraction_method": EXTRACTION_METHOD,
        "claim_status": CLAIM_STATUS,
        "root_rules": {
            "claim_root": "sha256 over claim content excluding claim_root",
            "claim_extraction_engine_root": "sha256 over sorted claim roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_claim_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("claim_schema schema_version changed unexpectedly")
    if schema.get("supported_claim_types") != list(SUPPORTED_CLAIM_TYPES):
        raise ValueError("claim_schema supported_claim_types changed unexpectedly")
    if schema.get("claim_fields") != list(CLAIM_FIELDS):
        raise ValueError("claim_schema claim_fields changed unexpectedly")
    if schema.get("evidence_anchor_fields") != list(EVIDENCE_ANCHOR_FIELDS):
        raise ValueError("claim_schema evidence_anchor_fields changed unexpectedly")


def _validate_upstream(
    localized_payload: Dict[str, Any],
    localization_summary: Dict[str, Any],
    integrated_schema: Dict[str, Any],
) -> str:
    if not localized_payload:
        return "BLOCKED_MISSING_LOCALIZED_EVIDENCE_PACKETS"
    if not localization_summary:
        return "BLOCKED_MISSING_EVIDENCE_LOCALIZATION_SUMMARY"
    if not integrated_schema:
        return "BLOCKED_MISSING_INTEGRATED_OUTPUT_SCHEMA"
    if (
        localization_summary.get("evidence_localization_status")
        != "EVIDENCE_LOCALIZATION_ENGINE_CANDIDATE"
    ):
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if localization_summary.get("localized_packet_count") != 3:
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if localization_summary.get("valid_localized_packet_count") != 3:
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if localization_summary.get("invalid_localized_packet_count") != 0:
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if localization_summary.get("image_structure_encoded") is not True:
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if localization_summary.get("localization_ready") is not True:
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if not _is_nonzero_hash(localization_summary.get("evidence_localization_engine_root")):
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if not _closed_flags(localization_summary):
        return "BLOCKED_INVALID_EVIDENCE_LOCALIZATION_SUMMARY"
    if integrated_schema.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return "BLOCKED_INVALID_INTEGRATED_OUTPUT_SCHEMA"
    if integrated_schema.get("top_level_sections") != list(INTEGRATED_OUTPUT_SECTIONS):
        return "BLOCKED_INVALID_INTEGRATED_OUTPUT_SCHEMA"

    packets = localized_payload.get("localized_packets")
    if not isinstance(packets, list) or len(packets) != 3:
        return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
    try:
        for packet in packets:
            for field_name in ("case_id", "packet_id", "packet_root", "localized_packet_root"):
                _require_nonempty_string(packet, field_name, "LocalizedEvidencePacket")
            if not _is_nonzero_hash(packet.get("packet_root")):
                return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
            if not _is_nonzero_hash(packet.get("localized_packet_root")):
                return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
            for section in INTEGRATED_OUTPUT_SECTIONS:
                if section not in packet or not isinstance(packet[section], dict):
                    return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
            items = packet["evidence_collection"].get("evidence_items")
            if not isinstance(items, list) or not items:
                return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
            for item in items:
                for field_name in (
                    "source_reference",
                    "quote_text",
                    "hash_sha256",
                    "verification_status",
                ):
                    _require_nonempty_string(item, field_name, "LocalizedEvidenceItem")
                anchors = _anchors_from_item(item)
                if not _has_forensic_anchor(anchors):
                    return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
    except (TypeError, ValueError):
        return "BLOCKED_INVALID_LOCALIZED_EVIDENCE_PACKETS"
    return ENGINE_STATUS


def _anchors_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "video_timestamp_start": item.get("video_timestamp_start", ""),
        "video_timestamp_end": item.get("video_timestamp_end", ""),
        "transcript_start_line": item.get("transcript_start_line", 0),
        "transcript_end_line": item.get("transcript_end_line", 0),
        "screenshot_reference": item.get("screenshot_reference", ""),
        "document_page_start": item.get("document_page_start", 0),
        "document_page_end": item.get("document_page_end", 0),
        "source_reference": item.get("source_reference", ""),
    }


def _claim_root_material(claim: Claim) -> Dict[str, Any]:
    data = claim.to_dict()
    data.pop("claim_root", None)
    return data


def _assign_claim_root(claim: Claim) -> Claim:
    claim.claim_root = _hash_json(_claim_root_material(claim))
    return claim


def _claim_for_packet(packet: Dict[str, Any]) -> Claim:
    case_id = packet["case_id"]
    if case_id not in CLAIM_MAPPING:
        raise ValueError(f"Unsupported sample case_id for claim extraction: {case_id}")
    mapping = CLAIM_MAPPING[case_id]
    evidence_items = packet["evidence_collection"]["evidence_items"]
    first_item = evidence_items[0]
    claim_text = first_item["quote_text"]
    evidence_hashes = [item["hash_sha256"] for item in evidence_items]
    source_references = [item["source_reference"] for item in evidence_items]
    source_reference = source_references[0]
    claim = Claim(
        claim_id=mapping["claim_id"],
        case_id=case_id,
        packet_id=packet["packet_id"],
        claim_type=mapping["claim_type"],
        claim_category=mapping["claim_category"],
        claim_subject=mapping["claim_subject"],
        claim_action=mapping["claim_action"],
        claim_target=mapping["claim_target"],
        claim_timeframe=mapping["claim_timeframe"],
        claim_text=claim_text,
        normalized_claim_text=_normalize_claim_text(claim_text),
        speaker_name=packet["speaker_political_leader"].get("speaker_name", ""),
        speaker_party=packet["speaker_political_leader"].get("political_party", ""),
        source_type=packet["source_details"].get("source_type", ""),
        source_reference=source_reference,
        evidence_anchors=_anchors_from_item(first_item),
        evidence_hashes=evidence_hashes,
        confidence_score=1.0,
        extraction_method=EXTRACTION_METHOD,
        claim_status=CLAIM_STATUS,
        claim_root="",
    )
    return _assign_claim_root(claim)


def validate_claim(claim: Any, valid_packet_ids: List[str]) -> None:
    data = claim.to_dict() if hasattr(claim, "to_dict") else claim
    if not isinstance(data, dict):
        raise ValueError("Claim must be a dictionary-like value")
    if tuple(data.keys()) != CLAIM_FIELDS:
        raise ValueError("Claim fields changed unexpectedly")
    for field_name in (
        "claim_id",
        "case_id",
        "packet_id",
        "claim_type",
        "claim_category",
        "claim_subject",
        "claim_action",
        "claim_target",
        "claim_text",
        "normalized_claim_text",
        "speaker_name",
        "speaker_party",
        "source_type",
        "source_reference",
        "extraction_method",
        "claim_status",
        "claim_root",
    ):
        _require_nonempty_string(data, field_name, "Claim")
    if data["packet_id"] not in valid_packet_ids:
        raise ValueError(f"Claim references unknown packet_id: {data['packet_id']}")
    if data["claim_type"] not in SUPPORTED_CLAIM_TYPES:
        raise ValueError(f"Unsupported claim_type: {data['claim_type']}")
    if data["extraction_method"] != EXTRACTION_METHOD:
        raise ValueError("Claim.extraction_method changed unexpectedly")
    if data["claim_status"] != CLAIM_STATUS:
        raise ValueError("Claim.claim_status changed unexpectedly")
    if data["confidence_score"] != 1.0:
        raise ValueError("Claim.confidence_score must be deterministic 1.0")
    anchors = data.get("evidence_anchors")
    if not isinstance(anchors, dict):
        raise ValueError("Claim.evidence_anchors must be a dictionary")
    if tuple(anchors.keys()) != EVIDENCE_ANCHOR_FIELDS:
        raise ValueError("Claim.evidence_anchors fields changed unexpectedly")
    if not _has_forensic_anchor(anchors):
        raise ValueError(f"Claim {data['claim_id']} has no forensic anchor")
    evidence_hashes = data.get("evidence_hashes")
    if not isinstance(evidence_hashes, list) or not evidence_hashes:
        raise ValueError(f"Claim {data['claim_id']} has no evidence hashes")
    for evidence_hash in evidence_hashes:
        if not _is_nonzero_hash(evidence_hash):
            raise ValueError(f"Claim {data['claim_id']} has an invalid evidence hash")
    if not _is_nonzero_hash(data["claim_root"]):
        raise ValueError(f"Claim {data['claim_id']} has an invalid claim_root")
    expected_root = _hash_json({key: value for key, value in data.items() if key != "claim_root"})
    if data["claim_root"] != expected_root:
        raise ValueError(f"Claim.claim_root mismatch for {data['claim_id']}")


def build_claim_extraction_engine(
    localized_packets_path: Path = DEFAULT_LOCALIZED_PACKETS,
    localization_summary_path: Path = DEFAULT_LOCALIZATION_SUMMARY,
    integrated_schema_path: Path = DEFAULT_INTEGRATED_SCHEMA,
) -> Dict[str, Any]:
    localized_payload = _load_json(localized_packets_path)
    localization_summary = _load_json(localization_summary_path)
    integrated_schema = _load_json(integrated_schema_path)
    status = _validate_upstream(localized_payload, localization_summary, integrated_schema)
    schema = _claim_schema()
    validate_claim_schema(schema)

    localized_packets = localized_payload.get("localized_packets", [])
    claims = [_claim_for_packet(packet) for packet in localized_packets]
    claim_dicts = [claim.to_dict() for claim in claims]
    valid_packet_ids = [packet.get("packet_id", "") for packet in localized_packets]

    valid_count = 0
    invalid_count = 0
    claim_roots: List[str] = []
    for claim in claim_dicts:
        try:
            validate_claim(claim, valid_packet_ids)
            valid_count += 1
        except ValueError:
            invalid_count += 1
            raise
        claim_roots.append(claim["claim_root"])

    packet_ids_with_claims = {claim["packet_id"] for claim in claim_dicts}
    if set(valid_packet_ids) != packet_ids_with_claims:
        raise ValueError("Every localized packet must produce exactly one sample claim")

    ready = status == ENGINE_STATUS and valid_count == 3 and invalid_count == 0
    engine_root = _hash_json({"claim_roots": sorted(claim_roots)})
    schema_hash = _hash_json(schema)
    payload = {
        "records": [
            {
                "claim_extraction_status": status,
                "localized_packet_count": len(localized_packets),
                "claim_count": len(claim_dicts),
                "valid_claim_count": valid_count,
                "invalid_claim_count": invalid_count,
                "claim_schema_hash": schema_hash,
                "claim_extraction_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "claim_extraction_status": status,
        "localized_packet_count": len(localized_packets),
        "claim_count": len(claim_dicts),
        "valid_claim_count": valid_count,
        "invalid_claim_count": invalid_count,
        "claim_schema_ready": True,
        "claim_extraction_ready": ready,
        "claim_roots": claim_roots,
        "claim_schema_hash": schema_hash,
        "claim_extraction_engine_root": engine_root,
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
    _write_json(CLAIMS_OUTPUT, {"claims": claim_dicts})
    _write_json(SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "claims": claim_dicts,
        "schema": schema,
    }
