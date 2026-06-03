#!/usr/bin/env python3
"""
Canonical Claim Embedding Projection v2.

Projects normalized canonical claims into deterministic local vector space while
preserving the symbolic claim structure. This lane does not call external
embedding APIs, infer facts, create relationships, detect contradictions,
generate final reports, mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import json
import math
import re


DEFAULT_NORMALIZED_CLAIMS = Path(
    "outputs/real_claim_normalization/normalized_claims.json"
)
DEFAULT_NORMALIZATION_SUMMARY = Path(
    "outputs/real_claim_normalization/real_claim_normalization_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/canonical_claim_embedding_projection")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "embedding_projection_summary.json"
EMBEDDED_CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "embedded_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "embedding_projection_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "embedding_projection_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "embedding_projection_schema.json"

SCHEMA_VERSION = "canonical_claim_embedding_projection_v2"

DRY_RUN_STATUS = "CANONICAL_CLAIM_EMBEDDING_PROJECTION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "CANONICAL_CLAIM_EMBEDDING_PROJECTION_CANDIDATE"
PARTIAL_STATUS = "CANONICAL_CLAIM_EMBEDDING_PROJECTION_PARTIAL"
REFUSED_STATUS = "CANONICAL_CLAIM_EMBEDDING_PROJECTION_REFUSED"

UPSTREAM_STATUSES = (
    "REAL_CLAIM_NORMALIZATION_CANDIDATE",
    "REAL_CLAIM_NORMALIZATION_PARTIAL",
)

EMBEDDING_METHOD = "deterministic_hash_bow_l2_v1"
EMBEDDING_DIMENSION = 256
EMBEDDING_ROUND_DIGITS = 12

NORMALIZATION_STATUS = "REAL_NORMALIZED_CLAIM_REQUIRES_MANUAL_REVIEW"

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

REFUSAL_FIELDS = (
    "refusal_id",
    "normalized_claim_id",
    "claim_id",
    "refusal_code",
    "refusal_reason",
    "canonical_text",
    "symbolic_claim",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_MALFORMED_NORMALIZED_CLAIM",
    "REFUSED_EMPTY_CANONICAL_TEXT",
    "REFUSED_NON_VECTORIZABLE_CANONICAL_TEXT",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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


def _embedding_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("embedding_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_claim_embedding_projection_only": True,
        "modes": ["dry-run", "project"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "normalized_claim_fields": list(NORMALIZED_CLAIM_FIELDS),
        "symbolic_claim_fields": list(SYMBOLIC_CLAIM_FIELDS),
        "embedded_claim_fields": list(EMBEDDED_CLAIM_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "embedding_method": EMBEDDING_METHOD,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_round_digits": EMBEDDING_ROUND_DIGITS,
        "embedding_rule": (
            "Tokenize canonical_text with [a-z0-9]+, hash each lowercased token "
            "into one of 256 buckets using sha256(token) % 256, accumulate term "
            "counts, L2-normalize, and round deterministically."
        ),
        "symbolic_preservation_rule": (
            "Symbolic claims are nested unchanged; vector geometry is additive "
            "and does not replace subject, predicate, object, anchors, hashes, "
            "or roots."
        ),
        "prohibited_outputs": {
            "facts_invented": 0,
            "relationships_created": 0,
            "contradictions_created": 0,
            "final_reports_created": 0,
            "conclusions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "embedding_hash": (
                "sha256 over method, dimension, canonical_text, and embedding_vector"
            ),
            "embedding_root": "sha256 over embedded claim excluding embedding_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "embedding_projection_root": (
                "sha256 over sorted embedding roots, sorted refusal roots, and closed flags"
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
        raise ValueError("embedding projection schema_version changed unexpectedly")
    if schema.get("normalized_claim_fields") != list(NORMALIZED_CLAIM_FIELDS):
        raise ValueError("embedding projection normalized_claim_fields changed unexpectedly")
    if schema.get("embedded_claim_fields") != list(EMBEDDED_CLAIM_FIELDS):
        raise ValueError("embedding projection embedded_claim_fields changed unexpectedly")
    if schema.get("embedding_dimension") != EMBEDDING_DIMENSION:
        raise ValueError("embedding projection dimension changed unexpectedly")
    if schema.get("embedding_method") != EMBEDDING_METHOD:
        raise ValueError("embedding projection method changed unexpectedly")


def _load_normalized_claims(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("normalized_claims.json is missing")
    claims = payload.get("normalized_claims")
    if not isinstance(claims, list):
        raise ValueError("normalized_claims must be a list")
    return claims


def _validate_upstream_summary(summary: Dict[str, Any], normalized_count: int) -> None:
    if not summary:
        raise ValueError("real_claim_normalization_summary.json is missing")
    if summary.get("normalization_status") not in UPSTREAM_STATUSES:
        raise ValueError("real claim normalization upstream status is invalid")
    if summary.get("normalized_claim_count") != normalized_count:
        raise ValueError("normalized claim count does not match normalization summary")
    for counter_name in (
        "facts_invented",
        "embeddings_created",
        "similarity_scores_created",
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
        raise ValueError("real claim normalization guardrails must remain closed")


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
    if claim["normalization_status"] != NORMALIZATION_STATUS:
        raise ValueError("NormalizedClaim.normalization_status changed unexpectedly")
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


def _canonical_text(claim: Dict[str, Any]) -> str:
    parts = [claim["subject"], claim["predicate"], claim["object"]]
    if claim.get("time_reference"):
        parts.append(f"time: {claim['time_reference']}")
    if claim.get("location_reference"):
        parts.append(f"location: {claim['location_reference']}")
    return _normalize_space(" ".join(parts))


def _tokenize(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _embedding_vector(canonical_text: str) -> List[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in _tokenize(canonical_text):
        bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        vector[bucket % EMBEDDING_DIMENSION] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [round(value / norm, EMBEDDING_ROUND_DIGITS) for value in vector]


def _symbolic_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {field_name: claim[field_name] for field_name in SYMBOLIC_CLAIM_FIELDS}


def _embedding_hash(canonical_text: str, vector: List[float]) -> str:
    return _hash_json(
        {
            "embedding_method": EMBEDDING_METHOD,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "canonical_text": canonical_text,
            "embedding_vector": vector,
        }
    )


def _make_embedded_claim(
    normalized_claim: Dict[str, Any],
    embedded_index: int,
) -> Dict[str, Any]:
    canonical_text = _canonical_text(normalized_claim)
    vector = _embedding_vector(canonical_text)
    embedded = {
        "embedded_claim_id": f"EMBEDDED_CANONICAL_CLAIM_{embedded_index:04d}",
        "normalized_claim_id": normalized_claim["normalized_claim_id"],
        "claim_id": normalized_claim["claim_id"],
        "canonical_text": canonical_text,
        "symbolic_claim": _symbolic_claim(normalized_claim),
        "embedding_vector": vector,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_method": EMBEDDING_METHOD,
        "embedding_hash": _embedding_hash(canonical_text, vector),
        "embedding_root": "",
        "manual_review_required": True,
    }
    embedded["embedding_root"] = _hash_json(_embedding_root_material(embedded))
    return embedded


def _empty_symbolic_claim(raw_claim: Dict[str, Any]) -> Dict[str, Any]:
    symbolic: Dict[str, Any] = {}
    for field_name in SYMBOLIC_CLAIM_FIELDS:
        value = raw_claim.get(field_name, EMPTY_CONTEXT)
        if field_name in ("evidence_anchors", "evidence_hashes"):
            symbolic[field_name] = dict(value) if isinstance(value, dict) else {}
        else:
            symbolic[field_name] = value
    return symbolic


def _make_refusal(
    raw_claim: Dict[str, Any],
    code: str,
    reason: str,
) -> Dict[str, Any]:
    canonical_text = ""
    try:
        canonical_text = _canonical_text(raw_claim)
    except Exception:
        canonical_text = ""
    refusal = {
        "refusal_id": (
            "CANONICAL_CLAIM_EMBEDDING_PROJECTION_REFUSAL_"
            f"{raw_claim.get('normalized_claim_id', 'UNKNOWN_NORMALIZED_CLAIM')}"
        ),
        "normalized_claim_id": str(
            raw_claim.get("normalized_claim_id") or "UNKNOWN_NORMALIZED_CLAIM"
        ),
        "claim_id": str(raw_claim.get("claim_id") or "UNKNOWN_CLAIM"),
        "refusal_code": code,
        "refusal_reason": reason,
        "canonical_text": canonical_text,
        "symbolic_claim": _empty_symbolic_claim(raw_claim),
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_embedded_claim(
    embedded_claim: Dict[str, Any],
    normalized_claims_by_id: Dict[str, Dict[str, Any]],
) -> None:
    if tuple(embedded_claim.keys()) != EMBEDDED_CLAIM_FIELDS:
        raise ValueError("Embedded canonical claim fields changed unexpectedly")
    for field_name in (
        "embedded_claim_id",
        "normalized_claim_id",
        "claim_id",
        "canonical_text",
        "embedding_method",
        "embedding_hash",
        "embedding_root",
    ):
        _require_nonempty_string(embedded_claim, field_name, "EmbeddedCanonicalClaim")
    normalized_claim_id = embedded_claim["normalized_claim_id"]
    if normalized_claim_id not in normalized_claims_by_id:
        raise ValueError(
            f"EmbeddedCanonicalClaim references unknown normalized_claim_id: {normalized_claim_id}"
        )
    source_claim = normalized_claims_by_id[normalized_claim_id]
    if embedded_claim["claim_id"] != source_claim["claim_id"]:
        raise ValueError("EmbeddedCanonicalClaim must preserve claim_id")
    if embedded_claim["canonical_text"] != _canonical_text(source_claim):
        raise ValueError("EmbeddedCanonicalClaim canonical_text changed unexpectedly")
    if embedded_claim["symbolic_claim"] != _symbolic_claim(source_claim):
        raise ValueError("EmbeddedCanonicalClaim must preserve symbolic_claim exactly")
    vector = embedded_claim["embedding_vector"]
    if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSION:
        raise ValueError("EmbeddedCanonicalClaim.embedding_vector dimension mismatch")
    if not all(isinstance(value, float) for value in vector):
        raise ValueError("EmbeddedCanonicalClaim.embedding_vector must contain floats")
    if not any(value != 0.0 for value in vector):
        raise ValueError("EmbeddedCanonicalClaim.embedding_vector must be non-zero")
    if embedded_claim["embedding_dimension"] != EMBEDDING_DIMENSION:
        raise ValueError("EmbeddedCanonicalClaim.embedding_dimension changed unexpectedly")
    if embedded_claim["embedding_method"] != EMBEDDING_METHOD:
        raise ValueError("EmbeddedCanonicalClaim.embedding_method changed unexpectedly")
    if embedded_claim["embedding_hash"] != _embedding_hash(
        embedded_claim["canonical_text"], vector
    ):
        raise ValueError(f"embedding_hash mismatch for {embedded_claim['embedded_claim_id']}")
    if embedded_claim["embedding_root"] != _hash_json(
        _embedding_root_material(embedded_claim)
    ):
        raise ValueError(f"embedding_root mismatch for {embedded_claim['embedded_claim_id']}")
    if embedded_claim["manual_review_required"] is not True:
        raise ValueError("EmbeddedCanonicalClaim.manual_review_required must remain true")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Embedding projection refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "normalized_claim_id",
        "claim_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "EmbeddingProjectionRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("EmbeddingProjectionRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("EmbeddingProjectionRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _project_or_refuse(
    normalized_claim: Dict[str, Any],
    embedded_index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        validate_normalized_claim(normalized_claim)
    except ValueError as exc:
        return None, _make_refusal(
            normalized_claim,
            "REFUSED_MALFORMED_NORMALIZED_CLAIM",
            f"Malformed normalized claim: {exc}",
        )
    canonical_text = _canonical_text(normalized_claim)
    if not canonical_text:
        return None, _make_refusal(
            normalized_claim,
            "REFUSED_EMPTY_CANONICAL_TEXT",
            "Canonical text is empty.",
        )
    if not _tokenize(canonical_text):
        return None, _make_refusal(
            normalized_claim,
            "REFUSED_NON_VECTORIZABLE_CANONICAL_TEXT",
            "Canonical text produced no vectorizable tokens.",
        )
    return _make_embedded_claim(normalized_claim, embedded_index), None


def _status_for(mode: str, embedded_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if embedded_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if embedded_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    input_count: int,
    embedded_claims: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    embedded_lines = ["- None"]
    if embedded_claims:
        embedded_lines = []
        for claim in embedded_claims[:20]:
            symbolic = claim["symbolic_claim"]
            embedded_lines.extend(
                [
                    f"- {claim['embedded_claim_id']}",
                    f"  - Normalized Claim ID: {claim['normalized_claim_id']}",
                    f"  - Subject: {symbolic['subject']}",
                    f"  - Predicate: {symbolic['predicate']}",
                    f"  - Object: {symbolic['object']}",
                    f"  - Embedding Hash: {claim['embedding_hash']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Normalized Claim ID: {refusal['normalized_claim_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Canonical Claim Embedding Projection v2",
            "",
            "This lane projects normalized symbolic claims into deterministic "
            "local vector space. It preserves the symbolic claim structure and "
            "does not infer facts, create relationships, detect contradictions, "
            "generate final reports, mark production readiness, or approve evidence.",
            "",
            "## Summary",
            f"- embedding_projection_status: {status}",
            f"- mode: {mode}",
            f"- input_normalized_claim_count: {input_count}",
            f"- embedded_claim_count: {len(embedded_claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- embedding_method: {EMBEDDING_METHOD}",
            f"- embedding_dimension: {EMBEDDING_DIMENSION}",
            f"- embedding_projection_root: {root}",
            "",
            "## First Embedded Claims",
            *embedded_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Symbolic Claims Preserved: True",
            "- Facts Invented: 0",
            "- Relationships Created: 0",
            "- Contradictions Created: 0",
            "- Final Reports Created: 0",
            "- Conclusions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_canonical_claim_embedding_projection(
    mode: str = "dry-run",
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
    normalization_summary_path: Path = DEFAULT_NORMALIZATION_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "project"):
        raise ValueError("mode must be dry-run or project")

    normalized_payload = _load_json(normalized_claims_path)
    normalization_summary = _load_json(normalization_summary_path)
    normalized_claims = _load_normalized_claims(normalized_payload)
    _validate_upstream_summary(normalization_summary, len(normalized_claims))

    schema = _schema()
    validate_schema(schema)

    embedded_claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    validated_claim_count = 0
    if mode == "dry-run":
        for claim in normalized_claims:
            validate_normalized_claim(claim)
            validated_claim_count += 1
    else:
        for claim in normalized_claims:
            validated_claim_count += 1
            embedded_claim, refusal = _project_or_refuse(
                claim, len(embedded_claims) + 1
            )
            if embedded_claim is not None:
                embedded_claims.append(embedded_claim)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    normalized_claims_by_id = {
        claim["normalized_claim_id"]: claim for claim in normalized_claims
    }
    for embedded_claim in embedded_claims:
        validate_embedded_claim(embedded_claim, normalized_claims_by_id)
    for refusal in refusals:
        validate_refusal(refusal)

    embedding_roots = [claim["embedding_root"] for claim in embedded_claims]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    symbolic_claims_preserved_count = len(embedded_claims)
    anchors_preserved_count = len(embedded_claims)
    hashes_preserved_count = len(embedded_claims)
    roots_preserved_count = len(embedded_claims)
    root = _hash_json(
        {
            "embedding_roots": sorted(embedding_roots),
            "refusal_roots": sorted(refusal_roots),
            "embedding_method": EMBEDDING_METHOD,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "facts_invented": 0,
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
    status = _status_for(mode, len(embedded_claims), len(refusals))
    report = _build_report(
        status, mode, len(normalized_claims), embedded_claims, refusals, root
    )
    summary = {
        "embedding_projection_status": status,
        "mode": mode,
        "input_normalized_claim_count": len(normalized_claims),
        "validated_normalized_claim_count": validated_claim_count,
        "embedded_claim_count": len(embedded_claims),
        "refusal_count": len(refusals),
        "embedding_method": EMBEDDING_METHOD,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "symbolic_claims_preserved_count": symbolic_claims_preserved_count,
        "anchors_preserved_count": anchors_preserved_count,
        "hashes_preserved_count": hashes_preserved_count,
        "roots_preserved_count": roots_preserved_count,
        "facts_invented": 0,
        "relationships_created": 0,
        "contradictions_created": 0,
        "final_reports_created": 0,
        "conclusions_created": 0,
        "embedding_roots": embedding_roots,
        "refusal_roots": refusal_roots,
        "embedding_projection_schema_hash": _hash_json(schema),
        "embedding_projection_report_hash": _sha256_text(report),
        "embedding_projection_root": root,
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
        "relationships_created",
        "contradictions_created",
        "final_reports_created",
        "conclusions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("embedding projection guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(EMBEDDED_CLAIMS_OUTPUT, {"embedded_claims": embedded_claims})
    _write_json(REFUSALS_OUTPUT, {"embedding_projection_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "embedded_claims": embedded_claims,
        "embedding_projection_refusals": refusals,
        "schema": schema,
        "report": report,
    }
