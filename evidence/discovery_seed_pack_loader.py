#!/usr/bin/env python3
"""
Discovery Seed Pack Loader v2.

Loads deterministic discovery targets for the Duma Boko Contradiction Engine v2.
Discovery seeds are investigation targets only: they are not verified evidence,
do not contain quotes or timestamps, and do not establish contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_DISCOVERY_SEEDS = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")
DEFAULT_RESEARCH_SUMMARY = Path("docs/research/Duma_Boko_Investigation_Cases_Summary.md")

DEFAULT_OUTPUT_DIR = Path("outputs/discovery_seed_pack_loader")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "discovery_seed_pack_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "discovery_seed_pack_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_discovery_seeds.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "discovery_seed_pack_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "discovery_seed_pack_schema.json"

ENGINE_STATUS = "DISCOVERY_SEED_PACK_CANDIDATE"
SCHEMA_VERSION = "discovery_seed_pack_loader_v2"
UNSPECIFIED_URL = "UNSPECIFIED"
UNVERIFIED_EXACT_URL = "UNVERIFIED_EXACT_URL"

SOURCE_TYPES = (
    "document",
    "parliament_record",
    "video",
    "official_statement",
    "news_article",
    "social_media",
)

METADATA_FIELDS = (
    "generated_on",
    "generator_mode",
    "speaker_name",
    "geographic_context",
    "date_range_focus",
)

CASE_FIELDS = (
    "case_id",
    "title",
    "speaker_name",
    "topic",
    "expected_claim_keywords",
    "priority",
    "notes",
)

SOURCE_FIELDS = (
    "source_id",
    "case_id",
    "source_type",
    "platform",
    "url",
    "title",
    "published_date",
    "channel_author",
    "duration",
    "transcript_available",
    "transcript_url",
    "manual_timestamp_hints",
    "confidence_of_relevance",
    "verification_status",
    "requires_manual_review",
    "language",
    "geographic_context",
    "captions_asr_likely",
    "search_query_suggestions",
    "notes",
)

SEED_FIELDS = (
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
        "metadata_fields": list(METADATA_FIELDS),
        "investigation_case_fields": list(CASE_FIELDS),
        "candidate_source_fields": list(SOURCE_FIELDS),
        "discovery_seed_fields": list(SEED_FIELDS),
        "source_types": list(SOURCE_TYPES),
        "missing_url_rule": {
            "url": UNSPECIFIED_URL,
            "candidate_url": UNSPECIFIED_URL,
            "verification_status": UNVERIFIED_EXACT_URL,
            "requires_manual_review": True,
        },
        "prohibited_outputs": {
            "verified_evidence_count": 0,
            "quote_count": 0,
            "timestamp_count": 0,
            "contradiction_count": 0,
        },
        "root_rules": {
            "case_roots": "sha256 over each investigation case",
            "candidate_source_roots": "sha256 over each candidate source",
            "discovery_seed_roots": "sha256 over each discovery seed",
            "discovery_seed_pack_root": (
                "sha256 over sorted case, source, seed, markdown, and schema hashes"
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
        raise ValueError("discovery_seed_pack_schema schema_version changed unexpectedly")
    if schema.get("investigation_case_fields") != list(CASE_FIELDS):
        raise ValueError("discovery_seed_pack_schema investigation_case_fields changed")
    if schema.get("candidate_source_fields") != list(SOURCE_FIELDS):
        raise ValueError("discovery_seed_pack_schema candidate_source_fields changed")
    if schema.get("discovery_seed_fields") != list(SEED_FIELDS):
        raise ValueError("discovery_seed_pack_schema discovery_seed_fields changed")


def _validate_metadata(payload: Dict[str, Any]) -> None:
    for field_name in METADATA_FIELDS:
        _require_nonempty_string(payload, field_name, "DiscoverySeedPack")
    if payload["generated_on"] != "2026-06-01":
        raise ValueError("DiscoverySeedPack.generated_on must remain deterministic")
    if payload["generator_mode"] != "knowledge_based_no_live_web_access":
        raise ValueError("DiscoverySeedPack.generator_mode changed unexpectedly")
    if payload["speaker_name"] != "Duma Boko":
        raise ValueError("DiscoverySeedPack.speaker_name changed unexpectedly")
    if payload["geographic_context"] != "Botswana":
        raise ValueError("DiscoverySeedPack.geographic_context changed unexpectedly")


def _validate_case(case: Dict[str, Any]) -> None:
    if tuple(case.keys()) != CASE_FIELDS:
        raise ValueError("Investigation case fields changed unexpectedly")
    for field_name in ("case_id", "title", "speaker_name", "topic", "priority", "notes"):
        _require_nonempty_string(case, field_name, "InvestigationCase")
    keywords = case.get("expected_claim_keywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("InvestigationCase.expected_claim_keywords must be non-empty")
    if case["speaker_name"] != "Duma Boko":
        raise ValueError("InvestigationCase.speaker_name changed unexpectedly")


def _validate_source(source: Dict[str, Any], case_ids: set[str]) -> None:
    if tuple(source.keys()) != SOURCE_FIELDS:
        raise ValueError("Candidate source fields changed unexpectedly")
    for field_name in (
        "source_id",
        "case_id",
        "source_type",
        "platform",
        "url",
        "title",
        "published_date",
        "channel_author",
        "duration",
        "transcript_url",
        "verification_status",
        "language",
        "geographic_context",
        "notes",
    ):
        _require_nonempty_string(source, field_name, "CandidateSource")
    if source["case_id"] not in case_ids:
        raise ValueError(f"CandidateSource references unknown case_id: {source['case_id']}")
    if source["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source['source_type']}")
    if source["url"] == UNSPECIFIED_URL:
        if source["verification_status"] != UNVERIFIED_EXACT_URL:
            raise ValueError("UNSPECIFIED source URL requires UNVERIFIED_EXACT_URL")
        if source["requires_manual_review"] is not True:
            raise ValueError("UNSPECIFIED source URL requires manual review")
    if source["transcript_available"] is not False:
        raise ValueError("Discovery candidates must not mark transcripts available")
    if source["manual_timestamp_hints"] != []:
        raise ValueError("Discovery candidates must not include timestamp hints")
    if not isinstance(source["search_query_suggestions"], list) or not source[
        "search_query_suggestions"
    ]:
        raise ValueError("CandidateSource.search_query_suggestions must be non-empty")


def _validate_seed(seed: Dict[str, Any], case_ids: set[str]) -> None:
    if tuple(seed.keys()) != SEED_FIELDS:
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
    if seed["case_id"] not in case_ids:
        raise ValueError(f"DiscoverySeed references unknown case_id: {seed['case_id']}")
    if seed["speaker_name"] != "Duma Boko":
        raise ValueError("DiscoverySeed.speaker_name changed unexpectedly")
    if seed["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"Unsupported discovery seed source_type: {seed['source_type']}")
    if seed["candidate_url"] != UNSPECIFIED_URL:
        raise ValueError("Discovery seed candidate_url must remain UNSPECIFIED")
    keywords = seed.get("expected_claim_keywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("DiscoverySeed.expected_claim_keywords must be non-empty")


def _case_source_counts(sources: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for source in sources:
        counts[source["case_id"]] = counts.get(source["case_id"], 0) + 1
    return counts


def _cases_with_video_sources(cases: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> int:
    count = 0
    for case in cases:
        if any(
            source["case_id"] == case["case_id"] and source["source_type"] == "video"
            for source in sources
        ):
            count += 1
    return count


def _validated_payload(
    payload: Dict[str, Any],
    case_roots: List[str],
    source_roots: List[str],
    seed_roots: List[str],
    markdown_hash: str,
    schema_hash: str,
    pack_root: str,
) -> Dict[str, Any]:
    return {
        "metadata": {
            field_name: payload[field_name] for field_name in METADATA_FIELDS
        },
        "investigation_cases": payload["investigation_cases"],
        "candidate_sources": payload["candidate_sources"],
        "discovery_seeds": payload["discovery_seeds"],
        "case_roots": case_roots,
        "candidate_source_roots": source_roots,
        "discovery_seed_roots": seed_roots,
        "research_summary_hash": markdown_hash,
        "discovery_seed_pack_schema_hash": schema_hash,
        "discovery_seed_pack_root": pack_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
    }


def _build_report(summary: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Discovery Seed Pack Loader v2",
            "",
            "This report validates discovery targets only. It does not verify sources, "
            "quotes, timestamps, transcripts, claims, or contradictions.",
            "",
            "## Summary",
            f"- discovery_seed_pack_status: {summary['discovery_seed_pack_status']}",
            f"- investigation_case_count: {summary['investigation_case_count']}",
            f"- candidate_source_count: {summary['candidate_source_count']}",
            f"- discovery_seed_count: {summary['discovery_seed_count']}",
            f"- cases_with_minimum_sources: {summary['cases_with_minimum_sources']}",
            f"- cases_with_video_candidates: {summary['cases_with_video_candidates']}",
            f"- manual_review_required_count: {summary['manual_review_required_count']}",
            "",
            "## Guardrails",
            "- Verified Evidence Count: 0",
            "- Quote Count: 0",
            "- Timestamp Count: 0",
            "- Contradiction Count: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
            "## Next Lane",
            "The v2 evidence discovery execution engine may consume "
            "`validated_discovery_seeds.json` to resolve real URLs and metadata without "
            "inventing evidence.",
            "",
        ]
    )


def build_discovery_seed_pack_loader(
    discovery_seed_path: Path = DEFAULT_DISCOVERY_SEEDS,
    research_summary_path: Path = DEFAULT_RESEARCH_SUMMARY,
) -> Dict[str, Any]:
    payload = _load_json(discovery_seed_path)
    if not payload:
        raise ValueError("Discovery seed pack input is missing")
    if not research_summary_path.exists():
        raise ValueError("Research summary Markdown is missing")

    _validate_metadata(payload)
    cases = payload.get("investigation_cases")
    sources = payload.get("candidate_sources")
    seeds = payload.get("discovery_seeds")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("Discovery seed pack must contain exactly 10 investigation cases")
    if not isinstance(sources, list) or len(sources) < 60:
        raise ValueError("Discovery seed pack must contain at least 60 candidate sources")
    if not isinstance(seeds, list) or len(seeds) < 60:
        raise ValueError("Discovery seed pack must contain at least 60 discovery seeds")

    for case in cases:
        _validate_case(case)
    case_ids = {case["case_id"] for case in cases}
    for source in sources:
        _validate_source(source, case_ids)
    for seed in seeds:
        _validate_seed(seed, case_ids)

    source_counts = _case_source_counts(sources)
    cases_with_minimum_sources = sum(
        1 for case in cases if source_counts.get(case["case_id"], 0) >= 6
    )
    if cases_with_minimum_sources != 10:
        raise ValueError("Every investigation case must have at least 6 candidate sources")
    cases_with_video_candidates = _cases_with_video_sources(cases, sources)
    if cases_with_video_candidates != 10:
        raise ValueError("Every investigation case must have at least one video candidate")

    manual_review_required_count = sum(
        1
        for source in sources
        if source["url"] == UNSPECIFIED_URL
        and source["verification_status"] == UNVERIFIED_EXACT_URL
        and source["requires_manual_review"] is True
    )
    if manual_review_required_count != len(sources):
        raise ValueError("Every missing URL source must require manual review")

    schema = _schema()
    validate_schema(schema)
    markdown_text = research_summary_path.read_text(encoding="utf-8")
    markdown_hash = _sha256_text(markdown_text)
    schema_hash = _hash_json(schema)
    case_roots = [_hash_json(case) for case in cases]
    source_roots = [_hash_json(source) for source in sources]
    seed_roots = [_hash_json(seed) for seed in seeds]
    pack_root = _hash_json(
        {
            "case_roots": sorted(case_roots),
            "candidate_source_roots": sorted(source_roots),
            "discovery_seed_roots": sorted(seed_roots),
            "research_summary_hash": markdown_hash,
            "schema_hash": schema_hash,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )

    summary = {
        "discovery_seed_pack_status": ENGINE_STATUS,
        "investigation_case_count": len(cases),
        "candidate_source_count": len(sources),
        "discovery_seed_count": len(seeds),
        "cases_with_minimum_sources": cases_with_minimum_sources,
        "cases_with_video_candidates": cases_with_video_candidates,
        "verified_evidence_count": 0,
        "quote_count": 0,
        "timestamp_count": 0,
        "contradiction_count": 0,
        "manual_review_required_count": manual_review_required_count,
        "research_summary_hash": markdown_hash,
        "discovery_seed_pack_schema_hash": schema_hash,
        "case_roots": case_roots,
        "candidate_source_roots": source_roots,
        "discovery_seed_roots": seed_roots,
        "discovery_seed_pack_root": pack_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if not _closed_flags(summary):
        raise ValueError("Discovery seed pack summary flags must remain closed")

    status_payload = {
        "records": [
            {
                "discovery_seed_pack_status": ENGINE_STATUS,
                "investigation_case_count": len(cases),
                "candidate_source_count": len(sources),
                "discovery_seed_count": len(seeds),
                "discovery_seed_pack_root": pack_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    validated_payload = _validated_payload(
        payload,
        case_roots,
        source_roots,
        seed_roots,
        markdown_hash,
        schema_hash,
        pack_root,
    )
    report = _build_report(summary)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(VALIDATED_OUTPUT, validated_payload)
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "validated_discovery_seeds": validated_payload,
        "schema": schema,
        "report": report,
    }
