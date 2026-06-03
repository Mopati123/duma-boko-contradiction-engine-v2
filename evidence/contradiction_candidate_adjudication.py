#!/usr/bin/env python3
"""
Contradiction Candidate Adjudication v2.

Evaluates dual-representation relationship edges and determines whether any
edge should become a manual-review contradiction candidate. This lane does not
create proven contradictions, proof chains, final reports, Word reports, new
claims, inferred facts, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import re


DEFAULT_RELATIONSHIP_EDGES = Path(
    "outputs/dual_representation_relationship_graph/relationship_edges.json"
)
DEFAULT_RELATIONSHIP_SUMMARY = Path(
    "outputs/dual_representation_relationship_graph/relationship_graph_summary.json"
)
DEFAULT_NORMALIZED_CLAIMS = Path(
    "outputs/real_claim_normalization/normalized_claims.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/contradiction_candidate_adjudication")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_candidate_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_candidate_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_candidate_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_candidate_schema.json"

SCHEMA_VERSION = "contradiction_candidate_adjudication_v2"

DRY_RUN_STATUS = "CONTRADICTION_CANDIDATE_ADJUDICATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "CONTRADICTION_CANDIDATE_ADJUDICATION_CANDIDATE"
PARTIAL_STATUS = "CONTRADICTION_CANDIDATE_ADJUDICATION_PARTIAL"
REFUSED_STATUS = "CONTRADICTION_CANDIDATE_ADJUDICATION_REFUSED"

UPSTREAM_GRAPH_STATUSES = (
    "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_CANDIDATE",
    "DUAL_REPRESENTATION_RELATIONSHIP_GRAPH_PARTIAL",
)

GRAPH_RELATIONSHIP_TYPES = (
    "DUPLICATE",
    "SUPPORTS",
    "RELATED",
    "POTENTIAL_CONTRADICTION",
    "UNRELATED",
)

ADJUDICATION_STATUSES = (
    "SUPPORTED",
    "DUPLICATE",
    "RELATED",
    "UNRELATED",
    "CONTRADICTION_CANDIDATE",
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

RELATIONSHIP_EDGE_FIELDS = (
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

RELATIONSHIP_EVIDENCE_HASH_FIELDS = (
    "source",
    "target",
    "source_claim_root",
    "target_claim_root",
    "source_packet_root",
    "target_packet_root",
    "source_normalized_claim_root",
    "target_normalized_claim_root",
    "source_embedding_hash",
    "target_embedding_hash",
    "source_embedding_root",
    "target_embedding_root",
)

ADJUDICATION_FIELDS = (
    "adjudication_id",
    "relationship_edge_id",
    "adjudication_status",
    "source_claim_id",
    "target_claim_id",
    "source_normalized_claim_id",
    "target_normalized_claim_id",
    "source_subject",
    "target_subject",
    "source_predicate",
    "target_predicate",
    "source_object",
    "target_object",
    "subject_overlap",
    "object_overlap",
    "predicate_opposition_detected",
    "opposition_pair",
    "time_context_compatible",
    "time_context_summary",
    "relationship_type",
    "symbolic_score",
    "embedding_similarity",
    "combined_score",
    "adjudication_reasoning",
    "source_symbolic_claim",
    "target_symbolic_claim",
    "source_embedding_hash",
    "target_embedding_hash",
    "evidence_anchors",
    "evidence_hashes",
    "relationship_edge_root",
    "adjudication_root",
    "manual_review_required",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "relationship_edge_id",
    "source_claim_id",
    "target_claim_id",
    "source_normalized_claim_id",
    "target_normalized_claim_id",
    "relationship_type",
    "refusal_code",
    "refusal_reason",
    "evidence_anchors",
    "evidence_hashes",
    "relationship_edge_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_MALFORMED_RELATIONSHIP_EDGE",
    "REFUSED_MISSING_NORMALIZED_CLAIM",
    "REFUSED_SYMBOLIC_PRESERVATION_MISMATCH",
    "REFUSED_MISSING_ANCHORS",
    "REFUSED_MISSING_HASHES",
    "REFUSED_MISSING_ROOTS",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
    "REFUSED_PROVEN_CONTRADICTION_ATTEMPT",
)

OPPOSITION_PHRASE_PAIRS = (
    ("increase", "reduce"),
    ("approved", "rejected"),
    ("implemented", "failed"),
    ("is", "is not"),
    ("has", "has not"),
    ("will", "will not"),
    ("supports", "opposes"),
)

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


def _normalized_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("normalized_claim_root", None)
    return material


def _edge_root_material(edge: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(edge)
    material.pop("edge_root", None)
    return material


def _adjudication_root_material(adjudication: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(adjudication)
    material.pop("adjudication_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contradiction_candidate_adjudication_only": True,
        "modes": ["dry-run", "adjudicate"],
        "upstream_graph_statuses": list(UPSTREAM_GRAPH_STATUSES),
        "graph_relationship_types": list(GRAPH_RELATIONSHIP_TYPES),
        "adjudication_statuses": list(ADJUDICATION_STATUSES),
        "adjudication_fields": list(ADJUDICATION_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "relationship_edge_fields": list(RELATIONSHIP_EDGE_FIELDS),
        "symbolic_claim_fields": list(SYMBOLIC_CLAIM_FIELDS),
        "opposition_phrase_pairs": [
            {"left": left, "right": right} for left, right in OPPOSITION_PHRASE_PAIRS
        ],
        "classification_order": [
            "DUPLICATE",
            "CONTRADICTION_CANDIDATE",
            "SUPPORTED",
            "RELATED",
            "UNRELATED",
        ],
        "contradiction_candidate_requirements": {
            "same_or_near_same_subject_token_overlap": 0.90,
            "same_or_strongly_overlapping_object_token_overlap": 0.55,
            "explicit_opposing_predicate_or_object_phrase_pair": True,
            "compatible_time_context_where_available": True,
        },
        "prohibited_outputs": {
            "proven_contradiction_count": 0,
            "proof_chains_created": 0,
            "final_contradiction_certifications_created": 0,
            "final_reports_created": 0,
            "word_reports_created": 0,
            "new_claims_created": 0,
            "facts_invented": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "adjudication_root": "sha256 over adjudicated relationship excluding adjudication_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "contradiction_candidate_root": (
                "sha256 over sorted adjudication roots, candidate roots, refusal roots, "
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
        raise ValueError("contradiction candidate schema_version changed unexpectedly")
    if schema.get("adjudication_statuses") != list(ADJUDICATION_STATUSES):
        raise ValueError("contradiction candidate adjudication statuses changed unexpectedly")
    if schema.get("adjudication_fields") != list(ADJUDICATION_FIELDS):
        raise ValueError("contradiction candidate adjudication fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("contradiction candidate refusal fields changed unexpectedly")


def _load_relationship_edges(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("relationship_edges.json is missing")
    edges = payload.get("relationship_edges")
    if not isinstance(edges, list):
        raise ValueError("relationship_edges must be a list")
    return edges


def _load_normalized_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("normalized_claims.json is missing")
    claims = payload.get("normalized_claims")
    if not isinstance(claims, list):
        raise ValueError("normalized_claims must be a list")
    return claims


def _has_line_anchor(anchors: Dict[str, Any]) -> bool:
    start = _safe_int(anchors.get("text_line_start") or anchors.get("transcript_start_line"))
    end = _safe_int(anchors.get("text_line_end") or anchors.get("transcript_end_line"))
    return start > 0 and end >= start


def _has_timestamp_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("timestamp_start")) and bool(anchors.get("timestamp_end"))


def _has_anchor(anchors: Dict[str, Any]) -> bool:
    return _has_line_anchor(anchors) or _has_timestamp_anchor(anchors)


def _expected_symbolic_claim(normalized_claim: Dict[str, Any]) -> Dict[str, Any]:
    return {field_name: normalized_claim[field_name] for field_name in SYMBOLIC_CLAIM_FIELDS}


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _phrase_present(text: str, phrase: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _pair_presence(text: str, left: str, right: str) -> Tuple[bool, bool]:
    normalized = _normalize_space(text).lower()
    right_present = _phrase_present(normalized, right)
    left_present = _phrase_present(normalized, left)
    if right.startswith(left + " "):
        left_present = left_present and not right_present
    return left_present, right_present


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
        left_in_source, right_in_source = _pair_presence(source_text, left, right)
        left_in_target, right_in_target = _pair_presence(target_text, left, right)
        if (left_in_source and right_in_target) or (right_in_source and left_in_target):
            return True, f"{left}/{right}"
    return False, EMPTY_CONTEXT


def _time_context_compatible(
    source_symbolic: Dict[str, Any],
    target_symbolic: Dict[str, Any],
) -> Tuple[bool, str]:
    source_time = _normalize_space(str(source_symbolic.get("time_reference") or ""))
    target_time = _normalize_space(str(target_symbolic.get("time_reference") or ""))
    if not source_time and not target_time:
        return True, "time_context=not_available"
    if not source_time or not target_time:
        return True, "time_context=partially_available"
    if source_time.lower() == target_time.lower():
        return True, f"time_context=exact:{source_time}"
    source_tokens = _token_set(source_time)
    target_tokens = _token_set(target_time)
    years_source = {token for token in source_tokens if re.fullmatch(r"[12][0-9]{3}", token)}
    years_target = {token for token in target_tokens if re.fullmatch(r"[12][0-9]{3}", token)}
    if years_source and years_target and years_source & years_target:
        return True, "time_context=shared_year"
    if _jaccard(source_tokens, target_tokens) >= 0.50:
        return True, "time_context=token_overlap"
    return False, "time_context=conflicting_explicit_references"


def _validate_upstream_graph_summary(summary: Dict[str, Any], edge_count: int) -> None:
    if not summary:
        raise ValueError("relationship_graph_summary.json is missing")
    if summary.get("relationship_graph_status") not in UPSTREAM_GRAPH_STATUSES:
        raise ValueError("relationship graph upstream status is invalid")
    if summary.get("edge_count") != edge_count:
        raise ValueError("relationship edge count does not match graph summary")
    if summary.get("proven_contradiction_count") != 0:
        raise ValueError("upstream proven_contradiction_count must remain 0")
    for counter_name in (
        "facts_invented",
        "new_claims_created",
        "proof_chains_created",
        "word_reports_created",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(summary):
        raise ValueError("relationship graph guardrails must remain closed")
    summary_count_map = {
        "DUPLICATE": summary.get("duplicate_count"),
        "SUPPORTS": summary.get("support_count"),
        "RELATED": summary.get("related_count"),
        "POTENTIAL_CONTRADICTION": summary.get("potential_contradiction_count"),
        "UNRELATED": summary.get("unrelated_count"),
    }
    if any(not isinstance(value, int) for value in summary_count_map.values()):
        raise ValueError("relationship graph relationship counts must be integers")
    if sum(summary_count_map.values()) != edge_count:
        raise ValueError("relationship graph relationship counts must sum to edge_count")


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


def validate_relationship_edge(edge: Dict[str, Any]) -> None:
    if set(edge.keys()) != set(RELATIONSHIP_EDGE_FIELDS):
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
    if edge["relationship_type"] == "PROVEN_CONTRADICTION":
        raise ValueError("RelationshipEdge must never be PROVEN_CONTRADICTION")
    if edge["relationship_type"] not in GRAPH_RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported relationship_type: {edge['relationship_type']}")
    for score_name in ("symbolic_score", "embedding_similarity", "combined_score"):
        score = edge.get(score_name)
        if not isinstance(score, float) or score < 0.0 or score > 1.0:
            raise ValueError(f"RelationshipEdge.{score_name} must be a float in [0, 1]")
    if edge.get("manual_review_required") is not True:
        raise ValueError("RelationshipEdge.manual_review_required must remain true")
    if not isinstance(edge.get("source_symbolic_claim"), dict):
        raise ValueError("RelationshipEdge.source_symbolic_claim must be a dict")
    if not isinstance(edge.get("target_symbolic_claim"), dict):
        raise ValueError("RelationshipEdge.target_symbolic_claim must be a dict")
    anchors = edge.get("evidence_anchors")
    if not isinstance(anchors, dict) or set(anchors.keys()) != {"source", "target"}:
        raise ValueError("RelationshipEdge.evidence_anchors fields changed unexpectedly")
    hashes = edge.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(
        RELATIONSHIP_EVIDENCE_HASH_FIELDS
    ):
        raise ValueError("RelationshipEdge.evidence_hashes fields changed unexpectedly")
    if not isinstance(hashes.get("source"), dict) or not isinstance(hashes.get("target"), dict):
        raise ValueError("RelationshipEdge source/target evidence hashes must be dicts")
    for field_name in (
        "source_claim_root",
        "target_claim_root",
        "source_packet_root",
        "target_packet_root",
        "source_normalized_claim_root",
        "target_normalized_claim_root",
        "source_embedding_hash",
        "target_embedding_hash",
        "source_embedding_root",
        "target_embedding_root",
    ):
        if not _is_nonzero_hash(hashes.get(field_name)):
            raise ValueError(f"RelationshipEdge.evidence_hashes.{field_name} must be non-zero")
    if edge["source_embedding_hash"] != hashes["source_embedding_hash"]:
        raise ValueError("RelationshipEdge source embedding hash must be preserved")
    if edge["target_embedding_hash"] != hashes["target_embedding_hash"]:
        raise ValueError("RelationshipEdge target embedding hash must be preserved")
    if edge["edge_root"] != _hash_json(_edge_root_material(edge)):
        raise ValueError(f"edge_root mismatch for {edge['relationship_edge_id']}")


def _validate_symbolic_preservation(
    edge: Dict[str, Any],
    normalized_claims_by_id: Dict[str, Dict[str, Any]],
) -> None:
    source_id = edge["source_normalized_claim_id"]
    target_id = edge["target_normalized_claim_id"]
    if source_id not in normalized_claims_by_id or target_id not in normalized_claims_by_id:
        raise KeyError("edge references a missing normalized claim")
    source_claim = normalized_claims_by_id[source_id]
    target_claim = normalized_claims_by_id[target_id]
    validate_normalized_claim(source_claim)
    validate_normalized_claim(target_claim)
    expected_source = _expected_symbolic_claim(source_claim)
    expected_target = _expected_symbolic_claim(target_claim)
    if edge["source_symbolic_claim"] != expected_source:
        raise ValueError("source symbolic claim does not match normalized claim exactly")
    if edge["target_symbolic_claim"] != expected_target:
        raise ValueError("target symbolic claim does not match normalized claim exactly")
    if edge["source_claim_id"] != source_claim["claim_id"]:
        raise ValueError("RelationshipEdge source claim_id must match normalized claim")
    if edge["target_claim_id"] != target_claim["claim_id"]:
        raise ValueError("RelationshipEdge target claim_id must match normalized claim")
    hashes = edge["evidence_hashes"]
    if hashes["source_claim_root"] != source_claim["claim_root"]:
        raise ValueError("RelationshipEdge source claim root must be preserved")
    if hashes["target_claim_root"] != target_claim["claim_root"]:
        raise ValueError("RelationshipEdge target claim root must be preserved")
    if hashes["source_packet_root"] != source_claim["packet_root"]:
        raise ValueError("RelationshipEdge source packet root must be preserved")
    if hashes["target_packet_root"] != target_claim["packet_root"]:
        raise ValueError("RelationshipEdge target packet root must be preserved")
    if hashes["source_normalized_claim_root"] != source_claim["normalized_claim_root"]:
        raise ValueError("RelationshipEdge source normalized claim root must be preserved")
    if hashes["target_normalized_claim_root"] != target_claim["normalized_claim_root"]:
        raise ValueError("RelationshipEdge target normalized claim root must be preserved")


def _make_refusal(
    edge: Optional[Dict[str, Any]],
    code: str,
    reason: str,
    fallback_index: int,
) -> Dict[str, Any]:
    edge = edge or {}
    refusal_id_source = str(edge.get("relationship_edge_id") or f"UNKNOWN_{fallback_index:06d}")
    refusal = {
        "refusal_id": f"CONTRADICTION_CANDIDATE_ADJUDICATION_REFUSAL_{refusal_id_source}",
        "relationship_edge_id": str(edge.get("relationship_edge_id") or ""),
        "source_claim_id": str(edge.get("source_claim_id") or ""),
        "target_claim_id": str(edge.get("target_claim_id") or ""),
        "source_normalized_claim_id": str(edge.get("source_normalized_claim_id") or ""),
        "target_normalized_claim_id": str(edge.get("target_normalized_claim_id") or ""),
        "relationship_type": str(edge.get("relationship_type") or ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "evidence_anchors": edge.get("evidence_anchors") if isinstance(edge.get("evidence_anchors"), dict) else {},
        "evidence_hashes": edge.get("evidence_hashes") if isinstance(edge.get("evidence_hashes"), dict) else {},
        "relationship_edge_root": str(edge.get("edge_root") or ""),
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _status_for(mode: str, adjudication_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if adjudication_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if adjudication_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _adjudication_status(
    edge: Dict[str, Any],
    subject_overlap: float,
    object_overlap: float,
    has_opposition: bool,
    time_compatible: bool,
) -> str:
    relationship_type = edge["relationship_type"]
    same_subject = subject_overlap >= 0.90
    same_or_overlapping_object = object_overlap >= 0.55
    if relationship_type == "DUPLICATE":
        return "DUPLICATE"
    if same_subject and same_or_overlapping_object and has_opposition and time_compatible:
        return "CONTRADICTION_CANDIDATE"
    if relationship_type == "SUPPORTS" and not has_opposition:
        return "SUPPORTED"
    if relationship_type in ("RELATED", "POTENTIAL_CONTRADICTION"):
        return "RELATED"
    if relationship_type == "SUPPORTS":
        return "RELATED"
    return "UNRELATED"


def _adjudication_reasoning(
    adjudication_status: str,
    subject_overlap: float,
    object_overlap: float,
    opposition_pair: str,
    time_summary: str,
    edge: Dict[str, Any],
) -> str:
    opposition_text = opposition_pair or "none"
    return (
        f"{adjudication_status} from relationship_type={edge['relationship_type']}, "
        f"subject_overlap={subject_overlap}, object_overlap={object_overlap}, "
        f"opposition_pair={opposition_text}, {time_summary}, "
        f"symbolic_score={edge['symbolic_score']}, "
        f"embedding_similarity={edge['embedding_similarity']}, "
        f"combined_score={edge['combined_score']}. "
        "This is not a proven contradiction."
    )


def _adjudication_for_edge(edge: Dict[str, Any], adjudication_index: int) -> Dict[str, Any]:
    source_symbolic = edge["source_symbolic_claim"]
    target_symbolic = edge["target_symbolic_claim"]
    subject_overlap = _round_score(
        _jaccard(_token_set(source_symbolic["subject"]), _token_set(target_symbolic["subject"]))
    )
    object_overlap = _round_score(
        _jaccard(_token_set(source_symbolic["object"]), _token_set(target_symbolic["object"]))
    )
    has_opposition, opposition_pair = _has_opposition(source_symbolic, target_symbolic)
    time_compatible, time_summary = _time_context_compatible(source_symbolic, target_symbolic)
    status = _adjudication_status(
        edge, subject_overlap, object_overlap, has_opposition, time_compatible
    )
    adjudication = {
        "adjudication_id": f"CONTRADICTION_ADJUDICATION_{adjudication_index:06d}",
        "relationship_edge_id": edge["relationship_edge_id"],
        "adjudication_status": status,
        "source_claim_id": edge["source_claim_id"],
        "target_claim_id": edge["target_claim_id"],
        "source_normalized_claim_id": edge["source_normalized_claim_id"],
        "target_normalized_claim_id": edge["target_normalized_claim_id"],
        "source_subject": source_symbolic["subject"],
        "target_subject": target_symbolic["subject"],
        "source_predicate": source_symbolic["predicate"],
        "target_predicate": target_symbolic["predicate"],
        "source_object": source_symbolic["object"],
        "target_object": target_symbolic["object"],
        "subject_overlap": subject_overlap,
        "object_overlap": object_overlap,
        "predicate_opposition_detected": has_opposition,
        "opposition_pair": opposition_pair,
        "time_context_compatible": time_compatible,
        "time_context_summary": time_summary,
        "relationship_type": edge["relationship_type"],
        "symbolic_score": edge["symbolic_score"],
        "embedding_similarity": edge["embedding_similarity"],
        "combined_score": edge["combined_score"],
        "adjudication_reasoning": _adjudication_reasoning(
            status, subject_overlap, object_overlap, opposition_pair, time_summary, edge
        ),
        "source_symbolic_claim": source_symbolic,
        "target_symbolic_claim": target_symbolic,
        "source_embedding_hash": edge["source_embedding_hash"],
        "target_embedding_hash": edge["target_embedding_hash"],
        "evidence_anchors": edge["evidence_anchors"],
        "evidence_hashes": dict(edge["evidence_hashes"]),
        "relationship_edge_root": edge["edge_root"],
        "adjudication_root": "",
        "manual_review_required": True,
    }
    adjudication["evidence_hashes"]["relationship_edge_root"] = edge["edge_root"]
    adjudication["adjudication_root"] = _hash_json(
        _adjudication_root_material(adjudication)
    )
    return adjudication


def validate_adjudication(adjudication: Dict[str, Any]) -> None:
    if tuple(adjudication.keys()) != ADJUDICATION_FIELDS:
        raise ValueError("Contradiction adjudication fields changed unexpectedly")
    for field_name in (
        "adjudication_id",
        "relationship_edge_id",
        "adjudication_status",
        "source_claim_id",
        "target_claim_id",
        "source_normalized_claim_id",
        "target_normalized_claim_id",
        "source_subject",
        "target_subject",
        "source_predicate",
        "target_predicate",
        "source_object",
        "target_object",
        "relationship_type",
        "adjudication_reasoning",
        "source_embedding_hash",
        "target_embedding_hash",
        "relationship_edge_root",
        "adjudication_root",
    ):
        _require_nonempty_string(adjudication, field_name, "ContradictionAdjudication")
    if adjudication["adjudication_status"] not in ADJUDICATION_STATUSES:
        raise ValueError(f"Unsupported adjudication_status: {adjudication['adjudication_status']}")
    if adjudication["adjudication_status"] == "PROVEN_CONTRADICTION":
        raise ValueError("ContradictionAdjudication must never be PROVEN_CONTRADICTION")
    for score_name in ("subject_overlap", "object_overlap", "symbolic_score", "embedding_similarity", "combined_score"):
        score = adjudication.get(score_name)
        if not isinstance(score, float) or score < 0.0 or score > 1.0:
            raise ValueError(f"ContradictionAdjudication.{score_name} must be in [0, 1]")
    if not isinstance(adjudication.get("predicate_opposition_detected"), bool):
        raise ValueError("ContradictionAdjudication.predicate_opposition_detected must be bool")
    if not isinstance(adjudication.get("time_context_compatible"), bool):
        raise ValueError("ContradictionAdjudication.time_context_compatible must be bool")
    if adjudication["manual_review_required"] is not True:
        raise ValueError("ContradictionAdjudication.manual_review_required must remain true")
    hashes = adjudication.get("evidence_hashes")
    if not isinstance(hashes, dict):
        raise ValueError("ContradictionAdjudication.evidence_hashes must be a dict")
    for field_name in (
        "source_claim_root",
        "target_claim_root",
        "source_packet_root",
        "target_packet_root",
        "source_normalized_claim_root",
        "target_normalized_claim_root",
        "source_embedding_hash",
        "target_embedding_hash",
        "source_embedding_root",
        "target_embedding_root",
        "relationship_edge_root",
    ):
        if not _is_nonzero_hash(hashes.get(field_name)):
            raise ValueError(f"ContradictionAdjudication.evidence_hashes.{field_name} missing")
    if adjudication["relationship_edge_root"] != hashes["relationship_edge_root"]:
        raise ValueError("ContradictionAdjudication relationship edge root must be preserved")
    if adjudication["source_embedding_hash"] != hashes["source_embedding_hash"]:
        raise ValueError("ContradictionAdjudication source embedding hash must be preserved")
    if adjudication["target_embedding_hash"] != hashes["target_embedding_hash"]:
        raise ValueError("ContradictionAdjudication target embedding hash must be preserved")
    if adjudication["adjudication_root"] != _hash_json(
        _adjudication_root_material(adjudication)
    ):
        raise ValueError(f"adjudication_root mismatch for {adjudication['adjudication_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Contradiction candidate refusal fields changed unexpectedly")
    for field_name in ("refusal_id", "refusal_code", "refusal_reason", "refusal_root"):
        _require_nonempty_string(refusal, field_name, "ContradictionCandidateRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("ContradictionCandidateRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("ContradictionCandidateRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _build_normalized_claim_lookup(
    normalized_claims: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    normalized_claims_by_id: Dict[str, Dict[str, Any]] = {}
    for claim in normalized_claims:
        normalized_claim_id = str(claim.get("normalized_claim_id") or "")
        if not normalized_claim_id:
            raise ValueError("normalized_claim_id values must be non-empty")
        if normalized_claim_id in normalized_claims_by_id:
            raise ValueError("normalized_claim_id values must be unique")
        normalized_claims_by_id[normalized_claim_id] = claim
    return normalized_claims_by_id


def _validate_inputs(
    edges: List[Dict[str, Any]],
    relationship_summary: Dict[str, Any],
    normalized_claims: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    _validate_upstream_graph_summary(relationship_summary, len(edges))
    normalized_claims_by_id = _build_normalized_claim_lookup(normalized_claims)
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("relationship_edges must contain dict records")
    return normalized_claims_by_id


def _refusal_code_for_error(error: Exception) -> str:
    message = str(error)
    if isinstance(error, KeyError):
        return "REFUSED_MISSING_NORMALIZED_CLAIM"
    if "PROVEN_CONTRADICTION" in message:
        return "REFUSED_PROVEN_CONTRADICTION_ATTEMPT"
    if "anchor" in message.lower():
        return "REFUSED_MISSING_ANCHORS"
    if "hash" in message.lower():
        return "REFUSED_MISSING_HASHES"
    if "root" in message.lower():
        return "REFUSED_MISSING_ROOTS"
    if "symbolic" in message.lower() or "preserv" in message.lower():
        return "REFUSED_SYMBOLIC_PRESERVATION_MISMATCH"
    return "REFUSED_MALFORMED_RELATIONSHIP_EDGE"


def _build_adjudications(
    edges: List[Dict[str, Any]],
    normalized_claims_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    adjudications: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    adjudication_index = 1
    for edge_index, edge in enumerate(edges, start=1):
        try:
            validate_relationship_edge(edge)
            _validate_symbolic_preservation(edge, normalized_claims_by_id)
            adjudication = _adjudication_for_edge(edge, adjudication_index)
            validate_adjudication(adjudication)
            adjudications.append(adjudication)
            adjudication_index += 1
        except Exception as error:  # Keep invalid edges out of candidate output.
            refusal = _make_refusal(
                edge if isinstance(edge, dict) else {},
                _refusal_code_for_error(error),
                str(error),
                edge_index,
            )
            validate_refusal(refusal)
            refusals.append(refusal)
    return adjudications, refusals


def _build_report(
    status: str,
    mode: str,
    input_edge_count: int,
    adjudications: List[Dict[str, Any]],
    contradiction_candidates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    candidate_lines = ["- None"]
    if contradiction_candidates:
        candidate_lines = []
        for candidate in contradiction_candidates[:20]:
            candidate_lines.extend(
                [
                    f"- {candidate['adjudication_id']}: {candidate['relationship_edge_id']}",
                    f"  - Source: {candidate['source_normalized_claim_id']}",
                    f"  - Target: {candidate['target_normalized_claim_id']}",
                    f"  - Opposition Pair: {candidate['opposition_pair']}",
                    f"  - Subject Overlap: {candidate['subject_overlap']}",
                    f"  - Object Overlap: {candidate['object_overlap']}",
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
            "# Contradiction Candidate Adjudication v2",
            "",
            "This lane adjudicates relationship graph edges into manual-review "
            "relationship statuses. It does not create proven contradictions, "
            "proof chains, final reports, Word reports, new claims, inferred "
            "facts, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- contradiction_candidate_status: {status}",
            f"- mode: {mode}",
            f"- input_edge_count: {input_edge_count}",
            f"- adjudicated_edge_count: {len(adjudications)}",
            f"- candidate_contradiction_count: {len(contradiction_candidates)}",
            f"- refusal_count: {len(refusals)}",
            f"- contradiction_candidate_root: {root}",
            "",
            "## First Contradiction Candidates",
            *candidate_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Proven Contradiction Count: 0",
            "- Proof Chains Created: 0",
            "- Final Contradiction Certifications Created: 0",
            "- Final Reports Created: 0",
            "- Word Reports Created: 0",
            "- New Claims Created: 0",
            "- Facts Invented: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_contradiction_candidate_adjudication(
    mode: str = "dry-run",
    relationship_edges_path: Path = DEFAULT_RELATIONSHIP_EDGES,
    relationship_summary_path: Path = DEFAULT_RELATIONSHIP_SUMMARY,
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "adjudicate"):
        raise ValueError("mode must be dry-run or adjudicate")

    relationship_edges_payload = _load_json(relationship_edges_path)
    relationship_summary = _load_json(relationship_summary_path)
    normalized_claims_payload = _load_json(normalized_claims_path)

    relationship_edges = _load_relationship_edges(relationship_edges_payload)
    normalized_claims = _load_normalized_claims(normalized_claims_payload)

    schema = _schema()
    validate_schema(schema)
    normalized_claims_by_id = _validate_inputs(
        relationship_edges, relationship_summary, normalized_claims
    )

    adjudications: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "adjudicate":
        adjudications, refusals = _build_adjudications(
            relationship_edges, normalized_claims_by_id
        )

    contradiction_candidates = [
        adjudication
        for adjudication in adjudications
        if adjudication["adjudication_status"] == "CONTRADICTION_CANDIDATE"
    ]
    status_counts = {
        adjudication_status: sum(
            1
            for adjudication in adjudications
            if adjudication["adjudication_status"] == adjudication_status
        )
        for adjudication_status in ADJUDICATION_STATUSES
    }
    adjudication_roots = [adjudication["adjudication_root"] for adjudication in adjudications]
    candidate_roots = [
        adjudication["adjudication_root"] for adjudication in contradiction_candidates
    ]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    anchors_preserved_count = len(adjudications)
    hashes_preserved_count = len(adjudications)
    roots_preserved_count = len(adjudications)
    embedding_hashes_preserved_count = len(adjudications)
    relationship_roots_preserved_count = len(adjudications)
    root = _hash_json(
        {
            "adjudication_roots": sorted(adjudication_roots),
            "candidate_roots": sorted(candidate_roots),
            "refusal_roots": sorted(refusal_roots),
            "proven_contradiction_count": 0,
            "proof_chains_created": 0,
            "final_contradiction_certifications_created": 0,
            "final_reports_created": 0,
            "word_reports_created": 0,
            "new_claims_created": 0,
            "facts_invented": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(adjudications), len(refusals))
    report = _build_report(
        status,
        mode,
        len(relationship_edges),
        adjudications,
        contradiction_candidates,
        refusals,
        root,
    )
    summary = {
        "contradiction_candidate_status": status,
        "mode": mode,
        "input_edge_count": len(relationship_edges),
        "adjudicated_edge_count": len(adjudications),
        "candidate_contradiction_count": len(contradiction_candidates),
        "duplicate_count": status_counts["DUPLICATE"],
        "related_count": status_counts["RELATED"],
        "supported_count": status_counts["SUPPORTED"],
        "unrelated_count": status_counts["UNRELATED"],
        "refusal_count": len(refusals),
        "anchors_preserved_count": anchors_preserved_count,
        "hashes_preserved_count": hashes_preserved_count,
        "roots_preserved_count": roots_preserved_count,
        "embedding_hashes_preserved_count": embedding_hashes_preserved_count,
        "relationship_roots_preserved_count": relationship_roots_preserved_count,
        "adjudication_roots": adjudication_roots,
        "candidate_roots": candidate_roots,
        "refusal_roots": refusal_roots,
        "contradiction_candidate_schema_hash": _hash_json(schema),
        "contradiction_candidate_report_hash": _sha256_text(report),
        "contradiction_candidate_root": root,
        "proven_contradiction_count": 0,
        "proof_chains_created": 0,
        "final_contradiction_certifications_created": 0,
        "final_reports_created": 0,
        "word_reports_created": 0,
        "new_claims_created": 0,
        "facts_invented": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "proven_contradiction_count",
        "proof_chains_created",
        "final_contradiction_certifications_created",
        "final_reports_created",
        "word_reports_created",
        "new_claims_created",
        "facts_invented",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("contradiction candidate guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(
        CANDIDATES_OUTPUT,
        {
            "adjudicated_relationships": adjudications,
            "contradiction_candidates": contradiction_candidates,
        },
    )
    _write_json(REFUSALS_OUTPUT, {"contradiction_candidate_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "adjudicated_relationships": adjudications,
        "contradiction_candidates": contradiction_candidates,
        "contradiction_candidate_refusals": refusals,
        "schema": schema,
        "report": report,
    }
