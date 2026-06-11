#!/usr/bin/env python3
"""
Temporal Claim Extraction v2.

Extracts conservative manual-review temporal claim candidates from flat temporal
evidence packet text. This lane does not invent claims, normalize claims, create
embeddings, create contradictions, generate final reports, mark production
readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re


DEFAULT_TEMPORAL_EVIDENCE_PACKETS = Path(
    "outputs/temporal_evidence_packet_generation/temporal_evidence_packets.json"
)
DEFAULT_TEMPORAL_EVIDENCE_PACKET_SUMMARY = Path(
    "outputs/temporal_evidence_packet_generation/temporal_evidence_packet_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_claim_extraction")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_extraction_summary.json"
CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_extracted_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_extraction_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_extraction_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_schema.json"

SCHEMA_VERSION = "temporal_claim_extraction_v2"
UPSTREAM_SCHEMA_VERSION = "temporal_evidence_packet_generation_v2"

DRY_RUN_STATUS = "TEMPORAL_CLAIM_EXTRACTION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_CLAIM_EXTRACTION_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_CLAIM_EXTRACTION_PARTIAL"
REFUSED_STATUS = "TEMPORAL_CLAIM_EXTRACTION_REFUSED"

UPSTREAM_STATUSES = (
    "TEMPORAL_EVIDENCE_PACKET_DRY_RUN_VALIDATED",
    "TEMPORAL_EVIDENCE_PACKET_CANDIDATE",
    "TEMPORAL_EVIDENCE_PACKET_PARTIAL",
    "TEMPORAL_EVIDENCE_PACKET_REFUSED",
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
CLAIM_TYPES = (
    "PROMISE_CANDIDATE",
    "POLICY_STATEMENT",
    "BIOGRAPHICAL_STATEMENT",
    "PUBLIC_STATUS",
    "UNKNOWN_CLAIM",
)
CLAIM_FIELDS = (
    "temporal_claim_id",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "publisher",
    "topic",
    "claim_text",
    "claim_type",
    "claim_category",
    "claim_confidence",
    "evidence_hashes",
    "packet_root",
    "manual_review_required",
    "claim_root",
)
EVIDENCE_HASH_FIELDS = (
    "segment_sha256",
    "localization_root",
    "packet_hash",
    "packet_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "url",
    "claim_text",
    "refusal_code",
    "refusal_reason",
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
    "REFUSED_EMPTY_TEXT",
    "REFUSED_NAVIGATION_OR_BOILERPLATE",
    "REFUSED_NO_EXPLICIT_CLAIM",
    "REFUSED_MALFORMED_PACKET",
    "REFUSED_HASH_OR_ROOT_MISMATCH",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
)

NAVIGATION_TERMS = {
    "about",
    "accessibility",
    "account",
    "archive",
    "back",
    "blog",
    "browse",
    "contact",
    "copyright",
    "download",
    "email",
    "facebook",
    "faq",
    "feedback",
    "follow",
    "footer",
    "gallery",
    "home",
    "instagram",
    "latest news",
    "login",
    "menu",
    "more",
    "news",
    "next",
    "photos",
    "privacy",
    "read more",
    "rss",
    "search",
    "share",
    "site map",
    "skip to content",
    "terms",
    "twitter",
    "videos",
    "youtube",
}
BOILERPLATE_PHRASES = (
    "all rights reserved",
    "cookies",
    "cookie policy",
    "privacy policy",
    "terms and conditions",
    "this website uses cookies",
    "subscribe to our newsletter",
    "follow us on",
    "share this",
    "skip to content",
)

PROMISE_PATTERN = re.compile(
    r"\b(will|vow(?:s|ed)?|promise[sd]?|pledge[sd]?|commit(?:s|ted|ment)?|ensure[sd]?|"
    r"deliver(?:s|ed)?|increase[sd]?|create[sd]?|guarantee[sd]?|undertake[sn]?)\b",
    re.IGNORECASE,
)
POLICY_PATTERN = re.compile(
    r"\b(policy|programme|program|fund|bill|act|regulation|strategy|initiative|"
    r"service[- ]?plan|manifesto|reform|framework|agenda|development|economy|"
    r"education|health|budget|allocation|project|solar|energy)\b",
    re.IGNORECASE,
)
BIOGRAPHICAL_PATTERN = re.compile(
    r"\b(candidate|leader|president|minister|attorney|lawyer|advocate|member|"
    r"party|background|born|educated|graduated|founded|chairperson|boko)\b",
    re.IGNORECASE,
)
PUBLIC_STATUS_PATTERN = re.compile(
    r"\b(status|office|current|appointed|appointment|elected|announced|serving|"
    r"serves|government|president|minister|ministry|official|leadership|"
    r"administration)\b",
    re.IGNORECASE,
)
DECLARATIVE_VERB_PATTERN = re.compile(
    r"\b(is|are|was|were|has|have|had|serves|serving|provides|offers|requires|"
    r"allows|enables|announces|announced|approves|approved|launches|launched|"
    r"establishes|established|implements|implemented|opened|closed|starts|"
    r"started|ends|ended|appoints|appointed|elects|elected|states|stated|"
    r"seeks|says|said|plans|planned|leads|led|won|formed|includes)\b",
    re.IGNORECASE,
)


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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string.")


def _packet_hash_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: packet[field]
        for field in PACKET_FIELDS
        if field not in ("packet_hash", "packet_root")
    }


def _packet_root_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {field: packet[field] for field in PACKET_FIELDS if field != "packet_root"}


def _claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("claim_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "temporal_claim_extraction_only": True,
        "modes": ["dry-run", "extract-claims"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "packet_fields": list(PACKET_FIELDS),
        "claim_fields": list(CLAIM_FIELDS),
        "claim_types": list(CLAIM_TYPES),
        "evidence_hash_fields": list(EVIDENCE_HASH_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "extraction_rule": (
            "Claim text is copied exactly from temporal evidence packet evidence_text. "
            "No rewriting, splitting, summarizing, normalization, or inference is performed."
        ),
        "root_rules": {
            "packet_hash": "validated sha256 over upstream packet excluding packet_hash and packet_root",
            "packet_root": "validated sha256 over upstream packet excluding packet_root",
            "claim_root": "sha256 over temporal claim excluding claim_root",
            "refusal_root": "sha256 over temporal claim refusal excluding refusal_root",
        },
        "closed_guardrails": {
            "approved_evidence": 0,
            "claims_invented": 0,
            "claims_normalized": 0,
            "claims_normalized_semantically": 0,
            "claims_rewritten": 0,
            "contradictions_created": 0,
            "embeddings_created": 0,
            "final_reports_created": 0,
            "live_web_access_performed": 0,
            "llm_calls": 0,
            "production_ready": False,
            "urls_fetched": 0,
        },
    }


def _load_packets(packets_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(packets_path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("temporal_evidence_packets.json is missing.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("temporal_evidence_packets schema_version is unsupported.")
    packets = payload.get("temporal_evidence_packets")
    if not isinstance(packets, list):
        raise ValueError("temporal_evidence_packets must be a list.")
    return packets


def _validate_upstream_summary(summary_path: Path, packet_count: int) -> Dict[str, Any]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        raise ValueError("temporal_evidence_packet_summary.json is missing.")
    if summary.get("temporal_evidence_packet_status") not in UPSTREAM_STATUSES:
        raise ValueError("Temporal evidence packet upstream status is invalid.")
    if summary.get("temporal_evidence_packet_count") != packet_count:
        raise ValueError("Temporal evidence packet count does not match summary.")
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
        if summary.get(counter_name) != 0:
            raise ValueError(f"Upstream guardrail {counter_name} must remain 0.")
    for flag_name in (
        "lineage_preserved",
        "segment_sha256_preserved",
        "localization_root_preserved",
        "evidence_text_exact_copy",
        "no_generated_outputs_committed",
    ):
        if summary.get(flag_name) is not True:
            raise ValueError(f"Upstream preservation flag {flag_name} must remain true.")
    if not _closed_flags(summary):
        raise ValueError("Temporal evidence packet governance flags must remain closed.")
    return summary


def _validate_packet_for_claims(packet: Dict[str, Any]) -> None:
    if not isinstance(packet, dict) or set(packet.keys()) != set(PACKET_FIELDS):
        raise ValueError("Temporal evidence packet fields do not match upstream schema.")
    for field_name in PACKET_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(packet, field_name, "TemporalEvidencePacket")
    if packet["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalEvidencePacket.time_direction unsupported.")
    if packet["source_type"] not in SOURCE_TYPES:
        raise ValueError("TemporalEvidencePacket.source_type unsupported.")
    if not _is_public_url(packet["url"]):
        raise ValueError("TemporalEvidencePacket.url must be public HTTP(S).")
    if packet["manual_review_required"] is not True:
        raise ValueError("TemporalEvidencePacket.manual_review_required must remain true.")
    if packet["segment_sha256"] != _sha256_text(packet["evidence_text"]):
        raise ValueError("TemporalEvidencePacket.segment_sha256 does not match evidence_text.")
    for hash_field in EVIDENCE_HASH_FIELDS:
        if not _is_nonzero_hash(packet.get(hash_field)):
            raise ValueError(f"TemporalEvidencePacket missing preserved {hash_field}.")
    if packet["packet_hash"] != _hash_json(_packet_hash_material(packet)):
        raise ValueError("TemporalEvidencePacket.packet_hash mismatch.")
    if packet["packet_root"] != _hash_json(_packet_root_material(packet)):
        raise ValueError("TemporalEvidencePacket.packet_root mismatch.")


def _is_url_or_path_like(text: str) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    if stripped.startswith(("/", "#")):
        return True
    if re.fullmatch(r"https?://\S+", lowered):
        return True
    if re.fullmatch(r"[\w./?=&%#:-]+", lowered) and "/" in lowered:
        return True
    return False


def _is_navigation_or_boilerplate(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    has_explicit_signal = bool(PROMISE_PATTERN.search(lowered) or DECLARATIVE_VERB_PATTERN.search(lowered))
    if lowered in NAVIGATION_TERMS:
        return True
    if any(phrase in lowered for phrase in BOILERPLATE_PHRASES) and (
        _word_count(lowered) <= 40 or not has_explicit_signal
    ):
        return True
    if _is_url_or_path_like(lowered):
        return True
    if _word_count(lowered) <= 3 and not DECLARATIVE_VERB_PATTERN.search(lowered):
        return True
    if "," in lowered and _word_count(lowered) <= 6 and not DECLARATIVE_VERB_PATTERN.search(lowered):
        return True
    return False


def _is_heading_or_slogan(text: str) -> bool:
    stripped = text.strip()
    if _word_count(stripped) <= 4 and not re.search(r"[.!?]", stripped):
        return True
    if len(stripped) <= 120 and stripped == stripped.upper() and not re.search(r"[.!?]$", stripped):
        return True
    if not DECLARATIVE_VERB_PATTERN.search(stripped) and not PROMISE_PATTERN.search(stripped):
        if not re.search(r"[.!?]", stripped) and _word_count(stripped) <= 10:
            return True
    return False


def _has_explicit_statement(text: str) -> bool:
    return bool(
        DECLARATIVE_VERB_PATTERN.search(text)
        or PROMISE_PATTERN.search(text)
        or re.search(r"\b(to|for)\s+[a-z0-9][a-z0-9-]+\b", text, re.IGNORECASE)
        and POLICY_PATTERN.search(text)
    )


def _claim_type_for_text(text: str) -> Optional[str]:
    stripped = text.strip()
    if not stripped or _word_count(stripped) < 5:
        return None
    if _is_navigation_or_boilerplate(stripped) or _is_heading_or_slogan(stripped):
        return None
    if not _has_explicit_statement(stripped):
        return None
    if PROMISE_PATTERN.search(stripped):
        return "PROMISE_CANDIDATE"
    if POLICY_PATTERN.search(stripped):
        return "POLICY_STATEMENT"
    if BIOGRAPHICAL_PATTERN.search(stripped) and DECLARATIVE_VERB_PATTERN.search(stripped):
        return "BIOGRAPHICAL_STATEMENT"
    if PUBLIC_STATUS_PATTERN.search(stripped) and DECLARATIVE_VERB_PATTERN.search(stripped):
        return "PUBLIC_STATUS"
    if DECLARATIVE_VERB_PATTERN.search(stripped) and _word_count(stripped) >= 8:
        return "UNKNOWN_CLAIM"
    return None


def _claim_confidence_for_type(claim_type: str) -> float:
    return {
        "PROMISE_CANDIDATE": 0.70,
        "POLICY_STATEMENT": 0.60,
        "BIOGRAPHICAL_STATEMENT": 0.55,
        "PUBLIC_STATUS": 0.65,
        "UNKNOWN_CLAIM": 0.45,
    }[claim_type]


def _claim_category_for_type(claim_type: str) -> str:
    return {
        "PROMISE_CANDIDATE": "temporal_promise_candidate",
        "POLICY_STATEMENT": "temporal_policy_statement",
        "BIOGRAPHICAL_STATEMENT": "temporal_biographical_statement",
        "PUBLIC_STATUS": "temporal_public_status",
        "UNKNOWN_CLAIM": "temporal_unknown_claim",
    }[claim_type]


def _evidence_hashes_from_packet(packet: Dict[str, Any]) -> Dict[str, str]:
    hashes = {
        "segment_sha256": str(packet.get("segment_sha256") or ""),
        "localization_root": str(packet.get("localization_root") or ""),
        "packet_hash": str(packet.get("packet_hash") or ""),
        "packet_root": str(packet.get("packet_root") or ""),
    }
    if tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("Temporal claim evidence hash fields changed unexpectedly.")
    return hashes


def _make_claim(packet: Dict[str, Any], claim_index: int, claim_type: str) -> Dict[str, Any]:
    claim = {
        "temporal_claim_id": f"TEMPORAL_CLAIM_{claim_index:06d}",
        "temporal_evidence_packet_id": packet["temporal_evidence_packet_id"],
        "localized_segment_id": packet["localized_segment_id"],
        "source_id": packet["source_id"],
        "time_direction": packet["time_direction"],
        "source_type": packet["source_type"],
        "url": packet["url"],
        "publisher": packet["publisher"],
        "topic": packet["topic"],
        "claim_text": packet["evidence_text"],
        "claim_type": claim_type,
        "claim_category": _claim_category_for_type(claim_type),
        "claim_confidence": _claim_confidence_for_type(claim_type),
        "evidence_hashes": _evidence_hashes_from_packet(packet),
        "packet_root": packet["packet_root"],
        "manual_review_required": True,
        "claim_root": "",
    }
    claim["claim_root"] = _hash_json(_claim_root_material(claim))
    return claim


def _packet_identity(packet: Any) -> Tuple[str, str, str, str]:
    if not isinstance(packet, dict):
        return ("UNKNOWN_PACKET", "UNKNOWN_SEGMENT", "UNKNOWN_SOURCE", "")
    return (
        str(packet.get("temporal_evidence_packet_id") or "UNKNOWN_PACKET"),
        str(packet.get("localized_segment_id") or "UNKNOWN_SEGMENT"),
        str(packet.get("source_id") or "UNKNOWN_SOURCE"),
        str(packet.get("url") or ""),
    )


def _make_refusal(packet: Any, code: str, reason: str) -> Dict[str, Any]:
    packet_id, localized_segment_id, source_id, url = _packet_identity(packet)
    hashes = (
        _evidence_hashes_from_packet(packet)
        if isinstance(packet, dict)
        else {field_name: "" for field_name in EVIDENCE_HASH_FIELDS}
    )
    claim_text = str(packet.get("evidence_text") or "") if isinstance(packet, dict) else ""
    packet_root = str(packet.get("packet_root") or "") if isinstance(packet, dict) else ""
    refusal = {
        "refusal_id": f"TEMPORAL_CLAIM_REFUSAL_{packet_id}",
        "temporal_evidence_packet_id": packet_id,
        "localized_segment_id": localized_segment_id,
        "source_id": source_id,
        "url": url,
        "claim_text": claim_text,
        "refusal_code": code,
        "refusal_reason": reason,
        "evidence_hashes": hashes,
        "packet_root": packet_root,
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
        raise ValueError("Temporal claim fields changed unexpectedly.")
    for field_name in (
        "temporal_claim_id",
        "temporal_evidence_packet_id",
        "localized_segment_id",
        "source_id",
        "time_direction",
        "source_type",
        "url",
        "publisher",
        "topic",
        "claim_text",
        "claim_type",
        "claim_category",
        "packet_root",
        "claim_root",
    ):
        _require_nonempty_string(claim, field_name, "TemporalClaim")
    if claim["temporal_evidence_packet_id"] not in valid_packet_ids:
        raise ValueError("TemporalClaim references an unknown temporal evidence packet.")
    if claim["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalClaim.time_direction unsupported.")
    if claim["source_type"] not in SOURCE_TYPES:
        raise ValueError("TemporalClaim.source_type unsupported.")
    if not _is_public_url(claim["url"]):
        raise ValueError("TemporalClaim.url must be public HTTP(S).")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError("TemporalClaim.claim_type unsupported.")
    if not isinstance(claim["claim_confidence"], float):
        raise ValueError("TemporalClaim.claim_confidence must be a float.")
    if claim["claim_confidence"] < 0 or claim["claim_confidence"] > 1:
        raise ValueError("TemporalClaim.claim_confidence must be between 0 and 1.")
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("TemporalClaim.evidence_hashes fields changed unexpectedly.")
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("TemporalClaim.evidence_hashes must preserve non-zero hashes.")
    if hashes["packet_root"] != claim["packet_root"]:
        raise ValueError("TemporalClaim packet_root preservation mismatch.")
    if claim["manual_review_required"] is not True:
        raise ValueError("TemporalClaim.manual_review_required must remain true.")
    if claim["claim_root"] != _hash_json(_claim_root_material(claim)):
        raise ValueError(f"claim_root mismatch for {claim['temporal_claim_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Temporal claim refusal fields changed unexpectedly.")
    for field_name in (
        "refusal_id",
        "temporal_evidence_packet_id",
        "localized_segment_id",
        "source_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TemporalClaimRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("TemporalClaimRefusal.refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalClaimRefusal.manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("TemporalClaimRefusal guardrails must remain closed.")
    hashes = refusal.get("evidence_hashes")
    if not isinstance(hashes, dict) or tuple(hashes.keys()) != EVIDENCE_HASH_FIELDS:
        raise ValueError("TemporalClaimRefusal.evidence_hashes fields changed unexpectedly.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _refusal_for_text(packet: Dict[str, Any], text: str) -> Tuple[str, str]:
    if not text.strip():
        return "REFUSED_EMPTY_TEXT", "Temporal evidence packet text is empty."
    if _is_navigation_or_boilerplate(text) or _is_heading_or_slogan(text):
        return (
            "REFUSED_NAVIGATION_OR_BOILERPLATE",
            "Temporal evidence packet text is navigation, slogan, heading, or boilerplate.",
        )
    return (
        "REFUSED_NO_EXPLICIT_CLAIM",
        "Temporal evidence packet text lacks an explicit factual, policy, promise, or status statement.",
    )


def _claim_or_refusal(
    packet: Dict[str, Any],
    claim_index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_packet_for_claims(packet)
    except ValueError as exc:
        code = "REFUSED_HASH_OR_ROOT_MISMATCH" if "mismatch" in str(exc).lower() else "REFUSED_MALFORMED_PACKET"
        return None, _make_refusal(packet, code, str(exc))

    text = packet["evidence_text"]
    claim_type = _claim_type_for_text(text)
    if claim_type is None:
        code, reason = _refusal_for_text(packet, text)
        return None, _make_refusal(packet, code, reason)
    return _make_claim(packet, claim_index, claim_type), None


def _status_for(mode: str, claim_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if claim_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if claim_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_claim_extraction_root",
        "temporal_claim_schema_hash",
        "temporal_claim_extraction_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    packet_count: int,
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
                    f"- {claim['temporal_claim_id']}: {claim['claim_type']}",
                    f"  - Packet: {claim['temporal_evidence_packet_id']}",
                    f"  - Source: {claim['source_id']}",
                    f"  - URL: {claim['url']}",
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
                    f"  - Packet: {refusal['temporal_evidence_packet_id']}",
                    f"  - Text Preview: {preview}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Claim Extraction v2",
            "",
            "This lane extracts conservative manual-review temporal claim candidates "
            "from flat temporal evidence packet text. It refuses empty, generic, "
            "navigational, slogan, heading, boilerplate, or non-claim text. It "
            "does not invent claims, normalize claims, create embeddings, create "
            "contradictions, or generate final reports.",
            "",
            "## Summary",
            f"- temporal_claim_extraction_status: {status}",
            f"- mode: {mode}",
            f"- temporal_evidence_packet_count: {packet_count}",
            f"- temporal_claim_count: {len(claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_claim_extraction_root: {root}",
            "",
            "## First Temporal Claims",
            *claim_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Claims Invented: 0",
            "- Claims Normalized: 0",
            "- Claims Rewritten: 0",
            "- Claims Normalized Semantically: 0",
            "- Embeddings Created: 0",
            "- URLs Fetched: 0",
            "- Live Web Access Performed: 0",
            "- LLM Calls: 0",
            "- Contradictions Created: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )


def build_temporal_claim_extraction(
    mode: str = "dry-run",
    packets_path: Path = DEFAULT_TEMPORAL_EVIDENCE_PACKETS,
    packet_summary_path: Path = DEFAULT_TEMPORAL_EVIDENCE_PACKET_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "extract-claims"):
        raise ValueError("mode must be 'dry-run' or 'extract-claims'.")

    packets = _load_packets(packets_path)
    _validate_upstream_summary(packet_summary_path, len(packets))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_packet_ids = [str(packet.get("temporal_evidence_packet_id") or "") for packet in packets]
    validated_packet_count = 0

    if mode == "dry-run":
        for packet in packets:
            _validate_packet_for_claims(packet)
            validated_packet_count += 1
    else:
        for packet in packets:
            claim, refusal = _claim_or_refusal(packet, len(claims) + 1)
            if claim is not None:
                validate_claim(claim, valid_packet_ids)
                claims.append(claim)
                validated_packet_count += 1
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)
                if refusal["refusal_code"] not in ("REFUSED_MALFORMED_PACKET", "REFUSED_HASH_OR_ROOT_MISMATCH"):
                    validated_packet_count += 1

    for claim in claims:
        validate_claim(claim, valid_packet_ids)
    for refusal in refusals:
        validate_refusal(refusal)

    claim_roots = [claim["claim_root"] for claim in claims]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    status = _status_for(mode, len(claims), len(refusals))
    report = _build_report(status, mode, len(packets), claims, refusals, "")
    summary = {
        "temporal_claim_extraction_status": status,
        "mode": mode,
        "temporal_evidence_packet_count": len(packets),
        "validated_packet_count": validated_packet_count,
        "temporal_claim_count": len(claims),
        "refusal_count": len(refusals),
        "before_claim_count": sum(1 for claim in claims if claim["time_direction"] == "BEFORE"),
        "after_claim_count": sum(1 for claim in claims if claim["time_direction"] == "AFTER"),
        "claim_type_counts": {
            claim_type: sum(1 for claim in claims if claim["claim_type"] == claim_type)
            for claim_type in CLAIM_TYPES
        },
        "source_type_claim_counts": {
            source_type: sum(1 for claim in claims if claim["source_type"] == source_type)
            for source_type in SOURCE_TYPES
        },
        "claim_roots": claim_roots,
        "refusal_roots": refusal_roots,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "lineage_preserved": True,
        "hashes_preserved": True,
        "roots_preserved": True,
        "packet_text_exact_copy": True,
        "temporal_claim_schema_hash": schema_hash,
        "temporal_claim_extraction_report_hash": "",
        "temporal_claim_extraction_root": "",
        "claims_invented": 0,
        "claims_normalized": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "embeddings_created": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "contradictions_created": 0,
        "final_reports_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_claim_extraction_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(packets),
        claims,
        refusals,
        summary["temporal_claim_extraction_root"],
    )
    summary["temporal_claim_extraction_report_hash"] = _sha256_text(report)
    summary["temporal_claim_extraction_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(packets),
        claims,
        refusals,
        summary["temporal_claim_extraction_root"],
    )

    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "claims_rewritten",
        "claims_normalized_semantically",
        "embeddings_created",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "contradictions_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Temporal claim extraction guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / CLAIMS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "temporal_extracted_claims": claims,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "temporal_claim_extraction_refusals": refusals,
        },
    )
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "temporal_extracted_claims": claims,
        "temporal_claim_extraction_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_temporal_claim_extraction"]
