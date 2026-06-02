#!/usr/bin/env python3
"""
Registry Source Discovery Strategy Upgrade v2.

Builds stronger source-specific registry endpoint probes without creating
evidence packets, quotes, timestamps, transcript lines, claims,
contradictions, proof chains, or reports outside this lane.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse
import hashlib
import json
import urllib.error
import urllib.request


DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")
DEFAULT_VALIDATED_REGISTRY = Path(
    "outputs/canonical_source_registry_engine/validated_source_registry.json"
)
DEFAULT_DISCOVERY_SUMMARY = Path(
    "outputs/registry_source_discovery_engine/registry_source_discovery_summary.json"
)
DEFAULT_DISCOVERY_REFUSALS = Path(
    "outputs/registry_source_discovery_engine/registry_source_discovery_refusals.json"
)
DEFAULT_RESEARCH_SUMMARY = Path("docs/research/Duma_Boko_Investigation_Cases_Summary.md")
DEFAULT_DISCOVERY_SEEDS = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")

DEFAULT_OUTPUT_DIR = Path("outputs/registry_source_discovery_strategy_upgrade")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_upgrade_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_upgrade_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_upgrade_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "strategy_upgrade_schema.json"

SCHEMA_VERSION = "registry_source_discovery_strategy_upgrade_v2"
UPSTREAM_REGISTRY_SCHEMA_VERSION = "canonical_source_registry_engine_v2"

DEMO_STATUS = "REGISTRY_SOURCE_DISCOVERY_STRATEGY_DEMO_CANDIDATE"
CANDIDATE_STATUS = "REGISTRY_SOURCE_DISCOVERY_STRATEGY_CANDIDATE"
PARTIAL_STATUS = "REGISTRY_SOURCE_DISCOVERY_STRATEGY_PARTIAL"
REFUSED_STATUS = "REGISTRY_SOURCE_DISCOVERY_STRATEGY_REFUSED"

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

VERIFICATION_STATUSES = (
    "STRATEGY_DEMO_UNVERIFIED",
    "VERIFIED_REACHABLE_PUBLIC_ENDPOINT",
    "DISCOVERED_REQUIRES_MANUAL_REVIEW",
    "REFUSED_NOT_FOUND",
    "REFUSED_UNREACHABLE",
    "REFUSED_LOGIN_REQUIRED",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_UNSUPPORTED_PLATFORM",
    "REFUSED_WEB_PROBE_UNAVAILABLE",
)

CANDIDATE_FIELDS = (
    "strategy_candidate_id",
    "registry_target_id",
    "source_name",
    "source_category",
    "platform",
    "strategy_name",
    "query",
    "candidate_url",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "reasoning_summary",
    "metadata_hash",
    "strategy_candidate_root",
)

REFUSAL_FIELDS = (
    "strategy_refusal_id",
    "registry_target_id",
    "source_name",
    "source_category",
    "platform",
    "strategy_name",
    "query",
    "candidate_url",
    "http_status",
    "content_type",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
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

APPLIED_REGISTRY_OPTIONAL_FIELDS = (
    "resolved_url",
    "verification_status",
    "source_origin",
    "verified_endpoints",
)

VALIDATED_SOURCE_FIELDS = REGISTRY_SOURCE_FIELDS + ("registry_source_root",)


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


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _duckduckgo_url(query: str) -> str:
    return f"https://duckduckgo.com/html/?q={quote_plus(query)}"


def _bing_url(query: str) -> str:
    return f"https://www.bing.com/search?q={quote_plus(query)}"


def _google_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


def _youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _facebook_search_url(query: str) -> str:
    return f"https://www.facebook.com/search/top/?q={quote_plus(query)}"


def _x_search_url(query: str) -> str:
    return f"https://twitter.com/search?q={quote_plus(query)}&src=typed_query"


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_source_discovery_strategy_upgrade_only": True,
        "candidate_fields": list(CANDIDATE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "source_categories": list(SOURCE_CATEGORIES),
        "supported_platforms": list(SUPPORTED_PLATFORMS),
        "verification_statuses": list(VERIFICATION_STATUSES),
        "modes": ["dry-run", "probe-web"],
        "strategies": [
            "direct_known_domain_probe",
            "platform_specific_search_url",
            "site_scoped_query_probe",
            "organization_speaker_probe",
            "manual_review_candidate_preservation",
        ],
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
        "root_rules": {
            "metadata_hash": "sha256 over deterministic candidate metadata excluding roots",
            "strategy_candidate_root": "sha256 over candidate excluding strategy_candidate_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "strategy_upgrade_root": (
                "sha256 over sorted candidate roots, sorted refusal roots, and closed flags"
            ),
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("strategy_upgrade_schema schema_version changed")
    if schema.get("candidate_fields") != list(CANDIDATE_FIELDS):
        raise ValueError("strategy candidate fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("strategy refusal fields changed")


def _metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in CANDIDATE_FIELDS
        if field not in ("metadata_hash", "strategy_candidate_root")
    }


def _candidate_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(record)
    material.pop("strategy_candidate_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_candidate(
    sequence_number: int,
    source: Dict[str, Any],
    strategy_name: str,
    query: str,
    candidate_url: str,
    http_status: int,
    content_type: str,
    verification_status: str,
    reasoning_summary: str,
) -> Dict[str, Any]:
    record = {
        "strategy_candidate_id": f"STRATEGY_CANDIDATE_{sequence_number:03d}",
        "registry_target_id": source["registry_source_id"],
        "source_name": source["source_name"],
        "source_category": source["source_category"],
        "platform": source["platform"],
        "strategy_name": strategy_name,
        "query": query,
        "candidate_url": candidate_url,
        "http_status": int(http_status),
        "content_type": content_type or UNSPECIFIED,
        "verification_status": verification_status,
        "manual_review_required": True,
        "reasoning_summary": reasoning_summary,
        "metadata_hash": "",
        "strategy_candidate_root": "",
    }
    record["metadata_hash"] = _hash_json(_metadata_material(record))
    record["strategy_candidate_root"] = _hash_json(_candidate_root_material(record))
    return record


def _make_refusal(
    sequence_number: int,
    source: Dict[str, Any],
    strategy_name: str,
    query: str,
    candidate_url: str,
    http_status: int,
    content_type: str,
    refusal_code: str,
    refusal_reason: str,
) -> Dict[str, Any]:
    refusal = {
        "strategy_refusal_id": f"STRATEGY_REFUSAL_{sequence_number:03d}",
        "registry_target_id": source["registry_source_id"],
        "source_name": source["source_name"],
        "source_category": source["source_category"],
        "platform": source["platform"],
        "strategy_name": strategy_name,
        "query": query,
        "candidate_url": candidate_url or UNSPECIFIED,
        "http_status": int(http_status),
        "content_type": content_type or UNSPECIFIED,
        "refusal_code": refusal_code,
        "refusal_reason": refusal_reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_strategy_candidate(record: Dict[str, Any]) -> None:
    if set(record.keys()) != set(CANDIDATE_FIELDS):
        raise ValueError("Strategy candidate fields changed unexpectedly")
    for field_name in (
        "strategy_candidate_id",
        "registry_target_id",
        "source_name",
        "source_category",
        "platform",
        "strategy_name",
        "query",
        "candidate_url",
        "content_type",
        "verification_status",
        "reasoning_summary",
        "metadata_hash",
        "strategy_candidate_root",
    ):
        _require_nonempty_string(record, field_name, "StrategyCandidate")
    if record["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {record['source_category']}")
    if record["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {record['platform']}")
    if record["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {record['verification_status']}")
    if record["verification_status"].startswith("REFUSED_"):
        raise ValueError("Candidates must not carry refusal statuses")
    if record["manual_review_required"] is not True:
        raise ValueError("StrategyCandidate.manual_review_required must remain true")
    if not isinstance(record["http_status"], int):
        raise ValueError("StrategyCandidate.http_status must be an integer")
    if record["verification_status"] == "VERIFIED_REACHABLE_PUBLIC_ENDPOINT":
        if not _is_public_url(record["candidate_url"]):
            raise ValueError("Verified strategy candidate candidate_url must be public")
        if record["http_status"] < 200 or record["http_status"] >= 400:
            raise ValueError("Verified strategy candidate http_status must be 200-399")
        if not _is_nonzero_hash(record["metadata_hash"]):
            raise ValueError("Verified strategy candidate metadata_hash must be non-empty")
        if record["source_category"] not in SOURCE_CATEGORIES:
            raise ValueError("Verified strategy candidate source_category must be supported")
    if record["metadata_hash"] != _hash_json(_metadata_material(record)):
        raise ValueError(f"metadata_hash mismatch for {record['strategy_candidate_id']}")
    if record["strategy_candidate_root"] != _hash_json(_candidate_root_material(record)):
        raise ValueError(f"root mismatch for {record['strategy_candidate_id']}")


def validate_strategy_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Strategy refusal fields changed unexpectedly")
    for field_name in (
        "strategy_refusal_id",
        "registry_target_id",
        "source_name",
        "source_category",
        "platform",
        "strategy_name",
        "query",
        "candidate_url",
        "content_type",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "StrategyRefusal")
    if refusal["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {refusal['source_category']}")
    if refusal["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {refusal['platform']}")
    if refusal["refusal_code"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if not refusal["refusal_code"].startswith("REFUSED_"):
        raise ValueError("Strategy refusal code must be a REFUSED_* status")
    if refusal["manual_review_required"] is not True:
        raise ValueError("StrategyRefusal.manual_review_required must be true")
    if not isinstance(refusal["http_status"], int):
        raise ValueError("StrategyRefusal.http_status must be an integer")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['strategy_refusal_id']}")


def _validate_registry_source(source: Dict[str, Any], object_name: str) -> None:
    if "registry_source_root" in source:
        if set(source.keys()) != set(VALIDATED_SOURCE_FIELDS):
            raise ValueError(f"{object_name} fields changed unexpectedly")
    else:
        required_fields = set(REGISTRY_SOURCE_FIELDS)
        optional_fields = set(APPLIED_REGISTRY_OPTIONAL_FIELDS)
        source_fields = set(source.keys())
        if not required_fields <= source_fields or source_fields - required_fields - optional_fields:
            raise ValueError(f"{object_name} fields changed unexpectedly")
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
        _require_nonempty_string(source, field_name, object_name)
    if source["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {source['source_category']}")
    if source["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {source['platform']}")
    if not isinstance(source.get("trust_tier"), int) or source["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError(f"{object_name}.trust_tier must be 1-4")
    if source.get("manual_review_required") is not True:
        raise ValueError(f"{object_name}.manual_review_required must remain true")


def _validate_upstream(
    registry_input: Dict[str, Any],
    validated_registry: Dict[str, Any],
    discovery_summary: Dict[str, Any],
    discovery_refusals: Dict[str, Any],
    research_summary_path: Path,
    discovery_seeds: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not registry_input:
        raise ValueError("source registry input is missing")
    if not validated_registry:
        raise ValueError("validated source registry output is missing")
    if not discovery_summary:
        raise ValueError("registry source discovery summary is missing")
    if not discovery_refusals:
        raise ValueError("registry source discovery refusals output is missing")
    if not research_summary_path.exists() or not research_summary_path.read_text(encoding="utf-8").strip():
        raise ValueError("research summary Markdown is missing or empty")
    if not discovery_seeds:
        raise ValueError("discovery seed input is missing")
    if registry_input.get("registry_version") != UPSTREAM_REGISTRY_SCHEMA_VERSION:
        raise ValueError("source registry input version is invalid")
    if validated_registry.get("schema_version") != UPSTREAM_REGISTRY_SCHEMA_VERSION:
        raise ValueError("validated source registry schema is invalid")
    if validated_registry.get("source_registry_status") != "CANONICAL_SOURCE_REGISTRY_CANDIDATE":
        raise ValueError("validated source registry status is invalid")
    if not _closed_flags(validated_registry):
        raise ValueError("validated source registry guardrails must remain closed")
    if not _closed_flags(discovery_summary):
        raise ValueError("registry source discovery guardrails must remain closed")
    for counter_name in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if discovery_summary.get(counter_name) != 0:
            raise ValueError(f"registry source discovery {counter_name} must be 0")
    if discovery_summary.get("registry_source_discovery_status") not in (
        "REGISTRY_SOURCE_DISCOVERY_DEMO_CANDIDATE",
        "REGISTRY_SOURCE_DISCOVERY_CANDIDATE",
        "REGISTRY_SOURCE_DISCOVERY_PARTIAL",
        "REGISTRY_SOURCE_DISCOVERY_REFUSED",
    ):
        raise ValueError("registry source discovery status is invalid")
    registry_sources = registry_input.get("registry_sources")
    validated_sources = validated_registry.get("validated_source_registry")
    if not isinstance(registry_sources, list) or len(registry_sources) != 20:
        raise ValueError("source registry input must contain 20 sources")
    if not isinstance(validated_sources, list) or len(validated_sources) != 20:
        raise ValueError("validated source registry must contain 20 sources")
    seed_records = discovery_seeds.get("discovery_seeds")
    if not isinstance(seed_records, list) or len(seed_records) != 60:
        raise ValueError("discovery seed input must contain 60 seeds")
    refusal_records = discovery_refusals.get("registry_source_discovery_refusals")
    if not isinstance(refusal_records, list):
        raise ValueError("registry source discovery refusals must be a list")
    input_ids = [source.get("registry_source_id") for source in registry_sources]
    validated_ids = [source.get("registry_source_id") for source in validated_sources]
    if input_ids != validated_ids:
        raise ValueError("validated registry source order must match registry input")
    for source in registry_sources:
        _validate_registry_source(source, "RegistrySource")
    for source in validated_sources:
        _validate_registry_source(source, "ValidatedRegistrySource")
    return validated_sources


def _make_probe_spec(
    source: Dict[str, Any],
    strategy_name: str,
    query: str,
    candidate_url: str,
    verifiable_endpoint: bool,
) -> Dict[str, Any]:
    return {
        "source": source,
        "strategy_name": strategy_name,
        "query": query,
        "candidate_url": candidate_url,
        "verifiable_endpoint": verifiable_endpoint,
    }


def _probe_specs(validated_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for source in validated_sources:
        category = source["source_category"]
        platform = source["platform"]
        name = source["source_name"]
        if category == "parliament_record":
            specs.append(
                _make_probe_spec(
                    source,
                    "direct_known_domain_probe",
                    "Botswana Parliament Duma Boko",
                    "https://parliament.gov.bw/",
                    True,
                )
            )
            specs.append(
                _make_probe_spec(
                    source,
                    "site_scoped_query_probe",
                    'site:parliament.gov.bw "Duma Boko"',
                    _duckduckgo_url('site:parliament.gov.bw "Duma Boko"'),
                    False,
                )
            )
        if category in ("official_government", "public_archive"):
            for domain in ("gov.bw", "dailynews.gov.bw"):
                specs.append(
                    _make_probe_spec(
                        source,
                        "direct_known_domain_probe",
                        f"Duma Boko Botswana government {domain}",
                        f"https://{domain}/",
                        True,
                    )
                )
            specs.append(
                _make_probe_spec(
                    source,
                    "site_scoped_query_probe",
                    'site:dailynews.gov.bw "Duma Boko"',
                    _duckduckgo_url('site:dailynews.gov.bw "Duma Boko"'),
                    False,
                )
            )
        if category == "news_publisher":
            for domain in (
                "mmegi.bw",
                "sundaystandard.info",
                "weekendpost.co.bw",
                "thegazette.news",
                "patriot.co.bw",
            ):
                specs.append(
                    _make_probe_spec(
                        source,
                        "direct_known_domain_probe",
                        f"Duma Boko {domain}",
                        f"https://{domain}/",
                        True,
                    )
                )
                specs.append(
                    _make_probe_spec(
                        source,
                        "site_scoped_query_probe",
                        f'site:{domain} "Duma Boko"',
                        _duckduckgo_url(f'site:{domain} "Duma Boko"'),
                        False,
                    )
                )
        if category == "radio_tv_broadcaster":
            specs.append(
                _make_probe_spec(
                    source,
                    "direct_known_domain_probe",
                    "Duma Boko BTV dailynews.gov.bw",
                    "https://dailynews.gov.bw/",
                    True,
                )
            )
        if platform == "youtube":
            query = "Duma Boko UDC YouTube" if category == "youtube_channel" else f"{name} YouTube"
            specs.append(
                _make_probe_spec(
                    source,
                    "platform_specific_search_url",
                    query,
                    _youtube_search_url(query),
                    False,
                )
            )
            specs.append(
                _make_probe_spec(
                    source,
                    "site_scoped_query_probe",
                    'site:youtube.com "Duma Boko" "UDC"',
                    _duckduckgo_url('site:youtube.com "Duma Boko" "UDC"'),
                    False,
                )
            )
        if platform == "facebook":
            query = "Duma Boko official Facebook" if "Duma" in name else "Umbrella for Democratic Change Facebook"
            specs.append(
                _make_probe_spec(
                    source,
                    "platform_specific_search_url",
                    query,
                    _facebook_search_url(query),
                    False,
                )
            )
        if platform == "x_twitter":
            query = "Duma Boko official" if "Duma" in name else "Botswana Parliament Duma Boko"
            specs.append(
                _make_probe_spec(
                    source,
                    "platform_specific_search_url",
                    query,
                    _x_search_url(query),
                    False,
                )
            )
        if category == "official_party":
            query = (
                "Umbrella for Democratic Change official"
                if "Umbrella" in name
                else "Duma Boko official"
            )
            specs.append(
                _make_probe_spec(
                    source,
                    "organization_speaker_probe",
                    query,
                    _duckduckgo_url(query),
                    False,
                )
            )
            specs.append(
                _make_probe_spec(
                    source,
                    "organization_speaker_probe",
                    "Umbrella for Democratic Change YouTube",
                    _youtube_search_url("Umbrella for Democratic Change YouTube"),
                    False,
                )
            )
            specs.append(
                _make_probe_spec(
                    source,
                    "organization_speaker_probe",
                    "Umbrella for Democratic Change Facebook",
                    _facebook_search_url("Umbrella for Democratic Change Facebook"),
                    False,
                )
            )
        if category == "manual_review_source":
            for query in ("Duma Boko official", "Duma Boko Mmegi"):
                specs.append(
                    _make_probe_spec(
                        source,
                        "manual_review_candidate_preservation",
                        query,
                        _bing_url(query),
                        False,
                    )
                )
        if category in ("official_government", "parliament_record"):
            query = "Botswana Parliament Duma Boko"
            specs.append(
                _make_probe_spec(
                    source,
                    "organization_speaker_probe",
                    query,
                    _google_url(query),
                    False,
                )
            )
        if category in ("news_publisher", "manual_review_source"):
            query = "Duma Boko Mmegi"
            specs.append(
                _make_probe_spec(
                    source,
                    "organization_speaker_probe",
                    query,
                    _duckduckgo_url(query),
                    False,
                )
            )
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for spec in specs:
        source = spec["source"]
        key = (
            source["registry_source_id"],
            spec["strategy_name"],
            spec["query"],
            spec["candidate_url"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped


def _fetch_url(url: str) -> Tuple[str, int, str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; RegistrySourceStrategyUpgrade/2.0; "
                "source-endpoint-discovery-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(800000)
            text = raw.decode("utf-8", errors="replace")
            return response.geturl(), int(response.status), response.headers.get("content-type", ""), text, ""
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return "", 0, "", "", str(exc)


def _is_login_required(url: str, page_text: str) -> bool:
    lowered_url = url.lower()
    lowered_text = page_text.lower()
    if any(marker in lowered_url for marker in ("/login", "login?", "/i/flow/login")):
        return True
    return any(
        marker in lowered_text
        for marker in (
            "login required",
            "sign in to continue",
            "log in to continue",
            "create an account",
        )
    )


def _probe_refusal_code(strategy_name: str) -> str:
    if strategy_name in (
        "platform_specific_search_url",
        "site_scoped_query_probe",
        "organization_speaker_probe",
        "manual_review_candidate_preservation",
    ):
        return "REFUSED_WEB_PROBE_UNAVAILABLE"
    return "REFUSED_UNREACHABLE"


def _probe_candidate(
    sequence_number: int,
    refusal_sequence_number: int,
    spec: Dict[str, Any],
    mode: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    source = spec["source"]
    strategy_name = spec["strategy_name"]
    query = spec["query"]
    candidate_url = spec["candidate_url"]
    if source["platform"] not in SUPPORTED_PLATFORMS:
        return None, _make_refusal(
            refusal_sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            0,
            UNSPECIFIED,
            "REFUSED_UNSUPPORTED_PLATFORM",
            "Registry source platform is not supported by strategy upgrade probes.",
        )
    if not _is_public_url(candidate_url):
        return None, _make_refusal(
            refusal_sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            0,
            UNSPECIFIED,
            "REFUSED_METADATA_UNVERIFIED",
            "Candidate URL is not public HTTP(S).",
        )
    if mode == "dry-run":
        return _make_candidate(
            sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            0,
            UNSPECIFIED,
            "STRATEGY_DEMO_UNVERIFIED",
            "Dry-run strategy candidate only; no live URL verification was attempted.",
        ), None
    final_url, status, content_type, page_text, error = _fetch_url(candidate_url)
    if error:
        return None, _make_refusal(
            refusal_sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            0,
            UNSPECIFIED,
            _probe_refusal_code(strategy_name),
            error,
        )
    if status < 200 or status >= 400:
        return None, _make_refusal(
            refusal_sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            status,
            content_type or UNSPECIFIED,
            _probe_refusal_code(strategy_name),
            f"Candidate probe returned HTTP status {status}.",
        )
    if _is_login_required(final_url or candidate_url, page_text):
        return None, _make_refusal(
            refusal_sequence_number,
            source,
            strategy_name,
            query,
            candidate_url,
            status,
            content_type or UNSPECIFIED,
            "REFUSED_LOGIN_REQUIRED",
            "Candidate endpoint appears to require login.",
        )
    final_candidate_url = final_url if _is_public_url(final_url) else candidate_url
    if spec["verifiable_endpoint"]:
        return _make_candidate(
            sequence_number,
            source,
            strategy_name,
            query,
            final_candidate_url,
            status,
            content_type or "UNVERIFIED_PENDING_MANUAL_REVIEW",
            "VERIFIED_REACHABLE_PUBLIC_ENDPOINT",
            "Direct source-specific endpoint probe returned a reachable public endpoint.",
        ), None
    return _make_candidate(
        sequence_number,
        source,
        strategy_name,
        query,
        final_candidate_url,
        status,
        content_type or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "DISCOVERED_REQUIRES_MANUAL_REVIEW",
        "Source-specific search candidate is reachable but remains unverified pending manual review.",
    ), None


def _status_for(mode: str, candidate_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DEMO_STATUS
    if candidate_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if candidate_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    candidates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    candidate_lines = ["- None"]
    if candidates:
        candidate_lines = []
        for candidate in candidates[:40]:
            candidate_lines.extend(
                [
                    f"- {candidate['strategy_candidate_id']}",
                    f"  - Source: {candidate['source_name']}",
                    f"  - Strategy: {candidate['strategy_name']}",
                    f"  - Candidate URL: {candidate['candidate_url']}",
                    f"  - Verification Status: {candidate['verification_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:40]:
            refusal_lines.extend(
                [
                    f"- {refusal['strategy_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_name']}",
                    f"  - Strategy: {refusal['strategy_name']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    lines = [
        "# Registry Source Discovery Strategy Upgrade v2",
        "",
        "This lane emits registry endpoint strategy candidates only. It does not "
        "extract quotes, timestamps, transcript lines, evidence packets, claims, "
        "contradictions, proof chains, or downstream reports.",
        "",
        "## Summary",
        f"- strategy_upgrade_status: {status}",
        f"- mode: {mode}",
        f"- strategy_candidate_count: {len(candidates)}",
        f"- verified_endpoint_count: {sum(1 for c in candidates if c['verification_status'] == 'VERIFIED_REACHABLE_PUBLIC_ENDPOINT')}",
        f"- manual_review_required_count: {sum(1 for c in candidates if c['manual_review_required'] is True)}",
        f"- refusal_count: {len(refusals)}",
        f"- strategy_upgrade_root: {root}",
        "",
        "## Strategy Candidates",
        *candidate_lines,
        "",
        "## Strategy Refusals",
        *refusal_lines,
        "",
        "## Guardrails",
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


def build_registry_source_discovery_strategy_upgrade(
    mode: str = "dry-run",
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
    validated_registry_path: Path = DEFAULT_VALIDATED_REGISTRY,
    discovery_summary_path: Path = DEFAULT_DISCOVERY_SUMMARY,
    discovery_refusals_path: Path = DEFAULT_DISCOVERY_REFUSALS,
    research_summary_path: Path = DEFAULT_RESEARCH_SUMMARY,
    discovery_seeds_path: Path = DEFAULT_DISCOVERY_SEEDS,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "probe-web"):
        raise ValueError("mode must be dry-run or probe-web")
    registry_input = _load_json(registry_input_path)
    validated_registry = _load_json(validated_registry_path)
    discovery_summary = _load_json(discovery_summary_path)
    discovery_refusals = _load_json(discovery_refusals_path)
    discovery_seeds = _load_json(discovery_seeds_path)
    validated_sources = _validate_upstream(
        registry_input,
        validated_registry,
        discovery_summary,
        discovery_refusals,
        research_summary_path,
        discovery_seeds,
    )
    schema = _schema()
    validate_schema(schema)

    candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for spec in _probe_specs(validated_sources):
        candidate, refusal = _probe_candidate(
            len(candidates) + 1,
            len(refusals) + 1,
            spec,
            mode,
        )
        if candidate is not None:
            validate_strategy_candidate(candidate)
            candidates.append(candidate)
        if refusal is not None:
            validate_strategy_refusal(refusal)
            refusals.append(refusal)

    candidate_roots = [candidate["strategy_candidate_root"] for candidate in candidates]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "strategy_candidate_roots": sorted(candidate_roots),
            "refusal_roots": sorted(refusal_roots),
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
    status = _status_for(mode, len(candidates), len(refusals))
    verified_endpoint_count = sum(
        1
        for candidate in candidates
        if candidate["verification_status"] == "VERIFIED_REACHABLE_PUBLIC_ENDPOINT"
    )
    manual_review_required_count = sum(
        1 for candidate in candidates if candidate["manual_review_required"] is True
    )
    report = _build_report(status, mode, candidates, refusals, root)
    summary = {
        "strategy_upgrade_status": status,
        "mode": mode,
        "strategy_candidate_count": len(candidates),
        "verified_endpoint_count": verified_endpoint_count,
        "manual_review_required_count": manual_review_required_count,
        "refusal_count": len(refusals),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "strategy_candidate_roots": candidate_roots,
        "refusal_roots": refusal_roots,
        "strategy_upgrade_schema_hash": _hash_json(schema),
        "strategy_upgrade_report_hash": _sha256_text(report),
        "strategy_upgrade_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "downstream_engines_untouched": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run":
        if summary["strategy_upgrade_status"] != DEMO_STATUS:
            raise ValueError("Dry-run must emit demo candidate status")
        if summary["strategy_candidate_count"] < 15:
            raise ValueError("Dry-run must emit at least 15 strategy candidates")
        if summary["verified_endpoint_count"] != 0:
            raise ValueError("Dry-run must not verify public endpoints")
        if summary["manual_review_required_count"] < 15:
            raise ValueError("Dry-run must keep at least 15 candidates in manual review")
        if summary["refusal_count"] != 0:
            raise ValueError("Dry-run must not emit refusals")
    if not _closed_flags(summary):
        raise ValueError("Strategy upgrade guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "strategy_upgrade_status": status,
                "strategy_candidate_count": len(candidates),
                "verified_endpoint_count": verified_endpoint_count,
                "manual_review_required_count": manual_review_required_count,
                "refusal_count": len(refusals),
                "strategy_upgrade_root": root,
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
    _write_json(CANDIDATES_OUTPUT, {"strategy_candidates": candidates})
    _write_json(REFUSALS_OUTPUT, {"strategy_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "strategy_candidates": candidates,
        "strategy_refusals": refusals,
        "schema": schema,
        "report": report,
    }
