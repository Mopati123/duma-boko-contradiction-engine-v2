#!/usr/bin/env python3
"""
Registry Discovery to Bootstrap Bridge v2.

Converts verified promoted endpoints into canonical source-registry update
candidates. This lane does not modify the registry, harvest content, create
transcripts, create quotes, create claims, or create contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse
import hashlib
import json


DEFAULT_PROMOTED_ENDPOINTS = Path(
    "outputs/manual_review_endpoint_promotion_engine/promoted_registry_endpoints.json"
)
DEFAULT_PROMOTION_SUMMARY = Path(
    "outputs/manual_review_endpoint_promotion_engine/endpoint_promotion_summary.json"
)
DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/registry_discovery_to_bootstrap_bridge")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_bridge_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_bridge_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_update_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_bridge_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_bridge_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_bridge_schema.json"

SCHEMA_VERSION = "registry_discovery_to_bootstrap_bridge_v2"
UPSTREAM_PROMOTION_SCHEMA_VERSION = "manual_review_endpoint_promotion_engine_v2"
UPSTREAM_REGISTRY_SCHEMA_VERSION = "canonical_source_registry_engine_v2"

REGISTRY_BRIDGE_STATUS = "REGISTRY_DISCOVERY_TO_BOOTSTRAP_BRIDGE_CANDIDATE"
REGISTRY_UPDATE_CANDIDATE_STATUS = "REGISTRY_UPDATE_CANDIDATE"
SOURCE_ORIGIN = "manual_review_endpoint_promotion_engine"
VERIFIED_ENDPOINT_STATUS = "PROMOTED_VERIFIED_PUBLIC_ENDPOINT"
SEARCH_ENDPOINT_STATUS = "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED"
UNSPECIFIED = "UNSPECIFIED"

SOURCE_CATEGORIES = (
    "official_party",
    "official_government",
    "parliament_record",
    "youtube_channel",
    "facebook_page",
    "x_twitter_account",
    "news_publisher",
    "radio_tv_broadcaster",
    "public_archive",
    "manual_review_source",
)

SUPPORTED_PLATFORMS = (
    "party_public_communications",
    "government_public_communications",
    "parliament_record_search",
    "youtube",
    "facebook",
    "x_twitter",
    "news_archive_search",
    "broadcast_archive_search",
    "public_archive_search",
    "manual_review",
)

PROMOTED_ENDPOINT_FIELDS = (
    "promoted_endpoint_id",
    "strategy_candidate_id",
    "registry_target_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "http_status",
    "content_type",
    "redirect_chain",
    "verification_status",
    "promotion_method",
    "manual_review_required",
    "reasoning_summary",
    "metadata_hash",
    "promoted_endpoint_root",
)

REGISTRY_SOURCE_FIELDS = (
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "search_url_template",
    "speaker_focus",
    "geographic_context",
    "trust_tier",
    "expected_source_types",
    "manual_review_required",
    "notes",
)

REGISTRY_UPDATE_CANDIDATE_FIELDS = (
    "registry_update_candidate_id",
    "promoted_endpoint_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "http_status",
    "content_type",
    "trust_tier",
    "manual_review_required",
    "source_origin",
    "candidate_status",
    "metadata_hash",
    "registry_update_candidate_root",
)

REGISTRY_BRIDGE_REFUSAL_FIELDS = (
    "refusal_id",
    "promoted_endpoint_id",
    "registry_target_id",
    "candidate_url",
    "refusal_code",
    "refusal_reason",
    "verification_status",
    "manual_review_required",
    "refusal_root",
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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_generic_search_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    if host.endswith("google.com") and path.startswith("/search"):
        return True
    if host.endswith("bing.com") and path.startswith("/search"):
        return True
    if host.endswith("duckduckgo.com") and (path.startswith("/html") or "q=" in query):
        return True
    if host.endswith("youtube.com") and path.startswith("/results"):
        return True
    if host.endswith("facebook.com") and path.startswith("/search"):
        return True
    if host.endswith("twitter.com") and path.startswith("/search"):
        return True
    if host.endswith("x.com") and path.startswith("/search"):
        return True
    return False


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
        "registry_discovery_to_bootstrap_bridge_only": True,
        "upstream_promotion_schema_version": UPSTREAM_PROMOTION_SCHEMA_VERSION,
        "upstream_registry_schema_version": UPSTREAM_REGISTRY_SCHEMA_VERSION,
        "registry_update_candidate_fields": list(REGISTRY_UPDATE_CANDIDATE_FIELDS),
        "registry_bridge_refusal_fields": list(REGISTRY_BRIDGE_REFUSAL_FIELDS),
        "source_categories": list(SOURCE_CATEGORIES),
        "supported_platforms": list(SUPPORTED_PLATFORMS),
        "modes": ["from-promotions"],
        "consumption_rules": {
            "consume_only": VERIFIED_ENDPOINT_STATUS,
            "exclude_without_refusal": SEARCH_ENDPOINT_STATUS,
            "registry_mutation": False,
            "harvesting": False,
        },
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
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
        raise ValueError("registry bridge schema_version changed")
    if schema.get("registry_update_candidate_fields") != list(REGISTRY_UPDATE_CANDIDATE_FIELDS):
        raise ValueError("registry update candidate fields changed")
    if schema.get("registry_bridge_refusal_fields") != list(REGISTRY_BRIDGE_REFUSAL_FIELDS):
        raise ValueError("registry bridge refusal fields changed")


def _candidate_root_material(candidate: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(candidate)
    material.pop("registry_update_candidate_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_refusal(
    sequence_number: int,
    endpoint: Dict[str, Any],
    refusal_code: str,
    refusal_reason: str,
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REGISTRY_BRIDGE_REFUSAL_{sequence_number:03d}",
        "promoted_endpoint_id": endpoint.get("promoted_endpoint_id", UNSPECIFIED),
        "registry_target_id": endpoint.get("registry_target_id", UNSPECIFIED),
        "candidate_url": endpoint.get("resolved_url") or endpoint.get("base_url") or UNSPECIFIED,
        "refusal_code": refusal_code,
        "refusal_reason": refusal_reason,
        "verification_status": endpoint.get("verification_status", UNSPECIFIED),
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REGISTRY_BRIDGE_REFUSAL_FIELDS):
        raise ValueError("Registry bridge refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "promoted_endpoint_id",
        "registry_target_id",
        "candidate_url",
        "refusal_code",
        "refusal_reason",
        "verification_status",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RegistryBridgeRefusal")
    if not refusal["refusal_code"].startswith("REFUSED_"):
        raise ValueError("Registry bridge refusal code must start with REFUSED_")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RegistryBridgeRefusal.manual_review_required must be true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def validate_promoted_endpoint(endpoint: Dict[str, Any]) -> None:
    if set(endpoint.keys()) != set(PROMOTED_ENDPOINT_FIELDS):
        raise ValueError("Promoted endpoint fields changed unexpectedly")
    for field_name in (
        "promoted_endpoint_id",
        "strategy_candidate_id",
        "registry_target_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "content_type",
        "verification_status",
        "promotion_method",
        "reasoning_summary",
        "metadata_hash",
        "promoted_endpoint_root",
    ):
        _require_nonempty_string(endpoint, field_name, "PromotedEndpoint")
    if endpoint["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {endpoint['source_category']}")
    if endpoint["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {endpoint['platform']}")
    if endpoint["manual_review_required"] is not True:
        raise ValueError("PromotedEndpoint.manual_review_required must remain true")
    if not isinstance(endpoint["http_status"], int):
        raise ValueError("PromotedEndpoint.http_status must be an integer")
    if not isinstance(endpoint["redirect_chain"], list):
        raise ValueError("PromotedEndpoint.redirect_chain must be a list")


def _validate_verified_endpoint_for_bridge(endpoint: Dict[str, Any]) -> str | None:
    if endpoint["verification_status"] != VERIFIED_ENDPOINT_STATUS:
        return "Endpoint is not a verified public promotion."
    if not _is_public_url(endpoint["base_url"]) or not _is_public_url(endpoint["resolved_url"]):
        return "Verified promoted endpoint URL fields must be public HTTP(S)."
    if endpoint["http_status"] < 200 or endpoint["http_status"] >= 400:
        return "Verified promoted endpoint http_status must be 200-399."
    if not endpoint["content_type"] or endpoint["content_type"] == UNSPECIFIED:
        return "Verified promoted endpoint content_type must be present."
    if not _is_nonzero_hash(endpoint["metadata_hash"]):
        return "Verified promoted endpoint metadata_hash must be non-empty."
    if _is_generic_search_url(endpoint["base_url"]) or _is_generic_search_url(endpoint["resolved_url"]):
        return "Generic search result endpoints cannot become registry update candidates."
    return None


def validate_registry_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(REGISTRY_SOURCE_FIELDS):
        raise ValueError("Registry source fields changed unexpectedly")
    for field_name in (
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "search_url_template",
        "speaker_focus",
        "geographic_context",
        "notes",
    ):
        _require_nonempty_string(source, field_name, "RegistrySource")
    if source["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {source['source_category']}")
    if source["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {source['platform']}")
    if source["speaker_focus"] != "Duma Boko":
        raise ValueError("RegistrySource.speaker_focus must remain Duma Boko")
    if source["geographic_context"] != "Botswana":
        raise ValueError("RegistrySource.geographic_context must remain Botswana")
    if not isinstance(source.get("trust_tier"), int) or source["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("RegistrySource.trust_tier must be an integer from 1 to 4")
    if source["manual_review_required"] is not True:
        raise ValueError("RegistrySource.manual_review_required must remain true")


def validate_registry_update_candidate(candidate: Dict[str, Any]) -> None:
    if set(candidate.keys()) != set(REGISTRY_UPDATE_CANDIDATE_FIELDS):
        raise ValueError("Registry update candidate fields changed unexpectedly")
    for field_name in (
        "registry_update_candidate_id",
        "promoted_endpoint_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "content_type",
        "source_origin",
        "candidate_status",
        "metadata_hash",
        "registry_update_candidate_root",
    ):
        _require_nonempty_string(candidate, field_name, "RegistryUpdateCandidate")
    if candidate["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {candidate['source_category']}")
    if candidate["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {candidate['platform']}")
    if not isinstance(candidate["http_status"], int) or candidate["http_status"] < 200 or candidate["http_status"] >= 400:
        raise ValueError("RegistryUpdateCandidate.http_status must be 200-399")
    if not isinstance(candidate["trust_tier"], int) or candidate["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("RegistryUpdateCandidate.trust_tier must be an integer from 1 to 4")
    if candidate["manual_review_required"] is not True:
        raise ValueError("RegistryUpdateCandidate.manual_review_required must remain true")
    if candidate["source_origin"] != SOURCE_ORIGIN:
        raise ValueError("RegistryUpdateCandidate.source_origin changed")
    if candidate["candidate_status"] != REGISTRY_UPDATE_CANDIDATE_STATUS:
        raise ValueError("RegistryUpdateCandidate.candidate_status changed")
    if not _is_nonzero_hash(candidate["metadata_hash"]):
        raise ValueError("RegistryUpdateCandidate.metadata_hash must be non-empty")
    if _is_generic_search_url(candidate["base_url"]) or _is_generic_search_url(candidate["resolved_url"]):
        raise ValueError("RegistryUpdateCandidate must not point at a generic search endpoint")
    if candidate["registry_update_candidate_root"] != _hash_json(_candidate_root_material(candidate)):
        raise ValueError(f"root mismatch for {candidate['registry_update_candidate_id']}")


def _validate_upstream(
    promoted_payload: Dict[str, Any],
    promotion_summary: Dict[str, Any],
    registry_input: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if not promoted_payload:
        raise ValueError("promoted registry endpoints output is missing")
    if not promotion_summary:
        raise ValueError("endpoint promotion summary output is missing")
    if not registry_input:
        raise ValueError("source registry input is missing")
    if registry_input.get("registry_version") != UPSTREAM_REGISTRY_SCHEMA_VERSION:
        raise ValueError("source registry input version is invalid")
    if promotion_summary.get("endpoint_promotion_status") not in (
        "ENDPOINT_PROMOTION_CANDIDATE",
        "ENDPOINT_PROMOTION_PARTIAL",
    ):
        raise ValueError("endpoint promotion summary must contain verified promotion output")
    if promotion_summary.get("mode") != "verify-endpoints":
        raise ValueError("endpoint promotion summary must come from verify-endpoints mode")
    if not _closed_flags(promotion_summary):
        raise ValueError("endpoint promotion guardrails must remain closed")
    for counter_name in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if promotion_summary.get(counter_name) != 0:
            raise ValueError(f"endpoint promotion {counter_name} must be 0")

    endpoints = promoted_payload.get("promoted_registry_endpoints")
    if not isinstance(endpoints, list):
        raise ValueError("promoted_registry_endpoints must be a list")
    for endpoint in endpoints:
        validate_promoted_endpoint(endpoint)

    registry_sources = registry_input.get("registry_sources")
    if not isinstance(registry_sources, list) or len(registry_sources) != 20:
        raise ValueError("source registry input must contain 20 source families")
    registry_by_id: Dict[str, Dict[str, Any]] = {}
    for source in registry_sources:
        validate_registry_source(source)
        registry_by_id[source["registry_source_id"]] = source

    verified_count = sum(1 for endpoint in endpoints if endpoint["verification_status"] == VERIFIED_ENDPOINT_STATUS)
    search_count = sum(1 for endpoint in endpoints if endpoint["verification_status"] == SEARCH_ENDPOINT_STATUS)
    if promotion_summary.get("promoted_endpoint_count") != verified_count:
        raise ValueError("promoted endpoint count does not match verified promotion records")
    if promotion_summary.get("verified_public_endpoint_count") != verified_count:
        raise ValueError("verified public endpoint count does not match promotion records")
    if promotion_summary.get("search_endpoint_review_count") != search_count:
        raise ValueError("search endpoint review count does not match promotion records")
    return endpoints, registry_by_id


def _make_registry_update_candidate(
    sequence_number: int,
    endpoint: Dict[str, Any],
    registry_source: Dict[str, Any],
) -> Dict[str, Any]:
    candidate = {
        "registry_update_candidate_id": f"REGISTRY_UPDATE_CANDIDATE_{sequence_number:03d}",
        "promoted_endpoint_id": endpoint["promoted_endpoint_id"],
        "source_name": endpoint["source_name"],
        "source_category": endpoint["source_category"],
        "platform": endpoint["platform"],
        "base_url": endpoint["base_url"],
        "resolved_url": endpoint["resolved_url"],
        "http_status": endpoint["http_status"],
        "content_type": endpoint["content_type"],
        "trust_tier": registry_source["trust_tier"],
        "manual_review_required": True,
        "source_origin": SOURCE_ORIGIN,
        "candidate_status": REGISTRY_UPDATE_CANDIDATE_STATUS,
        "metadata_hash": endpoint["metadata_hash"],
        "registry_update_candidate_root": "",
    }
    candidate["registry_update_candidate_root"] = _hash_json(_candidate_root_material(candidate))
    return candidate


def _build_report(
    status: str,
    candidates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    search_endpoint_excluded_count: int,
    root: str,
) -> str:
    candidate_lines = ["- None"]
    if candidates:
        candidate_lines = []
        for candidate in candidates[:40]:
            candidate_lines.extend(
                [
                    f"- {candidate['registry_update_candidate_id']}",
                    f"  - Promoted Endpoint: {candidate['promoted_endpoint_id']}",
                    f"  - Source: {candidate['source_name']}",
                    f"  - Resolved URL: {candidate['resolved_url']}",
                    f"  - Trust Tier: {candidate['trust_tier']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:40]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Candidate URL: {refusal['candidate_url']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    lines = [
        "# Registry Discovery to Bootstrap Bridge v2",
        "",
        "This lane converts verified promoted endpoints into registry update "
        "candidates. It does not mutate the canonical registry, harvest content, "
        "create transcripts, create quotes, create claims, or create contradictions.",
        "",
        "## Summary",
        f"- registry_bridge_status: {status}",
        f"- registry_update_candidate_count: {len(candidates)}",
        f"- search_endpoint_excluded_count: {search_endpoint_excluded_count}",
        f"- refusal_count: {len(refusals)}",
        f"- registry_bridge_root: {root}",
        "",
        "## Registry Update Candidates",
        *candidate_lines,
        "",
        "## Refusals",
        *refusal_lines,
        "",
        "## Guardrails",
        "- Search Endpoints Consumed As Verified Sources: 0",
        "- Quotes Created: 0",
        "- Timestamps Created: 0",
        "- Transcripts Created: 0",
        "- Claims Created: 0",
        "- Contradictions Created: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def build_registry_discovery_to_bootstrap_bridge(
    mode: str = "from-promotions",
    promoted_endpoints_path: Path = DEFAULT_PROMOTED_ENDPOINTS,
    promotion_summary_path: Path = DEFAULT_PROMOTION_SUMMARY,
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
) -> Dict[str, Any]:
    if mode != "from-promotions":
        raise ValueError("Registry discovery to bootstrap bridge supports from-promotions only")

    promoted_payload = _load_json(promoted_endpoints_path)
    promotion_summary = _load_json(promotion_summary_path)
    registry_input = _load_json(registry_input_path)
    endpoints, registry_by_id = _validate_upstream(promoted_payload, promotion_summary, registry_input)
    schema = _schema()
    validate_schema(schema)

    candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    search_endpoint_excluded_count = 0
    for endpoint in endpoints:
        verification_status = endpoint["verification_status"]
        if verification_status == SEARCH_ENDPOINT_STATUS:
            search_endpoint_excluded_count += 1
            continue
        if verification_status != VERIFIED_ENDPOINT_STATUS:
            continue

        validation_error = _validate_verified_endpoint_for_bridge(endpoint)
        registry_source = registry_by_id.get(endpoint["registry_target_id"])
        if registry_source is None:
            validation_error = "Promoted endpoint registry_target_id is missing from canonical registry."
        if validation_error:
            refusal = _make_refusal(
                len(refusals) + 1,
                endpoint,
                "REFUSED_REGISTRY_UPDATE_CANDIDATE",
                validation_error,
            )
            validate_refusal(refusal)
            refusals.append(refusal)
            continue

        candidate = _make_registry_update_candidate(len(candidates) + 1, endpoint, registry_source)
        validate_registry_update_candidate(candidate)
        candidates.append(candidate)

    candidate_roots = [candidate["registry_update_candidate_root"] for candidate in candidates]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "registry_update_candidate_roots": sorted(candidate_roots),
            "refusal_roots": sorted(refusal_roots),
            "search_endpoint_excluded_count": search_endpoint_excluded_count,
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    report = _build_report(
        REGISTRY_BRIDGE_STATUS,
        candidates,
        refusals,
        search_endpoint_excluded_count,
        root,
    )
    verified_endpoint_input_count = sum(
        1 for endpoint in endpoints if endpoint["verification_status"] == VERIFIED_ENDPOINT_STATUS
    )
    summary = {
        "registry_bridge_status": REGISTRY_BRIDGE_STATUS,
        "mode": mode,
        "promoted_endpoint_count": promotion_summary["promoted_endpoint_count"],
        "verified_endpoint_input_count": verified_endpoint_input_count,
        "search_endpoint_excluded_count": search_endpoint_excluded_count,
        "registry_update_candidate_count": len(candidates),
        "refusal_count": len(refusals),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "registry_update_candidate_roots": candidate_roots,
        "refusal_roots": refusal_roots,
        "registry_bridge_schema_hash": _hash_json(schema),
        "registry_bridge_report_hash": _sha256_text(report),
        "registry_bridge_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "downstream_engines_untouched": True,
        "canonical_registry_untouched": True,
        "search_endpoints_consumed_as_verified_sources": 0,
        "no_generated_outputs_committed": True,
    }
    if summary["registry_update_candidate_count"] != summary["verified_endpoint_input_count"] - summary["refusal_count"]:
        raise ValueError("Registry update candidate count must match accepted verified endpoints")
    if summary["search_endpoints_consumed_as_verified_sources"] != 0:
        raise ValueError("Search endpoints must not be consumed as verified registry sources")
    for counter_name in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("Registry bridge guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "registry_bridge_status": REGISTRY_BRIDGE_STATUS,
                "verified_endpoint_input_count": verified_endpoint_input_count,
                "registry_update_candidate_count": len(candidates),
                "search_endpoint_excluded_count": search_endpoint_excluded_count,
                "refusal_count": len(refusals),
                "registry_bridge_root": root,
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
    _write_json(CANDIDATES_OUTPUT, {"registry_update_candidates": candidates})
    _write_json(REFUSALS_OUTPUT, {"registry_bridge_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "registry_update_candidates": candidates,
        "registry_bridge_refusals": refusals,
        "schema": schema,
        "report": report,
    }
