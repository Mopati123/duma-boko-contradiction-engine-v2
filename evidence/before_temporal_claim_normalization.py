#!/usr/bin/env python3
"""
BEFORE Temporal Claim Normalization.

Converts existing generic BEFORE extracted claims into temporal claim candidates
while preserving exact claim text and lineage. This lane does not fetch URLs,
rewrite claims, semantically normalize claims, create embeddings, create
contradictions, create proof chains, create final reports, approve evidence, or
mark production readiness.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


DEFAULT_TEMPORAL_CLAIMS = Path(
    "outputs/temporal_claim_extraction/temporal_extracted_claims.json"
)
DEFAULT_TEMPORAL_CLAIM_SUMMARY = Path(
    "outputs/temporal_claim_extraction/temporal_claim_extraction_summary.json"
)
DEFAULT_SOURCE_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/before_temporal_claim_normalization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "before_temporal_claim_normalization_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "before_temporal_claim_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "before_temporal_claim_normalization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "before_temporal_claim_normalization_report.md"

SCHEMA_VERSION = "before_temporal_claim_normalization_v1"
UPSTREAM_SCHEMA_VERSION = "temporal_claim_extraction_v2"
SOURCE_PACK_VERSION = "duma_boko_temporal_source_pack_v2"

DRY_RUN_STATUS = "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_CANDIDATE"
PARTIAL_STATUS = "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_PARTIAL"
REFUSED_STATUS = "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_REFUSED"

UPSTREAM_ALLOWED_STATUSES = (
    "TEMPORAL_CLAIM_EXTRACTION_CANDIDATE",
    "TEMPORAL_CLAIM_EXTRACTION_PARTIAL",
)
TEMPORAL_POSITION = "BEFORE"

SOURCE_CLAIM_FIELDS = (
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
TEMPORAL_CLAIM_FIELDS = (
    "temporal_claim_id",
    "source_claim_id",
    "claim_text",
    "claim_type",
    "claim_time",
    "temporal_position",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "source_type",
    "url",
    "publisher",
    "topic",
    "evidence_hashes",
    "packet_root",
    "source_claim_root",
    "manual_review_required",
    "temporal_claim_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "source_claim_id",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MISSING_UPSTREAM_CLAIMS",
    "REFUSED_UPSTREAM_STATUS",
    "REFUSED_NO_BEFORE_CLAIMS",
    "REFUSED_MALFORMED_SOURCE_CLAIM",
    "REFUSED_MISSING_REQUIRED_LINEAGE",
    "REFUSED_NON_BEFORE_SOURCE_CLAIM",
    "REFUSED_SOURCE_CLAIM_ROOT_MISMATCH",
    "REFUSED_INVARIANT_VIOLATION",
)
REQUIRED_SOURCE_FIELDS = (
    "temporal_claim_id",
    "temporal_evidence_packet_id",
    "localized_segment_id",
    "source_id",
    "claim_text",
    "packet_root",
    "claim_root",
)


class BeforeTemporalClaimNormalizationRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


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
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            f"{object_name}.{field_name} must be a non-empty string.",
        )


def _source_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("claim_root", None)
    return material


def _temporal_claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("temporal_claim_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _load_source_claims(claims_path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    payload = _load_json(claims_path)
    if not isinstance(payload, dict) or not payload:
        return [], "temporal_extracted_claims.json is missing."
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return [], "temporal_extracted_claims schema_version is unsupported."
    claims = payload.get("temporal_extracted_claims")
    if not isinstance(claims, list):
        return [], "temporal_extracted_claims must contain a list."
    return claims, None


def _load_upstream_summary(summary_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        return None, "temporal_claim_extraction_summary.json is missing."
    return summary, None


def _validate_upstream_summary(summary: Dict[str, Any], claim_count: int) -> None:
    status = summary.get("temporal_claim_extraction_status")
    if status not in UPSTREAM_ALLOWED_STATUSES:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"Upstream temporal claim extraction status is {status}, not a candidate or partial status.",
        )
    if summary.get("temporal_claim_count") != claim_count:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream temporal claim count does not match source claims.",
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
        if summary.get(counter_name) != 0:
            raise BeforeTemporalClaimNormalizationRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream guardrail {counter_name} must remain 0.",
            )
    for flag_name in ("lineage_preserved", "hashes_preserved", "roots_preserved"):
        if summary.get(flag_name) is not True:
            raise BeforeTemporalClaimNormalizationRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream preservation flag {flag_name} must remain true.",
            )
    if not _closed_flags(summary):
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream governance flags must remain closed.",
        )


def _load_before_claim_times(source_pack_path: Path) -> Dict[str, str]:
    payload = _load_json(source_pack_path)
    if not isinstance(payload, dict) or not payload:
        return {}
    if payload.get("pack_version") != SOURCE_PACK_VERSION:
        return {}
    sources = payload.get("curated_temporal_sources")
    if not isinstance(sources, list):
        return {}
    claim_times: Dict[str, str] = {}
    for source in sources:
        if not isinstance(source, dict) or source.get("time_direction") != TEMPORAL_POSITION:
            continue
        source_id = str(source.get("source_id") or "")
        published_date = str(source.get("published_date") or "").strip()
        if source_id and published_date:
            claim_times[source_id] = published_date
    return claim_times


def _validate_source_claim_shape(claim: Dict[str, Any]) -> None:
    if not isinstance(claim, dict) or set(claim.keys()) != set(SOURCE_CLAIM_FIELDS):
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            "Temporal source claim fields do not match upstream schema.",
        )
    for field_name in SOURCE_CLAIM_FIELDS:
        if field_name in ("claim_confidence", "manual_review_required"):
            continue
        if field_name == "evidence_hashes":
            continue
        _require_nonempty_string(claim, field_name, "TemporalExtractedClaim")
    if claim["manual_review_required"] is not True:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            "Temporal source claim manual_review_required must remain true.",
        )
    if claim["time_direction"] != TEMPORAL_POSITION:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_NON_BEFORE_SOURCE_CLAIM",
            "Temporal source claim time_direction must be BEFORE.",
        )
    if not isinstance(claim["claim_confidence"], float):
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            "Temporal source claim claim_confidence must be a float.",
        )
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(EVIDENCE_HASH_FIELDS):
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            "Temporal source claim evidence_hashes fields changed unexpectedly.",
        )
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise BeforeTemporalClaimNormalizationRefusal(
                "REFUSED_MISSING_REQUIRED_LINEAGE",
                "Temporal source claim evidence_hashes must preserve non-zero hashes.",
            )
    if hashes["packet_root"] != claim["packet_root"]:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            "Temporal source claim packet_root preservation mismatch.",
        )
    if claim["claim_root"] != _hash_json(_source_claim_root_material(claim)):
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_SOURCE_CLAIM_ROOT_MISMATCH",
            f"claim_root mismatch for {claim['temporal_claim_id']}.",
        )


def _claim_time_for_source_claim(claim: Dict[str, Any], claim_times: Dict[str, str]) -> str:
    claim_time = str(claim_times.get(claim["source_id"]) or "").strip()
    if not claim_time:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            f"No source-pack published_date found for BEFORE source {claim['source_id']}.",
        )
    return claim_time


def _make_temporal_claim(
    claim: Dict[str, Any],
    index: int,
    claim_times: Dict[str, str],
) -> Dict[str, Any]:
    temporal_claim = {
        "temporal_claim_id": f"TEMPORAL_CLAIM_{index:06d}",
        "source_claim_id": claim["temporal_claim_id"],
        "claim_text": claim["claim_text"],
        "claim_type": claim["claim_type"],
        "claim_time": _claim_time_for_source_claim(claim, claim_times),
        "temporal_position": TEMPORAL_POSITION,
        "temporal_evidence_packet_id": claim["temporal_evidence_packet_id"],
        "localized_segment_id": claim["localized_segment_id"],
        "source_id": claim["source_id"],
        "source_type": claim["source_type"],
        "url": claim["url"],
        "publisher": claim["publisher"],
        "topic": claim["topic"],
        "evidence_hashes": claim["evidence_hashes"],
        "packet_root": claim["packet_root"],
        "source_claim_root": claim["claim_root"],
        "manual_review_required": True,
        "temporal_claim_root": "",
    }
    temporal_claim["temporal_claim_root"] = _hash_json(
        _temporal_claim_root_material(temporal_claim)
    )
    return temporal_claim


def _validate_temporal_claim(temporal_claim: Dict[str, Any], source_claim: Dict[str, Any]) -> None:
    if tuple(temporal_claim.keys()) != TEMPORAL_CLAIM_FIELDS:
        raise ValueError("BEFORE temporal claim candidate fields changed unexpectedly.")
    for field_name in TEMPORAL_CLAIM_FIELDS:
        if field_name in ("manual_review_required", "evidence_hashes"):
            continue
        _require_nonempty_string(temporal_claim, field_name, "BeforeTemporalClaimCandidate")
    if temporal_claim["claim_text"] != source_claim["claim_text"]:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "BEFORE temporal claim text does not exactly match source claim text.",
        )
    invariant_pairs = (
        ("source_claim_id", "temporal_claim_id"),
        ("temporal_evidence_packet_id", "temporal_evidence_packet_id"),
        ("localized_segment_id", "localized_segment_id"),
        ("source_id", "source_id"),
        ("packet_root", "packet_root"),
        ("source_claim_root", "claim_root"),
    )
    for temporal_field, source_field in invariant_pairs:
        if temporal_claim[temporal_field] != source_claim[source_field]:
            raise BeforeTemporalClaimNormalizationRefusal(
                "REFUSED_INVARIANT_VIOLATION",
                f"BEFORE temporal claim {temporal_field} does not match source {source_field}.",
            )
    if temporal_claim["temporal_position"] != TEMPORAL_POSITION:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "BEFORE temporal claim temporal_position must be BEFORE.",
        )
    if temporal_claim["evidence_hashes"] != source_claim["evidence_hashes"]:
        raise BeforeTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "BEFORE temporal claim evidence_hashes do not match source claim.",
        )
    if temporal_claim["manual_review_required"] is not True:
        raise ValueError("BEFORE temporal claim manual_review_required must remain true.")
    if temporal_claim["temporal_claim_root"] != _hash_json(
        _temporal_claim_root_material(temporal_claim)
    ):
        raise ValueError(f"temporal_claim_root mismatch for {temporal_claim['temporal_claim_id']}.")


def _claim_identity(claim: Any) -> Tuple[str, str, str, str]:
    if not isinstance(claim, dict):
        return ("UNKNOWN_SOURCE_CLAIM", "UNKNOWN_PACKET", "UNKNOWN_SEGMENT", "UNKNOWN_SOURCE")
    return (
        str(claim.get("temporal_claim_id") or "UNKNOWN_SOURCE_CLAIM"),
        str(claim.get("temporal_evidence_packet_id") or "UNKNOWN_PACKET"),
        str(claim.get("localized_segment_id") or "UNKNOWN_SEGMENT"),
        str(claim.get("source_id") or "UNKNOWN_SOURCE"),
    )


def _make_refusal(claim: Any, code: str, reason: str) -> Dict[str, Any]:
    source_claim_id, packet_id, localized_segment_id, source_id = _claim_identity(claim)
    refusal = {
        "refusal_id": f"BEFORE_TEMPORAL_CLAIM_NORMALIZATION_REFUSAL_{source_claim_id}",
        "source_claim_id": source_claim_id,
        "temporal_evidence_packet_id": packet_id,
        "localized_segment_id": localized_segment_id,
        "source_id": source_id,
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("BEFORE temporal claim normalization refusal fields changed unexpectedly.")
    for field_name in (
        "refusal_id",
        "source_claim_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "BeforeTemporalClaimNormalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("BEFORE temporal claim normalization refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("BEFORE temporal claim normalization refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("BEFORE temporal claim normalization refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _temporal_claim_or_refusal(
    source_claim: Dict[str, Any],
    index: int,
    claim_times: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_source_claim_shape(source_claim)
        for field_name in REQUIRED_SOURCE_FIELDS:
            _require_nonempty_string(source_claim, field_name, "TemporalExtractedClaim")
        temporal_claim = _make_temporal_claim(source_claim, index, claim_times)
        _validate_temporal_claim(temporal_claim, source_claim)
        return temporal_claim, None
    except BeforeTemporalClaimNormalizationRefusal as exc:
        refusal = _make_refusal(source_claim, exc.code, exc.reason)
        _validate_refusal(refusal)
        return None, refusal
    except ValueError as exc:
        refusal = _make_refusal(
            source_claim,
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            str(exc),
        )
        _validate_refusal(refusal)
        return None, refusal


def _status_for(mode: str, candidate_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if candidate_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if candidate_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {"before_temporal_claim_normalization_root"}
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    source_claim_count: int,
    before_claim_count: int,
    candidates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    candidate_lines = ["- None"]
    if candidates:
        candidate_lines = []
        for candidate in candidates[:20]:
            preview = candidate["claim_text"][:160].replace("\n", " ")
            candidate_lines.extend(
                [
                    f"- {candidate['temporal_claim_id']}: {candidate['claim_type']}",
                    f"  - Source Claim: {candidate['source_claim_id']}",
                    f"  - Source: {candidate['source_id']}",
                    f"  - Text Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source Claim: {refusal['source_claim_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# BEFORE Temporal Claim Normalization Report",
            "",
            f"- before_temporal_claim_normalization_status: {status}",
            f"- mode: {mode}",
            f"- source_claim_count: {source_claim_count}",
            f"- before_source_claim_count: {before_claim_count}",
            f"- before_temporal_claim_candidate_count: {len(candidates)}",
            f"- refusal_count: {len(refusals)}",
            f"- before_temporal_claim_normalization_root: {root}",
            "",
            "## Candidates",
            *candidate_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Fetched: 0",
            "- Live Web Access Performed: 0",
            "- LLM Calls: 0",
            "- Claims Rewritten: 0",
            "- Claims Normalized Semantically: 0",
            "- Contradictions Created: 0",
            "- Claim Pairs Created: 0",
            "- Embeddings Created: 0",
            "- Proof Chains Created: 0",
            "- Final Reports Created: 0",
            "- Approved Evidence: 0",
            "- Production Ready: False",
            "",
        ]
    )


def build_before_temporal_claim_normalization(
    mode: str = "dry-run",
    claims_path: Path = DEFAULT_TEMPORAL_CLAIMS,
    claim_summary_path: Path = DEFAULT_TEMPORAL_CLAIM_SUMMARY,
    source_pack_path: Path = DEFAULT_SOURCE_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "normalize"):
        raise ValueError("mode must be 'dry-run' or 'normalize'.")

    source_claims, claims_error = _load_source_claims(claims_path)
    upstream_summary, summary_error = _load_upstream_summary(claim_summary_path)
    claim_times = _load_before_claim_times(source_pack_path)
    schema_hash = _hash_json(
        {
            "schema_version": SCHEMA_VERSION,
            "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
            "source_claim_fields": list(SOURCE_CLAIM_FIELDS),
            "temporal_claim_fields": list(TEMPORAL_CLAIM_FIELDS),
            "refusal_fields": list(REFUSAL_FIELDS),
            "refusal_codes": list(REFUSAL_CODES),
        }
    )

    candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    validated_source_claim_count = 0
    before_source_claims = [
        claim
        for claim in source_claims
        if isinstance(claim, dict) and claim.get("time_direction") == TEMPORAL_POSITION
    ]

    if claims_error:
        refusals.append(
            _make_refusal({}, "REFUSED_MISSING_UPSTREAM_CLAIMS", claims_error)
        )
    elif summary_error:
        refusals.append(
            _make_refusal({}, "REFUSED_UPSTREAM_STATUS", summary_error)
        )
    elif upstream_summary is not None:
        try:
            _validate_upstream_summary(upstream_summary, len(source_claims))
        except BeforeTemporalClaimNormalizationRefusal as exc:
            refusals.append(_make_refusal({}, exc.code, exc.reason))

    if not refusals and not before_source_claims:
        refusals.append(
            _make_refusal(
                {},
                "REFUSED_NO_BEFORE_CLAIMS",
                "No extracted BEFORE claims exist; bottleneck is upstream harvesting, localization, or claim extraction.",
            )
        )

    if not refusals:
        for source_claim in before_source_claims:
            if mode == "dry-run":
                claim, refusal = _temporal_claim_or_refusal(
                    source_claim,
                    len(candidates) + 1,
                    claim_times,
                )
                if claim is not None:
                    validated_source_claim_count += 1
                if refusal is not None:
                    refusals.append(refusal)
            else:
                claim, refusal = _temporal_claim_or_refusal(
                    source_claim,
                    len(candidates) + 1,
                    claim_times,
                )
                if claim is not None:
                    candidates.append(claim)
                    validated_source_claim_count += 1
                if refusal is not None:
                    refusals.append(refusal)

    for refusal in refusals:
        _validate_refusal(refusal)
    source_claims_by_id = {
        claim["temporal_claim_id"]: claim for claim in before_source_claims if isinstance(claim, dict)
    }
    for candidate in candidates:
        _validate_temporal_claim(candidate, source_claims_by_id[candidate["source_claim_id"]])

    candidate_roots = [candidate["temporal_claim_root"] for candidate in candidates]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    status = _status_for(mode, len(candidates), len(refusals))
    summary = {
        "before_temporal_claim_normalization_status": status,
        "mode": mode,
        "source_claim_count": len(source_claims),
        "before_source_claim_count": len(before_source_claims),
        "non_before_source_claim_count": len(source_claims) - len(before_source_claims),
        "validated_source_claim_count": validated_source_claim_count,
        "before_temporal_claim_candidate_count": len(candidates),
        "refusal_count": len(refusals),
        "candidate_roots": candidate_roots,
        "refusal_roots": refusal_roots,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "lineage_preserved": len(refusals) == 0,
        "claim_text_exact_copy": len(refusals) == 0,
        "packet_root_preserved": len(refusals) == 0,
        "source_claim_root_preserved": len(refusals) == 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "claim_pairs_created": 0,
        "embeddings_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "approved_evidence": 0,
        "production_ready": False,
        "public_ready": False,
        "institutional_ready": False,
        "before_temporal_claim_normalization_schema_hash": schema_hash,
        "before_temporal_claim_normalization_root": "",
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["before_temporal_claim_normalization_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(source_claims),
        len(before_source_claims),
        candidates,
        refusals,
        summary["before_temporal_claim_normalization_root"],
    )

    for counter_name in (
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "claim_pairs_created",
        "embeddings_created",
        "proof_chains_created",
        "final_reports_created",
        "approved_evidence",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("BEFORE temporal claim normalization guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / CANDIDATES_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "before_temporal_claim_candidates": candidates,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "before_temporal_claim_normalization_refusals": refusals,
        },
    )
    (output_dir / REPORT_OUTPUT.name).write_text(report, encoding="utf-8")

    return {
        "summary": summary,
        "before_temporal_claim_candidates": candidates,
        "before_temporal_claim_normalization_refusals": refusals,
        "report": report,
    }


__all__ = ["build_before_temporal_claim_normalization"]
