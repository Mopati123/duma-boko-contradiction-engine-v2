#!/usr/bin/env python3
"""
Temporal Evidence Expansion Seeds v2.

Generates deterministic manual-review discovery seeds for before/after temporal
comparison evidence. This lane does not search the web, resolve URLs, invent
evidence, invent quotes, create contradictions, mark production readiness, or
approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re


DEFAULT_NORMALIZED_CLAIMS = Path("outputs/real_claim_normalization/normalized_claims.json")
DEFAULT_ADJUDICATION_SUMMARY = Path(
    "outputs/contradiction_candidate_adjudication/contradiction_candidate_summary.json"
)
DEFAULT_ADJUDICATION_CANDIDATES = Path(
    "outputs/contradiction_candidate_adjudication/contradiction_candidates.json"
)
DEFAULT_DISCOVERY_INPUT = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")

DEFAULT_OUTPUT_DIR = Path("outputs/temporal_evidence_expansion_seeds")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_expansion_summary.json"
SEEDS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_expansion_seeds.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_expansion_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_expansion_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_expansion_schema.json"

SCHEMA_VERSION = "temporal_evidence_expansion_seeds_v2"

DRY_RUN_STATUS = "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_PARTIAL"
REFUSED_STATUS = "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_REFUSED"

UPSTREAM_ADJUDICATION_STATUSES = (
    "CONTRADICTION_CANDIDATE_ADJUDICATION_CANDIDATE",
    "CONTRADICTION_CANDIDATE_ADJUDICATION_PARTIAL",
)

BEFORE_TARGETS = (
    "CAMPAIGN_PROMISE",
    "MANIFESTO",
    "RALLY_SPEECH",
    "INTERVIEW",
)

AFTER_TARGETS = (
    "OFFICIAL_GOVERNMENT_STATUS",
    "MINISTRY_UPDATE",
    "BUDGET_ACTION",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
)

TARGET_EVIDENCE_TYPES = BEFORE_TARGETS + AFTER_TARGETS

TARGET_SEARCH_PHRASES = {
    "CAMPAIGN_PROMISE": "campaign promise",
    "MANIFESTO": "manifesto",
    "RALLY_SPEECH": "rally speech",
    "INTERVIEW": "interview",
    "OFFICIAL_GOVERNMENT_STATUS": "official government status",
    "MINISTRY_UPDATE": "ministry update",
    "BUDGET_ACTION": "budget allocation",
    "PARLIAMENT_RECORD": "parliament record",
    "NEWS_FOLLOWUP": "news follow up",
}

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

TEMPORAL_SEED_FIELDS = (
    "temporal_seed_id",
    "source_claim_id",
    "normalized_claim_id",
    "subject",
    "predicate",
    "object",
    "time_direction",
    "target_evidence_type",
    "search_query",
    "expected_topic",
    "expected_claim_keywords",
    "reasoning_summary",
    "manual_review_required",
    "seed_root",
)

LINEAGE_FIELDS = (
    "temporal_seed_id",
    "source_claim_id",
    "normalized_claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "evidence_anchors",
    "evidence_hashes",
    "claim_root",
    "packet_root",
    "normalized_claim_root",
    "lineage_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "source_claim_id",
    "normalized_claim_id",
    "refusal_code",
    "refusal_reason",
    "subject",
    "predicate",
    "object",
    "evidence_anchors",
    "evidence_hashes",
    "claim_root",
    "packet_root",
    "normalized_claim_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_MALFORMED_NORMALIZED_CLAIM",
    "REFUSED_MISSING_ADJUDICATION_INPUTS",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
    "REFUSED_EMPTY_SEARCH_QUERY_MATERIAL",
    "REFUSED_UNSUPPORTED_TARGET_EVIDENCE_TYPE",
    "REFUSED_MISSING_CLAIM_LINEAGE",
)

DISCOVERY_CONTEXT_FIELDS = (
    "speaker_name",
    "geographic_context",
    "investigation_cases",
    "discovery_seeds",
    "candidate_sources",
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}

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


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _tokenize(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _keyword_tokens(value: str) -> List[str]:
    tokens: List[str] = []
    seen = set()
    for token in _tokenize(value):
        if len(token) < 3 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    tokens = _keyword_tokens(value)
    if not tokens:
        return "temporal_comparison"
    return "_".join(tokens[:8])


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


def _normalized_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("normalized_claim_root", None)
    return material


def _seed_root_material(seed: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(seed)
    material.pop("seed_root", None)
    return material


def _lineage_root_material(lineage: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(lineage)
    material.pop("lineage_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "temporal_evidence_expansion_seeds_only": True,
        "modes": ["dry-run", "generate"],
        "upstream_adjudication_statuses": list(UPSTREAM_ADJUDICATION_STATUSES),
        "time_direction_values": ["BEFORE", "AFTER"],
        "before_target_evidence_types": list(BEFORE_TARGETS),
        "after_target_evidence_types": list(AFTER_TARGETS),
        "target_evidence_types": list(TARGET_EVIDENCE_TYPES),
        "temporal_seed_fields": list(TEMPORAL_SEED_FIELDS),
        "lineage_fields": list(LINEAGE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "search_query_policy": (
            "Queries are deterministic strings built from explicit normalized "
            "claim text, static discovery context, Botswana, speaker name, and "
            "target evidence type phrases. No URLs are created."
        ),
        "prohibited_outputs": {
            "evidence_invented": 0,
            "urls_invented": 0,
            "quotes_created": 0,
            "quotes_invented": 0,
            "contradictions_created": 0,
            "proof_chains_created": 0,
            "final_reports_created": 0,
            "word_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "seed_root": "sha256 over temporal seed excluding seed_root",
            "lineage_root": "sha256 over temporal seed lineage excluding lineage_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "temporal_expansion_root": (
                "sha256 over sorted seed roots, lineage roots, refusal roots, "
                "and closed guardrail counters"
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
        raise ValueError("temporal expansion schema_version changed unexpectedly")
    if schema.get("temporal_seed_fields") != list(TEMPORAL_SEED_FIELDS):
        raise ValueError("temporal expansion seed fields changed unexpectedly")
    if schema.get("lineage_fields") != list(LINEAGE_FIELDS):
        raise ValueError("temporal expansion lineage fields changed unexpectedly")
    if schema.get("target_evidence_types") != list(TARGET_EVIDENCE_TYPES):
        raise ValueError("temporal expansion target evidence types changed unexpectedly")


def _load_normalized_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("normalized_claims.json is missing")
    claims = payload.get("normalized_claims")
    if not isinstance(claims, list):
        raise ValueError("normalized_claims must be a list")
    return claims


def _load_adjudication_payload(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not payload:
        raise ValueError("contradiction_candidates.json is missing")
    adjudicated = payload.get("adjudicated_relationships")
    candidates = payload.get("contradiction_candidates")
    if not isinstance(adjudicated, list):
        raise ValueError("adjudicated_relationships must be a list")
    if not isinstance(candidates, list):
        raise ValueError("contradiction_candidates must be a list")
    return adjudicated, candidates


def _has_line_anchor(anchors: Dict[str, Any]) -> bool:
    start = _safe_int(anchors.get("text_line_start") or anchors.get("transcript_start_line"))
    end = _safe_int(anchors.get("text_line_end") or anchors.get("transcript_end_line"))
    return start > 0 and end >= start


def _has_timestamp_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("timestamp_start")) and bool(anchors.get("timestamp_end"))


def _has_anchor(anchors: Dict[str, Any]) -> bool:
    return _has_line_anchor(anchors) or _has_timestamp_anchor(anchors)


def validate_normalized_claim(claim: Dict[str, Any]) -> None:
    if set(claim.keys()) != set(NORMALIZED_CLAIM_FIELDS):
        raise ValueError("Normalized claim fields changed unexpectedly")
    for field_name in (
        "normalized_claim_id",
        "claim_id",
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_text",
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
        _require_nonempty_string(claim, field_name, "NormalizedClaim")
    if claim["manual_review_required"] is not True:
        raise ValueError("NormalizedClaim.manual_review_required must remain true")
    if not _is_public_url(claim["source_url"]):
        raise ValueError("NormalizedClaim.source_url must be public HTTP(S)")
    anchors = claim.get("evidence_anchors")
    if not isinstance(anchors, dict) or set(anchors.keys()) != set(EVIDENCE_ANCHOR_FIELDS):
        raise ValueError("NormalizedClaim.evidence_anchors fields changed unexpectedly")
    if not _has_anchor(anchors):
        raise ValueError("NormalizedClaim must preserve a line or timestamp anchor")
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(EVIDENCE_HASH_FIELDS):
        raise ValueError("NormalizedClaim.evidence_hashes fields changed unexpectedly")
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("NormalizedClaim.evidence_hashes must preserve non-zero hashes")
    if hashes["packet_hash"] != claim["packet_root"]:
        raise ValueError("NormalizedClaim packet_hash must match packet_root")
    if not _is_nonzero_hash(claim["claim_root"]):
        raise ValueError("NormalizedClaim.claim_root must be non-zero")
    if not _is_nonzero_hash(claim["normalized_claim_root"]):
        raise ValueError("NormalizedClaim.normalized_claim_root must be non-zero")
    if claim["normalized_claim_root"] != _hash_json(_normalized_claim_root_material(claim)):
        raise ValueError(
            f"normalized_claim_root mismatch for {claim['normalized_claim_id']}"
        )


def _validate_adjudication_inputs(
    adjudication_summary: Dict[str, Any],
    adjudicated_relationships: List[Dict[str, Any]],
    contradiction_candidates: List[Dict[str, Any]],
) -> None:
    if not adjudication_summary:
        raise ValueError("contradiction_candidate_summary.json is missing")
    if (
        adjudication_summary.get("contradiction_candidate_status")
        not in UPSTREAM_ADJUDICATION_STATUSES
    ):
        raise ValueError("contradiction candidate upstream status is invalid")
    if adjudication_summary.get("adjudicated_edge_count") != len(adjudicated_relationships):
        raise ValueError("adjudicated relationship count does not match summary")
    if adjudication_summary.get("candidate_contradiction_count") != len(
        contradiction_candidates
    ):
        raise ValueError("contradiction candidate count does not match summary")
    for counter_name in (
        "proven_contradiction_count",
        "proof_chains_created",
        "final_contradiction_certifications_created",
        "final_reports_created",
        "word_reports_created",
        "new_claims_created",
        "facts_invented",
    ):
        if adjudication_summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if adjudication_summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(adjudication_summary):
        raise ValueError("contradiction candidate guardrails must remain closed")


def _validate_discovery_input(discovery_input: Dict[str, Any]) -> None:
    if not discovery_input:
        raise ValueError("duma_boko_discovery_seeds.json is missing")
    for field_name in DISCOVERY_CONTEXT_FIELDS:
        if field_name not in discovery_input:
            raise ValueError(f"discovery input missing {field_name}")
    if not isinstance(discovery_input.get("investigation_cases"), list) or not discovery_input[
        "investigation_cases"
    ]:
        raise ValueError("discovery input investigation_cases must be non-empty")
    if not isinstance(discovery_input.get("discovery_seeds"), list) or not discovery_input[
        "discovery_seeds"
    ]:
        raise ValueError("discovery input discovery_seeds must be non-empty")


def _best_discovery_case(
    claim: Dict[str, Any],
    investigation_cases: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], int]:
    claim_tokens = set(
        _keyword_tokens(
            " ".join(
                [
                    str(claim["subject"]),
                    str(claim["predicate"]),
                    str(claim["object"]),
                    str(claim.get("claim_text") or ""),
                ]
            )
        )
    )
    best_case: Optional[Dict[str, Any]] = None
    best_score = 0
    for case in investigation_cases:
        keywords = case.get("expected_claim_keywords")
        if not isinstance(keywords, list):
            continue
        case_tokens = set(_keyword_tokens(" ".join(str(keyword) for keyword in keywords)))
        score = len(claim_tokens & case_tokens)
        if score > best_score:
            best_score = score
            best_case = case
    return best_case, best_score


def _expected_topic(claim: Dict[str, Any], discovery_case: Optional[Dict[str, Any]], score: int) -> str:
    if discovery_case and score > 0 and isinstance(discovery_case.get("topic"), str):
        return discovery_case["topic"]
    return _slug(f"{claim['subject']} {claim['object']}")


def _expected_keywords(
    claim: Dict[str, Any],
    discovery_case: Optional[Dict[str, Any]],
    score: int,
) -> List[str]:
    keywords: List[str] = []
    seen = set()
    if discovery_case and score > 0:
        case_keywords = discovery_case.get("expected_claim_keywords")
        if isinstance(case_keywords, list):
            for keyword in case_keywords:
                normalized = _normalize_space(str(keyword))
                if normalized and normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    keywords.append(normalized)
    for token in _keyword_tokens(
        f"{claim['subject']} {claim['predicate']} {claim['object']}"
    ):
        if token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords[:12] or [_slug(f"{claim['subject']} {claim['object']}")]


def _compact_object_phrase(claim_object: str) -> str:
    tokens = _keyword_tokens(claim_object)
    if not tokens:
        return _normalize_space(claim_object)[:80]
    return " ".join(tokens[:8])


def _search_query(
    claim: Dict[str, Any],
    discovery_input: Dict[str, Any],
    target_evidence_type: str,
) -> str:
    speaker_name = _normalize_space(str(discovery_input.get("speaker_name") or "Duma Boko"))
    geographic_context = _normalize_space(
        str(discovery_input.get("geographic_context") or "Botswana")
    )
    subject = _normalize_space(str(claim["subject"]))
    object_phrase = _compact_object_phrase(str(claim["object"]))
    target_phrase = TARGET_SEARCH_PHRASES[target_evidence_type]
    query_parts = [
        f'"{speaker_name}"',
        f'"{subject}"',
        f'"{object_phrase}"' if object_phrase else "",
        geographic_context,
        target_phrase,
    ]
    query = _normalize_space(" ".join(part for part in query_parts if part))
    return query


def _time_direction_for_target(target_evidence_type: str) -> str:
    if target_evidence_type in BEFORE_TARGETS:
        return "BEFORE"
    if target_evidence_type in AFTER_TARGETS:
        return "AFTER"
    raise ValueError(f"unsupported target evidence type: {target_evidence_type}")


def _reasoning_summary(
    claim: Dict[str, Any],
    time_direction: str,
    target_evidence_type: str,
    expected_topic: str,
) -> str:
    return (
        f"{time_direction} discovery seed for {target_evidence_type} evidence "
        f"about normalized claim {claim['normalized_claim_id']} on topic "
        f"{expected_topic}. This is a search seed only; it asserts no URL, quote, "
        "evidence item, or contradiction."
    )


def _seed_for_claim_target(
    claim: Dict[str, Any],
    discovery_input: Dict[str, Any],
    discovery_case: Optional[Dict[str, Any]],
    discovery_case_score: int,
    target_evidence_type: str,
    seed_index: int,
) -> Dict[str, Any]:
    if target_evidence_type not in TARGET_EVIDENCE_TYPES:
        raise ValueError(f"unsupported target evidence type: {target_evidence_type}")
    time_direction = _time_direction_for_target(target_evidence_type)
    expected_topic = _expected_topic(claim, discovery_case, discovery_case_score)
    query = _search_query(claim, discovery_input, target_evidence_type)
    if not query:
        raise ValueError("temporal seed search query material is empty")
    seed = {
        "temporal_seed_id": f"TEMPORAL_SEED_{seed_index:06d}",
        "source_claim_id": claim["claim_id"],
        "normalized_claim_id": claim["normalized_claim_id"],
        "subject": claim["subject"],
        "predicate": claim["predicate"],
        "object": claim["object"],
        "time_direction": time_direction,
        "target_evidence_type": target_evidence_type,
        "search_query": query,
        "expected_topic": expected_topic,
        "expected_claim_keywords": _expected_keywords(
            claim, discovery_case, discovery_case_score
        ),
        "reasoning_summary": _reasoning_summary(
            claim, time_direction, target_evidence_type, expected_topic
        ),
        "manual_review_required": True,
        "seed_root": "",
    }
    seed["seed_root"] = _hash_json(_seed_root_material(seed))
    return seed


def _lineage_for_seed(seed: Dict[str, Any], claim: Dict[str, Any]) -> Dict[str, Any]:
    lineage = {
        "temporal_seed_id": seed["temporal_seed_id"],
        "source_claim_id": claim["claim_id"],
        "normalized_claim_id": claim["normalized_claim_id"],
        "packet_id": claim["packet_id"],
        "source_url": claim["source_url"],
        "source_owner": claim["source_owner"],
        "source_title": claim["source_title"],
        "evidence_anchors": claim["evidence_anchors"],
        "evidence_hashes": claim["evidence_hashes"],
        "claim_root": claim["claim_root"],
        "packet_root": claim["packet_root"],
        "normalized_claim_root": claim["normalized_claim_root"],
        "lineage_root": "",
    }
    lineage["lineage_root"] = _hash_json(_lineage_root_material(lineage))
    return lineage


def _make_refusal(
    claim: Optional[Dict[str, Any]],
    code: str,
    reason: str,
    refusal_index: int,
) -> Dict[str, Any]:
    claim = claim or {}
    refusal = {
        "refusal_id": f"TEMPORAL_EXPANSION_REFUSAL_{refusal_index:06d}",
        "source_claim_id": str(claim.get("claim_id") or ""),
        "normalized_claim_id": str(claim.get("normalized_claim_id") or ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "subject": str(claim.get("subject") or ""),
        "predicate": str(claim.get("predicate") or ""),
        "object": str(claim.get("object") or ""),
        "evidence_anchors": claim.get("evidence_anchors") if isinstance(claim.get("evidence_anchors"), dict) else {},
        "evidence_hashes": claim.get("evidence_hashes") if isinstance(claim.get("evidence_hashes"), dict) else {},
        "claim_root": str(claim.get("claim_root") or ""),
        "packet_root": str(claim.get("packet_root") or ""),
        "normalized_claim_root": str(claim.get("normalized_claim_root") or ""),
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _refusal_code_for_error(error: Exception) -> str:
    message = str(error).lower()
    if "adjudication" in message or "upstream" in message:
        return "REFUSED_MISSING_ADJUDICATION_INPUTS"
    if "guardrail" in message:
        return "REFUSED_INVALID_UPSTREAM_GUARDRAILS"
    if "query" in message or "material" in message:
        return "REFUSED_EMPTY_SEARCH_QUERY_MATERIAL"
    if "unsupported target" in message:
        return "REFUSED_UNSUPPORTED_TARGET_EVIDENCE_TYPE"
    if "lineage" in message or "root" in message:
        return "REFUSED_MISSING_CLAIM_LINEAGE"
    return "REFUSED_MALFORMED_NORMALIZED_CLAIM"


def validate_seed(seed: Dict[str, Any]) -> None:
    if tuple(seed.keys()) != TEMPORAL_SEED_FIELDS:
        raise ValueError("Temporal seed fields changed unexpectedly")
    for field_name in (
        "temporal_seed_id",
        "source_claim_id",
        "normalized_claim_id",
        "subject",
        "predicate",
        "object",
        "time_direction",
        "target_evidence_type",
        "search_query",
        "expected_topic",
        "reasoning_summary",
        "seed_root",
    ):
        _require_nonempty_string(seed, field_name, "TemporalSeed")
    if seed["time_direction"] not in ("BEFORE", "AFTER"):
        raise ValueError(f"Unsupported time_direction: {seed['time_direction']}")
    if seed["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise ValueError(f"Unsupported target_evidence_type: {seed['target_evidence_type']}")
    if seed["target_evidence_type"] in BEFORE_TARGETS and seed["time_direction"] != "BEFORE":
        raise ValueError("Before target evidence type must use BEFORE direction")
    if seed["target_evidence_type"] in AFTER_TARGETS and seed["time_direction"] != "AFTER":
        raise ValueError("After target evidence type must use AFTER direction")
    if not isinstance(seed.get("expected_claim_keywords"), list) or not seed[
        "expected_claim_keywords"
    ]:
        raise ValueError("TemporalSeed.expected_claim_keywords must be non-empty")
    if any("http://" in str(value).lower() or "https://" in str(value).lower() for value in seed.values()):
        raise ValueError("TemporalSeed must not invent or carry URLs")
    if seed["manual_review_required"] is not True:
        raise ValueError("TemporalSeed.manual_review_required must remain true")
    if seed["seed_root"] != _hash_json(_seed_root_material(seed)):
        raise ValueError(f"seed_root mismatch for {seed['temporal_seed_id']}")


def validate_lineage(lineage: Dict[str, Any]) -> None:
    if tuple(lineage.keys()) != LINEAGE_FIELDS:
        raise ValueError("Temporal seed lineage fields changed unexpectedly")
    for field_name in (
        "temporal_seed_id",
        "source_claim_id",
        "normalized_claim_id",
        "packet_id",
        "source_url",
        "source_owner",
        "source_title",
        "claim_root",
        "packet_root",
        "normalized_claim_root",
        "lineage_root",
    ):
        _require_nonempty_string(lineage, field_name, "TemporalSeedLineage")
    if not _is_public_url(lineage["source_url"]):
        raise ValueError("TemporalSeedLineage.source_url must preserve source URL")
    if not _is_nonzero_hash(lineage["claim_root"]):
        raise ValueError("TemporalSeedLineage.claim_root must be preserved")
    if not _is_nonzero_hash(lineage["packet_root"]):
        raise ValueError("TemporalSeedLineage.packet_root must be preserved")
    if not _is_nonzero_hash(lineage["normalized_claim_root"]):
        raise ValueError("TemporalSeedLineage.normalized_claim_root must be preserved")
    if not isinstance(lineage.get("evidence_anchors"), dict) or not _has_anchor(
        lineage["evidence_anchors"]
    ):
        raise ValueError("TemporalSeedLineage.evidence_anchors must be preserved")
    if not isinstance(lineage.get("evidence_hashes"), dict):
        raise ValueError("TemporalSeedLineage.evidence_hashes must be preserved")
    for hash_value in lineage["evidence_hashes"].values():
        if not _is_nonzero_hash(hash_value):
            raise ValueError("TemporalSeedLineage.evidence_hashes must be non-zero")
    if lineage["lineage_root"] != _hash_json(_lineage_root_material(lineage)):
        raise ValueError(f"lineage_root mismatch for {lineage['temporal_seed_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Temporal expansion refusal fields changed unexpectedly")
    for field_name in ("refusal_id", "refusal_code", "refusal_reason", "refusal_root"):
        _require_nonempty_string(refusal, field_name, "TemporalExpansionRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalExpansionRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("TemporalExpansionRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _build_seeds(
    normalized_claims: List[Dict[str, Any]],
    discovery_input: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    seeds: List[Dict[str, Any]] = []
    lineages: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    seed_index = 1
    refusal_index = 1
    investigation_cases = discovery_input["investigation_cases"]
    for claim in normalized_claims:
        try:
            validate_normalized_claim(claim)
            discovery_case, discovery_case_score = _best_discovery_case(
                claim, investigation_cases
            )
            for target_evidence_type in TARGET_EVIDENCE_TYPES:
                seed = _seed_for_claim_target(
                    claim,
                    discovery_input,
                    discovery_case,
                    discovery_case_score,
                    target_evidence_type,
                    seed_index,
                )
                lineage = _lineage_for_seed(seed, claim)
                validate_seed(seed)
                validate_lineage(lineage)
                seeds.append(seed)
                lineages.append(lineage)
                seed_index += 1
        except Exception as error:
            refusal = _make_refusal(
                claim if isinstance(claim, dict) else {},
                _refusal_code_for_error(error),
                str(error),
                refusal_index,
            )
            validate_refusal(refusal)
            refusals.append(refusal)
            refusal_index += 1
    return seeds, lineages, refusals


def _status_for(mode: str, seed_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if seed_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if seed_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    input_normalized_claim_count: int,
    seeds: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    seed_lines = ["- None"]
    if seeds:
        seed_lines = []
        for seed in seeds[:20]:
            seed_lines.extend(
                [
                    f"- {seed['temporal_seed_id']}: {seed['time_direction']} {seed['target_evidence_type']}",
                    f"  - Claim: {seed['normalized_claim_id']}",
                    f"  - Topic: {seed['expected_topic']}",
                    f"  - Query: {seed['search_query']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Evidence Expansion Seeds v2",
            "",
            "This lane generates before/after discovery seeds only. It does not "
            "search the web, resolve URLs, invent evidence, invent quotes, create "
            "contradictions, mark production readiness, or approve evidence.",
            "",
            "## Summary",
            f"- temporal_expansion_status: {status}",
            f"- mode: {mode}",
            f"- input_normalized_claim_count: {input_normalized_claim_count}",
            f"- temporal_seed_count: {len(seeds)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_expansion_root: {root}",
            "",
            "## First Seeds",
            *seed_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Evidence Invented: 0",
            "- URLs Invented: 0",
            "- Quotes Created: 0",
            "- Quotes Invented: 0",
            "- Contradictions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_evidence_expansion_seeds(
    mode: str = "dry-run",
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
    adjudication_summary_path: Path = DEFAULT_ADJUDICATION_SUMMARY,
    adjudication_candidates_path: Path = DEFAULT_ADJUDICATION_CANDIDATES,
    discovery_input_path: Path = DEFAULT_DISCOVERY_INPUT,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "generate"):
        raise ValueError("mode must be dry-run or generate")

    normalized_payload = _load_json(normalized_claims_path)
    adjudication_summary = _load_json(adjudication_summary_path)
    adjudication_payload = _load_json(adjudication_candidates_path)
    discovery_input = _load_json(discovery_input_path)

    normalized_claims = _load_normalized_claims(normalized_payload)
    adjudicated_relationships, contradiction_candidates = _load_adjudication_payload(
        adjudication_payload
    )

    schema = _schema()
    validate_schema(schema)
    _validate_discovery_input(discovery_input)
    _validate_adjudication_inputs(
        adjudication_summary, adjudicated_relationships, contradiction_candidates
    )
    for claim in normalized_claims:
        validate_normalized_claim(claim)

    seeds: List[Dict[str, Any]] = []
    lineages: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "generate":
        seeds, lineages, refusals = _build_seeds(normalized_claims, discovery_input)

    before_seed_count = sum(1 for seed in seeds if seed["time_direction"] == "BEFORE")
    after_seed_count = sum(1 for seed in seeds if seed["time_direction"] == "AFTER")
    seed_roots = [seed["seed_root"] for seed in seeds]
    lineage_roots = [lineage["lineage_root"] for lineage in lineages]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "seed_roots": sorted(seed_roots),
            "lineage_roots": sorted(lineage_roots),
            "refusal_roots": sorted(refusal_roots),
            "evidence_invented": 0,
            "urls_invented": 0,
            "quotes_created": 0,
            "quotes_invented": 0,
            "contradictions_created": 0,
            "proof_chains_created": 0,
            "final_reports_created": 0,
            "word_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(seeds), len(refusals))
    report = _build_report(status, mode, len(normalized_claims), seeds, refusals, root)
    summary = {
        "temporal_expansion_status": status,
        "mode": mode,
        "input_normalized_claim_count": len(normalized_claims),
        "adjudicated_edge_count": len(adjudicated_relationships),
        "upstream_candidate_contradiction_count": len(contradiction_candidates),
        "temporal_seed_count": len(seeds),
        "before_seed_count": before_seed_count,
        "after_seed_count": after_seed_count,
        "refusal_count": len(refusals),
        "lineage_preserved_count": len(lineages),
        "anchor_lineage_preserved_count": len(lineages),
        "hash_lineage_preserved_count": len(lineages),
        "root_lineage_preserved_count": len(lineages),
        "seed_roots": seed_roots,
        "lineage_roots": lineage_roots,
        "refusal_roots": refusal_roots,
        "temporal_expansion_schema_hash": _hash_json(schema),
        "temporal_expansion_report_hash": _sha256_text(report),
        "temporal_expansion_root": root,
        "evidence_invented": 0,
        "urls_invented": 0,
        "quotes_created": 0,
        "quotes_invented": 0,
        "contradictions_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "word_reports_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "evidence_invented",
        "urls_invented",
        "quotes_created",
        "quotes_invented",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
        "word_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("temporal expansion guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(
        SEEDS_OUTPUT,
        {
            "temporal_expansion_seeds": seeds,
            "temporal_seed_lineage": lineages,
        },
    )
    _write_json(REFUSALS_OUTPUT, {"temporal_expansion_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "temporal_expansion_seeds": seeds,
        "temporal_seed_lineage": lineages,
        "temporal_expansion_refusals": refusals,
        "schema": schema,
        "report": report,
    }
