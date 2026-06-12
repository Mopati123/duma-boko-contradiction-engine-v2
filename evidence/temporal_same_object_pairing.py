#!/usr/bin/env python3
"""
Temporal same-object pairing.

Builds neutral BEFORE/AFTER temporal comparison pairs from already-normalized
temporal claim candidates using deterministic allowed domain-token overlap only.
This lane does not fetch URLs, call LLMs, create embeddings, rewrite claims,
evaluate predicate incompatibility, detect contradictions, approve evidence, or
create final reports.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import hashlib
import json
import re


DEFAULT_BEFORE_CANDIDATES = Path(
    "outputs/before_temporal_claim_normalization/before_temporal_claim_candidates.json"
)
DEFAULT_BEFORE_SUMMARY = Path(
    "outputs/before_temporal_claim_normalization/before_temporal_claim_normalization_summary.json"
)
DEFAULT_AFTER_CANDIDATES = Path(
    "outputs/temporal_claim_normalization/temporal_claim_candidates.json"
)
DEFAULT_AFTER_SUMMARY = Path(
    "outputs/temporal_claim_normalization/temporal_claim_normalization_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_same_object_pairing")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_same_object_pairing_summary.json"
PAIRS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_comparison_pairs.json"
UNPAIRED_BEFORE_OUTPUT = DEFAULT_OUTPUT_DIR / "unpaired_before_claims.json"
UNPAIRED_AFTER_OUTPUT = DEFAULT_OUTPUT_DIR / "unpaired_after_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_same_object_pairing_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_same_object_pairing_report.md"

SCHEMA_VERSION = "temporal_same_object_pairing_v1"
BEFORE_SCHEMA_VERSION = "before_temporal_claim_normalization_v1"
AFTER_SCHEMA_VERSION = "manual_after_temporal_claim_normalization_v1"

CANDIDATE_STATUS = "TEMPORAL_SAME_OBJECT_PAIRING_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_SAME_OBJECT_PAIRING_PARTIAL"
NO_MATCH_STATUS = "TEMPORAL_SAME_OBJECT_PAIRING_NO_MATCH"
REFUSED_STATUS = "TEMPORAL_SAME_OBJECT_PAIRING_REFUSED"

BEFORE_UPSTREAM_STATUSES = (
    "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_CANDIDATE",
    "BEFORE_TEMPORAL_CLAIM_NORMALIZATION_PARTIAL",
)
AFTER_UPSTREAM_STATUSES = (
    "TEMPORAL_CLAIM_NORMALIZATION_CANDIDATE",
    "TEMPORAL_CLAIM_NORMALIZATION_PARTIAL",
)

ALLOWED_DOMAIN_TOKENS = ("solar", "energy", "jobs", "employment", "economy", "grid", "power")
PAIRING_METHOD = "DETERMINISTIC_ALLOWED_DOMAIN_TOKEN_OVERLAP"

BEFORE_CANDIDATE_FIELDS = (
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
AFTER_CANDIDATE_FIELDS = (
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
EVIDENCE_HASH_FIELDS = (
    "segment_sha256",
    "localization_root",
    "packet_hash",
    "packet_root",
)
PAIR_FIELDS = (
    "temporal_comparison_pair_id",
    "pairing_method",
    "matched_domain_tokens",
    "before_domain_tokens",
    "after_domain_tokens",
    "before_temporal_claim_id",
    "after_temporal_claim_id",
    "before_claim_text",
    "after_claim_text",
    "before_claim_time",
    "after_claim_time",
    "before_temporal_position",
    "after_temporal_position",
    "before_lineage",
    "after_lineage",
    "manual_review_required",
    "neutral_pairing_only",
    "pair_root",
)
REFUSAL_CODES = (
    "REFUSED_MISSING_BEFORE_CANDIDATES",
    "REFUSED_MISSING_AFTER_CANDIDATES",
    "REFUSED_UPSTREAM_STATUS",
    "REFUSED_MALFORMED_BEFORE_CLAIM",
    "REFUSED_MALFORMED_AFTER_CLAIM",
    "REFUSED_NON_BEFORE_CLAIM",
    "REFUSED_NON_AFTER_CLAIM",
    "REFUSED_MISSING_LINEAGE",
    "REFUSED_HASH_OR_ROOT_MISMATCH",
)


class TemporalSameObjectPairingRefusal(ValueError):
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


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TemporalSameObjectPairingRefusal(code, f"{field_name} must be a non-empty string.")


def _root_material(data: Dict[str, Any], root_field: str) -> Dict[str, Any]:
    material = dict(data)
    material.pop(root_field, None)
    return material


def _pair_root_material(pair: Dict[str, Any]) -> Dict[str, Any]:
    return {field: pair[field] for field in PAIR_FIELDS if field != "pair_root"}


def _load_before_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MISSING_BEFORE_CANDIDATES",
            "before_temporal_claim_candidates.json is missing.",
        )
    if payload.get("schema_version") != BEFORE_SCHEMA_VERSION:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_BEFORE_CLAIM",
            "BEFORE temporal claim candidate schema_version is unsupported.",
        )
    candidates = payload.get("before_temporal_claim_candidates")
    if not isinstance(candidates, list):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_BEFORE_CLAIM",
            "before_temporal_claim_candidates must be a list.",
        )
    return candidates


def _load_after_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MISSING_AFTER_CANDIDATES",
            "temporal_claim_candidates.json is missing.",
        )
    if payload.get("schema_version") != AFTER_SCHEMA_VERSION:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_AFTER_CLAIM",
            "AFTER temporal claim candidate schema_version is unsupported.",
        )
    candidates = payload.get("temporal_claim_candidates")
    if not isinstance(candidates, list):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_AFTER_CLAIM",
            "temporal_claim_candidates must be a list.",
        )
    return candidates


def _validate_summary(
    path: Path,
    status_field: str,
    allowed_statuses: Sequence[str],
    count_field: str,
    expected_count: int,
) -> Dict[str, Any]:
    summary = _load_json(path)
    if not isinstance(summary, dict) or not summary:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"{path.name} is missing.",
        )
    if summary.get(status_field) not in allowed_statuses:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"{status_field} is not a candidate or partial status.",
        )
    if summary.get(count_field) != expected_count:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"{count_field} does not match candidate artifact.",
        )
    for flag_name in ("lineage_preserved", "claim_text_exact_copy"):
        if summary.get(flag_name) is not True:
            raise TemporalSameObjectPairingRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream preservation flag {flag_name} must remain true.",
            )
    for counter_name in (
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "claim_pairs_created",
        "final_reports_created",
        "approved_evidence",
    ):
        if counter_name in summary and summary.get(counter_name) != 0:
            raise TemporalSameObjectPairingRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream guardrail {counter_name} must remain 0.",
            )
    if not _closed_flags(summary):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream governance flags must remain closed.",
        )
    return summary


def _validate_before_claim(claim: Dict[str, Any]) -> None:
    if not isinstance(claim, dict) or set(claim.keys()) != set(BEFORE_CANDIDATE_FIELDS):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_BEFORE_CLAIM",
            "BEFORE temporal claim candidate fields do not match schema.",
        )
    for field_name in BEFORE_CANDIDATE_FIELDS:
        if field_name in ("manual_review_required", "evidence_hashes"):
            continue
        _require_nonempty_string(claim, field_name, "REFUSED_MISSING_LINEAGE")
    if claim["temporal_position"] != "BEFORE":
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_NON_BEFORE_CLAIM",
            "BEFORE temporal claim temporal_position must be BEFORE.",
        )
    if claim["manual_review_required"] is not True:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_BEFORE_CLAIM",
            "BEFORE temporal claim manual_review_required must remain true.",
        )
    hashes = claim.get("evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes.keys()) != set(EVIDENCE_HASH_FIELDS):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MISSING_LINEAGE",
            "BEFORE temporal claim evidence_hashes fields changed unexpectedly.",
        )
    for hash_value in hashes.values():
        if not _is_nonzero_hash(hash_value):
            raise TemporalSameObjectPairingRefusal(
                "REFUSED_MISSING_LINEAGE",
                "BEFORE temporal claim evidence_hashes must preserve non-zero hashes.",
            )
    if hashes["packet_root"] != claim["packet_root"]:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MISSING_LINEAGE",
            "BEFORE temporal claim packet_root preservation mismatch.",
        )
    for field_name in ("packet_root", "source_claim_root", "temporal_claim_root"):
        if not _is_nonzero_hash(claim[field_name]):
            raise TemporalSameObjectPairingRefusal(
                "REFUSED_MISSING_LINEAGE",
                f"BEFORE temporal claim missing {field_name}.",
            )
    if claim["temporal_claim_root"] != _hash_json(_root_material(claim, "temporal_claim_root")):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_HASH_OR_ROOT_MISMATCH",
            f"BEFORE temporal_claim_root mismatch for {claim['temporal_claim_id']}.",
        )


def _validate_after_claim(claim: Dict[str, Any]) -> None:
    if not isinstance(claim, dict) or set(claim.keys()) != set(AFTER_CANDIDATE_FIELDS):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_AFTER_CLAIM",
            "AFTER temporal claim candidate fields do not match schema.",
        )
    for field_name in AFTER_CANDIDATE_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(claim, field_name, "REFUSED_MISSING_LINEAGE")
    if claim["temporal_position"] != "AFTER":
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_NON_AFTER_CLAIM",
            "AFTER temporal claim temporal_position must be AFTER.",
        )
    if claim["manual_review_required"] is not True:
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_MALFORMED_AFTER_CLAIM",
            "AFTER temporal claim manual_review_required must remain true.",
        )
    for field_name in ("packet_root", "packet_hash", "source_claim_root", "temporal_claim_root"):
        if not _is_nonzero_hash(claim[field_name]):
            raise TemporalSameObjectPairingRefusal(
                "REFUSED_MISSING_LINEAGE",
                f"AFTER temporal claim missing {field_name}.",
            )
    if claim["temporal_claim_root"] != _hash_json(_root_material(claim, "temporal_claim_root")):
        raise TemporalSameObjectPairingRefusal(
            "REFUSED_HASH_OR_ROOT_MISMATCH",
            f"AFTER temporal_claim_root mismatch for {claim['temporal_claim_id']}.",
        )


def _domain_tokens(text: str) -> List[str]:
    found: Set[str] = set()
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    for token in ALLOWED_DOMAIN_TOKENS:
        if token in words:
            found.add(token)
    return [token for token in ALLOWED_DOMAIN_TOKENS if token in found]


def _before_lineage(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_claim_id": claim["source_claim_id"],
        "temporal_evidence_packet_id": claim["temporal_evidence_packet_id"],
        "localized_segment_id": claim["localized_segment_id"],
        "source_id": claim["source_id"],
        "source_type": claim["source_type"],
        "url": claim["url"],
        "publisher": claim["publisher"],
        "topic": claim["topic"],
        "evidence_hashes": claim["evidence_hashes"],
        "packet_root": claim["packet_root"],
        "source_claim_root": claim["source_claim_root"],
        "temporal_claim_root": claim["temporal_claim_root"],
    }


def _after_lineage(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_claim_id": claim["source_claim_id"],
        "snapshot_id": claim["snapshot_id"],
        "linked_after_candidate_id": claim["linked_after_candidate_id"],
        "manual_after_snapshot_packet_id": claim["manual_after_snapshot_packet_id"],
        "url": claim["url"],
        "title": claim["title"],
        "publisher": claim["publisher"],
        "published_date": claim["published_date"],
        "after_stability_target_id": claim["after_stability_target_id"],
        "linked_before_claim_id": claim["linked_before_claim_id"],
        "target_theme": claim["target_theme"],
        "target_evidence_type": claim["target_evidence_type"],
        "preferred_source_family": claim["preferred_source_family"],
        "packet_root": claim["packet_root"],
        "packet_hash": claim["packet_hash"],
        "source_claim_root": claim["source_claim_root"],
        "temporal_claim_root": claim["temporal_claim_root"],
    }


def _make_pair(
    before_claim: Dict[str, Any],
    after_claim: Dict[str, Any],
    matched_tokens: List[str],
    before_tokens: List[str],
    after_tokens: List[str],
    index: int,
) -> Dict[str, Any]:
    pair = {
        "temporal_comparison_pair_id": f"TEMPORAL_COMPARISON_PAIR_{index:06d}",
        "pairing_method": PAIRING_METHOD,
        "matched_domain_tokens": matched_tokens,
        "before_domain_tokens": before_tokens,
        "after_domain_tokens": after_tokens,
        "before_temporal_claim_id": before_claim["temporal_claim_id"],
        "after_temporal_claim_id": after_claim["temporal_claim_id"],
        "before_claim_text": before_claim["claim_text"],
        "after_claim_text": after_claim["claim_text"],
        "before_claim_time": before_claim["claim_time"],
        "after_claim_time": after_claim["claim_time"],
        "before_temporal_position": before_claim["temporal_position"],
        "after_temporal_position": after_claim["temporal_position"],
        "before_lineage": _before_lineage(before_claim),
        "after_lineage": _after_lineage(after_claim),
        "manual_review_required": True,
        "neutral_pairing_only": True,
        "pair_root": "",
    }
    pair["pair_root"] = _hash_json(_pair_root_material(pair))
    return pair


def _unpaired_before_claim(claim: Dict[str, Any], tokens: List[str]) -> Dict[str, Any]:
    payload = dict(claim)
    payload["domain_tokens"] = tokens
    payload["unpaired_reason"] = "NO_SHARED_ALLOWED_DOMAIN_TOKEN"
    return payload


def _unpaired_after_claim(claim: Dict[str, Any], tokens: List[str]) -> Dict[str, Any]:
    payload = dict(claim)
    payload["domain_tokens"] = tokens
    payload["unpaired_reason"] = "NO_SHARED_ALLOWED_DOMAIN_TOKEN"
    return payload


def _candidate_identity(claim: Any, side: str) -> Tuple[str, str]:
    if not isinstance(claim, dict):
        return (f"UNKNOWN_{side}_CLAIM", "UNKNOWN_SOURCE")
    return (
        str(claim.get("temporal_claim_id") or f"UNKNOWN_{side}_CLAIM"),
        str(claim.get("source_id") or claim.get("linked_after_candidate_id") or "UNKNOWN_SOURCE"),
    )


def _make_refusal(claim: Any, side: str, code: str, reason: str) -> Dict[str, Any]:
    claim_id, source_id = _candidate_identity(claim, side)
    refusal = {
        "refusal_id": f"TEMPORAL_SAME_OBJECT_PAIRING_REFUSAL_{side}_{claim_id}",
        "claim_side": side,
        "temporal_claim_id": claim_id,
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
    refusal["refusal_root"] = _hash_json(_root_material(refusal, "refusal_root"))
    return refusal


def _validate_pair(pair: Dict[str, Any]) -> None:
    if tuple(pair.keys()) != PAIR_FIELDS:
        raise ValueError("Temporal comparison pair fields changed unexpectedly.")
    if not pair["matched_domain_tokens"]:
        raise ValueError("Temporal comparison pair must preserve matched domain tokens.")
    if pair["before_temporal_position"] != "BEFORE" or pair["after_temporal_position"] != "AFTER":
        raise ValueError("Temporal comparison pair positions must remain BEFORE/AFTER.")
    if pair["manual_review_required"] is not True or pair["neutral_pairing_only"] is not True:
        raise ValueError("Temporal comparison pair governance flags must remain closed.")
    if pair["pair_root"] != _hash_json(_pair_root_material(pair)):
        raise ValueError(f"pair_root mismatch for {pair['temporal_comparison_pair_id']}.")


def _status_for(pair_count: int, refusal_count: int, before_count: int, after_count: int) -> str:
    if pair_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if (pair_count > 0 or before_count > 0 or after_count > 0) and refusal_count > 0:
        return PARTIAL_STATUS
    if before_count > 0 and after_count > 0 and refusal_count == 0:
        return NO_MATCH_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(summary)
    material.pop("temporal_same_object_pairing_root", None)
    material.pop("temporal_same_object_pairing_report_hash", None)
    return material


def _build_report(summary: Dict[str, Any], pairs: List[Dict[str, Any]], refusals: List[Dict[str, Any]]) -> str:
    pair_lines = ["- None"]
    if pairs:
        pair_lines = []
        for pair in pairs[:20]:
            pair_lines.extend(
                [
                    f"- {pair['temporal_comparison_pair_id']}",
                    f"  - Matched Tokens: {', '.join(pair['matched_domain_tokens'])}",
                    f"  - BEFORE: {pair['before_temporal_claim_id']}",
                    f"  - AFTER: {pair['after_temporal_claim_id']}",
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
            "# Temporal Same-Object Pairing",
            "",
            "This lane creates neutral BEFORE/AFTER temporal comparison pairs from "
            "deterministic allowed domain-token overlap only. It does not detect "
            "contradictions, score contradictions, evaluate predicate incompatibility, "
            "or approve evidence.",
            "",
            "## Summary",
            f"- temporal_same_object_pairing_status: {summary['temporal_same_object_pairing_status']}",
            f"- before_temporal_claim_count: {summary['before_temporal_claim_count']}",
            f"- after_temporal_claim_count: {summary['after_temporal_claim_count']}",
            f"- temporal_comparison_pair_count: {summary['temporal_comparison_pair_count']}",
            f"- unpaired_before_claim_count: {summary['unpaired_before_claim_count']}",
            f"- unpaired_after_claim_count: {summary['unpaired_after_claim_count']}",
            f"- refusal_count: {summary['refusal_count']}",
            "",
            "## First Pairs",
            *pair_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Fetched: 0",
            "- Live Web Access Performed: 0",
            "- LLM Calls: 0",
            "- Embeddings Created: 0",
            "- Claims Rewritten: 0",
            "- Claims Normalized Semantically: 0",
            "- Contradictions Created: 0",
            "- Claim Pairs Created: 0",
            "- Final Reports Created: 0",
            "- Approved Evidence: 0",
            "- Production Ready: False",
            "",
        ]
    )


def build_temporal_same_object_pairing(
    before_candidates_path: Path = DEFAULT_BEFORE_CANDIDATES,
    before_summary_path: Path = DEFAULT_BEFORE_SUMMARY,
    after_candidates_path: Path = DEFAULT_AFTER_CANDIDATES,
    after_summary_path: Path = DEFAULT_AFTER_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    pairs: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_before_claims: List[Dict[str, Any]] = []
    valid_after_claims: List[Dict[str, Any]] = []

    try:
        before_candidates = _load_before_candidates(before_candidates_path)
        after_candidates = _load_after_candidates(after_candidates_path)
        _validate_summary(
            before_summary_path,
            "before_temporal_claim_normalization_status",
            BEFORE_UPSTREAM_STATUSES,
            "before_temporal_claim_candidate_count",
            len(before_candidates),
        )
        _validate_summary(
            after_summary_path,
            "temporal_claim_normalization_status",
            AFTER_UPSTREAM_STATUSES,
            "temporal_claim_candidate_count",
            len(after_candidates),
        )
    except TemporalSameObjectPairingRefusal as exc:
        before_candidates = []
        after_candidates = []
        refusals.append(_make_refusal({}, "UPSTREAM", exc.code, exc.reason))

    if not refusals:
        seen_before_ids: Set[str] = set()
        for claim in before_candidates:
            try:
                _validate_before_claim(claim)
                claim_id = claim["temporal_claim_id"]
                if claim_id in seen_before_ids:
                    raise TemporalSameObjectPairingRefusal(
                        "REFUSED_MALFORMED_BEFORE_CLAIM",
                        f"Duplicate BEFORE temporal_claim_id: {claim_id}.",
                    )
                seen_before_ids.add(claim_id)
                valid_before_claims.append(claim)
            except TemporalSameObjectPairingRefusal as exc:
                refusals.append(_make_refusal(claim, "BEFORE", exc.code, exc.reason))

        seen_after_ids: Set[str] = set()
        for claim in after_candidates:
            try:
                _validate_after_claim(claim)
                claim_id = claim["temporal_claim_id"]
                if claim_id in seen_after_ids:
                    raise TemporalSameObjectPairingRefusal(
                        "REFUSED_MALFORMED_AFTER_CLAIM",
                        f"Duplicate AFTER temporal_claim_id: {claim_id}.",
                    )
                seen_after_ids.add(claim_id)
                valid_after_claims.append(claim)
            except TemporalSameObjectPairingRefusal as exc:
                refusals.append(_make_refusal(claim, "AFTER", exc.code, exc.reason))

    before_tokens_by_id = {
        claim["temporal_claim_id"]: _domain_tokens(claim["claim_text"]) for claim in valid_before_claims
    }
    after_tokens_by_id = {
        claim["temporal_claim_id"]: _domain_tokens(claim["claim_text"]) for claim in valid_after_claims
    }
    paired_before_ids: Set[str] = set()
    paired_after_ids: Set[str] = set()
    if not refusals:
        for before_claim in valid_before_claims:
            before_tokens = before_tokens_by_id[before_claim["temporal_claim_id"]]
            for after_claim in valid_after_claims:
                after_tokens = after_tokens_by_id[after_claim["temporal_claim_id"]]
                matched_tokens = [
                    token for token in ALLOWED_DOMAIN_TOKENS if token in before_tokens and token in after_tokens
                ]
                if not matched_tokens:
                    continue
                pair = _make_pair(
                    before_claim,
                    after_claim,
                    matched_tokens,
                    before_tokens,
                    after_tokens,
                    len(pairs) + 1,
                )
                _validate_pair(pair)
                pairs.append(pair)
                paired_before_ids.add(before_claim["temporal_claim_id"])
                paired_after_ids.add(after_claim["temporal_claim_id"])

    unpaired_before = [
        _unpaired_before_claim(claim, before_tokens_by_id[claim["temporal_claim_id"]])
        for claim in valid_before_claims
        if claim["temporal_claim_id"] not in paired_before_ids
    ]
    unpaired_after = [
        _unpaired_after_claim(claim, after_tokens_by_id[claim["temporal_claim_id"]])
        for claim in valid_after_claims
        if claim["temporal_claim_id"] not in paired_after_ids
    ]

    status = _status_for(len(pairs), len(refusals), len(valid_before_claims), len(valid_after_claims))
    summary = {
        "temporal_same_object_pairing_status": status,
        "schema_version": SCHEMA_VERSION,
        "pairing_method": PAIRING_METHOD,
        "allowed_domain_tokens": list(ALLOWED_DOMAIN_TOKENS),
        "before_temporal_claim_count": len(valid_before_claims),
        "after_temporal_claim_count": len(valid_after_claims),
        "temporal_comparison_pair_count": len(pairs),
        "unpaired_before_claim_count": len(unpaired_before),
        "unpaired_after_claim_count": len(unpaired_after),
        "refusal_count": len(refusals),
        "pair_ids": [pair["temporal_comparison_pair_id"] for pair in pairs],
        "pair_roots": [pair["pair_root"] for pair in pairs],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "matched_domain_token_counts": {
            token: sum(1 for pair in pairs if token in pair["matched_domain_tokens"])
            for token in ALLOWED_DOMAIN_TOKENS
        },
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "before_claim_text_exact_copy": True,
        "after_claim_text_exact_copy": True,
        "before_lineage_preserved": len(refusals) == 0,
        "after_lineage_preserved": len(refusals) == 0,
        "neutral_pairing_only": True,
        "predicate_incompatibility_evaluated": False,
        "contradiction_labels_created": 0,
        "contradiction_scores_created": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "embeddings_created": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "claim_pairs_created": 0,
        "final_reports_created": 0,
        "approved_evidence": 0,
        "production_ready": False,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
        "temporal_same_object_pairing_report_hash": "",
        "temporal_same_object_pairing_root": "",
    }
    summary["temporal_same_object_pairing_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(summary, pairs, refusals)
    summary["temporal_same_object_pairing_report_hash"] = _sha256_text(report)
    summary["temporal_same_object_pairing_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(summary, pairs, refusals)

    for counter_name in (
        "contradiction_labels_created",
        "contradiction_scores_created",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "claim_pairs_created",
        "final_reports_created",
        "approved_evidence",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if summary["production_ready"] is not False or not _closed_flags(summary):
        raise ValueError("Temporal same-object pairing guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / PAIRS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "temporal_comparison_pairs": pairs,
        },
    )
    _write_json(
        output_dir / UNPAIRED_BEFORE_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "unpaired_before_claims": unpaired_before,
        },
    )
    _write_json(
        output_dir / UNPAIRED_AFTER_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "unpaired_after_claims": unpaired_after,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "temporal_same_object_pairing_refusals": refusals,
        },
    )
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "temporal_comparison_pairs": pairs,
        "unpaired_before_claims": unpaired_before,
        "unpaired_after_claims": unpaired_after,
        "temporal_same_object_pairing_refusals": refusals,
        "report": report,
    }


__all__ = ["build_temporal_same_object_pairing"]
