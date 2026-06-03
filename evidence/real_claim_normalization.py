#!/usr/bin/env python3
"""
Real Claim Normalization v2.

Converts raw real claim candidates into canonical symbolic semantic objects.
This lane does not invent facts, create embeddings, compute similarity scores,
create relationships, detect contradictions, produce conclusions, generate
final reports, mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re


DEFAULT_REAL_CLAIMS = Path(
    "outputs/real_evidence_packets_to_claims/real_extracted_claims.json"
)
DEFAULT_REAL_CLAIM_SUMMARY = Path(
    "outputs/real_evidence_packets_to_claims/real_claim_extraction_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/real_claim_normalization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_normalization_summary.json"
NORMALIZED_CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "normalized_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_normalization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_claim_normalization_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "normalized_claim_schema.json"

SCHEMA_VERSION = "real_claim_normalization_v2"

DRY_RUN_STATUS = "REAL_CLAIM_NORMALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "REAL_CLAIM_NORMALIZATION_CANDIDATE"
PARTIAL_STATUS = "REAL_CLAIM_NORMALIZATION_PARTIAL"
REFUSED_STATUS = "REAL_CLAIM_NORMALIZATION_REFUSED"

UPSTREAM_STATUSES = (
    "REAL_CLAIM_EXTRACTION_CANDIDATE",
    "REAL_CLAIM_EXTRACTION_PARTIAL",
    "REAL_CLAIM_EXTRACTION_REFUSED",
)

NORMALIZATION_STATUS = "REAL_NORMALIZED_CLAIM_REQUIRES_MANUAL_REVIEW"
REFUSAL_STATUS = "REAL_CLAIM_NORMALIZATION_REFUSAL_REQUIRES_MANUAL_REVIEW"

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

NORMALIZED_CLAIM_FIELDS = (
    "normalized_claim_id",
    "claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "claim_text",
    "source_claim_type",
    "source_claim_category",
    "claim_root",
    "packet_root",
    "evidence_anchors",
    "evidence_hashes",
    "subject",
    "predicate",
    "object",
    "time_reference",
    "location_reference",
    "claim_type",
    "claim_category",
    "confidence",
    "normalization_status",
    "manual_review_required",
    "normalized_claim_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "claim_text",
    "refusal_code",
    "refusal_reason",
    "evidence_anchors",
    "evidence_hashes",
    "claim_root",
    "packet_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_INSUFFICIENT_SEMANTIC_STRUCTURE",
    "REFUSED_MALFORMED_CLAIM",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
)

CLAIM_TYPES = (
    "POLICY_STATEMENT",
    "GOVERNMENT_STATUS",
    "PUBLIC_SERVICE_INFORMATION",
    "PROMISE_CANDIDATE",
    "UNKNOWN_CLAIM",
)

CLAIM_STATUS = "REAL_CLAIM_REQUIRES_MANUAL_REVIEW"

EMPTY_CONTEXT = ""


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


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", value))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "real_claim_normalization_only": True,
        "modes": ["dry-run", "normalize"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "raw_claim_fields": list(CLAIM_FIELDS),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "evidence_hash_fields": list(EVIDENCE_HASH_FIELDS),
        "normalized_claim_fields": list(NORMALIZED_CLAIM_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "normalization_rule": (
            "Subject, predicate, and object are extracted only from explicit text "
            "inside the raw claim. Missing facts are not inferred."
        ),
        "future_embedding_fields_not_created": [
            "embedding_vector",
            "embedding_root",
            "semantic_cluster_id",
            "similarity_score",
        ],
        "prohibited_outputs": {
            "facts_invented": 0,
            "embeddings_created": 0,
            "similarity_scores_created": 0,
            "relationships_created": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "conclusions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "normalized_claim_root": "sha256 over normalized claim excluding normalized_claim_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "real_claim_normalization_root": (
                "sha256 over sorted normalized claim roots, sorted refusal roots, and closed flags"
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
        raise ValueError("real claim normalization schema_version changed unexpectedly")
    if schema.get("raw_claim_fields") != list(CLAIM_FIELDS):
        raise ValueError("real claim normalization raw_claim_fields changed unexpectedly")
    if schema.get("normalized_claim_fields") != list(NORMALIZED_CLAIM_FIELDS):
        raise ValueError("real claim normalization normalized_claim_fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("real claim normalization refusal_fields changed unexpectedly")


def _claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("claim_root", None)
    return material


def _normalized_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("normalized_claim_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _load_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("real_extracted_claims.json is missing")
    claims = payload.get("real_extracted_claims")
    if not isinstance(claims, list):
        raise ValueError("real_extracted_claims must be a list")
    return claims


def _validate_upstream_summary(summary: Dict[str, Any], claim_count: int) -> None:
    if not summary:
        raise ValueError("real_claim_extraction_summary.json is missing")
    if summary.get("real_claim_extraction_status") not in UPSTREAM_STATUSES:
        raise ValueError("real claim extraction upstream status is invalid")
    if summary.get("real_claim_count") != claim_count:
        raise ValueError("real claim count does not match extraction summary")
    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "contradictions_created",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(summary):
        raise ValueError("real claim extraction guardrails must remain closed")


def _has_line_anchor(anchors: Dict[str, Any]) -> bool:
    start = _safe_int(anchors.get("text_line_start") or anchors.get("transcript_start_line"))
    end = _safe_int(anchors.get("text_line_end") or anchors.get("transcript_end_line"))
    return start > 0 and end >= start


def _has_timestamp_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("timestamp_start")) and bool(anchors.get("timestamp_end"))


def _has_anchor(anchors: Dict[str, Any]) -> bool:
    return _has_line_anchor(anchors) or _has_timestamp_anchor(anchors)


def validate_raw_claim(claim: Dict[str, Any]) -> None:
    if set(claim.keys()) != set(CLAIM_FIELDS):
        raise ValueError("Raw real claim fields changed unexpectedly")
    for field_name in (
        "claim_id",
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_text",
        "claim_type",
        "claim_category",
        "packet_root",
        "claim_root",
        "claim_status",
    ):
        _require_nonempty_string(claim, field_name, "RawRealClaim")
    if not _is_public_url(claim["source_url"]):
        raise ValueError("RawRealClaim.source_url must be public HTTP(S)")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError(f"Unsupported RawRealClaim.claim_type: {claim['claim_type']}")
    if claim["claim_status"] != CLAIM_STATUS:
        raise ValueError("RawRealClaim.claim_status changed unexpectedly")
    if claim["manual_review_required"] is not True:
        raise ValueError("RawRealClaim.manual_review_required must remain true")
    anchors = claim.get("evidence_anchors")
    if not isinstance(anchors, dict) or set(anchors.keys()) != set(EVIDENCE_ANCHOR_FIELDS):
        raise ValueError("RawRealClaim.evidence_anchors fields changed unexpectedly")
    if not _has_anchor(anchors):
        raise ValueError("RawRealClaim must preserve a line or timestamp anchor")
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(EVIDENCE_HASH_FIELDS):
        raise ValueError("RawRealClaim.evidence_hashes fields changed unexpectedly")
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("RawRealClaim.evidence_hashes must preserve non-zero hashes")
    if hashes["packet_hash"] != claim["packet_root"]:
        raise ValueError("RawRealClaim packet_hash must match packet_root")
    if not _is_nonzero_hash(claim["claim_root"]):
        raise ValueError("RawRealClaim.claim_root must be non-zero")
    if claim["claim_root"] != _hash_json(_claim_root_material(claim)):
        raise ValueError(f"claim_root mismatch for {claim['claim_id']}")


def _extract_explicit_time(text: str) -> str:
    patterns = (
        r"\bsince\s+\d{4}\b",
        r"\bfor\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)\b",
        r"\bseven\s+days\b",
        r"\bwith immediate effect\b",
        r"\bJuly\s+\d{1,2}(?:\s+through\s+\d{1,2})?\b",
        r"\b\d{4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _normalize_space(match.group(0))
    return EMPTY_CONTEXT


def _extract_explicit_location(text: str) -> str:
    patterns = (
        r"\bin\s+([A-Z][A-Za-z]+(?:\s+(?:of|the|and|[A-Z][A-Za-z]+)){0,6})\b",
        r"\bat\s+the\s+([A-Z][A-Za-z]+(?:\s+(?:of|the|and|[A-Z][A-Za-z]+)){0,8})\b",
        r"\balong\s+the\s+border\s+with\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_space(match.group(1))
    return EMPTY_CONTEXT


def _valid_semantic_part(value: str) -> bool:
    value = _normalize_space(value)
    if not value:
        return False
    if _word_count(value) < 1:
        return False
    if re.search(r"\b(a|an|the|to|for|of|with|and|or|at|in)$", value, re.IGNORECASE):
        return False
    if value in ("...", "…"):
        return False
    return True


def _valid_predicate(value: str) -> bool:
    value = _normalize_space(value)
    return bool(value) and _word_count(value) >= 1


def _valid_subject(value: str) -> bool:
    value = _normalize_space(value)
    if not _valid_semantic_part(value):
        return False
    if re.match(r"^(as|when|while|after|before)\b", value, re.IGNORECASE):
        return False
    if re.search(r"\b(which|who|that)$", value, re.IGNORECASE):
        return False
    return True


def _semantic_tuple_from_match(
    subject: str,
    predicate: str,
    object_text: str,
) -> Optional[Tuple[str, str, str]]:
    subject = _normalize_space(subject.strip(" ,;:-"))
    predicate = _normalize_space(predicate.strip(" ,;:-")).lower()
    object_text = re.split(r"\.\s+", object_text, maxsplit=1)[0]
    object_text = _normalize_space(object_text.strip(" ,;:-."))
    if not (
        _valid_subject(subject)
        and _valid_predicate(predicate)
        and _valid_semantic_part(object_text)
    ):
        return None
    return subject, predicate, object_text


def _extract_semantic_tuple(text: str) -> Optional[Tuple[str, str, str]]:
    claim_text = _normalize_space(text)
    claim_text = re.sub(r"\s+-\s+[A-Z]{2,}$", "", claim_text).strip()
    patterns = (
        r"^(?P<subject>.+?)\s+(?P<predicate>ended\s+in\s+favour\s+of)\s+(?P<object>.+?)(?:\s+at\s+.+|,\s+.+|\.)?$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has\s+been\s+[A-Za-z]+ed)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has\s+[A-Za-z]+ed)\s+(?P<object>.+)$",
        r"^(?P<subject>[^,]+),\s+which\s+.+?,\s+(?P<predicate>is|are|was|were)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>will\s+have)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>have\s+[A-Za-z]+)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has|have|had)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>is|are|was|were)\s+(?P<object>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, claim_text, re.IGNORECASE)
        if not match:
            continue
        semantic_tuple = _semantic_tuple_from_match(
            match.group("subject"),
            match.group("predicate"),
            match.group("object"),
        )
        if semantic_tuple is not None:
            return semantic_tuple
    return None


def _make_normalized_claim(
    raw_claim: Dict[str, Any],
    normalized_index: int,
    semantic_tuple: Tuple[str, str, str],
) -> Dict[str, Any]:
    subject, predicate, object_text = semantic_tuple
    normalized = {
        "normalized_claim_id": f"REAL_NORMALIZED_CLAIM_{normalized_index:04d}",
        "claim_id": raw_claim["claim_id"],
        "packet_id": raw_claim["packet_id"],
        "source_url": raw_claim["source_url"],
        "source_owner": raw_claim["source_owner"],
        "source_title": raw_claim["source_title"],
        "claim_text": raw_claim["claim_text"],
        "source_claim_type": raw_claim["claim_type"],
        "source_claim_category": raw_claim["claim_category"],
        "claim_root": raw_claim["claim_root"],
        "packet_root": raw_claim["packet_root"],
        "evidence_anchors": dict(raw_claim["evidence_anchors"]),
        "evidence_hashes": dict(raw_claim["evidence_hashes"]),
        "subject": subject,
        "predicate": predicate,
        "object": object_text,
        "time_reference": _extract_explicit_time(raw_claim["claim_text"]),
        "location_reference": _extract_explicit_location(raw_claim["claim_text"]),
        "claim_type": raw_claim["claim_type"],
        "claim_category": raw_claim["claim_category"],
        "confidence": float(raw_claim["claim_confidence"]),
        "normalization_status": NORMALIZATION_STATUS,
        "manual_review_required": True,
        "normalized_claim_root": "",
    }
    normalized["normalized_claim_root"] = _hash_json(
        _normalized_claim_root_material(normalized)
    )
    return normalized


def _make_refusal(raw_claim: Dict[str, Any], reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REAL_CLAIM_NORMALIZATION_REFUSAL_{raw_claim.get('claim_id', 'UNKNOWN_CLAIM')}",
        "claim_id": str(raw_claim.get("claim_id") or "UNKNOWN_CLAIM"),
        "packet_id": str(raw_claim.get("packet_id") or ""),
        "source_url": str(raw_claim.get("source_url") or ""),
        "source_owner": str(raw_claim.get("source_owner") or ""),
        "source_title": str(raw_claim.get("source_title") or ""),
        "claim_text": str(raw_claim.get("claim_text") or ""),
        "refusal_code": "REFUSED_INSUFFICIENT_SEMANTIC_STRUCTURE",
        "refusal_reason": reason,
        "evidence_anchors": dict(raw_claim.get("evidence_anchors") or {}),
        "evidence_hashes": dict(raw_claim.get("evidence_hashes") or {}),
        "claim_root": str(raw_claim.get("claim_root") or ""),
        "packet_root": str(raw_claim.get("packet_root") or ""),
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_normalized_claim(
    normalized_claim: Dict[str, Any],
    raw_claims_by_id: Dict[str, Dict[str, Any]],
) -> None:
    if tuple(normalized_claim.keys()) != NORMALIZED_CLAIM_FIELDS:
        raise ValueError("Normalized real claim fields changed unexpectedly")
    for field_name in (
        "normalized_claim_id",
        "claim_id",
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_text",
        "source_claim_type",
        "source_claim_category",
        "claim_root",
        "packet_root",
        "subject",
        "predicate",
        "object",
        "claim_type",
        "claim_category",
        "normalization_status",
        "normalized_claim_root",
    ):
        _require_nonempty_string(normalized_claim, field_name, "NormalizedRealClaim")
    claim_id = normalized_claim["claim_id"]
    if claim_id not in raw_claims_by_id:
        raise ValueError(f"NormalizedRealClaim references unknown claim_id: {claim_id}")
    raw_claim = raw_claims_by_id[claim_id]
    for field_name in (
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_text",
        "claim_root",
        "packet_root",
    ):
        if normalized_claim[field_name] != raw_claim[field_name]:
            raise ValueError(f"NormalizedRealClaim must preserve {field_name}")
    if normalized_claim["evidence_anchors"] != raw_claim["evidence_anchors"]:
        raise ValueError("NormalizedRealClaim must preserve evidence_anchors")
    if normalized_claim["evidence_hashes"] != raw_claim["evidence_hashes"]:
        raise ValueError("NormalizedRealClaim must preserve evidence_hashes")
    if normalized_claim["claim_type"] != raw_claim["claim_type"]:
        raise ValueError("NormalizedRealClaim must preserve claim_type")
    if normalized_claim["claim_category"] != raw_claim["claim_category"]:
        raise ValueError("NormalizedRealClaim must preserve claim_category")
    if normalized_claim["normalization_status"] != NORMALIZATION_STATUS:
        raise ValueError("NormalizedRealClaim.normalization_status changed unexpectedly")
    if normalized_claim["manual_review_required"] is not True:
        raise ValueError("NormalizedRealClaim.manual_review_required must remain true")
    if not _has_anchor(normalized_claim["evidence_anchors"]):
        raise ValueError("NormalizedRealClaim must preserve a line or timestamp anchor")
    if not isinstance(normalized_claim["evidence_hashes"], dict):
        raise ValueError("NormalizedRealClaim.evidence_hashes must be a dictionary")
    for hash_value in normalized_claim["evidence_hashes"].values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("NormalizedRealClaim must preserve non-zero hashes")
    if not _is_nonzero_hash(normalized_claim["normalized_claim_root"]):
        raise ValueError("NormalizedRealClaim.normalized_claim_root must be non-zero")
    if normalized_claim["normalized_claim_root"] != _hash_json(
        _normalized_claim_root_material(normalized_claim)
    ):
        raise ValueError(
            f"normalized_claim_root mismatch for {normalized_claim['normalized_claim_id']}"
        )


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Real claim normalization refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "claim_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RealClaimNormalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RealClaimNormalizationRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("RealClaimNormalizationRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _normalize_or_refuse(
    raw_claim: Dict[str, Any],
    normalized_index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        validate_raw_claim(raw_claim)
    except ValueError as exc:
        return None, _make_refusal(raw_claim, f"Malformed raw claim: {exc}")
    semantic_tuple = _extract_semantic_tuple(raw_claim["claim_text"])
    if semantic_tuple is None:
        return None, _make_refusal(
            raw_claim,
            "Subject, predicate, and object could not be extracted without inference.",
        )
    return _make_normalized_claim(raw_claim, normalized_index, semantic_tuple), None


def _status_for(mode: str, normalized_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if normalized_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if normalized_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    input_claim_count: int,
    normalized_claims: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    normalized_lines = ["- None"]
    if normalized_claims:
        normalized_lines = []
        for claim in normalized_claims[:20]:
            normalized_lines.extend(
                [
                    f"- {claim['normalized_claim_id']}",
                    f"  - Claim ID: {claim['claim_id']}",
                    f"  - Subject: {claim['subject']}",
                    f"  - Predicate: {claim['predicate']}",
                    f"  - Object: {claim['object']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Claim ID: {refusal['claim_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Real Claim Normalization v2",
            "",
            "This lane converts raw real claims into canonical symbolic semantic "
            "objects. It does not invent facts, create embeddings, compute "
            "similarity scores, create relationships, detect contradictions, "
            "produce conclusions, generate final reports, mark production "
            "readiness, or approve evidence.",
            "",
            "## Summary",
            f"- normalization_status: {status}",
            f"- mode: {mode}",
            f"- input_claim_count: {input_claim_count}",
            f"- normalized_claim_count: {len(normalized_claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- real_claim_normalization_root: {root}",
            "",
            "## First Normalized Claims",
            *normalized_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Facts Invented: 0",
            "- Embeddings Created: 0",
            "- Similarity Scores Created: 0",
            "- Relationships Created: 0",
            "- Contradictions Created: 0",
            "- Final Reports Created: 0",
            "- Conclusions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_real_claim_normalization(
    mode: str = "dry-run",
    claims_path: Path = DEFAULT_REAL_CLAIMS,
    claim_summary_path: Path = DEFAULT_REAL_CLAIM_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "normalize"):
        raise ValueError("mode must be dry-run or normalize")

    claims_payload = _load_json(claims_path)
    claim_summary = _load_json(claim_summary_path)
    raw_claims = _load_claims(claims_payload)
    _validate_upstream_summary(claim_summary, len(raw_claims))

    schema = _schema()
    validate_schema(schema)

    normalized_claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    validated_claim_count = 0
    if mode == "dry-run":
        for claim in raw_claims:
            validate_raw_claim(claim)
            validated_claim_count += 1
    else:
        for claim in raw_claims:
            validate_raw_claim(claim)
            validated_claim_count += 1
            normalized_claim, refusal = _normalize_or_refuse(
                claim, len(normalized_claims) + 1
            )
            if normalized_claim is not None:
                normalized_claims.append(normalized_claim)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    raw_claims_by_id = {claim["claim_id"]: claim for claim in raw_claims}
    for normalized_claim in normalized_claims:
        validate_normalized_claim(normalized_claim, raw_claims_by_id)
    for refusal in refusals:
        validate_refusal(refusal)

    normalized_roots = [claim["normalized_claim_root"] for claim in normalized_claims]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    anchors_preserved_count = len(normalized_claims)
    hashes_preserved_count = len(normalized_claims)
    roots_preserved_count = len(normalized_claims)
    root = _hash_json(
        {
            "normalized_claim_roots": sorted(normalized_roots),
            "refusal_roots": sorted(refusal_roots),
            "facts_invented": 0,
            "embeddings_created": 0,
            "similarity_scores_created": 0,
            "relationships_created": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "conclusions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(normalized_claims), len(refusals))
    report = _build_report(status, mode, len(raw_claims), normalized_claims, refusals, root)
    summary = {
        "normalization_status": status,
        "mode": mode,
        "input_claim_count": len(raw_claims),
        "validated_claim_count": validated_claim_count,
        "normalized_claim_count": len(normalized_claims),
        "refusal_count": len(refusals),
        "anchors_preserved_count": anchors_preserved_count,
        "hashes_preserved_count": hashes_preserved_count,
        "roots_preserved_count": roots_preserved_count,
        "facts_invented": 0,
        "embeddings_created": 0,
        "similarity_scores_created": 0,
        "relationships_created": 0,
        "contradictions_created": 0,
        "final_reports_created": 0,
        "conclusions_created": 0,
        "normalized_claim_roots": normalized_roots,
        "refusal_roots": refusal_roots,
        "normalized_claim_schema_hash": _hash_json(schema),
        "real_claim_normalization_report_hash": _sha256_text(report),
        "real_claim_normalization_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "facts_invented",
        "embeddings_created",
        "similarity_scores_created",
        "relationships_created",
        "contradictions_created",
        "final_reports_created",
        "conclusions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("real claim normalization guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(NORMALIZED_CLAIMS_OUTPUT, {"normalized_claims": normalized_claims})
    _write_json(REFUSALS_OUTPUT, {"claim_normalization_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "normalized_claims": normalized_claims,
        "claim_normalization_refusals": refusals,
        "schema": schema,
        "report": report,
    }
