#!/usr/bin/env python3
"""
Real Evidence Packets To Claims v2.

Extracts conservative manual-review claim candidates from real evidence packet
text. This lane does not invent claims, normalize claims, create contradictions,
generate final reports, mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re

from evidence.real_segments_to_evidence_packets import (
    EVIDENCE_ITEM_FIELDS as REAL_PACKET_EVIDENCE_ITEM_FIELDS,
    PACKET_FIELDS as REAL_PACKET_FIELDS,
    validate_packet,
)


DEFAULT_REAL_EVIDENCE_PACKETS = Path(
    "outputs/real_segments_to_evidence_packets/real_evidence_packets.json"
)
DEFAULT_REAL_EVIDENCE_PACKET_SUMMARY = Path(
    "outputs/real_segments_to_evidence_packets/real_evidence_packets_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/real_evidence_packets_to_claims")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_extraction_summary.json"
CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_extracted_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_extraction_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_extraction_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_schema.json"

SCHEMA_VERSION = "real_evidence_packets_to_claims_v2"

DRY_RUN_STATUS = "REAL_CLAIM_EXTRACTION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "REAL_CLAIM_EXTRACTION_CANDIDATE"
PARTIAL_STATUS = "REAL_CLAIM_EXTRACTION_PARTIAL"
REFUSED_STATUS = "REAL_CLAIM_EXTRACTION_REFUSED"

UPSTREAM_STATUSES = (
    "REAL_EVIDENCE_PACKETS_DRY_RUN_VALIDATED",
    "REAL_EVIDENCE_PACKETS_CANDIDATE",
    "REAL_EVIDENCE_PACKETS_PARTIAL",
    "REAL_EVIDENCE_PACKETS_REFUSED",
)

CLAIM_STATUS = "REAL_CLAIM_REQUIRES_MANUAL_REVIEW"

CLAIM_TYPES = (
    "POLICY_STATEMENT",
    "GOVERNMENT_STATUS",
    "PUBLIC_SERVICE_INFORMATION",
    "PROMISE_CANDIDATE",
    "UNKNOWN_CLAIM",
)

CLAIM_FIELDS = (
    "claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "claim_text",
    "claim_type",
    "claim_subject",
    "claim_category",
    "claim_confidence",
    "evidence_anchors",
    "evidence_hashes",
    "packet_root",
    "claim_root",
    "manual_review_required",
    "claim_status",
)

EVIDENCE_ANCHOR_FIELDS = (
    "segment_id",
    "source_reference",
    "timestamp_start",
    "timestamp_end",
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
    "document_reference",
    "document_page_start",
    "document_page_end",
)

EVIDENCE_HASH_FIELDS = (
    "evidence_hash_sha256",
    "segment_metadata_hash",
    "localized_segment_root",
    "packet_hash",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "segment_id",
    "claim_text",
    "refusal_code",
    "refusal_reason",
    "evidence_anchors",
    "evidence_hashes",
    "packet_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_NO_CLAIM_TEXT",
    "REFUSED_MALFORMED_PACKET",
    "REFUSED_MISSING_PACKET_TEXT",
    "REFUSED_MISSING_SOURCE_METADATA",
    "REFUSED_MISSING_ANCHORS",
    "REFUSED_MISSING_HASHES",
)

NAVIGATION_TERMS = {
    "about",
    "accessibility",
    "account",
    "back",
    "contact",
    "copyright",
    "download",
    "email",
    "facebook",
    "faq",
    "feedback",
    "follow",
    "footer",
    "home",
    "login",
    "menu",
    "more",
    "next",
    "privacy",
    "read more",
    "rss",
    "search",
    "share",
    "site map",
    "skip to content",
    "terms",
    "twitter",
    "youtube",
}

BOILERPLATE_PHRASES = (
    "government information portal",
    "the best place to find government services and information",
    "sales of goods and services",
    "communications, media",
    "benefits and payments",
    "education and learning",
    "health and wellness",
    "immigration and civil registration",
)

PROMISE_PATTERN = re.compile(
    r"\b(will|pledge[sd]?|promise[sd]?|commit(?:s|ted|ment)?|deliver(?:s|ed)?|"
    r"create[sd]?|ensure[sd]?|undertake[sn]?|guarantee[sd]?)\b",
    re.IGNORECASE,
)

GOVERNMENT_STATUS_PATTERN = re.compile(
    r"\b(is|are|was|were|serves|serving|appointed|appointment|announced|"
    r"elected|current|president|minister|ministry|official|office|notice|"
    r"status|update)\b",
    re.IGNORECASE,
)

POLICY_PATTERN = re.compile(
    r"\b(policy|programme|program|fund|bill|act|regulation|outbreak|launch(?:ed)?|"
    r"approval|approved|revision|revised|strategy|initiative|scheme|disease|"
    r"development)\b",
    re.IGNORECASE,
)

PUBLIC_SERVICE_PATTERN = re.compile(
    r"\b(apply|register|renew|pay|submit|obtain|report|eligibility|requirements|"
    r"available|service|services|certificate|license|licence|permit|application|"
    r"request|portal|form)\b",
    re.IGNORECASE,
)

DECLARATIVE_VERB_PATTERN = re.compile(
    r"\b(is|are|was|were|has|have|had|serves|serving|provides|offers|requires|"
    r"allows|enables|announces|announced|approves|approved|launches|launched|"
    r"establishes|established|implements|implemented|opened|closed|starts|"
    r"started|ends|ended|appoints|appointed|elects|elected|states|stated)\b",
    re.IGNORECASE,
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


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "real_claim_extraction_only": True,
        "modes": ["dry-run", "extract-claims"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "claim_types": list(CLAIM_TYPES),
        "claim_fields": list(CLAIM_FIELDS),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "evidence_hash_fields": list(EVIDENCE_HASH_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "extraction_rule": (
            "Claim text is copied exactly from packet evidence quote_text. "
            "Generic navigation, headings, menus, boilerplate, and text without "
            "an explicit factual, policy, promise, status, or public-service "
            "statement are refused."
        ),
        "prohibited_outputs": {
            "claims_invented": 0,
            "claims_normalized": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "claim_root": "sha256 over claim excluding claim_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "real_claim_extraction_root": (
                "sha256 over sorted claim roots, sorted refusal roots, and closed flags"
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
        raise ValueError("real claim schema_version changed unexpectedly")
    if schema.get("claim_types") != list(CLAIM_TYPES):
        raise ValueError("real claim types changed unexpectedly")
    if schema.get("claim_fields") != list(CLAIM_FIELDS):
        raise ValueError("real claim fields changed unexpectedly")
    if schema.get("evidence_anchor_fields") != list(EVIDENCE_ANCHOR_FIELDS):
        raise ValueError("real claim evidence anchor fields changed unexpectedly")
    if schema.get("evidence_hash_fields") != list(EVIDENCE_HASH_FIELDS):
        raise ValueError("real claim evidence hash fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("real claim refusal fields changed unexpectedly")


def _load_packets(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("real_evidence_packets.json is missing")
    packets = payload.get("real_evidence_packets")
    if not isinstance(packets, list):
        raise ValueError("real_evidence_packets must be a list")
    return packets


def _validate_upstream_summary(summary: Dict[str, Any], packet_count: int) -> None:
    if not summary:
        raise ValueError("real_evidence_packets_summary.json is missing")
    if summary.get("real_evidence_packet_status") not in UPSTREAM_STATUSES:
        raise ValueError("real evidence packet upstream status is invalid")
    if summary.get("real_evidence_packet_count") != packet_count:
        raise ValueError("real evidence packet count does not match summary")
    for counter_name in (
        "quotes_invented",
        "timestamps_invented",
        "quotes_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(summary):
        raise ValueError("real evidence packet guardrails must remain closed")


def _packet_item(packet: Dict[str, Any]) -> Dict[str, Any]:
    collection = packet.get("evidence_collection", {})
    items = collection.get("evidence_items")
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("real evidence packet must contain exactly one evidence item")
    item = items[0]
    if not isinstance(item, dict):
        raise ValueError("real evidence item must be a dictionary")
    return item


def _packet_for_prior_validation(packet: Dict[str, Any]) -> Dict[str, Any]:
    ordered = {field_name: packet.get(field_name) for field_name in REAL_PACKET_FIELDS}
    collection = dict(ordered.get("evidence_collection") or {})
    items = collection.get("evidence_items")
    if isinstance(items, list):
        collection["evidence_items"] = [
            {field_name: item.get(field_name) for field_name in REAL_PACKET_EVIDENCE_ITEM_FIELDS}
            if isinstance(item, dict)
            else item
            for item in items
        ]
    ordered["evidence_collection"] = collection
    return ordered


def _anchors_from_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    item = _packet_item(packet)
    anchors = {
        "segment_id": item.get("source_reference", ""),
        "source_reference": item.get("source_reference", ""),
        "timestamp_start": item.get("timestamp_start"),
        "timestamp_end": item.get("timestamp_end"),
        "video_timestamp_start": item.get("video_timestamp_start", ""),
        "video_timestamp_end": item.get("video_timestamp_end", ""),
        "audio_timestamp_start": item.get("audio_timestamp_start", ""),
        "audio_timestamp_end": item.get("audio_timestamp_end", ""),
        "transcript_start_line": item.get("transcript_start_line", 0),
        "transcript_end_line": item.get("transcript_end_line", 0),
        "text_line_start": item.get("text_line_start", 0),
        "text_line_end": item.get("text_line_end", 0),
        "text_char_start": item.get("text_char_start", 0),
        "text_char_end": item.get("text_char_end", 0),
        "document_reference": item.get("document_reference", ""),
        "document_page_start": item.get("document_page_start", 0),
        "document_page_end": item.get("document_page_end", 0),
    }
    if tuple(anchors.keys()) != EVIDENCE_ANCHOR_FIELDS:
        raise ValueError("real claim evidence anchors changed unexpectedly")
    return anchors


def _hashes_from_packet(packet: Dict[str, Any]) -> Dict[str, str]:
    item = _packet_item(packet)
    hashes = {
        "evidence_hash_sha256": str(item.get("hash_sha256") or ""),
        "segment_metadata_hash": str(item.get("segment_metadata_hash") or ""),
        "localized_segment_root": str(item.get("localized_segment_root") or ""),
        "packet_hash": str(packet.get("packet_root") or ""),
    }
    if tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("real claim evidence hashes changed unexpectedly")
    return hashes


def _has_line_anchor(anchors: Dict[str, Any]) -> bool:
    start = _safe_int(anchors.get("text_line_start") or anchors.get("transcript_start_line"))
    end = _safe_int(anchors.get("text_line_end") or anchors.get("transcript_end_line"))
    return start > 0 and end >= start


def _has_timestamp_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("timestamp_start")) and bool(anchors.get("timestamp_end"))


def _has_anchor(anchors: Dict[str, Any]) -> bool:
    return _has_line_anchor(anchors) or _has_timestamp_anchor(anchors)


def _validate_packet_for_claims(packet: Dict[str, Any]) -> None:
    validate_packet(_packet_for_prior_validation(packet))
    source_details = packet.get("source_details", {})
    source_ownership = packet.get("source_ownership", {})
    item = _packet_item(packet)
    for field_name in ("packet_id", "packet_root"):
        _require_nonempty_string(packet, field_name, "RealEvidencePacket")
    for field_name in ("source_url", "source_title"):
        _require_nonempty_string(source_details, field_name, "RealEvidencePacket.source_details")
    _require_nonempty_string(source_ownership, "owner_name", "RealEvidencePacket.source_ownership")
    if not _is_public_url(source_details["source_url"]):
        raise ValueError("RealEvidencePacket.source_url must be public HTTP(S)")
    for field_name in ("source_reference", "quote_text", "hash_sha256", "localized_segment_root"):
        _require_nonempty_string(item, field_name, "RealEvidenceItem")
    anchors = _anchors_from_packet(packet)
    hashes = _hashes_from_packet(packet)
    if not _has_anchor(anchors):
        raise ValueError("RealEvidencePacket must preserve a line or timestamp anchor")
    for hash_name, hash_value in hashes.items():
        if not _is_nonzero_hash(hash_value):
            raise ValueError(f"RealEvidencePacket missing preserved {hash_name}")


def _is_url_or_path_like(text: str) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    if stripped.startswith(("/", "#")):
        return True
    if "field_" in lowered or "target_id=" in lowered:
        return True
    if re.fullmatch(r"https?://\S+", lowered):
        return True
    if re.fullmatch(r"[\w./?=&%#:-]+", lowered) and "/" in lowered:
        return True
    return False


def _is_navigation_or_boilerplate(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    if lowered in NAVIGATION_TERMS:
        return True
    if any(phrase in lowered for phrase in BOILERPLATE_PHRASES):
        return True
    if lowered.endswith("services") and _word_count(lowered) <= 5:
        return True
    if "," in lowered and _word_count(lowered) <= 5 and not DECLARATIVE_VERB_PATTERN.search(lowered):
        return True
    return False


def _has_statement_signal(text: str) -> bool:
    if DECLARATIVE_VERB_PATTERN.search(text):
        return True
    if PROMISE_PATTERN.search(text):
        return True
    return False


def _is_heading_without_statement(text: str) -> bool:
    stripped = text.strip()
    if (
        len(stripped) <= 120
        and stripped == stripped.upper()
        and _word_count(stripped) >= 3
        and not re.search(r"[.!?]$", stripped)
    ):
        return True
    if _has_statement_signal(stripped):
        return False
    if not re.search(r"[.!?]", stripped) and _word_count(stripped) <= 8:
        return True
    return False


def _claim_type_for_text(text: str) -> Optional[str]:
    stripped = text.strip()
    if not stripped or _word_count(stripped) < 5:
        return None
    if _is_url_or_path_like(stripped):
        return None
    if _is_navigation_or_boilerplate(stripped):
        return None
    if _is_heading_without_statement(stripped):
        return None
    has_statement = _has_statement_signal(stripped)
    if PROMISE_PATTERN.search(stripped) and has_statement:
        return "PROMISE_CANDIDATE"
    if GOVERNMENT_STATUS_PATTERN.search(stripped) and has_statement:
        return "GOVERNMENT_STATUS"
    if POLICY_PATTERN.search(stripped) and has_statement:
        return "POLICY_STATEMENT"
    if PUBLIC_SERVICE_PATTERN.search(stripped) and has_statement:
        return "PUBLIC_SERVICE_INFORMATION"
    if has_statement and _word_count(stripped) >= 8:
        return "UNKNOWN_CLAIM"
    return None


def _claim_subject_for_type(claim_type: str) -> str:
    return {
        "PROMISE_CANDIDATE": "promise_candidate",
        "GOVERNMENT_STATUS": "government_status",
        "POLICY_STATEMENT": "policy_statement",
        "PUBLIC_SERVICE_INFORMATION": "public_service_information",
        "UNKNOWN_CLAIM": "unknown_claim",
    }[claim_type]


def _claim_confidence_for_type(claim_type: str) -> float:
    return {
        "PROMISE_CANDIDATE": 0.7,
        "GOVERNMENT_STATUS": 0.65,
        "POLICY_STATEMENT": 0.6,
        "PUBLIC_SERVICE_INFORMATION": 0.55,
        "UNKNOWN_CLAIM": 0.45,
    }[claim_type]


def _claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("claim_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_claim(packet: Dict[str, Any], claim_index: int, claim_type: str) -> Dict[str, Any]:
    item = _packet_item(packet)
    claim = {
        "claim_id": f"REAL_CLAIM_{claim_index:04d}",
        "packet_id": packet["packet_id"],
        "source_url": packet["source_details"]["source_url"],
        "source_owner": packet["source_ownership"]["owner_name"],
        "source_title": packet["source_details"]["source_title"],
        "claim_text": item["quote_text"],
        "claim_type": claim_type,
        "claim_subject": _claim_subject_for_type(claim_type),
        "claim_category": "real_evidence_packet_text",
        "claim_confidence": _claim_confidence_for_type(claim_type),
        "evidence_anchors": _anchors_from_packet(packet),
        "evidence_hashes": _hashes_from_packet(packet),
        "packet_root": packet["packet_root"],
        "claim_root": "",
        "manual_review_required": True,
        "claim_status": CLAIM_STATUS,
    }
    claim["claim_root"] = _hash_json(_claim_root_material(claim))
    return claim


def _make_refusal(packet: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    try:
        item = _packet_item(packet)
        anchors = _anchors_from_packet(packet)
        hashes = _hashes_from_packet(packet)
        claim_text = str(item.get("quote_text") or "")
        segment_id = str(item.get("source_reference") or "")
    except ValueError:
        anchors = {field_name: "" for field_name in EVIDENCE_ANCHOR_FIELDS}
        hashes = {field_name: "" for field_name in EVIDENCE_HASH_FIELDS}
        claim_text = ""
        segment_id = ""
    source_details = packet.get("source_details", {}) if isinstance(packet, dict) else {}
    source_ownership = packet.get("source_ownership", {}) if isinstance(packet, dict) else {}
    packet_id = str(packet.get("packet_id") or "UNKNOWN_PACKET") if isinstance(packet, dict) else "UNKNOWN_PACKET"
    refusal = {
        "refusal_id": f"REAL_CLAIM_REFUSAL_{packet_id}",
        "packet_id": packet_id,
        "source_url": str(source_details.get("source_url") or ""),
        "source_owner": str(source_ownership.get("owner_name") or ""),
        "source_title": str(source_details.get("source_title") or ""),
        "segment_id": segment_id,
        "claim_text": claim_text,
        "refusal_code": code,
        "refusal_reason": reason,
        "evidence_anchors": anchors,
        "evidence_hashes": hashes,
        "packet_root": str(packet.get("packet_root") or "") if isinstance(packet, dict) else "",
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_claim(claim: Dict[str, Any], valid_packet_ids: List[str]) -> None:
    if tuple(claim.keys()) != CLAIM_FIELDS:
        raise ValueError("Real claim fields changed unexpectedly")
    for field_name in (
        "claim_id",
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_text",
        "claim_type",
        "claim_subject",
        "claim_category",
        "packet_root",
        "claim_root",
        "claim_status",
    ):
        _require_nonempty_string(claim, field_name, "RealClaim")
    if claim["packet_id"] not in valid_packet_ids:
        raise ValueError(f"RealClaim references unknown packet_id: {claim['packet_id']}")
    if not _is_public_url(claim["source_url"]):
        raise ValueError("RealClaim.source_url must be public HTTP(S)")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError(f"Unsupported real claim_type: {claim['claim_type']}")
    if not isinstance(claim["claim_confidence"], float):
        raise ValueError("RealClaim.claim_confidence must be a float")
    if claim["claim_confidence"] < 0 or claim["claim_confidence"] > 1:
        raise ValueError("RealClaim.claim_confidence must be between 0 and 1")
    if claim["manual_review_required"] is not True:
        raise ValueError("RealClaim.manual_review_required must remain true")
    if claim["claim_status"] != CLAIM_STATUS:
        raise ValueError("RealClaim.claim_status changed unexpectedly")
    anchors = claim.get("evidence_anchors")
    if not isinstance(anchors, dict) or tuple(anchors.keys()) != EVIDENCE_ANCHOR_FIELDS:
        raise ValueError("RealClaim.evidence_anchors fields changed unexpectedly")
    if not _has_anchor(anchors):
        raise ValueError("RealClaim must preserve a line or timestamp anchor")
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("RealClaim.evidence_hashes fields changed unexpectedly")
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("RealClaim.evidence_hashes must preserve non-zero hashes")
    if hashes["packet_hash"] != claim["packet_root"]:
        raise ValueError("RealClaim packet_hash must match packet_root")
    if not _is_nonzero_hash(claim["packet_root"]):
        raise ValueError("RealClaim.packet_root must be non-zero")
    if claim["claim_root"] != _hash_json(_claim_root_material(claim)):
        raise ValueError(f"claim_root mismatch for {claim['claim_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Real claim refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "packet_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RealClaimRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported real claim refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RealClaimRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("RealClaimRefusal guardrails must remain closed")
    anchors = refusal.get("evidence_anchors")
    if not isinstance(anchors, dict) or tuple(anchors.keys()) != EVIDENCE_ANCHOR_FIELDS:
        raise ValueError("RealClaimRefusal.evidence_anchors fields changed unexpectedly")
    hashes = refusal.get("evidence_hashes")
    if not isinstance(hashes, dict) or tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("RealClaimRefusal.evidence_hashes fields changed unexpectedly")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _claim_or_refusal(
    packet: Dict[str, Any],
    claim_index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_packet_for_claims(packet)
    except ValueError as exc:
        return None, _make_refusal(packet, "REFUSED_MALFORMED_PACKET", str(exc))
    item = _packet_item(packet)
    text = str(item.get("quote_text") or "")
    if not text.strip():
        return None, _make_refusal(
            packet,
            "REFUSED_MISSING_PACKET_TEXT",
            "Packet evidence item is missing quote_text.",
        )
    anchors = _anchors_from_packet(packet)
    if not _has_anchor(anchors):
        return None, _make_refusal(
            packet,
            "REFUSED_MISSING_ANCHORS",
            "Packet evidence item is missing preserved line or timestamp anchors.",
        )
    hashes = _hashes_from_packet(packet)
    if any(not _is_nonzero_hash(value) for value in hashes.values()):
        return None, _make_refusal(
            packet,
            "REFUSED_MISSING_HASHES",
            "Packet evidence item is missing preserved hashes.",
        )
    claim_type = _claim_type_for_text(text)
    if claim_type is None:
        return None, _make_refusal(
            packet,
            "REFUSED_NO_CLAIM_TEXT",
            "Packet text is generic, navigational, heading-like, boilerplate, or lacks an explicit claim statement.",
        )
    claim = _make_claim(packet, claim_index, claim_type)
    return claim, None


def _status_for(mode: str, claim_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if claim_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if claim_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    input_packet_count: int,
    claims: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    claim_lines = ["- None"]
    if claims:
        claim_lines = []
        for claim in claims[:20]:
            preview = claim["claim_text"][:160].replace("\n", " ")
            claim_lines.extend(
                [
                    f"- {claim['claim_id']}: {claim['claim_type']}",
                    f"  - Packet: {claim['packet_id']}",
                    f"  - Source: {claim['source_title']}",
                    f"  - URL: {claim['source_url']}",
                    f"  - Text Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            preview = refusal["claim_text"][:120].replace("\n", " ")
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Packet: {refusal['packet_id']}",
                    f"  - Text Preview: {preview}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Real Evidence Packets To Claims v2",
            "",
            "This lane extracts conservative manual-review claim candidates from "
            "real evidence packet text. It refuses generic navigation, headings, "
            "menus, boilerplate, and text without an explicit claim statement. It "
            "does not invent claims, normalize claims, create contradictions, or "
            "generate final reports.",
            "",
            "## Summary",
            f"- real_claim_extraction_status: {status}",
            f"- mode: {mode}",
            f"- input_packet_count: {input_packet_count}",
            f"- real_claim_count: {len(claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- real_claim_extraction_root: {root}",
            "",
            "## First Claims",
            *claim_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Claims Invented: 0",
            "- Claims Normalized: 0",
            "- Contradictions Created: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )


def build_real_evidence_packets_to_claims(
    mode: str = "dry-run",
    packets_path: Path = DEFAULT_REAL_EVIDENCE_PACKETS,
    packet_summary_path: Path = DEFAULT_REAL_EVIDENCE_PACKET_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "extract-claims"):
        raise ValueError("mode must be dry-run or extract-claims")

    packets_payload = _load_json(packets_path)
    packet_summary = _load_json(packet_summary_path)
    packets = _load_packets(packets_payload)
    _validate_upstream_summary(packet_summary, len(packets))

    schema = _schema()
    validate_schema(schema)

    claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_packet_ids = [str(packet.get("packet_id") or "") for packet in packets]
    validated_packet_count = 0
    if mode == "dry-run":
        for packet in packets:
            _validate_packet_for_claims(packet)
            validated_packet_count += 1
    else:
        for packet in packets:
            _validate_packet_for_claims(packet)
            validated_packet_count += 1
            claim, refusal = _claim_or_refusal(packet, len(claims) + 1)
            if claim is not None:
                validate_claim(claim, valid_packet_ids)
                claims.append(claim)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    for claim in claims:
        validate_claim(claim, valid_packet_ids)
    for refusal in refusals:
        validate_refusal(refusal)

    claim_roots = [claim["claim_root"] for claim in claims]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    anchors_preserved_count = len(claims)
    hashes_preserved_count = len(claims)
    root = _hash_json(
        {
            "claim_roots": sorted(claim_roots),
            "refusal_roots": sorted(refusal_roots),
            "claims_invented": 0,
            "claims_normalized": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(claims), len(refusals))
    report = _build_report(status, mode, len(packets), claims, refusals, root)
    summary = {
        "real_claim_extraction_status": status,
        "mode": mode,
        "input_packet_count": len(packets),
        "validated_packet_count": validated_packet_count,
        "real_claim_count": len(claims),
        "refusal_count": len(refusals),
        "anchors_preserved_count": anchors_preserved_count,
        "hashes_preserved_count": hashes_preserved_count,
        "claims_invented": 0,
        "claims_normalized": 0,
        "contradictions_created": 0,
        "final_reports_created": 0,
        "claim_roots": claim_roots,
        "refusal_roots": refusal_roots,
        "real_claim_schema_hash": _hash_json(schema),
        "real_claim_extraction_report_hash": _sha256_text(report),
        "real_claim_extraction_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "contradictions_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("real claim extraction guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CLAIMS_OUTPUT, {"real_extracted_claims": claims})
    _write_json(REFUSALS_OUTPUT, {"real_claim_extraction_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "real_extracted_claims": claims,
        "real_claim_extraction_refusals": refusals,
        "schema": schema,
        "report": report,
    }
