#!/usr/bin/env python3
"""
Temporal Claim Normalization v2.

Converts temporal claim candidates into canonical symbolic claim identities.
This lane does not invent claims, merge unrelated claims, create embeddings,
create contradictions, generate final reports, mark production readiness, or
approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re


DEFAULT_TEMPORAL_CLAIMS = Path(
    "outputs/temporal_claim_extraction/temporal_extracted_claims.json"
)
DEFAULT_TEMPORAL_CLAIM_SUMMARY = Path(
    "outputs/temporal_claim_extraction/temporal_claim_extraction_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_claim_normalization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_normalization_summary.json"
NORMALIZED_OUTPUT = DEFAULT_OUTPUT_DIR / "normalized_temporal_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_normalization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_normalization_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_normalization_schema.json"

SCHEMA_VERSION = "temporal_claim_normalization_v2"
UPSTREAM_SCHEMA_VERSION = "temporal_claim_extraction_v2"

DRY_RUN_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_PARTIAL"
REFUSED_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_REFUSED"

UPSTREAM_STATUSES = (
    "TEMPORAL_CLAIM_EXTRACTION_CANDIDATE",
    "TEMPORAL_CLAIM_EXTRACTION_PARTIAL",
    "TEMPORAL_CLAIM_EXTRACTION_REFUSED",
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
CLAIM_TYPES = (
    "PROMISE_CANDIDATE",
    "POLICY_STATEMENT",
    "BIOGRAPHICAL_STATEMENT",
    "PUBLIC_STATUS",
    "UNKNOWN_CLAIM",
)
CLAIM_FAMILIES = ("PROMISE", "POLICY", "BIOGRAPHICAL", "PUBLIC_STATUS", "UNKNOWN")
NORMALIZATION_STATUS = "TEMPORAL_NORMALIZED_CLAIM_REQUIRES_MANUAL_REVIEW"

RAW_CLAIM_FIELDS = (
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
NORMALIZED_CLAIM_FIELDS = (
    "normalized_claim_id",
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
    "claim_root",
    "canonical_subject",
    "canonical_predicate",
    "canonical_object",
    "claim_family",
    "normalization_confidence",
    "normalization_status",
    "manual_review_required",
    "normalized_claim_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "temporal_claim_id",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "url",
    "claim_text",
    "refusal_code",
    "refusal_reason",
    "evidence_hashes",
    "packet_root",
    "claim_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_INSUFFICIENT_SEMANTIC_STRUCTURE",
    "REFUSED_MALFORMED_TEMPORAL_CLAIM",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string.")


def _word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", value))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _raw_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
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


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "temporal_claim_normalization_only": True,
        "modes": ["dry-run", "normalize"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "raw_claim_fields": list(RAW_CLAIM_FIELDS),
        "evidence_hash_fields": list(EVIDENCE_HASH_FIELDS),
        "normalized_claim_fields": list(NORMALIZED_CLAIM_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "normalization_rule": (
            "Canonical subject, predicate, and object are extracted only from "
            "explicit statement text inside one temporal claim. Missing facts "
            "are not inferred and unrelated claims are not merged."
        ),
        "prohibited_outputs": {
            "claims_invented": 0,
            "claims_merged": 0,
            "embeddings_created": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "claim_root": "validated sha256 over upstream temporal claim excluding claim_root",
            "normalized_claim_root": "sha256 over normalized temporal claim excluding normalized_claim_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
        },
    }


def _load_claims(claims_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(claims_path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("temporal_extracted_claims.json is missing.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("temporal_extracted_claims schema_version is unsupported.")
    claims = payload.get("temporal_extracted_claims")
    if not isinstance(claims, list):
        raise ValueError("temporal_extracted_claims must be a list.")
    return claims


def _validate_upstream_summary(summary_path: Path, claim_count: int) -> Dict[str, Any]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        raise ValueError("temporal_claim_extraction_summary.json is missing.")
    if summary.get("temporal_claim_extraction_status") not in UPSTREAM_STATUSES:
        raise ValueError("Temporal claim extraction upstream status is invalid.")
    if summary.get("temporal_claim_count") != claim_count:
        raise ValueError("Temporal claim count does not match extraction summary.")
    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "embeddings_created",
        "contradictions_created",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"Upstream guardrail {counter_name} must remain 0.")
    for flag_name in (
        "lineage_preserved",
        "hashes_preserved",
        "roots_preserved",
        "packet_text_exact_copy",
        "no_generated_outputs_committed",
    ):
        if summary.get(flag_name) is not True:
            raise ValueError(f"Upstream preservation flag {flag_name} must remain true.")
    if not _closed_flags(summary):
        raise ValueError("Temporal claim extraction governance flags must remain closed.")
    return summary


def validate_raw_claim(claim: Dict[str, Any]) -> None:
    if not isinstance(claim, dict) or set(claim.keys()) != set(RAW_CLAIM_FIELDS):
        raise ValueError("Temporal claim fields do not match upstream schema.")
    for field_name in RAW_CLAIM_FIELDS:
        if field_name in ("manual_review_required", "claim_confidence", "evidence_hashes"):
            continue
        _require_nonempty_string(claim, field_name, "TemporalClaim")
    if claim["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalClaim.time_direction unsupported.")
    if claim["source_type"] not in SOURCE_TYPES:
        raise ValueError("TemporalClaim.source_type unsupported.")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError("TemporalClaim.claim_type unsupported.")
    if not _is_public_url(claim["url"]):
        raise ValueError("TemporalClaim.url must be public HTTP(S).")
    if claim["manual_review_required"] is not True:
        raise ValueError("TemporalClaim.manual_review_required must remain true.")
    if not isinstance(claim["claim_confidence"], float):
        raise ValueError("TemporalClaim.claim_confidence must be a float.")
    if claim["claim_confidence"] < 0 or claim["claim_confidence"] > 1:
        raise ValueError("TemporalClaim.claim_confidence must be between 0 and 1.")
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(EVIDENCE_HASH_FIELDS):
        raise ValueError("TemporalClaim.evidence_hashes fields changed unexpectedly.")
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("TemporalClaim.evidence_hashes must preserve non-zero hashes.")
    if hashes["packet_root"] != claim["packet_root"]:
        raise ValueError("TemporalClaim.packet_root preservation mismatch.")
    if claim["claim_root"] != _hash_json(_raw_claim_root_material(claim)):
        raise ValueError(f"claim_root mismatch for {claim['temporal_claim_id']}.")


def _valid_semantic_part(value: str) -> bool:
    value = _normalize_space(value)
    if not value or _word_count(value) < 1:
        return False
    if re.search(r"\b(a|an|the|to|for|of|with|and|or|at|in|on)$", value, re.IGNORECASE):
        return False
    if value in ("...", "…"):
        return False
    return True


def _valid_subject(value: str) -> bool:
    value = _normalize_space(value)
    if not _valid_semantic_part(value):
        return False
    if _word_count(value) > 24:
        return False
    if re.search(r"[.!?]", value):
        return False
    if re.match(r"^(as|when|while|after|before|during|which|who|that)\b", value, re.IGNORECASE):
        return False
    return True


def _semantic_tuple_from_match(
    subject: str,
    predicate: str,
    object_text: str,
) -> Optional[Tuple[str, str, str]]:
    subject = _normalize_space(subject.strip(" |,;:-"))
    subject = re.sub(r"^(thus|therefore|hence),\s+", "", subject, flags=re.IGNORECASE)
    predicate = _normalize_space(predicate.strip(" |,;:-")).lower()
    object_text = re.split(r"\.\s+", object_text, maxsplit=1)[0]
    object_text = _normalize_space(object_text.strip(" |,;:-."))
    if not (
        _valid_subject(subject)
        and _valid_semantic_part(predicate)
        and _valid_semantic_part(object_text)
    ):
        return None
    return subject, predicate, object_text


def _statement_candidates(text: str) -> List[str]:
    candidates: List[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = _normalize_space(line)
        if not line:
            continue
        sentence_parts = [
            _normalize_space(part)
            for part in re.split(r"(?<=[.!?])\s+", line)
            if _normalize_space(part)
        ]
        candidates.extend(sentence_parts)
        candidates.append(line)
    whole = _normalize_space(text)
    candidates.extend(
        _normalize_space(part)
        for part in re.split(r"(?<=[.!?])\s+", whole)
        if _normalize_space(part)
    )
    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _extract_semantic_tuple_from_statement(statement: str) -> Optional[Tuple[str, str, str]]:
    statement = _normalize_space(statement)
    statement = statement.strip("•*- ")
    patterns = (
        r"^(?P<subject>.+?)\s+(?P<predicate>will\s+(?:affirm|commit|ensure|deliver|increase|create|guarantee|provide|establish|build|make|have|support|develop|improve|expand|introduce|reduce|raise|restore|transform))\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>vows|vowed|pledges|pledged|promises|promised|commits|committed|ensures|ensured|delivers|delivered|increases|increased|creates|created)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has\s+been|have\s+been|had\s+been)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>is|are|was|were)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has\s+not|have\s+not|had\s+not)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>has|have|had)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>launched|launches|implemented|implements|marked|marks|announced|announces|appointed|appoints|elected|elects|approved|approves)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<predicate>breaks\s+ground\s+on|broke\s+ground\s+on)\s+(?P<object>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, statement, re.IGNORECASE)
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


def _extract_semantic_tuple(text: str) -> Optional[Tuple[str, str, str]]:
    for statement in _statement_candidates(text):
        semantic_tuple = _extract_semantic_tuple_from_statement(statement)
        if semantic_tuple is not None:
            return semantic_tuple
    return None


def _claim_family_for_type(claim_type: str) -> str:
    return {
        "PROMISE_CANDIDATE": "PROMISE",
        "POLICY_STATEMENT": "POLICY",
        "BIOGRAPHICAL_STATEMENT": "BIOGRAPHICAL",
        "PUBLIC_STATUS": "PUBLIC_STATUS",
        "UNKNOWN_CLAIM": "UNKNOWN",
    }[claim_type]


def _normalization_confidence(raw_claim: Dict[str, Any], semantic_tuple: Tuple[str, str, str]) -> float:
    subject, predicate, object_text = semantic_tuple
    base = float(raw_claim["claim_confidence"])
    structure_bonus = 0.15 if all(_word_count(part) >= 1 for part in (subject, predicate, object_text)) else 0.0
    return round(min(0.95, max(0.0, base + structure_bonus)), 2)


def _make_normalized_claim(
    raw_claim: Dict[str, Any],
    normalized_index: int,
    semantic_tuple: Tuple[str, str, str],
) -> Dict[str, Any]:
    subject, predicate, object_text = semantic_tuple
    normalized = {
        "normalized_claim_id": f"TEMPORAL_NORMALIZED_CLAIM_{normalized_index:06d}",
        "temporal_claim_id": raw_claim["temporal_claim_id"],
        "temporal_evidence_packet_id": raw_claim["temporal_evidence_packet_id"],
        "localized_segment_id": raw_claim["localized_segment_id"],
        "source_id": raw_claim["source_id"],
        "time_direction": raw_claim["time_direction"],
        "source_type": raw_claim["source_type"],
        "url": raw_claim["url"],
        "publisher": raw_claim["publisher"],
        "topic": raw_claim["topic"],
        "claim_text": raw_claim["claim_text"],
        "claim_type": raw_claim["claim_type"],
        "claim_category": raw_claim["claim_category"],
        "claim_confidence": raw_claim["claim_confidence"],
        "evidence_hashes": dict(raw_claim["evidence_hashes"]),
        "packet_root": raw_claim["packet_root"],
        "claim_root": raw_claim["claim_root"],
        "canonical_subject": subject,
        "canonical_predicate": predicate,
        "canonical_object": object_text,
        "claim_family": _claim_family_for_type(raw_claim["claim_type"]),
        "normalization_confidence": _normalization_confidence(raw_claim, semantic_tuple),
        "normalization_status": NORMALIZATION_STATUS,
        "manual_review_required": True,
        "normalized_claim_root": "",
    }
    normalized["normalized_claim_root"] = _hash_json(
        _normalized_claim_root_material(normalized)
    )
    return normalized


def _make_refusal(raw_claim: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"TEMPORAL_CLAIM_NORMALIZATION_REFUSAL_{raw_claim.get('temporal_claim_id', 'UNKNOWN_CLAIM')}",
        "temporal_claim_id": str(raw_claim.get("temporal_claim_id") or "UNKNOWN_CLAIM"),
        "temporal_evidence_packet_id": str(raw_claim.get("temporal_evidence_packet_id") or ""),
        "localized_segment_id": str(raw_claim.get("localized_segment_id") or ""),
        "source_id": str(raw_claim.get("source_id") or ""),
        "url": str(raw_claim.get("url") or ""),
        "claim_text": str(raw_claim.get("claim_text") or ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "evidence_hashes": dict(raw_claim.get("evidence_hashes") or {}),
        "packet_root": str(raw_claim.get("packet_root") or ""),
        "claim_root": str(raw_claim.get("claim_root") or ""),
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
    if set(normalized_claim.keys()) != set(NORMALIZED_CLAIM_FIELDS):
        raise ValueError("Normalized temporal claim fields changed unexpectedly.")
    for field_name in (
        "normalized_claim_id",
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
        "canonical_subject",
        "canonical_predicate",
        "canonical_object",
        "claim_family",
        "normalization_status",
        "normalized_claim_root",
    ):
        _require_nonempty_string(normalized_claim, field_name, "NormalizedTemporalClaim")
    claim_id = normalized_claim["temporal_claim_id"]
    if claim_id not in raw_claims_by_id:
        raise ValueError(f"NormalizedTemporalClaim references unknown claim: {claim_id}.")
    raw_claim = raw_claims_by_id[claim_id]
    for field_name in (
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
        "packet_root",
        "claim_root",
    ):
        if normalized_claim[field_name] != raw_claim[field_name]:
            raise ValueError(f"NormalizedTemporalClaim must preserve {field_name}.")
    if normalized_claim["evidence_hashes"] != raw_claim["evidence_hashes"]:
        raise ValueError("NormalizedTemporalClaim must preserve evidence_hashes.")
    if normalized_claim["claim_family"] not in CLAIM_FAMILIES:
        raise ValueError("NormalizedTemporalClaim.claim_family unsupported.")
    if not isinstance(normalized_claim["normalization_confidence"], float):
        raise ValueError("NormalizedTemporalClaim.normalization_confidence must be a float.")
    if normalized_claim["normalization_confidence"] < 0 or normalized_claim["normalization_confidence"] > 1:
        raise ValueError("NormalizedTemporalClaim.normalization_confidence must be between 0 and 1.")
    if normalized_claim["normalization_status"] != NORMALIZATION_STATUS:
        raise ValueError("NormalizedTemporalClaim.normalization_status changed unexpectedly.")
    if normalized_claim["manual_review_required"] is not True:
        raise ValueError("NormalizedTemporalClaim.manual_review_required must remain true.")
    if normalized_claim["normalized_claim_root"] != _hash_json(
        _normalized_claim_root_material(normalized_claim)
    ):
        raise ValueError(
            f"normalized_claim_root mismatch for {normalized_claim['normalized_claim_id']}."
        )


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal claim normalization refusal fields changed unexpectedly.")
    for field_name in (
        "refusal_id",
        "temporal_claim_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TemporalClaimNormalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("TemporalClaimNormalizationRefusal.refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalClaimNormalizationRefusal.manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("TemporalClaimNormalizationRefusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _normalize_or_refuse(
    raw_claim: Dict[str, Any],
    normalized_index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        validate_raw_claim(raw_claim)
    except ValueError as exc:
        return None, _make_refusal(
            raw_claim,
            "REFUSED_MALFORMED_TEMPORAL_CLAIM",
            f"Malformed temporal claim: {exc}",
        )
    semantic_tuple = _extract_semantic_tuple(raw_claim["claim_text"])
    if semantic_tuple is None:
        return None, _make_refusal(
            raw_claim,
            "REFUSED_INSUFFICIENT_SEMANTIC_STRUCTURE",
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


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_claim_normalization_root",
        "temporal_claim_normalization_schema_hash",
        "temporal_claim_normalization_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


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
                    f"- {claim['normalized_claim_id']}: {claim['claim_family']}",
                    f"  - Claim ID: {claim['temporal_claim_id']}",
                    f"  - Subject: {claim['canonical_subject']}",
                    f"  - Predicate: {claim['canonical_predicate']}",
                    f"  - Object: {claim['canonical_object']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Claim ID: {refusal['temporal_claim_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Claim Normalization v2",
            "",
            "This lane converts temporal claim candidates into canonical symbolic "
            "claim identities. It refuses claims when subject, predicate, and "
            "object cannot be extracted from explicit text without inference.",
            "",
            "## Summary",
            f"- temporal_claim_normalization_status: {status}",
            f"- mode: {mode}",
            f"- input_claim_count: {input_claim_count}",
            f"- normalized_claim_count: {len(normalized_claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_claim_normalization_root: {root}",
            "",
            "## First Normalized Claims",
            *normalized_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Claims Invented: 0",
            "- Claims Merged: 0",
            "- Embeddings Created: 0",
            "- Contradictions Created: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_claim_normalization(
    mode: str = "dry-run",
    claims_path: Path = DEFAULT_TEMPORAL_CLAIMS,
    claim_summary_path: Path = DEFAULT_TEMPORAL_CLAIM_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "normalize"):
        raise ValueError("mode must be 'dry-run' or 'normalize'.")

    raw_claims = _load_claims(claims_path)
    _validate_upstream_summary(claim_summary_path, len(raw_claims))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    normalized_claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    validated_claim_count = 0
    if mode == "dry-run":
        for raw_claim in raw_claims:
            validate_raw_claim(raw_claim)
            validated_claim_count += 1
    else:
        for raw_claim in raw_claims:
            normalized_claim, refusal = _normalize_or_refuse(
                raw_claim, len(normalized_claims) + 1
            )
            validate_raw_claim(raw_claim)
            validated_claim_count += 1
            if normalized_claim is not None:
                normalized_claims.append(normalized_claim)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    raw_claims_by_id = {claim["temporal_claim_id"]: claim for claim in raw_claims}
    for normalized_claim in normalized_claims:
        validate_normalized_claim(normalized_claim, raw_claims_by_id)
    for refusal in refusals:
        validate_refusal(refusal)

    normalized_roots = [claim["normalized_claim_root"] for claim in normalized_claims]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    status = _status_for(mode, len(normalized_claims), len(refusals))
    report = _build_report(status, mode, len(raw_claims), normalized_claims, refusals, "")
    summary = {
        "temporal_claim_normalization_status": status,
        "mode": mode,
        "input_claim_count": len(raw_claims),
        "validated_claim_count": validated_claim_count,
        "normalized_claim_count": len(normalized_claims),
        "refusal_count": len(refusals),
        "before_normalized_claim_count": sum(
            1 for claim in normalized_claims if claim["time_direction"] == "BEFORE"
        ),
        "after_normalized_claim_count": sum(
            1 for claim in normalized_claims if claim["time_direction"] == "AFTER"
        ),
        "claim_family_counts": {
            family: sum(1 for claim in normalized_claims if claim["claim_family"] == family)
            for family in CLAIM_FAMILIES
        },
        "source_type_normalized_claim_counts": {
            source_type: sum(1 for claim in normalized_claims if claim["source_type"] == source_type)
            for source_type in SOURCE_TYPES
        },
        "normalized_claim_roots": normalized_roots,
        "refusal_roots": refusal_roots,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "lineage_preserved": True,
        "hashes_preserved": True,
        "roots_preserved": True,
        "claims_invented": 0,
        "claims_merged": 0,
        "embeddings_created": 0,
        "contradictions_created": 0,
        "final_reports_created": 0,
        "temporal_claim_normalization_schema_hash": schema_hash,
        "temporal_claim_normalization_report_hash": "",
        "temporal_claim_normalization_root": "",
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_claim_normalization_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(raw_claims),
        normalized_claims,
        refusals,
        summary["temporal_claim_normalization_root"],
    )
    summary["temporal_claim_normalization_report_hash"] = _sha256_text(report)
    summary["temporal_claim_normalization_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(raw_claims),
        normalized_claims,
        refusals,
        summary["temporal_claim_normalization_root"],
    )

    for counter_name in (
        "claims_invented",
        "claims_merged",
        "embeddings_created",
        "contradictions_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Temporal claim normalization guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / NORMALIZED_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "normalized_temporal_claims": normalized_claims,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "temporal_claim_normalization_refusals": refusals,
        },
    )
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "normalized_temporal_claims": normalized_claims,
        "temporal_claim_normalization_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_temporal_claim_normalization"]
