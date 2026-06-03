#!/usr/bin/env python3
"""
Dual-Representation Relationship Graph v2.

Builds deterministic candidate relationship edges between embedded canonical
claims using both symbolic structure and local embedding geometry. This lane
does not create final/proven contradictions, proof chains, Word reports, new
claims, inferred facts, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import math
import re


DEFAULT_EMBEDDED_CLAIMS = Path(
    "outputs/canonical_claim_embedding_projection/embedded_claims.json"
)
DEFAULT_EMBEDDING_SUMMARY = Path(
    "outputs/canonical_claim_embedding_projection/embedding_projection_summary.json"
)
DEFAULT_NORMALIZED_CLAIMS = Path(
    "outputs/real_claim_normalization/normalized_claims.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/dual_representation_relationship_graph")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "relationship_graph_summary.json"
EDGES_OUTPUT = DEFAULT_OUTPUT_DIR / "relationship_edges.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "relationship_graph_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "relationship_graph_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "relationship_graph_schema.json"

SCHEMA_VERSION = "dual_representation_relationship_graph_v2"

DRY_RUN_STATUS = "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_CANDIDATE"
PARTIAL_STATUS = "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_PARTIAL"
REFUSED_STATUS = "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_REFUSED"

UPSTREAM_PROJECTION_STATUSES = (
    "CANONICAL_CLAIM_EMBEDDING_PROJECTION_CANDIDATE",
    "CANONICAL_CLAIM_EMBEDDING_PROJECTION_PARTIAL",
)

EMBEDDING_METHOD = "deterministic_hash_bow_l2_v1"
EMBEDDING_DIMENSION = 256

RELATIONSHIP_TYPES = (
    "DUPLICATE",
    "SUPPORTS",
    "RELATED",
    "POTENTIAL_CONTRADICTION",
    "UNRELATED",
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

SYMBOLIC_CLAIM_FIELDS = (
    "claim_id",
    "normalized_claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "claim_text",
    "subject",
    "predicate",
    "object",
    "time_reference",
    "location_reference",
    "claim_type",
    "claim_category",
    "confidence",
    "evidence_anchors",
    "evidence_hashes",
    "claim_root",
    "packet_root",
    "normalized_claim_root",
)

EMBEDDED_CLAIM_FIELDS = (
    "embedded_claim_id",
    "normalized_claim_id",
    "claim_id",
    "canonical_text",
    "symbolic_claim",
    "embedding_vector",
    "embedding_dimension",
    "embedding_method",
    "embedding_hash",
    "embedding_root",
    "manual_review_required",
)

EDGE_FIELDS = (
    "relationship_edge_id",
    "source_claim_id",
    "target_claim_id",
    "source_normalized_claim_id",
    "target_normalized_claim_id",
    "relationship_type",
    "symbolic_score",
    "embedding_similarity",
    "combined_score",
    "reasoning_summary",
    "source_symbolic_claim",
    "target_symbolic_claim",
    "source_embedding_hash",
    "target_embedding_hash",
    "evidence_anchors",
    "evidence_hashes",
    "edge_root",
    "manual_review_required",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "refusal_code",
    "refusal_reason",
    "source_claim_id",
    "target_claim_id",
    "source_normalized_claim_id",
    "target_normalized_claim_id",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_MALFORMED_EMBEDDED_CLAIM",
    "REFUSED_MALFORMED_NORMALIZED_CLAIM",
    "REFUSED_SYMBOLIC_PRESERVATION_MISMATCH",
    "REFUSED_INVALID_EMBEDDING_VECTOR",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
)

OPPOSITION_PHRASE_PAIRS = (
    ("increase", "reduce"),
    ("increased", "reduced"),
    ("increases", "reduces"),
    ("approve", "reject"),
    ("approved", "rejected"),
    ("implement", "fail"),
    ("implemented", "failed"),
    ("is", "is not"),
    ("are", "are not"),
    ("was", "was not"),
    ("were", "were not"),
    ("has", "has not"),
    ("have", "have not"),
    ("had", "had not"),
    ("will", "will not"),
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


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _tokenize(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _token_set(value: str) -> set:
    return set(_tokenize(value))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_score(value: float) -> float:
    return round(float(value), 6)


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


def _embedding_hash(canonical_text: str, vector: List[float]) -> str:
    return _hash_json(
        {
            "embedding_method": EMBEDDING_METHOD,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "canonical_text": canonical_text,
            "embedding_vector": vector,
        }
    )


def _embedding_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("embedding_root", None)
    return material


def _normalized_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("normalized_claim_root", None)
    return material


def _edge_root_material(edge: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(edge)
    material.pop("edge_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dual_representation_relationship_graph_only": True,
        "modes": ["dry-run", "build-graph"],
        "upstream_projection_statuses": list(UPSTREAM_PROJECTION_STATUSES),
        "relationship_types": list(RELATIONSHIP_TYPES),
        "edge_fields": list(EDGE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "embedded_claim_fields": list(EMBEDDED_CLAIM_FIELDS),
        "symbolic_claim_fields": list(SYMBOLIC_CLAIM_FIELDS),
        "embedding_method": EMBEDDING_METHOD,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "symbolic_score_weights": {
            "subject_token_jaccard": 0.35,
            "object_token_jaccard": 0.25,
            "predicate_score": 0.20,
            "claim_category_match": 0.15,
            "claim_type_match": 0.05,
        },
        "combined_score_weights": {
            "symbolic_score": 0.55,
            "embedding_similarity": 0.45,
        },
        "classification_order": [
            "DUPLICATE",
            "POTENTIAL_CONTRADICTION",
            "SUPPORTS",
            "RELATED",
            "UNRELATED",
        ],
        "opposition_phrase_pairs": [
            {"left": left, "right": right} for left, right in OPPOSITION_PHRASE_PAIRS
        ],
        "prohibited_outputs": {
            "facts_invented": 0,
            "new_claims_created": 0,
            "proven_contradiction_count": 0,
            "proof_chains_created": 0,
            "word_reports_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "edge_root": "sha256 over relationship edge excluding edge_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "relationship_graph_root": (
                "sha256 over sorted edge roots, sorted refusal roots, and closed flags"
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
        raise ValueError("relationship graph schema_version changed unexpectedly")
    if schema.get("edge_fields") != list(EDGE_FIELDS):
        raise ValueError("relationship graph edge_fields changed unexpectedly")
    if schema.get("relationship_types") != list(RELATIONSHIP_TYPES):
        raise ValueError("relationship graph relationship_types changed unexpectedly")
    if schema.get("embedding_method") != EMBEDDING_METHOD:
        raise ValueError("relationship graph embedding_method changed unexpectedly")
    if schema.get("embedding_dimension") != EMBEDDING_DIMENSION:
        raise ValueError("relationship graph embedding_dimension changed unexpectedly")


def _load_embedded_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("embedded_claims.json is missing")
    claims = payload.get("embedded_claims")
    if not isinstance(claims, list):
        raise ValueError("embedded_claims must be a list")
    return claims


def _load_normalized_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("normalized_claims.json is missing")
    claims = payload.get("normalized_claims")
    if not isinstance(claims, list):
        raise ValueError("normalized_claims must be a list")
    return claims


def _validate_upstream_projection_summary(
    summary: Dict[str, Any],
    embedded_count: int,
    normalized_count: int,
) -> None:
    if not summary:
        raise ValueError("embedding_projection_summary.json is missing")
    if summary.get("embedding_projection_status") not in UPSTREAM_PROJECTION_STATUSES:
        raise ValueError("embedding projection upstream status is invalid")
    if summary.get("embedded_claim_count") != embedded_count:
        raise ValueError("embedded claim count does not match projection summary")
    if summary.get("input_normalized_claim_count") != normalized_count:
        raise ValueError("normalized claim count does not match projection summary")
    if summary.get("embedding_method") != EMBEDDING_METHOD:
        raise ValueError("embedding projection method changed unexpectedly")
    if summary.get("embedding_dimension") != EMBEDDING_DIMENSION:
        raise ValueError("embedding projection dimension changed unexpectedly")
    for counter_name in (
        "facts_invented",
        "relationships_created",
        "contradictions_created",
        "final_reports_created",
        "conclusions_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(summary):
        raise ValueError("embedding projection guardrails must remain closed")


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
    if claim["normalized_claim_root"] != _hash_json(
        _normalized_claim_root_material(claim)
    ):
        raise ValueError(
            f"normalized_claim_root mismatch for {claim['normalized_claim_id']}"
        )


def _expected_symbolic_claim(normalized_claim: Dict[str, Any]) -> Dict[str, Any]:
    return {field_name: normalized_claim[field_name] for field_name in SYMBOLIC_CLAIM_FIELDS}


def validate_embedded_claim(
    embedded_claim: Dict[str, Any],
    normalized_claims_by_id: Dict[str, Dict[str, Any]],
) -> None:
    if set(embedded_claim.keys()) != set(EMBEDDED_CLAIM_FIELDS):
        raise ValueError("Embedded claim fields changed unexpectedly")
    for field_name in (
        "embedded_claim_id",
        "normalized_claim_id",
        "claim_id",
        "canonical_text",
        "embedding_method",
        "embedding_hash",
        "embedding_root",
    ):
        _require_nonempty_string(embedded_claim, field_name, "EmbeddedClaim")
    normalized_claim_id = embedded_claim["normalized_claim_id"]
    if normalized_claim_id not in normalized_claims_by_id:
        raise ValueError(f"EmbeddedClaim references unknown normalized claim: {normalized_claim_id}")
    normalized_claim = normalized_claims_by_id[normalized_claim_id]
    if embedded_claim["claim_id"] != normalized_claim["claim_id"]:
        raise ValueError("EmbeddedClaim must preserve claim_id")
    if embedded_claim["symbolic_claim"] != _expected_symbolic_claim(normalized_claim):
        raise ValueError("EmbeddedClaim symbolic_claim must match normalized claim exactly")
    vector = embedded_claim.get("embedding_vector")
    if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSION:
        raise ValueError("EmbeddedClaim.embedding_vector dimension mismatch")
    if not all(isinstance(value, float) for value in vector):
        raise ValueError("EmbeddedClaim.embedding_vector must contain floats")
    if not any(value != 0.0 for value in vector):
        raise ValueError("EmbeddedClaim.embedding_vector must be non-zero")
    if embedded_claim["embedding_method"] != EMBEDDING_METHOD:
        raise ValueError("EmbeddedClaim.embedding_method changed unexpectedly")
    if embedded_claim["embedding_dimension"] != EMBEDDING_DIMENSION:
        raise ValueError("EmbeddedClaim.embedding_dimension changed unexpectedly")
    if embedded_claim["embedding_hash"] != _embedding_hash(
        embedded_claim["canonical_text"], vector
    ):
        raise ValueError(f"embedding_hash mismatch for {embedded_claim['embedded_claim_id']}")
    if embedded_claim["embedding_root"] != _hash_json(
        _embedding_root_material(embedded_claim)
    ):
        raise ValueError(f"embedding_root mismatch for {embedded_claim['embedded_claim_id']}")
    if embedded_claim["manual_review_required"] is not True:
        raise ValueError("EmbeddedClaim.manual_review_required must remain true")


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _predicate_score(source: Dict[str, Any], target: Dict[str, Any]) -> float:
    source_predicate = _normalize_space(str(source["predicate"]).lower())
    target_predicate = _normalize_space(str(target["predicate"]).lower())
    if source_predicate == target_predicate:
        return 1.0
    source_tokens = _tokenize(source_predicate)
    target_tokens = _tokenize(target_predicate)
    if source_tokens and target_tokens and source_tokens[0] == target_tokens[0]:
        return 0.6
    return 0.0


def _symbolic_score(
    source_symbolic: Dict[str, Any],
    target_symbolic: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    subject_overlap = _jaccard(
        _token_set(source_symbolic["subject"]),
        _token_set(target_symbolic["subject"]),
    )
    object_overlap = _jaccard(
        _token_set(source_symbolic["object"]),
        _token_set(target_symbolic["object"]),
    )
    predicate_score = _predicate_score(source_symbolic, target_symbolic)
    category_match = 1.0 if source_symbolic["claim_category"] == target_symbolic["claim_category"] else 0.0
    type_match = 1.0 if source_symbolic["claim_type"] == target_symbolic["claim_type"] else 0.0
    score = (
        0.35 * subject_overlap
        + 0.25 * object_overlap
        + 0.20 * predicate_score
        + 0.15 * category_match
        + 0.05 * type_match
    )
    details = {
        "subject_overlap": _round_score(subject_overlap),
        "object_overlap": _round_score(object_overlap),
        "predicate_score": _round_score(predicate_score),
        "claim_category_match": _round_score(category_match),
        "claim_type_match": _round_score(type_match),
    }
    return _round_score(score), details


def _cosine_similarity(source_vector: List[float], target_vector: List[float]) -> float:
    dot = sum(source * target for source, target in zip(source_vector, target_vector))
    source_norm = math.sqrt(sum(value * value for value in source_vector))
    target_norm = math.sqrt(sum(value * value for value in target_vector))
    if source_norm == 0.0 or target_norm == 0.0:
        return 0.0
    return _round_score(dot / (source_norm * target_norm))


def _phrase_present(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _has_opposition(
    source_symbolic: Dict[str, Any],
    target_symbolic: Dict[str, Any],
) -> Tuple[bool, str]:
    source_text = _normalize_space(
        f"{source_symbolic['predicate']} {source_symbolic['object']}"
    ).lower()
    target_text = _normalize_space(
        f"{target_symbolic['predicate']} {target_symbolic['object']}"
    ).lower()
    for left, right in OPPOSITION_PHRASE_PAIRS:
        left_in_source = _phrase_present(source_text, left)
        right_in_source = _phrase_present(source_text, right)
        left_in_target = _phrase_present(target_text, left)
        right_in_target = _phrase_present(target_text, right)
        if (left_in_source and right_in_target) or (right_in_source and left_in_target):
            return True, f"opposition_terms={left}/{right}"
    return False, "opposition_terms=none"


def _relationship_type(
    source_symbolic: Dict[str, Any],
    target_symbolic: Dict[str, Any],
    embedding_similarity: float,
    score_details: Dict[str, float],
    has_opposition: bool,
) -> str:
    same_category = source_symbolic["claim_category"] == target_symbolic["claim_category"]
    subject_overlap = score_details["subject_overlap"]
    object_overlap = score_details["object_overlap"]
    predicate_score = score_details["predicate_score"]
    if (
        subject_overlap >= 0.90
        and object_overlap >= 0.90
        and predicate_score == 1.0
        and same_category
        and embedding_similarity >= 0.95
    ):
        return "DUPLICATE"
    if (
        subject_overlap >= 0.50
        and (object_overlap >= 0.25 or same_category)
        and has_opposition
    ):
        return "POTENTIAL_CONTRADICTION"
    if (
        same_category
        and not has_opposition
        and embedding_similarity >= 0.70
        and (predicate_score >= 0.60 or object_overlap >= 0.55)
    ):
        return "SUPPORTS"
    symbolic_score = (
        0.35 * subject_overlap
        + 0.25 * object_overlap
        + 0.20 * predicate_score
        + 0.15 * (1.0 if same_category else 0.0)
        + 0.05 * (1.0 if source_symbolic["claim_type"] == target_symbolic["claim_type"] else 0.0)
    )
    if embedding_similarity >= 0.60 or symbolic_score >= 0.35:
        return "RELATED"
    return "UNRELATED"


def _reasoning_summary(
    relationship_type: str,
    symbolic_score: float,
    embedding_similarity: float,
    combined_score: float,
    score_details: Dict[str, float],
    opposition_summary: str,
) -> str:
    return (
        f"{relationship_type} candidate from symbolic_score={symbolic_score}, "
        f"embedding_similarity={embedding_similarity}, combined_score={combined_score}, "
        f"subject_overlap={score_details['subject_overlap']}, "
        f"object_overlap={score_details['object_overlap']}, "
        f"predicate_score={score_details['predicate_score']}, "
        f"claim_category_match={score_details['claim_category_match']}, "
        f"claim_type_match={score_details['claim_type_match']}, "
        f"{opposition_summary}. This is not a proven contradiction."
    )


def _edge_for_pair(
    source: Dict[str, Any],
    target: Dict[str, Any],
    edge_index: int,
) -> Dict[str, Any]:
    source_symbolic = source["symbolic_claim"]
    target_symbolic = target["symbolic_claim"]
    symbolic_score, score_details = _symbolic_score(source_symbolic, target_symbolic)
    embedding_similarity = _cosine_similarity(
        source["embedding_vector"], target["embedding_vector"]
    )
    combined_score = _round_score(0.55 * symbolic_score + 0.45 * embedding_similarity)
    has_opposition, opposition_summary = _has_opposition(source_symbolic, target_symbolic)
    relationship_type = _relationship_type(
        source_symbolic,
        target_symbolic,
        embedding_similarity,
        score_details,
        has_opposition,
    )
    edge = {
        "relationship_edge_id": f"RELATIONSHIP_EDGE_{edge_index:06d}",
        "source_claim_id": source["claim_id"],
        "target_claim_id": target["claim_id"],
        "source_normalized_claim_id": source["normalized_claim_id"],
        "target_normalized_claim_id": target["normalized_claim_id"],
        "relationship_type": relationship_type,
        "symbolic_score": symbolic_score,
        "embedding_similarity": embedding_similarity,
        "combined_score": combined_score,
        "reasoning_summary": _reasoning_summary(
            relationship_type,
            symbolic_score,
            embedding_similarity,
            combined_score,
            score_details,
            opposition_summary,
        ),
        "source_symbolic_claim": source_symbolic,
        "target_symbolic_claim": target_symbolic,
        "source_embedding_hash": source["embedding_hash"],
        "target_embedding_hash": target["embedding_hash"],
        "evidence_anchors": {
            "source": source_symbolic["evidence_anchors"],
            "target": target_symbolic["evidence_anchors"],
        },
        "evidence_hashes": {
            "source": source_symbolic["evidence_hashes"],
            "target": target_symbolic["evidence_hashes"],
            "source_claim_root": source_symbolic["claim_root"],
            "target_claim_root": target_symbolic["claim_root"],
            "source_packet_root": source_symbolic["packet_root"],
            "target_packet_root": target_symbolic["packet_root"],
            "source_normalized_claim_root": source_symbolic["normalized_claim_root"],
            "target_normalized_claim_root": target_symbolic["normalized_claim_root"],
            "source_embedding_hash": source["embedding_hash"],
            "target_embedding_hash": target["embedding_hash"],
            "source_embedding_root": source["embedding_root"],
            "target_embedding_root": target["embedding_root"],
        },
        "edge_root": "",
        "manual_review_required": True,
    }
    edge["edge_root"] = _hash_json(_edge_root_material(edge))
    return edge


def _make_refusal(
    code: str,
    reason: str,
    source: Optional[Dict[str, Any]] = None,
    target: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = source or {}
    target = target or {}
    refusal = {
        "refusal_id": (
            "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_REFUSAL_"
            f"{source.get('normalized_claim_id', 'UNKNOWN_SOURCE')}_"
            f"{target.get('normalized_claim_id', 'UNKNOWN_TARGET')}"
        ),
        "refusal_code": code,
        "refusal_reason": reason,
        "source_claim_id": str(source.get("claim_id") or ""),
        "target_claim_id": str(target.get("claim_id") or ""),
        "source_normalized_claim_id": str(source.get("normalized_claim_id") or ""),
        "target_normalized_claim_id": str(target.get("normalized_claim_id") or ""),
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_edge(edge: Dict[str, Any]) -> None:
    if tuple(edge.keys()) != EDGE_FIELDS:
        raise ValueError("Relationship edge fields changed unexpectedly")
    for field_name in (
        "relationship_edge_id",
        "source_claim_id",
        "target_claim_id",
        "source_normalized_claim_id",
        "target_normalized_claim_id",
        "relationship_type",
        "reasoning_summary",
        "source_embedding_hash",
        "target_embedding_hash",
        "edge_root",
    ):
        _require_nonempty_string(edge, field_name, "RelationshipEdge")
    if edge["relationship_type"] not in RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported relationship_type: {edge['relationship_type']}")
    for score_name in ("symbolic_score", "embedding_similarity", "combined_score"):
        score = edge.get(score_name)
        if not isinstance(score, float) or score < 0.0 or score > 1.0:
            raise ValueError(f"RelationshipEdge.{score_name} must be a float in [0, 1]")
    if edge["source_symbolic_claim"] == edge["target_symbolic_claim"]:
        raise ValueError("RelationshipEdge must connect two distinct symbolic claim records")
    if edge["manual_review_required"] is not True:
        raise ValueError("RelationshipEdge.manual_review_required must remain true")
    if edge["relationship_type"] == "PROVEN_CONTRADICTION":
        raise ValueError("RelationshipEdge must never be PROVEN_CONTRADICTION")
    if edge["source_embedding_hash"] != edge["evidence_hashes"]["source_embedding_hash"]:
        raise ValueError("RelationshipEdge source embedding hash must be preserved")
    if edge["target_embedding_hash"] != edge["evidence_hashes"]["target_embedding_hash"]:
        raise ValueError("RelationshipEdge target embedding hash must be preserved")
    if not _is_nonzero_hash(edge["evidence_hashes"]["source_embedding_root"]):
        raise ValueError("RelationshipEdge must preserve source embedding root")
    if not _is_nonzero_hash(edge["evidence_hashes"]["target_embedding_root"]):
        raise ValueError("RelationshipEdge must preserve target embedding root")
    if edge["edge_root"] != _hash_json(_edge_root_material(edge)):
        raise ValueError(f"edge_root mismatch for {edge['relationship_edge_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Relationship graph refusal fields changed unexpectedly")
    for field_name in ("refusal_id", "refusal_code", "refusal_reason", "refusal_root"):
        _require_nonempty_string(refusal, field_name, "RelationshipGraphRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RelationshipGraphRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("RelationshipGraphRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _validate_inputs(
    embedded_claims: List[Dict[str, Any]],
    normalized_claims: List[Dict[str, Any]],
    embedding_summary: Dict[str, Any],
) -> None:
    _validate_upstream_projection_summary(
        embedding_summary, len(embedded_claims), len(normalized_claims)
    )
    normalized_by_id = {claim["normalized_claim_id"]: claim for claim in normalized_claims}
    if len(normalized_by_id) != len(normalized_claims):
        raise ValueError("normalized_claim_id values must be unique")
    for normalized_claim in normalized_claims:
        validate_normalized_claim(normalized_claim)
    embedded_ids = set()
    for embedded_claim in embedded_claims:
        validate_embedded_claim(embedded_claim, normalized_by_id)
        embedded_id = embedded_claim["embedded_claim_id"]
        if embedded_id in embedded_ids:
            raise ValueError("embedded_claim_id values must be unique")
        embedded_ids.add(embedded_id)


def _build_edges(embedded_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    edge_index = 1
    for source_index, source in enumerate(embedded_claims):
        for target in embedded_claims[source_index + 1 :]:
            edge = _edge_for_pair(source, target, edge_index)
            validate_edge(edge)
            edges.append(edge)
            edge_index += 1
    return edges


def _status_for(mode: str, edge_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if edge_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if edge_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    input_claim_count: int,
    embedded_claim_count: int,
    edges: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    edge_lines = ["- None"]
    if edges:
        edge_lines = []
        for edge in edges[:20]:
            edge_lines.extend(
                [
                    f"- {edge['relationship_edge_id']}: {edge['relationship_type']}",
                    f"  - Source: {edge['source_normalized_claim_id']}",
                    f"  - Target: {edge['target_normalized_claim_id']}",
                    f"  - Symbolic Score: {edge['symbolic_score']}",
                    f"  - Embedding Similarity: {edge['embedding_similarity']}",
                    f"  - Combined Score: {edge['combined_score']}",
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
            "# Dual-Representation Relationship Graph v2",
            "",
            "This lane creates deterministic candidate relationship edges using "
            "symbolic canonical claim fields and embedding geometry. It does not "
            "create final/proven contradictions, proof chains, Word reports, new "
            "claims, inferred facts, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- relationship_graph_status: {status}",
            f"- mode: {mode}",
            f"- input_claim_count: {input_claim_count}",
            f"- embedded_claim_count: {embedded_claim_count}",
            f"- edge_count: {len(edges)}",
            f"- refusal_count: {len(refusals)}",
            f"- relationship_graph_root: {root}",
            "",
            "## First Edges",
            *edge_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Proven Contradiction Count: 0",
            "- Proof Chains Created: 0",
            "- Word Reports Created: 0",
            "- New Claims Created: 0",
            "- Facts Invented: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_dual_representation_relationship_graph(
    mode: str = "dry-run",
    embedded_claims_path: Path = DEFAULT_EMBEDDED_CLAIMS,
    embedding_summary_path: Path = DEFAULT_EMBEDDING_SUMMARY,
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "build-graph"):
        raise ValueError("mode must be dry-run or build-graph")

    embedded_payload = _load_json(embedded_claims_path)
    embedding_summary = _load_json(embedding_summary_path)
    normalized_payload = _load_json(normalized_claims_path)
    embedded_claims = _load_embedded_claims(embedded_payload)
    normalized_claims = _load_normalized_claims(normalized_payload)

    schema = _schema()
    validate_schema(schema)
    _validate_inputs(embedded_claims, normalized_claims, embedding_summary)

    edges: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "build-graph":
        edges = _build_edges(embedded_claims)

    relationship_counts = {
        relationship_type: sum(
            1 for edge in edges if edge["relationship_type"] == relationship_type
        )
        for relationship_type in RELATIONSHIP_TYPES
    }
    edge_roots = [edge["edge_root"] for edge in edges]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    symbolic_roots_preserved_count = len(edges)
    embedding_roots_preserved_count = len(edges)
    root = _hash_json(
        {
            "edge_roots": sorted(edge_roots),
            "refusal_roots": sorted(refusal_roots),
            "facts_invented": 0,
            "new_claims_created": 0,
            "proven_contradiction_count": 0,
            "proof_chains_created": 0,
            "word_reports_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(edges), len(refusals))
    report = _build_report(
        status, mode, len(normalized_claims), len(embedded_claims), edges, refusals, root
    )
    summary = {
        "relationship_graph_status": status,
        "mode": mode,
        "input_claim_count": len(normalized_claims),
        "embedded_claim_count": len(embedded_claims),
        "edge_count": len(edges),
        "refusal_count": len(refusals),
        "duplicate_count": relationship_counts["DUPLICATE"],
        "support_count": relationship_counts["SUPPORTS"],
        "related_count": relationship_counts["RELATED"],
        "potential_contradiction_count": relationship_counts["POTENTIAL_CONTRADICTION"],
        "unrelated_count": relationship_counts["UNRELATED"],
        "symbolic_roots_preserved_count": symbolic_roots_preserved_count,
        "embedding_roots_preserved_count": embedding_roots_preserved_count,
        "facts_invented": 0,
        "new_claims_created": 0,
        "proven_contradiction_count": 0,
        "proof_chains_created": 0,
        "word_reports_created": 0,
        "final_reports_created": 0,
        "edge_roots": edge_roots,
        "refusal_roots": refusal_roots,
        "relationship_graph_schema_hash": _hash_json(schema),
        "relationship_graph_report_hash": _sha256_text(report),
        "relationship_graph_root": root,
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
        "new_claims_created",
        "proven_contradiction_count",
        "proof_chains_created",
        "word_reports_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("relationship graph guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(EDGES_OUTPUT, {"relationship_edges": edges})
    _write_json(REFUSALS_OUTPUT, {"relationship_graph_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "relationship_edges": edges,
        "relationship_graph_refusals": refusals,
        "schema": schema,
        "report": report,
    }
