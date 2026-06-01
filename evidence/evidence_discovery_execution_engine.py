#!/usr/bin/env python3
"""
Evidence Discovery Execution Engine v2.

Resolves validated discovery seeds into candidate public sources only when a
real URL is present. Unresolved or unverifiable seeds become deterministic
refusal records. This lane creates no quotes, timestamps, evidence approvals,
or contradiction findings.
"""

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_VALIDATED_DISCOVERY_SEEDS = Path(
    "outputs/discovery_seed_pack_loader/validated_discovery_seeds.json"
)
DEFAULT_DISCOVERY_SUMMARY = Path(
    "outputs/discovery_seed_pack_loader/discovery_seed_pack_summary.json"
)
DEFAULT_DISCOVERY_INPUT = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")
DEFAULT_RESEARCH_SUMMARY = Path("docs/research/Duma_Boko_Investigation_Cases_Summary.md")

DEFAULT_OUTPUT_DIR = Path("outputs/evidence_discovery_execution_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_discovery_execution_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_discovery_execution_summary.json"
RESOLVED_OUTPUT = DEFAULT_OUTPUT_DIR / "resolved_candidate_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "discovery_execution_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_discovery_execution_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_discovery_execution_schema.json"

SCHEMA_VERSION = "evidence_discovery_execution_engine_v2"
UPSTREAM_STATUS = "DISCOVERY_SEED_PACK_CANDIDATE"
DRY_RUN_STATUS = "EVIDENCE_DISCOVERY_EXECUTION_DRY_RUN_REFUSED"
CANDIDATE_STATUS = "EVIDENCE_DISCOVERY_EXECUTION_CANDIDATE"
PARTIAL_STATUS = "EVIDENCE_DISCOVERY_EXECUTION_PARTIAL"
REFUSED_STATUS = "EVIDENCE_DISCOVERY_EXECUTION_REFUSED"

UNSPECIFIED_URL = "UNSPECIFIED"
RESOLUTION_METHOD_PROVIDED_URL = "provided_candidate_url"
RESOLUTION_METHOD_REFUSED_UNSPECIFIED = "refused_unresolved_candidate_url"
SOURCE_VERIFICATION_STATUS = "CANDIDATE_SOURCE_REQUIRES_MANUAL_REVIEW"

SUPPORTED_SOURCE_TYPES = (
    "video",
    "audio",
    "transcript",
    "document",
    "screenshot",
    "official_statement",
    "social_media",
    "news_article",
    "parliament_record",
)

REFUSAL_CODES = (
    "REFUSED_UNRESOLVED_CANDIDATE_URL",
    "REFUSED_MISSING_TITLE",
    "REFUSED_MISSING_SPEAKER",
    "REFUSED_UNSUPPORTED_SOURCE_TYPE",
    "REFUSED_SOURCE_NOT_PUBLIC",
    "REFUSED_SOURCE_METADATA_UNVERIFIED",
)

RESOLVED_SOURCE_FIELDS = (
    "resolved_source_id",
    "seed_id",
    "case_id",
    "speaker_name",
    "speaker_party",
    "source_type",
    "platform",
    "source_url",
    "source_title",
    "source_owner",
    "published_date",
    "duration",
    "transcript_available",
    "candidate_topics",
    "expected_claim_keywords",
    "source_resolution_method",
    "source_verification_status",
    "source_metadata_hash",
    "resolved_source_root",
    "manual_review_required",
    "notes",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "seed_id",
    "case_id",
    "speaker_name",
    "source_type",
    "platform",
    "candidate_title",
    "refusal_code",
    "refusal_reason",
    "search_query",
    "manual_review_required",
    "refusal_root",
)

SEED_REQUIRED_FIELDS = (
    "seed_id",
    "case_id",
    "speaker_name",
    "speaker_party",
    "source_type",
    "platform",
    "search_query",
    "candidate_url",
    "candidate_title",
    "expected_topic",
    "expected_claim_keywords",
    "notes",
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


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "supported_source_types": list(SUPPORTED_SOURCE_TYPES),
        "resolved_source_fields": list(RESOLVED_SOURCE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "seed_required_fields": list(SEED_REQUIRED_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "dry_run_behavior": (
            "Dry-run performs local validation only and refuses all UNSPECIFIED URLs."
        ),
        "from_seeds_behavior": (
            "From-seeds resolves only supplied real candidate URLs; unresolved seeds "
            "become refusal records. Web search requires explicit opt-in and must not "
            "invent URLs."
        ),
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "source_metadata_hash": (
                "sha256 over deterministic source metadata excluding roots"
            ),
            "resolved_source_root": "sha256 over resolved source excluding resolved_source_root",
            "refusal_root": "sha256 over refusal record excluding refusal_root",
            "evidence_discovery_execution_engine_root": (
                "sha256 over sorted resolved source roots and sorted refusal roots"
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
        raise ValueError("evidence_discovery_execution_schema schema_version changed")
    if schema.get("supported_source_types") != list(SUPPORTED_SOURCE_TYPES):
        raise ValueError("supported_source_types changed unexpectedly")
    if schema.get("resolved_source_fields") != list(RESOLVED_SOURCE_FIELDS):
        raise ValueError("resolved_source_fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("refusal_fields changed unexpectedly")


def _validate_seed(seed: Dict[str, Any]) -> None:
    if set(seed.keys()) != set(SEED_REQUIRED_FIELDS):
        raise ValueError("Discovery seed fields changed unexpectedly")
    for field_name in (
        "seed_id",
        "case_id",
        "speaker_name",
        "source_type",
        "platform",
        "search_query",
        "candidate_url",
        "candidate_title",
        "expected_topic",
        "notes",
    ):
        _require_nonempty_string(seed, field_name, "DiscoverySeed")
    if not isinstance(seed.get("expected_claim_keywords"), list) or not seed[
        "expected_claim_keywords"
    ]:
        raise ValueError("DiscoverySeed.expected_claim_keywords must be non-empty")


def _validate_upstream(
    validated_payload: Dict[str, Any],
    discovery_summary: Dict[str, Any],
    discovery_input: Dict[str, Any],
    research_summary_path: Path,
) -> None:
    if not validated_payload:
        raise ValueError("validated_discovery_seeds.json is missing")
    if not discovery_summary:
        raise ValueError("discovery_seed_pack_summary.json is missing")
    if not discovery_input:
        raise ValueError("duma_boko_discovery_seeds.json is missing")
    if not research_summary_path.exists():
        raise ValueError("research summary Markdown is missing")
    if discovery_summary.get("discovery_seed_pack_status") != UPSTREAM_STATUS:
        raise ValueError("Discovery seed pack upstream status is invalid")
    if discovery_summary.get("investigation_case_count") != 10:
        raise ValueError("Discovery seed pack investigation_case_count is invalid")
    if discovery_summary.get("candidate_source_count") != 60:
        raise ValueError("Discovery seed pack candidate_source_count is invalid")
    if discovery_summary.get("discovery_seed_count") != 60:
        raise ValueError("Discovery seed pack discovery_seed_count is invalid")
    if discovery_summary.get("cases_with_video_candidates") != 10:
        raise ValueError("Discovery seed pack video candidate count is invalid")
    if discovery_summary.get("quote_count") != 0:
        raise ValueError("Discovery seed pack must not create quotes")
    if discovery_summary.get("timestamp_count") != 0:
        raise ValueError("Discovery seed pack must not create timestamps")
    if discovery_summary.get("contradiction_count") != 0:
        raise ValueError("Discovery seed pack must not create contradictions")
    if discovery_summary.get("manual_review_required_count") != 60:
        raise ValueError("Discovery seed pack manual review count is invalid")
    if not _closed_flags(discovery_summary):
        raise ValueError("Discovery seed pack governance flags must remain closed")
    if not _is_nonzero_hash(discovery_summary.get("discovery_seed_pack_root")):
        raise ValueError("Discovery seed pack root is invalid")

    seeds = validated_payload.get("discovery_seeds")
    if not isinstance(seeds, list) or len(seeds) != 60:
        raise ValueError("validated_discovery_seeds must contain 60 seeds")
    for seed in seeds:
        _validate_seed(seed)


def _is_real_candidate_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate_url = value.strip()
    return bool(candidate_url) and candidate_url != UNSPECIFIED_URL


def _is_public_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("https://") or lowered.startswith("http://")


def _source_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "seed_id": source["seed_id"],
        "case_id": source["case_id"],
        "speaker_name": source["speaker_name"],
        "source_type": source["source_type"],
        "platform": source["platform"],
        "source_url": source["source_url"],
        "source_title": source["source_title"],
        "source_owner": source["source_owner"],
        "published_date": source["published_date"],
        "duration": source["duration"],
        "transcript_available": source["transcript_available"],
        "candidate_topics": source["candidate_topics"],
        "expected_claim_keywords": source["expected_claim_keywords"],
        "source_resolution_method": source["source_resolution_method"],
        "source_verification_status": source["source_verification_status"],
        "manual_review_required": source["manual_review_required"],
    }


def _resolved_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(source)
    material.pop("resolved_source_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_refusal(seed: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REFUSAL_EXECUTION_{seed.get('seed_id', 'UNKNOWN')}",
        "seed_id": seed.get("seed_id", ""),
        "case_id": seed.get("case_id", ""),
        "speaker_name": seed.get("speaker_name", ""),
        "source_type": seed.get("source_type", ""),
        "platform": seed.get("platform", ""),
        "candidate_title": seed.get("candidate_title", ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "search_query": seed.get("search_query", ""),
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _make_resolved_source(seed: Dict[str, Any]) -> Dict[str, Any]:
    source = {
        "resolved_source_id": f"RESOLVED_SOURCE_{seed['seed_id']}",
        "seed_id": seed["seed_id"],
        "case_id": seed["case_id"],
        "speaker_name": seed["speaker_name"],
        "speaker_party": seed.get("speaker_party", ""),
        "source_type": seed["source_type"],
        "platform": seed["platform"],
        "source_url": seed["candidate_url"].strip(),
        "source_title": seed["candidate_title"],
        "source_owner": "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "published_date": "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "duration": "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "transcript_available": False,
        "candidate_topics": [seed["expected_topic"]],
        "expected_claim_keywords": seed["expected_claim_keywords"],
        "source_resolution_method": RESOLUTION_METHOD_PROVIDED_URL,
        "source_verification_status": SOURCE_VERIFICATION_STATUS,
        "source_metadata_hash": "",
        "resolved_source_root": "",
        "manual_review_required": True,
        "notes": (
            "Candidate URL was supplied in the seed input. Metadata, source ownership, "
            "transcript availability, quote location, and public-use suitability still "
            "require manual review."
        ),
    }
    source["source_metadata_hash"] = _hash_json(_source_metadata_material(source))
    source["resolved_source_root"] = _hash_json(_resolved_root_material(source))
    return source


def _resolve_or_refuse_seed(
    seed: Dict[str, Any],
    mode: str,
    allow_web_search: bool,
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    try:
        _validate_seed(seed)
    except ValueError as exc:
        return None, _make_refusal(
            seed,
            "REFUSED_SOURCE_METADATA_UNVERIFIED",
            f"Seed validation failed: {exc}",
        )

    if seed["source_type"] not in SUPPORTED_SOURCE_TYPES:
        return None, _make_refusal(
            seed,
            "REFUSED_UNSUPPORTED_SOURCE_TYPE",
            "Seed source_type is not supported by the discovery execution engine.",
        )
    if not seed["speaker_name"].strip():
        return None, _make_refusal(
            seed,
            "REFUSED_MISSING_SPEAKER",
            "Seed does not contain a non-empty speaker_name.",
        )
    if not seed["candidate_title"].strip():
        return None, _make_refusal(
            seed,
            "REFUSED_MISSING_TITLE",
            "Seed does not contain a non-empty candidate_title.",
        )
    if not _is_real_candidate_url(seed["candidate_url"]):
        suffix = (
            " Web search was explicitly allowed, but this deterministic lane has no "
            "implemented local resolver that can safely produce a URL."
            if allow_web_search
            else " Web search was not enabled."
        )
        return None, _make_refusal(
            seed,
            "REFUSED_UNRESOLVED_CANDIDATE_URL",
            "Seed candidate_url is UNSPECIFIED or empty." + suffix,
        )
    if not _is_public_url(seed["candidate_url"]):
        return None, _make_refusal(
            seed,
            "REFUSED_SOURCE_NOT_PUBLIC",
            "Seed candidate_url is not an HTTP(S) public URL.",
        )
    if mode == "dry-run":
        return None, _make_refusal(
            seed,
            "REFUSED_UNRESOLVED_CANDIDATE_URL",
            "Dry-run mode refuses all candidate URL resolution.",
        )
    return _make_resolved_source(seed), None


def validate_resolved_source(source: Dict[str, Any]) -> None:
    if tuple(source.keys()) != RESOLVED_SOURCE_FIELDS:
        raise ValueError("Resolved source fields changed unexpectedly")
    for field_name in (
        "resolved_source_id",
        "seed_id",
        "case_id",
        "speaker_name",
        "source_type",
        "platform",
        "source_url",
        "source_title",
        "source_owner",
        "published_date",
        "duration",
        "source_resolution_method",
        "source_verification_status",
        "source_metadata_hash",
        "resolved_source_root",
        "notes",
    ):
        _require_nonempty_string(source, field_name, "ResolvedCandidateSource")
    if source["source_url"] == UNSPECIFIED_URL:
        raise ValueError("ResolvedCandidateSource.source_url must not be UNSPECIFIED")
    if not _is_public_url(source["source_url"]):
        raise ValueError("ResolvedCandidateSource.source_url must be public HTTP(S)")
    if source["source_type"] not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"Unsupported resolved source_type: {source['source_type']}")
    if source["manual_review_required"] is not True:
        raise ValueError("ResolvedCandidateSource.manual_review_required must remain true")
    if source["transcript_available"] is not False:
        raise ValueError("ResolvedCandidateSource must not claim transcripts are available")
    if not _is_nonzero_hash(source["source_metadata_hash"]):
        raise ValueError("ResolvedCandidateSource.source_metadata_hash must be non-zero")
    if not _is_nonzero_hash(source["resolved_source_root"]):
        raise ValueError("ResolvedCandidateSource.resolved_source_root must be non-zero")
    if source["source_metadata_hash"] != _hash_json(_source_metadata_material(source)):
        raise ValueError(f"source_metadata_hash mismatch for {source['resolved_source_id']}")
    if source["resolved_source_root"] != _hash_json(_resolved_root_material(source)):
        raise ValueError(f"resolved_source_root mismatch for {source['resolved_source_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Discovery execution refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "seed_id",
        "case_id",
        "speaker_name",
        "source_type",
        "platform",
        "candidate_title",
        "refusal_code",
        "refusal_reason",
        "search_query",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "DiscoveryExecutionRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("DiscoveryExecutionRefusal.manual_review_required must remain true")
    if not _is_nonzero_hash(refusal["refusal_root"]):
        raise ValueError("DiscoveryExecutionRefusal.refusal_root must be non-zero")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _status_for(mode: str, resolved_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if resolved_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if resolved_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    allow_web_search: bool,
    resolved_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    engine_root: str,
) -> str:
    resolved_lines = ["- None"]
    if resolved_sources:
        resolved_lines = []
        for source in resolved_sources:
            resolved_lines.extend(
                [
                    f"- Resolved Source ID: {source['resolved_source_id']}",
                    f"  - Case ID: {source['case_id']}",
                    f"  - Seed ID: {source['seed_id']}",
                    f"  - Source URL: {source['source_url']}",
                    f"  - Manual Review Required: {source['manual_review_required']}",
                ]
            )

    refused_lines = ["- None"]
    if refusals:
        refused_lines = []
        for refusal in refusals:
            refused_lines.extend(
                [
                    f"- Refusal ID: {refusal['refusal_id']}",
                    f"  - Case ID: {refusal['case_id']}",
                    f"  - Seed ID: {refusal['seed_id']}",
                    f"  - Refusal Code: {refusal['refusal_code']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )

    lines = [
        "# Evidence Discovery Execution Engine v2",
        "",
        "This report resolves discovery seeds into candidate public sources only when "
        "a real public URL is present. It does not create quotes, timestamps, "
        "approved evidence, or contradiction findings.",
        "",
        "## Summary",
        f"- evidence_discovery_execution_status: {status}",
        f"- mode: {mode}",
        f"- allow_web_search: {allow_web_search}",
        f"- resolved_source_count: {len(resolved_sources)}",
        f"- refusal_count: {len(refusals)}",
        f"- evidence_discovery_execution_engine_root: {engine_root}",
        "",
        "## Resolved Candidate Sources",
        *resolved_lines,
        "",
        "## Unresolved / Refused Seeds",
        *refused_lines,
        "",
        "## Next Manual Actions",
        "- Replace UNSPECIFIED candidate URLs with verified public URLs.",
        "- Confirm source metadata and ownership.",
        "- Capture transcripts, document text, quote locations, and forensic anchors in a later lane.",
        "- Keep all unresolved items as refusals until source evidence is verifiable.",
        "",
        "## Guardrails",
        "- Quotes Created: 0",
        "- Timestamps Created: 0",
        "- Contradictions Created: 0",
        "- Evidence Approved Count: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def _seeds_for_mode(
    mode: str,
    validated_payload: Dict[str, Any],
    discovery_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if mode == "dry-run":
        return list(validated_payload.get("discovery_seeds", []))
    return list(discovery_input.get("discovery_seeds", []))


def build_evidence_discovery_execution_engine(
    mode: str = "dry-run",
    allow_web_search: bool = False,
    validated_discovery_path: Path = DEFAULT_VALIDATED_DISCOVERY_SEEDS,
    discovery_summary_path: Path = DEFAULT_DISCOVERY_SUMMARY,
    discovery_input_path: Path = DEFAULT_DISCOVERY_INPUT,
    research_summary_path: Path = DEFAULT_RESEARCH_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-seeds"):
        raise ValueError("mode must be dry-run or from-seeds")

    validated_payload = _load_json(validated_discovery_path)
    discovery_summary = _load_json(discovery_summary_path)
    discovery_input = _load_json(discovery_input_path)
    _validate_upstream(
        validated_payload,
        discovery_summary,
        discovery_input,
        research_summary_path,
    )
    schema = _schema()
    validate_schema(schema)

    seeds = _seeds_for_mode(mode, validated_payload, discovery_input)
    resolved_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for seed in seeds:
        resolved, refusal = _resolve_or_refuse_seed(seed, mode, allow_web_search)
        if resolved is not None:
            validate_resolved_source(resolved)
            resolved_sources.append(resolved)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    resolved_roots = [source["resolved_source_root"] for source in resolved_sources]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    engine_root = _hash_json(
        {
            "resolved_source_roots": sorted(resolved_roots),
            "refusal_roots": sorted(refusal_roots),
            "quotes_created": 0,
            "timestamps_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        }
    )
    status = _status_for(mode, len(resolved_sources), len(refusals))
    unresolved_url_refusal_count = sum(
        1
        for refusal in refusals
        if refusal["refusal_code"] == "REFUSED_UNRESOLVED_CANDIDATE_URL"
    )
    schema_hash = _hash_json(schema)
    report = _build_report(
        status,
        mode,
        allow_web_search,
        resolved_sources,
        refusals,
        engine_root,
    )
    report_hash = _sha256_text(report)
    summary = {
        "evidence_discovery_execution_status": status,
        "mode": mode,
        "allow_web_search": allow_web_search,
        "seed_count": len(seeds),
        "resolved_source_count": len(resolved_sources),
        "refusal_count": len(refusals),
        "unresolved_url_refusal_count": unresolved_url_refusal_count,
        "quotes_created": 0,
        "timestamps_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "resolved_source_roots": resolved_roots,
        "refusal_roots": refusal_roots,
        "evidence_discovery_execution_schema_hash": schema_hash,
        "evidence_discovery_execution_report_hash": report_hash,
        "evidence_discovery_execution_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if not _closed_flags(summary):
        raise ValueError("Evidence discovery execution summary flags must remain closed")
    status_payload = {
        "records": [
            {
                "evidence_discovery_execution_status": status,
                "seed_count": len(seeds),
                "resolved_source_count": len(resolved_sources),
                "refusal_count": len(refusals),
                "evidence_discovery_execution_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(RESOLVED_OUTPUT, {"resolved_candidate_sources": resolved_sources})
    _write_json(REFUSALS_OUTPUT, {"discovery_execution_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "resolved_candidate_sources": resolved_sources,
        "discovery_execution_refusals": refusals,
        "schema": schema,
        "report": report,
    }
