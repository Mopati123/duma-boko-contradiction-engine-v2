#!/usr/bin/env python3
"""
Manual AFTER Temporal Claim Normalization.

Converts extracted manual AFTER snapshot claims into temporal claim candidates
while preserving exact claim text and full lineage. This lane does not fetch
URLs, rewrite claims, semantically normalize claims, create embeddings, create
contradictions, create proof chains, create final reports, approve evidence, or
mark production readiness.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


DEFAULT_MANUAL_AFTER_CLAIMS = Path(
    "outputs/manual_after_snapshot_claim_extraction/manual_after_snapshot_claims.json"
)
DEFAULT_MANUAL_AFTER_CLAIM_SUMMARY = Path(
    "outputs/manual_after_snapshot_claim_extraction/manual_after_snapshot_claim_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_claim_normalization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_normalization_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_claim_candidates.json"

SCHEMA_VERSION = "manual_after_temporal_claim_normalization_v1"
UPSTREAM_SCHEMA_VERSION = "manual_after_snapshot_claim_extraction_v2"
REQUIRED_UPSTREAM_STATUS = "MANUAL_AFTER_SNAPSHOT_CLAIM_EXTRACTION_CANDIDATE"

DRY_RUN_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_PARTIAL"
REFUSED_STATUS = "TEMPORAL_CLAIM_NORMALIZATION_REFUSED"

TEMPORAL_POSITION = "AFTER"
SOURCE_TYPE = "MANUAL_AFTER_SOURCE_SNAPSHOT"

SOURCE_CLAIM_FIELDS = (
    "manual_after_snapshot_claim_id",
    "manual_after_snapshot_packet_id",
    "snapshot_id",
    "linked_after_candidate_id",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "claim_text",
    "claim_type",
    "claim_category",
    "claim_confidence",
    "packet_hash",
    "packet_root",
    "manual_review_required",
    "claim_root",
)
TEMPORAL_CLAIM_FIELDS = (
    "temporal_claim_id",
    "source_claim_id",
    "claim_text",
    "claim_type",
    "claim_time",
    "temporal_position",
    "snapshot_id",
    "linked_after_candidate_id",
    "manual_after_snapshot_packet_id",
    "packet_root",
    "packet_hash",
    "url",
    "title",
    "publisher",
    "published_date",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "source_claim_root",
    "manual_review_required",
    "temporal_claim_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "source_claim_id",
    "snapshot_id",
    "linked_after_candidate_id",
    "manual_after_snapshot_packet_id",
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
    "REFUSED_UPSTREAM_STATUS",
    "REFUSED_MALFORMED_SOURCE_CLAIM",
    "REFUSED_MISSING_REQUIRED_LINEAGE",
    "REFUSED_NON_AFTER_SOURCE_CLAIM",
    "REFUSED_SOURCE_CLAIM_ROOT_MISMATCH",
    "REFUSED_INVARIANT_VIOLATION",
)
REQUIRED_SOURCE_FIELDS = (
    "manual_after_snapshot_claim_id",
    "claim_text",
    "snapshot_id",
    "linked_after_candidate_id",
    "manual_after_snapshot_packet_id",
    "packet_root",
)


class ManualAfterTemporalClaimNormalizationRefusal(ValueError):
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
        raise ManualAfterTemporalClaimNormalizationRefusal(
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


def _load_source_claims(claims_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(claims_path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("manual_after_snapshot_claims.json is missing.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("manual_after_snapshot_claims schema_version is unsupported.")
    claims = payload.get("manual_after_snapshot_claims")
    if not isinstance(claims, list):
        raise ValueError("manual_after_snapshot_claims must contain a list.")
    return claims


def _upstream_status(summary_path: Path) -> Tuple[Optional[str], Dict[str, Any]]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        raise ValueError("manual_after_snapshot_claim_summary.json is missing.")
    return summary.get("manual_after_snapshot_claim_status"), summary


def _validate_upstream_summary(summary: Dict[str, Any], claim_count: int) -> None:
    status = summary.get("manual_after_snapshot_claim_status")
    if status != REQUIRED_UPSTREAM_STATUS:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"Upstream manual AFTER snapshot claim status is {status}, not {REQUIRED_UPSTREAM_STATUS}.",
        )
    if summary.get("manual_after_snapshot_claim_count") != claim_count:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream manual AFTER snapshot claim count does not match source claims.",
        )
    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "embeddings_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
        "urls_fetched",
    ):
        if summary.get(counter_name) != 0:
            raise ManualAfterTemporalClaimNormalizationRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream guardrail {counter_name} must remain 0.",
            )
    for flag_name in (
        "lineage_preserved",
        "hashes_preserved",
        "roots_preserved",
        "packet_text_exact_copy",
        "no_generated_outputs_committed",
    ):
        if summary.get(flag_name) is not True:
            raise ManualAfterTemporalClaimNormalizationRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream preservation flag {flag_name} must remain true.",
            )
    if not _closed_flags(summary):
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream governance flags must remain closed.",
        )


def _validate_source_claim_shape(claim: Dict[str, Any]) -> None:
    if not isinstance(claim, dict) or set(claim.keys()) != set(SOURCE_CLAIM_FIELDS):
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            "Manual AFTER source claim fields do not match upstream schema.",
        )
    for field_name in SOURCE_CLAIM_FIELDS:
        if field_name in ("claim_confidence", "manual_review_required"):
            continue
        _require_nonempty_string(claim, field_name, "ManualAfterSnapshotClaim")
    if claim["manual_review_required"] is not True:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_MALFORMED_SOURCE_CLAIM",
            "Manual AFTER source claim manual_review_required must remain true.",
        )
    if claim["time_direction"] != TEMPORAL_POSITION:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_NON_AFTER_SOURCE_CLAIM",
            "Manual AFTER source claim time_direction must be AFTER.",
        )
    if claim["source_type"] != SOURCE_TYPE:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_NON_AFTER_SOURCE_CLAIM",
            "Manual AFTER source claim source_type is unsupported.",
        )
    if not _is_nonzero_hash(claim["packet_root"]) or not _is_nonzero_hash(claim["packet_hash"]):
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            "Manual AFTER source claim must preserve packet_root and packet_hash.",
        )
    if claim["claim_root"] != _hash_json(_source_claim_root_material(claim)):
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_SOURCE_CLAIM_ROOT_MISMATCH",
            f"claim_root mismatch for {claim['manual_after_snapshot_claim_id']}.",
        )


def _claim_time_from_source_claim(claim: Dict[str, Any]) -> str:
    published_date = str(claim.get("published_date") or "").strip()
    if not published_date:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_MISSING_REQUIRED_LINEAGE",
            "Manual AFTER source claim published_date is required for claim_time.",
        )
    return published_date


def _make_temporal_claim(claim: Dict[str, Any], index: int) -> Dict[str, Any]:
    claim_time = _claim_time_from_source_claim(claim)
    temporal_claim = {
        "temporal_claim_id": f"TEMPORAL_CLAIM_{index:06d}",
        "source_claim_id": claim["manual_after_snapshot_claim_id"],
        "claim_text": claim["claim_text"],
        "claim_type": claim["claim_type"],
        "claim_time": claim_time,
        "temporal_position": TEMPORAL_POSITION,
        "snapshot_id": claim["snapshot_id"],
        "linked_after_candidate_id": claim["linked_after_candidate_id"],
        "manual_after_snapshot_packet_id": claim["manual_after_snapshot_packet_id"],
        "packet_root": claim["packet_root"],
        "packet_hash": claim["packet_hash"],
        "url": claim["url"],
        "title": claim["title"],
        "publisher": claim["publisher"],
        "published_date": claim["published_date"],
        "after_stability_target_id": claim["after_stability_target_id"],
        "linked_before_claim_id": claim["linked_before_claim_id"],
        "target_theme": claim["target_theme"],
        "target_evidence_type": claim["target_evidence_type"],
        "preferred_source_family": claim["preferred_source_family"],
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
        raise ValueError("Temporal claim candidate fields changed unexpectedly.")
    for field_name in TEMPORAL_CLAIM_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(temporal_claim, field_name, "TemporalClaimCandidate")
    if temporal_claim["claim_text"] != source_claim["claim_text"]:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "Temporal claim text does not exactly match source claim text.",
        )
    invariant_pairs = (
        ("source_claim_id", "manual_after_snapshot_claim_id"),
        ("packet_root", "packet_root"),
        ("snapshot_id", "snapshot_id"),
        ("linked_after_candidate_id", "linked_after_candidate_id"),
        ("manual_after_snapshot_packet_id", "manual_after_snapshot_packet_id"),
        ("packet_hash", "packet_hash"),
    )
    for temporal_field, source_field in invariant_pairs:
        if temporal_claim[temporal_field] != source_claim[source_field]:
            raise ManualAfterTemporalClaimNormalizationRefusal(
                "REFUSED_INVARIANT_VIOLATION",
                f"Temporal claim {temporal_field} does not match source {source_field}.",
            )
    if temporal_claim["temporal_position"] != TEMPORAL_POSITION:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "Temporal claim temporal_position must be AFTER.",
        )
    if not temporal_claim["claim_time"]:
        raise ManualAfterTemporalClaimNormalizationRefusal(
            "REFUSED_INVARIANT_VIOLATION",
            "Temporal claim claim_time must be non-empty.",
        )
    if temporal_claim["manual_review_required"] is not True:
        raise ValueError("Temporal claim candidate manual_review_required must remain true.")
    if temporal_claim["temporal_claim_root"] != _hash_json(
        _temporal_claim_root_material(temporal_claim)
    ):
        raise ValueError(f"temporal_claim_root mismatch for {temporal_claim['temporal_claim_id']}.")


def _claim_identity(claim: Any) -> Tuple[str, str, str, str]:
    if not isinstance(claim, dict):
        return ("UNKNOWN_SOURCE_CLAIM", "", "", "")
    return (
        str(claim.get("manual_after_snapshot_claim_id") or "UNKNOWN_SOURCE_CLAIM"),
        str(claim.get("snapshot_id") or ""),
        str(claim.get("linked_after_candidate_id") or ""),
        str(claim.get("manual_after_snapshot_packet_id") or ""),
    )


def _make_refusal(
    claim: Any,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    source_claim_id, snapshot_id, linked_after_candidate_id, packet_id = _claim_identity(claim)
    refusal = {
        "refusal_id": f"TEMPORAL_CLAIM_NORMALIZATION_REFUSAL_{source_claim_id}",
        "source_claim_id": source_claim_id,
        "snapshot_id": snapshot_id,
        "linked_after_candidate_id": linked_after_candidate_id,
        "manual_after_snapshot_packet_id": packet_id,
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
        raise ValueError("Temporal claim normalization refusal fields changed unexpectedly.")
    for field_name in (
        "refusal_id",
        "source_claim_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TemporalClaimNormalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Temporal claim normalization refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Temporal claim normalization refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("Temporal claim normalization refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _temporal_claim_or_refusal(
    source_claim: Dict[str, Any],
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_source_claim_shape(source_claim)
        for field_name in REQUIRED_SOURCE_FIELDS:
            _require_nonempty_string(source_claim, field_name, "ManualAfterSnapshotClaim")
        claim_time = _claim_time_from_source_claim(source_claim)
        if not claim_time:
            raise ManualAfterTemporalClaimNormalizationRefusal(
                "REFUSED_MISSING_REQUIRED_LINEAGE",
                "Manual AFTER source claim claim_time could not be derived.",
            )
        temporal_claim = _make_temporal_claim(source_claim, index)
        _validate_temporal_claim(temporal_claim, source_claim)
        return temporal_claim, None
    except ManualAfterTemporalClaimNormalizationRefusal as exc:
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
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if candidate_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if candidate_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {"temporal_claim_normalization_root"}
    return {key: value for key, value in summary.items() if key not in excluded}


def build_manual_after_temporal_claim_normalization(
    mode: str = "dry-run",
    claims_path: Path = DEFAULT_MANUAL_AFTER_CLAIMS,
    claim_summary_path: Path = DEFAULT_MANUAL_AFTER_CLAIM_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "normalize"):
        raise ValueError("mode must be 'dry-run' or 'normalize'.")

    source_claims = _load_source_claims(claims_path)
    upstream_status, upstream_summary = _upstream_status(claim_summary_path)
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
    upstream_refused = upstream_status != REQUIRED_UPSTREAM_STATUS

    if upstream_refused:
        refusal = _make_refusal(
            {},
            "REFUSED_UPSTREAM_STATUS",
            f"Upstream manual AFTER snapshot claim status is {upstream_status}, not {REQUIRED_UPSTREAM_STATUS}.",
        )
        _validate_refusal(refusal)
        refusals.append(refusal)
    else:
        try:
            _validate_upstream_summary(upstream_summary, len(source_claims))
        except ManualAfterTemporalClaimNormalizationRefusal as exc:
            refusal = _make_refusal({}, exc.code, exc.reason)
            _validate_refusal(refusal)
            refusals.append(refusal)
        if not refusals:
            if mode == "dry-run":
                for source_claim in source_claims:
                    _validate_source_claim_shape(source_claim)
                    for field_name in REQUIRED_SOURCE_FIELDS:
                        _require_nonempty_string(source_claim, field_name, "ManualAfterSnapshotClaim")
                    _claim_time_from_source_claim(source_claim)
                    validated_source_claim_count += 1
            else:
                for source_claim in source_claims:
                    temporal_claim, refusal = _temporal_claim_or_refusal(
                        source_claim,
                        len(candidates) + 1,
                    )
                    if temporal_claim is not None:
                        candidates.append(temporal_claim)
                        validated_source_claim_count += 1
                    if refusal is not None:
                        refusals.append(refusal)

    for candidate in candidates:
        matching = [
            claim
            for claim in source_claims
            if claim.get("manual_after_snapshot_claim_id") == candidate["source_claim_id"]
        ]
        if len(matching) != 1:
            raise ValueError("Temporal claim candidate source claim lookup failed.")
        _validate_temporal_claim(candidate, matching[0])
    for refusal in refusals:
        _validate_refusal(refusal)

    status = _status_for(mode, len(candidates), len(refusals))
    summary = {
        "temporal_claim_normalization_status": status,
        "mode": mode,
        "upstream_claim_status": upstream_status,
        "source_claim_count": len(source_claims),
        "validated_source_claim_count": validated_source_claim_count,
        "temporal_claim_candidate_count": len(candidates),
        "refusal_count": len(refusals),
        "candidate_ids": [candidate["temporal_claim_id"] for candidate in candidates],
        "candidate_roots": [candidate["temporal_claim_root"] for candidate in candidates],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "temporal_position_counts": {
            TEMPORAL_POSITION: sum(
                1 for candidate in candidates if candidate["temporal_position"] == TEMPORAL_POSITION
            )
        },
        "lineage_preserved": True,
        "claim_text_exact_copy": True,
        "packet_root_preserved": True,
        "packet_hash_preserved": True,
        "snapshot_id_preserved": True,
        "linked_after_candidate_id_preserved": True,
        "manual_after_snapshot_packet_id_preserved": True,
        "temporal_claim_normalization_schema_hash": schema_hash,
        "temporal_claim_normalization_root": "",
        "urls_fetched": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "embeddings_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "approved_evidence": 0,
        "production_ready": False,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_claim_normalization_root"] = _hash_json(_summary_root_material(summary))

    for counter_name in (
        "urls_fetched",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "embeddings_created",
        "proof_chains_created",
        "final_reports_created",
        "approved_evidence",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Temporal claim normalization guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / CANDIDATES_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "temporal_claim_candidates": candidates,
            "temporal_claim_normalization_refusals": refusals,
        },
    )

    return {
        "summary": summary,
        "temporal_claim_candidates": candidates,
        "temporal_claim_normalization_refusals": refusals,
    }


__all__ = ["build_manual_after_temporal_claim_normalization"]
